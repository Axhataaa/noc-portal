"""
NOC Portal — Display helpers
Format dates, enrich DB rows with computed fields, paginate lists.
"""
from datetime import datetime, date


def fmt_date(s, long=False):
    """Format an ISO date/datetime string for display."""
    if not s:
        return '—'
    try:
        dt = datetime.fromisoformat(str(s))
        return dt.strftime('%B %d, %Y' if long else '%b %d, %Y')
    except Exception:
        return str(s)


def fmt_datetime(s):
    """Format an ISO datetime string with time for display."""
    if not s:
        return '—'
    try:
        return datetime.fromisoformat(str(s)).strftime('%b %d, %Y at %I:%M %p')
    except Exception:
        return str(s)


def duration_display(start_str, end_str):
    """Return a human-readable internship duration string."""
    try:
        s = date.fromisoformat(str(start_str))
        e = date.fromisoformat(str(end_str))
        weeks = (e - s).days // 7
        return f"{weeks} week{'s' if weeks != 1 else ''}"
    except Exception:
        return 'N/A'


def enrich(row):
    """
    Convert a sqlite3.Row (or dict) to a plain dict, adding computed
    display fields used in templates.
    """
    if row is None:
        return None
    d = dict(row)
    d['created_at_fmt']   = fmt_date(d.get('created_at'))
    d['reviewed_at_fmt']  = fmt_datetime(d.get('reviewed_at'))
    d['start_date_fmt']   = fmt_date(d.get('start_date'), long=True)
    d['end_date_fmt']     = fmt_date(d.get('end_date'), long=True)
    d['duration_display'] = duration_display(d.get('start_date', ''), d.get('end_date', ''))
    return d


def enrich_all(rows):
    """Apply enrich() to every row in a list."""
    return [enrich(r) for r in rows]


def paginate(items, page, per_page=20):
    """
    Slice a list for the requested page.
    Returns (page_items, total_pages, current_page).
    """
    page      = max(1, page)
    total     = len(items)
    total_pgs = max(1, (total + per_page - 1) // per_page)
    page      = min(page, total_pgs)
    start     = (page - 1) * per_page
    return items[start:start + per_page], total_pgs, page


def get_setting(key):
    """Retrieve a value from system_settings by key."""
    from database.db import db_query
    row = db_query("SELECT value FROM system_settings WHERE key=?", (key,), one=True)
    return row['value'] if row else None


def set_setting(key, value):
    """Insert or update a value in system_settings."""
    from database.db import db_query
    db_query(
        "INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)",
        (key, value),
        commit=True
    )
