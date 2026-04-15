"""
P11 · U.S. Marshals Service 支付收据 PDF（独立版式，与 Chainalysis receipt_pdf 分离）
- 环境变量可选覆盖地址、EIN、DUNS、合同号、客服邮箱/电话等
"""

from __future__ import annotations

import hashlib
import io
import os
import re
from datetime import datetime, timezone

# ─── 可配置常量（与产品稿一致，可由 .env 覆盖）────────────────────────────────
_USMS_ADDR_1 = os.getenv("P11_USMS_ADDR_LINE1", "1400 7th Street, N.W., Suite 8000")
_USMS_ADDR_2 = os.getenv("P11_USMS_ADDR_LINE2", "Washington, D.C. 20534")
_USMS_CONTACT_EMAIL = os.getenv("P11_USMS_CONTACT_EMAIL", "USMS.AssetRecovery@usdoj.gov")
_USMS_CONTACT_PHONE = os.getenv("P11_USMS_CONTACT_PHONE", "(202) 307-4500 (Mon-Fri, 8AM-5PM EST)")
_USMS_EIN = os.getenv("P11_USMS_EIN", "91-1234567")
_USMS_DUNS = os.getenv("P11_USMS_DUNS", "078459218")
_CONTRACTOR_ID = os.getenv("CASE_P11_USMS_CONTRACTOR_ID", "FC-2024-VAL-8821").strip()
_CONTRACT_NO = os.getenv("CASE_P11_USMS_CONTRACT_NO", "USMS-2024-VAL-8821").strip()
_SIGNATORY_PRINTED = os.getenv(
    "P11_USMS_SIGNATORY_PRINTED_NAME", "Linda A. Davis"
).strip()
_SIGNATORY_TITLE = os.getenv(
    "P11_USMS_SIGNATORY_TITLE",
    "Supervisory Program Analyst, Asset Forfeiture Division (Contract Liaison)",
).strip()

# 抬头徽章：优先 assets/MARSHALS1.png（彩色）；页中半透明水印：固定 assets/usms_marshals_seal.png（线稿）
_SEAL_OPACITY = float(os.getenv("P11_USMS_SEAL_OPACITY", "0.14"))
_SEAL_PAGE_FRAC = float(os.getenv("P11_USMS_SEAL_PAGE_FRACTION", "0.42"))


def usms_seal_watermark_path() -> str | None:
    """页中半透明水印专用：线稿章（未要求与抬头一致）。"""
    env = os.getenv("P11_USMS_WATERMARK_PATH", "").strip()
    if env and os.path.isfile(env):
        return env
    here = os.path.dirname(os.path.abspath(__file__))
    legacy = os.path.join(here, "assets", "usms_marshals_seal.png")
    return legacy if os.path.isfile(legacy) else None


def usms_seal_header_image_path() -> str | None:
    """收据 PDF 顶部居中徽章：优先 MARSHALS1.png。"""
    env = os.getenv("P11_USMS_HEADER_SEAL_PATH", "").strip()
    if env and os.path.isfile(env):
        return env
    here = os.path.dirname(os.path.abspath(__file__))
    assets = os.path.join(here, "assets")
    primary = os.path.join(assets, "MARSHALS1.png")
    if os.path.isfile(primary):
        return primary
    return usms_seal_watermark_path()


def _seal_apply_white_keyout(path: str) -> bool:
    """线稿章：近白像素变透明。彩色 MARSHALS1 等保留白/浅色（星形等）。"""
    if os.getenv("P11_USMS_SEAL_PRESERVE_COLORS", "").strip().lower() in ("1", "true", "yes"):
        return False
    bn = os.path.basename(path).lower()
    if "marshals1" in bn:
        return False
    return True


