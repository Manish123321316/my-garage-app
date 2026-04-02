from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from fpdf import FPDF
from werkzeug.utils import secure_filename
import os
import json
from datetime import datetime, timedelta

app = Flask(__name__)

# --- Configuration ---
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
    mobile = db.Column(db.String(15))
    role = db.Column(db.String(20)) 
    reward_points = db.Column(db.Float, default=0.0)
    reset_req = db.Column(db.Boolean, default=False)
    p_stats = db.Column(db.Boolean, default=False)
    is_premium = db.Column(db.Boolean, default=False)
    plan_name = db.Column(db.String(100))
    sub_start_date = db.Column(db.DateTime)
    sub_end_date = db.Column(db.DateTime)
    admin_reply = db.Column(db.String(200))

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

class ClientData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    car_number = db.Column(db.String(20), unique=True)
    owner_name = db.Column(db.String(100))
    mobile = db.Column(db.String(15))

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    price = db.Column(db.Float, nullable=False)

class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    car_number = db.Column(db.String(20))
    car_model = db.Column(db.String(50))
    owner_name = db.Column(db.String(100))
    mobile = db.Column(db.String(15))
    total_amount = db.Column(db.Float)
    points_earned = db.Column(db.Float, default=0.0)
    details_json = db.Column(db.Text)
    filename = db.Column(db.String(200))
    date_time = db.Column(db.DateTime, default=datetime.now)

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

@app.route('/')
@login_required
def index():
    if current_user.role == 'Client':
        bookings = Booking.query.filter_by(client_name=current_user.username).all()
        return render_template('client_dash.html', bookings=bookings, services=Service.query.all(), plans=SubPlan.query.all(), notices=Notice.query.all())
    
    # Admin Stats (Dhyan se saare variables bhej rahe hain)
    inc_bill = db.session.query(db.func.sum(Bill.total_amount)).scalar() or 0
    stats = {'clients': ClientData.query.count(), 'bills': Bill.query.count(), 'income': inc_bill}
    resets = User.query.filter_by(reset_req=True).all()
    pending_bookings = Booking.query.filter_by(status='Pending').all()
    pay_reqs = PaymentRequest.query.filter_by(status='Pending').all()
    all_feedbacks = Feedback.query.order_by(Feedback.id.desc()).all()

    return render_template('index.html', 
                           stats=stats, 
                           users_with_reset_req=resets, 
                           bookings=pending_bookings, 
                           pay_reqs=pay_reqs, 
                           feedbacks=all_feedbacks, 
                           notices=Notice.query.all())

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = User.query.filter_by(username=request.form['username'], password=request.form['password']).first()
        if u: login_user(u); return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login'))

@app.route('/generate_bill', methods=['POST'])
@login_required
def generate_bill():
    car = request.form['car_number'].upper()
    model = request.form.get('car_model', '')
    owner = request.form['owner_name']
    mobile = request.form['mobile']
    total = float(request.form['grand_total_val'])
    
    # Client Management
    c = ClientData.query.filter_by(car_number=car).first()
    if not c: db.session.add(ClientData(car_number=car, owner_name=owner, mobile=mobile))
    else: c.mobile = mobile
    
    # --- DISCOUNT & ITEMS LOGIC ---
    s_names = request.form.getlist('service_names[]')
    s_prices = request.form.getlist('service_prices[]')
    s_discs = request.form.getlist('service_discs[]')
    s_totals = request.form.getlist('service_totals[]')
    
    items = []
    for i in range(len(s_names)):
        if s_names[i] != "Select":
            items.append({
                'name': s_names[i], 
                'price': s_prices[i], 
                'disc': s_discs[i], 
                'total': s_totals[i]
            })
    
    fname = f"Bill_{car}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    path = os.path.join(app.config['BILL_FOLDER'], fname)
    
    # PDF generation
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "JAGESHWAR CAR CARE", ln=True, align='C')
    pdf.output(path)
    
    # Save Bill
    new_bill = Bill(car_number=car, car_model=model, owner_name=owner, mobile=mobile, 
                    total_amount=total, points_earned=total/100, filename=fname, 
                    details_json=json.dumps(items))
    
    # Update User Points if exists
    u = User.query.filter_by(username=owner).first()
    if u: u.reward_points += (total/100)
    
    db.session.add(new_bill); db.session.commit()
    flash("Bill Generated Successfully!")
    return redirect(url_for('index'))

