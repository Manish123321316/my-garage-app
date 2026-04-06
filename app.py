from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from fpdf import FPDF
from werkzeug.utils import secure_filename
import os
import json
from datetime import datetime, timedelta
from sqlalchemy import func
import urllib.parse
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import random # OTP generate karne ke liye
from flask import session # OTP ko yaad rakhne ke liye
import threading



app = Flask(__name__)
# Mail settings
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True 
app.config['MAIL_USERNAME'] = 'manish.b2bdesign@gmail.com'
app.config['MAIL_PASSWORD'] = 'xeuypqevcyligqaw' # <-- YAHAN SPACES HATA DIYE HAIN
app.config['MAIL_DEFAULT_SENDER'] = ('Jageshwar Car Care', 'manish.b2bdesign@gmail.com')

mail = Mail(app)
# app.py mein top par
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000 # 1 Year cache
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
    "pool_size": 10,          # Connections pehle se open rahenge
    "max_overflow": 20,       # Load badhne par extra connections
    "pool_pre_ping": True,
    "pool_recycle": 60,
    
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
        # Commit mat karo, bas object update karke chhod do. 
        # Jab aap koi aur kaam (like bill generate ya status update) karoge, 
        # tab ye apne aap save ho jayega. Speed par asar nahi padega.
        current_user.last_seen = datetime.now()


