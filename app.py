from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from fpdf import FPDF
from werkzeug.utils import secure_filename
import os
import json
from datetime import datetime, timedelta
from sqlalchemy import func



app = Flask(__name__)
app.config['SECRET_KEY'] = 'my-super-secret-key-123' # Ye line zaroori hai Flash messages ke liye
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

# # --- TEMPORARY DATABASE FIX ---
# with app.app_context():
#     try:
#         from sqlalchemy import text
#         # PostgreSQL ke liye direct query chala rahe hain
#         db.session.execute(text('ALTER TABLE "user" ADD COLUMN last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP'))
#         db.session.commit()
#         print("✅ Column 'last_seen' successfully added to Database!")
#     except Exception as e:
#         db.session.rollback()
#         print("⚠️ Column add nahi hua (ya shayad pehle se hai):", e)
# --- FIX END ---

for folder in [app.config['UPLOAD_FOLDER'], app.config['BILL_FOLDER']]:
    os.makedirs(folder, exist_ok=True)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@app.before_request
def update_last_seen():
    if current_user.is_authenticated:
        from datetime import datetime
        current_user.last_seen = datetime.now()
        db.session.commit()



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
    # class User(UserMixin, db.Model):
    # ... aapke purane columns ...
    admin_reply = db.Column(db.String(200))
    # Ye naya column add karo:
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

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

@app.before_request
def update_last_seen():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now()
        db.session.commit()   

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
    total_amount = db.Column(db.Float)
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
        username = request.form.get('username')
        password = request.form.get('password')

        # User ko database mein dhoondo
        u = User.query.filter_by(username=username, password=password).first()
        
        if u:
            login_user(u)
            return redirect(url_for('index'))
        else:
            # AGAR PASSWORD GALAT HAI TOH YE MESSAGE BHEJO
            flash("Opps! Galat Username ya Password.") 
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    if current_user.is_authenticated:
        # User ka time 10 minute piche kar do taaki wo turant 'Offline' ho jaye
        current_user.last_seen = datetime.now() - timedelta(minutes=10)
        db.session.commit()
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    # --- 1. ROLE-WISE LIVE USER LOGIC ---
    from datetime import datetime, timedelta
    # 30 seconds ka gap rakha hai taaki logout hote hi count gir jaye
    threshold = datetime.now() - timedelta(seconds=10)
    
    # Sirf Clients kitne online hain
    active_clients = User.query.filter(User.last_seen >= threshold, User.role == 'Client').count()
    # Sirf Team (Owner) kitne online hain
    active_team = User.query.filter(User.last_seen >= threshold, User.role == 'Owner').count()
    # Total count (Backup ke liye)
    active_count = active_clients + active_team

    # --- 2. CLIENT DASHBOARD LOGIC ---
    if current_user.role == 'Client':
        if current_user.is_premium and datetime.now() > current_user.sub_end_date:
            current_user.is_premium = False
            db.session.commit()
            
        bookings = Booking.query.filter_by(client_name=current_user.username).order_by(Booking.id.desc()).all()
        pay_reqs = PaymentRequest.query.filter_by(client_id=current_user.id).order_by(PaymentRequest.id.desc()).all()
        notices = Notice.query.filter(Notice.visible_to.in_(['All', 'Client'])).all()
        
        return render_template('client_dash.html', 
                               bookings=bookings, 
                               pay_reqs=pay_reqs, 
                               notices=notices, 
                               services=Service.query.all(), 
                               plans=SubPlan.query.all(), 
                               active_count=active_count)

    # --- 3. OWNER/ADMIN LOGIC (Stats calculation) ---
    # from app import ClientData, Bill, PaymentRequest, Booking, Feedback, SubPlan, Service # Ensure imports
    
    t_rev = db.session.query(db.func.sum(Bill.total_amount)).scalar() or 0
    t_cli = ClientData.query.count()
    t_bil = Bill.query.count()
    
    stats = {'clients': t_cli, 'bills': t_bil, 'income': t_rev}
    
    pay_reqs_data = []
    if current_user.role == 'Owner' or current_user.p_stats:
        raw_reqs = PaymentRequest.query.filter_by(status='Pending').all()
        for r in raw_reqs:
            p = SubPlan.query.get(r.plan_id)
            pay_reqs_data.append({
                'id': r.id, 
                'user': r.client_username, 
                'plan': r.plan_name, 
                'details': p.details if p else ""
            })

    pending_bookings = Booking.query.filter_by(status='Pending').all()
    feedbacks = Feedback.query.order_by(Feedback.id.desc()).all()
    
    # --- 4. FINAL RENDER (Sab variables bhej diye) ---
    return render_template('index.html', 
                           active_clients=active_clients, 
                           active_team=active_team,
                           active_count=active_count,
                           stats=stats, 
                           bookings=pending_bookings, 
                           pay_reqs=pay_reqs_data, 
                           services=Service.query.all(), 
                           feedbacks=feedbacks,
                           total_revenue=t_rev, 
                           total_clients=t_cli, 
                           total_bills=t_bil)
    # --- YAHAN TAK ---

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
    total = float(request.form['grand_total_val'])
    if not ClientData.query.filter_by(car_number=car).first():
        db.session.add(ClientData(car_number=car, owner_name=owner, mobile=request.form['mobile']))
    services = request.form.getlist('service_names[]')
    prices = request.form.getlist('service_prices[]')
    discs = request.form.getlist('service_discs[]')
    totals = request.form.getlist('service_totals[]')
    items = []
    for i in range(len(services)):
        if services[i] != "Select":
            items.append({'name': services[i], 'price': prices[i], 'disc': discs[i], 'total': totals[i]})
    fname = f"Bill_{car}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    path = os.path.join(app.config['BILL_FOLDER'], fname)
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "JAGESHWAR CAR CARE", ln=True, align='C')
    pdf.set_font("Arial", '', 10); pdf.cell(190, 5, "Professional Car Service & Maintenance", ln=True, align='C')
    pdf.ln(10); pdf.set_font("Arial", 'B', 11); pdf.cell(100, 8, f"Customer: {owner}"); pdf.cell(90, 8, f"Date: {datetime.now().strftime('%d-%m-%Y %H:%M')}", ln=True, align='R')
    pdf.cell(100, 8, f"Car No: {car}"); pdf.cell(90, 8, f"Model: {model}", ln=True, align='R')
    pdf.ln(5); pdf.set_fill_color(240, 240, 240); pdf.set_font("Arial", 'B', 10)
    pdf.cell(80, 10, " Service Description", 1, 0, 'L', True); pdf.cell(35, 10, " Price", 1, 0, 'C', True); pdf.cell(35, 10, " Discount %", 1, 0, 'C', True); pdf.cell(40, 10, " Total", 1, 1, 'C', True)
    pdf.set_font("Arial", '', 10)
    for item in items:
        pdf.cell(80, 10, f" {item['name']}", 1); pdf.cell(35, 10, f" {item['price']}", 1, 0, 'C'); pdf.cell(35, 10, f" {item['disc']}%", 1, 0, 'C'); pdf.cell(40, 10, f" Rs. {item['total']}", 1, 1, 'C')
    pdf.set_font("Arial", 'B', 12); pdf.cell(150, 12, " GRAND TOTAL", 1, 0, 'R', True); pdf.cell(40, 12, f" Rs. {total}", 1, 1, 'C', True); pdf.output(path)
    db.session.add(Bill(car_number=car, car_model=model, owner_name=owner, total_amount=total, filename=fname, details_json=json.dumps(items)))
    db.session.commit(); flash("Bill Generated!"); return redirect(url_for('index'))

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

