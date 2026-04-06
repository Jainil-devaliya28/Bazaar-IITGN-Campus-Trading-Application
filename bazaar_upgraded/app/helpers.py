from functools import wraps
from flask import session, redirect, url_for, flash, request, jsonify
from .models import db, Log, Member


def log_action(action_type: str, description: str, member_id: int = None):
    try:
        if member_id is None:
            member_id = session.get('member_id')
        entry = Log(member_id=member_id, action_type=action_type, description=description)
        db.session.add(entry)
        db.session.commit()
    except Exception as e:
        print(f"Failed to log action: {e}")


def log_security_event(action_type: str, description: str, ip_address: str = None, user_agent: str = None):
    try:
        full_description = f"{description} | IP: {ip_address or 'unknown'} | UA: {user_agent or 'unknown'}"
        entry = Log(member_id=None, action_type=action_type, description=full_description)
        db.session.add(entry)
        db.session.commit()
    except Exception as e:
        print(f"Failed to log security event: {e}")


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'member_id' not in session:
            ip = request.remote_addr
            ua = request.headers.get('User-Agent', 'unknown')
            log_security_event(
                'UNAUTHORIZED_ACCESS',
                f"Attempted access to {request.path} without authentication",
                ip, ua
            )
            if request.path.endswith('/poll') or request.is_json:
                return jsonify(error='login required'), 401
            flash('Please log in first.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'member_id' not in session:
            flash('Please log in first.', 'warning')
            return redirect(url_for('auth.login'))
        member = Member.query.get(session['member_id'])
        if not member or member.role != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('main.dashboard'))
        session['role'] = member.role
        return f(*args, **kwargs)
    return decorated


def notify(member_id: int, title: str, message: str, link: str = None):
    from .models import Notification
    notif = Notification(member_id=member_id, title=title, message=message, link=link)
    db.session.add(notif)
    db.session.commit()


def recalculate_karma(member_id: int):
    """Recalculate and store karma score for a member based on their reviews."""
    from .models import Review, Member
    reviews = Review.query.filter_by(reviewed_id=member_id).all()
    if reviews:
        avg = sum(r.rating for r in reviews) / len(reviews)
        karma = round(avg * 20)   # 5-star avg = 100 karma
    else:
        karma = 0
    member = Member.query.get(member_id)
    if member:
        member.karma_score = karma
        db.session.commit()
    return karma
