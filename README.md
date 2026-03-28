# NOC Portal — Production-Grade Flask Application

A complete **No Objection Certificate** management system for internship approvals, refactored to industry-standard architecture.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment (copy and edit)
cp .env.example .env    # or edit .env directly

# 3. Run
python app.py
# → Open http://localhost:5000
```

**Windows (with Google OAuth):**

```
run.bat
```

> **First run:** Delete `noc_portal.db` if upgrading from an older version — the DB will be recreated with demo data.

---

## ✨ Key Highlights

- 🔐 Secure authentication (OAuth + session-based)
- 👥 Role-based dashboards (Admin / HOD / Student)
- 📄 Automated NOC generation
- 🔍 QR code verification system
- 📁 Secure document upload (PDF validation)
- ⚡ Modular, production-ready architecture

---

## Demo Credentials

| Role    | Email           | Password   |
| ------- | --------------- | ---------- |
| Admin   | admin@noc.edu   | admin123   |
| HOD CS  | hod.cs@noc.edu  | hod123     |
| Student | student@noc.edu | student123 |

---

## Project Structure

```
noc_portal/
│
├── app.py                       ← Application factory (entry point)
├── .env                         ← Environment variables (secrets — never commit)
├── .gitignore
├── requirements.txt
│
├── config/
│   ├── config.py                ← Canonical configuration class (all settings)
│   └── settings.py              ← Backward-compat re-export of config.py
│
├── models/
│   └── models.py                ← Data model layer: User, Application, AuditLog
│                                   Repository methods, ForeignKey declarations,
│                                   typed dataclasses mirroring the DB schema.
│
├── services/
│   └── business_logic.py        ← Business logic layer:
│                                   ApplicationService (apply/approve/reject/withdraw)
│                                   UserService (registration, password, admin ops)
│                                   DocumentService (upload/download/replace)
│
├── routes/
│   ├── auth.py                  ← / /login /register /logout /dashboard Google OAuth
│   ├── auth_routes.py           ← Re-export alias (for named-file convention)
│   ├── student.py               ← /student/* routes
│   ├── student_routes.py        ← Re-export alias
│   ├── hod.py                   ← /hod/* routes
│   ├── hod_routes.py            ← Re-export alias
│   ├── admin.py                 ← /admin/* routes
│   └── admin_routes.py          ← Re-export alias
│
├── api/
│   └── endpoints.py             ← REST API: /api/v1/*
│                                   /api/v1/health
│                                   /api/v1/applications
│                                   /api/v1/applications/<id>
│                                   /api/v1/applications/all
│                                   /api/v1/status/<id>          
│                                   /api/v1/users
│                                   /api/v1/users/<id>
│                                   /api/v1/stats
│
├── database/
│   └── db.py                    ← SQLite connection, schema, migrations, seed data
│
├── utils/
│   ├── auth.py                  ← current_user(), login_required, role_required
│   ├── helpers.py               ← fmt_date, enrich, paginate, duration_display
│   ├── email.py                 ← send_notification (optional email alerts)
│   ├── csrf.py                  ← CSRF token generation + validation
│   └── uploads.py               ← PDF validation (magic bytes), secure save/delete
│
├── uploads/                     ← Uploaded offer letter PDFs (auto-created)
│   └── .gitkeep
│
├── static/
│   ├── css/style.css
│   └── js/main.js
│
└── templates/
    ├── base.html
    ├── landing.html
    ├── auth/          login.html  register.html  google_complete.html
    ├── student/       dashboard.html  profile.html  apply.html  view_application.html
    ├── hod/           dashboard.html  profile.html  view_application.html
    ├── admin/         dashboard.html  profile.html  applications.html  users.html
    └── errors/        403.html  404.html  500.html
```

---

## Architecture Overview

### Layer Responsibilities

| Layer        | Files                        | Responsibility                                  |
| ------------ | ---------------------------- | ----------------------------------------------- |
| **Config**   | `config/config.py`           | All settings from env vars                      |
| **Models**   | `models/models.py`           | Data contracts, schema docs, repository methods |
| **Database** | `database/db.py`             | SQLite connection, schema, migrations           |
| **Services** | `services/business_logic.py` | Domain logic, validation, orchestration         |
| **Routes**   | `routes/*.py`                | HTTP handling — thin wrappers over services     |
| **API**      | `api/endpoints.py`           | JSON REST endpoints                             |
| **Utils**    | `utils/*.py`                 | Cross-cutting: auth, CSRF, uploads, helpers     |

### Data Flow

```
HTTP Request
    → Route handler (validates HTTP input)
        → Service layer (business logic)
            → Model / Repository (db_query)
                → SQLite
        ← returns result or error
    ← renders template or JSON
```

---

## Models

Defined in `models/models.py` using typed Python dataclasses with SQLAlchemy-compatible annotations (`Column`, `ForeignKey`). Ready for a full ORM migration — swap the repository methods to use SQLAlchemy sessions and nothing else changes.

```python
from models import User, Application, AuditLog

# Repository pattern
user = User.get_by_id(1)
user = User.get_by_email('student@noc.edu')
apps = Application.for_student(student_id=1)
apps = Application.for_department('Information Technology', status='Pending')

# Relationships (lazy-loaded)
student  = application.get_student()   # → User
reviewer = application.get_reviewer()  # → User | None
```

---

## Services

Defined in `services/business_logic.py`:

```python
from services import ApplicationService, UserService, DocumentService

# Validate and submit a NOC application
errors = ApplicationService.validate_application(form_data)
aid, err = ApplicationService.create_application(form_data, current_user)

# HOD approve/reject
ok, err = ApplicationService.approve(app_id, hod_user, remarks)
ok, err = ApplicationService.reject(app_id, hod_user, remarks)

# Student withdraw
ok, err = ApplicationService.withdraw(app_id, student_id)

# Document upload
filename, err = DocumentService.handle_upload(file, app_id, student_id)
DocumentService.attach_to_application(app_id, filename)
filename, err = DocumentService.get_safe_path(app_id, user)

# User management
err = UserService.change_password(user_id, old_pw, new_pw, confirm)
ok, msg = UserService.toggle_active(uid, acting_user_id)
ok, msg = UserService.reset_password(uid, new_password)
ok, msg = UserService.delete_user(uid, acting_user_id)
```

---

## REST API

All endpoints use session auth (same as the web UI). Prefix: `/api/v1`

| Method | Endpoint             | Auth  | Description               |
| ------ | -------------------- | ----- | ------------------------- |
| GET    | `/health`            | None  | Health check              |
| GET    | `/applications`      | Any   | List apps (role-scoped)   |
| GET    | `/applications/<id>` | Any   | Single application        |
| GET    | `/applications/all`  | Any   | Alias for `/applications` |
| GET    | `/status/<id>`       | Any   | Application status only   |
| GET    | `/users`             | Admin | All users                 |
| GET    | `/users/<id>`        | Admin | Single user               |
| GET    | `/stats`             | Any   | Counts (role-scoped)      |

**Example responses:**

```bash
# Health
GET /api/v1/health
{"status": "ok", "service": "NOC Portal API", "version": "1.0"}

# Application status
GET /api/v1/status/3
{"application_id": 3, "status": "Approved", "hod_remarks": "Good.", "reviewed_at": "..."}

# Applications list
GET /api/v1/applications?status=Pending&page=1
{"total": 5, "page": 1, "per_page": 20, "pages": 1, "data": [...]}
```

---

## Document Upload (Offer Letter)

### Student flow

1. Fill the application form — Section 4 contains the PDF upload field (required)
2. Submit — PDF is validated and saved; application is linked to the file
3. View application detail → download own offer letter; upload replacement on pending apps

### Validation

- Extension must be `.pdf`
- First 4 bytes must be `%PDF` (magic bytes — rejects disguised executables)
- Max 5 MB (configurable via `MAX_UPLOAD_MB` in `.env`)
- `werkzeug.utils.secure_filename` strips path traversal

### Storage

- Saved as `offer_<app_id>_<student_id>_<uuid4>.pdf` in `uploads/`
- Database stores filename only — never full system path
- Served via controlled Flask route (`/admin/offer-letter/<app_id>`)

### HOD / Admin access

- Download button on application detail page (HOD: own dept only)
- Download icon in admin applications table

---

## Security

| Feature          | Implementation                                                                   |
| ---------------- | -------------------------------------------------------------------------------- |
| Passwords        | PBKDF2-SHA256 via Werkzeug                                                       |
| Sessions         | `SESSION_COOKIE_HTTPONLY=True`, `SAMESITE=Lax`, 8h lifetime                      |
| CSRF             | Synchronizer token in all POST forms; `validate_csrf_token()` in all POST routes |
| File uploads     | Extension + magic bytes + `secure_filename` + UUID naming                        |
| Security headers | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `X-XSS-Protection`   |
| Role enforcement | `@login_required` + `@role_required('role')` decorators on every route           |
| Secrets          | All in `.env`, never hardcoded                                                   |

---

## Environment Variables (`.env`)

```ini
# Required
SECRET_KEY=change-me-in-production-use-a-long-random-string

# Registration codes
HOD_SECRET=hod_secret_code
ADMIN_SECRET=admin_secret_code


# File uploads
MAX_UPLOAD_MB=5

# Google OAuth (optional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# Email notifications (optional)
MAIL_SERVER=
MAIL_PORT=587
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_FROM=noc@college.edu
```

---

## ORM Migration Path

When SQLAlchemy becomes available:

1. `pip install SQLAlchemy Flask-SQLAlchemy Flask-Migrate`
2. Replace `Column` / `ForeignKey` annotations in `models/models.py` with real SQLAlchemy columns
3. Replace repository `@classmethod` bodies with `db.session.query(...)` calls
4. Remove `database/db.py` — let SQLAlchemy handle connections
5. Run `flask db init && flask db migrate && flask db upgrade`

Nothing in routes, services, templates, or tests needs to change.

---

## Running Tests

```bash
# Quick smoke test
python3 -c "
import sys; sys.path.insert(0,'.')
from app import create_app
app = create_app()
client = app.test_client()
print(client.get('/').status_code)   # 200
print(client.get('/api/v1/health').status_code)  # 200
"
```
