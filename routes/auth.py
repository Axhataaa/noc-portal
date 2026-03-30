"""
NOC Portal — Auth routes
Handles login, register, logout, dashboard redirect, and Google OAuth flow.
Blueprint name: 'auth'
"""
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, session, current_app)
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import db_query
from utils.auth import current_user, log_action
from utils.logger import get_logger

logger = get_logger(__name__)

auth_bp = Blueprint('auth', __name__)


# ── Landing ──────────────────────────────────────────

@auth_bp.route('/')
def landing():
    return render_template('landing.html')


# ── Login ─────────────────────────────────────────────

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user():
        return redirect(url_for('auth.dashboard_redirect'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        pwd   = request.form.get('password', '')
        role  = request.form.get('role', '')

        any_user = db_query("SELECT * FROM users WHERE email=?", (email,), one=True)
        if not any_user:
            flash('No account found with this email. Please create an account first.', 'error')
            return redirect(url_for('auth.register'))

        row = db_query("SELECT * FROM users WHERE email=? AND role=?", (email, role), one=True)
        if not row:
            logger.warning('Login failed: %s tried role=%s but not registered', email, role)
            flash(f'This email is not registered as a {role.upper()}. Please select the correct role.', 'error')
        elif not row['is_active']:
            flash('Your account has been deactivated. Please contact the administrator.', 'error')
        elif not check_password_hash(row['password'], pwd):
            flash('Incorrect password. Please try again.', 'error')
        else:
            # CHECK BEFORE LOGIN
            if row['verification_required'] == 1:
                session.clear()
                session['temp_user_id'] = row['id']
                return redirect(url_for('auth.reverify', msg=1))

            # NORMAL LOGIN
            session.clear()
            session.permanent = True
            session['user_id'] = row['id']

            log_action('LOGIN', details=f'Logged in as {role}')
            logger.info('User %s logged in as %s', email, role)

            flash(f"Welcome back, {row['name']}!", 'success')
            return redirect(url_for('auth.dashboard_redirect'))
        
    return render_template('auth/login.html')


@auth_bp.route('/reverify', methods=['GET', 'POST'])
def reverify():

    if request.args.get('msg') and request.method == 'GET':
        flash("Re-verification required", "warning")
    
    user = current_user()
    user_id = None

    # If already logged in (shouldn't normally happen)
    if user:
        user_id = user['id']
    else:
        user_id = session.get('temp_user_id')

    if not user_id:
        return redirect(url_for('auth.login'))

    # Attempt limit: max 3 failed reverify attempts
    attempts = session.get('reverify_attempts', 0)
    if attempts >= 3:
        flash("Too many failed attempts. Try again later.", "error")
        session.clear()
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip()

        from utils.helpers import get_setting
        HOD_CODE   = get_setting('HOD_SECRET')
        ADMIN_CODE = get_setting('ADMIN_SECRET')

        row = db_query("SELECT * FROM users WHERE id=?", (user_id,), one=True)

        valid = False
        if row['role'] == 'hod' and code == HOD_CODE:
            valid = True
        elif row['role'] == 'admin' and code == ADMIN_CODE:
            valid = True

        if valid:
            from datetime import datetime
            db_query(
                "UPDATE users SET verification_required=0, is_verified=1, last_verified_at=? WHERE id=?",
                (datetime.now().isoformat(), user_id),
                commit=True
            )

            session.pop('reverify_attempts', None)
            session.clear()
            session['user_id'] = user_id
            session.permanent = True

            flash("Re-verification successful", "success")
            return redirect(url_for('auth.dashboard_redirect'))

        session['reverify_attempts'] = session.get('reverify_attempts', 0) + 1
        flash("Invalid code", "error")

    return render_template('auth/reverify.html')


# ── Register ──────────────────────────────────────────

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user():
        return redirect(url_for('auth.dashboard_redirect'))

    cfg          = current_app.config
    from utils.helpers import get_setting
    HOD_SECRET = get_setting('HOD_SECRET')
    ADMIN_SECRET = get_setting('ADMIN_SECRET')
    BRANCH_TO_DEPT = cfg['BRANCH_TO_DEPT']

    if request.method == 'POST':
        form   = {k: v.strip() if isinstance(v, str) else v for k, v in request.form.items()}
        name   = form.get('name', '')
        email  = form.get('email', '').lower()
        pwd    = form.get('password', '')
        conf   = form.get('confirm_password', '')
        role   = form.get('role', 'student')
        branch = form.get('branch', '')
        enroll = form.get('enrollment_no', '')
        secret = form.get('secret_code', '')

        if role == 'student':
            dept = BRANCH_TO_DEPT.get(branch, form.get('department', ''))
        elif role == 'hod':
            dept = form.get('department_hod', '').strip()
        else:
            dept = 'Administration'

        errors = {}
        if not name:  errors['name']  = 'Full name is required.'
        if not email: errors['email'] = 'Email address is required.'
        elif '@' not in email or '.' not in email.split('@')[-1]:
            errors['email'] = 'Please enter a valid email address.'
        if role == 'student' and not dept:         errors['department']   = 'Please select your department.'
        if role == 'student' and not branch:       errors['branch']       = 'Please select your branch.'
        if role == 'hod'     and not dept:         errors['department']   = 'Please select your department.'
        if role == 'student' and not enroll:       errors['enrollment_no'] = 'Enrollment number is required.'
        if role == 'hod'   and secret != HOD_SECRET:   errors['secret_code'] = 'Invalid HOD registration code. Contact your administrator.'
        if role == 'admin' and secret != ADMIN_SECRET: errors['secret_code'] = 'Invalid Admin registration code. Contact your system administrator.'
        if not pwd:           errors['password'] = 'Password is required.'
        elif len(pwd) < 6:    errors['password'] = 'Password must be at least 6 characters.'
        elif pwd != conf:     errors['confirm_password'] = 'Passwords do not match.'

        if not errors.get('email') and email:
            if db_query("SELECT 1 FROM users WHERE email=?", (email,), one=True):
                flash('An account with this email already exists. Please sign in.', 'error')
                return redirect(url_for('auth.login'))

        if errors:
            return render_template('auth/register.html', form=form, errors=errors)

        if role == 'admin':
            dept = 'Administration'
        branch_val = branch if role == 'student' else ''
        uid = db_query(
            "INSERT INTO users(name,email,password,role,department,branch,enrollment) VALUES(?,?,?,?,?,?,?)",
            (name, email, generate_password_hash(pwd), role, dept, branch_val, enroll),
            commit=True
        )
        log_action('REGISTER', entity_type='User', entity_id=uid)
        logger.info('New %s account registered: %s (id=%s)', role, email, uid)
        flash('Account created successfully! Please sign in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', form={}, errors={})


# ── Logout ────────────────────────────────────────────

@auth_bp.route('/logout')
def logout():
    if current_user():
        log_action('LOGOUT')
    session.clear()
    flash('Signed out successfully.', 'info')
    return redirect(url_for('auth.landing'))


# ── Dashboard redirect ────────────────────────────────

@auth_bp.route('/dashboard')
def dashboard_redirect():
    u = current_user()
    if not u:
        session.clear()
        return redirect(url_for('auth.login'))
    if u.get('verification_required') == 1:
        return redirect(url_for('auth.reverify'))
    routes = {
        'student': 'student.dashboard',
        'hod':     'hod.dashboard',
        'admin':   'admin.dashboard',
    }
    return redirect(url_for(routes.get(u['role'], 'auth.login')))


# ── Google OAuth ──────────────────────────────────────
@auth_bp.route('/auth/google/login')
def google_login():
    google_oauth_enabled = current_app.config.get('GOOGLE_OAUTH_ENABLED', False)
    if not google_oauth_enabled:
        flash('Google login is not configured on this server.', 'error')
        return redirect(url_for('auth.login'))
    if current_user():
        return redirect(url_for('auth.dashboard_redirect'))

    google = current_app.extensions['authlib.integrations.flask_client'].google

    import os
    BASE_URL = os.getenv("BASE_URL")

    redirect_uri = f"{BASE_URL}/auth/google/callback"
    print("REDIRECT_URI:", redirect_uri)

    return google.authorize_redirect(redirect_uri)


@auth_bp.route('/auth/google/callback')
def google_callback():
    google_oauth_enabled = current_app.config.get('GOOGLE_OAUTH_ENABLED', False)
    if not google_oauth_enabled:
        flash('Google login is not configured.', 'error')
        return redirect(url_for('auth.login'))
    try:
        google = current_app.extensions['authlib.integrations.flask_client'].google
        token     = google.authorize_access_token()
        user_info = token.get('userinfo') or google.userinfo()
        email     = user_info.get('email', '').lower()
        name      = user_info.get('name', '')
        google_id = user_info.get('sub', '')
    except Exception as exc:
        logger.warning('Google OAuth failed: %s', exc)
        flash('Google sign-in failed. Please try again or use email/password.', 'error')
        return redirect(url_for('auth.login'))

    if not email:
        flash('Could not retrieve email from Google. Please try again.', 'error')
        return redirect(url_for('auth.login'))

    existing = db_query("SELECT * FROM users WHERE email=?", (email,), one=True)
    if existing:
        if not existing['is_active']:
            flash('Your account has been deactivated. Contact the administrator.', 'error')
            return redirect(url_for('auth.login'))
        session.clear()
        session.permanent = True
        session['user_id'] = existing['id']
        log_action('GOOGLE_LOGIN', details=f'Google OAuth login for {email}')
        flash(f"Welcome back, {existing['name']}!", 'success')
        return redirect(url_for('auth.dashboard_redirect'))

    session['google_pending'] = {'email': email, 'name': name, 'google_id': google_id}
    flash('Google account verified! Please complete your registration below.', 'info')
    return redirect(url_for('auth.google_complete'))


@auth_bp.route('/auth/google/complete', methods=['GET', 'POST'])
def google_complete():
    pending = session.get('google_pending')
    if not pending:
        flash('Session expired. Please sign in with Google again.', 'error')
        return redirect(url_for('auth.login'))

    cfg            = current_app.config
    BRANCH_TO_DEPT = cfg['BRANCH_TO_DEPT']
    from utils.helpers import get_setting
    HOD_SECRET     = get_setting('HOD_SECRET') 
    ADMIN_SECRET   = get_setting('ADMIN_SECRET') 

    if request.method == 'POST':
        form       = {k: v.strip() for k, v in request.form.items()}
        errors     = {}
        name       = form.get('name', '')
        role       = form.get('role', 'student')
        branch     = form.get('branch', '')
        enroll     = form.get('enrollment_no', '')
        secret     = form.get('secret_code', '')
        password   = form.get('password', '')
        confirm_pw = form.get('confirm_password', '')

        if role == 'student':
            dept = BRANCH_TO_DEPT.get(branch, form.get('department', ''))
        elif role == 'hod':
            dept = form.get('department_hod', '').strip()
        else:
            dept = 'Administration'

        if not name:                                 errors['name']         = 'Full name is required.'
        if role == 'student' and not dept:           errors['department']   = 'Please select your department.'
        if role == 'student' and not branch:         errors['branch']       = 'Please select your branch.'
        if role == 'hod'     and not dept:           errors['department']   = 'Please select your department.'
        if role == 'student' and not enroll:         errors['enrollment_no'] = 'Enrollment number is required for students.'
        if role == 'hod'   and secret != HOD_SECRET:   errors['secret_code'] = 'Invalid HOD registration code.'
        if role == 'admin' and secret != ADMIN_SECRET: errors['secret_code'] = 'Invalid Admin registration code.'
        if len(password) < 6:   errors['password']         = 'Password must be at least 6 characters.'
        elif password != confirm_pw: errors['confirm_password'] = 'Passwords do not match.'

        if errors:
            return render_template('auth/google_complete.html', pending=pending, form=form, errors=errors)

        if db_query("SELECT 1 FROM users WHERE email=?", (pending['email'],), one=True):
            flash('An account with this email already exists. Please sign in.', 'error')
            session.pop('google_pending', None)
            return redirect(url_for('auth.login'))

        branch_val = branch if role == 'student' else ''
        uid = db_query(
            "INSERT INTO users(name,email,password,role,department,branch,enrollment) VALUES(?,?,?,?,?,?,?)",
            (name, pending['email'], generate_password_hash(password), role, dept, branch_val, enroll),
            commit=True
        )
        session.pop('google_pending', None)
        log_action('GOOGLE_REGISTER', entity_type='User', entity_id=uid,
                   details=f'New {role} via Google OAuth: {pending["email"]}')
        session['user_id'] = uid
        session.permanent = True
        flash(f"Welcome to NOC Portal, {name}!", 'success')
        return redirect(url_for('auth.dashboard_redirect'))

    return render_template('auth/google_complete.html', pending=pending, form={}, errors={})


# ─────────────────────────────────────────────────────────────────────────────
#  PUBLIC NOC VERIFICATION PAGE  (new feature — no auth required)
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route('/verify')
def verify_noc():
    noc_id = request.args.get('noc_id', '').strip()
    submitted = bool(request.args.get('verify'))  # key logic

    result = None
    error  = None

    if noc_id and submitted:
        row = db_query(
            """
            SELECT 
                a.noc_id,
                a.status,
                a.company_name,
                a.internship_role,
                a.start_date,
                a.end_date,
                a.approval_date,
                a.reviewed_at,
                u.name AS student_name,
                u.enrollment AS student_enrollment,
                u.branch AS student_branch
            FROM applications a
            JOIN users u ON a.student_id = u.id
            WHERE a.noc_id = ? AND a.status = 'Approved'
            """,
            (noc_id,), one=True
        )

        if row:
            result = dict(row)
        else:
            error = 'No valid NOC found. The certificate may be invalid or tampered.'

    return render_template(
        'verify_noc.html',
        noc_id=noc_id,
        result=result,
        error=error
    )