"""
NOC Portal — Configuration
══════════════════════════
Single source of truth for all application settings.
All secrets are read from environment variables (or a .env file).

Usage:
    from config.config import Config
    app.config.from_object(Config)
"""
import os

BASE_URL = os.getenv("BASE_URL")

# Load .env automatically if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
except ImportError:
    pass  # Fall back to OS environment variables


class Config:
    """Production-safe configuration class."""

    # ── Flask core ────────────────────────────────────────────────
    SECRET_KEY              = os.environ.get('SECRET_KEY', 'nocPortal@1304_secureKey_!Ak')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 28800           # 8 hours in seconds

    # ── Database ──────────────────────────────────────────────────
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATABASE = os.path.join(BASE_DIR, 'noc_portal.db')

    # ── File uploads ──────────────────────────────────────────────
    UPLOAD_FOLDER      = os.path.join(BASE_DIR, 'uploads')
    MAX_UPLOAD_BYTES   = int(os.environ.get('MAX_UPLOAD_MB', 5)) * 1024 * 1024
    ALLOWED_EXTENSIONS = {'pdf'}

    # ── Pagination ────────────────────────────────────────────────
    PER_PAGE = 20

    # ── Registration secret codes ─────────────────────────────────
    HOD_SECRET   = os.environ.get('HOD_SECRET',   'HOD@NOC2026')
    ADMIN_SECRET = os.environ.get('ADMIN_SECRET', 'ADMIN@NOC2026')

    # ── Google OAuth (optional) ───────────────────────────────────
    GOOGLE_CLIENT_ID     = os.environ.get('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')

    # ── Email notifications (optional) ───────────────────────────
    MAIL_SERVER   = os.environ.get('MAIL_SERVER', '')
    MAIL_PORT     = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_FROM     = os.environ.get('MAIL_FROM', 'noc@college.edu')

    # ── NOC Certificate settings ─────────────────────────────────────────────
    INSTITUTE_NAME = os.environ.get('INSTITUTE_NAME', 'Institute of Technology')
    BASE_URL       = os.environ.get('BASE_URL', 'http://localhost:5000')
    # ─────────────────────────────────────────────────────────────────────────
    # ── Branch → Department mappings ─────────────────────────────
    BRANCH_TO_DEPT = {
        'Artificial Intelligence and Machine Learning': 'Center of Artificial Intelligence',
        'Artificial Intelligence and Data Science':     'Center of Artificial Intelligence',
        'Artificial Intelligence':                      'Center of Artificial Intelligence',
        'Computer Science and Engineering':             'Computer Science',
        'Computer Science and Design':                  'Computer Science',
        'Information Technology':                       'Information Technology',
        'Electronics and Telecommunication Engineering':'Electronics',
        'Electrical Engineering':                       'Electrical',
        'Mechanical Engineering':                       'Mechanical Engineering',
        'Civil Engineering':                            'Civil Engineering',
        'Chemical Engineering':                         'Chemical Engineering',
        'Mathematics and Computing':                    'Mathematics',
    }

    DEPT_TO_BRANCHES = {
        'Center of Artificial Intelligence': [
            'Artificial Intelligence and Machine Learning',
            'Artificial Intelligence and Data Science',
            'Artificial Intelligence',
        ],
        'Computer Science': [
            'Computer Science and Engineering',
            'Computer Science and Design',
        ],
        'Information Technology': ['Information Technology'],
        'Electronics':            ['Electronics and Telecommunication Engineering'],
        'Electrical':             ['Electrical Engineering'],
        'Mechanical Engineering': ['Mechanical Engineering'],
        'Civil Engineering':      ['Civil Engineering'],
        'Chemical Engineering':   ['Chemical Engineering'],
        'Mathematics':            ['Mathematics and Computing'],
    }

    BRANCH_SHORT = {
        'Artificial Intelligence and Machine Learning': 'AI & ML',
        'Artificial Intelligence and Data Science':     'AI & DS',
        'Artificial Intelligence':                      'AI',
        'Computer Science and Engineering':             'CSE',
        'Computer Science and Design':                  'CSD',
        'Information Technology':                       'IT',
        'Electronics and Telecommunication Engineering':'ENTC',
        'Electrical Engineering':                       'EE',
        'Mechanical Engineering':                       'Mech',
        'Civil Engineering':                            'Civil',
        'Chemical Engineering':                         'Chem',
        'Mathematics and Computing':                    'M&C',
    }

    DEPT_SHORT = {
        'Center of Artificial Intelligence': 'CAI',
        'Computer Science':                  'CS',
        'Information Technology':            'IT',
        'Electronics':                       'ECE',
        'Electrical':                        'EE',
        'Mechanical Engineering':            'Mech',
        'Civil Engineering':                 'Civil',
        'Chemical Engineering':              'Chem',
        'Mathematics':                       'Math',
    }