@app.route('/view_bills')
@login_required
def view_bills():
    bills = Bill.query.order_by(Bill.id.desc()).all()
    t_sum = db.session.query(db.func.sum(Bill.total_amount)).filter(db.func.date(Bill.date_time) == datetime.now().date()).scalar() or 0
    return render_template('view_bills.html', bills=bills, t_sum=t_sum)

@app.route('/users')
@login_required
def manage_users():
    if current_user.role != 'Owner': return "Access Denied"
    return render_template('manage_users.html', users=User.query.all())

@app.route('/clients')
@login_required
def clients_list():
    return render_template('clients.html', clients=ClientData.query.all())

@app.route('/track_history', methods=['GET', 'POST'])
def track_history():
    bills = None
    if request.method == 'POST':
        car = request.form.get('car_number').upper()
        mob = request.form.get('mobile')
        bills = Bill.query.filter_by(car_number=car, mobile=mob).order_by(Bill.id.desc()).all()
    return render_template('track_history.html', bills=bills)

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if current_user.role != 'Owner': return "Denied"
    if request.method == 'POST':
        act = request.form.get('action')
        if act == 'add_service':
            db.session.add(Service(name=request.form['name'], price=float(request.form['price'])))
        elif act == 'add_plan':
            f = request.files.get('qr_image')
            fn = secure_filename(f.filename) if f else "default.png"
            if f: f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
            db.session.add(SubPlan(name=request.form['name'], price=request.form['price'], 
                                  details=request.form['details'], qr_image=fn))
        elif act == 'add_notice':
            db.session.add(Notice(title=request.form['title'], content=request.form['content'], 
                                  visible_to=request.form['visible'], color=request.form['color']))
        db.session.commit(); flash("Settings Updated!")
        return redirect(url_for('settings'))
    return render_template('settings.html', services=Service.query.all(), 
                           plans=SubPlan.query.all(), notices=Notice.query.all())

@app.route('/approve_sub', methods=['POST'])
@login_required
def approve_sub():
    req = PaymentRequest.query.get(request.form['req_id'])
    u = User.query.get(req.client_id)
    if request.form['action'] == 'approve':
        req.status = 'Approved'; u.is_premium = True; u.plan_name = req.plan_name
        u.sub_start_date = datetime.now()
        u.sub_end_date = datetime.now() + timedelta(days=30)
    else:
        req.status = 'Rejected'
    db.session.commit(); flash("Subscription Updated!"); return redirect(url_for('index'))

@app.route('/delete/<string:type>/<int:id>')
@login_required
def delete_item(type, id):
    m = {'plan':SubPlan, 'service':Service, 'notice':Notice, 'user':User, 'booking':Booking, 'payreq':PaymentRequest, 'feedback':Feedback}[type]
    item = m.query.get(id)
    if item and not (type == 'user' and item.username == 'admin'):
        db.session.delete(item); db.session.commit()
    return redirect(request.referrer or url_for('index'))

@app.route('/book_slot', methods=['POST'])
@login_required
def book_slot():
    db.session.add(Booking(client_name=current_user.username, car_number=request.form['car'], 
                           service_name=request.form['service'], slot_time=request.form['slot']))
    db.session.commit(); flash("Slot Requested!"); return redirect(url_for('index'))

@app.route('/view_pdf/<filename>')
def view_pdf(filename): return send_from_directory(app.config['BILL_FOLDER'], filename)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(username='admin', password='123', role='Owner', p_stats=True))
            db.session.commit()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
