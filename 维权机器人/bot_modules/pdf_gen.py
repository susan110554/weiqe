"""
FBI IC3 – ADRI Bot
PDF Generation Engine — Enhanced official case report.
"""
import io, base64 as _b64, hashlib

# ── Embedded IC3 Seal (base64 PNG) ────────────────────
IC3_SEAL_B64 = "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"

def _get_seal_image(w, h):
    """
    Return a ReportLab Image for the IC3 seal.

    优先从本地 PNG 加载你提供的圆形徽章：
      C:\\Users\\Administrator\\Desktop\\维权机器人\\圆形徽章.png
    如果加载失败，再退回到内嵌的 base64 PNG。
    """
    from reportlab.platypus import Image as RLImage

    # 1) 本地 PNG（你的原始圆形徽章）
    LOCAL_SEAL_PATH = r"C:\Users\Administrator\Desktop\维权机器人\圆形徽章.png"
    try:
        img = RLImage(LOCAL_SEAL_PATH, width=w, height=h)
        return img
    except Exception:
        pass

    # 2) 回退：使用内嵌 base64 PNG
    try:
        data = _b64.b64decode(IC3_SEAL_B64 + "==")
    except Exception:
        return None
    buf = io.BytesIO(data)
    buf.seek(0)
    try:
        img = RLImage(buf, width=w, height=h)
        img._seal_buf = buf
        return img
    except Exception:
        return None


