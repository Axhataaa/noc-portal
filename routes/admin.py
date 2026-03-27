"""
NOC Portal — Admin routes
Blueprint name: 'admin'   prefix: /admin
"""
import csv, io
from datetime import date, datetime, timedelta
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, abort, make_response, current_app,
                   send_from_directory)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from database.db import db_query
from utils.auth import current_user, log_action, login_required, role_required
from utils.csrf import validate_csrf_token
from utils.helpers import enrich, enrich_all, paginate, fmt_date
from utils.logger import get_logger

logger = get_logger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/dashboard')
@login_required
@role_required('admin')
def dashboard():
    # Use explicit parameterized queries — avoids f-string SQL interpolation
    def _cnt(table_where: str, args: tuple = ()) -> int:
        """Safe COUNT helper — table_where must be a hardcoded string, never user input."""
        return db_query(f"SELECT COUNT(*) AS c FROM {table_where}", args, one=True)['c']

    total    = _cnt("applications")
    pending  = _cnt("applications WHERE status='Pending'")
    approved = _cnt("applications WHERE status='Approved'")
    rejected = _cnt("applications WHERE status='Rejected'")
    students = _cnt("users WHERE role='student'")
    hods     = _cnt("users WHERE role='hod'")
    reviewed = approved + rejected or 1

    stats = dict(
        total          = total,
        pending        = pending,
        approved       = approved,
        rejected       = rejected,
        students       = students,
        hods           = hods,
        approval_rate  = round(approved / reviewed * 100, 1),
        rejection_rate = round(rejected / reviewed * 100, 1),
    )

    dept_stats = [dict(r) for r in db_query("""
        SELECT department,
               COUNT(*) AS total,
               SUM(CASE WHEN status='Approved' THEN 1 ELSE 0 END) AS approved,
               SUM(CASE WHEN status='Rejected' THEN 1 ELSE 0 END) AS rejected,
               SUM(CASE WHEN status='Pending'  THEN 1 ELSE 0 END) AS pending
        FROM applications GROUP BY department ORDER BY total DESC
    """)]

    monthly_data = []
    for i in range(5, -1, -1):
        month_start = (date.today().replace(day=1) - timedelta(days=i * 30))
        month_end   = (month_start + timedelta(days=31)).replace(day=1)
        cnt = db_query(
            "SELECT COUNT(*) AS c FROM applications WHERE created_at >= ? AND created_at < ?",
            (month_start.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d')), one=True
        )['c']
        monthly_data.append({'month': month_start.strftime('%b %Y'), 'count': cnt})

    recent_apps = enrich_all(db_query(
        """SELECT a.*, u.name AS student_name, u.branch AS branch,
                  u.enrollment AS student_enrollment
           FROM applications a JOIN users u ON a.student_id=u.id
           ORDER BY a.created_at DESC LIMIT 10"""
    ))

    raw_logs = db_query(
        """SELECT l.*, u.name AS user_name
           FROM audit_logs l LEFT JOIN users u ON l.user_id=u.id
           ORDER BY l.timestamp DESC LIMIT 20"""
    )
    audit_logs = []
    for log_row in raw_logs:
        d = dict(log_row)
        d['timestamp_fmt'] = fmt_date(d.get('timestamp', ''))
        uname = d.get('user_name')
        d['user'] = {'name': uname} if uname else None
        audit_logs.append(d)

    top_companies = [
        (r['company_name'], r['cnt'])
        for r in db_query(
            "SELECT company_name, COUNT(*) AS cnt FROM applications "
            "GROUP BY company_name ORDER BY cnt DESC LIMIT 5"
        )
    ]

    return render_template('admin/dashboard.html',
                           stats=stats, dept_stats=dept_stats,
                           monthly_data=monthly_data, recent_apps=recent_apps,
                           audit_logs=audit_logs, top_companies=top_companies)


@admin_bp.route('/users')
@login_required
@role_required('admin')
def users():
    all_users = [dict(r) for r in db_query("SELECT * FROM users ORDER BY created_at DESC")]
    for u in all_users:
        u['created_at_fmt'] = fmt_date(u.get('created_at', ''))
    return render_template('admin/users.html', users=all_users)


@admin_bp.route('/applications')
@login_required
@role_required('admin')
def applications():
    sf     = request.args.get('status', '')
    df     = request.args.get('department', '')
    search = request.args.get('search', '').strip()

    sql    = """SELECT a.*, u.name AS student_name, u.enrollment AS student_enrollment,
                       u.branch AS branch
                FROM applications a JOIN users u ON a.student_id=u.id WHERE 1=1"""
    params = []
    if sf:     sql += " AND a.status=?";     params.append(sf)
    if df:     sql += " AND a.department=?"; params.append(df)
    if search:
        like = f'%{search}%'
        sql += " AND (u.name LIKE ? OR a.company_name LIKE ? OR a.internship_role LIKE ?)"
        params += [like, like, like]
    sql += " ORDER BY a.created_at DESC"

    all_apps = enrich_all(db_query(sql, params))
    page     = int(request.args.get('page', 1)) if request.args.get('page', '1').isdigit() else 1
    apps, total_pages, page = paginate(all_apps, page)

    depts = [r[0] for r in db_query(
        "SELECT DISTINCT department FROM applications WHERE department IS NOT NULL ORDER BY department"
    )]
    return render_template('admin/applications.html', applications=apps, departments=depts,
                           status_filter=sf, dept_filter=df, search=search,
                           page=page, total_pages=total_pages, total_results=len(all_apps))


@admin_bp.route('/export/csv')
@login_required
@role_required('admin')
def export_csv():
    apps = enrich_all(db_query(
        """SELECT a.*, u.name AS student_name, u.enrollment AS student_enrollment,
                  u.branch AS branch
           FROM applications a JOIN users u ON a.student_id=u.id
           ORDER BY a.created_at DESC"""
    ))
    out = io.StringIO()
    w   = csv.writer(out)
    # Header — all application fields in logical order
    w.writerow([
        'ID', 'Student', 'Enrollment', 'Department', 'Branch',
        'Contact', 'Academic Year',
        'Company', 'Role', 'Company Website',
        'Start Date', 'End Date', 'Duration', 'Work Hours',
        'Stipend', 'Location', 'Mode',
        'Company Address', 'Manager Name', 'Manager Designation',
        'Manager Email', 'Manager Phone',
        'Offer Letter Ref', 'NOC Purpose', 'Description',
        'Status', 'HOD Remarks', 'Reviewed By',
        'Submitted', 'Reviewed',
        'NOC ID', 'Approval Date',
    ])
    for a in apps:
        # Resolve reviewer name from reviewed_by ID if present
        reviewer_name = ''
        if a.get('reviewed_by'):
            rev_row = db_query(
                "SELECT name FROM users WHERE id=?", (a['reviewed_by'],), one=True
            )
            reviewer_name = rev_row['name'] if rev_row else str(a['reviewed_by'])
        w.writerow([
            a['id'],
            a.get('student_name', ''),
            a.get('student_enrollment', ''),
            a.get('department', ''),
            a.get('branch', ''),
            a.get('student_contact', ''),
            a.get('academic_year', ''),
            a.get('company_name', ''),
            a.get('internship_role', ''),
            a.get('company_website', ''),
            a.get('start_date', ''),
            a.get('end_date', ''),
            a.get('duration_display', ''),
            a.get('work_hours', ''),
            a.get('stipend', ''),
            a.get('location', ''),
            a.get('internship_mode', ''),
            a.get('company_address', ''),
            a.get('manager_name', ''),
            a.get('manager_designation', ''),
            a.get('manager_email', ''),
            a.get('manager_phone', ''),
            a.get('offer_letter_ref', ''),
            a.get('noc_purpose', ''),
            a.get('description', ''),
            a.get('status', ''),
            a.get('hod_remarks', ''),
            reviewer_name,
            a.get('created_at_fmt', ''),
            a.get('reviewed_at_fmt', ''),
            a.get('noc_id', ''),
            a.get('approval_date', ''),
        ])
    out.seek(0)
    resp = make_response(out.getvalue())
    resp.headers['Content-Disposition'] = 'attachment; filename=noc_applications.csv'
    resp.headers['Content-type'] = 'text/csv'
    return resp


@admin_bp.route('/add-user', methods=['POST'])
@login_required
@role_required('admin')
def add_user():
    if not validate_csrf_token():
        abort(403)
    BRANCH_TO_DEPT = current_app.config['BRANCH_TO_DEPT']
    name   = request.form.get('name', '').strip()
    email  = request.form.get('email', '').strip().lower()
    pwd    = request.form.get('password', '')
    role   = request.form.get('role', 'student')
    dept   = request.form.get('department', '').strip()
    enroll = request.form.get('enrollment_no', '').strip()

    if not all([name, email, pwd]):
        flash('Name, email and password are required.', 'error')
        return redirect(url_for('admin.users'))
    if len(pwd) < 6:
        flash('Password must be at least 6 characters.', 'error')
        return redirect(url_for('admin.users'))
    if db_query("SELECT 1 FROM users WHERE email=?", (email,), one=True):
        flash(f'An account with email {email} already exists.', 'error')
        return redirect(url_for('admin.users'))
    if role == 'admin':
        dept = 'Administration'

    branch_val = request.form.get('branch', '').strip() if role == 'student' else ''
    if branch_val and branch_val in BRANCH_TO_DEPT:
        dept = BRANCH_TO_DEPT[branch_val]
    uid = db_query(
        "INSERT INTO users(name,email,password,role,department,branch,enrollment) VALUES(?,?,?,?,?,?,?)",
        (name, email, generate_password_hash(pwd), role, dept, branch_val, enroll),
        commit=True
    )
    log_action('ADMIN_ADD_USER', entity_type='User', entity_id=uid,
               details=f'Admin created {role} account for {name}')
    logger.info('Admin created %s account for %s (id=%s)', role, email, uid)
    flash(f'Account for {name} ({role}) created successfully.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/user/<int:uid>/toggle', methods=['POST'])
@login_required
@role_required('admin')
def toggle_user(uid):
    if not validate_csrf_token():
        abort(403)
    me = current_user()
    if uid == me['id']:
        flash("You cannot deactivate your own account.", 'error')
        return redirect(url_for('admin.users'))
    row = db_query("SELECT * FROM users WHERE id=?", (uid,), one=True)
    if not row:
        abort(404)
    new_val = 0 if row['is_active'] else 1
    db_query("UPDATE users SET is_active=? WHERE id=?", (new_val, uid), commit=True)
    logger.info('Admin %s user #%s (%s)', 'activated' if new_val else 'deactivated', uid, row['name'])
    flash(f"User {row['name']} has been {'activated' if new_val else 'deactivated'}.", 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/user/<int:uid>/reset-password', methods=['POST'])
@login_required
@role_required('admin')
def reset_password(uid):
    if not validate_csrf_token():
        abort(403)
    row = db_query("SELECT * FROM users WHERE id=?", (uid,), one=True)
    if not row:
        abort(404)
    new_pwd = request.form.get('new_password', '').strip()
    if len(new_pwd) < 6:
        flash('New password must be at least 6 characters.', 'error')
        return redirect(url_for('admin.users'))
    db_query("UPDATE users SET password=? WHERE id=?",
             (generate_password_hash(new_pwd), uid), commit=True)
    log_action('RESET_PASSWORD', entity_type='User', entity_id=uid,
               details=f"Admin reset password for {row['name']}")
    flash(f"Password for {row['name']} has been reset successfully.", 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/user/<int:uid>/delete', methods=['POST'])
@login_required
@role_required('admin')
def delete_user(uid):
    if not validate_csrf_token():
        abort(403)
    me = current_user()
    if uid == me['id']:
        flash("You cannot delete your own account.", 'error')
        return redirect(url_for('admin.users'))
    row = db_query("SELECT * FROM users WHERE id=?", (uid,), one=True)
    if not row:
        abort(404)
    db_query("DELETE FROM audit_logs WHERE user_id=?", (uid,), commit=True)
    db_query("DELETE FROM applications WHERE student_id=?", (uid,), commit=True)
    db_query("DELETE FROM users WHERE id=?", (uid,), commit=True)
    log_action('DELETE_USER', entity_type='User', entity_id=uid,
               details=f"Permanently deleted user: {row['name']} ({row['email']})")
    logger.warning('Admin permanently deleted user #%s (%s / %s)', uid, row['name'], row['email'])
    flash(f"User {row['name']} has been permanently deleted.", 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/profile')
@login_required
@role_required('admin')
def profile():
    stats = dict(
        total_apps  = db_query("SELECT COUNT(*) AS c FROM applications", one=True)['c'],
        total_users = db_query("SELECT COUNT(*) AS c FROM users WHERE role != 'admin'", one=True)['c'],
        students    = db_query("SELECT COUNT(*) AS c FROM users WHERE role='student'", one=True)['c'],
        hods        = db_query("SELECT COUNT(*) AS c FROM users WHERE role='hod'", one=True)['c'],
    )
    return render_template('admin/profile.html', stats=stats)


@admin_bp.route('/change-password', methods=['POST'])
@login_required
@role_required('admin')
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
    return redirect(url_for('admin.profile'))



@admin_bp.route('/offer-letter/<int:app_id>')
@login_required
@role_required('admin', 'hod', 'student')
def download_offer_letter(app_id):
    """
    Serve an uploaded offer letter PDF securely.
    - Admin:   any application
    - HOD:     own department only
    - Student: own applications only
    """
    import os

    u = current_user()
    if u['role'] == 'hod':
        row = db_query("SELECT * FROM applications WHERE id=? AND department=?",
                       (app_id, u['department']), one=True)
    elif u['role'] == 'student':
        row = db_query("SELECT * FROM applications WHERE id=? AND student_id=?",
                       (app_id, u['id']), one=True)
    else:
        row = db_query("SELECT * FROM applications WHERE id=?", (app_id,), one=True)

    if not row:
        abort(404)

    filename = row['offer_letter_path']
    if not filename:
        flash('No offer letter has been uploaded for this application.', 'info')
        return redirect(request.referrer or url_for('admin.applications'))

    upload_dir = current_app.config['UPLOAD_FOLDER']
    safe_name  = secure_filename(filename)
    full_path  = os.path.join(upload_dir, safe_name)

    if not os.path.isfile(full_path):
        flash('Offer letter file not found on server.', 'error')
        return redirect(request.referrer or url_for('admin.applications'))

    # Students download with their original filename.
    # HOD/Admin get the structured name for easy identification.
    original = row['offer_letter_original_name'] if row['offer_letter_original_name'] else None
    if u['role'] == 'student' and original:
        dl_name = original
    else:
        dl_name = f'offer_letter_app_{app_id}.pdf'

    log_action('DOWNLOAD_OFFER_LETTER', entity_type='Application', entity_id=app_id,
               details=f'Downloaded by {u["role"]}: {safe_name}')
    return send_from_directory(
        upload_dir,
        safe_name,
        as_attachment=False,
        download_name=dl_name,
    )
