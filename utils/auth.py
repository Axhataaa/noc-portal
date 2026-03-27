"""
NOC Portal — Authentication helpers
current_user(), log_action(), login_required, role_required.
"""
import functools
from flask import session, redirect, url_for, flash, request
from database.db import db_query


def current_user():
    """Return the logged-in user as a dict, or None if not logged in / deactivated."""
    uid = session.get('user_id')
    if not uid:
        return None
    row = db_query("SELECT * FROM users WHERE id=? AND is_active=1", (uid,), one=True)
    return dict(row) if row else None


def log_action(action, entity_type=None, entity_id=None, details=None):
    """Write an audit log entry for the current user and request."""
    db_query(
        "INSERT INTO audit_logs(user_id,action,entity_type,entity_id,details,ip_address) VALUES(?,?,?,?,?,?)",
        (session.get('user_id'), action, entity_type, entity_id, details, request.remote_addr),
        commit=True
    )


def login_required(f):
    """Decorator: redirect to login if user is not authenticated."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not current_user():
            session.clear()
            flash('Please log in to continue.', 'info')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    """Decorator factory: abort with 403-redirect if user lacks the required role."""
    def decorator(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            u = current_user()
            if not u or u['role'] not in roles:
                flash('Access denied.', 'error')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated
    return decorator
