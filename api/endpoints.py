"""
NOC Portal — REST API Layer
JSON endpoints for programmatic access. All require an active session
(same auth as the web UI). These are ADDITIVE — existing template routes
are completely unchanged.

Base prefix: /api/v1
"""
from flask import Blueprint, jsonify, request, session
from database.db import db_query
from utils.auth import current_user
from utils.helpers import enrich, enrich_all
from utils.logger import get_logger

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')
logger = get_logger(__name__)


def _api_error(message: str, status: int) -> tuple:
    """
    Return a standardised JSON error response.
    JSON body:  {"error": "<message>", "status": <code>}
    HTTP status code matches the 'status' field.
    """
    return jsonify({'error': message, 'status': status}), status


def _api_auth():
    """Return current user dict or None. Used to protect API endpoints."""
    return current_user()


def _require_roles(*roles):
    """
    Validate session auth and role membership.
    Returns (user_dict, None) on success, or (None, error_response) on failure.
    """
    u = _api_auth()
    if not u:
        return None, _api_error('Authentication required. Please log in.', 401)
    if u['role'] not in roles:
        return None, _api_error('Access denied. Insufficient permissions.', 403)
    return u, None


# ── Health check ──────────────────────────────────────

@api_bp.route('/health')
def health():
    """Simple health check — no auth required."""
    return jsonify({'status': 'ok', 'service': 'NOC Portal API', 'version': '1.0', 'message': 'All systems operational'})


# ── Applications ──────────────────────────────────────