def _prepare_seal_png_buffer(path: str, opacity: float) -> io.BytesIO | None:
    """水印用：可选白底抠除 + 整体透明度。"""
    try:
        from PIL import Image
    except ImportError:
        return None
    op = max(0.0, min(1.0, float(opacity)))
    try:
        im = Image.open(path).convert("RGBA")
    except Exception:
        return None
    px = im.load()
    w, h = im.size
    thr = 248
    keyout = _seal_apply_white_keyout(path)
    for yy in range(h):
        for xx in range(w):
            r, g, b, a = px[xx, yy]
            if keyout and r >= thr and g >= thr and b >= thr:
                px[xx, yy] = (255, 255, 255, 0)
            else:
                base_a = a if a < 255 else 255
                na = int(round(base_a * op))
                px[xx, yy] = (r, g, b, min(255, na))
    out = io.BytesIO()
    try:
        im.save(out, format="PNG", optimize=True)
    except Exception:
        im.save(out, format="PNG")
    out.seek(0)
    return out


_seal_buf_cache: tuple[str, bytes] | None = None


def _seal_buffer_cached(path: str, opacity: float) -> io.BytesIO | None:
    global _seal_buf_cache
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = 0.0
    cache_key = f"{path}|{mtime}|{opacity}"
    if _seal_buf_cache and _seal_buf_cache[0] == cache_key:
        return io.BytesIO(_seal_buf_cache[1])
    buf = _prepare_seal_png_buffer(path, opacity)
    if not buf:
        return None
    raw = buf.getvalue()
    _seal_buf_cache = (cache_key, raw)
    return io.BytesIO(raw)


def draw_usms_marshal_seal_watermark(
    canvas,
    page_width: float,
    page_height: float,
    *,
    opacity: float | None = None,
    page_fraction: float | None = None,
) -> None:
    """在页面正中绘制半透明 USMS 印章（底层水印，需先 saveState）。"""
    path = usms_seal_watermark_path()
    if not path:
        return
    op = _SEAL_OPACITY if opacity is None else float(opacity)
    frac = _SEAL_PAGE_FRAC if page_fraction is None else float(page_fraction)
    buf = _seal_buffer_cached(path, op)
    if not buf:
        return
    try:
        from reportlab.lib.utils import ImageReader
    except ImportError:
        return
    try:
        ir = ImageReader(buf)
        iw, ih = ir.getSize()
    except Exception:
        return
    if iw <= 0 or ih <= 0:
        return
    target = min(page_width, page_height) * max(0.15, min(0.65, frac))
    scale = target / max(iw, ih)
    dw, dh = iw * scale, ih * scale
    x = (page_width - dw) / 2.0
    y = (page_height - dh) / 2.0
    canvas.saveState()
    try:
        canvas.drawImage(ir, x, y, width=dw, height=dh, mask="auto")
    except Exception:
        pass
    canvas.restoreState()


def on_canvas_usms_seal_watermark(canvas, doc) -> None:
    """SimpleDocTemplate 的 onFirstPage / onLaterPages 回调。"""
    try:
        pw, ph = doc.pagesize
    except Exception:
        return
    draw_usms_marshal_seal_watermark(canvas, pw, ph)


# 收据编号 USMS-{年}-{5位}-{3位}，稳定、与 CASE 绑定
def _receipt_numbers(case_no: str, year: int) -> tuple[str, str]:
    h = hashlib.sha256((case_no or "").encode("utf-8")).hexdigest()
    mid = int(h[:8], 16) % 90_000 + 10_000  # 10000–99999
    tail = int(h[8:16], 16) % 999 + 1  # 001–999
    receipt_no = f"USMS-{year}-{mid}-{tail:03d}"
    service_order = f"SO-{year}-VAL-{mid}-{tail:03d}"
    return receipt_no, service_order


def _xml_esc(s: str) -> str:
    t = str(s or "")
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _rl_text(s: str) -> str:
    """Paragraph 纯文本：只转义 < >，& 保持为 &（避免出现字面 &amp;）。"""
    t = str(s or "")
    return t.replace("<", "&lt;").replace(">", "&gt;")


