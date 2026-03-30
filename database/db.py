"""
NOC Portal — Database Layer
Handles SQLite connection, schema creation, migration, and demo seeding.
Uses the same raw sqlite3 approach as original — no ORM dependency added.
"""
import sqlite3
from datetime import date, datetime, timedelta
from flask import g
from werkzeug.security import generate_password_hash


def get_db():
    """Return the per-request database connection (creates it if needed)."""
    if 'db' not in g:
        from flask import current_app
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


def close_db(exc):
    """Teardown: close DB connection at end of request."""
    db = g.pop('db', None)
    if db:
        db.close()


def db_query(sql, args=(), one=False, commit=False):
    """
    Execute SQL with optional parameters.

    If commit=True  → commit the transaction and return lastrowid (for INSERT/UPDATE/DELETE).
    If one=True     → return a single Row or None.
    Otherwise       → return a list of Rows.
    """
    db = get_db()
    cur = db.execute(sql, args)
    if commit:
        db.commit()
        return cur.lastrowid
    return cur.fetchone() if one else cur.fetchall()


def init_db():
    """Create tables, run migrations, and seed demo data."""
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        email       TEXT UNIQUE NOT NULL,
        password    TEXT NOT NULL,
        role        TEXT NOT NULL CHECK(role IN ('student','hod','admin')),
        department  TEXT,
        branch      TEXT,
        enrollment  TEXT,
        is_active   INTEGER DEFAULT 1,
        created_at  TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS applications (
        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id              INTEGER NOT NULL REFERENCES users(id),
        company_name            TEXT NOT NULL,
        internship_role         TEXT NOT NULL,
        start_date              TEXT NOT NULL,
        end_date                TEXT NOT NULL,
        duration_weeks          INTEGER,
        stipend                 TEXT,
        location                TEXT,
        description             TEXT,
        department              TEXT,
        branch                  TEXT,
        company_address         TEXT,
        company_website         TEXT,
        manager_name            TEXT,
        manager_designation     TEXT,
        manager_email           TEXT,
        manager_phone           TEXT,
        offer_letter_ref        TEXT,
        internship_mode         TEXT DEFAULT 'On-site',
        work_hours              TEXT,
        noc_purpose             TEXT,
        student_contact         TEXT,
        academic_year           TEXT,
        status          TEXT DEFAULT 'Pending',
        hod_remarks     TEXT,
        reviewed_by     INTEGER REFERENCES users(id),
        reviewed_at     TEXT,
        created_at      TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS audit_logs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER REFERENCES users(id),
        action      TEXT NOT NULL,
        entity_type TEXT,
        entity_id   INTEGER,
        details     TEXT,
        ip_address  TEXT,
        timestamp   TEXT DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_applications_student    ON applications(student_id);
    CREATE INDEX IF NOT EXISTS idx_applications_department ON applications(department);
    CREATE INDEX IF NOT EXISTS idx_applications_status     ON applications(status);
    CREATE INDEX IF NOT EXISTS idx_applications_created    ON applications(created_at);
    CREATE INDEX IF NOT EXISTS idx_users_email             ON users(email);
    CREATE INDEX IF NOT EXISTS idx_audit_user              ON audit_logs(user_id);
    CREATE INDEX IF NOT EXISTS idx_audit_timestamp         ON audit_logs(timestamp);
    """)
    db.commit()

    # Migrations: safely add new columns to existing databases
    # system_settings table for dynamic config (registration codes, etc.)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS system_settings (
        key   TEXT PRIMARY KEY,
        value TEXT
    );
    INSERT OR IGNORE INTO system_settings (key, value) VALUES ('HOD_SECRET',   'default_hod_code');
    INSERT OR IGNORE INTO system_settings (key, value) VALUES ('ADMIN_SECRET', 'default_admin_code');
    """)
    db.commit()

    for migration_sql in [
        "ALTER TABLE users ADD COLUMN branch TEXT",
        "ALTER TABLE applications ADD COLUMN branch TEXT",
        "ALTER TABLE applications ADD COLUMN offer_letter_path TEXT",
        "ALTER TABLE applications ADD COLUMN offer_letter_original_name TEXT",
        # NOC certificate feature columns
        "ALTER TABLE applications ADD COLUMN noc_id TEXT",
        "ALTER TABLE applications ADD COLUMN certificate_path TEXT",
        "ALTER TABLE applications ADD COLUMN approval_date TEXT",
        "ALTER TABLE users ADD COLUMN verification_required INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 1",
        "ALTER TABLE users ADD COLUMN last_verified_at TEXT",
    ]:
        try:
            db.execute(migration_sql)
            db.commit()
        except Exception:
            pass  # Column already exists — expected on re-runs

    _seed_demo(db)