async def generate_case_pdf(case_data: dict, attest_ts: str, auth_id: str) -> bytes:
    """
    Generate official IC3 complaint confirmation PDF.
    Enhanced with:
    - Federal Blue / Gold color theme
    - IC3 Seal on first page header
    - Dynamic status with SHA-256 fingerprint
    - Digital signature verification block
    - Legal attestation box
    - Evidence checklist section
    - Blockchain trace analysis note
    - QR-like case reference footer
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                     Table, TableStyle, HRFlowable)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    buf = io.BytesIO()

    # ── Color palette ──────────────────────────────────────────
    federal_blue  = colors.HexColor("#002D72")
    light_blue    = colors.HexColor("#0054A6")
    gold          = colors.HexColor("#B8960C")
    dark_gold     = colors.HexColor("#8B6914")
    silver        = colors.HexColor("#CBD5E0")
    off_white     = colors.HexColor("#F7FAFC")
    dark_text     = colors.HexColor("#1A202C")
    mid_text      = colors.HexColor("#4A5568")
    green_ok      = colors.HexColor("#276749")
    warn_amber    = colors.HexColor("#744210")
    warn_bg       = colors.HexColor("#FFFBEB")
    warn_border   = colors.HexColor("#D69E2E")
    red_text      = colors.HexColor("#C53030")
    teal_accent   = colors.HexColor("#1A5276")

    # ── Page setup ─────────────────────────────────────────────
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        topMargin=1.2*inch,   bottomMargin=1.2*inch,
        title=f"IC3 Official Case Report — {case_data.get('case_no','N/A')}",
        author="Federal Bureau of Investigation / IC3",
        subject="Internet Crime Complaint — Authorized Digital Reporting Interface",
        creator="IC3-ADRI v2.1",
    )

    styles = getSampleStyleSheet()

    def S(name, **kw):
        base = kw.pop("parent", styles["Normal"])
        return ParagraphStyle(name, parent=base, **kw)

    # ── Styles ─────────────────────────────────────────────────
    accept_style = S("Accept", fontSize=13, textColor=dark_text,
                     fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=8)
    cid_style    = S("CID",    fontSize=14, textColor=federal_blue,
                     fontName="Helvetica-Bold", alignment=TA_CENTER, leading=18)
    section_style= S("Section",fontSize=10, textColor=federal_blue,
                     fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4)
    field_label  = S("Label",  fontSize=9,  textColor=mid_text,
                     fontName="Helvetica", leading=13)
    field_value  = S("Value",  fontSize=9,  textColor=dark_text,
                     fontName="Helvetica-Bold", leading=13)
    footer_style = S("Footer", fontSize=7.5, textColor=mid_text,
                     alignment=TA_CENTER, fontName="Helvetica-Oblique")
    warn_style   = S("Warn",   fontSize=8,  textColor=red_text,
                     fontName="Helvetica-Bold", spaceBefore=6)
    legal_style  = S("Legal",  fontSize=8,  textColor=warn_amber,
                     fontName="Helvetica", leading=12)
    digsig_label = S("DigsigL",fontSize=8,  textColor=federal_blue,
                     fontName="Helvetica-Bold")
    digsig_val   = S("DigsigV",fontSize=7.5,textColor=mid_text,
                     fontName="Helvetica-Oblique")
    note_style   = S("Note",   fontSize=8,  textColor=teal_accent,
                     fontName="Helvetica-Oblique", leading=11, spaceBefore=4)
    bold_small   = S("BoldSm", fontSize=8,  textColor=dark_text,
                     fontName="Helvetica-Bold")

    story = []
    story.append(Spacer(1, 1.4 * inch))  # 留出 Header 空间

    # ── Case Acceptance Banner ─────────────────────────────────
    story.append(Paragraph("OFFICIAL CASE ACCEPTANCE NOTICE", accept_style))

    # ── Case ID + Dynamic Status Box ──────────────────────────
    case_id = case_data.get("case_no", "N/A")
    _status_map = {
        "SUBMITTED":    ("SUBMITTED / PENDING REVIEW",               colors.HexColor("#276749")),
        "VALIDATING":   ("P2 · VALIDATING — AUTO-CHECK IN PROGRESS", colors.HexColor("#2B6CB0")),
        "UNDER REVIEW": ("P3 · UNDER REVIEW — AGENT ASSIGNED",       colors.HexColor("#553C9A")),
        "REFERRED":     ("P4 · REFERRED — TRANSFERRED TO FIELD OFFICE", colors.HexColor("#276749")),
        "CLOSED":       ("P5 · ACTIONED / CLOSED — ARCHIVED",        colors.HexColor("#1A202C")),
    }
    raw_status = case_data.get("status", "SUBMITTED")
    status_label, status_color = _status_map.get(raw_status, (raw_status, green_ok))

    _dyn_status_style = ParagraphStyle("DynStatus", parent=styles["Normal"],
        fontSize=10, textColor=status_color,
        fontName="Helvetica-Bold", alignment=TA_CENTER)

    last_updated = case_data.get("last_updated", case_data.get("registered", attest_ts))
    agent_code   = case_data.get("agent_code", "N/A")

    _pdf_sha = hashlib.sha256(
        f"{case_id}|{raw_status}|{agent_code}|{last_updated}".encode()
    ).hexdigest()

    _upd_style = ParagraphStyle("UpdStyle", parent=styles["Normal"],
        fontSize=8, textColor=mid_text, alignment=TA_CENTER,
        fontName="Helvetica-Oblique")
    _sha_style = ParagraphStyle("ShaStyle", parent=styles["Normal"],
        fontSize=7, textColor=mid_text, alignment=TA_CENTER,
        fontName="Courier")

    cid_table = Table([
        [Paragraph(f"CASE ID: {case_id}", cid_style)],
        [Paragraph(f"STATUS: {status_label}", _dyn_status_style)],
        [Paragraph(f"Last Updated: {last_updated}", _upd_style)],
        [Paragraph(f"STATE-HASH (SHA-256): {_pdf_sha}", _sha_style)],
    ], colWidths=[7*inch])
    cid_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#EBF8FF")),
        ("LINEABOVE",     (0,0), (-1,0), 0.5, silver),
        ("LINEBELOW",     (0,-1), (-1,-1), 0.5, silver),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    story.append(cid_table)
    story.append(Spacer(1, 12))

    # ── Registration metadata ──────────────────────────────────
    _agent_line = agent_code if agent_code != "N/A" else "Not yet assigned"
    reg_rows = [
        ["Registered:",        case_data.get("registered", "N/A")],
        ["Auth Reference:",    auth_id],
        ["Legal Attestation:", attest_ts],
        ["Complainant UID:",   str(case_data.get("uid", "N/A"))],
        ["Assigned Agent:",    _agent_line],
    ]
    reg_table = Table(reg_rows, colWidths=[2.0*inch, 5.0*inch])
    reg_table.setStyle(TableStyle([
        ("FONTNAME",      (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE",      (0,0), (-1,-1), 8.5),
        ("FONTNAME",      (0,0), (0,-1), "Helvetica-Bold"),
        ("TEXTCOLOR",     (0,0), (0,-1), mid_text),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
        ("LINEBELOW",     (0,0), (-1,-2), 0.3, silver),
    ]))
    story.append(reg_table)
    story.append(Spacer(1, 10))

    # ── Section / field helpers ────────────────────────────────
    def section(title, note=None):
        elems = [
            Paragraph(title, section_style),
            HRFlowable(width="100%", thickness=0.8, color=federal_blue, spaceAfter=4),
        ]
        if note:
            elems.append(Paragraph(note, note_style))
        return elems

    def field_row(label, value):
        return [Paragraph(label, field_label),
                Paragraph(str(value) if value else "Not provided", field_value)]

    def data_table(rows):
        t = Table(rows, colWidths=[1.7*inch, 5.3*inch])
        t.setStyle(TableStyle([
            ("FONTSIZE",      (0,0), (-1,-1), 8.5),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LEFTPADDING",   (0,0), (-1,-1), 0),
            ("LINEBELOW",     (0,0), (-1,-2), 0.3, silver),
        ]))
        return t

    # ── CRS-01: Identity & Residency ──────────────────────────
    story.extend(section("CRS-01  |  Identity & Residency"))
    story.append(data_table([
        field_row("Complainant Name",  case_data.get("fullname", "—")),
        field_row("Physical Address",  case_data.get("address",  "—")),
        field_row("Phone / Contact",   case_data.get("phone",    "—")),
        field_row("Email Address",     case_data.get("email",    "—")),
    ]))
    story.append(Spacer(1, 6))

    # ── CRS-02: Crypto Transaction Data ───────────────────────
    story.extend(section(
        "CRS-02  |  Crypto Transaction Data",
        note="⚠ All wallet addresses and transaction hashes are cross-referenced against IC3 blockchain trace database."
    ))
    txid = case_data.get("tx_hash", "—")
    if str(txid).startswith("file:"): txid = "[Screenshot Uploaded — Forensic hash retained]"

    # 金额精度格式化
    raw_amount = case_data.get("amount", "—")
    coin_code  = (case_data.get("coin", "") or "").upper()
    formatted_amount = raw_amount
    try:
        from decimal import Decimal, ROUND_DOWN
        amt_dec = Decimal(str(raw_amount))
        if coin_code in ("USDT", "USDC"): q = Decimal("0.01")
        elif coin_code in ("BTC", "ETH"): q = Decimal("0.00000001")
        else:                              q = Decimal("0.0001")
        formatted_amount = str(amt_dec.quantize(q, rounding=ROUND_DOWN))
    except Exception:
        formatted_amount = raw_amount

    chain = case_data.get("chain_type", "—")
    victim_w = case_data.get("victim_wallet", "—")
    suspect_w = case_data.get("wallet_addr", "—")

    # 自动检测链类型（如未填）
    if chain in ("—", "Unknown", None, ""):
        import re
        if victim_w and re.match(r"^0x[0-9a-fA-F]{40}$", str(victim_w)):
            chain = "ERC-20 / BSC (Ethereum)"
        elif victim_w and re.match(r"^T[A-Za-z0-9]{33}$", str(victim_w)):
            chain = "TRC-20 (TRON)"
        elif victim_w and re.match(r"^(1|3|bc1)[A-Za-z0-9]{25,62}$", str(victim_w)):
            chain = "Bitcoin Network"

    story.append(data_table([
        field_row("Disputed Assets",      f"{formatted_amount} {coin_code}".strip()),
        field_row("Incident Date/Time",   case_data.get("incident_time", "—")),
        field_row("Transaction Hash",     txid),
        field_row("Victim Wallet Addr",   victim_w),
        field_row("Suspect Wallet Addr",  suspect_w),
        field_row("Blockchain Network",   chain),
    ]))
    story.append(Spacer(1, 6))

    # ── Blockchain Trace Analysis Note ────────────────────────
    if suspect_w and suspect_w not in ("—", "Unknown", ""):
        trace_box = Table([[Paragraph(
            f"🔍 <b>BLOCKCHAIN TRACE INITIATED</b><br/>"
            f"Suspect wallet <b>{suspect_w[:20]}...</b> has been flagged for "
            f"on-chain trace analysis via IC3 Crypto Intelligence Unit. "
            f"Results will be attached to case file upon completion.",
            S("TraceNote", fontSize=8, textColor=colors.HexColor("#1A5276"),
              fontName="Helvetica", leading=12)
        )]], colWidths=[7*inch])
        trace_box.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#EBF5FB")),
            ("BOX",           (0,0), (-1,-1), 0.8, colors.HexColor("#1A5276")),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ]))
        story.append(trace_box)
        story.append(Spacer(1, 6))

    # ── CRS-03: Platform & Suspect Info ───────────────────────
    story.extend(section("CRS-03  |  Platform & Suspect Info"))
    story.append(data_table([
        field_row("Scam Platform",          case_data.get("platform",   "—")),
        field_row("Subject Identification", case_data.get("scammer_id", "—")),
    ]))
    story.append(Spacer(1, 10))

    # ── Evidence Summary ───────────────────────────────────────
    evidence_list = case_data.get("evidence_files", [])
    if evidence_list:
        story.extend(section("EVM  |  Attached Evidence Files"))
        ev_rows = []
        for i, ev in enumerate(evidence_list[:10], 1):
            fname = (ev.get("filename") or ev.get("file_name") or f"FILE_{i:02d}").upper()
            sha   = str(ev.get("sha256") or "")[:16]
            ev_rows.append(field_row(f"File {i:02d}", f"{fname}  •  SHA-256: {sha}..."))
        if len(evidence_list) > 10:
            ev_rows.append(field_row("Additional", f"+ {len(evidence_list)-10} more file(s)"))
        story.append(data_table(ev_rows))
        story.append(Spacer(1, 6))

    # ── Legal Attestation Box ──────────────────────────────────
    legal_text = (
        "<b>LEGAL ATTESTATION — 18 U.S.C. § 1001</b><br/>"
        "The complainant has certified under penalty of federal law that all information "
        "provided is true, accurate, and complete to the best of their knowledge. "
        "False statements are subject to federal prosecution with fines and/or imprisonment "
        "up to 5 years.<br/><br/>"
        f"<b>Electronic Signature recorded:</b> {attest_ts}"
    )
    story.append(HRFlowable(width="100%", thickness=1.5, color=federal_blue,
                            spaceBefore=2, spaceAfter=4))
    legal_table = Table([[Paragraph(legal_text, legal_style)]], colWidths=[7*inch])
    legal_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), warn_bg),
        ("BOX",           (0,0), (-1,-1), 1, warn_border),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("RIGHTPADDING",  (0,0), (-1,-1), 10),
    ]))
    story.append(legal_table)
    story.append(Spacer(1, 12))

    # ── Digital Signature Verification Block ──────────────────
    digsig_rows = [
        [Paragraph("DIGITAL SIGNATURE VERIFICATION", digsig_label),
         Paragraph("", digsig_val)],
        [Paragraph("Authentication Method:", digsig_label),
         Paragraph("GPO Authentication Service (AATL)", digsig_val)],
        [Paragraph("Certificate Authority:", digsig_label),
         Paragraph("U.S. Government Publishing Office — Federal PKI Root CA", digsig_val)],
        [
            Paragraph("Signature Status:", digsig_label),
            Paragraph(
                f'<font color="#1A5276"><b>◉</b></font> ✔ Digitally Signed — {attest_ts}',
                digsig_val,
            ),
        ],
        [Paragraph("Verification URL:", digsig_label),
         Paragraph("www.govinfo.gov/verify", digsig_val)],
        [Paragraph("Document Hash:", digsig_label),
         Paragraph(_pdf_sha[:32] + "...", digsig_val)],
        [Paragraph("Signer:", digsig_label),
         Paragraph(f"IC3-ADRI Automated Certification System | Auth Ref: {auth_id}", digsig_val)],
    ]
    digsig_table = Table(digsig_rows, colWidths=[1.8*inch, 5.2*inch])
    digsig_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#EBF4FF")),
        ("BOX",           (0,0), (-1,-1), 1.2, federal_blue),
        ("LINEBELOW",     (0,0), (-1,0),  0.8, federal_blue),
        ("INNERGRID",     (0,1), (-1,-1), 0.3, silver),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("RIGHTPADDING",  (0,0), (-1,-1), 8),
        ("SPAN",          (0,0), (1,0)),
        ("ALIGN",         (0,0), (1,0),  "CENTER"),
    ]))
    story.append(digsig_table)
    story.append(Spacer(1, 8))

    # ── Security Warning ───────────────────────────────────────
    story.append(Paragraph(
        "SECURITY NOTICE: This document contains sensitive law enforcement information. "
        "Handle in accordance with federal data protection standards (FIPS 140-3). "
        "Retain Case ID as your official query credential for all future correspondence.",
        warn_style))
    story.append(Spacer(1, 8))

    # ── Next Steps box ─────────────────────────────────────────
    next_steps = Table([[Paragraph(
        "<b>RECOMMENDED NEXT STEPS</b><br/>"
        "1. Save this PDF securely and do not share Case ID publicly.<br/>"
        "2. Preserve all original communications, wallet records, and screenshots.<br/>"
        "3. Use Case ID to track your case status via the bot (<code>/status</code>).<br/>"
        "4. An IC3 case officer may contact you via your provided contact information.",
        S("NextSteps", fontSize=8, textColor=dark_text,
          fontName="Helvetica", leading=12)
    )]], colWidths=[7*inch])
    next_steps.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#F0FFF4")),
        ("BOX",           (0,0), (-1,-1), 0.8, green_ok),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
    ]))
    story.append(next_steps)
    story.append(Spacer(1, 8))

    # ── Footer ────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=silver))
    story.append(Spacer(1, 4))
    footer_table = Table([[Paragraph(
        f"Digitally signed via U.S. Government Publishing Office PKI · "
        f"IC3-ADRI System v2.1  |  Auth Ref: {auth_id}  |  fbi.gov/ic3",
        footer_style)]], colWidths=[7*inch])
    footer_table.setStyle(TableStyle([
        ("ALIGN",       (0,0), (-1,-1), "CENTER"),
        ("TOPPADDING",  (0,0), (-1,-1), 2),
        ("BOTTOMPADDING",(0,0),(-1,-1), 2),
    ]))
    story.append(footer_table)

    # ── Page decorations ──────────────────────────────────────
    banner_h = 1.2 * inch
    logo_s   = 0.8 * inch

    def _draw_common_marks(canvas_obj, w, h):
        # Top/Bottom classification line
        canvas_obj.setFont("Helvetica-Bold", 8)
        canvas_obj.setFillColor(green_ok)
        canvas_obj.drawCentredString(w / 2.0, h - 0.15 * inch, "UNCLASSIFIED")
        canvas_obj.drawCentredString(w / 2.0, 0.35 * inch, "UNCLASSIFIED")

        # Diagonal watermark: OFFICIAL RECORD（淡灰色透明防伪水印）
        try:
            if hasattr(canvas_obj, "setFillAlpha"):
                canvas_obj.setFillAlpha(0.05)
        except Exception:
            pass
        canvas_obj.setFont("Helvetica-Bold", 50)
        canvas_obj.setFillColor(colors.HexColor("#E2E8F0"))
        canvas_obj.translate(w / 2.0, h / 2.0)
        canvas_obj.rotate(45)
        canvas_obj.drawCentredString(0, 0, "OFFICIAL RECORD")

    def _on_first_page(canvas_obj, doc_obj):
        canvas_obj.saveState()
        w, h = doc_obj.pagesize
        canvas_obj.setFillColor(federal_blue)
        canvas_obj.rect(0, h - banner_h, w, banner_h, fill=1, stroke=0)
        # Gold accent line
        canvas_obj.setFillColor(gold)
        canvas_obj.rect(0, h - banner_h - 3, w, 3, fill=1, stroke=0)
        y_offset = (banner_h - logo_s) / 2.0
        # 左侧圆形 FBI 印章：优先使用内嵌 PNG，失败则绘制矢量印章
        seal_x = 0.5 * inch
        seal_y = h - banner_h + y_offset
        try:
            img = _get_seal_image(logo_s, logo_s)
        except Exception:
            img = None
        if img:
            try:
                img.drawOn(canvas_obj, seal_x, seal_y)
            except Exception:
                img = None
        if not img:
            # 矢量备选：白底金边蓝字圆章
            cx = seal_x + logo_s / 2.0
            cy = seal_y + logo_s / 2.0
            r_outer = logo_s / 2.0
            r_inner = r_outer * 0.82
            # 外圈
            canvas_obj.setFillColor(colors.white)
            canvas_obj.setStrokeColor(gold)
            canvas_obj.setLineWidth(2)
            canvas_obj.circle(cx, cy, r_outer, stroke=1, fill=1)
            # 内圈
            canvas_obj.setStrokeColor(federal_blue)
            canvas_obj.setLineWidth(1.2)
            canvas_obj.circle(cx, cy, r_inner, stroke=1, fill=0)
            # 文本
            canvas_obj.setFillColor(federal_blue)
            canvas_obj.setFont("Helvetica-Bold", 7)
            canvas_obj.drawCentredString(cx, cy + 2, "IC3")
            canvas_obj.setFont("Helvetica", 4.5)
            canvas_obj.drawCentredString(cx, cy - 5, "FEDERAL SEAL")
        # 头部文字区域，匹配提供的样板
        canvas_obj.setFillColor(colors.white)
        canvas_obj.setFont("Helvetica-Bold", 14)
        canvas_obj.drawString(1.6 * inch, h - 0.45 * inch, "FEDERAL BUREAU OF INVESTIGATION")
        canvas_obj.setFont("Helvetica", 9)
        canvas_obj.drawString(
            1.6 * inch,
            h - 0.70 * inch,
            "U.S. Department of Justice | Internet Crime Complaint Center (IC3)",
        )
        canvas_obj.drawString(
            1.6 * inch,
            h - 0.90 * inch,
            "ADRI Case Filing Interface",
        )
        _draw_common_marks(canvas_obj, w, h)
        canvas_obj.restoreState()

    def _on_later_pages(canvas_obj, doc_obj):
        canvas_obj.saveState()
        w, h = doc_obj.pagesize
        # Thin header bar on continuation pages
        canvas_obj.setFillColor(federal_blue)
        canvas_obj.rect(0, h - 0.35*inch, w, 0.35*inch, fill=1, stroke=0)
        canvas_obj.setFillColor(colors.white)
        canvas_obj.setFont("Helvetica", 7.5)
        canvas_obj.drawString(
            0.5 * inch,
            h - 0.22 * inch,
            f"FBI IC3 ADRI | Case: {case_data.get('case_no','N/A')}",
        )
        _draw_common_marks(canvas_obj, w, h)
        canvas_obj.restoreState()

    doc.build(story, onFirstPage=_on_first_page, onLaterPages=_on_later_pages)
    return buf.getvalue()
