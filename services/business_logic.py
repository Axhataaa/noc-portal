from __future__ import annotations
"""
NOC Portal — Business Logic / Service Layer
═══════════════════════════════════════════
Centralises all domain logic that was previously scattered across route
handlers. Routes become thin — they validate HTTP input, call a service
method, and render/redirect. All real decisions live here.

Services are stateless — every method is a @staticmethod or @classmethod
that receives its inputs explicitly and returns a result dict or raises.

Design:
  • ApplicationService  → NOC apply, approve, reject, withdraw
  • UserService         → registration, password change, admin operations
  • DocumentService     → offer letter upload, download, delete
"""
import hashlib

def generate_verification_token(noc_id):
    secret = "NOC_SECRET_KEY_2026"
    raw = f"{noc_id}{secret}"
    return hashlib.sha256(raw.encode()).hexdigest()

from datetime import date, datetime
from typing import Optional, Tuple

from database.db import db_query
from models.models import Application, User
from utils.helpers import enrich, enrich_all, paginate


# ══════════════════════════════════════════════════════════════════
#  APPLICATION SERVICE
# ══════════════════════════════════════════════════════════════════

class ApplicationService:
    """
    Handles all business logic related to NOC applications.
    Each method returns a (result, error) tuple — error is None on success.
    """

    # ── Validation constants ──────────────────────────────────────
    REQUIRED_FIELDS = [
        'company_name', 'internship_role', 'location', 'company_address',
        'manager_name', 'manager_email', 'noc_purpose',
        'start_date', 'end_date', 'student_contact', 'academic_year',
    ]
    MIN_DURATION_DAYS = 7

    @staticmethod
    def validate_application(form: dict) -> dict:
        """
        Validate application form data.

        Returns:
            A dict of field → error message. Empty dict means no errors.
        """
        errors = {}

        # Required field checks
        for field_name in ApplicationService.REQUIRED_FIELDS:
            if not form.get(field_name, '').strip():
                label = field_name.replace('_', ' ').title()
                errors[field_name] = f'{label} is required.'

        # Date logic
        s_str = form.get('start_date', '')
        e_str = form.get('end_date', '')
        if s_str and e_str and 'start_date' not in errors and 'end_date' not in errors:
            try:
                s = date.fromisoformat(s_str)
                e = date.fromisoformat(e_str)
                if s < date.today():
                    errors['start_date'] = 'Start date cannot be in the past.'
                elif e <= s:
                    errors['end_date'] = 'End date must be after start date.'
                elif (e - s).days < ApplicationService.MIN_DURATION_DAYS:
                    errors['end_date'] = 'Duration must be at least 1 week.'
            except ValueError:
                errors['start_date'] = 'Invalid date format.'

        return errors

    @staticmethod
    def create_application(form: dict, student: dict) -> Tuple[Optional[int], Optional[str]]:
        """
        Insert a new NOC application for the given student.

        Args:
            form:    Cleaned POST form data dict.
            student: Current user dict (must be role='student').

        Returns:
            (application_id, None) on success, or (None, error_message).
        """
        s_str = form.get('start_date', '')
        e_str = form.get('end_date', '')

        try:
            s     = date.fromisoformat(s_str)
            e     = date.fromisoformat(e_str)
            weeks = (e - s).days // 7
        except ValueError:
            return None, 'Invalid date values.'

        # Fetch student's branch (may differ from form)
        sb       = db_query("SELECT branch FROM users WHERE id=?", (student['id'],), one=True)
        s_branch = sb['branch'] if sb and sb['branch'] else ''

        # 🔥 Generate NOC ID
        import random
        noc_id = f"NOC-{datetime.now().year}-{random.randint(100000,999999)}"

        # 🔐 Generate token
        token = generate_verification_token(noc_id)

        aid = db_query(
            """INSERT INTO applications
            (student_id, company_name, internship_role, start_date, end_date,
                duration_weeks, stipend, location, description, department, branch,
                company_address, company_website, manager_name, manager_designation,
                manager_email, manager_phone, offer_letter_ref,
                internship_mode, work_hours, noc_purpose,
                student_contact, academic_year,
                noc_id, verification_token)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                student['id'],
                form.get('company_name', ''),
                form.get('internship_role', ''),
                s_str, e_str, weeks,
                form.get('stipend', ''),
                form.get('location', ''),
                form.get('description', ''),
                student.get('department', ''),
                s_branch,
                form.get('company_address', ''),
                form.get('company_website', ''),
                form.get('manager_name', ''),
                form.get('manager_designation', ''),
                form.get('manager_email', ''),
                form.get('manager_phone', ''),
                form.get('offer_letter_ref', ''),
                form.get('internship_mode', 'On-site'),
                form.get('work_hours', ''),
                form.get('noc_purpose', ''),
                form.get('student_contact', ''),
                form.get('academic_year', ''),
                noc_id,
                token
            ),
            commit=True
        )
        return aid, None

    @staticmethod
    def approve(app_id: int, hod: dict, remarks: str) -> Tuple[bool, Optional[str]]:
        """
        Approve a Pending application.

        Returns (True, None) on success, or (False, error_message).
        """
        row = db_query("SELECT * FROM applications WHERE id=?", (app_id,), one=True)
        if not row:
            return False, 'Application not found.'
        if row['department'] != hod['department']:
            return False, 'Access denied — wrong department.'
        if row['status'] != 'Pending':
            return False, 'Only pending applications can be approved.'

        db_query(
            """UPDATE applications
               SET status='Approved', hod_remarks=?, reviewed_by=?, reviewed_at=?
               WHERE id=?""",
            (remarks, hod['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'), app_id),
            commit=True
        )
        return True, None

    @staticmethod
    def reject(app_id: int, hod: dict, remarks: str) -> Tuple[bool, Optional[str]]:
        """
        Reject a Pending application. Remarks are required.

        Returns (True, None) on success, or (False, error_message).
        """
        if not remarks:
            return False, 'A rejection reason is required.'

        row = db_query("SELECT * FROM applications WHERE id=?", (app_id,), one=True)
        if not row:
            return False, 'Application not found.'
        if row['department'] != hod['department']:
            return False, 'Access denied — wrong department.'
        if row['status'] != 'Pending':
            return False, 'Only pending applications can be rejected.'

        db_query(
            """UPDATE applications
               SET status='Rejected', hod_remarks=?, reviewed_by=?, reviewed_at=?
               WHERE id=?""",
            (remarks, hod['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'), app_id),
            commit=True
        )
        return True, None

    @staticmethod
    def withdraw(app_id: int, student_id: int) -> Tuple[bool, Optional[str]]:
        """
        Withdraw (delete) a Pending application belonging to the student.

        Returns (True, None) on success, or (False, error_message).
        """
        row = db_query(
            "SELECT * FROM applications WHERE id=? AND student_id=?",
            (app_id, student_id), one=True
        )
        if not row:
            return False, 'Application not found.'
        if row['status'] != 'Pending':
            return False, 'Only pending applications can be withdrawn.'

        # Clean up uploaded file if any
        if row['offer_letter_path']:
            from utils.uploads import delete_offer_letter
            delete_offer_letter(row['offer_letter_path'])

        db_query("DELETE FROM applications WHERE id=?", (app_id,), commit=True)
        return True, None

    @staticmethod
    def get_student_stats(student_id: int) -> dict:
        """Return count stats for a student's applications."""
        rows = db_query(
            "SELECT status FROM applications WHERE student_id=?", (student_id,)
        )
        apps = [dict(r) for r in rows]
        return {
            'total':    len(apps),
            'pending':  sum(1 for a in apps if a['status'] == 'Pending'),
            'approved': sum(1 for a in apps if a['status'] == 'Approved'),
            'rejected': sum(1 for a in apps if a['status'] == 'Rejected'),
        }

    @staticmethod
    def get_department_stats(department: str) -> dict:
        """Return count stats for a HOD's department."""
        rows = db_query(
            "SELECT status FROM applications WHERE department=?", (department,)
        )
        apps = [dict(r) for r in rows]
        return {
            'total':    len(rows),
            'pending':  sum(1 for a in apps if a['status'] == 'Pending'),
            'approved': sum(1 for a in apps if a['status'] == 'Approved'),
            'rejected': sum(1 for a in apps if a['status'] == 'Rejected'),
        }

    @staticmethod
    def list_for_hod(department: str, search: str = '', status_filter: str = '',
                     page: int = 1, per_page: int = 20) -> dict:
        """
        Fetch paginated applications for a HOD's department, with optional
        search and status filter.
        """
        sql    = """SELECT a.*, u.name AS student_name,
                           u.enrollment AS student_enrollment,
                           u.branch AS branch
                    FROM applications a
                    JOIN users u ON a.student_id = u.id
                    WHERE a.department = ?"""
        params = [department]

        if status_filter:
            sql += " AND a.status = ?"; params.append(status_filter)
        if search:
            like  = f'%{search}%'
            sql  += """ AND (u.name LIKE ? OR a.company_name LIKE ?
                             OR a.internship_role LIKE ? OR u.enrollment LIKE ?)"""
            params += [like, like, like, like]
        sql += " ORDER BY a.created_at DESC"

        all_apps              = enrich_all(db_query(sql, params))
        apps, total_pgs, page = paginate(all_apps, page, per_page)
        return {
            'applications':  apps,
            'total_results': len(all_apps),
            'total_pages':   total_pgs,
            'page':          page,
        }

    @staticmethod
    def list_for_admin(status_filter: str = '', dept_filter: str = '',
                       search: str = '', page: int = 1, per_page: int = 20) -> dict:
        """Fetch paginated applications for the admin view."""
        sql    = """SELECT a.*, u.name AS student_name,
                           u.enrollment AS student_enrollment,
                           u.branch AS branch
                    FROM applications a
                    JOIN users u ON a.student_id=u.id WHERE 1=1"""
        params = []
        if status_filter:
            sql += " AND a.status=?";     params.append(status_filter)
        if dept_filter:
            sql += " AND a.department=?"; params.append(dept_filter)
        if search:
            like  = f'%{search}%'
            sql  += " AND (u.name LIKE ? OR a.company_name LIKE ? OR a.internship_role LIKE ?)"
            params += [like, like, like]
        sql += " ORDER BY a.created_at DESC"

        all_apps              = enrich_all(db_query(sql, params))
        apps, total_pgs, page = paginate(all_apps, page, per_page)
        return {
            'applications':  apps,
            'total_results': len(all_apps),
            'total_pages':   total_pgs,
            'page':          page,
        }


# ══════════════════════════════════════════════════════════════════
#  USER SERVICE
# ══════════════════════════════════════════════════════════════════

class UserService:
    """Handles user registration, authentication helpers, and admin operations."""

    @staticmethod
    def validate_registration(form: dict, branch_to_dept: dict) -> Tuple[dict, str]:
        """
        Validate registration form. Returns (errors_dict, derived_department).
        errors_dict is empty on success.
        """
        from flask import current_app
        from utils.helpers import get_setting

        HOD_SECRET = get_setting('HOD_SECRET')
        ADMIN_SECRET = get_setting('ADMIN_SECRET')

        name   = form.get('name', '')
        email  = form.get('email', '').lower()
        pwd    = form.get('password', '')
        conf   = form.get('confirm_password', '')
        role   = form.get('role', 'student')
        branch = form.get('branch', '')
        secret = form.get('secret_code', '')

        # Derive department
        if role == 'student':
            dept = branch_to_dept.get(branch, form.get('department', ''))
        elif role == 'hod':
            dept = form.get('department_hod', '').strip()
        else:
            dept = 'Administration'

        errors = {}
        if not name:  errors['name']  = 'Full name is required.'
        if not email: errors['email'] = 'Email address is required.'
        elif '@' not in email or '.' not in email.split('@')[-1]:
            errors['email'] = 'Please enter a valid email address.'
        if role == 'student' and not dept:   errors['department']    = 'Please select your department.'
        if role == 'student' and not branch: errors['branch']        = 'Please select your branch.'
        if role == 'hod'     and not dept:   errors['department']    = 'Please select your department.'
        if role == 'student' and not form.get('enrollment_no'): errors['enrollment_no'] = 'Enrollment number is required.'
        if role == 'hod'   and secret != HOD_SECRET:   errors['secret_code'] = 'Invalid HOD registration code.'
        if role == 'admin' and secret != ADMIN_SECRET: errors['secret_code'] = 'Invalid Admin registration code.'
        if not pwd:        errors['password'] = 'Password is required.'
        elif len(pwd) < 6: errors['password'] = 'Password must be at least 6 characters.'
        elif pwd != conf:  errors['confirm_password'] = 'Passwords do not match.'

        return errors, dept

    @staticmethod
    def change_password(user_id: int, current_pw: str,
                        new_pw: str, confirm_pw: str) -> Optional[str]:
        """
        Change a user's password.

        Returns None on success, or an error string on failure.
        """
        from werkzeug.security import check_password_hash, generate_password_hash
        row = db_query("SELECT password FROM users WHERE id=?", (user_id,), one=True)
        if not row or not check_password_hash(row['password'], current_pw):
            return 'Current password is incorrect.'
        if len(new_pw) < 6:
            return 'New password must be at least 6 characters.'
        if new_pw != confirm_pw:
            return 'New passwords do not match.'
        db_query("UPDATE users SET password=? WHERE id=?",
                 (generate_password_hash(new_pw), user_id), commit=True)
        return None

    @staticmethod
    def toggle_active(uid: int, acting_user_id: int) -> Tuple[bool, str]:
        """Toggle a user's is_active flag. Returns (success, message)."""
        if uid == acting_user_id:
            return False, 'You cannot deactivate your own account.'
        row = db_query("SELECT * FROM users WHERE id=?", (uid,), one=True)
        if not row:
            return False, 'User not found.'
        new_val = 0 if row['is_active'] else 1
        db_query("UPDATE users SET is_active=? WHERE id=?", (new_val, uid), commit=True)
        state = 'activated' if new_val else 'deactivated'
        return True, f"User {row['name']} has been {state}."

    @staticmethod
    def reset_password(uid: int, new_pwd: str) -> Tuple[bool, str]:
        """Admin: reset any user's password."""
        from werkzeug.security import generate_password_hash
        if len(new_pwd) < 6:
            return False, 'New password must be at least 6 characters.'
        row = db_query("SELECT name FROM users WHERE id=?", (uid,), one=True)
        if not row:
            return False, 'User not found.'
        db_query("UPDATE users SET password=? WHERE id=?",
                 (generate_password_hash(new_pwd), uid), commit=True)
        return True, f"Password for {row['name']} has been reset successfully."

    @staticmethod
    def delete_user(uid: int, acting_user_id: int) -> Tuple[bool, str]:
        """Admin: permanently delete a user and all their data."""
        if uid == acting_user_id:
            return False, 'You cannot delete your own account.'
        row = db_query("SELECT * FROM users WHERE id=?", (uid,), one=True)
        if not row:
            return False, 'User not found.'
        # Cascade delete
        db_query("DELETE FROM audit_logs  WHERE user_id=?",   (uid,), commit=True)
        db_query("DELETE FROM applications WHERE student_id=?", (uid,), commit=True)
        db_query("DELETE FROM users WHERE id=?",               (uid,), commit=True)
        return True, f"User {row['name']} has been permanently deleted."


# ══════════════════════════════════════════════════════════════════
#  DOCUMENT SERVICE
# ══════════════════════════════════════════════════════════════════

class DocumentService:
    """Handles offer letter file operations with security validation."""

    MAX_BYTES = 5 * 1024 * 1024   # 5 MB hard limit

    @staticmethod
    def handle_upload(file, app_id: int, student_id: int,
                      max_bytes: Optional[int] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Validate, save, and register an uploaded offer letter.

        Args:
            file:       werkzeug FileStorage object from request.files
            app_id:     ID of the application this document belongs to
            student_id: ID of the uploading student
            max_bytes:  Override default size limit

        Returns:
            (saved_filename, None)  on success
            (None, error_message)  on failure — caller should flash + continue
        """
        from utils.uploads import save_offer_letter

        if not file or not file.filename:
            return None, 'No file provided.'

        limit = max_bytes or DocumentService.MAX_BYTES

        # Size check before saving
        file.stream.seek(0, 2)
        size = file.stream.tell()
        file.stream.seek(0)
        if size > limit:
            return None, f'File exceeds the {limit // (1024*1024)} MB limit.'

        saved = save_offer_letter(file, app_id, student_id)
        if not saved:
            return None, 'Only valid PDF files are accepted.'

        return saved, None

    @staticmethod
    def attach_to_application(app_id: int, filename: str) -> None:
        """Update the application record with the uploaded filename."""
        db_query(
            "UPDATE applications SET offer_letter_path=? WHERE id=?",
            (filename, app_id), commit=True
        )

    @staticmethod
    def replace(app_id: int, student_id: int, new_file,
                max_bytes: Optional[int] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Replace an existing offer letter (delete old, save new).

        Returns (new_filename, None) on success, or (None, error_message).
        """
        # Get current filename to delete
        row = db_query(
            "SELECT offer_letter_path FROM applications WHERE id=? AND student_id=?",
            (app_id, student_id), one=True
        )
        if row and row['offer_letter_path']:
            from utils.uploads import delete_offer_letter
            delete_offer_letter(row['offer_letter_path'])

        saved, err = DocumentService.handle_upload(new_file, app_id, student_id, max_bytes)
        if err:
            return None, err
        DocumentService.attach_to_application(app_id, saved)
        return saved, None

    @staticmethod
    def get_safe_path(app_id: int, user: dict) -> Tuple[Optional[str], Optional[str]]:
        """
        Retrieve and authorise access to an offer letter file.

        Enforces:
          - Admin: can access any application's file
          - HOD:   only their department's applications
          - Student: only their own applications

        Returns (filename, None) if authorised, or (None, error_message).
        """
        from flask import current_app
        import os
        from werkzeug.utils import secure_filename

        # Role-based query
        if user['role'] == 'admin':
            row = db_query("SELECT * FROM applications WHERE id=?", (app_id,), one=True)
        elif user['role'] == 'hod':
            row = db_query(
                "SELECT * FROM applications WHERE id=? AND department=?",
                (app_id, user['department']), one=True
            )
        else:  # student
            row = db_query(
                "SELECT * FROM applications WHERE id=? AND student_id=?",
                (app_id, user['id']), one=True
            )

        if not row:
            return None, 'Application not found or access denied.'
        if not row['offer_letter_path']:
            return None, 'No offer letter has been uploaded for this application.'

        filename  = secure_filename(row['offer_letter_path'])
        full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        if not os.path.isfile(full_path):
            return None, 'File not found on server.'

        return filename, None
