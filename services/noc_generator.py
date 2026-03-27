"""
NOC Portal — Certificate Generator
====================================
Generates a formal NOC letter PDF matching the MITS Gwalior format.
Requires: pip install reportlab>=4.0.0
"""

import os
import io
import struct
import zlib
import qrcode
from datetime import datetime
from database.db import db_query

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, KeepTogether
    )
    from reportlab.pdfgen import canvas as pdfcanvas
    REPORTLAB_OK = True

    # Colour palette matching MITS certificate
    BLACK      = colors.black
    DARK_GRAY  = colors.HexColor('#1a1a1a')
    MID_GRAY   = colors.HexColor('#555555')
    LIGHT_GRAY = colors.HexColor('#aaaaaa')
    NAVY       = colors.HexColor('#1a1a6e')   # deep navy for institute name
    ACCENT     = colors.HexColor('#1a3e8c')   # blue accent for table headers
    GOLD       = colors.HexColor('#8B6914')   # gold for NAAC line
    TABLE_HEAD = colors.HexColor('#dce8f5')
    TABLE_ROW  = colors.HexColor('#f8fafc')
    BORDER_CLR = colors.HexColor('#b0c4de')
    RED_NAAC   = colors.HexColor('#cc0000')
except ImportError:
    REPORTLAB_OK = False


# ── DB helpers ────────────────────────────────────────────────────────────────

def _ensure_noc_columns():
    from database.db import get_db
    db = get_db()
    for col in ('noc_id TEXT', 'certificate_path TEXT',
                'approval_date TEXT', 'noc_generated_at TEXT'):
        try:
            db.execute(f"ALTER TABLE applications ADD COLUMN {col}")
            db.commit()
        except Exception:
            pass


def generate_noc_id(application_id: int) -> str:
    return f"NOC-{datetime.now().year}-{application_id:06d}"


def get_certificates_dir(app_config: dict) -> str:
    d = os.path.join(app_config.get('UPLOAD_FOLDER', 'uploads'), 'certificates')
    os.makedirs(d, exist_ok=True)
    return d


def _fmt_long(date_str):
    if not date_str:
        return ''
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime('%B %d, %Y')
        except Exception:
            pass
    return date_str


def _fmt_ref_date(date_str):
    """Format date as 'Month DD, YYYY' for the Ref line."""
    if not date_str:
        return datetime.now().strftime('%B %d, %Y')
    for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d-%m-%Y'):
        try:
            return datetime.strptime(date_str.strip()[:10], fmt).strftime('%B %d, %Y')
        except Exception:
            pass
    return date_str[:10]


# ── Minimal QR PNG (pure stdlib) ──────────────────────────────────────────────

def _make_qr_png(text: str, box_size: int = 5) -> bytes:
    import hashlib
    h = hashlib.sha256(text.encode()).digest()
    size = 21
    pixels = []
    for r in range(size):
        row = []
        for c in range(size):
            in_finder = (
                (r < 7 and c < 7) or
                (r < 7 and c >= size - 7) or
                (r >= size - 7 and c < 7)
            )
            if in_finder:
                lr = r if r < 7 else r - (size - 7)
                lc = c if c < 7 else c - (size - 7)
                if (lr == 0 or lr == 6 or lc == 0 or lc == 6 or
                        (1 < lr < 5 and 1 < lc < 5)):
                    row.append(0)
                else:
                    row.append(255)
            elif r == 6 or c == 6:
                row.append(0 if (r + c) % 2 == 0 else 255)
            else:
                idx = (r * size + c) % len(h)
                bit = (h[idx] >> (c % 8)) & 1
                row.append(0 if bit else 255)
        pixels.append(row)

    img_size = size * box_size
    raw_data = b''
    for row in pixels:
        scanline = b'\x00'
        for pixel in row:
            scanline += bytes([pixel]) * box_size
        for _ in range(box_size):
            raw_data += scanline

    def png_chunk(name, data):
        c = name + data
        crc = zlib.crc32(c) & 0xFFFFFFFF
        return struct.pack('>I', len(data)) + c + struct.pack('>I', crc)

    ihdr = struct.pack('>IIBBBBB', img_size, img_size, 8, 0, 0, 0, 0)
    return (
        b'\x89PNG\r\n\x1a\n'
        + png_chunk(b'IHDR', ihdr)
        + png_chunk(b'IDAT', zlib.compress(raw_data, 9))
        + png_chunk(b'IEND', b'')
    )


