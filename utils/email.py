"""
NOC Portal — Email notifications
send_notification() silently skips if MAIL_SERVER is not configured.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app


def send_notification(to_email, subject, body_html):
    """
    Send an HTML email notification.
    Does nothing if MAIL_SERVER / MAIL_USERNAME are not set in config.
    Never raises — email failures must not crash the application.
    """
    cfg = current_app.config
    if not cfg.get('MAIL_SERVER') or not cfg.get('MAIL_USERNAME'):
        return  # Email not configured — skip silently

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = cfg.get('MAIL_FROM', 'noc@college.edu')
        msg['To']      = to_email
        msg.attach(MIMEText(body_html, 'html'))
        with smtplib.SMTP(cfg['MAIL_SERVER'], cfg['MAIL_PORT'], timeout=5) as s:
            s.starttls()
            s.login(cfg['MAIL_USERNAME'], cfg['MAIL_PASSWORD'])
            s.sendmail(msg['From'], [to_email], msg.as_string())
    except Exception:
        pass  # Never crash the app due to email failure
