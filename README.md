# NOC Portal — Internship Approval System

> A production-grade, role-based web application that digitizes the entire **No Objection Certificate** workflow for college internship approvals.

---

## The Problem

In most colleges, internship approvals are still handled manually — students submit physical documents, HODs sign them by hand, and coordinators track everything in spreadsheets. The process is slow, error-prone, and leaves zero audit trail.

**NOC Portal fixes this end-to-end.** Students apply online, HODs review and decide digitally, the T&P coordinator monitors everything from a live dashboard, and the approved certificate can be verified by anyone via a unique NOC ID — no paperwork, no chasing signatures.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env    # then edit .env with your values

# 3. Run
python app.py
# → http://localhost:5000
```

**Windows (with Google OAuth):**

```
run.bat
```

> **First run:** Delete `noc_portal.db` if upgrading from an older version — the DB will be recreated with demo data automatically.

---

## Demo Credentials

> ⚠️ For local testing only. Never use these in production.

| Role     | Email           | Password   |
| -------- | --------------- | ---------- |
| Admin    | admin@noc.edu   | admin123   |
| HOD (IT) | hod.it@noc.edu  | hod123     |
| Student  | student@noc.edu | student123 |

---

## Features

**For Students**

- Submit internship applications with company, manager, role, and offer letter details
- Upload offer letters (PDF) directly in the form
- Track application status and read HOD remarks in real time
- Download the generated NOC certificate once approved
- Replace uploaded documents while application is still pending

**For HODs**

- Review pending applications for their department with full detail view
- Approve or reject with written remarks
- Access uploaded offer letter PDFs for verification

**For Administrators (T&P Coordinator)**

- Live analytics dashboard with department-wise and status-wise breakdown
- Full application list with search, filter, and pagination
- User management — activate, deactivate, reset passwords
- Export all data to CSV for reporting
- NOC certificate verification system via unique NOC ID

**System-wide**

- Google OAuth + email/password authentication
- CSRF protection on every POST form
- Automatic NOC PDF generation on approval
- QR code on every certificate linking to the public verification page
- Structured audit log of all actions
- REST API with role-scoped responses

---

## Tech Stack

| Layer          | Technology                                                       |
| -------------- | ---------------------------------------------------------------- |
| Backend        | Python 3, Flask                                                  |
| Database       | SQLite (designed for easy migration to PostgreSQL in production) |
| Auth           | Session-based + Google OAuth 2.0                                 |
| Security       | PBKDF2-SHA256 hashing, CSRF tokens, file magic-byte validation   |
| Frontend       | HTML5, CSS3 (custom design system), Vanilla JS                   |
| PDF Generation | ReportLab                                                        |
| QR Codes       | qrcode library                                                   |
| Deployment     | Environment-variable-based config, .env support                  |

---

## 🌐 Deployment

The application is deployed on Render:

🔗 https://noc-portal.onrender.com

⚠️ **Note on performance:**
Since the app is hosted on Render’s free tier, it may take a few seconds (or up to a minute) to load on the first visit. This is due to **cold starts**, where the server goes idle after inactivity and needs to restart.

Once loaded, the application performs normally.

In a production environment, this can be improved by:

- Using always-on backend services
- Deploying with Docker containers
- Migrating to PostgreSQL for persistent storage

---

## 📸 Screenshots

### 🔹 Landing Page (Hero Section)

Main entry view showing the core idea and introduction of the system.
![Landing Hero](screenshots\landing-top.png)

---

### 🔹 Landing Page (Workflow & Roles Section)

Explains the internship approval process and role-based system (Student, HOD, Admin).
![Landing Roles](screenshots\landing-bottom.png)

---

### 🔹 Student Dashboard

Students can submit applications, track status, and view HOD remarks in real time.
![Student Dashboard](screenshots\student-dashboard.png)

---

### 🔹 HOD Dashboard

HOD reviews applications, verifies details, and approves or rejects with remarks.
![HOD Dashboard](screenshots\hod-dashboard.png)

---

### 🔹 Admin Dashboard

Admin monitors system-wide analytics, manages users, and exports reports.
![Admin Dashboard](screenshots\admin-dashboard.png)

---

## Project Structure

```
noc_portal/
│
├── app.py                       ← Application factory (entry point)
├── .env                         ← Secrets — never commit this
├── requirements.txt
│
├── config/
│   └── config.py                ← All settings loaded from environment variables
│
├── models/
│   └── models.py                ← Data layer: User, Application, AuditLog
│                                   Typed dataclasses + repository methods
│
├── services/
│   └── business_logic.py        ← Domain logic:
│                                   ApplicationService — apply/approve/reject/withdraw
│                                   UserService       — registration, password, admin ops
│                                   DocumentService   — upload/download/replace
│
├── routes/
│   ├── auth.py                  ← / /login /register /logout + Google OAuth
│   ├── student.py               ← /student/* routes
│   ├── hod.py                   ← /hod/* routes
│   └── admin.py                 ← /admin/* routes
│
├── api/
│   └── endpoints.py             ← REST API — /api/v1/*
│
├── database/
│   └── db.py                    ← SQLite connection, schema, migrations, seed data
│
├── utils/
│   ├── auth.py                  ← current_user(), @login_required, @role_required
│   ├── helpers.py               ← Formatting, pagination, enrichment utilities
│   ├── email.py                 ← Email notifications (optional)
│   ├── csrf.py                  ← CSRF token generation + validation
│   └── uploads.py               ← PDF validation, secure save/delete
│
├── uploads/                     ← Uploaded offer letter PDFs (auto-created)
├── static/
│   ├── css/style.css
│   └── js/main.js
│
└── templates/
    ├── base.html
    ├── landing.html
    ├── auth/          login · register · google_complete
    ├── student/       dashboard · profile · apply · view_application · my_nocs
    ├── hod/           dashboard · profile · view_application
    ├── admin/         dashboard · profile · applications · users
    └── errors/        403 · 404 · 500
```

---

## Architecture

The application follows a strict **layered architecture** — each layer has one job, and layers never skip each other.

```
HTTP Request
    ↓
Route handler         ← validates HTTP input, handles redirects
    ↓
Service layer         ← all business logic and validation lives here
    ↓
Model / Repository    ← data access only, no business logic
    ↓
SQLite
```

| Layer        | Files                        | Responsibility                                   |
| ------------ | ---------------------------- | ------------------------------------------------ |
| **Config**   | `config/config.py`           | All settings from env vars, one source of truth  |
| **Models**   | `models/models.py`           | Data contracts, schema docs, repository methods  |
| **Database** | `database/db.py`             | Connection, schema creation, migrations, seeding |
| **Services** | `services/business_logic.py` | Domain logic, validation, orchestration          |
| **Routes**   | `routes/*.py`                | Thin HTTP wrappers — call services, return views |
| **API**      | `api/endpoints.py`           | JSON REST endpoints, same session auth as web    |
| **Utils**    | `utils/*.py`                 | Cross-cutting: auth guards, CSRF, uploads        |

This means: you can swap SQLite for PostgreSQL without touching routes. You can add a mobile API without touching services. The model layer is already annotated to be ORM-compatible with zero structural changes.

---

## Models

Typed Python dataclasses in `models/models.py`. Ready for SQLAlchemy — swap the repository methods to use `db.session` and nothing else changes.

```python
from models import User, Application, AuditLog

user = User.get_by_id(1)
user = User.get_by_email('student@noc.edu')

apps = Application.for_student(student_id=1)
apps = Application.for_department('Computer Science', status='Pending')

student  = application.get_student()    # → User
reviewer = application.get_reviewer()   # → User | None
```

---

## Services

```python
from services import ApplicationService, UserService, DocumentService

# Submit
errors = ApplicationService.validate_application(form_data)
aid, err = ApplicationService.create_application(form_data, current_user)

# HOD actions
ok, err = ApplicationService.approve(app_id, hod_user, remarks)
ok, err = ApplicationService.reject(app_id, hod_user, remarks)

# Student withdraw
ok, err = ApplicationService.withdraw(app_id, student_id)

# Document handling
filename, err = DocumentService.handle_upload(file, app_id, student_id)
DocumentService.attach_to_application(app_id, filename)

# User management
err = UserService.change_password(user_id, old_pw, new_pw, confirm)
ok, msg = UserService.toggle_active(uid, acting_user_id)
ok, msg = UserService.reset_password(uid, new_password)
ok, msg = UserService.delete_user(uid, acting_user_id)
```

---

## REST API

All endpoints use the same session auth as the web UI. Prefix: `/api/v1`

| Method | Endpoint             | Auth  | Description                |
| ------ | -------------------- | ----- | -------------------------- |
| GET    | `/health`            | None  | Health check               |
| GET    | `/applications`      | Any   | Applications (role-scoped) |
| GET    | `/applications/<id>` | Any   | Single application detail  |
| GET    | `/status/<id>`       | Any   | Status + remarks only      |
| GET    | `/users`             | Admin | All users                  |
| GET    | `/users/<id>`        | Admin | Single user                |
| GET    | `/stats`             | Any   | Counts (role-scoped)       |

```bash
GET /api/v1/health
→ {"status": "ok", "service": "NOC Portal API", "version": "1.0"}

GET /api/v1/status/3
→ {"application_id": 3, "status": "Approved", "hod_remarks": "...", "reviewed_at": "..."}

GET /api/v1/applications?status=Pending&page=1
→ {"total": 5, "page": 1, "per_page": 20, "pages": 1, "data": [...]}
```

---

## Security

| Area             | Implementation                                                                 |
| ---------------- | ------------------------------------------------------------------------------ |
| Passwords        | PBKDF2-SHA256 via Werkzeug — no plaintext ever stored                          |
| Sessions         | `HttpOnly`, `SameSite=Lax`, 8-hour lifetime                                    |
| CSRF             | Synchronizer token in every POST form, validated server-side                   |
| File uploads     | Extension check + magic-byte check (`%PDF`) + `secure_filename` + UUID         |
| Security headers | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `X-XSS-Protection` |
| Route guards     | `@login_required` + `@role_required('role')` on every protected route          |
| Secrets          | All in `.env`, zero hardcoding                                                 |
| Document access  | Offer letters served only through controlled Flask routes, not as static files |

---

## Document Upload

1. Student fills the application form and uploads the offer letter PDF (required)
2. Server validates: correct extension, correct magic bytes, under 5 MB
3. File saved as `offer_<app_id>_<student_id>_<uuid4>.pdf` — UUID prevents enumeration
4. Database stores only the filename, never the full system path
5. File served via `/admin/offer-letter/<app_id>` — access is role-checked on every request

---

## Environment Variables

```ini
# Required
SECRET_KEY=use-a-long-random-string-in-production

# Registration access codes
HOD_SECRET=hod_secret_code
ADMIN_SECRET=admin_secret_code

# Uploads
MAX_UPLOAD_MB=5

# Google OAuth (optional — email/password works without this)
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

The architecture was designed so a database migration is a surgical swap, not a rewrite.

```
1. pip install SQLAlchemy Flask-SQLAlchemy Flask-Migrate
2. Replace Column/ForeignKey annotations in models/models.py with real SQLAlchemy columns
3. Replace repository @classmethod bodies with db.session.query(...) calls
4. Remove database/db.py — SQLAlchemy handles connections
5. flask db init && flask db migrate && flask db upgrade
```

Routes, services, templates, and tests need zero changes.

---

## Running Tests

```bash
python3 -c "
import sys; sys.path.insert(0, '.')
from app import create_app
app = create_app()
c = app.test_client()
print(c.get('/').status_code)             # 200
print(c.get('/api/v1/health').status_code) # 200
"
```

---

## What I Built and Learned

This project was built from scratch as a complete, production-minded system — not a tutorial clone.

**Architectural decisions:**

- Chose a strict layered architecture (routes → services → models) to keep business logic testable and routes thin. This meant resisting the temptation to put logic directly in route handlers, which is the most common Flask anti-pattern.
- Designed the model layer to be ORM-compatible from day one, so a future migration to SQLAlchemy requires no structural changes.

**Security decisions:**

- CSRF tokens were implemented manually (not via a library) to understand the underlying mechanism.
- File uploads reject files that have the correct extension but wrong magic bytes — a disguised executable with a `.pdf` extension will be rejected.
- Offer letters are never served as static files; every download goes through a Flask route that checks role and ownership.

**Things learned the hard way:**

- Session management across Google OAuth requires careful handling of the callback state to prevent open redirect attacks.
- SQLite's default threading behavior causes issues under Flask's development server with concurrent requests — fixed with `check_same_thread=False` and connection-per-request pattern.
- Paginating queries efficiently without an ORM requires writing reusable helpers, which led to the `paginate()` utility in `utils/helpers.py`.

---

## Planned Improvements

- PostgreSQL support (schema is already portable — just swap the connection layer)
- Full SQLAlchemy ORM integration
- Email notifications on status change (SMTP config is already wired in `.env`)
- Department-wise analytics charts on the admin dashboard
- Docker container + deployment guide for Render / Railway
- Expanded REST API with POST/PATCH endpoints

---

\*Developed by **Akshata Lokhande\***
