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
# Isse database connection zyada stable ho jata hai
app.config['SECRET_KEY'] = 'jageshwar_ultimate_v30_pro'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['BILL_FOLDER'] = 'static/bills'
# Ye 4 lines speed badha dengi
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
    mobile = db.Column(db.String(15))  # Naya
    role = db.Column(db.String(20)) 
    reward_points = db.Column(db.Float, default=0.0)  # Naya
    reset_req = db.Column(db.Boolean, default=False)  # Naya
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

# class Service(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     name = db.Column(db.String(100), unique=True, nullable=False)
#     price = db.Column(db.Float, nullable=False)  # default_price ki jagah sirf price rakhein

# 1. Model aisa hona chahiye
class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    price = db.Column(db.Float, nullable=False) # Iska naam 'price' hi rakhein

# 2. Add Service ka Route aisa hona chahiye
@app.route('/add_service', methods=['POST'])
@login_required
def add_service():
    if current_user.role != 'Owner':
        return redirect(url_for('index'))
    
    name = request.form.get('name')
    # Yahan dhyan dein: 'price' wahi hona chahiye jo HTML form mein 'name' hai
    price = request.form.get('price') 
    
    if name and price:
        new_service = Service(name=name, price=float(price))
        db.session.add(new_service)
        db.session.commit()
        flash("Service added successfully!")
    
    return redirect(url_for('settings'))

class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    car_number = db.Column(db.String(20))
    car_model = db.Column(db.String(50))
    owner_name = db.Column(db.String(100))
    mobile = db.Column(db.String(15))  # Naya
    total_amount = db.Column(db.Float)
    points_earned = db.Column(db.Float, default=0.0)  # Naya
    points_redeemed = db.Column(db.Float, default=0.0)  # Naya
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

with app.app_context():
    db.create_all()
    if not User.query.filter_by(role='Owner').first():
        db.session.add(User(username='admin', password='123', role='Owner', p_stats=True))
        db.session.commit()

# --- ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = User.query.filter_by(username=request.form['username'], password=request.form['password']).first()
        if u: login_user(u); return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login'))

@app.route('/')
@login_required
# def index():
#     if current_user.role == 'Client':
#         if current_user.is_premium and datetime.now() > current_user.sub_end_date:
#             current_user.is_premium = False
#             db.session.commit()
#         bookings = Booking.query.filter_by(client_name=current_user.username).order_by(Booking.id.desc()).all()
#         pay_reqs = PaymentRequest.query.filter_by(client_id=current_user.id).order_by(PaymentRequest.id.desc()).all()
#         notices = Notice.query.filter(Notice.visible_to.in_(['All', 'Client'])).all()
#         return render_template('client_dash.html', bookings=bookings, pay_reqs=pay_reqs, notices=notices, services=Service.query.all(), plans=SubPlan.query.all())
    
    
    # if current_user.role == 'Owner' or current_user.p_stats:
    #     inc_bill = db.session.query(db.func.sum(Bill.total_amount)).scalar() or 0
    #     stats = {'clients': ClientData.query.count(), 'bills': Bill.query.count(), 'income': inc_bill}
    #     raw_reqs = PaymentRequest.query.filter_by(status='Pending').all()
    #     for r in raw_reqs:
    #         p = SubPlan.query.get(r.plan_id)
    #         pay_reqs.append({'id': r.id, 'user': r.client_username, 'plan': r.plan_name, 'details': p.details if p else ""})

    # pending_bookings = Booking.query.filter_by(status='Pending').all()
    # feedbacks = Feedback.query.order_by(Feedback.id.desc()).all()
    # return render_template('index.html', stats=stats, bookings=pending_bookings, pay_reqs=pay_reqs, services=Service.query.all(), feedbacks=feedbacks)

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
    mobile = request.form['mobile']  # Naya: Mobile number le rahe hain
    total = float(request.form['grand_total_val'])
    
    # 1. Reward Points Calculation (Har ₹100 par 1 Point)
    earned_points = total / 100
    
    # 2. ClientData Update/Add (Purana Logic + Mobile)
    client_check = ClientData.query.filter_by(car_number=car).first()
    if not client_check:
        db.session.add(ClientData(car_number=car, owner_name=owner, mobile=mobile))
    else:
        client_check.mobile = mobile # Mobile update kar rahe hain agar badla ho
    
    # 3. Items list taiyar karna (Purana Logic)
    services = request.form.getlist('service_names[]')
    prices = request.form.getlist('service_prices[]')
    discs = request.form.getlist('service_discs[]')
    totals = request.form.getlist('service_totals[]')
    items = []
    for i in range(len(services)):
        if services[i] != "Select":
            items.append({'name': services[i], 'price': prices[i], 'disc': discs[i], 'total': totals[i]})
    
    # 4. PDF Generate karna (Purana Logic)
    fname = f"Bill_{car}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    path = os.path.join(app.config['BILL_FOLDER'], fname)
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "JAGESHWAR CAR CARE", ln=True, align='C')
    # ... (PDF ka baaki design wahi rahega jo aapke paas hai) ...
    pdf.output(path)
    
    # 5. Database mein Bill Save karna (Naye columns ke saath)
    new_bill = Bill(
        car_number=car, 
        car_model=model, 
        owner_name=owner, 
        mobile=mobile, 
        total_amount=total, 
        points_earned=earned_points, # Points save ho rahe hain
        filename=fname, 
        details_json=json.dumps(items)
    )
    db.session.add(new_bill)
    
    # 6. Agar User ka Account hai, toh uske Profile mein Points jodna
    user = User.query.filter_by(username=owner).first()
    if user:
        user.reward_points += earned_points
    
    db.session.commit()
    flash(f"Bill Generated! {earned_points} Reward Points Added.")
    return redirect(url_for('index'))

