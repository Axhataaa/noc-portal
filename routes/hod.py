"""
NOC Portal — HOD routes
Blueprint name: 'hod'   prefix: /hod
"""
from datetime import datetime
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, abort)
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import db_query
from utils.auth import current_user, log_action, login_required, role_required
from utils.csrf import validate_csrf_token
from utils.helpers import enrich, enrich_all, paginate
from utils.email import send_notification
from utils.logger import get_logger

logger = get_logger(__name__)

hod_bp = Blueprint('hod', __name__, url_prefix='/hod')


@hod_bp.route('/dashboard')
@login_required
@role_required('hod')
def dashboard():
    u      = current_user()
    dept   = u['department']
    search = request.args.get('search', '').strip()
    sf     = request.args.get('status', '')

    sql    = """SELECT a.*, u.name AS student_name, u.enrollment AS student_enrollment,
                       u.branch AS branch
                FROM applications a JOIN users u ON a.student_id = u.id
                WHERE a.department = ?"""
    params = [dept]
    if sf:
        sql += " AND a.status = ?"; params.append(sf)
    if search:
        like = f'%{search}%'
        sql += " AND (u.name LIKE ? OR a.company_name LIKE ? OR a.internship_role LIKE ? OR u.enrollment LIKE ?)"
        params += [like, like, like, like]
    sql += " ORDER BY a.created_at DESC"

    all_apps = enrich_all(db_query(sql, params))
    page     = int(request.args.get('page', 1)) if request.args.get('page', '1').isdigit() else 1
    apps, total_pages, page = paginate(all_apps, page)

    all_rows = db_query("SELECT status FROM applications WHERE department=?", (dept,))
    stats = dict(
        total    = len(all_rows),
        pending  = sum(1 for r in all_rows if r['status'] == 'Pending'),
        approved = sum(1 for r in all_rows if r['status'] == 'Approved'),
        rejected = sum(1 for r in all_rows if r['status'] == 'Rejected'),
    )
    return render_template('hod/dashboard.html', applications=apps, stats=stats,
                           search=search, status_filter=sf, department=dept,
                           page=page, total_pages=total_pages, total_results=len(all_apps))


@hod_bp.route('/application/<int:app_id>')
@login_required
@role_required('hod')
def view_app(app_id):
    u   = current_user()
    row = db_query(
        """SELECT a.*, u.name AS student_name, u.email AS student_email,
                  u.enrollment AS student_enrollment, u.branch AS branch
           FROM applications a JOIN users u ON a.student_id = u.id
           WHERE a.id = ?""",
        (app_id,), one=True
    )
    if not row or row['department'] != u['department']:
        abort(403)
    return render_template('hod/view_application.html', application=enrich(row))


@hod_bp.route('/application/<int:app_id>/approve', methods=['POST'])
@login_required
@role_required('hod')
def approve(app_id):
    if not validate_csrf_token():
        abort(403)
    u   = current_user()
    row = db_query("SELECT * FROM applications WHERE id=?", (app_id,), one=True)
    if not row or row['department'] != u['department']:
        abort(403)
    if row['status'] != 'Pending':
        flash('Only pending applications can be acted upon.', 'error')
        return redirect(url_for('hod.dashboard'))
    remarks = request.form.get('remarks', '').strip()
    db_query(
        "UPDATE applications SET status='Approved', hod_remarks=?, reviewed_by=?, reviewed_at=? WHERE id=?",
        (remarks, u['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'), app_id),
        commit=True
    )
    # ── Generate NOC Certificate (new feature — non-destructive) ──────────────
    try:
        from flask import current_app
        from services.noc_generator import generate_noc_certificate
        generate_noc_certificate(app_id, current_app.config)
    except Exception as _cert_err:
        # Certificate generation failure must never block approval
        logger.warning('NOC certificate generation failed for app #%s: %s', app_id, _cert_err)
    # ─────────────────────────────────────────────────────────────────────────
    log_action('APPROVE', entity_type='Application', entity_id=app_id)
    logger.info('HOD #%s approved application #%s', u['id'], app_id)
    student = db_query("SELECT name, email FROM users WHERE id=?", (row['student_id'],), one=True)
    if student:
        send_notification(
            student['email'],
            f"✓ Internship Approved – {row['company_name']}",
            f"""<p>Dear {student['name']},</p>
            <p>Your internship application for <strong>{row['internship_role']}</strong> at
            <strong>{row['company_name']}</strong> has been <strong style="color:green">Approved</strong>
            by your HOD.</p>
            {"<p><strong>Remarks:</strong> " + remarks + "</p>" if remarks else ""}
            <p>Login to the NOC Portal to view your approval.</p>"""
        )
    flash('Application approved successfully!', 'success')
    return redirect(url_for('hod.dashboard'))