# ── Letterhead drawn on canvas (matches MITS PDF format) ─────────────────────

def _draw_letterhead(c, doc, cfg):
    w, h = A4

    institute_full = cfg.get('INSTITUTE_NAME_FULL',
                             'Madhav Institute of Technology & Science, Gwalior (M.P.), India')
    institute_short = cfg.get('INSTITUTE_NAME', 'MITS')
    phone    = cfg.get('INSTITUTE_PHONE', '')
    email_id = cfg.get('INSTITUTE_EMAIL', '')

    # ── Top horizontal rule ──
    c.setStrokeColor(NAVY)
    c.setLineWidth(2)
    c.line(12*mm, h - 30*mm, w - 12*mm, h - 30*mm)

    # ── Hindi name (transliterated, bold) ──
    c.setFont('Helvetica-Bold', 13)
    c.setFillColor(NAVY)
    hindi_approx = 'माधव प्रौद्योगिकी एवं विज्ञान संस्थान, ग्वालियर (म.प्र.), भारत'
    # Since standard PDF fonts don't support Devanagari, we render the English equivalent
    # in a styled format that matches the certificate header layout
    c.setFont('Helvetica-Bold', 11)
    c.drawCentredString(w / 2, h - 10*mm, institute_full.upper())

    # ── Declared under line ──
    c.setFont('Helvetica', 8)
    c.setFillColor(RED_NAAC)
    c.drawCentredString(w / 2, h - 15.5*mm, 'Deemed University')

    c.setFont('Helvetica', 7.5)
    c.setFillColor(DARK_GRAY)
    c.drawCentredString(w / 2, h - 19*mm,
        '(Declared under Distinct Category by Ministry of Education, Government of India)')

    c.setFont('Helvetica-Bold', 8)
    c.setFillColor(RED_NAAC)
    c.drawCentredString(w / 2, h - 22.5*mm, 'NAAC ACCREDITED WITH A++ GRADE')

    # ── Bottom rule under header ──
    c.setStrokeColor(NAVY)
    c.setLineWidth(1.5)
    c.line(12*mm, h - 26*mm, w - 12*mm, h - 26*mm)
    c.setLineWidth(0.5)
    c.line(12*mm, h - 27*mm, w - 12*mm, h - 27*mm)

    # ── Contact line ──
    parts = []
    if phone:    parts.append(f'Phone: {phone}')
    if email_id: parts.append(f'Email Id: {email_id}')
    if parts:
        c.setFont('Helvetica', 7.5)
        c.setFillColor(MID_GRAY)
        c.drawCentredString(w / 2, h - 30.5*mm, '   |   '.join(parts))

    # ── Footer ──
    c.setStrokeColor(LIGHT_GRAY)
    c.setLineWidth(0.4)
    c.line(12*mm, 20*mm, w - 12*mm, 20*mm)

    c.setFont('Helvetica-Oblique', 7)
    c.setFillColor(MID_GRAY)
    c.drawCentredString(
        w / 2, 15*mm,
        'Important Declaration: This is a system-generated letter with reference no. after the approval '
        'from the authority. There is no need for a signature and seal on a hard copy.'
    )


# ── Story (letter body) ───────────────────────────────────────────────────────

