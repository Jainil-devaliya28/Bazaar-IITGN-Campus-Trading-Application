from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from ..models import db, Chat, Member
from ..helpers import login_required, log_action
from sqlalchemy import or_, and_

chat_bp = Blueprint('chat', __name__)


def get_sorted_chat_partners(member_id):
    """Return conversation partners sorted by latest exchanged message first."""
    recent = (Chat.query
              .filter(or_(Chat.sender_id == member_id, Chat.receiver_id == member_id))
              .order_by(Chat.created_at.desc())
              .all())

    partner_ids = []
    seen = set()
    for msg in recent:
        pid = msg.receiver_id if msg.sender_id == member_id else msg.sender_id
        if pid not in seen:
            seen.add(pid)
            partner_ids.append(pid)

    if not partner_ids:
        return []

    members = Member.query.filter(Member.member_id.in_(partner_ids)).all()
    member_map = {m.member_id: m for m in members}
    return [member_map[pid] for pid in partner_ids if pid in member_map]


@chat_bp.route('/chat')
@login_required
def inbox():
    """Show all conversations for the current user."""
    me = session['member_id']
    partners = get_sorted_chat_partners(me)

    # Unread counts per partner
    unread = {}
    for p in partners:
        unread[p.member_id] = Chat.query.filter_by(
            sender_id=p.member_id, receiver_id=me, is_read=False
        ).count()

    return render_template('chat.html', partners=partners, unread=unread, active_partner=None, messages=[])


@chat_bp.route('/chat/<int:partner_id>', methods=['GET', 'POST'])
@login_required
def conversation(partner_id):
    me      = session['member_id']
    partner = Member.query.get_or_404(partner_id)

    if request.method == 'POST':
        text = request.form.get('message', '').strip()
        if not text:
            flash('Message cannot be empty.', 'warning')
            return redirect(url_for('chat.conversation', partner_id=partner_id))

        msg = Chat(sender_id=me, receiver_id=partner_id, message=text)
        db.session.add(msg)
        db.session.commit()
        log_action('INSERT', f'Message sent to member {partner_id}')
        return redirect(url_for('chat.conversation', partner_id=partner_id))

    # Mark incoming as read
    Chat.query.filter_by(sender_id=partner_id, receiver_id=me, is_read=False).update({'is_read': True})
    db.session.commit()

    messages = (Chat.query
                .filter(
                    or_(
                        and_(Chat.sender_id == me,         Chat.receiver_id == partner_id),
                        and_(Chat.sender_id == partner_id, Chat.receiver_id == me)
                    )
                )
                .order_by(Chat.created_at.asc()).all())

    partners = get_sorted_chat_partners(me)
    if partner not in partners:
        partners.insert(0, partner)

    unread = {}
    for p in partners:
        unread[p.member_id] = Chat.query.filter_by(
            sender_id=p.member_id, receiver_id=me, is_read=False
        ).count()

    return render_template('chat.html',
                           partners=partners,
                           unread=unread,
                           active_partner=partner,
                           messages=messages,
                           me=me)


@chat_bp.route('/chat/start/<int:member_id>')
@login_required
def start_chat(member_id):
    """Redirect to conversation page (used from product pages)."""
    if member_id == session['member_id']:
        flash("You can't message yourself.", 'warning')
        return redirect(url_for('chat.inbox'))
    return redirect(url_for('chat.conversation', partner_id=member_id))


@chat_bp.route('/chat/<int:partner_id>/poll')
@login_required
def poll(partner_id):
    """JSON endpoint — returns messages with id > after parameter."""
    me    = session['member_id']
    after = request.args.get('after', 0, type=int)

    new_msgs = (Chat.query
                .filter(
                    or_(
                        and_(Chat.sender_id == me,         Chat.receiver_id == partner_id),
                        and_(Chat.sender_id == partner_id, Chat.receiver_id == me)
                    ),
                    Chat.chat_id > after
                )
                .order_by(Chat.created_at.asc()).all())

    # Mark incoming as read
    Chat.query.filter(
        Chat.sender_id == partner_id,
        Chat.receiver_id == me,
        Chat.chat_id > after,
        Chat.is_read == False
    ).update({'is_read': True})
    db.session.commit()

    result = [{
        'id':   m.chat_id,
        'text': m.message,
        'mine': m.sender_id == me,
        'time': m.created_at.strftime('%d %b %H:%M')
    } for m in new_msgs]

    return jsonify(messages=result)
