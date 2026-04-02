from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from fpdf import FPDF
from werkzeug.utils import secure_filename
import os
import json
from datetime import datetime, timedelta

app = Flask(__name__)

# Config
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://neondb_owner:npg_L40ycfqeIAGF@ep-fragrant-term-a1v7voar-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'jageshwar_ultimate_v30_pro'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['BILL_FOLDER'] = 'static/bills'
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True, "pool_recycle": 300}

db = SQLAlchemy(app)

for folder in [app.config['UPLOAD_FOLDER'], app.config['BILL_FOLDER']]:
    os.makedirs(folder, exist_ok=True)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(50))
    role = db.Column(db.String(20)) 
    p_stats = db.Column(db.Boolean, default=False)
    is_premium = db.Column(db.Boolean, default=False)
    plan_name = db.Column(db.String(100))
    sub_start_date = db.Column(db.DateTime)
    sub_end_date = db.Column(db.DateTime)
    admin_reply = db.Column(db.String(200))

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    price = db.Column(db.Float, nullable=False)

class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    car_number = db.Column(db.String(20))
    car_model = db.Column(db.String(50))
    owner_name = db.Column(db.String(100))
    total_amount = db.Column(db.Float)
    details_json = db.Column(db.Text)
    filename = db.Column(db.String(200))
    date_time = db.Column(db.DateTime, default=datetime.now)

class ClientData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    car_number = db.Column(db.String(20), unique=True)
    owner_name = db.Column(db.String(100))
    mobile = db.Column(db.String(15))

class SubPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    price = db.Column(db.Float)
    details = db.Column(db.Text)
    qr_image = db.Column(db.String(200))

class PaymentRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer)
    client_username = db.Column(db.String(100))
    plan_id = db.Column(db.Integer)
    plan_name = db.Column(db.String(100))
    status = db.Column(db.String(20), default="Pending")
    request_date = db.Column(db.DateTime, default=datetime.now)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(100))
    car_number = db.Column(db.String(20))
    service_name = db.Column(db.String(100))
    slot_time = db.Column(db.String(50))
    status = db.Column(db.String(20), default="Pending")
    admin_note = db.Column(db.String(200), default="")

class Notice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    content = db.Column(db.Text)
    visible_to = db.Column(db.String(20)) 
    color = db.Column(db.String(10))

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(100))
    rating = db.Column(db.Integer)
    comment = db.Column(db.Text)
    date_time = db.Column(db.DateTime, default=datetime.now)

@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))

# --- ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = User.query.filter_by(username=request.form['username'], password=request.form['password']).first()
        if u: login_user(u); return redirect(url_for('index_dashboard'))
    return render_template('login.html')

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login'))

# Function name changed to index_dashboard to avoid duplicate errors
@app.route('/')
@login_required
def index_dashboard():
    stats = {'clients': 0, 'bills': 0, 'income': 0}
    pay_reqs = []
    
    if current_user.role == 'Client':
        if current_user.is_premium and current_user.sub_end_date and datetime.now() > current_user.sub_end_date:
            current_user.is_premium = False
            db.session.commit()
        bookings = Booking.query.filter_by(client_name=current_user.username).order_by(Booking.id.desc()).all()
        p_reqs = PaymentRequest.query.filter_by(client_id=current_user.id).order_by(PaymentRequest.id.desc()).all()
        notices = Notice.query.filter(Notice.visible_to.in_(['All', 'Client'])).all()
        return render_template('client_dash.html', bookings=bookings, pay_reqs=p_reqs, notices=notices, services=Service.query.all(), plans=SubPlan.query.all())
    
    if current_user.role == 'Owner' or current_user.p_stats:
        try:
            inc_bill = db.session.query(db.func.sum(Bill.total_amount)).scalar() or 0
            stats = {'clients': ClientData.query.count(), 'bills': Bill.query.count(), 'income': inc_bill}
            raw_reqs = PaymentRequest.query.filter_by(status='Pending').all()
            for r in raw_reqs:
                p = SubPlan.query.get(r.plan_id)
                pay_reqs.append({'id': r.id, 'user': r.client_username, 'plan': r.plan_name, 'details': p.details if p else ""})
        except: pass

    pending_bookings = Booking.query.filter_by(status='Pending').all()
    feedbacks = Feedback.query.order_by(Feedback.id.desc()).all()
    return render_template('index.html', stats=stats, bookings=pending_bookings, pay_reqs=pay_reqs, services=Service.query.all(), feedbacks=feedbacks)

@app.route('/clients')
@login_required
def clients_view():
    return render_template('clients.html', clients=ClientData.query.all())

@app.route('/generate_bill', methods=['POST'])
@login_required
def generate_bill():
    try:
        car = request.form['car_number'].upper()
        owner = request.form['owner_name']
        total = float(request.form.get('grand_total_val', 0))
        
        if not ClientData.query.filter_by(car_number=car).first():
            db.session.add(ClientData(car_number=car, owner_name=owner, mobile=request.form.get('mobile', '')))
        
        db.session.add(Bill(car_number=car, owner_name=owner, total_amount=total))
        db.session.commit()
        flash("Bill Generated Successfully!")
    except: flash("Error generating bill")
    return redirect(url_for('index_dashboard'))

@app.route('/view_bills')
@login_required
def view_bills():
    return render_template('view_bills.html', bills=Bill.query.order_by(Bill.id.desc()).all())

@app.route('/users')
@login_required
def manage_users():
    if current_user.role != 'Owner': return "Denied"
    return render_template('manage_users.html', users=User.query.all())

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(username='admin', password='123', role='Owner', p_stats=True))
            db.session.commit()
            
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