@app.route('/view_bills')
@login_required
def view_bills():
    bills = Bill.query.order_by(Bill.id.desc()).all()
    today = datetime.now().date()
    start_week = today - timedelta(days=today.weekday())
    start_month = today.replace(day=1)
    t_sum = db.session.query(db.func.sum(Bill.total_amount)).filter(db.func.date(Bill.date_time) == today).scalar() or 0
    w_sum = db.session.query(db.func.sum(Bill.total_amount)).filter(db.func.date(Bill.date_time) >= start_week).scalar() or 0
    m_sum = db.session.query(db.func.sum(Bill.total_amount)).filter(db.func.date(Bill.date_time) >= start_month).scalar() or 0
    return render_template('view_bills.html', bills=bills, t_sum=t_sum, w_sum=w_sum, m_sum=m_sum)

# @app.route('/settings', methods=['GET', 'POST'])
# @login_required
# def settings():
#     if current_user.role != 'Owner': return "Denied"
#     if request.method == 'POST':
#         act = request.form.get('action')
#         if act == 'add_service': db.session.add(Service(name=request.form['name'], default_price=request.form['price']))
#         elif act == 'add_plan':
#             f = request.files['qr_image']
#             fname = secure_filename(f.filename)
#             f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
#             db.session.add(SubPlan(name=request.form['name'], price=request.form['price'], details=request.form['details'], qr_image=fname))
#         elif act == 'add_notice': db.session.add(Notice(title=request.form['title'], content=request.form['content'], visible_to=request.form['visible'], color=request.form['color']))
#         db.session.commit(); flash("Added!")
#     return render_template('settings.html', services=Service.query.all(), plans=SubPlan.query.all(), notices=Notice.query.all())

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if current_user.role != 'Owner': return "Denied"
    if request.method == 'POST':
        act = request.form.get('action')
        
        # YAHAN BADLAV HAI: 'default_price' ki jagah sirf 'price' likhna hai
        if act == 'add_service': 
            name = request.form.get('name')
            price = request.form.get('price')
            if name and price:
                db.session.add(Service(name=name, price=float(price)))
        
        elif act == 'add_plan':
            f = request.files['qr_image']
            if f:
                fname = secure_filename(f.filename)
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                db.session.add(SubPlan(name=request.form['name'], price=request.form['price'], details=request.form['details'], qr_image=fname))
        
        elif act == 'add_notice': 
            db.session.add(Notice(title=request.form['title'], content=request.form['content'], visible_to=request.form['visible'], color=request.form['color']))
            
        db.session.commit()
        flash("Added successfully!")
        return redirect(url_for('settings')) # Refresh taaki data dikhe

    return render_template('settings.html', services=Service.query.all(), plans=SubPlan.query.all(), notices=Notice.query.all())

