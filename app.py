from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from fpdf import FPDF
from werkzeug.utils import secure_filename
import os
import json
from datetime import datetime, timedelta

app = Flask(__name__)
# Naya Neon Database Link
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://neondb_owner:npg_L40ycfqeIAGF@ep-fragrant-term-a1v7voar-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'jageshwar_ultimate_v30_pro'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['BILL_FOLDER'] = 'static/bills'
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}
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
    points_redeemed = db.Column(db.Float, default=0.0)
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
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = User.query.filter_by(username=request.form['username'], password=request.form['password']).first()
        if u: login_user(u); return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login'))

@app.route('/approve_sub', methods=['POST'])
@login_required
def approve_sub():
    if current_user.role != 'Owner': return "Denied"
    req = PaymentRequest.query.get(request.form['req_id'])
    client = User.query.get(req.client_id)
    if request.form['action'] == 'approve':
        req.status = 'Approved'
        client.is_premium, client.plan_name = True, req.plan_name
        client.sub_start_date = datetime.now()
        client.sub_end_date = datetime.now() + timedelta(days=30)
        client.admin_reply = request.form['reply']
    else:
        req.status = 'Rejected'
        client.admin_reply = "Rejected: " + request.form['reply']
    db.session.commit(); flash("Subscription Processed!"); return redirect(url_for('index'))

@app.route('/generate_bill', methods=['POST'])
@login_required
def generate_bill():
    car = request.form['car_number'].upper()
    model = request.form['car_model']
    owner = request.form['owner_name']
    mobile = request.form['mobile']
    total = float(request.form['grand_total_val'])
    earned_points = total / 100
    client_check = ClientData.query.filter_by(car_number=car).first()
    if not client_check:
        db.session.add(ClientData(car_number=car, owner_name=owner, mobile=mobile))
    else:
        client_check.mobile = mobile
    
    services_req = request.form.getlist('service_names[]')
    prices = request.form.getlist('service_prices[]')
    discs = request.form.getlist('service_discs[]')
    totals = request.form.getlist('service_totals[]')
    items = []
    for i in range(len(services_req)):
        if services_req[i] != "Select":
            items.append({'name': services_req[i], 'price': prices[i], 'disc': discs[i], 'total': totals[i]})
    
    fname = f"Bill_{car}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    path = os.path.join(app.config['BILL_FOLDER'], fname)
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "JAGESHWAR CAR CARE", ln=True, align='C')
    pdf.output(path)
    
    new_bill = Bill(car_number=car, car_model=model, owner_name=owner, mobile=mobile, total_amount=total, points_earned=earned_points, filename=fname, details_json=json.dumps(items))
    db.session.add(new_bill)
    user = User.query.filter_by(username=owner).first()
    if user: user.reward_points += earned_points
    db.session.commit()
    flash(f"Bill Generated! {earned_points} Reward Points Added.")
    return redirect(url_for('index'))

@app.route('/view_bills')
@login_required
def view_bills():
    bills = Bill.query.order_by(Bill.id.desc()).all()
    today = datetime.now().date()
    t_sum = db.session.query(db.func.sum(Bill.total_amount)).filter(db.func.date(Bill.date_time) == today).scalar() or 0
    return render_template('view_bills.html', bills=bills, t_sum=t_sum)

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if current_user.role != 'Owner': return "Denied"
    if request.method == 'POST':
        act = request.form.get('action')
        if act == 'add_service': 
            db.session.add(Service(name=request.form.get('name'), price=float(request.form.get('price'))))
        elif act == 'add_plan':
            f = request.files['qr_image']
            if f:
                fname = secure_filename(f.filename)
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                db.session.add(SubPlan(name=request.form['name'], price=request.form['price'], details=request.form['details'], qr_image=fname))
        elif act == 'add_notice': 
            db.session.add(Notice(title=request.form['title'], content=request.form['content'], visible_to=request.form['visible'], color=request.form['color']))
        db.session.commit(); flash("Added successfully!")
        return redirect(url_for('settings'))
    return render_template('settings.html', services=Service.query.all(), plans=SubPlan.query.all(), notices=Notice.query.all())

