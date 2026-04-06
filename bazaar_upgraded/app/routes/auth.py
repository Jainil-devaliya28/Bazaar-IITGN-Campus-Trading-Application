from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_bcrypt import Bcrypt
from ..models import db, Member, Student, Authentication
from ..helpers import log_action, log_security_event
from datetime import datetime
import os
# bazaar/app/routes/auth.py
from .. import db
from ..models import Member, Student, Authentication

auth_bp = Blueprint('auth', __name__)
bcrypt = Bcrypt()

ALLOWED_DOMAIN = 'iitgn.ac.in'


# Helper to get the google client without circular imports
def get_google_client():
    from .. import oauth  # Local import to break circularity
    
    if 'google' not in oauth._clients:
        oauth.register(
            name='google',
            client_id=os.environ.get('GOOGLE_CLIENT_ID'),
            client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'}
        )
    return oauth.google


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Email and password are required.', 'danger')
            return render_template('login.html')

        if not email.endswith(f'@{ALLOWED_DOMAIN}'):
            flash(f'Only @{ALLOWED_DOMAIN} accounts are permitted.', 'danger')
            return render_template('login.html')

        member = Member.query.filter_by(email=email).first()
        if not member or not member.auth:
            log_security_event('FAILED_LOGIN', f"Failed login: {email}", request.remote_addr, request.headers.get('User-Agent'))
            flash('Invalid email or password.', 'danger')
            return render_template('login.html')

        if not bcrypt.check_password_hash(member.auth.password_hash, password):
            log_security_event('FAILED_LOGIN', f"Failed login: {email}", request.remote_addr, request.headers.get('User-Agent'))
            flash('Invalid email or password.', 'danger')
            return render_template('login.html')

        member.auth.last_login = datetime.utcnow()
        db.session.commit()

        session['member_id'] = member.member_id
        session['name']      = member.name
        session['role']      = member.role

        log_action('LOGIN', f'User logged in: {email}', member.member_id)
        flash(f'Welcome back, {member.name}!', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    member_id = session.get('member_id')
    log_action('LOGOUT', 'User logged out', member_id)
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/login/google')
def google_login():
    google = get_google_client()
    redirect_uri = url_for('auth.google_authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@auth_bp.route('/auth/google/callback')
def google_authorize():
    google = get_google_client()
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    
    if not user_info:
        flash('Google login failed.', 'danger')
        return redirect(url_for('auth.login'))

    email = user_info.get('email').lower()
    name = user_info.get('name')

    if not email.endswith(f'@{ALLOWED_DOMAIN}'):
        flash(f'Only @{ALLOWED_DOMAIN} accounts are allowed.', 'danger')
        return redirect(url_for('auth.login'))

    member = Member.query.filter_by(email=email).first()

    # In google_authorize, find the "if not member:" block and update it:
    if not member:
        member = Member(name=name, email=email, role='user', hostel=None, wing=None)
        db.session.add(member)
        db.session.flush()
        student = Student(member_id=member.member_id, college_name='IIT Gandhinagar')
        db.session.add(student)
        db.session.commit()
        log_action('INSERT', f'New user registered via Google: {email}', member.member_id)
        session['member_id'] = member.member_id
        session['name'] = member.name
        session['role'] = member.role
        flash(f'Welcome to Bazaar@IITGN, {member.name}! Please complete your profile.', 'success')
        return redirect(url_for('main.edit_profile'))  # Send new users to fill hostel/wing

    session['member_id'] = member.member_id
    session['name'] = member.name
    session['role'] = member.role
    
    log_action('LOGIN', f'User logged in via Google: {email}', member.member_id)
    flash(f'Welcome back, {member.name}!', 'success')
    return redirect(url_for('main.dashboard'))

@auth_bp.route('/change-password', methods=['GET', 'POST'])
def change_password():
    from .. import bcrypt
    if 'member_id' not in session:
        return redirect(url_for('auth.login'))

    member = Member.query.get(session['member_id'])

    if request.method == 'POST':
        current  = request.form.get('current_password', '')
        new_pw   = request.form.get('new_password', '')
        confirm  = request.form.get('confirm_password', '')

        if not member.auth:
            flash('No password set for this account (Google login). Cannot change password.', 'warning')
            return redirect(url_for('main.profile', member_id=member.member_id))

        if not bcrypt.check_password_hash(member.auth.password_hash, current):
            flash('Current password is incorrect.', 'danger')
            return render_template('change_password.html')

        if new_pw != confirm:
            flash('New passwords do not match.', 'danger')
            return render_template('change_password.html')

        if len(new_pw) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('change_password.html')

        member.auth.password_hash = bcrypt.generate_password_hash(new_pw).decode('utf-8')
        db.session.commit()
        log_action('UPDATE', 'User changed password', member.member_id)
        flash('Password changed successfully!', 'success')
        return redirect(url_for('main.profile', member_id=member.member_id))

    return render_template('change_password.html')