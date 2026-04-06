"""
bazaar/app/routes/transactions.py

Upgraded with:
  - Verified Handshake System: buyer + seller must both confirm to complete a deal
  - Preferred Pickup Points: selectable campus locations per transaction
  - Concurrency handling: atomic DB updates to prevent double-confirmation race
  - Karma update fires only when BOTH parties confirm
"""

from flask import Blueprint, render_template, request, session, flash, redirect, url_for, jsonify
from sqlalchemy import exc
from ..models import db, TransactionHistory, Product, CAMPUS_PICKUP_POINTS
from ..helpers import login_required, log_action, notify, recalculate_karma

transactions_bp = Blueprint('transactions', __name__)


@transactions_bp.route('/transactions')
@login_required
def my_transactions():
    me   = session['member_id']
    role = request.args.get('role', '')

    query = TransactionHistory.query.filter(
        (TransactionHistory.buyer_id == me) |
        (TransactionHistory.seller_id == me)
    )
    if role == 'buyer':
        query = TransactionHistory.query.filter_by(buyer_id=me)
    elif role == 'seller':
        query = TransactionHistory.query.filter_by(seller_id=me)

    txns = query.order_by(TransactionHistory.created_at.desc()).all()

    total_spent = sum(
        float(t.amount) for t in txns if t.buyer_id == me and t.status == 'completed'
    )
    total_earned = sum(
        float(t.amount) for t in txns if t.seller_id == me and t.status == 'completed'
    )

    return render_template('transactions.html',
                           txns=txns,
                           role_filter=role,
                           total_spent=total_spent,
                           total_earned=total_earned,
                           pickup_points=CAMPUS_PICKUP_POINTS)


@transactions_bp.route('/transactions/<int:txn_id>/confirm', methods=['POST'])
@login_required
def confirm_transaction(txn_id):
    """
    Verified Handshake: the current user confirms their side of the deal.
    Uses an atomic DB update to avoid race conditions if both parties click
    at the same time.  When both confirmations are recorded, the transaction
    is atomically flipped to 'completed' and karma is recalculated.
    """
    me  = session['member_id']
    txn = TransactionHistory.query.get_or_404(txn_id)

    # Only participants can confirm
    if me not in (txn.buyer_id, txn.seller_id):
        flash('You are not part of this transaction.', 'danger')
        return redirect(url_for('transactions.my_transactions'))

    if txn.status == 'completed':
        flash('This transaction is already completed.', 'info')
        return redirect(url_for('transactions.my_transactions'))

    if txn.status == 'cancelled':
        flash('This transaction has been cancelled.', 'warning')
        return redirect(url_for('transactions.my_transactions'))

    # --- Atomic update to prevent double-submit race conditions ---
    try:
        if me == txn.buyer_id and not txn.buyer_confirmed:
            # Use a WHERE clause update so two simultaneous clicks don't both succeed
            rows = (db.session.query(TransactionHistory)
                    .filter_by(txn_id=txn_id, buyer_confirmed=False)
                    .update({'buyer_confirmed': True}))
            db.session.commit()
            if rows == 0:
                flash('Already confirmed as buyer.', 'info')
                return redirect(url_for('transactions.my_transactions'))
            flash('✅ You confirmed the deal as buyer.', 'success')
            log_action('UPDATE', f'Buyer confirmed txn #{txn_id}')
            notify(txn.seller_id,
                   'Buyer confirmed deal',
                   f'Buyer has confirmed transaction #{txn_id}. Please confirm your side to complete.',
                   url_for('transactions.my_transactions'))

        elif me == txn.seller_id and not txn.seller_confirmed:
            rows = (db.session.query(TransactionHistory)
                    .filter_by(txn_id=txn_id, seller_confirmed=False)
                    .update({'seller_confirmed': True}))
            db.session.commit()
            if rows == 0:
                flash('Already confirmed as seller.', 'info')
                return redirect(url_for('transactions.my_transactions'))
            flash('✅ You confirmed the deal as seller.', 'success')
            log_action('UPDATE', f'Seller confirmed txn #{txn_id}')
            notify(txn.buyer_id,
                   'Seller confirmed deal',
                   f'Seller has confirmed transaction #{txn_id}. Please confirm your side to complete.',
                   url_for('transactions.my_transactions'))
        else:
            flash('You have already confirmed this transaction.', 'info')
            return redirect(url_for('transactions.my_transactions'))

        # Re-fetch to get latest state after commit
        db.session.refresh(txn)

        # Check if BOTH parties have now confirmed — if so, complete atomically
        if txn.buyer_confirmed and txn.seller_confirmed:
            rows = (db.session.query(TransactionHistory)
                    .filter_by(txn_id=txn_id, status='pending')
                    .update({'status': 'completed'}))
            if rows > 0:
                # Mark product as sold
                if txn.product_id:
                    product = Product.query.get(txn.product_id)
                    if product:
                        product.is_available = False
                        product.status = 'sold'
                db.session.commit()

                # Update karma for both parties
                recalculate_karma(txn.buyer_id)
                recalculate_karma(txn.seller_id)

                log_action('UPDATE', f'Transaction #{txn_id} completed via handshake')
                notify(txn.buyer_id,  '🎉 Deal Complete!',
                       f'Transaction #{txn_id} is now complete. Karma updated!',
                       url_for('transactions.my_transactions'))
                notify(txn.seller_id, '🎉 Deal Complete!',
                       f'Transaction #{txn_id} is now complete. Karma updated!',
                       url_for('transactions.my_transactions'))
                flash('🎉 Both parties confirmed — deal is now COMPLETE!', 'success')

    except exc.SQLAlchemyError as e:
        db.session.rollback()
        flash('Database error — please try again.', 'danger')

    return redirect(url_for('transactions.my_transactions'))


@transactions_bp.route('/transactions/<int:txn_id>/set-pickup', methods=['POST'])
@login_required
def set_pickup_point(txn_id):
    """Allow either party to set/update the pickup point for a pending transaction."""
    me  = session['member_id']
    txn = TransactionHistory.query.get_or_404(txn_id)

    if me not in (txn.buyer_id, txn.seller_id):
        return jsonify(error='Not authorised'), 403

    if txn.status == 'completed':
        return jsonify(error='Transaction already completed'), 400

    pickup = request.form.get('pickup_point', '').strip()
    if pickup:
        txn.pickup_point = pickup
        db.session.commit()
        log_action('UPDATE', f'Pickup point set to {pickup} for txn #{txn_id}')
        flash(f'Pickup point set to: {pickup}', 'success')

    return redirect(url_for('transactions.my_transactions'))