@app.route('/')
@login_required
def index():
    # 1. Reset requests check karne ke liye (Naya Logic)
    resets = User.query.filter_by(reset_req=True).all()
    
    # 2. Aapka purana counting wala logic (Bills, Revenue etc.)
    bills = Bill.query.all()
    total_revenue = sum(b.total_amount for b in bills)
    total_bills = len(bills)
    total_clients = len(ClientData.query.all())

    # Sab kuch ek saath bhej rahe hain
    return render_template('index.html', 
                           users_with_reset_req=resets, 
                           total_revenue=total_revenue, 
                           total_bills=total_bills, 
                           total_clients=total_clients)

@app.route('/delete/<string:type>/<int:id>')
@login_required
def delete_item(type, id):
    m = {'plan':SubPlan, 'service':Service, 'notice':Notice, 'user':User, 'booking':Booking, 'payreq':PaymentRequest, 'feedback':Feedback}[type]
    item = m.query.get(id)
    if item:
        # Security: Client can only delete their own booking/request
        if current_user.role == 'Client' and type in ['booking', 'payreq']:
            if hasattr(item, 'client_name') and item.client_name != current_user.username: return "Unauthorized"
            if hasattr(item, 'client_id') and item.client_id != current_user.id: return "Unauthorized"
        db.session.delete(item); db.session.commit()
    return redirect(request.referrer)

@app.route('/booking_action', methods=['POST'])
def booking_action():
    b = Booking.query.get(request.form['id'])
    b.status, b.admin_note = request.form['status'], request.form['note']
    db.session.commit(); return redirect(url_for('index'))

@app.route('/book_slot', methods=['POST'])
def book_slot():
    db.session.add(Booking(client_name=current_user.username, car_number=request.form['car'], service_name=request.form['service'], slot_time=request.form['slot']))
    db.session.commit(); flash("Slot Request Sent!"); return redirect(url_for('index'))

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    db.session.add(Feedback(client_name=current_user.username, rating=request.form['rating'], comment=request.form['comment']))
    db.session.commit(); flash("Feedback Shared!"); return redirect(url_for('index'))

@app.route('/request_sub/<int:plan_id>')
def request_sub(plan_id):
    p = SubPlan.query.get(plan_id)
    PaymentRequest.query.filter_by(client_id=current_user.id, status='Pending').delete()
    db.session.add(PaymentRequest(client_id=current_user.id, client_username=current_user.username, plan_id=p.id, plan_name=p.name))
    db.session.commit(); flash("Plan Request Sent!"); return redirect(url_for('index'))

@app.route('/view_pdf/<filename>')
def view_pdf(filename): return send_from_directory(app.config['BILL_FOLDER'], filename)

@app.route('/clients')
def clients(): return render_template('clients.html', clients=ClientData.query.all())

@app.route('/track_history', methods=['GET', 'POST'])
def track_history():
    bills = None
    if request.method == 'POST':
        car_no = request.form.get('car_number').upper()
        mob = request.form.get('mobile')
        # Matching Car Number and Mobile
        bills = Bill.query.filter_by(car_number=car_no, mobile=mob).order_by(Bill.id.desc()).all()
        if not bills:
            flash("No service history found for this Car and Mobile number.")
            
    return render_template('track_history.html', bills=bills)

@app.route('/send_reminder/<int:bill_id>/<string:rem_type>')
@login_required
def send_reminder(bill_id, rem_type):
    if current_user.role != 'Owner': return "Denied"
    
    bill = Bill.query.get(bill_id)
    if not bill:
        flash("Bill not found!")
        return redirect(request.referrer)
    
    # Message taiyar karna
    msg = f"Reminder: Hello {bill.owner_name}, your car {bill.car_number} is due for a {rem_type}. - Jageshwar Car Care"
    
    # Abhi ke liye hum sirf screen par flash karenge
    flash(f"Notification Sent: {msg}")
    
    # Tip: Yahan aap WhatsApp ka link bhi generate kar sakte hain:
    # https://wa.me/{bill.mobile}?text={msg}
    
    return redirect(request.referrer)

@app.route('/request_password_reset', methods=['POST'])
def request_password_reset():
    uname = request.form.get('username')
    user = User.query.filter_by(username=uname).first()
    if user:
        user.reset_req = True # Humne SQL mein ye column banaya tha
        db.session.commit()
        flash("Reset request sent to Admin. Please wait for approval.")
    else:
        flash("Username not found.")
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # SAKHT FIX: Sirf admin account check hoga.
        # Agar koi 'team' ya 'client' banane ka code niche tha, toh use maine hata diya hai.
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', password='123', role='Owner')
            db.session.add(admin)
            db.session.commit()
            
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
