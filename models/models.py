"""
NOC Portal — Data Models
════════════════════════
Defines the schema using plain Python dataclasses / typed wrappers so the
codebase has a single, authoritative description of every table and column.

Why not Flask-SQLAlchemy?
  SQLAlchemy is not available in the current deployment environment.
  These models implement the same contract (fields, relationships, validation)
  using stdlib dataclasses + a thin repository pattern, keeping the door open
  for a full ORM migration by simply swapping the repository methods.

Architecture:
  • Model classes  → pure data containers (dataclass) with class-level field
                     declarations that mirror the SQLite schema exactly.
  • Repository     → static methods that call db_query() — the existing,
                     tested SQL layer — so all SQL stays in one place.
  • Relationships  → expressed via ForeignKey annotations and convenience
                     properties (e.g. application.student).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List


# ══════════════════════════════════════════════════════════════════
#  FIELD TYPE ANNOTATIONS  (mirrors SQLite schema)
# ══════════════════════════════════════════════════════════════════

class ForeignKey:
    """Annotation to document FK relationships (mirrors SQLAlchemy API)."""
    def __init__(self, target: str):
        self.target = target   # e.g.  "users.id"

    def __repr__(self):
        return f"ForeignKey('{self.target}')"


class Column:
    """
    Lightweight column descriptor — documents type, constraints, and
    defaults the same way SQLAlchemy's Column() does.
    """
    def __init__(self, col_type: str, *, primary_key=False, nullable=True,
                 unique=False, default=None, foreign_key: Optional[ForeignKey] = None,
                 check: Optional[str] = None):
        self.col_type    = col_type
        self.primary_key = primary_key
        self.nullable    = nullable
        self.unique      = unique
        self.default     = default
        self.foreign_key = foreign_key
        self.check       = check

    def __repr__(self):
        parts = [self.col_type]
        if self.primary_key: parts.append('PK')
        if not self.nullable: parts.append('NOT NULL')
        if self.unique: parts.append('UNIQUE')
        if self.foreign_key: parts.append(f'FK→{self.foreign_key.target}')
        return f"Column({', '.join(parts)})"


# ══════════════════════════════════════════════════════════════════
#  USER MODEL
# ══════════════════════════════════════════════════════════════════

@dataclass
class User:
    """
    Represents a portal user (student, HOD, or admin).

    Schema mirrors:  CREATE TABLE users (...)
    Roles           → CHECK(role IN ('student','hod','admin'))
    """

    # ── Column declarations (schema documentation) ──────────────
    __tablename__ = 'users'

    _id         = Column('INTEGER', primary_key=True)
    _name       = Column('TEXT', nullable=False)
    _email      = Column('TEXT', nullable=False, unique=True)
    _password   = Column('TEXT', nullable=False)          # PBKDF2-SHA256 hash
    _role       = Column('TEXT', nullable=False,
                         check="role IN ('student','hod','admin')")
    _department = Column('TEXT')
    _branch     = Column('TEXT')
    _enrollment = Column('TEXT')
    _is_active  = Column('INTEGER', default=1)
    _created_at = Column('TEXT', default="datetime('now')")

    # ── Instance fields (populated from DB rows) ─────────────────
    id:         int            = field(default=0)
    name:       str            = field(default='')
    email:      str            = field(default='')
    password:   str            = field(default='')        # hashed — never expose
    role:       str            = field(default='student')
    department: Optional[str]  = field(default=None)
    branch:     Optional[str]  = field(default=None)
    enrollment: Optional[str]  = field(default=None)
    is_active:  int            = field(default=1)
    created_at: Optional[str]  = field(default=None)

    # re-verification system
    verification_required: int = field(default=0)
    is_verified: int = field(default=1)
    last_verified_at: Optional[str] = field(default=None)

    # ── Convenience properties ────────────────────────────────────
    @property
    def is_student(self) -> bool:
        return self.role == 'student'

    @property
    def is_hod(self) -> bool:
        return self.role == 'hod'

    @property
    def is_admin(self) -> bool:
        return self.role == 'admin'

    @property
    def display_role(self) -> str:
        """Human-readable role label for the UI."""
        return {'student': 'Student', 'hod': 'Head of Department',
                'admin': 'Administrator'}.get(self.role, self.role.title())

    # ── Factory / Repository methods ─────────────────────────────
    @classmethod
    def from_dict(cls, d: dict) -> 'User':
        """Build a User instance from a plain dict (e.g. sqlite3.Row → dict)."""
        return cls(
            id         = d.get('id', 0),
            name       = d.get('name', ''),
            email      = d.get('email', ''),
            password   = d.get('password', ''),
            role       = d.get('role', 'student'),
            department = d.get('department'),
            branch     = d.get('branch'),
            enrollment = d.get('enrollment'),
            is_active  = d.get('is_active', 1),
            created_at = d.get('created_at'),
            verification_required = d.get('verification_required', 0),
            is_verified = d.get('is_verified', 1),
            last_verified_at = d.get('last_verified_at'),
        )

    @classmethod
    def get_by_id(cls, uid: int) -> Optional['User']:
        """Fetch a single user by primary key."""
        from database.db import db_query
        row = db_query("SELECT * FROM users WHERE id=?", (uid,), one=True)
        return cls.from_dict(dict(row)) if row else None

    @classmethod
    def get_by_email(cls, email: str) -> Optional['User']:
        """Fetch a user by email address (case-insensitive)."""
        from database.db import db_query
        row = db_query("SELECT * FROM users WHERE email=?", (email.lower(),), one=True)
        return cls.from_dict(dict(row)) if row else None

    @classmethod
    def get_active(cls, uid: int) -> Optional['User']:
        """Fetch an active user by primary key."""
        from database.db import db_query
        row = db_query("SELECT * FROM users WHERE id=? AND is_active=1", (uid,), one=True)
        return cls.from_dict(dict(row)) if row else None

    @classmethod
    def all(cls, role: Optional[str] = None) -> List['User']:
        """Return all users, optionally filtered by role."""
        from database.db import db_query
        if role:
            rows = db_query("SELECT * FROM users WHERE role=? ORDER BY created_at DESC", (role,))
        else:
            rows = db_query("SELECT * FROM users ORDER BY created_at DESC")
        return [cls.from_dict(dict(r)) for r in rows]
    
    @classmethod
    def force_reverify(cls, user_ids: List[int]):
        """Force re-verification for selected users (HOD/Admin only)."""
        from database.db import db_query

        for uid in user_ids:
            user = cls.get_by_id(uid)

            # skip students
            if not user or user.role == 'student':
                continue

            db_query(
                "UPDATE users SET verification_required=1, is_verified=0 WHERE id=?",
                (uid,),
                commit=True
            )

    def to_dict(self, include_password=False) -> dict:
        """Serialize to dict. Excludes password hash by default."""
        d = {
            'id': self.id, 'name': self.name, 'email': self.email,
            'role': self.role, 'department': self.department,
            'branch': self.branch, 'enrollment': self.enrollment,
            'is_active': self.is_active, 'created_at': self.created_at,
        }
        if include_password:
            d['password'] = self.password
        return d

    def __repr__(self):
        return f"<User id={self.id} email='{self.email}' role='{self.role}'>"


# ══════════════════════════════════════════════════════════════════
#  APPLICATION MODEL
# ══════════════════════════════════════════════════════════════════

@dataclass
class Application:
    """
    Represents a student's NOC application.

    Schema mirrors:  CREATE TABLE applications (...)
    Relationship:    student_id → users.id  (many-to-one)
                     reviewed_by → users.id (many-to-one, nullable)
    Status values:   'Pending' | 'Approved' | 'Rejected'
    """

    __tablename__ = 'applications'

    # ── Column declarations ──────────────────────────────────────
    _id                 = Column('INTEGER', primary_key=True)
    _student_id         = Column('INTEGER', nullable=False,
                                 foreign_key=ForeignKey('users.id'))
    _company_name       = Column('TEXT', nullable=False)
    _internship_role    = Column('TEXT', nullable=False)
    _start_date         = Column('TEXT', nullable=False)
    _end_date           = Column('TEXT', nullable=False)
    _duration_weeks     = Column('INTEGER')
    _stipend            = Column('TEXT')
    _location           = Column('TEXT')
    _description        = Column('TEXT')
    _department         = Column('TEXT')
    _branch             = Column('TEXT')
    _company_address    = Column('TEXT')
    _company_website    = Column('TEXT')
    _manager_name       = Column('TEXT')
    _manager_designation= Column('TEXT')
    _manager_email      = Column('TEXT')
    _manager_phone      = Column('TEXT')
    _offer_letter_ref   = Column('TEXT')
    _offer_letter_path  = Column('TEXT')          # stored filename in /uploads/
    _internship_mode    = Column('TEXT', default="'On-site'")
    _work_hours         = Column('TEXT')
    _noc_purpose        = Column('TEXT')
    _student_contact    = Column('TEXT')
    _academic_year      = Column('TEXT')
    _status             = Column('TEXT', default="'Pending'")
    _hod_remarks        = Column('TEXT')
    _reviewed_by        = Column('INTEGER', foreign_key=ForeignKey('users.id'))
    _reviewed_at        = Column('TEXT')
    _created_at         = Column('TEXT', default="datetime('now')")

    # ── Instance fields ──────────────────────────────────────────
    id:                  int           = field(default=0)
    student_id:          int           = field(default=0)
    company_name:        str           = field(default='')
    internship_role:     str           = field(default='')
    start_date:          str           = field(default='')
    end_date:            str           = field(default='')
    duration_weeks:      Optional[int] = field(default=None)
    stipend:             Optional[str] = field(default=None)
    location:            Optional[str] = field(default=None)
    description:         Optional[str] = field(default=None)
    department:          Optional[str] = field(default=None)
    branch:              Optional[str] = field(default=None)
    company_address:     Optional[str] = field(default=None)
    company_website:     Optional[str] = field(default=None)
    manager_name:        Optional[str] = field(default=None)
    manager_designation: Optional[str] = field(default=None)
    manager_email:       Optional[str] = field(default=None)
    manager_phone:       Optional[str] = field(default=None)
    offer_letter_ref:    Optional[str] = field(default=None)
    offer_letter_path:   Optional[str] = field(default=None)
    internship_mode:     str           = field(default='On-site')
    work_hours:          Optional[str] = field(default=None)
    noc_purpose:         Optional[str] = field(default=None)
    student_contact:     Optional[str] = field(default=None)
    academic_year:       Optional[str] = field(default=None)
    status:              str           = field(default='Pending')
    hod_remarks:         Optional[str] = field(default=None)
    reviewed_by:         Optional[int] = field(default=None)
    reviewed_at:         Optional[str] = field(default=None)
    created_at:          Optional[str] = field(default=None)

    # ── Convenience properties ────────────────────────────────────
    @property
    def is_pending(self) -> bool:
        return self.status == 'Pending'

    @property
    def is_approved(self) -> bool:
        return self.status == 'Approved'

    @property
    def is_rejected(self) -> bool:
        return self.status == 'Rejected'

    @property
    def has_offer_letter(self) -> bool:
        return bool(self.offer_letter_path)

    # ── Relationship accessors ────────────────────────────────────
    def get_student(self) -> Optional[User]:
        """Lazy-load the student who submitted this application."""
        return User.get_by_id(self.student_id)

    def get_reviewer(self) -> Optional[User]:
        """Lazy-load the HOD/admin who reviewed this application (if any)."""
        return User.get_by_id(self.reviewed_by) if self.reviewed_by else None

    # ── Factory / Repository methods ─────────────────────────────
    @classmethod
    def from_dict(cls, d: dict) -> 'Application':
        """Build an Application instance from a plain dict."""
        return cls(
            id                  = d.get('id', 0),
            student_id          = d.get('student_id', 0),
            company_name        = d.get('company_name', ''),
            internship_role     = d.get('internship_role', ''),
            start_date          = d.get('start_date', ''),
            end_date            = d.get('end_date', ''),
            duration_weeks      = d.get('duration_weeks'),
            stipend             = d.get('stipend'),
            location            = d.get('location'),
            description         = d.get('description'),
            department          = d.get('department'),
            branch              = d.get('branch'),
            company_address     = d.get('company_address'),
            company_website     = d.get('company_website'),
            manager_name        = d.get('manager_name'),
            manager_designation = d.get('manager_designation'),
            manager_email       = d.get('manager_email'),
            manager_phone       = d.get('manager_phone'),
            offer_letter_ref    = d.get('offer_letter_ref'),
            offer_letter_path   = d.get('offer_letter_path'),
            internship_mode     = d.get('internship_mode', 'On-site'),
            work_hours          = d.get('work_hours'),
            noc_purpose         = d.get('noc_purpose'),
            student_contact     = d.get('student_contact'),
            academic_year       = d.get('academic_year'),
            status              = d.get('status', 'Pending'),
            hod_remarks         = d.get('hod_remarks'),
            reviewed_by         = d.get('reviewed_by'),
            reviewed_at         = d.get('reviewed_at'),
            created_at          = d.get('created_at'),
        )

    @classmethod
    def get_by_id(cls, app_id: int) -> Optional['Application']:
        """Fetch a single application by primary key."""
        from database.db import db_query
        row = db_query("SELECT * FROM applications WHERE id=?", (app_id,), one=True)
        return cls.from_dict(dict(row)) if row else None

    @classmethod
    def for_student(cls, student_id: int) -> List['Application']:
        """All applications submitted by a specific student."""
        from database.db import db_query
        rows = db_query(
            "SELECT * FROM applications WHERE student_id=? ORDER BY created_at DESC",
            (student_id,)
        )
        return [cls.from_dict(dict(r)) for r in rows]

    @classmethod
    def for_department(cls, department: str, status: Optional[str] = None) -> List['Application']:
        """All applications for a department, optionally filtered by status."""
        from database.db import db_query
        if status:
            rows = db_query(
                "SELECT * FROM applications WHERE department=? AND status=? ORDER BY created_at DESC",
                (department, status)
            )
        else:
            rows = db_query(
                "SELECT * FROM applications WHERE department=? ORDER BY created_at DESC",
                (department,)
            )
        return [cls.from_dict(dict(r)) for r in rows]

    @classmethod
    def all(cls, status: Optional[str] = None, department: Optional[str] = None) -> List['Application']:
        """All applications, with optional filters."""
        from database.db import db_query
        sql    = "SELECT * FROM applications WHERE 1=1"
        params = []
        if status:
            sql += " AND status=?"; params.append(status)
        if department:
            sql += " AND department=?"; params.append(department)
        sql += " ORDER BY created_at DESC"
        rows = db_query(sql, params)
        return [cls.from_dict(dict(r)) for r in rows]

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dict (no binary fields)."""
        return {
            'id':                 self.id,
            'student_id':         self.student_id,
            'company_name':       self.company_name,
            'internship_role':    self.internship_role,
            'start_date':         self.start_date,
            'end_date':           self.end_date,
            'duration_weeks':     self.duration_weeks,
            'stipend':            self.stipend,
            'location':           self.location,
            'description':        self.description,
            'department':         self.department,
            'branch':             self.branch,
            'company_address':    self.company_address,
            'company_website':    self.company_website,
            'manager_name':       self.manager_name,
            'manager_designation':self.manager_designation,
            'manager_email':      self.manager_email,
            'manager_phone':      self.manager_phone,
            'offer_letter_ref':   self.offer_letter_ref,
            'has_offer_letter':   self.has_offer_letter,  # boolean, not path
            'internship_mode':    self.internship_mode,
            'work_hours':         self.work_hours,
            'noc_purpose':        self.noc_purpose,
            'student_contact':    self.student_contact,
            'academic_year':      self.academic_year,
            'status':             self.status,
            'hod_remarks':        self.hod_remarks,
            'reviewed_by':        self.reviewed_by,
            'reviewed_at':        self.reviewed_at,
            'created_at':         self.created_at,
        }

    def __repr__(self):
        return f"<Application id={self.id} company='{self.company_name}' status='{self.status}'>"