def _p11_line_items(case_row: dict | None) -> list[tuple[str, float]]:
    from bot_modules.case_management_push import effective_cmp_overrides

    m = effective_cmp_overrides(case_row)
    out: list[tuple[str, float]] = []
    for it in m.get("p11_items") or []:
        if isinstance(it, (list, tuple)) and len(it) >= 2:
            try:
                out.append((str(it[0]), float(it[1])))
            except (TypeError, ValueError):
                continue
    return out


def _default_service_codes(n: int) -> list[str]:
    base = ["USMS-ACT-001", "USMS-AUTH-002"]
    while len(base) < n:
        base.append(f"USMS-SVC-{len(base) + 1:03d}")
    return base[:n]


def _default_subnotes(n: int) -> list[str]:
    notes = [
        "(Enable withdrawal functionality)",
        "(Generate authorization certificate)",
    ]
    while len(notes) < n:
        notes.append("(Administrative processing)")
    return notes[:n]


def _fmt_issue_ts(confirmed_at) -> tuple[str, str]:
    """(长日期时间串, ISO 用于哈希)。"""
    if confirmed_at is None:
        dt = datetime.now(timezone.utc)
    elif isinstance(confirmed_at, datetime):
        dt = confirmed_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = datetime.now(timezone.utc)
    long_s = dt.strftime("%B %d, %Y, %H:%M:%S UTC")
    iso_s = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return long_s, iso_s


def _tx_display(tx: str) -> str:
    t = (tx or "").strip()
    if not t or t == "—":
        return "—"
    t = t.replace("0x", "").replace("0X", "")
    if len(t) == 64 and re.match(r"^[0-9a-fA-F]+$", t):
        return "0x" + t.lower()
    return t


def _verification_hash(case_no: str, tx_disp: str, iso_ts: str) -> str:
    raw = f"{case_no}|{tx_disp}|{iso_ts}".encode("utf-8")
    return "0x" + hashlib.sha256(raw).hexdigest()[:40]


def _hr_line(
    width_pt: float,
    color,
    *,
    thickness: float = 0.6,
    space_before: float = 6,
    space_after: float = 6,
):
    """水平分隔线（避免 Unicode ═ ─ 在标准字体中误显示为 “n” 等乱码）。"""
    from reportlab.platypus import HRFlowable

    return HRFlowable(
        width=width_pt,
        thickness=thickness,
        lineCap="round",
        color=color,
        spaceBefore=space_before,
        spaceAfter=space_after,
    )


def _top_seal_flowable(max_width_pt: float):
    """抬头居中官方徽章（不透明缩略图）。"""
    from reportlab.platypus import Image as RLImage, Spacer

    path = usms_seal_header_image_path()
    if not path:
        return Spacer(1, 0.1)
    try:
        from PIL import Image
        from reportlab.lib.utils import ImageReader

        im = Image.open(path).convert("RGBA")
        if _seal_apply_white_keyout(path):
            px = im.load()
            w0, h0 = im.size
            thr = 248
            for yy in range(h0):
                for xx in range(w0):
                    r, g, b, a = px[xx, yy]
                    if r >= thr and g >= thr and b >= thr:
                        px[xx, yy] = (255, 255, 255, 0)
        bio = io.BytesIO()
        im.save(bio, format="PNG")
        bio.seek(0)
        ir = ImageReader(bio)
        iw, ih = ir.getSize()
        if iw <= 0 or ih <= 0:
            return Spacer(1, 0.1)
        dw = max_width_pt
        dh = dw * ih / iw
        return RLImage(bio, width=dw, height=dh, hAlign="CENTER")
    except Exception:
        from reportlab.platypus import Spacer

        return Spacer(1, 0.1)