@api_bp.route('/applications')
def list_applications():
    """
    List applications. Scoped by role:
      - student → own applications only
      - hod     → their department's applications
      - admin   → all applications

    Optional query params: status, department, page (default 1), per_page (default 20)
    """
    u, err = _require_roles('student', 'hod', 'admin')
    if err: return err

    status = request.args.get('status', '')
    dept   = request.args.get('department', '')
    page   = max(1, int(request.args.get('page', 1))) if request.args.get('page', '1').isdigit() else 1
    per    = min(100, max(1, int(request.args.get('per_page', 20)))) if request.args.get('per_page', '20').isdigit() else 20

    sql    = """SELECT a.*, u.name AS student_name, u.enrollment AS student_enrollment,
                       u.branch AS branch
                FROM applications a JOIN users u ON a.student_id=u.id WHERE 1=1"""
    params = []

    if u['role'] == 'student':
        sql += " AND a.student_id=?"; params.append(u['id'])
    elif u['role'] == 'hod':
        sql += " AND a.department=?"; params.append(u['department'])

    if status:
        sql += " AND a.status=?"; params.append(status)
    if dept and u['role'] == 'admin':
        sql += " AND a.department=?"; params.append(dept)

    sql += " ORDER BY a.created_at DESC"
    all_apps = enrich_all(db_query(sql, params))

    total    = len(all_apps)
    start    = (page - 1) * per
    page_items = all_apps[start:start + per]

    # Serialize — remove password-adjacent fields, keep UI-safe fields
    def serialize(a):
        return {
            'id':              a['id'],
            'student_name':    a.get('student_name'),
            'enrollment':      a.get('student_enrollment'),
            'company_name':    a['company_name'],
            'internship_role': a['internship_role'],
            'department':      a.get('department'),
            'branch':          a.get('branch'),
            'location':        a.get('location'),
            'internship_mode': a.get('internship_mode'),
            'start_date':      a.get('start_date'),
            'end_date':        a.get('end_date'),
            'duration':        a.get('duration_display'),
            'stipend':         a.get('stipend'),
            'status':          a['status'],
            'hod_remarks':     a.get('hod_remarks'),
            'submitted_at':    a.get('created_at'),
            'reviewed_at':     a.get('reviewed_at'),
        }

    return jsonify({
        'total':    total,
        'page':     page,
        'per_page': per,
        'pages':    max(1, (total + per - 1) // per),
        'data':     [serialize(a) for a in page_items],
    })


@api_bp.route('/applications/<int:app_id>')
def get_application(app_id):
    """Get a single application by ID. Scoped by role."""
    u, err = _require_roles('student', 'hod', 'admin')
    if err: return err

    row = db_query(
        """SELECT a.*, u.name AS student_name, u.enrollment AS student_enrollment,
                  u.branch AS branch, u.email AS student_email
           FROM applications a JOIN users u ON a.student_id=u.id
           WHERE a.id=?""",
        (app_id,), one=True
    )
    if not row:
        return _api_error('Application not found.', 404)

    a = enrich(row)

    # Access control
    if u['role'] == 'student' and a['student_id'] != u['id']:
        return _api_error('Access denied. You do not have permission to view this resource.', 403)
    if u['role'] == 'hod' and a['department'] != u['department']:
        return _api_error('Access denied. You do not have permission to view this resource.', 403)

    return jsonify({
        'id':                 a['id'],
        'student_name':       a.get('student_name'),
        'student_email':      a.get('student_email'),
        'enrollment':         a.get('student_enrollment'),
        'company_name':       a['company_name'],
        'internship_role':    a['internship_role'],
        'department':         a.get('department'),
        'branch':             a.get('branch'),
        'location':           a.get('location'),
        'internship_mode':    a.get('internship_mode'),
        'start_date':         a.get('start_date'),
        'end_date':           a.get('end_date'),
        'duration':           a.get('duration_display'),
        'stipend':            a.get('stipend'),
        'work_hours':         a.get('work_hours'),
        'company_address':    a.get('company_address'),
        'company_website':    a.get('company_website'),
        'manager_name':       a.get('manager_name'),
        'manager_email':      a.get('manager_email'),
        'manager_phone':      a.get('manager_phone'),
        'offer_letter_ref':   a.get('offer_letter_ref'),
        'noc_purpose':        a.get('noc_purpose'),
        'description':        a.get('description'),
        'student_contact':    a.get('student_contact'),
        'academic_year':      a.get('academic_year'),
        'status':             a['status'],
        'hod_remarks':        a.get('hod_remarks'),
        'submitted_at':       a.get('created_at'),
        'reviewed_at':        a.get('reviewed_at'),
    })


# ── Users (admin only) ────────────────────────────────

@api_bp.route('/users')
def list_users():
    """List all users. Admin only."""
    u, err = _require_roles('admin')
    if err: return err

    role_filter = request.args.get('role', '')
    sql    = "SELECT id, name, email, role, department, branch, enrollment, is_active, created_at FROM users WHERE 1=1"
    params = []
    if role_filter:
        sql += " AND role=?"; params.append(role_filter)
    sql += " ORDER BY created_at DESC"

    rows = db_query(sql, params)
    return jsonify({
        'total': len(rows),
        'data': [dict(r) for r in rows],
    })


@api_bp.route('/users/<int:uid>')
def get_user(uid):
    """Get a single user by ID. Admin only."""
    u, err = _require_roles('admin')
    if err: return err

    row = db_query(
        "SELECT id, name, email, role, department, branch, enrollment, is_active, created_at FROM users WHERE id=?",
        (uid,), one=True
    )
    if not row:
        return _api_error('User not found.', 404)
    return jsonify(dict(row))


# ── Statistics ────────────────────────────────────────

def _count_where(table_clause: str, args: tuple = ()) -> int:
    """Count rows matching a WHERE clause fragment. Used by stats()."""
    return db_query(f"SELECT COUNT(*) AS c FROM {table_clause}", args, one=True)['c']


@api_bp.route('/stats')
def stats():
    """
    System statistics. Admin gets global stats; HOD gets department stats;
    student gets their own counts.
    """
    u, err = _require_roles('student', 'hod', 'admin')
    if err: return err

    if u['role'] == 'admin':
        return jsonify({
            'scope':    'global',
            'total':    _count_where("applications"),
            'pending':  _count_where("applications WHERE status='Pending'"),
            'approved': _count_where("applications WHERE status='Approved'"),
            'rejected': _count_where("applications WHERE status='Rejected'"),
            'students': _count_where("users WHERE role='student'"),
            'hods':     _count_where("users WHERE role='hod'"),
        })

    elif u['role'] == 'hod':
        dept = u['department']
        rows = db_query("SELECT status FROM applications WHERE department=?", (dept,))
        return jsonify({
            'scope':      'department',
            'department': dept,
            'total':      len(rows),
            'pending':    sum(1 for r in rows if r['status'] == 'Pending'),
            'approved':   sum(1 for r in rows if r['status'] == 'Approved'),
            'rejected':   sum(1 for r in rows if r['status'] == 'Rejected'),
        })

    else:  # student
        rows = db_query("SELECT status FROM applications WHERE student_id=?", (u['id'],))
        return jsonify({
            'scope':    'personal',
            'total':    len(rows),
            'pending':  sum(1 for r in rows if r['status'] == 'Pending'),
            'approved': sum(1 for r in rows if r['status'] == 'Approved'),
            'rejected': sum(1 for r in rows if r['status'] == 'Rejected'),
        })


# ── Backward-compatible shorthand routes ─────────────────────────
# These are the exact routes specified in the brief:
#   /api/applications       → all applications (role-scoped)
#   /api/status/<id>        → single application status

@api_bp.route('/applications/all')
def applications_all():
    """
    GET /api/v1/applications/all
    Alias for list_applications — returns all applications scoped by role.
    Identical payload format to /api/v1/applications.
    """
    return list_applications()


@api_bp.route('/status/<int:app_id>')
def application_status(app_id):
    """
    GET /api/v1/status/<app_id>
    Return the status of a single application.
    Scoped by role — students can only check their own.
    """
    u, err = _require_roles('student', 'hod', 'admin')
    if err: return err

    row = db_query(
        "SELECT id, student_id, department, status, hod_remarks, reviewed_at "
        "FROM applications WHERE id=?",
        (app_id,), one=True
    )
    if not row:
        return _api_error('Application not found.', 404)

    a = dict(row)

    # Access control
    if u['role'] == 'student' and a['student_id'] != u['id']:
        return _api_error('Access denied. You do not have permission to view this resource.', 403)
    if u['role'] == 'hod' and a['department'] != u['department']:
        return _api_error('Access denied. You do not have permission to view this resource.', 403)

    return jsonify({
        'application_id': a['id'],
        'status':         a['status'],
        'hod_remarks':    a.get('hod_remarks'),
        'reviewed_at':    a.get('reviewed_at'),
    })


# ── Departments ───────────────────────────────────────

@api_bp.route('/departments')
def departments():
    """
    GET /api/v1/departments
    Returns the department → branches mapping used in registration forms.
    No authentication required — this is public reference data.

    Response shape:
        {
            "departments": ["Computer Science", ...],
            "branches_by_dept": {"Computer Science": ["CSE", "CSD"], ...},
            "branch_to_dept": {"Computer Science and Engineering": "Computer Science", ...}
        }
    """
    from flask import current_app
    cfg = current_app.config
    return jsonify({
        'departments':       list(cfg['DEPT_TO_BRANCHES'].keys()),
        'branches_by_dept':  cfg['DEPT_TO_BRANCHES'],
        'branch_to_dept':    cfg['BRANCH_TO_DEPT'],
        'branch_short':      cfg['BRANCH_SHORT'],
    })
