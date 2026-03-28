"""
NOC Portal — Application Factory
────────────────────────────────
Creates and configures the Flask app, registers all blueprints,
sets up Jinja globals, security headers, and boots the database.

Run:  python app.py
"""
from dotenv import load_dotenv
load_dotenv(override=True)

from flask import Flask
from config.config import Config

import os
from datetime import datetime
from flask import Flask, render_template

# ── Optional Google OAuth ─────────────────────────────
try:
    from authlib.integrations.flask_client import OAuth
    OAUTH_AVAILABLE = True
except ImportError:
    OAUTH_AVAILABLE = False


def create_app():
    """Application factory — returns a configured Flask app."""
    app = Flask(__name__, template_folder='templates', static_folder='static')

    # ── Load config ───────────────────────────────────
    from config.config import Config   # canonical path (settings.py re-exports this)
    app.config.from_object(Config)
    print("CONFIG CLIENT ID:", app.config.get('GOOGLE_CLIENT_ID'))

    app.config['BASE_URL'] = os.environ.get("BASE_URL", "http://localhost:5000")

    # ── Google OAuth setup (optional) ─────────────────
    google_enabled = bool(
        app.config.get('GOOGLE_CLIENT_ID') and
        app.config.get('GOOGLE_CLIENT_SECRET') and
        OAUTH_AVAILABLE
    )
    app.config['GOOGLE_OAUTH_ENABLED'] = google_enabled

    if google_enabled:
        oauth = OAuth(app)
        oauth.register(
            name='google',
            client_id=app.config['GOOGLE_CLIENT_ID'],
            client_secret=app.config['GOOGLE_CLIENT_SECRET'],
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'},
        )

    # ── Logging ───────────────────────────────────────
    from utils.logger import configure_logging
    configure_logging(app)

    # ── Database teardown ─────────────────────────────
    from database.db import close_db, init_db
    app.teardown_appcontext(close_db)

    # ── Register blueprints ───────────────────────────
    from routes.auth    import auth_bp
    from routes.student import student_bp
    from routes.hod     import hod_bp
    from routes.admin   import admin_bp
    from api.endpoints  import api_bp

    app.register_blueprint(auth_bp)       # /  /login  /register  /logout  /dashboard  /auth/google/*
    app.register_blueprint(student_bp)    # /student/*
    app.register_blueprint(hod_bp)        # /hod/*
    app.register_blueprint(admin_bp)      # /admin/*
    app.register_blueprint(api_bp)        # /api/v1/*

    # ── Jinja globals ─────────────────────────────────
    from utils.helpers import fmt_date, fmt_datetime, duration_display
    from utils.auth    import current_user
    from utils.csrf    import generate_csrf_token
    cfg = app.config

    app.jinja_env.globals.update(
        fmt_date=fmt_date,
        fmt_datetime=fmt_datetime,
        duration_display=duration_display,
        BRANCH_TO_DEPT=cfg['BRANCH_TO_DEPT'],
        DEPT_TO_BRANCHES=cfg['DEPT_TO_BRANCHES'],
        BRANCH_SHORT=cfg['BRANCH_SHORT'],
        DEPT_SHORT=cfg['DEPT_SHORT'],
        branch_to_dept=lambda b: cfg['BRANCH_TO_DEPT'].get(b, ''),
        branch_short=lambda b: cfg['BRANCH_SHORT'].get(b, b),
        dept_short=lambda d: cfg['DEPT_SHORT'].get(d, d),
        csrf_token=generate_csrf_token,   # Available in all templates as {{ csrf_token() }}
    )

    # Max upload size enforced at Flask level
    app.config['MAX_CONTENT_LENGTH'] = app.config.get('MAX_UPLOAD_BYTES', 5 * 1024 * 1024)

    # ── Context processor ─────────────────────────────
    @app.context_processor
    def inject_globals():
        return {
            'current_user':        current_user(),
            'now':                 datetime.now(),
            'google_oauth_enabled': app.config.get('GOOGLE_OAUTH_ENABLED', False),
        }

    # ── Security headers ──────────────────────────────
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options']        = 'DENY'
        response.headers['X-XSS-Protection']       = '1; mode=block'
        response.headers['Referrer-Policy']        = 'strict-origin-when-cross-origin'
        return response

    # ── Error handlers ────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    @app.errorhandler(413)
    def file_too_large(e):
        """Handle uploads that exceed MAX_CONTENT_LENGTH."""
        from flask import request as req, jsonify, flash, redirect, url_for
        if req.is_json or req.headers.get('Accept', '').startswith('application/json'):
            return jsonify({'error': 'File too large. Maximum allowed size is 5 MB.', 'status': 413}), 413
        flash('File too large. Maximum allowed size is 5 MB.', 'error')
        return redirect(req.referrer or url_for('auth.landing'))

    # ── Initialise database ───────────────────────────
    with app.app_context():
        init_db()

    return app


# ── Entry point ───────────────────────────────────────
app = create_app()

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    print("\n  NOC Portal starting...")
    print("  Open your browser at: http://localhost:5000\n")
    app.run(
        debug=debug_mode,
        host='0.0.0.0',
        port=int(os.environ.get("PORT", 5000))
    )