@hod_bp.route('/application/<int:app_id>/reject', methods=['POST'])
@login_required
@role_required('hod')
def reject(app_id):
    if not validate_csrf_token():
        abort(403)
    u   = current_user()
    row = db_query("SELECT * FROM applications WHERE id=?", (app_id,), one=True)
    if not row or row['department'] != u['department']:
        abort(403)
    if row['status'] != 'Pending':
        flash('Only pending applications can be acted upon.', 'error')
        return redirect(url_for('hod.dashboard'))
    remarks = request.form.get('remarks', '').strip()
    if not remarks:
        flash('A rejection reason is required.', 'error')
        return redirect(url_for('hod.view_app', app_id=app_id))
    db_query(
        "UPDATE applications SET status='Rejected', hod_remarks=?, reviewed_by=?, reviewed_at=? WHERE id=?",
        (remarks, u['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'), app_id),
        commit=True
    )
    log_action('REJECT', entity_type='Application', entity_id=app_id, details=remarks)
    logger.info('HOD #%s rejected application #%s — %s', u['id'], app_id, remarks[:60])
    student = db_query("SELECT name, email FROM users WHERE id=?", (row['student_id'],), one=True)
    if student:
        send_notification(
            student['email'],
            f"✕ Internship Application Update – {row['company_name']}",
            f"""<p>Dear {student['name']},</p>
            <p>Your internship application for <strong>{row['internship_role']}</strong> at
            <strong>{row['company_name']}</strong> has been <strong style="color:red">Rejected</strong>
            by your HOD.</p>
            <p><strong>Reason:</strong> {remarks}</p>
            <p>Login to the NOC Portal to view details and reapply if needed.</p>"""
        )
    flash('Application rejected.', 'info')
    return redirect(url_for('hod.dashboard'))


@hod_bp.route('/profile')
@login_required
@role_required('hod')
def profile():
    u = current_user()
    # Single aggregated query instead of 4 round-trips
    row = db_query(
        """SELECT
               COUNT(*) AS total,
               SUM(CASE WHEN status='Pending'  THEN 1 ELSE 0 END) AS pending,
               SUM(CASE WHEN status='Approved' THEN 1 ELSE 0 END) AS approved,
               SUM(CASE WHEN status='Rejected' THEN 1 ELSE 0 END) AS rejected
           FROM applications WHERE department=?""",
        (u['department'],), one=True
    )
    stats = dict(
        total    = row['total']    or 0,
        pending  = row['pending']  or 0,
        approved = row['approved'] or 0,
        rejected = row['rejected'] or 0,
    )
    return render_template('hod/profile.html', stats=stats)


@hod_bp.route('/change-password', methods=['POST'])
@login_required
@role_required('hod')
def change_password():
    if not validate_csrf_token():
        abort(403)
    u          = current_user()
    current_pw = request.form.get('current_password', '')
    new_pw     = request.form.get('new_password', '')
    confirm_pw = request.form.get('confirm_password', '')
    row        = db_query("SELECT password FROM users WHERE id=?", (u['id'],), one=True)
    if not check_password_hash(row['password'], current_pw):
        flash('Current password is incorrect.', 'error')
    elif len(new_pw) < 6:
        flash('New password must be at least 6 characters.', 'error')
    elif new_pw != confirm_pw:
        flash('New passwords do not match.', 'error')
    else:
        db_query("UPDATE users SET password=? WHERE id=?",
                 (generate_password_hash(new_pw), u['id']), commit=True)
        log_action('CHANGE_PASSWORD')
        flash('Password updated successfully.', 'success')
    return redirect(url_for('hod.profile'))