# ══════════════════════════════════════════════════════════════════
#  AUDIT LOG MODEL
# ══════════════════════════════════════════════════════════════════

@dataclass
class AuditLog:
    """
    Represents a single audit trail entry.

    Schema mirrors:  CREATE TABLE audit_logs (...)
    Relationship:    user_id → users.id  (many-to-one, nullable)
    """

    __tablename__ = 'audit_logs'

    _id          = Column('INTEGER', primary_key=True)
    _user_id     = Column('INTEGER', foreign_key=ForeignKey('users.id'))
    _action      = Column('TEXT', nullable=False)
    _entity_type = Column('TEXT')
    _entity_id   = Column('INTEGER')
    _details     = Column('TEXT')
    _ip_address  = Column('TEXT')
    _timestamp   = Column('TEXT', default="datetime('now')")

    # ── Instance fields ──────────────────────────────────────────
    id:          int           = field(default=0)
    user_id:     Optional[int] = field(default=None)
    action:      str           = field(default='')
    entity_type: Optional[str] = field(default=None)
    entity_id:   Optional[int] = field(default=None)
    details:     Optional[str] = field(default=None)
    ip_address:  Optional[str] = field(default=None)
    timestamp:   Optional[str] = field(default=None)

    @classmethod
    def from_dict(cls, d: dict) -> 'AuditLog':
        return cls(
            id          = d.get('id', 0),
            user_id     = d.get('user_id'),
            action      = d.get('action', ''),
            entity_type = d.get('entity_type'),
            entity_id   = d.get('entity_id'),
            details     = d.get('details'),
            ip_address  = d.get('ip_address'),
            timestamp   = d.get('timestamp'),
        )

    @classmethod
    def recent(cls, limit: int = 20) -> List['AuditLog']:
        """Return the most recent audit log entries."""
        from database.db import db_query
        rows = db_query(
            "SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        return [cls.from_dict(dict(r)) for r in rows]

    def get_user(self) -> Optional[User]:
        """Lazy-load the user who triggered this log entry."""
        return User.get_by_id(self.user_id) if self.user_id else None

    def __repr__(self):
        return f"<AuditLog id={self.id} action='{self.action}' user_id={self.user_id}>"
