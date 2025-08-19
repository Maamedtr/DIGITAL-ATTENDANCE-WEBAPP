from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, current_user, login_required
from app.models import User
from app.extensions import db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            if not user.is_approved and user.role != 'admin':
                flash('Your account is pending approval.', 'warning')
                return redirect(url_for('auth.login'))
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for(f"{user.role}.{'admin_dashboard' if user.role == 'admin' else user.role + '_dashboard'}"))
        else:
            flash('Invalid credentials.', 'danger')
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        role = request.form['role']
        errors = []
        # Username validation
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        # Email validation
        if not email or '@' not in email:
            errors.append('A valid email is required.')
        if role == 'student' and not email.endswith('@st.ug.edu.gh'):
            errors.append('Students must use @st.ug.edu.gh email.')
        if role in ['lecturer', 'ta'] and not email.endswith('@staff.ug.edu.gh'):
            errors.append('Staff must use @staff.ug.edu.gh email.')
        # Password validation
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        # Uniqueness check
        if User.query.filter((User.username == username) | (User.email == email)).first():
            errors.append('Username or email already exists.')
        if errors:
            for error in errors:
                flash(error, 'danger')
            return redirect(url_for('auth.register'))
        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            role=role,
            is_approved=False
        )
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Await admin approval.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html')
