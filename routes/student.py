"""
NOC Portal — Student routes
Blueprint name: 'student'   prefix: /student
"""
import os
from datetime import date
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, abort, current_app, send_from_directory, jsonify)
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import db_query
from utils.auth import current_user, log_action, login_required, role_required
from utils.helpers import enrich, enrich_all
from utils.uploads import save_offer_letter, delete_offer_letter, validate_pdf
from utils.csrf import generate_csrf_token, validate_csrf_token
from utils.logger import get_logger

logger = get_logger(__name__)

student_bp = Blueprint('student', __name__, url_prefix='/student')


@student_bp.route('/dashboard')
@login_required
@role_required('student')
def dashboard():
    u    = current_user()
    rows = db_query("SELECT * FROM applications WHERE student_id=? ORDER BY created_at DESC", (u['id'],))
    apps = enrich_all(rows)
    stats = dict(
        total    = len(apps),
        pending  = sum(1 for a in apps if a['status'] == 'Pending'),
        approved = sum(1 for a in apps if a['status'] == 'Approved'),
        rejected = sum(1 for a in apps if a['status'] == 'Rejected'),
    )
    return render_template('student/dashboard.html', applications=apps, stats=stats)


@student_bp.route('/profile')
@login_required
@role_required('student')
def profile():
    u = current_user()
    latest_row = db_query(
        "SELECT * FROM applications WHERE student_id=? ORDER BY created_at DESC LIMIT 1",
        (u['id'],), one=True
    )
    return render_template('student/profile.html', latest_app=enrich(latest_row))


@student_bp.route('/change-password', methods=['POST'])
@login_required
@role_required('student')
def change_password():
    # CSRF validation
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
    return redirect(url_for('student.profile'))


