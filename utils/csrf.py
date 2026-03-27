"""
NOC Portal — Lightweight CSRF Protection
Implements the synchronizer token pattern using Flask sessions.
No external dependency required.

Usage in templates:
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">

Usage in routes (via decorator):
    @csrf_protect
    def my_post_route():
        ...
"""
import secrets
import functools
from flask import session, request, abort


def generate_csrf_token() -> str:
    """
    Return (and store) a CSRF token for the current session.
    Generates a new one if none exists.
    """
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']


def validate_csrf_token() -> bool:
    """
    Check that the token submitted in the form matches the one in session.
    Accepts token from form field or X-CSRFToken header (for API callers).
    """
    token = (
        request.form.get('csrf_token') or
        request.headers.get('X-CSRFToken')
    )
    session_token = session.get('_csrf_token')
    return bool(token and session_token and secrets.compare_digest(token, session_token))


def csrf_protect(f):
    """
    Decorator: validate CSRF token on POST/PUT/DELETE/PATCH requests.
    Aborts with 403 if token is missing or invalid.

    Apply to any state-changing route:
        @app.route('/some-form', methods=['POST'])
        @csrf_protect
        def some_form():
            ...
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
            if not validate_csrf_token():
                abort(403)
        return f(*args, **kwargs)
    return decorated