# --- Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(200)) # Hash ke liye length badha di hai
    role = db.Column(db.String(20)) 
    name = db.Column(db.String(100))    # <-- Ye Naya Hai
    mobile = db.Column(db.String(15))  # <-- Ye Naya Hai
    p_stats = db.Column(db.Boolean, default=False)
    is_premium = db.Column(db.Boolean, default=False)
    plan_name = db.Column(db.String(100))
    sub_start_date = db.Column(db.DateTime)
    sub_end_date = db.Column(db.DateTime)
    admin_reply = db.Column(db.String(200))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    is_verified = db.Column(db.Boolean, default=False)

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
    mobile = db.Column(db.String(20)) # <-- Ye line add kar do
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
        user = User.query.filter_by(username=username).first()

        # 1. Password check karo
        if user and user.password == password:
            
            # 2. AGAR USER OWNER HAI -> TOH OTP BHEJO
            if user.role == 'Owner':
                otp = str(random.randint(100000, 999999))
                session['otp_check'] = otp
                session['otp_user_id'] = user.id
                
                otp_table = f"""
                <tr>
                    <td style="padding: 20px; text-align: center; background-color: #f8f9fa; border: 2px dashed #ffc107; border-radius: 10px;">
                        <span style="font-size: 32px; font-weight: bold; letter-spacing: 10px; color: #212529;">{otp}</span>
                    </td>
                </tr>
                """
                
                # --- ISKO TRY-EXCEPT MEIN DAAL DIYA TAKI ERROR NA AAYE ---
                try:
                    send_notification(
                        subject="🔐 Owner Login Verification",
                        title="Security Verification Required",
                        details_table=otp_table,
                        action_url="#",
                        action_text="Enter this code on login page"
                    )
                    flash("Owner OTP sent to your email!", "warning")
                    return redirect(url_for('verify_otp'))
                except Exception as e:
                    print(f"Email Error: {e}")
                    flash(f"Email nahi ja raha! Error: {e}", "danger")
                    # Agar email fail ho toh error dikhaye, loading na chalti rahe
                    return redirect(url_for('login'))

            # 3. AGAR NORMAL USER HAI -> DIRECT LOGIN
            login_user(user)
            return redirect(url_for('index'))

        flash("Ghalat Username ya Password!", "danger")
    return render_template('login.html')

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if 'otp_check' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        user_otp = request.form.get('otp')
        
        if user_otp == session.get('otp_check'):
            user = User.query.get(session.get('otp_user_id'))
            login_user(user)
            
            # Session saaf karo
            session.pop('otp_check', None)
            session.pop('otp_user_id', None)
            
            flash("Welcome Back, Owner!", "success")
            return redirect(url_for('index'))
        else:
            flash("Galat OTP! Fir se koshish karein.", "danger")
            
    return render_template('verify_otp.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        name = request.form.get('name')
        mobile = request.form.get('mobile')

        # 1. Khali fields check
        if not username or not password or not mobile:
            flash("Sari details bharna zaroori hai!", "danger")
            return redirect(url_for('signup'))

        # 2. Check existing mobile
        if User.query.filter_by(mobile=mobile).first():
            flash("Ye mobile number pehle se registered hai!", "danger")
            return redirect(url_for('signup'))

        # 3. Naya user object
        new_user = User(
            username=username,
            password=password, 
            role='Client',
            name=name,
            mobile=mobile,
            is_verified=False
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            
            # --- NAYA CLEAN EMAIL LOGIC ---
            # Hum sirf table ki rows bhej rahe hain
            table_rows = f"""
            <tr><td style="padding: 10px; border: 1px solid #eee; font-weight: bold; background-color: #f9f9f9;">User Name:</td><td style="padding: 10px; border: 1px solid #eee;">{new_user.username}</td></tr>
            <tr><td style="padding: 10px; border: 1px solid #eee; font-weight: bold; background-color: #f9f9f9;">Full Name:</td><td style="padding: 10px; border: 1px solid #eee;">{new_user.name}</td></tr>
            <tr><td style="padding: 10px; border: 1px solid #eee; font-weight: bold; background-color: #f9f9f9;">Mobile:</td><td style="padding: 10px; border: 1px solid #eee;">{new_user.mobile}</td></tr>
            """
            
            # Master function call (Simple and Professional)
            send_notification(
                subject="🚨 New User Request", 
                title="New Signup Pending Approval", 
                details_table=table_rows, 
                action_url=url_for('manage_users', _external=True), 
                action_text="Review & Approve User"
            )
            # ------------------------------

            flash("Request sent to Admin. Please wait 1-2 hours.", "info")
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Error: {e}")
            flash("Username pehle se maujood hai!", "danger")
            
    return render_template('signup.html')

@app.route('/client_dashboard')
@login_required
def client_dashboard():
    # Agar galti se Admin yahan aaye toh use admin dashboard pe bhej do
    if current_user.role == 'Owner' or current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
        
    # Client ko sirf uska data dikhao
    return render_template('client_dash.html') # Ye file aapke templates mein honi chahiye

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
    from datetime import datetime, timedelta
    threshold = datetime.now() - timedelta(seconds=10)
    
    # 1. Online Users
    active_clients = User.query.filter(User.last_seen >= threshold, User.role == 'Client').count()
    active_team = User.query.filter(User.last_seen >= threshold, User.role == 'Owner').count()
    active_count = active_clients + active_team

    # --- 2. CLIENT DASHBOARD LOGIC ---
    if current_user.role == 'Client':
        if current_user.is_premium and current_user.sub_end_date and datetime.now() > current_user.sub_end_date:
            current_user.is_premium = False
            db.session.commit()
            
        bookings = Booking.query.filter_by(client_name=current_user.username).order_by(Booking.id.desc()).limit(10).all()
        pay_reqs = PaymentRequest.query.filter_by(client_id=current_user.id).order_by(PaymentRequest.id.desc()).limit(5).all()
        notices = Notice.query.filter(Notice.visible_to.in_(['All', 'Client'])).all()
        
        return render_template('client_dash.html', 
                               bookings=bookings, 
                               pay_reqs=pay_reqs, 
                               notices=notices, 
                               services=Service.query.limit(10).all(), 
                               plans=SubPlan.query.all(), 
                               active_count=active_count)

    # --- 3. OWNER/ADMIN LOGIC ---
    t_rev = db.session.query(db.func.sum(Bill.total_amount)).scalar() or 0
    t_cli = ClientData.query.count()
    t_bil = Bill.query.count()
    
    # NEW: Pending Signup Requests Count (Database se check karega kitne is_verified=False hain)
    pending_signups = User.query.filter_by(is_verified=False).count()
    
    stats = {'clients': t_cli, 'bills': t_bil, 'income': t_rev, 'pending_users': pending_signups}
    
    pay_reqs_data = []
    if current_user.role == 'Owner' or current_user.p_stats:
        raw_reqs = PaymentRequest.query.filter_by(status='Pending').limit(10).all()
        for r in raw_reqs:
            p = SubPlan.query.get(r.plan_id)
            pay_reqs_data.append({
                'id': r.id, 
                'user': r.client_username, 
                'plan': r.plan_name, 
                'details': p.details if p else ""
            })

    pending_bookings = Booking.query.filter_by(status='Pending').limit(10).all()
    feedbacks = Feedback.query.order_by(Feedback.id.desc()).limit(5).all() 
    
    return render_template('index.html', 
                           active_count=active_count,
                           stats=stats, 
                           pending_count=pending_signups, 
                           bookings=pending_bookings, 
                           pay_reqs=pay_reqs_data, 
                           services=Service.query.all(),  # <--- YE LINE MISSING THI! Isko add karo
                           total_revenue=t_rev, 
                           total_clients=t_cli, 
                           total_bills=t_bil)

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

import urllib.parse  # Ye line top par imports mein check kar lena

@app.route('/approve_user/<int:user_id>')
@login_required
def approve_user(user_id):
    if current_user.role != 'Owner': return "Access Denied", 403
    user = User.query.get(user_id)
    if user:
        user.is_verified = True
        db.session.commit()
        flash(f"User {user.username} has been APPROVED!", "success")
    return redirect(url_for('manage_users'))

@app.route('/reject_user/<int:user_id>')
@login_required
def reject_user(user_id):
    if current_user.role != 'Owner': return "Access Denied", 403
    user = User.query.get(user_id)
    if user:
        db.session.delete(user) # Reject matlab data delete
        db.session.commit()
        flash(f"User {user.username} request REJECTED and deleted.", "danger")
    return redirect(url_for('manage_users'))

@app.route('/generate_bill', methods=['POST'])
@login_required
def generate_bill():
    # 1. Form se data nikaalna
    car = request.form['car_number'].upper()
    model = request.form['car_model']
    owner = request.form['owner_name']
    mobile = request.form['mobile']
    total = float(request.form['grand_total_val'])
    action_type = request.form.get('action')

    # 2. Client Data Save/Update
    if not ClientData.query.filter_by(car_number=car).first():
        db.session.add(ClientData(car_number=car, owner_name=owner, mobile=mobile))
    
    # 3. Services ki list banana
    services = request.form.getlist('service_names[]')
    prices = request.form.getlist('service_prices[]')
    discs = request.form.getlist('service_discs[]')
    totals = request.form.getlist('service_totals[]')
    
    items = []
    for i in range(len(services)):
        if services[i] != "Select":
            items.append({'name': services[i], 'price': prices[i], 'disc': discs[i], 'total': totals[i]})
    
    # 4. PDF File banana
    fname = f"Bill_{car}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    path = os.path.join(app.config['BILL_FOLDER'], fname)
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "JAGESHWAR CAR CARE", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 5, "Professional Car Service & Maintenance", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(100, 8, f"Customer: {owner}")
    pdf.cell(90, 8, f"Date: {datetime.now().strftime('%d-%m-%Y %H:%M')}", ln=True, align='R')
    pdf.cell(100, 8, f"Car No: {car}")
    pdf.cell(90, 8, f"Model: {model}", ln=True, align='R')
    pdf.ln(5)
    
    # Table Header
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(80, 10, " Service Description", 1, 0, 'L', True)
    pdf.cell(35, 10, " Price", 1, 0, 'C', True)
    pdf.cell(35, 10, " Discount %", 1, 0, 'C', True)
    pdf.cell(40, 10, " Total", 1, 1, 'C', True)
    
    pdf.set_font("Arial", '', 10)
    for item in items:
        pdf.cell(80, 10, f" {item['name']}", 1)
        pdf.cell(35, 10, f" {item['price']}", 1, 0, 'C')
        pdf.cell(35, 10, f" {item['disc']}%", 1, 0, 'C')
        pdf.cell(40, 10, f" Rs. {item['total']}", 1, 1, 'C')
        
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(150, 12, " GRAND TOTAL", 1, 0, 'R', True)
    pdf.cell(40, 12, f" Rs. {total}", 1, 1, 'C', True)
    pdf.output(path)
    
    # 5. Database Save (IMPORTANT: mobile=mobile add kiya hai)
    new_bill = Bill(
        car_number=car, 
        car_model=model, 
        owner_name=owner, 
        mobile=mobile,  # <--- Yeh line database mein number save karegi
        total_amount=total, 
        filename=fname, 
        details_json=json.dumps(items)
    )
    db.session.add(new_bill)
    db.session.commit()
    
    # 6. WHATSAPP REDIRECT (Agar 'Generate & Send' dabaya)
    if action_type == 'bill_whatsapp':
        import urllib.parse
        # Number cleaning
        clean_mobile = "".join(filter(str.isdigit, mobile))
        if len(clean_mobile) == 10: 
            clean_mobile = "91" + clean_mobile
        
        # Link taiyar karna
        base_url = f"https://{request.host}" if "render.com" in request.host else request.host_url.rstrip('/')
        bill_link = f"{base_url}/static/bills/{fname}"
        
        msg = (f"*JAGESHWAR CAR CARE*\n\n"
               f"Hello {owner},\n"
               f"Aapki gaadi *{car}* taiyar hai.\n"
               f"Total Bill: *Rs. {total}*\n\n"
               f"Download Bill: {bill_link}\n\n"
               f"Thank you!")
               
        encoded_msg = urllib.parse.quote(msg)
        whatsapp_url = f"https://wa.me/{clean_mobile}?text={encoded_msg}"
        return redirect(whatsapp_url)
    
    # Normal return agar sirf generate kiya
    flash(f"Bill Generated Successfully for {car}!")
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

@app.route('/manage_users', methods=['GET', 'POST'])
@login_required
def manage_users():
    if current_user.role != 'Owner': return "Denied"
    
    if request.method == 'POST':
        uid = request.form.get('user_id')
        
        if uid:
            # Puraane User ko Edit karna
            u = User.query.get(uid)
            u.username = request.form.get('u')
            u.password = request.form.get('p')
            u.role = request.form.get('r')
            u.mobile = request.form.get('mobile')  # Mobile number update
            u.p_stats = 'st' in request.form
            u.is_premium = 'is_p' in request.form
            
            if u.is_premium:
                u.plan_name = request.form.get('p_name')
                u.sub_end_date = datetime.now() + timedelta(days=30)
                if not u.sub_start_date: u.sub_start_date = datetime.now()
            else: 
                u.plan_name, u.is_premium = None, False
        else:
            # Naya User Create karna (Admin ke through)
            new_user = User(
                username=request.form.get('u'), 
                password=request.form.get('p'), 
                role=request.form.get('r'), 
                mobile=request.form.get('mobile'), # Mobile save karna
                p_stats='st' in request.form,
                is_verified=True  # <--- YE ZAROORI HAI (Direct Active List mein jayega)
            )
            db.session.add(new_user)
            
        db.session.commit()
        flash("User Saved Successfully!", "success")
        
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
    # 1. Booking dhoondo
    b = Booking.query.get(request.form['id'])
    
    # 2. Status update karo
    b.status = request.form['status']
    b.admin_note = request.form['note']
    db.session.commit()
    
    # 3. Professional Email Design (Master Template ke sath)
    try:
        # Table ki rows tayyar karo
        table_rows = f"""
        <tr><td style="padding: 10px; border: 1px solid #eee; font-weight: bold; background-color: #f9f9f9;">Car Number:</td><td style="padding: 10px; border: 1px solid #eee;">{b.car_no}</td></tr>
        <tr><td style="padding: 10px; border: 1px solid #eee; font-weight: bold; background-color: #f9f9f9;">New Status:</td><td style="padding: 10px; border: 1px solid #eee; color: #d9534f; font-weight: bold;">{b.status}</td></tr>
        <tr><td style="padding: 10px; border: 1px solid #eee; font-weight: bold; background-color: #f9f9f9;">Admin Note:</td><td style="padding: 10px; border: 1px solid #eee;">{b.admin_note if b.admin_note else 'N/A'}</td></tr>
        """

        # Master notification function call
        send_notification(
            subject=f"Booking Update: {b.status} 🚗", 
            title="Booking Status Changed", 
            details_table=table_rows, 
            action_url=url_for('index', _external=True), 
            action_text="View Status in Dashboard"
        )
    except Exception as e:
        print(f"❌ Email Error: {e}")

    # 4. Ab redirect karo
    flash(f"Booking {b.status} successfully!", "success")
    return redirect(url_for('index'))

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
    
    # Purani pending requests delete karna
    PaymentRequest.query.filter_by(client_id=current_user.id, status='Pending').delete()
    
    # Nayi request add karna
    new_request = PaymentRequest(
        client_id=current_user.id, 
        client_username=current_user.username, 
        plan_id=p.id, 
        plan_name=p.name
    )
    db.session.add(new_request)
    db.session.commit()

    # --- Professional Email Logic ---
    try:
        table_rows = f"""
        <tr><td style="padding: 10px; border: 1px solid #eee; font-weight: bold; background-color: #f9f9f9;">Customer:</td><td style="padding: 10px; border: 1px solid #eee;">{current_user.username}</td></tr>
        <tr><td style="padding: 10px; border: 1px solid #eee; font-weight: bold; background-color: #f9f9f9;">Plan Name:</td><td style="padding: 10px; border: 1px solid #eee;">{p.name}</td></tr>
        <tr><td style="padding: 10px; border: 1px solid #eee; font-weight: bold; background-color: #f9f9f9;">Price:</td><td style="padding: 10px; border: 1px solid #eee;">₹{p.price}</td></tr>
        """

        send_notification(
            subject="💰 Plan Purchase Request", 
            title="New Subscription Request", 
            details_table=table_rows, 
            action_url=url_for('index', _external=True), 
            action_text="Verify & Approve Payment"
        )
    except Exception as e:
        print(f"❌ Email Error: {e}")

    flash("Plan Request Sent! Admin will verify your payment soon.", "success")
    return redirect(url_for('index'))
    

@app.route('/view_pdf/<filename>')
def view_pdf(filename): return send_from_directory(app.config['BILL_FOLDER'], filename)

@app.route('/clients')
def clients(): return render_template('clients.html', clients=ClientData.query.all())

def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
            print("✅ Email Sent successfully!")
        except Exception as e:
            print(f"❌ Email Error: {e}")

def send_notification(subject, title, details_table, action_url="#", action_text="View Details"):
    msg = Message(
        subject=subject,
        recipients=['manish.b2bdesign@gmail.com'],
        html=f"<h2>{title}</h2><table border='1'>{details_table}</table><br><a href='{action_url}'>{action_text}</a>"
    )
    
    # Background mein bhejte hain taaki page load na leta rahe
    def send_email(app, msg):
        with app.app_context():
            try:
                mail.send(msg)
            except Exception as e:
                print(f"❌ Email Failed: {e}")

    # Naya rasta (Thread) shuru karo
    thread = threading.Thread(target=send_email, args=(app, msg))
    thread.start()

@app.route('/admin_dashboard')
@login_required  # <--- Ye zaroori hai!
def admin_dashboard():
    # Safety Lock: Agar role Owner nahi hai, toh bhaga do
    if current_user.role != 'Owner' and current_user.role != 'admin':
        flash("Aapko yahan aane ki ijazat nahi hai!", "danger")
        return redirect(url_for('client_dashboard'))
    # if current_user.role != 'admin':
    #     return "Access Denied! Aap admin nahi hain.", 403
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    total_revenue = db.session.query(db.func.sum(Bill.total_amount)).scalar() or 0
    total_clients = ClientData.query.count()
    total_bills = Bill.query.count()

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
