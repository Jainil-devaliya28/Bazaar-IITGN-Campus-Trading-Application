from flask import Blueprint, render_template, redirect, url_for, session, jsonify
from ..models import db, Notification
from ..helpers import login_required

notifs_bp = Blueprint('notifs', __name__)


@notifs_bp.route('/notifications')
@login_required
def list_notifications():
    notifs = (Notification.query
              .filter_by(member_id=session['member_id'])
              .order_by(Notification.created_at.desc())
              .all())
    # Mark all as read when viewing the page
    Notification.query.filter_by(
        member_id=session['member_id'], is_read=False
    ).update({'is_read': True})
    db.session.commit()
    return render_template('notifications.html', notifs=notifs)


@notifs_bp.route('/notifications/<int:notif_id>/read')
@login_required
def mark_read(notif_id):
    """Mark one notification read and redirect to its link."""
    notif = Notification.query.get_or_404(notif_id)
    if notif.member_id == session['member_id']:
        notif.is_read = True
        db.session.commit()
    return redirect(notif.link or url_for('notifs.list_notifications'))


@notifs_bp.route('/notifications/count')
@login_required
def unread_count():
    """JSON endpoint for live badge polling."""
    count = Notification.query.filter_by(
        member_id=session['member_id'], is_read=False
    ).count()
    return jsonify(count=count)


@notifs_bp.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    Notification.query.filter_by(
        member_id=session['member_id'], is_read=False
    ).update({'is_read': True})
    db.session.commit()
    return redirect(url_for('notifs.list_notifications'))