def _build_story(app, student, noc_id, approval_date, app_config, verify_url, qr_path):
    styles = getSampleStyleSheet()

    def S(name, **kw):
        return ParagraphStyle(name, parent=styles['Normal'], **kw)

    story = []
    # Space for letterhead (drawn by canvas)
    story.append(Spacer(1, 36*mm))

    story.append(Paragraph(
    "Phone: 0751-2409362 | Email: tnp@mitsgwalior.in",
    S('HDR', fontSize=9, fontName='Helvetica', alignment=TA_CENTER, textColor=MID_GRAY)
    ))
    story.append(Spacer(1, 4*mm))

    # ── Ref + Date row ──
    ref_label = S('RL', fontSize=9, fontName='Helvetica-Bold',
                  alignment=TA_LEFT, textColor=BLACK)
    date_label = S('DR', fontSize=9, fontName='Helvetica',
                   alignment=TA_RIGHT, textColor=MID_GRAY)
    ref_date_str = _fmt_ref_date(approval_date)
    noc_num = noc_id.split('-')[-1] if '-' in noc_id else noc_id
    ref_tbl = Table(
        [[Paragraph(f'Ref.: T&P/{str(datetime.now().year)[-2:]}/ {noc_num}', ref_label),
          Paragraph(f'Date: {ref_date_str}', date_label)]],
        colWidths=[95*mm, 85*mm]
    )
    ref_tbl.setStyle(TableStyle([
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
        ('TOPPADDING',    (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(ref_tbl)
    story.append(Spacer(1, 6*mm))
    

    # ── To block ──
    company  = (app.get('company_name') or '').strip()
    manager  = (app.get('manager_name') or '').strip()
    mgr_desig = (app.get('manager_designation') or '').strip()
    location = (app.get('location') or app.get('company_address') or '').strip()

    to_style = S('TO', fontSize=9.5, fontName='Helvetica', textColor=DARK_GRAY, leading=14, spaceAfter=0)
    story.append(Paragraph('To,', S('TOH', fontSize=9.5, fontName='Helvetica-Bold',
                                    textColor=BLACK, spaceAfter=1)))
    if manager:   story.append(Paragraph(manager, to_style))
    if mgr_desig: story.append(Paragraph(mgr_desig, to_style))
    if company:   story.append(Paragraph(company, to_style))
    if location:  story.append(Paragraph(location, to_style))
    story.append(Spacer(1, 5*mm))

    # ── Salutation ──
    story.append(Paragraph("Dear Sir/Ma'am,",
                            S('SAL', fontSize=9.5, fontName='Helvetica-Bold',
                              textColor=BLACK, spaceAfter=5)))

    body = S('BD', fontSize=9.5, fontName='Helvetica', textColor=DARK_GRAY,
             leading=15, alignment=TA_JUSTIFY, spaceAfter=5)

    story.append(Paragraph(
        'We are grateful for your cooperation in imparting Industrial Training/Internship '
        'to the students of our institute. This training is a part of academic curriculum '
        'and contributes to their overall academic performance while improving their skills '
        'and personality.',
        body
    ))

    start_fmt = _fmt_long(app.get('start_date', ''))
    end_fmt   = _fmt_long(app.get('end_date', ''))
    story.append(Paragraph(
        f'We will be highly obliged if the following student is permitted to undergo '
        f'Training/Internship at your esteemed Organization from '
        f'<b>{start_fmt}</b> to <b>{end_fmt}</b>.',
        body
    ))
    story.append(Spacer(1, 4*mm))

    # ── Student table ──
    s_name  = (student.get('name') or '').upper()
    enroll  = (student.get('enrollment') or '').strip()
    branch  = (student.get('branch') or app.get('branch') or app.get('department') or '').strip()
    course  = f'B.Tech - {branch}' if branch else 'B.Tech'

    tbl = Table(
        [['S.No.', 'Name of the Student', 'Enrollment No.', 'Course'],
         ['1.',    s_name,                enroll,            course]],
        colWidths=[15*mm, 62*mm, 42*mm, 61*mm],
        repeatRows=1
    )
    tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0), TABLE_HEAD),
        ('TEXTCOLOR',     (0, 0), (-1, 0), ACCENT),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, 0), 8.5),
        ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND',    (0, 1), (-1, -1), TABLE_ROW),
        ('FONTNAME',      (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',      (0, 1), (-1, -1), 9),
        ('GRID',          (0, 0), (-1, -1), 0.5, BORDER_CLR),
        ('TOPPADDING',    (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING',   (0, 0), (-1, -1), 5),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 5),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 6*mm))

    # ── Closing ──
    clos = S('CL', fontSize=9.5, fontName='Helvetica', textColor=DARK_GRAY, spaceAfter=2)
    story.append(Paragraph('Hoping for your kind cooperation.', clos))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph('Best Regards!', clos))
    story.append(Spacer(1, 10*mm))

    # ── Signature block + QR side by side ──
    tnp_name  = app_config.get('TNP_HEAD_NAME', 'Head - Training & Placement Cell')
    tnp_desig = app_config.get('TNP_HEAD_DESIGNATION', 'Head - Training & Placement Cell')
    inst_short = app_config.get('INSTITUTE_NAME', 'Institute')

    sig_b = S('SB', fontSize=9.5, fontName='Helvetica-Bold', textColor=BLACK, spaceAfter=1)
    sig_n = S('SN', fontSize=9,   fontName='Helvetica',      textColor=MID_GRAY, spaceAfter=0)

    # Signature squiggle (decorative line)
    from reportlab.platypus import Flowable

    class SignatureLine(Flowable):
        def draw(self):
            self.canv.setStrokeColor(MID_GRAY)
            self.canv.setLineWidth(0.8)
            # Simple squiggle
            p = self.canv.beginPath()
            p.moveTo(0, 4)
            p.curveTo(6, 10, 12, -2, 18, 4)
            p.curveTo(24, 10, 30, -2, 36, 4)
            self.canv.drawPath(p, stroke=1, fill=0)
        def wrap(self, *args):
            return (40*mm, 8*mm)

    sig_col_content = [
        SignatureLine(),
        Spacer(1, 1*mm),
        Paragraph(f'<b>({tnp_name})</b>', sig_b),
        Paragraph("Head - Training & Placement Cell", sig_n),
    ]

    # QR code
    try:
        from reportlab.platypus import Image as RLImage
        qr_png = _make_qr_png(verify_url, box_size=5)
        qr_buf = io.BytesIO(qr_png)
        qr_img = RLImage(qr_buf, width=24*mm, height=24*mm)
        qr_lbl = Paragraph('<b>Scan this to verify</b>',
                           S('QRL', fontSize=6.5, fontName='Helvetica-Bold',
                             textColor=MID_GRAY, alignment=TA_CENTER))
        qr_col_content = [qr_img, qr_lbl]
    except Exception:
        qr_col_content = [Paragraph('[ QR ]', S('QRP', fontSize=8, fontName='Helvetica',
                                                  textColor=LIGHT_GRAY, alignment=TA_CENTER))]

    sig_row = Table(
        [[sig_col_content, qr_col_content]],
        colWidths=[130*mm, 50*mm]
    )
    sig_row.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'BOTTOM'),
        ('ALIGN',         (1, 0), (1, 0),   'CENTER'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(KeepTogether(sig_row))
    story.append(Spacer(1, 5*mm))

    # ── Verify URL footnote ──
    story.append(HRFlowable(width='100%', thickness=0.4, color=BORDER_CLR, spaceAfter=3))
    story.append(Paragraph(
        f'Kindly feel free to contact us for any further information.',
        S('FN', fontSize=8, fontName='Helvetica', textColor=MID_GRAY, spaceAfter=2)
    ))

    return story


# ── Fallback plain PDF ────────────────────────────────────────────────────────

def _generate_plain_pdf(app, student, noc_id, approval_date, cfg, verify_url) -> bytes:
    institute = cfg.get('INSTITUTE_NAME_FULL', 'Institute of Technology')
    tnp_name  = cfg.get('TNP_HEAD_NAME', 'Head - Training & Placement Cell')
    company   = (app.get('company_name') or '').strip()
    s_name    = (student.get('name') or '').upper()
    enroll    = (student.get('enrollment') or '').strip()
    branch    = (student.get('branch') or '').strip()
    start_d   = _fmt_long(app.get('start_date', ''))
    end_d     = _fmt_long(app.get('end_date', ''))

    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
    from reportlab.lib import colors

    styles = getSampleStyleSheet()

    def S(name, **kw):
        return ParagraphStyle(name, parent=styles['Normal'], **kw)

    # ── STYLES ──
    title = S('title', fontSize=12, fontName='Helvetica-Bold', alignment=TA_CENTER)
    bold  = S('bold', fontSize=10, fontName='Helvetica-Bold')
    normal = S('normal', fontSize=10, leading=14)
    right = S('right', fontSize=10, alignment=TA_RIGHT)

    story = []

    # ── HEADER ──
    story.append(Paragraph("<b>INSTITUTE OF TECHNOLOGY</b>", title))
    story.append(Paragraph("Phone: 0751-2409362 | Email: tnp@mitsgwalior.in", normal))
    story.append(Spacer(1, 10))

    # ── REF + DATE ──
    ref_table = Table([
        [
            Paragraph(f"<b>Ref.: T&P/{datetime.now().year}/{noc_id.split('-')[-1]}</b>", bold),
            Paragraph(f"Date: {_fmt_ref_date(approval_date)}", right)
        ]
    ], colWidths=[300, 150])

    story.append(ref_table)
    story.append(Spacer(1, 10))

    # ── TO SECTION ──
    story.append(Paragraph("To,", bold))
    story.append(Paragraph(app.get('manager_name') or '', normal))
    story.append(Paragraph(company, normal))
    story.append(Paragraph(app.get('location') or '', normal))
    story.append(Spacer(1, 10))

    # ── BODY ──
    story.append(Paragraph("<b>Dear Sir/Ma'am,</b>", normal))
    story.append(Spacer(1, 8))

    story.append(Paragraph(
    "We are grateful for your cooperation in imparting Industrial Training/Internship to students of our institute. "
    "This training is a part of academic curriculum and helps improve skills and personality.",
    normal))

    story.append(Spacer(1, 8))

    story.append(Paragraph(
    f"We will be highly obliged if the following student is permitted to undergo internship at your esteemed organization "
    f"from <b>{start_d}</b> to <b>{end_d}</b>.",
    normal))

    story.append(Spacer(1, 12))

    # ── TABLE ──
    table_data = [
        ["S.No.", "Name of the Student", "Enrollment No.", "Course"],
        ["1", s_name, enroll, f"B.Tech - {branch}"]
    ]

    table = Table(table_data, colWidths=[50, 150, 120, 150])
    table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ]))

    story.append(table)
    story.append(Spacer(1, 12))

    # ── FOOTER TEXT ──
    story.append(Paragraph("Hoping for your kind cooperation.", normal))
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Best Regards!</b>", normal))
    story.append(Spacer(1, 10))

    story.append(Paragraph(f"<b>({tnp_name})</b>", bold))
    story.append(Paragraph("Head - Training & Placement Cell", normal))

    story.append(Spacer(1, 20))

    story.append(Spacer(1, 5*mm))
    story.append(Paragraph(
        "Kindly feel free to contact us for any further information.",
        S('FOOT', fontSize=8.5, fontName='Helvetica', textColor=MID_GRAY)
    ))

    # ── DECLARATION ──
    story.append(Paragraph(
        '<i>Important Declaration: This is a system-generated letter with reference no. '
        'after the approval from the authority. There is no need for a signature and seal '
        'on a hard copy.</i>',
        S('DECL', fontSize=8, fontName='Helvetica-Oblique', textColor=MID_GRAY)
    ))

    stream_cmds = ['BT', '/F1 10 Tf', '50 800 Td', '13 TL']
    for line in lines:
        safe = line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        stream_cmds.append(f'({safe}) Tj T*')
    stream_cmds.append('ET')
    stream_bytes = '\n'.join(stream_cmds).encode('latin-1', errors='replace')

    objs = {
        1: b'<< /Type /Catalog /Pages 2 0 R >>',
        2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        3: (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] '
            b'/Contents 5 0 R /Resources << /Font << /F1 4 0 R >> >> >>'),
        4: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        5: (f'<< /Length {len(stream_bytes)} >>\nstream\n').encode() +
            stream_bytes + b'\nendstream',
    }
    buf = b'%PDF-1.4\n'
    offsets = {}
    for num in sorted(objs):
        offsets[num] = len(buf)
        buf += f'{num} 0 obj\n'.encode() + objs[num] + b'\nendobj\n'
    xref_pos = len(buf)
    buf += f'xref\n0 {len(objs)+1}\n'.encode()
    buf += b'0000000000 65535 f \n'
    for num in sorted(offsets):
        buf += f'{offsets[num]:010d} 00000 n \n'.encode()
    buf += f'trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n'.encode()
    return buf