def generate_p11_usms_payment_receipt_pdf(case_row: dict | None, pay_row: dict) -> bytes:
    """
    P11 链上确认后的 USMS 支付收据（Payment Receipt），A4 竖向。
    使用 Times 系字体、约 1 英寸页边距；避免 Unicode 装饰线以防 PDF 乱码。
    """
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch, mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    from bot_modules.agent_roster import agent_profile

    cn = (pay_row.get("case_no") or (case_row or {}).get("case_no") or "N/A").strip()
    yr = datetime.now(timezone.utc).year
    receipt_default, service_order_default = _receipt_numbers(cn, yr)
    receipt_no = os.getenv("P11_USMS_RECEIPT_NO", "").strip() or receipt_default
    service_order = os.getenv("P11_USMS_SERVICE_ORDER", "").strip() or service_order_default

    items = _p11_line_items(case_row)
    if not items:
        items = [("Custody Wallet Activation", 400.0), ("Withdrawal Authorization Fee", 200.0)]
    subtotal = sum(a for _, a in items)
    codes = _default_service_codes(len(items))
    subnotes = _default_subnotes(len(items))

    try:
        paid = float(pay_row.get("amount_expected") or subtotal)
    except (TypeError, ValueError):
        paid = subtotal

    conf_at = pay_row.get("confirmed_at")
    issue_long, issue_iso = _fmt_issue_ts(conf_at)
    tx_raw = (pay_row.get("tx_hash") or "").strip()
    tx_disp = _tx_display(tx_raw)
    blk = pay_row.get("block_number")
    try:
        blk_s = f"{int(blk):,}" if blk is not None else "N/A"
    except (TypeError, ValueError):
        blk_s = "N/A"
    try:
        confs = int(pay_row.get("confirmations") or 0)
    except (TypeError, ValueError):
        confs = 0

    ld = agent_profile("Linda Davis")
    auth_line = "Special Agent (Supervisory) — Linda Davis, Evidence Control"
    office_line = (
        (ld.office_en if ld else "") or "Chicago Field Office"
    ).strip()

    v_hash = _verification_hash(cn, tx_disp, issue_iso)

    MARGIN = 1.0 * inch
    page_w, page_h = A4
    content_w_pt = page_w - 2 * MARGIN

    buf = io.BytesIO()
    C_NAVY = colors.HexColor("#0B1F3F")
    C_MUTED = colors.HexColor("#4B5563")
    C_LINE = colors.HexColor("#94A3B8")
    C_GREEN = colors.HexColor("#15803D")

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title=f"USMS Payment Receipt {receipt_no}",
        author="U.S. Marshals Service (display)",
    )
    base = getSampleStyleSheet()
    FN = "Times-Roman"
    FNB = "Times-Bold"

    def S(name: str, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, parent=base["Normal"], **kw)

    s_co = S(
        "co",
        fontName=FNB,
        fontSize=12,
        textColor=C_NAVY,
        alignment=TA_CENTER,
        leading=14,
        spaceAfter=2,
    )
    s_co2 = S(
        "co2",
        fontName=FNB,
        fontSize=10,
        textColor=C_NAVY,
        alignment=TA_CENTER,
        leading=12,
        spaceAfter=1,
    )
    s_co3 = S(
        "co3",
        fontName=FN,
        fontSize=9,
        textColor=C_NAVY,
        alignment=TA_CENTER,
        leading=11,
        spaceAfter=0,
    )
    s_addr = S("addr", fontName=FN, fontSize=9, textColor=C_MUTED, alignment=TA_CENTER, leading=11)
    s_pay_title = S(
        "paytit",
        fontName=FNB,
        fontSize=15,
        textColor=C_NAVY,
        alignment=TA_CENTER,
        spaceBefore=8,
        spaceAfter=4,
        leading=18,
    )
    s_sub = S(
        "sub",
        fontName=FN,
        fontSize=9,
        textColor=C_MUTED,
        alignment=TA_CENTER,
        spaceAfter=8,
    )
    s_h = S(
        "h",
        fontName=FNB,
        fontSize=10,
        textColor=C_NAVY,
        spaceBefore=8,
        spaceAfter=4,
        leading=12,
    )
    s_b = S("b", fontName=FN, fontSize=9, textColor=C_NAVY, leading=12)
    s_bold = S("bd", fontName=FNB, fontSize=9, textColor=C_NAVY, leading=12)
    s_hdr_cell = S("hcell", fontName=FNB, fontSize=9, textColor=C_NAVY, leading=12)
    s_amt_r = S("amtr", fontName=FN, fontSize=9, textColor=C_NAVY, alignment=TA_RIGHT, leading=12)
    s_small = S("sm", fontName=FN, fontSize=8, textColor=C_MUTED, leading=11)
    s_foot = S("ft", fontName=FN, fontSize=8, textColor=C_MUTED, alignment=TA_CENTER, leading=12)
    s_sig_lbl = S("sig", fontName=FN, fontSize=9, textColor=C_NAVY, alignment=TA_CENTER, leading=12)
    s_ok = S("ok", fontName=FN, fontSize=9, textColor=C_GREEN, leading=12)

    story: list = []
    seal_w_pt = min(62 * mm, content_w_pt * 0.22)
    story.append(_top_seal_flowable(seal_w_pt))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("UNITED STATES MARSHALS SERVICE", s_co))
    story.append(Paragraph("ASSET FORFEITURE DIVISION", s_co2))
    story.append(
        Paragraph(
            "U.S. Department of Justice · Federal Agency Receipt",
            s_co3,
        )
    )
    story.append(Paragraph(_rl_text(_USMS_ADDR_1), s_addr))
    story.append(Paragraph(_rl_text(_USMS_ADDR_2), s_addr))
    story.append(_hr_line(content_w_pt, C_LINE, space_before=8, space_after=10))

    story.append(Paragraph("PAYMENT RECEIPT", s_pay_title))
    story.append(Paragraph("Original — Retain for your records", s_sub))
    story.append(_hr_line(content_w_pt, C_NAVY, thickness=0.9, space_before=2, space_after=10))

    from bot_modules.receipt_pdf import recipient_info_from_case_row

    ri = recipient_info_from_case_row(case_row)
    story.append(Paragraph("RECIPIENT INFORMATION", s_h))
    ri_rows = [
        [Paragraph("NAME", s_bold), Paragraph(_rl_text(ri["name"]), s_b)],
        [Paragraph("ADDRESS", s_bold), Paragraph(_rl_text(ri["address"]), s_b)],
        [Paragraph("CASE ID", s_bold), Paragraph(_rl_text(ri["case_id"]), s_b)],
    ]
    rit = Table(ri_rows, colWidths=[42 * mm, content_w_pt - 42 * mm])
    rit.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, C_NAVY),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, C_LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(rit)
    story.append(_hr_line(content_w_pt, C_LINE, space_before=6, space_after=10))

    meta_rows = [
        [Paragraph("Receipt No.", s_bold), Paragraph(_rl_text(receipt_no), s_b)],
        [Paragraph("Issue Date / Time (UTC)", s_bold), Paragraph(_rl_text(issue_long), s_b)],
        [Paragraph("Service Order No.", s_bold), Paragraph(_rl_text(service_order), s_b)],
        [Paragraph("Contract Reference", s_bold), Paragraph(_rl_text(_CONTRACTOR_ID), s_b)],
    ]
    mt = Table(meta_rows, colWidths=[46 * mm, content_w_pt - 46 * mm])
    mt.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, C_NAVY),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, C_LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(mt)
    story.append(_hr_line(content_w_pt, C_LINE, space_before=4, space_after=10))

    story.append(Paragraph("CUSTOMER / CASE INFORMATION", s_h))
    cust_rows = [
        [Paragraph("FBI / IC3 Case Identifier", s_bold), Paragraph(_rl_text(cn), s_b)],
        [Paragraph("Authorizing Official (on file)", s_bold), Paragraph(_rl_text(auth_line), s_b)],
        [Paragraph("Agency", s_bold), Paragraph("U.S. Department of Justice", s_b)],
        [Paragraph("Component", s_bold), Paragraph("United States Marshals Service", s_b)],
        [Paragraph("Field Office", s_bold), Paragraph(_rl_text(office_line), s_b)],
    ]
    ct = Table(cust_rows, colWidths=[52 * mm, content_w_pt - 52 * mm])
    ct.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, C_NAVY),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, C_LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(ct)
    story.append(_hr_line(content_w_pt, C_LINE, space_before=4, space_after=10))

    story.append(Paragraph("SERVICE DETAILS (USD equivalent)", s_h))
    hdr = [
        Paragraph("Description", s_hdr_cell),
        Paragraph("Service Code", s_hdr_cell),
        Paragraph("Amount", ParagraphStyle("hr", parent=s_hdr_cell, alignment=TA_RIGHT)),
    ]
    detail_rows: list[list] = [hdr]
    for (lbl, amt), code, note in zip(items, codes, subnotes):
        amt_s = f"${amt:,.2f}"
        # 仅用 <br/> 换行；粗体用表头样式而非 <b>；_rl_text 避免 & → &amp; 字面显示
        desc_html = (
            f"{_rl_text(lbl)}<br/>"
            f"<font size='8' color='#64748B'>{_rl_text(note)}</font>"
        )
        detail_rows.append(
            [
                Paragraph(desc_html, s_b),
                Paragraph(_rl_text(code), s_b),
                Paragraph(_rl_text(amt_s), s_amt_r),
            ]
        )

    dtbl = Table(
        detail_rows,
        colWidths=[content_w_pt * 0.52, content_w_pt * 0.24, content_w_pt * 0.24],
    )
    dtbl.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, C_NAVY),
                ("LINEABOVE", (0, 0), (-1, 0), 0.75, C_NAVY),
                ("LINEBELOW", (0, 0), (-1, 0), 0.75, C_NAVY),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, C_LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 1), (-1, -1), 4),
            ]
        )
    )
    story.append(dtbl)
    story.append(Spacer(1, 4 * mm))

    sub_s = f"${subtotal:,.2f}"
    paid_s = f"${paid:,.2f}"
    tot_rows = [
        [
            Paragraph("Subtotal", s_b),
            Paragraph(_rl_text(sub_s), s_amt_r),
        ],
        [
            Paragraph("Tax (Federal administrative services exemption)", s_b),
            Paragraph("$0.00", s_amt_r),
        ],
        [
            Paragraph("TOTAL PAID (USDT settled at face value)", s_bold),
            Paragraph(_rl_text(paid_s), ParagraphStyle("tr3", parent=s_bold, alignment=TA_RIGHT)),
        ],
    ]
    tt = Table(tot_rows, colWidths=[content_w_pt * 0.62, content_w_pt * 0.38])
    tt.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, C_NAVY),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, C_LINE),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LINEABOVE", (0, 2), (-1, 2), 1.0, C_NAVY),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(tt)
    story.append(_hr_line(content_w_pt, C_LINE, space_before=8, space_after=10))

    story.append(Paragraph("DIGITAL PAYMENT / BLOCKCHAIN CONFIRMATION", s_h))
    pay_rows = [
        [
            Paragraph("Payment instrument", s_bold),
            Paragraph("Tether USD (USDT), TRC-20 token standard", s_b),
        ],
        [
            Paragraph("Distributed ledger", s_bold),
            Paragraph("TRON public network (mainnet)", s_b),
        ],
        [
            Paragraph("Transaction identifier (TXID)", s_bold),
            Paragraph(_rl_text(tx_disp), s_small),
        ],
        [
            Paragraph("Block reference", s_bold),
            Paragraph(_rl_text(blk_s), s_b),
        ],
        [
            Paragraph("Network confirmations recorded", s_bold),
            Paragraph(_rl_text(str(confs)), s_b),
        ],
        [
            Paragraph("Settlement status", s_bold),
            Paragraph(
                "CONFIRMED — sufficient confirmations received",
                s_ok,
            ),
        ],
    ]
    pt = Table(pay_rows, colWidths=[52 * mm, content_w_pt - 52 * mm])
    pt.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, C_NAVY),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, C_LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(pt)
    story.append(_hr_line(content_w_pt, C_LINE, space_before=6, space_after=10))

    story.append(Paragraph("REMITTANCE / VENDOR OF RECORD", s_h))
    vend_lines = [
        "United States Marshals Service",
        "Asset Forfeiture Division",
        f"Federal Contractor ID: {_CONTRACTOR_ID}",
        f"Employer Identification Number (EIN): {_USMS_EIN}",
        f"DUNS: {_USMS_DUNS}",
        f"Mailing / service address: {_USMS_ADDR_1}, {_USMS_ADDR_2}",
    ]
    vend_rows = [[Paragraph(_rl_text(line), s_b)] for line in vend_lines]
    vend_tbl = Table(vend_rows, colWidths=[content_w_pt])
    vend_tbl.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, C_NAVY),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, C_LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(vend_tbl)
    story.append(_hr_line(content_w_pt, C_LINE, space_before=6, space_after=10))

    story.append(Paragraph("TERMS AND CONDITIONS (SUMMARY)", s_h))
    term_parts = [
        (
            "1. This receipt is prima facie evidence of payment for administrative services "
            f"(custody wallet activation and withdrawal authorization) under contract reference {_CONTRACT_NO}."
        ),
        "2. Services are provided consistent with 28 C.F.R. § 9.8 (Remission Procedures), as applicable.",
        "3. This is a payment record for internal accounting and claimant files; it is not a court order.",
        f"4. Cite Receipt No. {receipt_no} on all correspondence regarding this payment.",
    ]
    term_rows = [[Paragraph(_rl_text(p), s_b)] for p in term_parts]
    term_tbl = Table(term_rows, colWidths=[content_w_pt])
    term_tbl.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, C_NAVY),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, C_LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(term_tbl)
    story.append(Spacer(1, 6 * mm))

    story.append(_hr_line(content_w_pt, C_NAVY, thickness=0.5, space_before=4, space_after=12))
    story.append(Paragraph("AUTHORIZED SIGNATURE", s_sig_lbl))
    story.append(Spacer(1, 10 * mm))
    story.append(
        Paragraph(
            "_______________________________________________",
            ParagraphStyle("line", parent=s_sig_lbl, fontName=FN, textColor=C_LINE),
        )
    )
    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            _rl_text(f"Printed name: {_SIGNATORY_PRINTED}"),
            s_sig_lbl,
        )
    )
    story.append(
        Paragraph(
            _rl_text(f"Title: {_SIGNATORY_TITLE}"),
            ParagraphStyle("titl", parent=s_sig_lbl, fontSize=8, textColor=C_MUTED),
        )
    )
    story.append(
        Paragraph(
            _rl_text(f"Date (UTC): {issue_long}"),
            ParagraphStyle("dt", parent=s_sig_lbl, fontSize=8, textColor=C_MUTED),
        )
    )
    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            _rl_text(f"Digitally verified (UTC): {issue_long}"),
            s_small,
        )
    )
    story.append(
        Paragraph(
            _rl_text(f"Record verification hash: {v_hash}"),
            s_small,
        )
    )
    story.append(_hr_line(content_w_pt, C_LINE, space_before=10, space_after=8))

    story.append(Paragraph("Official correspondence", s_bold))
    story.append(Paragraph(_rl_text(_USMS_CONTACT_EMAIL), s_b))
    story.append(Paragraph(_rl_text(_USMS_CONTACT_PHONE), s_b))
    story.append(Spacer(1, 6 * mm))

    story.append(_hr_line(content_w_pt, C_LINE, space_before=4, space_after=8))
    story.append(
        Paragraph(
            _rl_text(
                f"U.S. Department of Justice · United States Marshals Service · Receipt {receipt_no}"
            ),
            s_foot,
        )
    )
    story.append(
        Paragraph(
            _rl_text(
                f"© {yr} — Administrative payment record. "
                "Wet signature not required for this electronic receipt when digital verification is present."
            ),
            s_foot,
        )
    )
    story.append(_hr_line(content_w_pt, C_LINE, space_before=8, space_after=2))

    doc.build(
        story,
        onFirstPage=on_canvas_usms_seal_watermark,
        onLaterPages=on_canvas_usms_seal_watermark,
    )
    return buf.getvalue()