@app.route('/manage_users', methods=['GET', 'POST'])
@login_required
def manage_users():
    if current_user.role != 'Owner': return "Denied"
    if request.method == 'POST':
        uid = request.form.get('user_id')
        if uid:
            u = User.query.get(uid)
            u.username, u.password, u.role, u.p_stats = request.form['u'], request.form['p'], request.form['r'], 'st' in request.form
            u.is_premium = 'is_p' in request.form
            if u.is_premium:
                u.plan_name, u.sub_end_date = request.form.get('p_name'), datetime.now() + timedelta(days=30)
                if not u.sub_start_date: u.sub_start_date = datetime.now()
            else: u.plan_name, u.is_premium = None, False
        else:
            db.session.add(User(username=request.form['u'], password=request.form['p'], role=request.form['r'], p_stats='st' in request.form))
        db.session.commit(); flash("User Updated!")
    return render_template('manage_users.html', users=User.query.all())

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

@app.route('/admin_dashboard')
def admin_dashboard():
    # Database se asli numbers nikalna
    total_revenue = db.session.query(db.func.sum(Bill.total_amount)).scalar() or 0
    total_clients = ClientData.query.count()
    total_bills = Bill.query.count()

    # Ye values HTML ko bhejna zaroori hai
    return render_template('admin_dashboard.html', 
                           total_revenue=total_revenue, 
                           total_clients=total_clients, 
                           total_bills=total_bills)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Admin check
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(username='admin', password='123', role='Owner', p_stats=True))
            db.session.commit()
            
    # YEH DO LINES SABSE ZAROORI HAIN RENDER KE LIYE
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# if __name__ == '__main__':
#     with app.app_context():
#         db.create_all()
        
#         # SAKHT FIX: Sirf admin account check hoga.
#         # Agar koi 'team' ya 'client' banane ka code niche tha, toh use maine hata diya hai.
#         if not User.query.filter_by(username='admin').first():
#             admin = User(username='admin', password='123', role='Owner')
#             db.session.add(admin)
#             db.session.commit()
            
#     port = int(os.environ.get("PORT", 10000))
#     app.run(host='0.0.0.0', port=port)
