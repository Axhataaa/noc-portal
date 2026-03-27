"""
NOC Portal — File Upload Utility
Handles secure PDF upload for offer letters.

Security measures:
- Only PDF files accepted (validated by extension + magic bytes)
- Unique filenames generated with UUID to prevent overwrites
- werkzeug.utils.secure_filename strips path traversal
- Files served through a controlled route, never via direct path exposure
- Max file size enforced at config level (MAX_UPLOAD_BYTES)
"""
import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app


ALLOWED_EXTENSIONS = {'pdf'}

# PDF magic bytes (first 4 bytes of every valid PDF)
PDF_MAGIC = b'%PDF'


def allowed_file(filename: str) -> bool:
    """Check file extension is in the allowed set."""
    return (
        '.' in filename and
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def validate_pdf_bytes(file_stream) -> bool:
    """
    Read the first 4 bytes and verify PDF magic number.
    Rewinds the stream to the start before returning.
    """
    header = file_stream.read(4)
    file_stream.seek(0)
    return header == PDF_MAGIC


def validate_pdf(file) -> bool:
    """
    Public helper: validate a FileStorage object is a real PDF.
    Checks both file extension and PDF magic bytes (%PDF).
    Rewinds the stream before returning so it remains readable.
    Returns True if valid, False otherwise.
    """
    if not file or not file.filename:
        return False
    return allowed_file(file.filename) and validate_pdf_bytes(file.stream)


def save_offer_letter(file, app_id: int, student_id: int):
    """
    Validate and save an uploaded offer letter PDF.

    Returns:
        (unique_name, original_name) tuple on success, or (None, None) on failure.

    Raises nothing — all errors are returned as None to keep upload failures
    non-blocking (the rest of the application form still works).
    """
    if not file or not file.filename:
        return None, None

    # Extension check
    if not allowed_file(file.filename):
        return None, None

    # Magic bytes check (prevents disguised files)
    if not validate_pdf_bytes(file.stream):
        return None, None

    # Sanitise the student's original filename for safe display (no path traversal)
    original_name = secure_filename(file.filename) or 'offer_letter.pdf'

    # Build a unique internal filename — UUID prevents overwrites and guessing
    unique_name = f"offer_{app_id}_{student_id}_{uuid.uuid4().hex}.pdf"

    upload_dir = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_dir, exist_ok=True)

    save_path = os.path.join(upload_dir, unique_name)
    file.stream.seek(0)
    file.save(save_path)

    return unique_name, original_name


def delete_offer_letter(filename: str) -> None:
    """Delete an offer letter file from disk. Silent on failure."""
    if not filename:
        return
    try:
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], secure_filename(filename))
        if os.path.isfile(path):
            os.remove(path)
    except Exception:
        pass

