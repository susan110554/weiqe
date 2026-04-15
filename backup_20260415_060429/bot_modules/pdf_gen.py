"""
FBI IC3 – ADRI Bot
PDF Generation Engine — Enhanced official case report.
"""
import io, base64 as _b64, hashlib, json, secrets
from datetime import date, datetime, timezone
from decimal import Decimal
from xml.sax.saxutils import escape as _xml_escape

# ── Embedded IC3 Seal (base64 PNG) ────────────────────
IC3_SEAL_B64 = "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"

def _get_seal_image(w, h):
    """
    Return a ReportLab Image for the header seal.
    此处使用 IC3 徽章（去背图），放在原 FBI 徽章位置；FBI 徽章由后端更新 PDF 时使用。
    """
    from reportlab.platypus import Image as RLImage
    import os

    # 1) IC3 徽章（去背 PNG），与脚本同目录或项目根目录
    _dir = os.path.dirname(os.path.abspath(__file__))
    _root = os.path.dirname(_dir)
    for _base in (_dir, _root):
        _path = os.path.join(_base, "ic3_badge.png")
        if os.path.isfile(_path):
            try:
                img = RLImage(_path, width=w, height=h)
                return img
            except Exception:
                pass
            break

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


def generate_pdf_auth_reference(now=None) -> str:
    """
    每次点击生成 PDF 时调用一次。格式 IC3-YYYY-REF-xxxx-xxx（四位数字 + 三位字母数字），
    年份取生成时刻；中间段与尾段含随机量，多次生成几乎必不相同。
    """
    if now is None:
        now = datetime.now(timezone.utc)
    y = now.year
    mid = secrets.randbelow(10000)
    tail = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(3))
    return f"IC3-{y}-REF-{mid:04d}-{tail}"


# 修改 PDF 版式、字体、段落样式、或 STATE-HASH 算法时递增，使 STATE-HASH 反映模板/代码变更
PDF_STATE_HASH_VERSION = "3"


def _sha256_state_hash(case_data: dict, attest_ts: str) -> str:
    """
    STATE-HASH：对完整 case_data（规范 JSON）、attest_ts、PDF_STATE_HASH_VERSION 做 SHA-256。
    不含当次生成的 pdf_auth_ref，故同一案件、同一快照、连点两次下载哈希相同；仅随案件数据与 attest
    及模板版本变化。
    """

    def _json_default(o):
        if isinstance(o, (bytes, bytearray)):
            return o.hex()
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if isinstance(o, Decimal):
            return format(o, "f")
        return str(o)

    payload = json.dumps(case_data, sort_keys=True, ensure_ascii=False, default=_json_default)
    h = hashlib.sha256()
    h.update(PDF_STATE_HASH_VERSION.encode("utf-8"))
    h.update(b"\x1e")
    h.update(attest_ts.encode("utf-8"))
    h.update(b"\x1e")
    h.update(payload.encode("utf-8"))
    return h.hexdigest()


