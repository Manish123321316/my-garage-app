import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///garage_v30_final.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='Client') # Owner, Team, Client
    is_premium = db.Column(db.Boolean, default=False)
    plan_name = db.Column(db.String(50))
    sub_start_date = db.Column(db.DateTime)
    sub_end_date = db.Column(db.DateTime)
    mobile = db.Column(db.String(15))

class SubPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    price = db.Column(db.Float)
    duration_days = db.Column(db.Integer)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Routes ---

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/create_bill')
@login_required
def create_bill():
    # Owner aur Team dono bill bana sakte hain
    if current_user.role not in ['Owner', 'Team']:
        return redirect(url_for('index'))
    return render_template('create_bill.html')

@app.route('/clients')
@login_required
def clients():
    if current_user.role != 'Owner':
        flash("Access Denied!")
        return redirect(url_for('index'))
    users = User.query.filter_by(role='Client').all()
    return render_template('clients.html', users=users)

@app.route('/admin_subs')
@login_required
def admin_subs():
    if current_user.role != 'Owner':
        return redirect(url_for('index'))
    premium_users = User.query.filter_by(role='Client', is_premium=True).all()
    total_rev = sum([SubPlan.query.filter_by(name=u.plan_name).first().price for u in premium_users if SubPlan.query.filter_by(name=u.plan_name).first()])
    return render_template('admin_subs.html', users=premium_users, revenue=total_rev, datetime=datetime)

@app.route('/manage_users')
@login_required
def manage_users():
    if current_user.role != 'Owner':
        return redirect(url_for('index'))
    all_users = User.query.all()
    return render_template('manage_users.html', users=all_users)

# --- Database Initialization ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Fresh Start: Sirf admin rahega
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', password='123', role='Owner')
            db.session.add(admin)
            db.session.commit()
            
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
