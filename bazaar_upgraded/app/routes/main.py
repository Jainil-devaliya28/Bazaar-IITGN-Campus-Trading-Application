from enum import member

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from ..models import db, Member, Student, TransactionHistory, Product, Feedback, Review, Demand, Watchlist, BargainingProposal
from ..helpers import login_required, log_action

main_bp = Blueprint('main', __name__)

HOSTELS = [
    "Aibaan", "Beauki", "Chimair", "Duven",
    "Emiet", "Firpeal", "Griwiksh", "Hiqom",
    "Ijokha", "Jurqia", "Kyzeel", "Lekhaag"
]

WINGS = ["Ground", "First ", "Second ", "Third"]

@main_bp.route('/')
def index():
    if 'member_id' in session:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    member = Member.query.get(session['member_id'])
    me     = member.member_id

    recent_products = (Product.query
                       .filter_by(seller_id=me, is_available=True)
                       .order_by(Product.created_at.desc()).limit(5).all())
    recent_txns = (TransactionHistory.query
                   .filter((TransactionHistory.buyer_id == me) |
                           (TransactionHistory.seller_id == me))
                   .order_by(TransactionHistory.created_at.desc()).limit(5).all())

    total_products  = Product.query.filter_by(seller_id=me).count()
    total_purchases = TransactionHistory.query.filter_by(buyer_id=me).count()
    total_sales     = TransactionHistory.query.filter_by(seller_id=me, status='completed').count()

    # My active offers
    my_offers = BargainingProposal.query.filter(
        BargainingProposal.buyer_id == me,
        BargainingProposal.status.in_(['pending', 'countered'])
    ).order_by(BargainingProposal.created_at.desc()).limit(5).all()

    # Watchlist count
    watchlist_count = Watchlist.query.filter_by(member_id=me).count()

    # Pending offers on my listings
    my_product_ids = [p.product_id for p in Product.query.filter_by(seller_id=me).all()]
    incoming_offers = 0
    if my_product_ids:
        incoming_offers = BargainingProposal.query.filter(
            BargainingProposal.product_id.in_(my_product_ids),
            BargainingProposal.status == 'pending'
        ).count()

    return render_template('dashboard.html', member=member,
                           recent_products=recent_products, recent_txns=recent_txns,
                           total_products=total_products, total_purchases=total_purchases,
                           total_sales=total_sales,
                           my_offers=my_offers,
                           watchlist_count=watchlist_count,
                           incoming_offers=incoming_offers)


@main_bp.route('/profile/<int:member_id>')
@login_required
def profile(member_id):
    member     = Member.query.get_or_404(member_id)
    viewer_id  = session['member_id']
    is_owner   = (viewer_id == member_id)
    is_admin   = (session.get('role') == 'admin')
    can_see_full = is_owner or is_admin

    products = (Product.query.filter_by(seller_id=member_id, is_available=True)
                .order_by(Product.created_at.desc()).all())

    reviews    = Review.query.filter_by(reviewed_id=member_id).order_by(Review.created_at.asc()).all()
    avg_rating = (sum(r.rating for r in reviews) / len(reviews)) if reviews else None

    txns = []
    if can_see_full:
        txns = (TransactionHistory.query
                .filter((TransactionHistory.buyer_id == member_id) |
                        (TransactionHistory.seller_id == member_id))
                .order_by(TransactionHistory.created_at.desc()).limit(10).all())

    demands = []
    if can_see_full:
        demands = (Demand.query.filter_by(member_id=member_id, status='open')
                   .order_by(Demand.created_at.desc()).limit(5).all())

    total_listed  = Product.query.filter_by(seller_id=member_id).count()
    total_sold    = Product.query.filter_by(seller_id=member_id, is_available=False).count()

    return render_template('profile.html', member=member,
                           products=products, txns=txns,
                           reviews=reviews, avg_rating=avg_rating,
                           demands=demands,
                           total_listed=total_listed, total_sold=total_sold,
                           is_owner=is_owner, is_admin=is_admin,
                           can_see_full=can_see_full)


@main_bp.route('/members')
@login_required
def members_directory():
    search  = request.args.get('search', '').strip()
    query   = Member.query
    if search:
        query = query.filter(
            Member.name.ilike(f'%{search}%') | Member.email.ilike(f'%{search}%'))
    members = query.order_by(Member.created_at.desc()).all()
    return render_template('members_directory.html', members=members, search=search)


@main_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    member  = Member.query.get(session['member_id'])
    student = member.student
    if request.method == 'POST':
        member.name   = request.form.get('name', member.name).strip()
        member.phone  = request.form.get('phone', member.phone or '').strip()
        # BUG FIX: These lines were commented out — hostel/wing were never saved.
        # Fixed: uncommented and properly strip/None-ify the values.
        member.hostel = request.form.get('hostel', '').strip() or None
        member.wing   = request.form.get('wing', '').strip() or None
        if student:
            student.college_name = request.form.get('college_name', '').strip()
            student.department   = request.form.get('department', '').strip()
            yr = request.form.get('year', '')
            student.year         = int(yr) if yr.isdigit() else student.year
            student.roll_number  = request.form.get('roll_number', '').strip()
        db.session.commit()
        log_action('UPDATE', 'User updated profile')
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('main.profile', member_id=member.member_id))
    return render_template('edit_profile.html', member=member,hostels=HOSTELS,
    wings=WINGS)


@main_bp.route('/feedback', methods=['GET', 'POST'])
@login_required
def feedback():
    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        if not message:
            flash('Message is required.', 'danger')
            return render_template('feedback.html')
        fb = Feedback(member_id=session['member_id'], subject=subject, message=message)
        db.session.add(fb)
        db.session.commit()
        log_action('INSERT', f'User submitted feedback: {subject}')
        flash('Feedback submitted. Thank you!', 'success')
        return redirect(url_for('main.dashboard'))
    return render_template('feedback.html')


@main_bp.route('/offline')
def offline():
    """Offline fallback page served by service worker cache."""
    return render_template('offline.html')

@main_bp.route('/google5448905c392d0cc5.html')
def google_verify():
    return app.send_static_file('google5448905c392d0cc5.html')