@student_bp.route('/apply', methods=['GET', 'POST'])
@login_required
@role_required('student')
def apply():
    u    = current_user()
    form = {}

    if request.method == 'POST':
        # CSRF validation
        if not validate_csrf_token():
            abort(403)

        form = {k: v.strip() if isinstance(v, str) else v for k, v in request.form.items()}

        company             = form.get('company_name', '')
        role                = form.get('internship_role', '')
        s_str               = form.get('start_date', '')
        e_str               = form.get('end_date', '')
        stipend             = form.get('stipend', '')
        loc                 = form.get('location', '')
        desc                = form.get('description', '')
        company_address     = form.get('company_address', '')
        company_website     = form.get('company_website', '')
        manager_name        = form.get('manager_name', '')
        manager_designation = form.get('manager_designation', '')
        manager_email       = form.get('manager_email', '')
        manager_phone       = form.get('manager_phone', '')
        offer_letter_ref    = form.get('offer_letter_ref', '')
        internship_mode     = form.get('internship_mode', 'On-site')
        work_hours          = form.get('work_hours', '')
        noc_purpose         = form.get('noc_purpose', '')
        student_contact     = form.get('student_contact', '')
        academic_year       = form.get('academic_year', '')

        errors = {}
        if not company:         errors['company_name']    = 'Company name is required.'
        if not role:            errors['internship_role'] = 'Internship role is required.'
        if not loc:             errors['location']        = 'Location is required.'
        if not company_address: errors['company_address'] = 'Company address is required.'
        if not manager_name:    errors['manager_name']    = 'Manager name is required.'
        if not manager_email:   errors['manager_email']   = 'Manager email is required.'
        if not noc_purpose:     errors['noc_purpose']     = 'NOC purpose is required.'
        if not s_str:           errors['start_date']      = 'Start date is required.'
        if not e_str:           errors['end_date']        = 'End date is required.'
        if not student_contact: errors['student_contact'] = 'Your contact number is required.'
        if not academic_year:   errors['academic_year']   = 'Academic year is required.'

        # Offer letter PDF is compulsory at submission time
        uploaded_file = request.files.get('offer_letter_pdf')
        if False:  # offer letter is now optional
            errors['offer_letter_pdf'] = 'Offer letter PDF is required.'
        else:
            max_bytes = current_app.config.get('MAX_UPLOAD_BYTES', 5 * 1024 * 1024)
            uploaded_file.stream.seek(0, 2)
            file_size = uploaded_file.stream.tell()
            uploaded_file.stream.seek(0)
            if file_size > max_bytes:
                errors['offer_letter_pdf'] = f'File exceeds maximum size ({max_bytes // (1024*1024)} MB).'
            elif not validate_pdf(uploaded_file):
                errors['offer_letter_pdf'] = 'Only valid PDF files are accepted.'

        if s_str and e_str and 'start_date' not in errors and 'end_date' not in errors:
            try:
                s = date.fromisoformat(s_str)
                e = date.fromisoformat(e_str)
                if s < date.today():
                    errors['start_date'] = 'Start date cannot be in the past.'
                elif e <= s:
                    errors['end_date'] = 'End date must be after start date.'
                elif (e - s).days < 7:
                    errors['end_date'] = 'Duration must be at least 1 week.'
            except ValueError:
                errors['start_date'] = 'Invalid date format.'

        if errors:
            return render_template('student/apply.html', form=form, errors=errors)

        s     = date.fromisoformat(s_str)
        e     = date.fromisoformat(e_str)
        weeks = (e - s).days // 7
        sb    = db_query("SELECT branch FROM users WHERE id=?", (u['id'],), one=True)
        s_branch = sb['branch'] if sb and sb['branch'] else ''

        aid = db_query(
            """INSERT INTO applications
               (student_id, company_name, internship_role, start_date, end_date,
                duration_weeks, stipend, location, description, department, branch,
                company_address, company_website, manager_name, manager_designation,
                manager_email, manager_phone, offer_letter_ref,
                internship_mode, work_hours, noc_purpose,
                student_contact, academic_year)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (u['id'], company, role, s_str, e_str, weeks, stipend, loc, desc,
             u['department'], s_branch, company_address, company_website,
             manager_name, manager_designation, manager_email, manager_phone,
             offer_letter_ref, internship_mode, work_hours, noc_purpose,
             student_contact, academic_year),
            commit=True
        )

        # ── Save the compulsory offer letter (already validated above) ──
        uploaded_file = request.files.get('offer_letter_pdf')
        saved_name, original_name = save_offer_letter(uploaded_file, aid, u['id'])
        if saved_name:
            db_query(
                "UPDATE applications SET offer_letter_path=?, offer_letter_original_name=? WHERE id=?",
                (saved_name, original_name, aid), commit=True
            )
            log_action('UPLOAD_OFFER_LETTER', entity_type='Application', entity_id=aid,
                       details=f'Offer letter uploaded: {original_name}')

        log_action('APPLY', entity_type='Application', entity_id=aid,
                   details=f'{role} at {company}')
        logger.info('Application #%s submitted by student #%s (%s at %s)', aid, u['id'], role, company)
        flash(f'Application for {company} submitted successfully!', 'success')
        return redirect(url_for('student.dashboard'))

    return render_template('student/apply.html', form=form, errors={})


@student_bp.route('/application/<int:app_id>')
@login_required
@role_required('student')
def view_app(app_id):
    u   = current_user()
    row = db_query("SELECT * FROM applications WHERE id=? AND student_id=?", (app_id, u['id']), one=True)
    if not row:
        abort(404)
    return render_template('student/view_application.html', application=enrich(row))


@student_bp.route('/application/<int:app_id>/upload', methods=['POST'])
@login_required
@role_required('student')
def upload_offer_letter(app_id):
    """
    Upload or replace an offer letter PDF for a Pending application.
    Non-blocking: on failure, redirects back with a warning flash.
    """
    if not validate_csrf_token():
        abort(403)

    u   = current_user()
    row = db_query("SELECT * FROM applications WHERE id=? AND student_id=?", (app_id, u['id']), one=True)
    if not row:
        abort(404)
    if row['status'] != 'Pending':
        flash('Documents can only be updated on pending applications.', 'error')
        return redirect(url_for('student.view_app', app_id=app_id))

    uploaded_file = request.files.get('offer_letter_pdf')
    if not uploaded_file or not uploaded_file.filename:
        flash('No file selected.', 'error')
        return redirect(url_for('student.view_app', app_id=app_id))

    max_bytes = current_app.config.get('MAX_UPLOAD_BYTES', 5 * 1024 * 1024)
    uploaded_file.stream.seek(0, 2)
    file_size = uploaded_file.stream.tell()
    uploaded_file.stream.seek(0)

    if file_size > max_bytes:
        flash(f'File exceeds maximum allowed size ({max_bytes // (1024*1024)} MB).', 'error')
        return redirect(url_for('student.view_app', app_id=app_id))

    saved_name, original_name = save_offer_letter(uploaded_file, app_id, u['id'])
    if not saved_name:
        flash('Upload failed. Only valid PDF files are accepted.', 'error')
        return redirect(url_for('student.view_app', app_id=app_id))

    # Delete old file if replacing
    if row['offer_letter_path']:
        delete_offer_letter(row['offer_letter_path'])

    db_query("UPDATE applications SET offer_letter_path=?, offer_letter_original_name=? WHERE id=?",
             (saved_name, original_name, app_id), commit=True)
    log_action('UPLOAD_OFFER_LETTER', entity_type='Application', entity_id=app_id,
               details=f'Offer letter uploaded: {original_name}')
    flash('Offer letter uploaded successfully.', 'success')
    return redirect(url_for('student.view_app', app_id=app_id))


@student_bp.route('/my-nocs')
@login_required
@role_required('student')
def my_nocs():
    """Display all approved NOC applications — student decides when to generate."""
    u = current_user()
    try:
        from services.noc_generator import _ensure_noc_columns
        _ensure_noc_columns()
    except Exception:
        pass
    rows = db_query(
        """SELECT * FROM applications
           WHERE student_id=? AND status='Approved'
           ORDER BY reviewed_at DESC, created_at DESC""",
        (u['id'],)
    )
    nocs = [dict(r) for r in rows]
    return render_template('student/my_nocs.html', nocs=nocs)


@student_bp.route('/application/<int:app_id>/generate-noc', methods=['POST'])
@login_required
@role_required('student')
def generate_noc(app_id):
    """NOC generation — supports both AJAX (JSON) and regular form POST."""
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if not validate_csrf_token():
        if is_ajax:
            return jsonify(ok=False, error='CSRF validation failed'), 403
        abort(403)

    u = current_user()
    row = db_query(
        "SELECT * FROM applications WHERE id=? AND student_id=? AND status='Approved'",
        (app_id, u['id']), one=True
    )
    if not row:
        if is_ajax:
            return jsonify(ok=False, error='Application not found'), 404
        abort(404)
    row = dict(row)

    # Already generated — return existing info
    if row.get('noc_generated_at') and row.get('certificate_path'):
        if is_ajax:
            return jsonify(
                ok=True,
                already_done=True,
                noc_id=row.get('noc_id', ''),
                view_url=url_for('student.view_noc', app_id=app_id),
                download_url=url_for('student.download_noc', app_id=app_id),
            )
        flash('NOC certificate already generated.', 'info')
        return redirect(url_for('student.my_nocs'))

    try:
        from services.noc_generator import generate_noc_certificate
        cert = generate_noc_certificate(app_id, current_app.config)
        log_action('GENERATE_NOC', entity_type='Application', entity_id=app_id,
                   details=f'Student generated NOC for {row["company_name"]}')
        if is_ajax:
            return jsonify(
                ok=True,
                noc_id=cert['noc_id'],
                view_url=url_for('student.view_noc', app_id=app_id),
                download_url=url_for('student.download_noc', app_id=app_id),
            )
        flash('NOC certificate generated successfully!', 'success')
    except Exception as e:
        logger.error('NOC generation failed app #%s: %s', app_id, e)
        if is_ajax:
            return jsonify(ok=False, error=str(e)), 500
        flash(f'Could not generate NOC: {e}', 'error')
    return redirect(url_for('student.my_nocs'))


@student_bp.route('/view-noc/<int:app_id>')
@login_required
@role_required('student')
def view_noc(app_id):
    """Serve the NOC PDF inline for viewing in browser."""
    from flask import send_file
    u = current_user()
    row = db_query(
        "SELECT * FROM applications WHERE id=? AND student_id=? AND status='Approved'",
        (app_id, u['id']), one=True
    )
    if not row:
        abort(404)
    row = dict(row)
    if not row.get('certificate_path'):
        flash('NOC has not been generated yet.', 'info')
        return redirect(url_for('student.my_nocs'))
    certs_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'certificates')
    filepath  = os.path.join(certs_dir, row['certificate_path'])
    if not os.path.isfile(filepath):
        flash('Certificate file not found on server. Please regenerate.', 'error')
        return redirect(url_for('student.my_nocs'))
    log_action('VIEW_NOC', entity_type='Application', entity_id=app_id)
    return send_file(
        filepath,
        mimetype='application/pdf',
        as_attachment=False,
        download_name=f"{row.get('noc_id', 'NOC')}_NOC.pdf"
    )


@student_bp.route('/download-noc/<int:app_id>')
@login_required
@role_required('student')
def download_noc(app_id):
    """Download the generated NOC certificate PDF."""
    from flask import send_file
    u = current_user()
    try:
        from services.noc_generator import _ensure_noc_columns
        _ensure_noc_columns()
    except Exception:
        pass

    row = db_query(
        "SELECT * FROM applications WHERE id=? AND student_id=? AND status='Approved'",
        (app_id, u['id']), one=True
    )
    if not row:
        abort(404)
    row = dict(row)

    # Generate on-the-fly if missing
    if not row.get('certificate_path'):
        try:
            from services.noc_generator import generate_noc_certificate
            cert_info = generate_noc_certificate(app_id, current_app.config)
            row.update(cert_info)
        except Exception as e:
            logger.error('NOC cert generation failed for app #%s: %s', app_id, e)
            flash(f'Certificate could not be generated: {e}', 'error')
            return redirect(url_for('student.my_nocs'))

    certs_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'certificates')
    filename  = row.get('certificate_path', '')
    if not filename:
        flash('Certificate file not found. Please try again.', 'error')
        return redirect(url_for('student.my_nocs'))

    filepath = os.path.join(certs_dir, filename)
    if not os.path.isfile(filepath):
        flash('Certificate file missing on server. Please regenerate.', 'error')
        return redirect(url_for('student.my_nocs'))

    dl_name = f"{row.get('noc_id', 'NOC')}_Certificate.pdf"
    log_action('DOWNLOAD_NOC', entity_type='Application', entity_id=app_id,
               details=f"Student downloaded NOC: {filename}")
    return send_file(
        filepath,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=dl_name
    )


@student_bp.route('/application/<int:app_id>/delete', methods=['POST'])
@login_required
@role_required('student')
def delete_app(app_id):
    if not validate_csrf_token():
        abort(403)
    u   = current_user()
    row = db_query("SELECT * FROM applications WHERE id=? AND student_id=?", (app_id, u['id']), one=True)
    if not row:
        abort(404)
    if row['status'] != 'Pending':
        flash('Only pending applications can be withdrawn.', 'error')
        return redirect(url_for('student.dashboard'))
    # Clean up uploaded file if any
    if row['offer_letter_path']:
        delete_offer_letter(row['offer_letter_path'])
    log_action('WITHDRAW', entity_type='Application', entity_id=app_id,
               details=f"Withdrew application for {row['company_name']}")
    db_query("DELETE FROM applications WHERE id=?", (app_id,), commit=True)
    flash('Application withdrawn successfully.', 'info')
    return redirect(url_for('student.dashboard'))

