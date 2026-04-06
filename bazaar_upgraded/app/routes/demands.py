from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from ..models import db, Demand
from ..helpers import login_required, log_action

demands_bp = Blueprint('demands', __name__)

CATEGORIES = ['Books', 'Electronics', 'Clothing', 'Stationery', 'Sports', 'Other']


@demands_bp.route('/demands')
@login_required
def list_demands():
    category = request.args.get('category', '')
    query = Demand.query.filter_by(status='open')
    if category:
        query = query.filter_by(category=category)
    demands = query.order_by(Demand.created_at.desc()).all()
    return render_template('demands.html',
                           demands=demands,
                           categories=CATEGORIES,
                           selected_category=category)


@demands_bp.route('/demands/add', methods=['GET', 'POST'])
@login_required
def add_demand():
    if request.method == 'POST':
        title       = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category    = request.form.get('category', '')
        budget      = request.form.get('budget', '')

        if not title:
            flash('Title is required.', 'danger')
            return render_template('add_demand.html', categories=CATEGORIES)

        budget_val = None
        if budget:
            try:
                budget_val = float(budget)
            except ValueError:
                flash('Invalid budget.', 'danger')
                return render_template('add_demand.html', categories=CATEGORIES)

        demand = Demand(
            member_id   = session['member_id'],
            title       = title,
            description = description,
            category    = category,
            budget      = budget_val
        )
        db.session.add(demand)
        db.session.commit()
        log_action('INSERT', f'Demand raised: {title}')
        flash('Demand posted!', 'success')
        return redirect(url_for('demands.list_demands'))

    return render_template('add_demand.html', categories=CATEGORIES)


@demands_bp.route('/demands/<int:demand_id>/close', methods=['POST'])
@login_required
def close_demand(demand_id):
    demand = Demand.query.get_or_404(demand_id)
    if demand.member_id != session['member_id'] and session.get('role') != 'admin':
        flash('Permission denied.', 'danger')
        return redirect(url_for('demands.list_demands'))

    demand.status = 'closed'
    db.session.commit()
    log_action('UPDATE', f'Demand closed: {demand.title}')
    flash('Demand closed.', 'info')
    return redirect(url_for('demands.list_demands'))