async def generate_case_pdf(
    case_data: dict,
    attest_ts: str,
    auth_id: str | None = None,
    pdf_password: str | None = None,
) -> bytes:
    """
    Generate official IC3 complaint confirmation PDF.
    每次生成会分配唯一的 PDF Auth Reference（IC3-YYYY-REF-xxxx-xxx），用于正文「Auth Reference」、
    签名块「Signer / Auth Ref」及尾页脚注；与传入的 auth_id（若仍由旧代码传入）无关。
    pdf_password：若提供，则使用 PDF 标准 AES-256 加密（需依赖 pyaes），离线打开需输入该口令。
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
    from reportlab.lib.units import inch, cm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                     Table, TableStyle, HRFlowable, Flowable)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    buf = io.BytesIO()
    pdf_auth_ref = generate_pdf_auth_reference()

    pdf_encrypt_obj = None
    if pdf_password:
        from reportlab.lib import pdfencrypt

        pw = pdf_password.encode("utf-8") if isinstance(pdf_password, str) else pdf_password
        pdf_encrypt_obj = pdfencrypt.StandardEncryption(pw, strength=256)
        pdf_encrypt_obj.setAllPermissions(1)

    # ── Color palette ──────────────────────────────────────────
    federal_blue  = colors.HexColor("#002D72")
    header_blue   = colors.Color(13/255.0, 31/255.0, 60/255.0)  # RGB(13,31,60) for all page headers
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
        creator="IC3",
        encrypt=pdf_encrypt_obj,
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
    pki_footer_style = S(
        "PkiFooter",
        fontSize=7.5,
        leading=9,
        textColor=colors.HexColor("#666666"),
        fontName="Helvetica-Oblique",
        alignment=TA_CENTER,
    )
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
    # 抬头在 onFirstPage 绘制；topMargin 已与 banner_h 对齐，勿再加大段 Spacer，否则首屏正文整体被压得过低

    # ── Case Acceptance Banner ─────────────────────────────────
    story.append(Paragraph("Official Complaint Receipt Confirmation", accept_style))

    # ── Case ID + Dynamic Status Box ──────────────────────────
    case_id = case_data.get("case_no", "N/A")
    _status_map = {
        "SUBMITTED":    ("SUBMITTED / PENDING REVIEW",               colors.HexColor("#276749")),
        "VALIDATING":   ("VALIDATING — AUTO-CHECK IN PROGRESS", colors.HexColor("#2B6CB0")),
        "UNDER REVIEW": ("UNDER REVIEW — AGENT ASSIGNED",       colors.HexColor("#553C9A")),
        "REFERRED":     ("REFERRED — TRANSFERRED TO FIELD OFFICE", colors.HexColor("#276749")),
        "CLOSED":       ("ACTIONED / CLOSED — ARCHIVED",        colors.HexColor("#1A202C")),
    }
    raw_status = case_data.get("status", "SUBMITTED")
    if case_data.get("pdf_status_label"):
        status_label = str(case_data["pdf_status_label"])
        hex_c = case_data.get("pdf_status_color_hex")
        try:
            status_color = colors.HexColor(hex_c) if hex_c else green_ok
        except Exception:
            status_color = green_ok
    else:
        status_label, status_color = _status_map.get(raw_status, (raw_status, green_ok))

    _dyn_status_style = ParagraphStyle("DynStatus", parent=styles["Normal"],
        fontSize=10, textColor=status_color,
        fontName="Helvetica-Bold", alignment=TA_CENTER)

    last_updated = case_data.get("last_updated", case_data.get("registered", attest_ts))
    agent_code   = case_data.get("agent_code", "N/A")

    _pdf_sha = _sha256_state_hash(case_data, attest_ts)

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

    ppt = (case_data.get("processing_pipeline_text") or "").strip()
    if ppt:
        story.append(Spacer(1, 6))
        body_xml = _xml_escape(ppt).replace("\n", "<br/>")
        story.append(Paragraph(body_xml, field_label))
        story.append(Spacer(1, 10))

    # ── Registration metadata ──────────────────────────────────
    def _uid_fmt(uid):
        """Convert raw Telegram UID to internal format e.g. 7628140504 → USR-76281."""
        try:
            s = str(uid or "").strip()
            if not s or s in ("N/A", "—", "Unknown"):
                return "N/A"
            digits = "".join(c for c in s if c.isdigit())
            if len(digits) >= 5:
                return f"USR-{digits[:5]}"
            return f"USR-{digits}" if digits else "N/A"
        except Exception:
            return "N/A"

    _agent_line = agent_code if agent_code != "N/A" else "Not yet assigned"
    reg_rows = [
        ["Registered:",        case_data.get("registered", "N/A")],
        ["Auth Reference:",    pdf_auth_ref],
        ["Legal Attestation:", attest_ts],
        ["Complainant UID:",   _uid_fmt(case_data.get("uid"))],
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

    def _val(v):
        """Display value or 'Not Provided' for empty/placeholder."""
        s = str(v or "").strip()
        if not s or s in ("—", "-", "Unknown", "CURRENCY"):
            return "Not Provided"
        return s

    def _filled(v) -> bool:
        """用户未填写或为占位符时不输出该行（PDF 中不显示标签与值）。"""
        if v is None:
            return False
        s = str(v).strip()
        if not s:
            return False
        if s in ("—", "-", "–", "―", "…"):
            return False
        sl = s.lower()
        if "not provided" in sl:
            return False
        if sl in (
            "unknown",
            "n/a",
            "na",
            "none",
            "null",
            "not specified",
            "currency",
        ):
            return False
        # 与 _val() 显示为 Not Provided 的输入一致时跳过
        try:
            if str(_val(v)).strip().lower() == "not provided":
                return False
        except Exception:
            pass
        return True

    def _mask_acct(v):
        """Mask account number to last 4 digits e.g. ****4654."""
        s = (v or "").strip()
        if not s or s in ("—", "-", "Unknown"):
            return "Not Provided"
        if s.startswith("****"):  # already masked
            return s
        if len(s) >= 4:
            return f"****{s[-4:]}"
        return "****"

    def _para_value_text(v):
        """Preserve multi-line values in PDF tables."""
        s = str(_val(v))
        if not s:
            return s
        # Escape user text first, then convert line breaks for ReportLab Paragraph.
        return _xml_escape(s).replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br/>")

    def field_row(label, value):
        return [Paragraph(_xml_escape(str(label)), field_label),
                Paragraph(_para_value_text(value), field_value)]

    def _rows_from_pairs(pairs):
        """pairs: (label, raw_value)；仅包含有实质内容的行。"""
        rows = []
        for label, raw in pairs:
            if not _filled(raw):
                continue
            rows.append(field_row(label, raw))
        return rows

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

    # ── CRS-01: Complainant Information（固定字段模板）──────────────
    crs01_rows = [
        field_row("Full Legal Name", case_data.get("fullname")),
        field_row("Age", case_data.get("dob") or case_data.get("age")),
        field_row("Physical Address", case_data.get("address")),
        field_row("Contact Number", case_data.get("phone")),
        field_row("Email Address", case_data.get("email")),
    ]
    if crs01_rows:
        story.extend(section("CRS-01 · Complainant Information"))
        story.append(data_table(crs01_rows))
        story.append(Spacer(1, 6))

    # ── CRS-02: Transaction Data ─────────────────────────────────
    import re

    def _tx1_label_pdf(tx1_type: str) -> str:
        m = {
            "CASH": "Cash",
            "CHECK": "Check/Cashier's Check",
            "MONEY_ORDER": "Money Order",
            "CRYPTO": "Cryptocurrency/Crypto ATM",
            "WIRE": "Wire Transfer",
            "OTHER": "Other",
        }
        return m.get((tx1_type or "").upper(), tx1_type or "Transaction")

    def _tx_dict_nonempty(tx: dict) -> bool:
        if not tx or not isinstance(tx, dict):
            return False
        for v in tx.values():
            if v is None:
                continue
            s = str(v).strip()
            if s and s not in ("—", "-"):
                return True
        return False

    def _append_yn(rows_inner, label, val):
        if val is True:
            rows_inner.append(field_row(label, "Yes"))
        elif val is False:
            rows_inner.append(field_row(label, "No"))
        else:
            rows_inner.append(field_row(label, "Not Provided"))

    def _add_pairs(rows_inner, txd, pairs):
        for lab, key in pairs:
            rows_inner.append(field_row(lab, txd.get(key)))

    def _pdf_rows_one_tx(tx: dict):
        rows = []
        ttype = (tx.get("tx1_type") or "").upper()
        lbl = _tx1_label_pdf(tx.get("tx1_type"))

        if ttype == "CRYPTO":
            rows.append(field_row("Transaction Type", lbl))
            _append_yn(rows, "Money Sent/Lost", tx.get("tx1_sent_lost"))
            amt = tx.get("tx1_amount") or tx.get("tx1_crypto_amount")
            rows.append(field_row("Amount (USD)", amt))
            dt = tx.get("tx1_date") or tx.get("tx1_crypto_date")
            rows.append(field_row("Incident Date", dt))
            _append_yn(rows, "Bank Contacted", tx.get("tx1_crypto_bank_contacted"))
            cur = tx.get("tx1_crypto_currency")
            rows.append(field_row("Asset Type", cur))
            th = tx.get("tx1_crypto_txhash")
            disp = "[Screenshot Uploaded — Forensic hash retained]" if (th and str(th).startswith("file:")) else th
            rows.append(field_row("TXID / Hash", disp))
            ow = tx.get("tx1_crypto_orig_wallet")
            rows.append(field_row("Victim (Originating) Wallet", ow))
            rw = tx.get("tx1_crypto_recip_wallet")
            rows.append(field_row("Suspect (Recipient) Wallet", rw))
            _add_pairs(rows, tx, [
                ("ATM/Kiosk Name", "tx1_crypto_atm_name"),
                ("ATM/Kiosk Address", "tx1_crypto_atm_address"),
                ("ATM/Kiosk City", "tx1_crypto_atm_city"),
                ("ATM/Kiosk Country", "tx1_crypto_atm_country"),
                ("ATM/Kiosk State", "tx1_crypto_atm_state"),
                ("ATM/Kiosk Zip", "tx1_crypto_atm_zip"),
            ])
            return rows

        rows.append(field_row("Transaction Type", lbl))
        _append_yn(rows, "Money Sent/Lost", tx.get("tx1_sent_lost"))
        amt = tx.get("tx1_amount")
        dt = tx.get("tx1_date")
        if ttype == "OTHER":
            cur = (tx.get("tx1_currency") or "USD").strip()
            amt_s = str(amt or "").strip()
            rows.append(field_row("Amount", f"{amt_s} {cur}".strip()))
        else:
            rows.append(field_row("Amount (USD)", amt))
        rows.append(field_row("Date", dt))

        if ttype == "CASH":
            _append_yn(rows, "Bank Contacted", tx.get("tx1_cash_bank_contacted"))
            _add_pairs(rows, tx, [
                ("Recipient Address", "tx1_cash_recipient_addr1"),
                ("Recipient Address (cont.)", "tx1_cash_recipient_addr2"),
                ("Suite/Mail Stop", "tx1_cash_recipient_suite"),
                ("City", "tx1_cash_recipient_city"),
                ("Country", "tx1_cash_recipient_country"),
                ("State", "tx1_cash_recipient_state"),
                ("Zip/Route", "tx1_cash_recipient_zip"),
            ])
            return rows

        if ttype == "CHECK":
            _append_yn(rows, "Bank Contacted", tx.get("tx1_check_bank_contacted"))
            _add_pairs(rows, tx, [
                ("Originating Bank Name", "tx1_check_orig_bank_name"),
                ("Originating Bank City", "tx1_check_orig_bank_city"),
                ("Originating Bank Country", "tx1_check_orig_bank_country"),
                ("Originating Name on Account", "tx1_check_orig_name_on_acct"),
                ("Originating Account Number", "tx1_check_orig_account_no"),
            ])
            _add_pairs(rows, tx, [
                ("Recipient Bank Name", "tx1_check_recip_bank_name"),
                ("Recipient Bank City", "tx1_check_recip_bank_city"),
                ("Recipient Bank Country", "tx1_check_recip_bank_country"),
                ("Recipient Name on Account", "tx1_check_recip_name_on_acct"),
                ("Recipient Account Number", "tx1_check_recip_account_no"),
                ("Recipient Routing Number", "tx1_check_recip_routing_no"),
                ("Recipient SWIFT Code", "tx1_check_recip_swift"),
            ])
            return rows

        if ttype == "MONEY_ORDER":
            _append_yn(rows, "Bank Contacted", tx.get("tx1_mo_bank_contacted"))
            _add_pairs(rows, tx, [
                ("Originating Bank Name", "tx1_mo_orig_bank_name"),
                ("Originating Bank Address", "tx1_mo_orig_bank_address"),
                ("Originating Bank City", "tx1_mo_orig_bank_city"),
                ("Originating Bank Country", "tx1_mo_orig_bank_country"),
                ("Originating Bank State", "tx1_mo_orig_bank_state"),
                ("Originating Name on Account", "tx1_mo_orig_name_on_acct"),
                ("Originating Account Number", "tx1_mo_orig_account_no"),
            ])
            _add_pairs(rows, tx, [
                ("Recipient Bank Name", "tx1_mo_recip_bank_name"),
                ("Recipient Bank Address", "tx1_mo_recip_bank_address"),
                ("Recipient Bank City", "tx1_mo_recip_bank_city"),
                ("Recipient Bank Country", "tx1_mo_recip_bank_country"),
                ("Recipient Bank State", "tx1_mo_recip_bank_state"),
                ("Recipient Name on Account", "tx1_mo_recip_name_on_acct"),
                ("Recipient Account Number", "tx1_mo_recip_account_no"),
                ("Recipient Routing Number", "tx1_mo_recip_routing_no"),
                ("Recipient SWIFT Code", "tx1_mo_recip_swift"),
            ])
            return rows

        if ttype == "WIRE":
            _append_yn(rows, "Bank Contacted", tx.get("tx1_wire_bank_contacted"))
            _add_pairs(rows, tx, [
                ("Originating Bank Name", "tx1_wire_orig_bank_name"),
                ("Originating Bank Address", "tx1_wire_orig_bank_address"),
                ("Originating Bank City", "tx1_wire_orig_bank_city"),
                ("Originating Bank Country", "tx1_wire_orig_bank_country"),
                ("Originating Bank State", "tx1_wire_orig_bank_state"),
                ("Originating Name on Account", "tx1_wire_orig_name_on_acct"),
            ])
            _add_pairs(rows, tx, [
                ("Recipient Bank Name", "tx1_wire_recip_bank_name"),
                ("Recipient Bank Address", "tx1_wire_recip_bank_address"),
                ("Recipient Bank City", "tx1_wire_recip_bank_city"),
                ("Recipient Bank Country", "tx1_wire_recip_bank_country"),
                ("Recipient Bank State", "tx1_wire_recip_bank_state"),
                ("Recipient Name on Account", "tx1_wire_recip_name_on_acct"),
                ("Recipient Routing Number", "tx1_wire_recip_routing_no"),
                ("Recipient Account Number", "tx1_wire_recip_account_no"),
                ("Recipient SWIFT Code", "tx1_wire_recip_swift"),
            ])
            return rows

        if ttype == "OTHER":
            _append_yn(rows, "Bank Contacted", tx.get("tx1_other_bank_contacted"))
            sp = tx.get("tx1_other_specify")
            rows.append(field_row("Specified Type", sp))
            cur = tx.get("tx1_currency")
            rows.append(field_row("Currency", cur))
            _add_pairs(rows, tx, [
                ("Originating Bank Name", "tx1_other_orig_bank_name"),
                ("Originating Bank Address", "tx1_other_orig_bank_address"),
                ("Originating Bank City", "tx1_other_orig_bank_city"),
                ("Originating Bank Country", "tx1_other_orig_bank_country"),
                ("Originating Bank State", "tx1_other_orig_bank_state"),
                ("Originating Name on Account", "tx1_other_orig_name_on_acct"),
            ])
            _add_pairs(rows, tx, [
                ("Recipient Bank Name", "tx1_other_recip_bank_name"),
                ("Recipient Bank Address", "tx1_other_recip_bank_address"),
                ("Recipient Bank City", "tx1_other_recip_bank_city"),
                ("Recipient Bank Country", "tx1_other_recip_bank_country"),
                ("Recipient Bank State", "tx1_other_recip_bank_state"),
                ("Recipient Name on Account", "tx1_other_recip_name_on_acct"),
                ("Recipient Routing Number", "tx1_other_recip_routing_no"),
                ("Recipient Account Number", "tx1_other_recip_account_no"),
                ("Recipient SWIFT Code", "tx1_other_recip_swift"),
            ])
            return rows

        return rows

    tx_data_raw = case_data.get("tx_data")
    if isinstance(tx_data_raw, str):
        try:
            tx_data_parsed = json.loads(tx_data_raw)
        except Exception:
            tx_data_parsed = None
    elif isinstance(tx_data_raw, dict):
        tx_data_parsed = tx_data_raw
    else:
        tx_data_parsed = None

    tx_count_cd = int(case_data.get("tx_count") or 1)
    crs02_total_loss_v = case_data.get("crs02_total_loss")
    use_multi = bool(tx_data_parsed) and len(tx_data_parsed) > 0

    is_bank = (case_data.get("transaction_type") == "bank")
    has_crypto_in_multi = False
    if use_multi:
        for v in tx_data_parsed.values():
            if isinstance(v, dict) and (v.get("tx1_type") or "").upper() == "CRYPTO":
                has_crypto_in_multi = True
                break

    section_note = (
        "⚠ All wallet addresses and transaction hashes are cross-referenced against IC3 blockchain trace database."
        if (has_crypto_in_multi if use_multi else (not is_bank))
        else None
    )

    crs02_rows = []
    crs02_has_content = False

    if use_multi:
        loss_rows = []
        if _filled(crs02_total_loss_v):
            loss_rows.append(
                field_row("Total Loss Amount", f"{str(crs02_total_loss_v).strip()} USD")
            )
        idx_keys = []
        for k in tx_data_parsed.keys():
            try:
                idx_keys.append(int(k))
            except (TypeError, ValueError):
                try:
                    idx_keys.append(int(str(k)))
                except Exception:
                    continue
        idx_keys = sorted(set(idx_keys)) if idx_keys else list(range(1, tx_count_cd + 1))

        tx_blocks = []
        for n in idx_keys:
            tx = tx_data_parsed.get(n) or tx_data_parsed.get(str(n))
            if not isinstance(tx, dict) or not _tx_dict_nonempty(tx):
                continue
            pr = _pdf_rows_one_tx(tx)
            if pr:
                tx_blocks.append((n, tx, pr))

        if loss_rows or tx_blocks:
            story.extend(section(
                "CRS-02  |  Transaction Data",
                note=section_note,
            ))
            crs02_has_content = True
            if loss_rows:
                story.append(data_table(loss_rows))
                story.append(Spacer(1, 6))
            for n, tx, pr in tx_blocks:
                ttl = _tx1_label_pdf(tx.get("tx1_type"))
                title_txt = f"Transaction #{n} — {ttl}"
                story.append(Paragraph(f"<b>{title_txt}</b>", section_style))
                story.append(Spacer(1, 3))
                story.append(data_table(pr))
                story.append(Spacer(1, 8))
            story.append(Spacer(1, 2))
    else:
        tx_hash_raw = case_data.get("tx_hash") or case_data.get("txid")
        txid = case_data.get("tx_hash") or case_data.get("txid") or "—"
        if str(txid).startswith("file:"):
            txid = "[Screenshot Uploaded — Forensic hash retained]"

        raw_amount = case_data.get("amount", "—")
        coin_code = (
            case_data.get("fin_currency") or
            case_data.get("crypto_currency") or
            case_data.get("coin", "") or
            ""
        ).strip().upper()
        if not coin_code or coin_code == "CURRENCY":
            coin_code = _val(case_data.get("coin"))
        formatted_amount = raw_amount
        try:
            from decimal import Decimal, ROUND_DOWN
            amt_dec = Decimal(str(raw_amount))
            if coin_code in ("USDT", "USDC"):
                q = Decimal("0.01")
            elif coin_code in ("BTC", "ETH"):
                q = Decimal("0.00000001")
            else:
                q = Decimal("0.0001")
            formatted_amount = str(amt_dec.quantize(q, rounding=ROUND_DOWN))
        except Exception:
            formatted_amount = raw_amount

        if _filled(crs02_total_loss_v):
            crs02_rows.append(
                field_row("Total Loss Amount", f"{str(crs02_total_loss_v).strip()} USD")
            )
        has_disputed = (
            _filled(case_data.get("amount"))
            or _filled(case_data.get("coin"))
            or _filled(case_data.get("crypto_currency"))
            or _filled(case_data.get("fin_currency"))
        )
        if has_disputed:
            crs02_rows.append(
                field_row("Disputed Assets", f"{formatted_amount} {coin_code}".strip())
            )
        if _filled(case_data.get("incident_time")):
            crs02_rows.append(field_row("Incident Date/Time", case_data.get("incident_time")))
        if is_bank:
            if _filled(case_data.get("vic_bank")):
                crs02_rows.append(field_row("Victim Bank", case_data.get("vic_bank")))
            v_acct_raw = case_data.get("vic_acct") or case_data.get("crs02a_vic_account_no")
            if _filled(v_acct_raw):
                crs02_rows.append(field_row("Victim Account", _mask_acct(v_acct_raw)))
            if _filled(case_data.get("sub_name")):
                crs02_rows.append(field_row("Subject Full Name", case_data.get("sub_name")))
            if _filled(case_data.get("sub_bank")):
                crs02_rows.append(field_row("Subject Bank", case_data.get("sub_bank")))
            s_acct_raw = case_data.get("sub_acct") or case_data.get("crs02a_com_account_no")
            if _filled(s_acct_raw):
                crs02_rows.append(field_row("Subject Account", _mask_acct(s_acct_raw)))
        else:
            if _filled(tx_hash_raw) or (tx_hash_raw and str(tx_hash_raw).startswith("file:")):
                crs02_rows.append(field_row("Transaction Hash", txid))
            if _filled(case_data.get("victim_wallet")):
                crs02_rows.append(
                    field_row("Victim Wallet Addr", case_data.get("victim_wallet"))
                )
            if _filled(case_data.get("wallet_addr")):
                crs02_rows.append(
                    field_row("Suspect Wallet Addr", case_data.get("wallet_addr"))
                )
            chain = case_data.get("chain_type", "—")
            victim_w = case_data.get("victim_wallet", "—")
            if chain in ("—", "Unknown", None, ""):
                if victim_w and re.match(r"^0x[0-9a-fA-F]{40}$", str(victim_w)):
                    chain = "ERC-20 / BSC (Ethereum)"
                elif victim_w and re.match(r"^T[A-Za-z0-9]{33}$", str(victim_w)):
                    chain = "TRC-20 (TRON)"
                elif victim_w and re.match(r"^(1|3|bc1)[A-Za-z0-9]{25,62}$", str(victim_w)):
                    chain = "Bitcoin Network"
            if _filled(chain):
                crs02_rows.append(field_row("Blockchain Network", chain))

        if crs02_rows:
            story.extend(section(
                "CRS-02  |  Transaction Data",
                note=section_note,
            ))
            story.append(data_table(crs02_rows))
            story.append(Spacer(1, 6))
            crs02_has_content = True

    # ── Blockchain Trace Analysis Note（仅加密货币案件）────────────────
    suspect_w = case_data.get("wallet_addr", "—")
    show_trace_crypto = has_crypto_in_multi if use_multi else (not is_bank)
    if (
        crs02_has_content
        and show_trace_crypto
        and suspect_w
        and suspect_w not in ("—", "Unknown", "", "Bank / Wire")
    ):
        trace_box = Table([[Paragraph(
            f"🔍 <b>BLOCKCHAIN TRACE INITIATED</b><br/>"
            f"Suspect wallet <b>{str(suspect_w)[:20]}...</b> has been flagged for "
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

    # ── CRS-03: Subject Identification（固定字段模板）──────────────
    crs03_rows = [
        field_row("Subject Contact Name", case_data.get("crs03_subject_name")),
        field_row("Subject Phone", case_data.get("crs03_subject_phone")),
        field_row("Subject Email", case_data.get("crs03_subject_email")),
        field_row("Subject Address", case_data.get("crs03_subject_address")),
        field_row("Subject City", case_data.get("crs03_subject_city")),
        field_row("Subject Country", case_data.get("crs03_subject_country")),
        field_row("Contact Info / Platform", case_data.get("platform")),
        field_row("Profile URL", case_data.get("profile_url")),
        field_row("Crime Type", case_data.get("crime_type")),
    ]
    if crs03_rows:
        story.extend(section("CRS-03  |  Subject Identification"))
        story.append(data_table(crs03_rows))
        story.append(Spacer(1, 10))

    # ── CRS-04: Other Information（固定字段、统一排版）────────
    # 要求：无论是否填写，都保持同一组字段行；填写后仅替换右侧值。
    prior_detail_map = {}
    detail_text = str(case_data.get("prior_reports") or "")
    for line in detail_text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        k, v = line.split(":", 1)
        prior_detail_map[k.strip().lower()] = v.strip()

    def _prior_val(key_name: str, fallback_key: str):
        v = case_data.get(fallback_key)
        if _filled(v):
            return v
        return prior_detail_map.get(key_name.lower(), "")

    crs04_rows = [
        field_row("Incident Narrative", case_data.get("incident_story")),
        field_row("Prior Reports to Agencies", case_data.get("prior_reports_flag")),
        field_row("Agency Name", _prior_val("Agency Name", "crs04_prior_agency_name")),
        field_row("Phone Number", _prior_val("Phone Number", "crs04_prior_phone")),
        field_row("Email Address", _prior_val("Email Address", "crs04_prior_email")),
        field_row("Date Reported", _prior_val("Date Reported", "crs04_prior_date_reported")),
        field_row("Report Number", _prior_val("Report Number", "crs04_prior_report_number")),
    ]

    # Witnesses: render as structured rows (aligned labels), not one multi-line blob.
    w_list = case_data.get("crs04_witnesses_list")
    if isinstance(w_list, list) and w_list:
        for i, w in enumerate(w_list, 1):
            ww = w if isinstance(w, dict) else {}
            crs04_rows.extend([
                field_row(f"Witness #{i} Name", ww.get("name")),
                field_row(f"Witness #{i} Phone Number", ww.get("phone")),
                field_row(f"Witness #{i} Email Address", ww.get("email")),
                field_row(f"Witness #{i} Relation", ww.get("relation")),
            ])
    else:
        # Legacy compatibility: parse flattened witnesses text if present.
        w_txt = str(case_data.get("witnesses") or "").strip()
        if w_txt and w_txt.lower() != "no witnesses provided (skipped).":
            cur_idx = None
            for line in w_txt.splitlines():
                ln = line.strip()
                if not ln:
                    continue
                if ln.lower().startswith("witness #"):
                    cur_idx = ln.replace("Witness", "Witness").strip()
                    continue
                if ":" in ln and cur_idx:
                    k, v = ln.split(":", 1)
                    crs04_rows.append(field_row(f"{cur_idx} {k.strip()}", v.strip()))
        else:
            crs04_rows.append(field_row("Witnesses & Others", case_data.get("witnesses")))
    if crs04_rows:
        story.extend(section("CRS-04  |  Other Information"))
        story.append(data_table(crs04_rows))
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
         Paragraph(f"IC3 Automated Certification System | Auth Ref: {pdf_auth_ref}", digsig_val)],
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

    # ── Page decorations ──────────────────────────────────────
    banner_h = 1.2 * inch
    logo_s   = 0.8 * inch
    # 尾页 FBI 深蓝条：高度 3cm；背景满铺纸宽；徽章/FBI 距纸张左缘见下方常量；条内垂直居中
    fbi_bar_h = 3 * cm
    fbi_seal_from_paper = 1.4 * cm   # 徽章左缘距纸张 x=0
    fbi_word_from_paper = 4 * cm     # 「FBI」左缘距纸张 x=0
    fbi_sub_gap = 0.2 * cm           # 副标题相对 FBI 字块右缘
    fbi_word_pt = 72
    # 满铺条左缘：须与 drawOn 里 translate 的 x 一致（含 Frame 默认 leftPadding 等），不能仅用 doc.leftMargin
    _fbi_page_w = doc.pagesize[0]
    _fbi_bleed_fallback = doc.leftMargin + 6  # SimpleDocTemplate 默认 Frame 的 leftPadding=6pt

    def _draw_tracked_text(canvas_obj, text: str, x: float, y: float, font_name: str, font_size: float, tracking_pt: float):
        """
        以“字间距 tracking_pt(点)”绘制文本（ReportLab 无原生 tracking，按字符推进模拟）。
        tracking_pt 可为负（紧缩）或正（拉宽）。
        """
        canvas_obj.setFont(font_name, font_size)
        cur_x = x
        for ch in text:
            canvas_obj.drawString(cur_x, y, ch)
            cur_x += canvas_obj.stringWidth(ch, font_name, font_size) + tracking_pt
        return cur_x

    def _get_footer_seal_image():
        """尾页 FBI 条徽章：优先项目根目录 fbi_footer_seal.png，否则 ic3_seal.png / 圆形徽章.png。"""
        from reportlab.platypus import Image as RLImage
        import os

        _dir = os.path.dirname(os.path.abspath(__file__))
        _root = os.path.dirname(_dir)
        candidates = [
            os.path.join(_root, "fbi_footer_seal.png"),
            os.path.join(_root, "ic3_seal.png"),
            os.path.join(_root, "圆形徽章.png"),
        ]
        for p in candidates:
            try:
                if os.path.isfile(p):
                    return RLImage(p)
            except Exception:
                continue
        return None

    def _draw_common_marks(canvas_obj, w, h):
        canvas_obj.setFont("Helvetica-Bold", 8)
        canvas_obj.setFillColor(colors.black)
        canvas_obj.drawCentredString(w / 2.0, h - 0.15 * inch, "SENSITIVE BUT UNCLASSIFIED")
        canvas_obj.drawCentredString(w / 2.0, 0.35 * inch, "SENSITIVE BUT UNCLASSIFIED")

    def _draw_footer_bar(canvas_obj, bar_h, bleed_left_page):
        """
        尾页 FBI 深蓝条：高 bar_h（默认 3cm）。
        bleed_left_page：纸张坐标下本 flowable 左下角 x（与 translate 一致），背景从 rect(-bleed_left_page,...) 铺满至 x=0。
        背景 RGB(13,31,60) 宽 _fbi_page_w；徽章/文字仍在 flowable 局部坐标内。
        """
        canvas_obj.saveState()
        canvas_obj.setFillColor(header_blue)
        canvas_obj.rect(-bleed_left_page, 0, _fbi_page_w, bar_h, fill=1, stroke=0)

        seal_size = min(0.78 * inch, bar_h * 0.88)
        seal_x = fbi_seal_from_paper - bleed_left_page
        seal_y = (bar_h - seal_size) / 2.0
        img = None
        try:
            img = _get_footer_seal_image()
        except Exception:
            img = None
        if img:
            try:
                img.drawWidth = seal_size
                img.drawHeight = seal_size
                img.drawOn(canvas_obj, seal_x, seal_y)
            except Exception:
                img = None

        canvas_obj.setFillColor(colors.white)
        fbi_x = fbi_word_from_paper - bleed_left_page
        # 大写无降部：基线使字形视觉中心约在条高一半处
        baseline_fbi = bar_h * 0.5 - 0.36 * fbi_word_pt
        end_fbi = _draw_tracked_text(
            canvas_obj,
            "FBI",
            fbi_x,
            baseline_fbi,
            "Helvetica-Bold",
            fbi_word_pt,
            -2.8,
        )
        sub_x = end_fbi + fbi_sub_gap
        sub_pt = 14
        # 两行副标题在条内垂直居中（基线关于条高中线对称）
        sub_upper = bar_h * 0.5 + 8.5
        sub_lower = bar_h * 0.5 - 8.5
        _draw_tracked_text(
            canvas_obj,
            "FEDERAL BUREAU OF",
            sub_x,
            sub_upper,
            "Helvetica",
            sub_pt,
            1.8,
        )
        _draw_tracked_text(
            canvas_obj,
            "INVESTIGATION",
            sub_x,
            sub_lower,
            "Helvetica",
            sub_pt,
            1.8,
        )

        canvas_obj.restoreState()

    class FBIBannerFlowable(Flowable):
        """FIPS 段落下 0.4cm 后插入 FBI 横幅（仅出现在正文末尾，不再每页页脚绘制）。"""

        def __init__(self, bar_w):
            self.bar_w = bar_w
            self.height = fbi_bar_h
            self.width = bar_w

        def drawOn(self, canvas, x, y, _sW=0):
            # 与 Flowable.drawOn 相同，但记录 translate 所用的 x（纸张坐标），供满铺条从 x=0 画起
            x = self._hAlignAdjust(x, _sW)
            self._bleed_x_page = x
            canvas.saveState()
            canvas.translate(x, y)
            self._drawOn(canvas)
            if hasattr(self, "_showBoundary") and self._showBoundary:
                canvas.setStrokeColor(colors.gray)
                canvas.rect(0, 0, self.width, self.height)
            canvas.restoreState()

        def draw(self):
            bleed = getattr(self, "_bleed_x_page", None)
            if bleed is None:
                bleed = _fbi_bleed_fallback
            _draw_footer_bar(self.canv, fbi_bar_h, bleed)

    story.append(Spacer(1, 0.4 * cm))
    story.append(FBIBannerFlowable(7 * inch))

    story.append(Spacer(1, 0.2 * cm))
    story.append(
        HRFlowable(
            width="100%",
            thickness=0.35,
            color=colors.HexColor("#D8D8D8"),
            spaceBefore=0,
            spaceAfter=0,
        )
    )
    story.append(Spacer(1, 0.1 * cm))
    story.append(
        Paragraph(
            "Digitally signed via U.S. Government Publishing Office PKI · IC3 | "
            f"Auth Ref: {pdf_auth_ref} | fbi.gov",
            pki_footer_style,
        )
    )

    def _on_first_page(canvas_obj, doc_obj):
        canvas_obj.saveState()
        w, h = doc_obj.pagesize
        canvas_obj.setFillColor(header_blue)
        canvas_obj.rect(0, h - banner_h, w, banner_h, fill=1, stroke=0)

        # FBI seal: left side, 40px from left, vertically centered in banner
        seal_size = 0.9 * inch
        seal_x = 40 / 72.0 * inch  # 40px from left edge
        seal_y = h - banner_h + (banner_h - seal_size) / 2.0
        try:
            img = _get_seal_image(seal_size, seal_size)
        except Exception:
            img = None
        if img:
            try:
                img.drawOn(canvas_obj, seal_x, seal_y)
            except Exception:
                img = None
        if not img:
            cx = seal_x + seal_size / 2.0
            cy = seal_y + seal_size / 2.0
            r_outer = seal_size / 2.0
            r_inner = r_outer * 0.82
            canvas_obj.setFillColor(colors.white)
            canvas_obj.setStrokeColor(gold)
            canvas_obj.setLineWidth(2)
            canvas_obj.circle(cx, cy, r_outer, stroke=1, fill=1)
            canvas_obj.setStrokeColor(federal_blue)
            canvas_obj.setLineWidth(1.2)
            canvas_obj.circle(cx, cy, r_inner, stroke=1, fill=0)
            canvas_obj.setFillColor(federal_blue)
            canvas_obj.setFont("Helvetica-Bold", 7)
            canvas_obj.drawCentredString(cx, cy + 2, "IC3")
            canvas_obj.setFont("Helvetica", 4.5)
            canvas_obj.drawCentredString(cx, cy - 5, "FEDERAL SEAL")

        # Text block: vertically centered in header banner
        text_y_base = h - banner_h + banner_h / 2.0 - 0.15 * inch
        canvas_obj.setFillColor(colors.white)
        canvas_obj.setFont("Helvetica-Bold", 12)
        canvas_obj.drawCentredString(w / 2.0, text_y_base + 0.22 * inch,
                                     "INTERNET CRIME COMPLAINT CENTER")
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.drawCentredString(w / 2.0, text_y_base + 0.08 * inch,
                                     "A Division of the Federal Bureau of Investigation")
        canvas_obj.setFont("Helvetica", 7.5)
        canvas_obj.drawCentredString(w / 2.0, text_y_base - 0.04 * inch,
                                     "U.S. Department of Justice")

        _draw_common_marks(canvas_obj, w, h)
        canvas_obj.restoreState()

    def _on_later_pages(canvas_obj, doc_obj):
        canvas_obj.saveState()
        w, h = doc_obj.pagesize
        # Thin header bar on continuation pages
        canvas_obj.setFillColor(header_blue)
        canvas_obj.rect(0, h - 0.35*inch, w, 0.35*inch, fill=1, stroke=0)
        canvas_obj.setFillColor(colors.white)
        canvas_obj.setFont("Helvetica", 7.5)
        canvas_obj.drawString(
            0.5 * inch,
            h - 0.22 * inch,
            f"IC3 | Case: {case_data.get('case_no','N/A')}",
        )
        _draw_common_marks(canvas_obj, w, h)
        canvas_obj.restoreState()

    doc.build(story, onFirstPage=_on_first_page, onLaterPages=_on_later_pages)
    return buf.getvalue()


async def generate_org_report_pdf(auth_id: str) -> bytes:
    """
    Generate an FBI CID-style annual operational overview PDF used by
    [Download Annual Report] under ORG-01.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.9 * inch,
        rightMargin=0.9 * inch,
        topMargin=1.1 * inch,
        bottomMargin=1.0 * inch,
        title="FBI Criminal Investigative Division — Annual Operational Report",
        author="Federal Bureau of Investigation",
        subject="CID Annual Operational Overview",
        creator="IC3",
    )

    styles = getSampleStyleSheet()

    def S(name, **kw):
        base = kw.pop("parent", styles["Normal"])
        return ParagraphStyle(name, parent=base, **kw)

    title_style = S(
        "OrgTitle",
        fontSize=14,
        leading=18,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1A202C"),
        spaceAfter=6,
    )
    subtitle_style = S(
        "OrgSub",
        fontSize=9,
        leading=12,
        fontName="Helvetica",
        alignment=TA_CENTER,
        textColor=colors.HexColor("#4A5568"),
        spaceAfter=14,
    )
    section_style = S(
        "OrgSection",
        fontSize=11,
        leading=14,
        fontName="Helvetica-Bold",
        alignment=TA_LEFT,
        textColor=colors.HexColor("#002D72"),
        spaceBefore=12,
        spaceAfter=4,
    )
    body_style = S(
        "OrgBody",
        fontSize=9,
        leading=13,
        fontName="Helvetica",
        alignment=TA_LEFT,
        textColor=colors.HexColor("#1A202C"),
    )

    story = []

    # Title block
    story.append(Paragraph("ORGANIZATIONAL OVERVIEW — FBI CRIMINAL INVESTIGATIVE DIVISION", title_style))
    story.append(
        Paragraph(
            "Annual Operational Overview (FY 2024)  •  Authorization Reference: "
            f"<code>{auth_id}</code>",
            subtitle_style,
        )
    )

    def section(title: str):
        story.append(Paragraph(title, section_style))
        story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#CBD5E0"), spaceAfter=4))

    # Structure & Mission
    section("Structure & Mission")
    story.append(
        Paragraph(
            "The FBI Criminal Investigative Division (CID) is the primary operational unit "
            "responsible for coordinating federal criminal investigations, legal proceedings, "
            "and interagency referrals across all 94 U.S. Attorney's Districts.",
            body_style,
        )
    )

    # Executive leadership
    section("Executive Leadership")
    story.append(
        Paragraph(
            "• Director, Federal Bureau of Investigation: Kash Patel (Presidential Appointee)<br/>"
            "• Attorney General: Pam Bondi (U.S. Department of Justice)<br/>"
            "• Assistant Director, CID: Senate-confirmed executive responsible for nationwide CID operations.",
            body_style,
        )
    )

    # Operational branches
    section("Operational Branches")
    story.append(
        Paragraph(
            "• Violent Crime &amp; Major Offenses Section (VCMOS) — Handles 47,000+ cases annually.<br/>"
            "• Financial Crimes Section (FCS) — Manages complex fraud, cyber-enabled theft, and virtual-asset schemes.<br/>"
            "• International Operations Section (IOS) — Coordinates cross-border investigations and MLAT referrals.<br/>"
            "• Federal Compliance &amp; Audit Branch (FCAB) — Ensures regulatory compliance and internal controls.",
            body_style,
        )
    )

    # Regional field offices
    section("Regional Field Offices")
    story.append(
        Paragraph(
            "• Washington D.C. Headquarters — Strategic command and national coordination.<br/>"
            "• New York Field Office — Northeast Districts.<br/>"
            "• Chicago Field Office — Midwest Districts.<br/>"
            "• Los Angeles Field Office — Western Districts.<br/>"
            "• Atlanta Field Office — Southern Districts.",
            body_style,
        )
    )

    # Mission & authority
    section("Mission & Legal Authority")
    story.append(
        Paragraph(
            'Primary Mission: "To protect the American people and uphold the Constitution by '
            "investigating federal criminal violations and supporting the prosecution of offenders "
            'through lawful, effective, and impartial operations."',
            body_style,
        )
    )
    story.append(
        Spacer(1, 4)
    )
    story.append(
        Paragraph(
            "• Established under Attorney General Order No. 1246-1976.<br/>"
            "• Operates under 28 U.S.C. §§ 510–525 (Department of Justice Organization).<br/>"
            "• Complies with the Federal Rules of Criminal and Civil Procedure.<br/>"
            "• Subject to oversight by the Senate and House Judiciary Committees.",
            body_style,
        )
    )

    # Annual statistics
    section("Annual Operational Statistics (FY 2024)")
    story.append(
        Paragraph(
            "• Total Cases Processed: 67,483.<br/>"
            "• Interagency Referrals Completed: 8,527.<br/>"
            "• Average Processing Time: 4.2 business days.<br/>"
            "• Operational Efficiency Index: 94.7%.<br/>"
            "• Federal Compliance Rate: 99.8%.<br/>"
            "• Budget Utilization: $487.3 million (FY 2024).",
            body_style,
        )
    )

    # Oversight
    section("Quality Assurance & Oversight")
    story.append(
        Paragraph(
            "The CID undergoes regular audits and reviews by:<br/>"
            "• Government Accountability Office (GAO) — Annual compliance audit.<br/>"
            "• U.S. Department of Justice, Office of the Inspector General (OIG) — Quarterly reviews.<br/>"
            "• Congressional Oversight Committees — Semi-annual hearings.<br/>"
            "• Federal Compliance &amp; Audit Branch (FCAB) — Internal operational audits.",
            body_style,
        )
    )

    # Footer note
    story.append(Spacer(1, 18))
    story.append(
        HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#CBD5E0"), spaceBefore=4, spaceAfter=4)
    )
    footer = Paragraph(
        "This overview is provided for informational and briefing purposes. "
        "It does not create any substantive or procedural rights, and it does not "
        "supersede existing statutes, regulations, or Attorney General Guidelines.",
        S(
            "OrgFooter",
            fontSize=7.5,
            leading=10,
            fontName="Helvetica-Oblique",
            textColor=colors.HexColor("#4A5568"),
            alignment=TA_LEFT,
        ),
    )
    story.append(footer)

    def _on_page(canvas_obj, doc_obj):
        w, h = doc_obj.pagesize
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica-Bold", 8)
        canvas_obj.setFillColor(colors.black)
        canvas_obj.drawCentredString(w / 2.0, h - 0.35 * inch, "SENSITIVE BUT UNCLASSIFIED")
        canvas_obj.drawCentredString(w / 2.0, 0.45 * inch, "SENSITIVE BUT UNCLASSIFIED")
        canvas_obj.restoreState()

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()