@app.route('/')
@login_required
def index():
    if current_user.role == 'Client':
        bookings = Booking.query.filter_by(client_name=current_user.username).all()
        return render_template('client_dash.html', bookings=bookings, services=Service.query.all(), plans=SubPlan.query.all())
    
    inc_bill = db.session.query(db.func.sum(Bill.total_amount)).scalar() or 0
    stats = {'clients': ClientData.query.count(), 'bills': Bill.query.count(), 'income': inc_bill}
    resets = User.query.filter_by(reset_req=True).all()
    return render_template('index.html', stats=stats, users_with_reset_req=resets, bookings=Booking.query.filter_by(status='Pending').all(), feedbacks=Feedback.query.all())

@app.route('/delete/<string:type>/<int:id>')
@login_required
def delete_item(type, id):
    m = {'plan':SubPlan, 'service':Service, 'notice':Notice, 'user':User, 'booking':Booking, 'payreq':PaymentRequest, 'feedback':Feedback}[type]
    item = m.query.get(id)
    if item:
        db.session.delete(item); db.session.commit()
    return redirect(request.referrer)

@app.route('/booking_action', methods=['POST'])
def booking_action():
    b = Booking.query.get(request.form['id'])
    b.status, b.admin_note = request.form['status'], request.form['note']
    db.session.commit(); return redirect(url_for('index'))

@app.route('/book_slot', methods=['POST'])
@login_required
def book_slot():
    db.session.add(Booking(client_name=current_user.username, car_number=request.form['car'], service_name=request.form['service'], slot_time=request.form['slot']))
    db.session.commit(); flash("Slot Request Sent!"); return redirect(url_for('index'))

@app.route('/submit_feedback', methods=['POST'])
@login_required
def submit_feedback():
    db.session.add(Feedback(client_name=current_user.username, rating=request.form['rating'], comment=request.form['comment']))
    db.session.commit(); flash("Feedback Shared!"); return redirect(url_for('index'))

@app.route('/request_sub/<int:plan_id>')
@login_required
def request_sub(plan_id):
    p = SubPlan.query.get(plan_id)
    PaymentRequest.query.filter_by(client_id=current_user.id, status='Pending').delete()
    db.session.add(PaymentRequest(client_id=current_user.id, client_username=current_user.username, plan_id=p.id, plan_name=p.name))
    db.session.commit(); flash("Plan Request Sent!"); return redirect(url_for('index'))

@app.route('/view_pdf/<filename>')
def view_pdf(filename): return send_from_directory(app.config['BILL_FOLDER'], filename)

@app.route('/track_history', methods=['GET', 'POST'])
def track_history():
    bills = None
    if request.method == 'POST':
        car_no = request.form.get('car_number').upper()
        mob = request.form.get('mobile')
        bills = Bill.query.filter_by(car_number=car_no, mobile=mob).order_by(Bill.id.desc()).all()
    return render_template('track_history.html', bills=bills)

@app.route('/request_password_reset', methods=['POST'])
def request_password_reset():
    uname = request.form.get('username')
    user = User.query.filter_by(username=uname).first()
    if user:
        user.reset_req = True
        db.session.commit()
        flash("Reset request sent.")
    return redirect(url_for('login'))

@app.route('/users')
@login_required
def manage_users():
    if current_user.role != 'Owner': return "Denied"
    return render_template('manage_users.html', users=User.query.all())

@app.route('/delete_user/<int:id>')
@login_required
def delete_user(id):
    if current_user.role != 'Owner': return "Denied"
    u = User.query.get(id)
    if u and u.username != 'admin':
        db.session.delete(u); db.session.commit()
    return redirect(url_for('manage_users'))

@app.route('/clients')
@login_required
def manage_clients():
    if current_user.role != 'Owner': return "Denied"
    return render_template('clients.html', clients=ClientData.query.all())

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(username='admin', password='123', role='Owner', p_stats=True))
            db.session.commit()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