def _seed_demo(db):
    """Populate demo users and applications (runs only on empty database)."""
    if db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        return  # Already seeded

    ph = generate_password_hash
    users = [
        ('System Admin', 'admin@noc.edu',    ph('admin123'),   'admin',   'Administration',                    '',                                              ''),
        ('Dr. Sharma',   'hod.cs@noc.edu',   ph('hod123'),     'hod',     'Computer Science',                  '',                                              ''),
        ('Dr. Patel',    'hod.ec@noc.edu',   ph('hod123'),     'hod',     'Electronics',                       '',                                              ''),
        ('Arjun Mehta',  'arjun@noc.edu',    ph('student123'), 'student', 'Computer Science',                  'Computer Science and Engineering',              'CS2021001'),
        ('Priya Singh',  'priya@noc.edu',    ph('student123'), 'student', 'Computer Science',                  'Computer Science and Design',                   'CS2021002'),
        ('Rahul Verma',  'rahul@noc.edu',    ph('student123'), 'student', 'Electronics',                       'Electronics and Telecommunication Engineering', 'EC2021001'),
        ('Sneha Gupta',  'sneha@noc.edu',    ph('student123'), 'student', 'Center of Artificial Intelligence', 'Artificial Intelligence and Machine Learning',  'CS2021003'),
        ('Amit Kumar',   'amit@noc.edu',     ph('student123'), 'student', 'Mechanical Engineering',            'Mechanical Engineering',                        'ME2021001'),
    ]
    for name, email, pwd, role, dept, branch, enroll in users:
        db.execute(
            "INSERT INTO users(name,email,password,role,department,branch,enrollment) VALUES(?,?,?,?,?,?,?)",
            (name, email, pwd, role, dept, branch, enroll)
        )
    db.commit()

    hod_id = db.execute("SELECT id FROM users WHERE email='hod.cs@noc.edu'").fetchone()[0]
    sid = {r[0]: r[1] for r in db.execute("SELECT email, id FROM users WHERE role='student'").fetchall()}

    today = date.today()
    now   = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    apps  = [
        (sid['arjun@noc.edu'], 'Google India',    'Software Engineering Intern', 'Computer Science', 'Bangalore', '₹50,000/month', 'Approved', 'Great opportunity.'),
        (sid['priya@noc.edu'], 'Infosys',          'Data Science Intern',         'Computer Science', 'Pune',      '₹25,000/month', 'Pending',  None),
        (sid['rahul@noc.edu'], 'ISRO',             'Electronics Intern',          'Electronics',      'Ahmedabad', '₹15,000/month', 'Approved', 'Approved by HOD.'),
        (sid['sneha@noc.edu'], 'Microsoft',        'Cloud Intern',                'Computer Science', 'Hyderabad', '₹45,000/month', 'Pending',  None),
        (sid['amit@noc.edu'],  'Tata Consultancy', 'Web Dev Intern',              'Mechanical',       'Mumbai',    '₹20,000/month', 'Rejected', 'Incomplete documentation.'),
        (sid['arjun@noc.edu'], 'Amazon',           'ML Intern',                   'Computer Science', 'Bangalore', '₹40,000/month', 'Approved', 'Strong profile.'),
    ]
    for i, (sid_, company, role, dept, loc, stipend, status, remarks) in enumerate(apps):
        start  = (today + timedelta(days=30 + i * 7)).strftime('%Y-%m-%d')
        end    = (today + timedelta(days=86 + i * 7)).strftime('%Y-%m-%d')
        rev_at = now if status != 'Pending' else None
        rev_by = hod_id if status != 'Pending' else None
        s_branch = db.execute("SELECT branch FROM users WHERE id=?", (sid_,)).fetchone()
        s_branch = s_branch[0] if s_branch and s_branch[0] else ''
        db.execute(
            """INSERT INTO applications
               (student_id, company_name, internship_role, start_date, end_date,
                duration_weeks, stipend, location, department, branch, status,
                hod_remarks, reviewed_by, reviewed_at)
               VALUES (?,?,?,?,?,8,?,?,?,?,?,?,?,?)""",
            (sid_, company, role, start, end, stipend, loc, dept, s_branch, status, remarks, rev_by, rev_at)
        )
    db.commit()
    print("✅ Demo data seeded successfully!")
