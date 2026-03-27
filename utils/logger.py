"""
NOC Portal — Application Logger
════════════════════════════════
Provides a single, consistently configured logger for the entire application.

Usage:
    from utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("User %s logged in", email)
    logger.warning("Failed upload attempt for app_id=%s", app_id)
    logger.error("DB error in student_apply: %s", exc)

Log format:
    2026-03-21 14:05:32  INFO  routes.student  Student arjun@noc.edu submitted application #7

Log levels follow standard severity:
    DEBUG    → detailed trace info (dev only)
    INFO     → normal operational events (logins, submissions, approvals)
    WARNING  → unexpected but recoverable situations (upload failures, bad tokens)
    ERROR    → failures that need attention (DB errors, unhandled exceptions)
"""
import logging
import os
from logging.handlers import RotatingFileHandler


# ── Constants ─────────────────────────────────────────────────────
LOG_FORMAT  = '%(asctime)s  %(levelname)-8s  %(name)s  %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
LOG_FILE    = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'noc_portal.log')
MAX_BYTES   = 5 * 1024 * 1024   # 5 MB per log file
BACKUP_COUNT = 3                 # keep 3 rotated files


def configure_logging(app) -> None:
    """
    Attach file + console handlers to the Flask app logger.
    Call once inside create_app() after the app is created.

    Args:
        app: The Flask application instance.
    """
    log_level = logging.DEBUG if app.debug else logging.INFO

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # ── Console handler (always on) ───────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    # ── Rotating file handler ─────────────────────────────────────
    try:
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        app.logger.addHandler(file_handler)
    except (OSError, PermissionError):
        # If the log file can't be written (e.g. read-only FS), continue without it
        app.logger.warning("Could not open log file %s — logging to console only.", LOG_FILE)

    app.logger.addHandler(console_handler)
    app.logger.setLevel(log_level)
    app.logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger that inherits the root configuration.

    Args:
        name: Typically __name__ of the calling module.

    Returns:
        A standard Python Logger instance.
    """
    return logging.getLogger(name)
