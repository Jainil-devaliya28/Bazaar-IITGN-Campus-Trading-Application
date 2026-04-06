from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from ..models import db, Log, Member, Product, Feedback, TransactionHistory, Report
from ..helpers import admin_required, log_action

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin')
@admin_required
def dashboard():
    total_members   = Member.query.count()
    total_products  = Product.query.count()
    total_txns      = TransactionHistory.query.count()
    total_feedbacks = Feedback.query.count()
    open_reports    = Report.query.filter_by(status='open').count()
    recent_logs     = Log.query.order_by(Log.timestamp.desc()).limit(10).all()

    return render_template('admin_dashboard.html',
                           total_members=total_members,
                           total_products=total_products,
                           total_txns=total_txns,
                           total_feedbacks=total_feedbacks,
                           open_reports=open_reports,
                           recent_logs=recent_logs)


@admin_bp.route('/admin/logs')
@admin_required
def logs():
    page     = request.args.get('page', 1, type=int)
    action_f = request.args.get('action', '')
    query    = Log.query
    if action_f:
        query = query.filter_by(action_type=action_f)
    logs_pag     = query.order_by(Log.timestamp.desc()).paginate(page=page, per_page=30)
    action_types = [a[0] for a in db.session.query(Log.action_type).distinct().all()]
    return render_template('admin_logs.html',
                           logs=logs_pag,
                           action_types=action_types,
                           selected_action=action_f)


@admin_bp.route('/admin/members')
@admin_required
def members():
    members = Member.query.order_by(Member.created_at.desc()).all()
    return render_template('admin_members.html', members=members)


@admin_bp.route('/admin/member/<int:member_id>/toggle-role', methods=['POST'])
@admin_required
def toggle_role(member_id):
    member = Member.query.get_or_404(member_id)
    if member.member_id == session['member_id']:
        flash("You can't change your own role.", 'warning')
        return redirect(url_for('admin.members'))
    member.role = 'user' if member.role == 'admin' else 'admin'
    db.session.commit()
    log_action('UPDATE', f'Role changed for member {member.email} to {member.role}')
    flash(f'Role updated to {member.role}.', 'success')
    return redirect(url_for('admin.members'))


@admin_bp.route('/admin/products')
@admin_required
def all_products():
    from ..routes.products import CATEGORIES
    search   = request.args.get('search', '').strip()
    category = request.args.get('category', '')
    page     = request.args.get('page', 1, type=int)
    query    = Product.query
    if search:
        query = query.filter(Product.title.ilike(f'%{search}%'))
    if category:
        query = query.filter_by(category=category)
    products_pag = query.order_by(Product.created_at.desc()).paginate(page=page, per_page=25)
    return render_template('admin_products.html',
                           products=products_pag,
                           search=search,
                           selected_category=category,
                           categories=CATEGORIES)


@admin_bp.route('/admin/feedbacks')
@admin_required
def feedbacks():
    feedbacks = Feedback.query.order_by(Feedback.created_at.desc()).all()
    return render_template('admin_feedbacks.html', feedbacks=feedbacks)


@admin_bp.route('/admin/reports')
@admin_required
def reports():
    status   = request.args.get('status', 'open')
    query    = Report.query
    if status:
        query = query.filter_by(status=status)
    reports = query.order_by(Report.created_at.desc()).all()
    return render_template('admin_reports.html', reports=reports, status_filter=status)


@admin_bp.route('/admin/report/<int:report_id>/update', methods=['POST'])
@admin_required
def update_report(report_id):
    report     = Report.query.get_or_404(report_id)
    new_status = request.form.get('status', 'reviewed')
    report.status = new_status
    db.session.commit()
    log_action('UPDATE', f'Report {report_id} marked as {new_status}')
    flash(f'Report marked as {new_status}.', 'success')
    return redirect(url_for('admin.reports'))
