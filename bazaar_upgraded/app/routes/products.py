import os
import io
import uuid
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from sqlalchemy import func, text
from werkzeug.utils import secure_filename
from ..models import db, Product, TransactionHistory, Review, BargainingProposal, Member, PurchaseRequest, Watchlist, Report, CAMPUS_PICKUP_POINTS
from ..helpers import login_required, admin_required, log_action, notify, recalculate_karma
from ..ai_services import ai_suggest_tags_and_category, get_price_insight

products_bp = Blueprint('products', __name__)

CATEGORIES = ['Books', 'Electronics', 'Cycles', 'Clothing', 'Stationery',
               'Sports', 'Hostel Gear', 'Other']
CONDITIONS  = ['New', 'Good', 'Fair']
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
REPORT_REASONS = [
    'Fake/misleading listing',
    'Item already sold',
    'Inappropriate content',
    'Spam',
    'Price gouging',
    'Other'
]

# Image optimization settings
MAX_IMAGE_SIZE = (800, 800)      # Max dimensions before resize
IMAGE_QUALITY  = 82              # JPEG quality (0-100); 82 is near-lossless visually


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


def save_uploaded_image(file):
    """
    Save and compress an uploaded image.
    Uses Pillow to resize (if needed) and re-encode at optimized quality.
    Falls back to raw save if Pillow is unavailable or image conversion fails.
    """
    if not file or file.filename == '':
        return None
    if not allowed_file(file.filename):
        return None

    ext = file.filename.rsplit('.', 1)[1].lower()
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)

    try:
        from PIL import Image, ExifTags
        file.stream.seek(0)
        img = Image.open(file.stream)

        # Auto-rotate based on EXIF orientation (fixes phone photos)
        try:
            for orientation in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation] == 'Orientation':
                    break
            exif = img._getexif()
            if exif and orientation in exif:
                actions = {3: 180, 6: 270, 8: 90}
                if exif[orientation] in actions:
                    img = img.rotate(actions[exif[orientation]], expand=True)
        except Exception:
            pass

        # Convert to RGB (handles PNG with alpha, etc.)
        if img.mode in ('RGBA', 'P', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                background.paste(img, mask=img.split()[3])
            else:
                background.paste(img)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Resize if larger than MAX_IMAGE_SIZE (preserving aspect ratio)
        img.thumbnail(MAX_IMAGE_SIZE, Image.LANCZOS)

        filename = f"{uuid.uuid4().hex}.jpg"
        dest_path = os.path.join(upload_dir, filename)
        img.save(dest_path, 'JPEG', quality=IMAGE_QUALITY, optimize=True)

    except ImportError:
        filename = f"{uuid.uuid4().hex}.{ext}"
        dest_path = os.path.join(upload_dir, filename)
        file.stream.seek(0)
        file.save(dest_path)
    except Exception:
        filename = f"{uuid.uuid4().hex}.{ext}"
        dest_path = os.path.join(upload_dir, filename)
        file.stream.seek(0)
        file.save(dest_path)

    return url_for('static', filename=f'uploads/{filename}')


# ─────────────────────────────────────────────
# AI: Auto-tag endpoint (called via fetch from add_product page)
# ─────────────────────────────────────────────
@products_bp.route('/products/ai-suggest', methods=['POST'])
@login_required
def ai_suggest():
    """
    JSON endpoint: returns AI-suggested category + tags for given title/description.
    Called client-side via fetch when user uploads an image or types a title.
    """
    data        = request.get_json(silent=True) or {}
    title       = data.get('title', '')
    description = data.get('description', '')
    suggestion  = ai_suggest_tags_and_category(title, description)
    return jsonify(suggestion)


# ─────────────────────────────────────────────
# Marketplace
# ─────────────────────────────────────────────
@products_bp.route('/marketplace')
@login_required
def marketplace():
    query    = Product.query.filter_by(is_available=True)
    category = request.args.get('category', '')
    min_p    = request.args.get('min_price', '')
    max_p    = request.args.get('max_price', '')
    search   = request.args.get('search', '').strip()
    hostel   = request.args.get('hostel', '')
    urgent   = request.args.get('urgent', '')
    tag      = request.args.get('tag', '').strip()

    if category:
        query = query.filter_by(category=category)
    if min_p:
        try:
            query = query.filter(Product.price >= float(min_p))
        except ValueError:
            pass
    if max_p:
        try:
            query = query.filter(Product.price <= float(max_p))
        except ValueError:
            pass
    if search:
        query = query.filter(
            Product.title.ilike(f'%{search}%') |
            Product.description.ilike(f'%{search}%') |
            Product.tags.ilike(f'%{search}%')
        )
    if hostel:
        query = query.join(Member, Product.seller_id == Member.member_id).filter(
            Member.hostel == hostel
        )
    if urgent:
        query = query.filter_by(is_urgent=True)
    if tag:
        query = query.filter(Product.tags.ilike(f'%{tag}%'))

    products = query.order_by(Product.is_urgent.desc(), Product.created_at.desc()).all()

    # Price insights per category
    price_insights = {}
    if category:
        result = db.session.query(
            func.avg(Product.price).label('avg'),
            func.min(Product.price).label('min'),
            func.max(Product.price).label('max'),
            func.count(Product.product_id).label('count')
        ).filter(
            Product.category == category,
            Product.is_available == True
        ).first()
        if result and result.count > 0:
            price_insights = {
                'avg': float(result.avg or 0),
                'min': float(result.min or 0),
                'max': float(result.max or 0),
                'count': result.count
            }

    # Get unique hostels for filter
    hostels = [h[0] for h in db.session.query(Member.hostel).filter(Member.hostel != None).distinct().all()]

    # Watchlist set for current user
    me = session['member_id']
    watchlisted = set(
        w.product_id for w in Watchlist.query.filter_by(member_id=me).all()
    )

    return render_template('marketplace.html',
                           products=products,
                           categories=CATEGORIES,
                           selected_category=category,
                           min_price=min_p,
                           max_price=max_p,
                           search=search,
                           selected_hostel=hostel,
                           hostels=hostels,
                           urgent=urgent,
                           selected_tag=tag,
                           price_insights=price_insights,
                           watchlisted=watchlisted)


# ─────────────────────────────────────────────
# My Listings
# ─────────────────────────────────────────────
@products_bp.route('/my-listings')
@login_required
def my_listings():
    status   = request.args.get('status', '')
    query    = Product.query.filter_by(seller_id=session['member_id'])
    if status == 'available':
        query = query.filter_by(is_available=True)
    elif status == 'sold':
        query = query.filter_by(is_available=False)
    products  = query.order_by(Product.created_at.desc()).all()
    total_val = sum(float(p.price) for p in products if not p.is_available)

    # Pending offers for each product
    pending_offers = {}
    for p in products:
        pending_offers[p.product_id] = BargainingProposal.query.filter_by(
            product_id=p.product_id, status='pending'
        ).count()

    return render_template('my_listings.html',
                           products=products,
                           status_filter=status,
                           total_earned=total_val,
                           pending_offers=pending_offers)


# ─────────────────────────────────────────────
# Add Product
# ─────────────────────────────────────────────
@products_bp.route('/product/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        title        = request.form.get('title', '').strip()
        description  = request.form.get('description', '').strip()
        price        = request.form.get('price', '')
        category     = request.form.get('category', '')
        condition    = request.form.get('condition', '')
        tags         = request.form.get('tags', '').strip()
        pickup_point = request.form.get('pickup_point', '').strip()
        is_urgent    = request.form.get('is_urgent') == 'on'

        if not title or not price or not category:
            flash('Title, price and category are required.', 'danger')
            return render_template('add_product.html', categories=CATEGORIES, conditions=CONDITIONS, pickup_points=CAMPUS_PICKUP_POINTS)

        try:
            price = float(price)
            if price <= 0:
                raise ValueError
        except ValueError:
            flash('Enter a valid positive price.', 'danger')
            return render_template('add_product.html', categories=CATEGORIES, conditions=CONDITIONS, pickup_points=CAMPUS_PICKUP_POINTS)

        image_url = save_uploaded_image(request.files.get('image'))

        product = Product(
            seller_id    = session['member_id'],
            title        = title,
            description  = description,
            price        = price,
            category     = category,
            condition    = condition or None,
            image_url    = image_url,
            is_available = True,
            status       = 'available',
            tags         = tags or None,
            pickup_point = pickup_point or None,
            is_urgent    = is_urgent
        )
        db.session.add(product)
        db.session.commit()
        log_action('INSERT', f'Product listed: {title}')
        flash('Product listed successfully!', 'success')
        return redirect(url_for('products.product_detail', product_id=product.product_id))

    return render_template('add_product.html', categories=CATEGORIES, conditions=CONDITIONS, pickup_points=CAMPUS_PICKUP_POINTS)


# ─────────────────────────────────────────────
# Edit Product
# ─────────────────────────────────────────────
@products_bp.route('/product/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    if product.seller_id != session['member_id'] and session.get('role') != 'admin':
        flash('Permission denied.', 'danger')
        return redirect(url_for('products.my_listings'))

    if request.method == 'POST':
        product.title        = request.form.get('title', product.title).strip()
        product.description  = request.form.get('description', '').strip()
        product.price        = float(request.form.get('price', product.price))
        product.category     = request.form.get('category', product.category)
        product.condition    = request.form.get('condition', product.condition)
        product.tags         = request.form.get('tags', '').strip() or None
        product.pickup_point = request.form.get('pickup_point', '').strip() or None
        product.is_urgent    = request.form.get('is_urgent') == 'on'

        new_image = save_uploaded_image(request.files.get('image'))
        if new_image:
            product.image_url = new_image

        db.session.commit()
        log_action('UPDATE', f'Product edited: {product.title}')
        flash('Product updated.', 'success')
        return redirect(url_for('products.product_detail', product_id=product_id))

    return render_template('add_product.html',
                           product=product,
                           categories=CATEGORIES,
                           conditions=CONDITIONS,
                           edit_mode=True)


# ─────────────────────────────────────────────
# Product Detail
# ─────────────────────────────────────────────
@products_bp.route('/product/<int:product_id>')
@login_required
def product_detail(product_id):
    product  = Product.query.get_or_404(product_id)
    me       = session['member_id']
    is_owner = (product.seller_id == me)
    is_admin = (session.get('role') == 'admin')

    reviews  = product.reviews.order_by(Review.created_at.desc()).all()
    avg_rating = (sum(r.rating for r in reviews) / len(reviews)) if reviews else None

    my_purchase_request = PurchaseRequest.query.filter_by(
        product_id=product_id, buyer_id=me
    ).order_by(PurchaseRequest.created_at.desc()).first()

    my_proposal = BargainingProposal.query.filter_by(
        product_id=product_id, buyer_id=me
    ).order_by(BargainingProposal.created_at.desc()).first()

    # Seller sees all proposals
    all_proposals = []
    if is_owner or is_admin:
        all_proposals = product.proposals.order_by(
            BargainingProposal.created_at.desc()
        ).all()

    # Purchase requests for seller
    pending_requests = []
    if is_owner or is_admin:
        pending_requests = PurchaseRequest.query.filter_by(
            product_id=product_id, status='pending'
        ).all()

    # Watchlist status
    is_watchlisted = bool(Watchlist.query.filter_by(
        member_id=me, product_id=product_id
    ).first())

    # Has user transacted on this product (for review gate)
    can_review = False
    if not is_owner:
        txn = TransactionHistory.query.filter_by(
            buyer_id=me, product_id=product_id, status='completed'
        ).first()
        can_review = bool(txn)
        # Also allow review via approved purchase request
        if not can_review:
            apr = PurchaseRequest.query.filter_by(
                buyer_id=me, product_id=product_id, status='approved'
            ).first()
            can_review = bool(apr)

    already_reviewed = bool(Review.query.filter_by(
        product_id=product_id, reviewer_id=me
    ).first())

    # Price insights: use ai_services for richer stats (avg, median, min, max)
    price_insights = get_price_insight(product.category) if product.category else None

    return render_template('product_detail.html',
                           product=product,
                           reviews=reviews,
                           avg_rating=avg_rating,
                           is_owner=is_owner,
                           is_admin=is_admin,
                           my_purchase_request=my_purchase_request,
                           my_proposal=my_proposal,
                           all_proposals=all_proposals,
                           pending_requests=pending_requests,
                           is_watchlisted=is_watchlisted,
                           can_review=can_review,
                           already_reviewed=already_reviewed,
                           price_insights=price_insights,
                           report_reasons=REPORT_REASONS)


# ─────────────────────────────────────────────
# Delete Product
# ─────────────────────────────────────────────
@products_bp.route('/product/<int:product_id>/delete', methods=['POST'])
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    if product.seller_id != session['member_id'] and session.get('role') != 'admin':
        flash('Permission denied.', 'danger')
        return redirect(url_for('products.my_listings'))
    title = product.title
    db.session.delete(product)
    db.session.commit()
    log_action('DELETE', f'Product deleted: {title}')
    flash(f'"{title}" deleted.', 'success')
    return redirect(url_for('products.my_listings'))


# ─────────────────────────────────────────────
# Request to Buy
# ─────────────────────────────────────────────
@products_bp.route('/product/<int:product_id>/request-buy', methods=['POST'])
@login_required
def request_buy(product_id):
    product = Product.query.get_or_404(product_id)
    me = session['member_id']

    if product.seller_id == me:
        flash("You can't buy your own product.", 'warning')
        return redirect(url_for('products.product_detail', product_id=product_id))

    if not product.is_available:
        flash('This product is no longer available.', 'warning')
        return redirect(url_for('products.product_detail', product_id=product_id))

    existing = PurchaseRequest.query.filter_by(
        product_id=product_id, buyer_id=me, status='pending'
    ).first()
    if existing:
        flash('You already have a pending purchase request for this item.', 'warning')
        return redirect(url_for('products.product_detail', product_id=product_id))

    msg = request.form.get('buy_message', '').strip()
    pr  = PurchaseRequest(product_id=product_id, buyer_id=me, message=msg)
    db.session.add(pr)

    # Mark product as reserved
    product.status = 'reserved'
    db.session.commit()

    buyer = Member.query.get(me)
    notify(
        member_id = product.seller_id,
        title     = '🛒 New purchase request!',
        message   = f'{buyer.name} wants to buy "{product.title}" at ₹{product.price}.',
        link      = url_for('products.product_detail', product_id=product_id)
    )
    log_action('INSERT', f'Purchase request for: {product.title}')
    flash('Purchase request sent! The seller will be notified.', 'success')
    return redirect(url_for('products.product_detail', product_id=product_id))


# ─────────────────────────────────────────────
# Respond to Purchase Request (seller)
# ─────────────────────────────────────────────
@products_bp.route('/purchase-request/<int:req_id>/respond', methods=['POST'])
@login_required
def respond_purchase_request(req_id):
    purchase_req = PurchaseRequest.query.get_or_404(req_id)
    product      = Product.query.get_or_404(purchase_req.product_id)
    seller       = Member.query.get(session['member_id'])

    if product.seller_id != session['member_id']:
        flash('Permission denied.', 'danger')
        return redirect(url_for('products.marketplace'))

    action = request.form.get('action')
    buyer  = Member.query.get(purchase_req.buyer_id)

    if action == 'approved':
        # Race condition guard: lock the product row
        locked = db.session.execute(
            text('SELECT product_id FROM Products WHERE product_id=:pid AND is_available=1 FOR UPDATE'),
            {'pid': product.product_id}
        ).fetchone()

        if not locked:
            db.session.rollback()
            flash('This item has already been sold or is no longer available.', 'warning')
            return redirect(url_for('products.product_detail', product_id=product.product_id))

        # Approve this request
        purchase_req.status = 'approved'

        # Reserve the product until both parties confirm the deal
        product.is_available = False
        product.status       = 'reserved'

        # Reject all other pending requests for same product
        PurchaseRequest.query.filter(
            PurchaseRequest.product_id == product.product_id,
            PurchaseRequest.request_id != req_id,
            PurchaseRequest.status == 'pending'
        ).update({'status': 'rejected'})

        # Create handshake transaction record in pending state
        txn = TransactionHistory(
            product_id = product.product_id,
            buyer_id   = purchase_req.buyer_id,
            seller_id  = product.seller_id,
            amount     = product.price,
            status     = 'pending'
        )
        db.session.add(txn)
        db.session.commit()

        notify(
            member_id = purchase_req.buyer_id,
            title     = '✅ Purchase approved!',
            message   = f'{seller.name} approved your request for "{product.title}". Confirm the deal in transactions once you meet.',
            link      = url_for('transactions.my_transactions')
        )
        log_action('UPDATE', f'Purchase approved: {product.title} → {buyer.name}')
        flash(f'Purchase approved! "{product.title}" is reserved for {buyer.name}. Confirm the deal in transactions after pickup.', 'success')

    else:
        purchase_req.status = 'rejected'
        # Revert to available if no other pending requests
        other_pending = PurchaseRequest.query.filter_by(
            product_id=product.product_id, status='pending'
        ).count()
        if other_pending == 0:
            product.status = 'available'
        db.session.commit()

        notify(
            member_id = purchase_req.buyer_id,
            title     = '❌ Purchase request declined',
            message   = f'{seller.name} declined your request for "{product.title}".',
            link      = url_for('products.product_detail', product_id=product.product_id)
        )
        log_action('UPDATE', f'Purchase rejected: {product.title} for {buyer.name}')
        flash(f'Purchase request from {buyer.name} rejected.', 'info')

    return redirect(url_for('products.product_detail', product_id=product.product_id))


# ─────────────────────────────────────────────
# Cancel Purchase Request (buyer)
# ─────────────────────────────────────────────
@products_bp.route('/purchase-request/<int:req_id>/cancel', methods=['POST'])
@login_required
def cancel_purchase_request(req_id):
    purchase_req = PurchaseRequest.query.get_or_404(req_id)
    if purchase_req.buyer_id != session['member_id']:
        flash('Permission denied.', 'danger')
        return redirect(url_for('products.marketplace'))

    product_id = purchase_req.product_id
    product    = Product.query.get(product_id)
    db.session.delete(purchase_req)

    # If no other pending requests, revert to available
    if product:
        other = PurchaseRequest.query.filter_by(
            product_id=product_id, status='pending'
        ).count()
        if other == 0:
            product.status = 'available'

    db.session.commit()
    log_action('DELETE', f'Purchase request cancelled for product {product_id}')
    flash('Purchase request cancelled.', 'info')
    return redirect(url_for('products.product_detail', product_id=product_id))


# ─────────────────────────────────────────────
# Toggle Availability
# ─────────────────────────────────────────────
@products_bp.route('/product/<int:product_id>/toggle-availability', methods=['POST'])
@login_required
def toggle_availability(product_id):
    product = Product.query.get_or_404(product_id)
    if product.seller_id != session['member_id']:
        flash('Permission denied.', 'danger')
        return redirect(url_for('products.my_listings'))

    product.is_available = not product.is_available
    product.status       = 'available' if product.is_available else 'sold'
    db.session.commit()
    action = 'relisted' if product.is_available else 'marked as sold'
    log_action('UPDATE', f'Product {action}: {product.title}')
    flash(f'Product {action}.', 'success')
    return redirect(url_for('products.my_listings'))


# ─────────────────────────────────────────────
# Add Review (gated on completed transaction)
# ─────────────────────────────────────────────
@products_bp.route('/product/<int:product_id>/review', methods=['POST'])
@login_required
def add_review(product_id):
    product = Product.query.get_or_404(product_id)
    me      = session['member_id']

    if product.seller_id == me:
        flash("You can't review your own product.", 'warning')
        return redirect(url_for('products.product_detail', product_id=product_id))

    # Gate: must have completed transaction OR approved purchase request
    txn = TransactionHistory.query.filter_by(
        buyer_id=me, product_id=product_id, status='completed'
    ).first()
    apr = PurchaseRequest.query.filter_by(
        buyer_id=me, product_id=product_id, status='approved'
    ).first()

    if not txn and not apr:
        flash('You can only review products you have bought.', 'warning')
        return redirect(url_for('products.product_detail', product_id=product_id))

    existing = Review.query.filter_by(product_id=product_id, reviewer_id=me).first()
    if existing:
        flash('You have already reviewed this product.', 'warning')
        return redirect(url_for('products.product_detail', product_id=product_id))

    rating  = request.form.get('rating', '')
    comment = request.form.get('comment', '').strip()

    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            raise ValueError
    except ValueError:
        flash('Rating must be between 1 and 5.', 'danger')
        return redirect(url_for('products.product_detail', product_id=product_id))

    review = Review(
        product_id  = product_id,
        reviewer_id = me,
        reviewed_id = product.seller_id,
        rating      = rating,
        comment     = comment
    )
    db.session.add(review)
    db.session.commit()

    # Update seller's karma
    recalculate_karma(product.seller_id)

    reviewer = Member.query.get(me)
    notify(
        member_id = product.seller_id,
        title     = 'New review on your product',
        message   = f'{reviewer.name} left a {rating}★ review on "{product.title}".',
        link      = url_for('products.product_detail', product_id=product_id)
    )
    log_action('INSERT', f'Review added for product: {product.title}')
    flash('Review submitted!', 'success')
    return redirect(url_for('products.product_detail', product_id=product_id))


# ─────────────────────────────────────────────
# Send Bargaining Proposal
# ─────────────────────────────────────────────
@products_bp.route('/product/<int:product_id>/bargain', methods=['POST'])
@login_required
def send_proposal(product_id):
    product = Product.query.get_or_404(product_id)
    me = session['member_id']

    if product.seller_id == me:
        flash("You can't bargain on your own product.", 'warning')
        return redirect(url_for('products.product_detail', product_id=product_id))

    if not product.is_available:
        flash('This item is no longer available.', 'warning')
        return redirect(url_for('products.product_detail', product_id=product_id))

    # Only one active proposal at a time
    existing = BargainingProposal.query.filter(
        BargainingProposal.product_id == product_id,
        BargainingProposal.buyer_id == me,
        BargainingProposal.status.in_(['pending', 'countered'])
    ).first()
    if existing:
        flash('You already have an active offer on this item.', 'warning')
        return redirect(url_for('products.product_detail', product_id=product_id))

    proposed_price = request.form.get('proposed_price', '')
    message        = request.form.get('message', '').strip()

    try:
        proposed_price = float(proposed_price)
        if proposed_price <= 0:
            raise ValueError
    except ValueError:
        flash('Enter a valid proposed price.', 'danger')
        return redirect(url_for('products.product_detail', product_id=product_id))

    proposal = BargainingProposal(
        product_id     = product_id,
        buyer_id       = me,
        proposed_price = proposed_price,
        message        = message
    )
    db.session.add(proposal)
    db.session.commit()

    buyer = Member.query.get(me)
    notify(
        member_id = product.seller_id,
        title     = '💰 New bargain offer',
        message   = f'{buyer.name} offered ₹{proposed_price:.0f} for "{product.title}".',
        link      = url_for('products.product_detail', product_id=product_id)
    )
    log_action('INSERT', f'Bargaining proposal sent for: {product.title}')
    flash('Offer sent!', 'success')
    return redirect(url_for('products.product_detail', product_id=product_id))


# ─────────────────────────────────────────────
# Respond to Proposal (seller: accept / counter / reject)
# ─────────────────────────────────────────────
@products_bp.route('/proposal/<int:proposal_id>/respond', methods=['POST'])
@login_required
def respond_proposal(proposal_id):
    proposal = BargainingProposal.query.get_or_404(proposal_id)
    product  = proposal.product

    if product.seller_id != session['member_id']:
        flash('Permission denied.', 'danger')
        return redirect(url_for('products.marketplace'))

    action  = request.form.get('action')
    seller  = Member.query.get(session['member_id'])

    if action == 'accepted':
        proposal.status = 'accepted'
        product.price = proposal.proposed_price
        db.session.commit()
        notify(
            member_id = proposal.buyer_id,
            title     = '🎉 Offer accepted!',
            message   = f'{seller.name} accepted your ₹{proposal.proposed_price:.0f} offer for "{product.title}". Proceed to buy!',
            link      = url_for('products.product_detail', product_id=product.product_id)
        )
        flash('Offer accepted. Buyer has been notified.', 'success')

    elif action == 'rejected':
        proposal.status = 'rejected'
        db.session.commit()
        notify(
            member_id = proposal.buyer_id,
            title     = 'Offer declined',
            message   = f'{seller.name} declined your ₹{proposal.proposed_price:.0f} offer for "{product.title}".',
            link      = url_for('products.product_detail', product_id=product.product_id)
        )
        flash('Offer rejected.', 'info')

    elif action == 'countered':
        counter_raw = request.form.get('counter_price', '')
        try:
            counter = float(counter_raw)
            if counter <= 0:
                raise ValueError
        except ValueError:
            flash('Enter a valid counter price.', 'danger')
            return redirect(url_for('products.product_detail', product_id=product.product_id))

        proposal.status        = 'countered'
        proposal.counter_price = counter
        db.session.commit()
        notify(
            member_id = proposal.buyer_id,
            title     = '↩️ Counter-offer received',
            message   = f'{seller.name} countered your offer for "{product.title}" at ₹{counter:.0f}.',
            link      = url_for('products.product_detail', product_id=product.product_id)
        )
        flash(f'Counter-offer of ₹{counter:.0f} sent to buyer.', 'success')

    log_action('UPDATE', f'Proposal {action} for: {product.title}')
    return redirect(url_for('products.product_detail', product_id=product.product_id))


# ─────────────────────────────────────────────
# Accept Counter-Offer (buyer)
# ─────────────────────────────────────────────
@products_bp.route('/proposal/<int:proposal_id>/accept-counter', methods=['POST'])
@login_required
def accept_counter(proposal_id):
    proposal = BargainingProposal.query.get_or_404(proposal_id)
    product  = proposal.product

    if proposal.buyer_id != session['member_id']:
        flash('Permission denied.', 'danger')
        return redirect(url_for('products.marketplace'))

    if proposal.status != 'countered':
        flash('No active counter-offer to accept.', 'warning')
        return redirect(url_for('products.product_detail', product_id=product.product_id))

    proposal.status = 'accepted'
    product.price = proposal.counter_price
    db.session.commit()

    seller = Member.query.get(product.seller_id)
    notify(
        member_id = product.seller_id,
        title     = '✅ Counter-offer accepted!',
        message   = f'Buyer accepted your ₹{proposal.counter_price:.0f} counter for "{product.title}".',
        link      = url_for('products.product_detail', product_id=product.product_id)
    )
    flash(f'Counter-offer of ₹{proposal.counter_price:.0f} accepted! Proceed with purchase.', 'success')
    return redirect(url_for('products.product_detail', product_id=product.product_id))


# ─────────────────────────────────────────────
# Reject Counter-Offer (buyer)
# ─────────────────────────────────────────────
@products_bp.route('/proposal/<int:proposal_id>/reject-counter', methods=['POST'])
@login_required
def reject_counter(proposal_id):
    proposal = BargainingProposal.query.get_or_404(proposal_id)
    product  = proposal.product

    if proposal.buyer_id != session['member_id']:
        flash('Permission denied.', 'danger')
        return redirect(url_for('products.marketplace'))

    if proposal.status != 'countered':
        flash('No active counter-offer to reject.', 'warning')
        return redirect(url_for('products.product_detail', product_id=product.product_id))

    proposal.status = 'rejected'
    db.session.commit()

    seller = Member.query.get(product.seller_id)
    notify(
        member_id = product.seller_id,
        title     = '❌ Counter-offer rejected',
        message   = f'Buyer rejected your ₹{proposal.counter_price:.0f} counter for "{product.title}".',
        link      = url_for('products.product_detail', product_id=product.product_id)
    )
    flash(f'Counter-offer of ₹{proposal.counter_price:.0f} rejected.', 'info')
    return redirect(url_for('products.product_detail', product_id=product.product_id))


# ─────────────────────────────────────────────
# Watchlist toggle
# ─────────────────────────────────────────────
@products_bp.route('/product/<int:product_id>/watchlist', methods=['POST'])
@login_required
def toggle_watchlist(product_id):
    me = session['member_id']
    Product.query.get_or_404(product_id)

    existing = Watchlist.query.filter_by(member_id=me, product_id=product_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash('Removed from watchlist.', 'info')
    else:
        w = Watchlist(member_id=me, product_id=product_id)
        db.session.add(w)
        db.session.commit()
        flash('Added to watchlist!', 'success')

    ref = request.referrer or url_for('products.product_detail', product_id=product_id)
    return redirect(ref)


# ─────────────────────────────────────────────
# Watchlist page
# ─────────────────────────────────────────────
@products_bp.route('/watchlist')
@login_required
def watchlist():
    me    = session['member_id']
    items = Watchlist.query.filter_by(member_id=me).order_by(
        Watchlist.created_at.desc()
    ).all()
    return render_template('watchlist.html', items=items)


# ─────────────────────────────────────────────
# Report a listing
# ─────────────────────────────────────────────
@products_bp.route('/product/<int:product_id>/report', methods=['POST'])
@login_required
def report_product(product_id):
    product     = Product.query.get_or_404(product_id)
    me          = session['member_id']
    reason      = request.form.get('reason', '').strip()
    details     = request.form.get('details', '').strip()

    if not reason:
        flash('Please select a reason.', 'danger')
        return redirect(url_for('products.product_detail', product_id=product_id))

    report = Report(
        reporter_id = me,
        reported_id = product.seller_id,
        product_id  = product_id,
        reason      = reason,
        details     = details
    )
    db.session.add(report)
    db.session.commit()
    log_action('INSERT', f'Report filed on product {product_id}: {reason}')
    flash('Report submitted. Our team will review it.', 'success')
    return redirect(url_for('products.product_detail', product_id=product_id))


# ─────────────────────────────────────────────
# My Offers dashboard section
# ─────────────────────────────────────────────
@products_bp.route('/my-offers')
@login_required
def my_offers():
    me = session['member_id']
    proposals = BargainingProposal.query.filter_by(buyer_id=me).order_by(
        BargainingProposal.created_at.desc()
    ).all()
    return render_template('my_offers.html', proposals=proposals)


# ─────────────────────────────────────────────
# Price Insight API endpoint
# ─────────────────────────────────────────────
@products_bp.route('/api/price-insight')
@login_required
def price_insight_api():
    """JSON endpoint returning price stats for a category. Used by add_product page."""
    category = request.args.get('category', '').strip()
    if not category:
        return jsonify(error='category required'), 400
    data = get_price_insight(category)
    if not data:
        return jsonify({}), 200
    return jsonify(data)