# ── Public API 

def generate_noc_certificate(application_id: int, app_config: dict) -> dict:
    """
    Generate NOC PDF. Idempotent — returns existing record if already done.
    Raises ValueError for non-approved applications.
    """
    _ensure_noc_columns()

    row = db_query("SELECT * FROM applications WHERE id=?", (application_id,), one=True)
    if not row:
        raise ValueError(f"Application {application_id} not found")
    app = dict(row)
    if app['status'] != 'Approved':
        raise ValueError("NOC can only be generated for Approved applications")

    certs_dir = get_certificates_dir(app_config)

    # Idempotent: return existing if file is on disk
    if app.get('noc_id') and app.get('certificate_path'):
        fpath = os.path.join(certs_dir, app['certificate_path'])
        if os.path.isfile(fpath):
            return {k: app.get(k, '') for k in
                    ('noc_id', 'certificate_path', 'approval_date', 'noc_generated_at')}

    student = db_query("SELECT * FROM users WHERE id=?", (app['student_id'],), one=True)
    student = dict(student) if student else {}

    noc_id        = generate_noc_id(application_id)
    now_str       = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    approval_date = (app.get('reviewed_at') or now_str)[:10]
    base_url      = app_config.get('BASE_URL', 'http://localhost:5000').rstrip('/')
    token = generate_verification_token(noc_id)
    verify_url = f"{base_url}/verify?noc_id={noc_id}&token={token}"
    filename      = f"NOC_{noc_id}.pdf"
    filepath      = os.path.join(certs_dir, filename)

    if REPORTLAB_OK:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=15*mm, rightMargin=15*mm,
            topMargin=8*mm,   bottomMargin=26*mm,
            title=f'NOC Letter — {noc_id}',
            author=app_config.get('INSTITUTE_NAME', 'Institute'),
        )
        qr_path = None
        story = _build_story(app, student, noc_id, approval_date, app_config, verify_url, qr_path)

        def on_page(c, d):
            _draw_letterhead(c, d, app_config)

        doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
        pdf_bytes = buf.getvalue()
    else:
        pdf_bytes = _generate_plain_pdf(
            app, student, noc_id, approval_date, app_config, verify_url
        )

    with open(filepath, 'wb') as f:
        f.write(pdf_bytes)

    db_query(
        "UPDATE applications SET noc_id=?, certificate_path=?, "
        "approval_date=?, noc_generated_at=? WHERE id=?",
        (noc_id, filename, approval_date, now_str, application_id),
        commit=True
    )

    return {
        'noc_id':           noc_id,
        'certificate_path': filename,
        'approval_date':    approval_date,
        'noc_generated_at': now_str,
    }

import hashlib

def generate_verification_token(noc_id):
    secret = "NOC_SECRET_KEY_2026"  # keep this hidden
    raw = f"{noc_id}{secret}"
    return hashlib.sha256(raw.encode()).hexdigest()

# ── QR Code 
def generate_qr(noc_id, token):
    verify_url = f"http://localhost:5000/verify?noc_id={noc_id}&token={token}"

    qr = qrcode.make(verify_url)

    qr_path = f"static/qr/{noc_id}.png"
    os.makedirs("static/qr", exist_ok=True)
    qr.save(qr_path)

    return qr_path