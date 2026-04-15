"""
bot_modules/receipt_pdf.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Chainalysis Enterprise Invoice PDF — A4 竖向
深蓝 (#0F172A) 主色调，企业/金融级排版
与 pdf_gen.py 完全隔离，互不影响
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import math
import os
import secrets
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ─── 品牌常量 ──────────────────────────────────────────────────────────────────
_CO_NAME    = "CHAINALYSIS INC."
_CO_ADDR    = "1440 Broadway, 32nd Floor, New York, NY 10018"
_CO_WEB     = "www.chainalysis.com"
_CO_EMAIL   = "Federal.Support@chainalysis.com"
_CO_EIN     = "82-2983010"
_CO_DUNS    = "078459218"

_BILL_L1    = "Federal Bureau of Investigation"
_BILL_L2    = "CJIS Division / IC3 Task Force"
_BILL_L3    = "1000 Custer Hollow Road, Clarksburg, WV 26306"

_SVC_CODE   = "FBI-PRIORITY-TRACE-001"
_API_INST   = "Private Instance #8842-X"
_DEF_CTR    = "DOJ-2024-BC-7829"

# ─── JSON 解析 ─────────────────────────────────────────────────────────────────
def _jb(v) -> dict:
    if isinstance(v, dict): return v
    if isinstance(v, str):
        try: return json.loads(v) or {}
        except Exception: return {}
    return {}

# ─── 时间格式化 ────────────────────────────────────────────────────────────────
def _fdate(ts) -> str:
    if ts is None: return "—"
    if isinstance(ts, datetime):
        if ts.tzinfo is None: ts = ts.replace(tzinfo=timezone.utc)
        return ts.strftime(f"%B {ts.day}, %Y")
    return str(ts)

def _fts(ts) -> str:
    if ts is None: return "—"
    if isinstance(ts, datetime):
        if ts.tzinfo is None: ts = ts.replace(tzinfo=timezone.utc)
        return ts.strftime("%Y-%m-%d  %H:%M:%S UTC")
    return str(ts)

# ─── 字段提取 ─────────────────────────────────────────────────────────────────
def recipient_info_from_case_row(case_row: dict | None) -> dict[str, str]:
    """
    报案人展示信息：优先数据库 `case_pdf_snapshot`（与官方 PDF 一致），
    其次 `case_cmp_overrides` 可选手动覆盖，最后顶层列。
    返回 name, address, case_id（用于 P5/P10/P11 收据与协议 PDF）。
    """
    c = case_row or {}
    snap = _jb(c.get("case_pdf_snapshot"))
    try:
        from bot_modules.case_management_push import effective_cmp_overrides

        m = effective_cmp_overrides(case_row)
    except Exception:
        m = {}
    name = (
        (m.get("recipient_full_name") or m.get("pdf_fullname") or "").strip()
        or (snap.get("fullname") or snap.get("full_name") or "").strip()
        or (c.get("fullname") or c.get("full_name") or "").strip()
    )
    addr = (
        (m.get("recipient_address") or m.get("pdf_address") or "").strip()
        or (snap.get("address") or "").strip()
        or (c.get("address") or "").strip()
    )
    cid = (
        (m.get("display_case_id") or "").strip()
        or (c.get("case_no") or c.get("case_number") or "—")
    )
    if not str(name).strip():
        name = "—"
    if not str(addr).strip():
        addr = "—"
    return {
        "name": str(name).strip(),
        "address": str(addr).strip(),
        "case_id": str(cid).strip() if cid else "—",
    }


def _extract(pay: dict, case: dict | None) -> dict:
    c    = case or {}
    ex   = _jb(pay.get("extra"))
    snap = _jb(c.get("case_pdf_snapshot"))
    ov   = _jb(c.get("case_cmp_overrides"))

    yr     = datetime.now(timezone.utc).year
    rid    = int(pay.get("id") or 0)

    # 顶层 invoice_no：供 P10 授权等未落库的假 pay_row 使用（不依赖 extra 解析）
    inv_no    = (pay.get("invoice_no") or ex.get("invoice_no")
                 or f"INV-{yr}-GB-{rid:05d}")
    ref_no    = ex.get("ref_no")      or f"IC3-{yr}-REF-{rid:05d}-B"
    proj_code = ex.get("proj_code")   or f"DOJ-FY{str(yr)[2:]}-CYBER-004"

    conf      = pay.get("confirmed_at")
    case_id   = pay.get("case_no") or c.get("case_no") or c.get("case_number") or "—"

    try:
        amt_f = float(pay.get("amount_expected") or 0)
        amt   = f"${amt_f:,.2f}"
    except Exception:
        amt   = "—"

    blk = pay.get("block_number")
    return {
        "inv_no":    inv_no,
        "ref_no":    ref_no,
        "proj_code": proj_code,
        "date_str":  _fdate(conf),
        "ts_str":    _fts(conf),
        "case_id":   case_id,
        "amt":       amt,
        "tx_hash":   pay.get("tx_hash") or "—",
        "blk_str":   f"#{blk:,}" if blk else "—",
        "confs":     str(pay.get("confirmations") or "—"),
        "agent":     (ex.get("agent_name") or ov.get("agent_name")
                      or snap.get("agent_name") or "Jennifer Martinez"),
        "ctr_no":    (ex.get("contract_no") or ov.get("contract_no")
                      or snap.get("contract_no") or _DEF_CTR),
        "yr":        yr,
    }


def _xml_esc(s: str) -> str:
    t = str(s or "")
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _rl_text(s: str) -> str:
    """ReportLab Paragraph 当作文本使用时：只转义 < >，保留 &（避免页面上出现字面 &amp;）。"""
    t = str(s or "")
    return t.replace("<", "&lt;").replace(">", "&gt;")


_U_ONES = ("", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE")
_TEENS = (
    "TEN",
    "ELEVEN",
    "TWELVE",
    "THIRTEEN",
    "FOURTEEN",
    "FIFTEEN",
    "SIXTEEN",
    "SEVENTEEN",
    "EIGHTEEN",
    "NINETEEN",
)
_TENS = ("", "", "TWENTY", "THIRTY", "FORTY", "FIFTY", "SIXTY", "SEVENTY", "EIGHTY", "NINETY")


def _wac_under_hundred(n: int) -> str:
    if n < 10:
        return _U_ONES[n]
    if n < 20:
        return _TEENS[n - 10]
    t, u = n // 10, n % 10
    return _TENS[t] + (("-" + _U_ONES[u]) if u else "")


def _wac_under_thousand(n: int) -> str:
    if n < 100:
        return _wac_under_hundred(n)
    h, r = n // 100, n % 100
    return _U_ONES[h] + " HUNDRED" + ((" " + _wac_under_hundred(r)) if r else "")


def _wac_int_to_words(n: int) -> str:
    if n == 0:
        return "ZERO"
    if n < 0:
        return "NEGATIVE " + _wac_int_to_words(-n)
    parts: list[str] = []
    scales = ((1_000_000_000, "BILLION"), (1_000_000, "MILLION"), (1_000, "THOUSAND"))
    rem = n
    for div, name in scales:
        q = rem // div
        if q:
            parts.append(_wac_under_thousand(q) + " " + name)
            rem %= div
    if rem:
        parts.append(_wac_under_thousand(rem))
    return " ".join(parts)


def _wac_usd_amount_words_line(amount: float) -> str:
    d = int(math.floor(float(amount) + 1e-9))
    cents = int(round((float(amount) - d) * 100)) % 100
    return f"{_wac_int_to_words(d)} DOLLARS AND {cents:02d}/100"


def _wac_release_order_id(case_no: str, year: int) -> str:
    h = hashlib.sha256((case_no or "").encode("utf-8")).hexdigest()
    n = int(h[16:24], 16) % 900_000 + 100_000
    return f"RO-{year}-USMS-{n}"


def _wac_doj_case_id_line(case_no: str, year: int, m: dict) -> str:
    for key in ("doj_case_id", "wac_doj_case_id"):
        v = m.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()
    cn = (case_no or "").strip()
    if cn.upper().startswith("IC3-") or "REF-" in cn.upper():
        return cn
    h = hashlib.sha256((case_no or "").encode("utf-8")).hexdigest()
    n5 = int(h[:8], 16) % 90_000 + 10_000
    return f"IC3-{year}-REF-{n5}-B"


def _wac_truncate_hex_display(tx: str, *, head: int = 8, tail: int = 6) -> str:
    t = (tx or "").strip().replace("0x", "").replace("0X", "")
    if not t or t == "—":
        return "—"
    if len(t) <= head + tail + 3:
        return t
    return f"{t[:head]}...{t[-tail:]}"


def _p10_line_items_from_case(case_row: dict | None) -> list[tuple[str, float]]:
    from bot_modules.case_management_push import effective_cmp_overrides

    m = effective_cmp_overrides(case_row)
    out: list[tuple[str, float]] = []
    for it in m.get("p10_items") or []:
        if isinstance(it, (list, tuple)) and len(it) >= 2:
            try:
                out.append((str(it[0]), float(it[1])))
            except (TypeError, ValueError):
                continue
    return out


def _line_items_for_receipt(pay_row: dict, case_row: dict | None) -> list[tuple[str, float]]:
    """P10 多项费用；其余（含 P5）单笔服务行。"""
    pk = (pay_row.get("payment_kind") or "").strip()
    if pk == "p10_pay":
        items = _p10_line_items_from_case(case_row)
        if items:
            return items
    try:
        a = float(pay_row.get("amount_expected") or 0)
    except (TypeError, ValueError):
        a = 0.0
    if pk == "p10_pay":
        return [("SANCTION / AML Compliance Bundle", a)]
    return [("Forensic Evidence Verification Service", a)]


# ─── 印章 Flowable ─────────────────────────────────────────────────────────────
class _Seal(object):
    """Pseudo-Flowable: 圆形 Chainalysis 官方印章，30% 不透明度。"""

    # 继承 Flowable 以便嵌入 Table 单元格
    pass


def _make_seal_flowable(diameter_mm: float = 46, opacity: float = 0.30):
    """返回一个自定义 Flowable，在 canvas 上绘制圆形印章。"""
    from reportlab.platypus import Flowable
    from reportlab.lib.colors import HexColor, Color

    class SealFlowable(Flowable):
        def __init__(self):
            Flowable.__init__(self)
            from reportlab.lib.units import mm
            self._d  = diameter_mm * mm
            self._op = opacity
            self.width  = self._d
            self.height = self._d

        def draw(self):
            from reportlab.lib.colors import HexColor, Color
            c   = self.canv
            op  = self._op
            d   = self._d
            cx  = d / 2
            cy  = d / 2
            R   = d / 2 - 2.0   # pt

            C_BLUE = HexColor("#0033CC")
            C_NAVY = HexColor("#0F172A")

            c.saveState()

            # ── 外圈粗线 ───────────────────────────────────
            c.setStrokeColor(C_BLUE)
            c.setStrokeAlpha(op)
            c.setFillColor(Color(0, 0, 0, alpha=0))
            c.setLineWidth(2.8)
            c.circle(cx, cy, R, stroke=1, fill=0)

            # ── 内圈细线 ───────────────────────────────────
            c.setLineWidth(0.7)
            c.circle(cx, cy, R - 6.5, stroke=1, fill=0)

            # ── 外圈点阵装饰 ───────────────────────────────
            c.setFillColor(C_BLUE)
            c.setFillAlpha(op)
            for i in range(24):
                ang = math.radians(i * 15 - 90)
                px  = cx + (R - 2.8) * math.cos(ang)
                py  = cy + (R - 2.8) * math.sin(ang)
                c.circle(px, py, 0.9, stroke=0, fill=1)

            # ── 盾牌形状 ───────────────────────────────────
            sw    = R * 0.50
            s_top = cy + R * 0.46
            s_mid = cy - R * 0.08
            s_bot = cy - R * 0.64

            p = c.beginPath()
            p.moveTo(cx - sw, s_top)
            p.lineTo(cx + sw, s_top)
            p.lineTo(cx + sw, s_mid)
            p.curveTo(cx + sw * 0.9, s_mid - R * 0.20,
                      cx + sw * 0.3,  s_bot + R * 0.20,
                      cx,             s_bot)
            p.curveTo(cx - sw * 0.3,  s_bot + R * 0.20,
                      cx - sw * 0.9, s_mid - R * 0.20,
                      cx - sw,        s_mid)
            p.close()

            c.setFillColor(C_BLUE)
            c.setFillAlpha(op * 0.60)
            c.setStrokeColor(C_BLUE)
            c.setStrokeAlpha(op)
            c.setLineWidth(1.2)
            c.drawPath(p, stroke=1, fill=1)

            # ── 对勾 ───────────────────────────────────────
            c.setStrokeColor(Color(1, 1, 1, alpha=min(op * 2.8, 0.85)))
            c.setLineWidth(2.4)
            c.setLineCap(1)
            ck_x = cx
            ck_y = cy - R * 0.06
            c.line(ck_x - R*0.14, ck_y - R*0.01,
                   ck_x - R*0.01, ck_y - R*0.17)
            c.line(ck_x - R*0.01, ck_y - R*0.17,
                   ck_x + R*0.19, ck_y + R*0.13)

            # ── 公司名 & 印章文字 ──────────────────────────
            c.setFillColor(C_NAVY)
            c.setFillAlpha(op)
            c.setFont("Helvetica-Bold", 6.2)
            c.drawCentredString(cx, cy + R * 0.68, "CHAINALYSIS INC.")

            c.setFont("Helvetica-Bold", 5.6)
            c.drawCentredString(cx, cy - R * 0.80, "OFFICIAL SEAL")

            c.restoreState()

    return SealFlowable()


# ─── PDF 主函数 ────────────────────────────────────────────────────────────────
def generate_payment_receipt_pdf(
    pay_row: dict,
    case_row: dict | None = None,
    *,
    agreement_mode: bool = False,
    deposit_address: str = "",
    agreement_memo: str = "",
    service_order: str = "",
    agreement_contract_no: str = "",
) -> bytes:
    """
    生成 Chainalysis 企业发票 PDF 并返回字节。
    agreement_mode=True 时用于 P10 付款前的《服务授权》摘要（与付讫收据同一版式，含多项费用）。
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.colors import HexColor, Color
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
        Table, TableStyle, HRFlowable, KeepTogether,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.pdfbase.pdfmetrics import stringWidth

    f = _extract(pay_row, case_row)
    if agreement_mode and agreement_contract_no.strip():
        f["ctr_no"] = agreement_contract_no.strip()

    pk = "p10_pay" if agreement_mode else (pay_row.get("payment_kind") or "").strip()
    line_items = (
        _p10_line_items_from_case(case_row)
        if agreement_mode
        else _line_items_for_receipt(pay_row, case_row)
    )
    if agreement_mode and not line_items:
        try:
            fb = float(pay_row.get("amount_expected") or 2500)
        except (TypeError, ValueError):
            fb = 2500.0
        line_items = [("SANCTION / AML Compliance (bundle)", fb)]

    buf = io.BytesIO()

    # ── 颜色 ──────────────────────────────────────────────────────
    C_NAVY   = HexColor("#0F172A")
    C_BLUE   = HexColor("#0033CC")
    C_HIBLUE = HexColor("#1D4ED8")
    C_GREEN  = HexColor("#15803D")
    C_LTGRN  = HexColor("#DCFCE7")
    C_LGREY  = HexColor("#F8F9FA")
    C_BORDER = HexColor("#CBD5E1")
    C_MUTED  = HexColor("#64748B")
    C_STRIPE = HexColor("#F1F5F9")

    PW = A4[0] - 30 * mm   # 可用宽度 ≈ 180mm

    _pdf_title = (
        f"Service Authorization {f['inv_no']}"
        if agreement_mode
        else f"Invoice {f['inv_no']}"
    )
    _pdf_subj = (
        "Contractor Service Authorization"
        if agreement_mode
        else "Federal Contractor Invoice"
    )
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=14*mm,  bottomMargin=14*mm,
        title=_pdf_title,
        author="Chainalysis Inc.",
        subject=_pdf_subj,
    )

    base = getSampleStyleSheet()

    def S(name, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, parent=base["Normal"], **kw)

    # ── 样式集 ────────────────────────────────────────────────────
    s_co_name  = S("co_nm",  fontName="Helvetica-Bold", fontSize=13,
                   textColor=C_NAVY, spaceAfter=2)
    s_co_info  = S("co_if",  fontName="Helvetica", fontSize=8,
                   textColor=C_MUTED, leading=13)
    # 大字标题须显式 leading，否则换行时行距过小会与下一行 Invoice 重叠
    s_inv_big  = S("inv_bg", fontName="Helvetica-Bold", fontSize=28,
                   textColor=C_NAVY, alignment=TA_RIGHT,
                   leading=34, spaceAfter=8)
    s_inv_no   = S("inv_no", fontName="Helvetica-Bold", fontSize=10,
                   textColor=C_HIBLUE, alignment=TA_RIGHT, spaceAfter=1)
    s_inv_dt   = S("inv_dt", fontName="Helvetica", fontSize=9,
                   textColor=C_NAVY, alignment=TA_RIGHT, leading=14)
    s_paid     = S("paid",   fontName="Helvetica-Bold", fontSize=9,
                   textColor=C_GREEN, alignment=TA_CENTER)
    s_sec_hdr  = S("sec_h",  fontName="Helvetica-Bold", fontSize=7.5,
                   textColor=C_MUTED, spaceBefore=1, spaceAfter=3,
                   letterSpacing=1.5)
    s_bill_v   = S("bill_v", fontName="Helvetica", fontSize=9,
                   textColor=C_NAVY, leading=14)
    s_bill_at  = S("bill_a", fontName="Helvetica-Oblique", fontSize=8.5,
                   textColor=C_MUTED, leading=13)
    s_th       = S("th",     fontName="Helvetica-Bold", fontSize=8.5,
                   textColor=colors.white, alignment=TA_LEFT)
    s_th_r     = S("th_r",   fontName="Helvetica-Bold", fontSize=8.5,
                   textColor=colors.white, alignment=TA_RIGHT)
    s_td_ctr   = S("td_c",   fontName="Helvetica-Bold", fontSize=9,
                   textColor=C_NAVY, alignment=TA_CENTER)
    s_td_desc  = S("td_dc",  fontName="Helvetica-Bold", fontSize=9,
                   textColor=C_NAVY, spaceAfter=1)
    s_td_dsm   = S("td_ds",  fontName="Helvetica", fontSize=8,
                   textColor=C_MUTED, leading=12)
    s_td_mono  = S("td_mn",  fontName="Courier", fontSize=7.5,
                   textColor=C_MUTED, leading=11, wordWrap="CJK")
    s_td_r     = S("td_r",   fontName="Helvetica", fontSize=9,
                   textColor=C_NAVY, alignment=TA_RIGHT)
    s_td_rb    = S("td_rb",  fontName="Helvetica-Bold", fontSize=9,
                   textColor=C_NAVY, alignment=TA_RIGHT)
    s_sub_l    = S("sub_l",  fontName="Helvetica", fontSize=9,
                   textColor=C_MUTED, alignment=TA_RIGHT)
    s_sub_v    = S("sub_v",  fontName="Helvetica", fontSize=9,
                   textColor=C_NAVY, alignment=TA_RIGHT)
    s_tot_l    = S("tot_l",  fontName="Helvetica-Bold", fontSize=11,
                   textColor=C_NAVY, alignment=TA_RIGHT)
    s_tot_v    = S("tot_v",  fontName="Helvetica-Bold", fontSize=11,
                   textColor=C_NAVY, alignment=TA_RIGHT)
    s_pay_l    = S("pay_l",  fontName="Helvetica-Bold", fontSize=8.5,
                   textColor=C_MUTED)
    s_pay_v    = S("pay_v",  fontName="Helvetica", fontSize=9,
                   textColor=C_NAVY, leading=13)
    s_pay_mn   = S("pay_mn", fontName="Courier", fontSize=8,
                   textColor=C_NAVY, leading=13, wordWrap="CJK")
    s_auth_l   = S("au_l",   fontName="Helvetica-Bold", fontSize=8,
                   textColor=C_MUTED, alignment=TA_CENTER, spaceAfter=2)
    s_auth_mn  = S("au_mn",  fontName="Courier", fontSize=7.5,
                   textColor=C_MUTED, alignment=TA_CENTER)
    s_trm_h    = S("trm_h",  fontName="Helvetica-Bold", fontSize=8,
                   textColor=C_NAVY, spaceAfter=3, letterSpacing=1.0)
    s_trm_t    = S("trm_t",  fontName="Helvetica", fontSize=7.8,
                   textColor=C_MUTED, leading=12)
    s_foot     = S("foot",   fontName="Helvetica", fontSize=7.5,
                   textColor=C_MUTED, alignment=TA_CENTER, leading=12)

    # ── 辅助 ──────────────────────────────────────────────────────
    def _hr(clr=C_BORDER, thick=0.6, sb=4, sa=4):
        return HRFlowable(width="100%", thickness=thick, color=clr,
                          spaceBefore=sb, spaceAfter=sa)

    C_AMBER = HexColor("#B45309")
    C_LAMBER = HexColor("#FEF3C7")

    def _paid_badge():
        t = Table([[Paragraph("  PAID  ", s_paid)]],
                  colWidths=[22*mm], rowHeights=[7*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), C_LTGRN),
            ("BOX",           (0,0), (-1,-1), 0.8, C_GREEN),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,0), (-1,-1), 1),
            ("BOTTOMPADDING", (0,0), (-1,-1), 1),
            ("LEFTPADDING",   (0,0), (-1,-1), 0),
            ("RIGHTPADDING",  (0,0), (-1,-1), 0),
        ]))
        return t

    s_pending = ParagraphStyle(
        "pend", parent=base["Normal"],
        fontName="Helvetica-Bold", fontSize=9, textColor=C_AMBER, alignment=TA_CENTER,
    )

    def _pending_badge():
        t = Table([[Paragraph("  PENDING AUTHORIZATION  ", s_pending)]],
                  colWidths=[48*mm], rowHeights=[7*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), C_LAMBER),
            ("BOX",           (0,0), (-1,-1), 0.8, C_AMBER),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,0), (-1,-1), 1),
            ("BOTTOMPADDING", (0,0), (-1,-1), 1),
            ("LEFTPADDING",   (0,0), (-1,-1), 0),
            ("RIGHTPADDING",  (0,0), (-1,-1), 0),
        ]))
        return t

    # ─────────────────────────────────────────────────────────────
    story = []

    # ══ §1  页眉（双栏）══════════════════════════════════════════
    import os as _os2
    from reportlab.platypus import Image as _RLImage2
    # 页眉 Logo：带公司名字的横版 logo1
    _logo1_path = _os2.path.join(
        _os2.path.dirname(_os2.path.abspath(__file__)),
        "chainalysis_logo1.png",
    )
    # 横版 logo 宽约 55mm，高度按比例自适应
    _hdr_logo = _RLImage2(_logo1_path, width=55*mm, height=14*mm,
                           kind="proportional")
    _hdr_logo.hAlign = "LEFT"

    left_col = [
        _hdr_logo,
        Spacer(1, 4),
        Paragraph(
            f"{_CO_ADDR}<br/>{_CO_WEB}<br/>{_CO_EMAIL}",
            s_co_info,
        ),
    ]
    inv_word = "SERVICE AUTHORIZATION" if agreement_mode else "INVOICE"
    pw_r = PW * 0.45
    # P10：徽章置顶右对齐；标题单行（自动缩字）或仅在两词之间换行，避免 AUTHORIZATION 被拆音节
    if agreement_mode:
        badge_w = 48 * mm
        _ph = _pending_badge()
        badge_top = Table(
            [[Spacer(1, 1), _ph]],
            colWidths=[max(1 * mm, pw_r - badge_w), badge_w],
        )
        badge_top.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        _ag_txt = "SERVICE AUTHORIZATION"
        _avail = float(pw_r) - 8
        _fs_pick = None
        for _fs in (28, 26, 24, 22, 20, 18, 17, 16, 15):
            if stringWidth(_ag_txt, "Helvetica-Bold", _fs) <= _avail:
                _fs_pick = _fs
                break
        if _fs_pick is not None:
            s_ag_t = ParagraphStyle(
                "ag_tit_1l",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=_fs_pick,
                textColor=C_NAVY,
                alignment=TA_RIGHT,
                leading=round(_fs_pick * 1.22, 1),
                spaceAfter=8,
            )
            agree_title_el = Paragraph(_xml_esc(_ag_txt), s_ag_t)
        else:
            agree_title_el = Paragraph("SERVICE<br/>AUTHORIZATION", s_inv_big)

        right_col = [
            badge_top,
            Spacer(1, 2),
            Paragraph(f"Invoice No.:&nbsp;&nbsp;<b>{f['inv_no']}</b>", s_inv_no),
            Paragraph(f"Date:&nbsp;&nbsp;{f['date_str']}", s_inv_dt),
            Spacer(1, 6),
            agree_title_el,
        ]
    else:
        right_col = [
            Paragraph(inv_word, s_inv_big),
            Paragraph(f"Invoice No.:&nbsp;&nbsp;<b>{f['inv_no']}</b>", s_inv_no),
            Paragraph(f"Date:&nbsp;&nbsp;{f['date_str']}", s_inv_dt),
            Spacer(1, 4),
            _paid_badge(),
        ]

    hdr = Table([[left_col, right_col]], colWidths=[PW * 0.55, PW * 0.45])
    hdr.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("ALIGN",         (1,0), (1,0),   "RIGHT"),
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
        ("RIGHTPADDING",  (0,0), (-1,-1), 0),
        ("TOPPADDING",    (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))
    story.append(hdr)
    story.append(Spacer(1, 4*mm))
    story.append(_hr(C_NAVY, thick=1.8, sb=0, sa=7))

    # ══ 报案人资料（P5 / P10 链上收据与授权页，来自 case_pdf_snapshot）══════════
    ri = recipient_info_from_case_row(case_row)
    story.append(Paragraph("RECIPIENT INFORMATION", s_sec_hdr))
    story.append(Paragraph(f"NAME:&nbsp;&nbsp;{_xml_esc(ri['name'])}", s_bill_v))
    story.append(Paragraph(f"ADDRESS:&nbsp;&nbsp;{_xml_esc(ri['address'])}", s_bill_v))
    story.append(
        Paragraph(
            f"CASE ID:&nbsp;&nbsp;<b>{_xml_esc(ri['case_id'])}</b>",
            s_bill_v,
        )
    )
    story.append(Spacer(1, 4 * mm))
    story.append(_hr(sb=2, sa=6))

    # ══ §2  收件方 ═══════════════════════════════════════════════
    story.append(Paragraph("BILL TO", s_sec_hdr))
    for line in [_BILL_L1, _BILL_L2, _BILL_L3]:
        story.append(Paragraph(line, s_bill_v))
    story.append(Paragraph(
        f"Attention:&nbsp; {f['agent']}, Identity Verification Manager",
        s_bill_at,
    ))
    story.append(Spacer(1, 5*mm))
    story.append(_hr(sb=0, sa=6))

    # ══ §3  服务明细表 ════════════════════════════════════════════
    cW_qty  = 13 * mm
    cW_up   = 32 * mm
    cW_amt  = 30 * mm
    cW_desc = PW - cW_qty - cW_up - cW_amt

    svc_data = [
        [   # ── 表头 ──
            Paragraph("QTY",         s_th),
            Paragraph("DESCRIPTION", s_th),
            Paragraph("UNIT PRICE",  s_th_r),
            Paragraph("AMOUNT",      s_th_r),
        ],
    ]

    if len(line_items) == 1 and pk != "p10_pay":
        lbl0, amt0 = line_items[0]
        _ = lbl0  # 单笔 P5 沿用固定服务文案
        amt_cell = f"${amt0:,.2f}"
        desc_cell = [
            Paragraph("Forensic Evidence Verification Service", s_td_desc),
            Paragraph(f"Service Code:&nbsp; {_SVC_CODE}", s_td_dsm),
            Paragraph(
                f"Includes: Blockchain address attribution, transaction tracing "
                f"for Case <b>{_xml_esc(f['case_id'])}</b>, API access: {_API_INST}.",
                s_td_dsm,
            ),
            Spacer(1, 3),
            Paragraph(f"Reference No.:&nbsp;&nbsp;{_xml_esc(f['ref_no'])}", s_td_mono),
            Paragraph(f"Project Code:&nbsp;&nbsp;&nbsp;{_xml_esc(f['proj_code'])}", s_td_mono),
        ]
        svc_data.append(
            [
                Paragraph("1", s_td_ctr),
                desc_cell,
                Paragraph(amt_cell, s_td_r),
                Paragraph(amt_cell, s_td_rb),
            ]
        )
    else:
        for lbl, amt_i in line_items:
            ams = f"${amt_i:,.2f}"
            desc_one = [
                Paragraph(_xml_esc(lbl), s_td_desc),
                Paragraph(
                    f"Case ID:&nbsp;<b>{_xml_esc(f['case_id'])}</b><br/>"
                    f"Reference No.:&nbsp;{_xml_esc(f['ref_no'])}<br/>"
                    f"Project Code:&nbsp;{_xml_esc(f['proj_code'])}",
                    s_td_dsm,
                ),
            ]
            svc_data.append(
                [
                    Paragraph("1", s_td_ctr),
                    desc_one,
                    Paragraph(ams, s_td_r),
                    Paragraph(ams, s_td_rb),
                ]
            )

    item_sum = sum(a for _, a in line_items)
    tot_amt_str = f"${item_sum:,.2f}"

    svc_tbl = Table(
        svc_data,
        colWidths=[cW_qty, cW_desc, cW_up, cW_amt],
        repeatRows=1,
    )
    svc_tbl.setStyle(TableStyle([
        # 表头
        ("BACKGROUND",    (0,0), (-1,0),  C_NAVY),
        # 外框 + 内线
        ("BOX",           (0,0), (-1,-1), 0.5, C_BORDER),
        ("LINEBELOW",     (0,0), (-1,0),  1.5, C_NAVY),
        ("LINEBELOW",     (0,1), (-1,-1), 0.3, HexColor("#E2E8F0")),
        ("LINEBEFORE",    (1,0), (1,-1),  0.3, HexColor("#E2E8F0")),
        ("LINEBEFORE",    (2,0), (2,-1),  0.3, HexColor("#E2E8F0")),
        ("LINEBEFORE",    (3,0), (3,-1),  0.3, HexColor("#E2E8F0")),
        # 对齐
        ("ALIGN",         (0,0), (0,-1),  "CENTER"),
        ("ALIGN",         (2,0), (-1,-1), "RIGHT"),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        # 内边距
        ("TOPPADDING",    (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (-1,-1), 6),
    ]))
    story.append(svc_tbl)
    story.append(Spacer(1, 3*mm))

    # ── 合计块（右对齐）──────────────────────────────────────────
    tot_lw = 40 * mm
    tot_vw = 28 * mm
    tot_data = [
        [Paragraph("Subtotal",      s_sub_l), Paragraph(tot_amt_str,  s_sub_v)],
        [Paragraph("Tax (Exempt)",  s_sub_l), Paragraph("$0.00",   s_sub_v)],
        [Paragraph("TOTAL",         s_tot_l), Paragraph(tot_amt_str,  s_tot_v)],
    ]
    tot_tbl = Table(tot_data, colWidths=[tot_lw, tot_vw], hAlign="RIGHT")
    tot_tbl.setStyle(TableStyle([
        ("LINEABOVE",     (0,2), (-1,2),  1.2, C_NAVY),
        ("LINEBELOW",     (0,2), (-1,2),  1.2, C_NAVY),
        ("BACKGROUND",    (0,2), (-1,2),  C_STRIPE),
        ("ALIGN",         (0,0), (-1,-1), "RIGHT"),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("RIGHTPADDING",  (0,0), (-1,-1), 8),
    ]))
    story.append(tot_tbl)
    story.append(Spacer(1, 6*mm))
    story.append(_hr(sb=0, sa=5))

    # ══ §4  支付信息 + 印章 ══════════════════════════════════════
    story.append(Paragraph("PAYMENT INFORMATION", s_sec_hdr))
    story.append(Spacer(1, 2))

    # 支付字段
    tot_due = tot_amt_str
    if agreement_mode:
        pay_rows = [
            ("Payment Method", "Cryptocurrency (USDT - TRC20)", False),
            ("Amount Due", tot_due, False),
            ("Deposit Address (TRC20)", _xml_esc(deposit_address.strip()) or "—", True),
            ("MEMO / Tag (include when supported)", _xml_esc(agreement_memo.strip()) or "—", True),
            ("Service Order", _xml_esc(service_order.strip()) or "—", False),
            ("Contract No.", _xml_esc(str(f.get("ctr_no") or "—")), False),
            ("Network", "Tron (TRC20)", False),
            ("Status", "PENDING PAYMENT — execute transfer per prior instructions", False),
        ]
    else:
        pay_rows = [
            ("Payment Method",  "Cryptocurrency (USDT - TRC20)", False),
            ("Transaction ID",  f["tx_hash"],                    True),
            ("Network",         "Tron (TRC20)",                  False),
            ("Block",           f["blk_str"],                    False),
            ("Confirmations",   f["confs"],                      False),
            ("Timestamp (UTC)", f["ts_str"],                     False),
            ("Status",          "CONFIRMED",                     False),
        ]
    pd_rows = []
    for i, (lbl, val, mono) in enumerate(pay_rows):
        vs = s_pay_mn if mono else s_pay_v
        pd_rows.append([
            Paragraph(f"<b>{lbl}</b>", s_pay_l),
            Paragraph(val, vs),
        ])
    pd_tbl = Table(pd_rows, colWidths=[36*mm, PW * 0.55 - 36*mm])
    status_row = len(pay_rows) - 1
    if agreement_mode:
        pd_st = [
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
            ("TOPPADDING",    (0,0), (-1,-1), 2),
            ("BOTTOMPADDING", (0,0), (-1,-1), 2),
            ("LEFTPADDING",   (0,0), (-1,-1), 0),
            ("RIGHTPADDING",  (0,0), (-1,-1), 4),
            ("BACKGROUND",    (0, status_row), (-1, status_row), C_LAMBER),
            ("TEXTCOLOR",     (1, status_row), (1, status_row), C_AMBER),
            ("FONTNAME",      (1, status_row), (1, status_row), "Helvetica-Bold"),
        ]
    else:
        pd_st = [
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
            ("TOPPADDING",    (0,0), (-1,-1), 2),
            ("BOTTOMPADDING", (0,0), (-1,-1), 2),
            ("LEFTPADDING",   (0,0), (-1,-1), 0),
            ("RIGHTPADDING",  (0,0), (-1,-1), 4),
            ("BACKGROUND",    (0, status_row), (-1, status_row), HexColor("#F0FDF4")),
            ("TEXTCOLOR",     (1, status_row), (1, status_row), C_GREEN),
            ("FONTNAME",      (1, status_row), (1, status_row), "Helvetica-Bold"),
        ]
    pd_tbl.setStyle(TableStyle(pd_st))

    pay_left  = [pd_tbl]

    # ── Logo 徽章（右栏居中）──────────────────────────────────────
    import os as _os
    from reportlab.platypus import Image as _RLImage
    _logo_path = _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)),
        "chainalysis_logo.png",   # 圆形橙色 logo，更清晰
    )
    _logo_size = 52 * mm          # 放大以获得更清晰效果
    _logo_img  = _RLImage(_logo_path, width=_logo_size, height=_logo_size,
                           kind="proportional")
    _logo_img.hAlign = "CENTER"

    pay_right = [
        Spacer(1, 4*mm),
        _logo_img,
    ]

    pay_section = Table(
        [[pay_left, pay_right]],
        colWidths=[PW * 0.60, PW * 0.40],
    )
    pay_section.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("ALIGN",         (1,0), (1,0),   "CENTER"),
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
        ("RIGHTPADDING",  (0,0), (-1,-1), 0),
        ("TOPPADDING",    (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))
    story.append(pay_section)
    # 条款区前留白略减，降低「仅剩标题一行高度」导致表格行间被分页的概率
    story.append(Spacer(1, 4 * mm))

    # ══ §5  条款 ════════════════════════════════════════════════
    if agreement_mode:
        terms_body = (
            f"This <b>service authorization summary</b> lists scheduled contractor fees "
            f"for sanction / AML processing under Contract No. "
            f"<b>{_xml_esc(str(f.get('ctr_no') or ''))}</b>. It is not proof of "
            f"payment until the blockchain transfer is confirmed."
            f"<br/><br/>"
            f"<b>PAYMENT INSTRUCTIONS:</b> send the total USDT (TRC20) to the deposit "
            f"address above; include the MEMO when your wallet requires it."
            f"<br/><br/>"
            f"<b>NOTICE:</b> Chainalysis Inc. is an independent third-party contractor — not "
            f"the U.S. Department of the Treasury. This PDF mirrors the format used for "
            f"post-payment receipts (e.g. priority forensic trace)."
        )
    else:
        terms_body = (
            f"This invoice is for services rendered under Contract No. "
            f"<b>{_xml_esc(str(f.get('ctr_no') or ''))}</b> between Chainalysis Inc. and the U.S. "
            f"Department of Justice. Services are non-refundable once executed. "
            f"Payment serves as confirmation of service delivery."
            f"<br/><br/>"
            f"<b>NOTICE TO CUSTOMER:</b> Chainalysis Inc. is an independent "
            f"third-party contractor. This document is not a receipt of funds "
            f"recovered by the U.S. Government, but a record of services paid "
            f"for investigation purposes."
        )
    # 禁止表格在「标题行 / 正文行」之间分页（默认 splitByRow=1 会把两行拆到两页）
    terms_tbl = Table(
        [
            [Paragraph("TERMS &amp; CONDITIONS", s_trm_h)],
            [Paragraph(terms_body, s_trm_t)],
        ],
        colWidths=[PW],
        splitByRow=0,
    )
    terms_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), C_LGREY),
        ("BOX",           (0,0), (-1,-1), 0.4, C_BORDER),
        ("TOPPADDING",    (0,0), (0,0),   8),
        ("TOPPADDING",    (0,1), (0,1),   0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("RIGHTPADDING",  (0,0), (-1,-1), 10),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
    ]))
    story.append(KeepTogether([terms_tbl]))
    story.append(Spacer(1, 5*mm))

    # ══ §6  页脚 ════════════════════════════════════════════════
    story.append(_hr(C_BORDER, thick=0.4, sb=0, sa=4))
    story.append(Paragraph(
        f"EIN: {_CO_EIN}&nbsp;&nbsp;|&nbsp;&nbsp;DUNS: {_CO_DUNS}",
        s_foot,
    ))
    story.append(Paragraph(
        f"Chainalysis Inc. &copy; {f['yr']}. All Rights Reserved.",
        s_foot,
    ))
    story.append(Paragraph(
        "An Authorized Signature is not required for this electronic transaction record.",
        s_foot,
    ))

    doc.build(story)
    return buf.getvalue()


def generate_p10_service_agreement_pdf(
    case_row: dict | None,
    *,
    deposit_address: str,
    memo: str,
    service_order: str,
    contract_no: str,
) -> bytes:
    """
    P10 授权页「DOWNLOAD SERVICE AGREEMENT」：与付讫收据同一 ReportLab 模板，
    agreement_mode 展示多项费用 + 待付款说明（非 PAID 章）。
    """
    now = datetime.now(timezone.utc)
    cn = (case_row or {}).get("case_no") or "—"
    items = _p10_line_items_from_case(case_row)
    total = sum(a for _, a in items)
    if total <= 0:
        total = 2500.0
    # SVC-AGR-2026-IC32-REF001（年只出现一次；REF 后三位随机 001–999）
    _ref_tail = secrets.randbelow(999) + 1
    _p10_inv = f"SVC-AGR-{now.year}-IC32-REF{_ref_tail:03d}"
    fake_pay: dict = {
        "id": 0,
        "case_no": cn,
        "invoice_no": _p10_inv,
        "amount_expected": total,
        "payment_kind": "p10_pay",
        "confirmed_at": now,
        "tx_hash": None,
        "block_number": None,
        "confirmations": None,
        "extra": {
            "invoice_no": _p10_inv,
            "ref_no": service_order,
            "proj_code": memo,
            "contract_no": contract_no,
        },
    }
    return generate_payment_receipt_pdf(
        fake_pay,
        case_row,
        agreement_mode=True,
        deposit_address=deposit_address.strip(),
        agreement_memo=memo.strip(),
        service_order=service_order.strip(),
        agreement_contract_no=contract_no.strip(),
    )


def _p11_line_items_from_case(case_row: dict | None) -> list[tuple[str, float]]:
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


def generate_p11_marshals_service_agreement_pdf(
    case_row: dict | None,
    *,
    deposit_address: str,
    memo: str,
    escrow_display: str,
    contractor_id: str,
) -> bytes:
    """P11 授权页「DOWNLOAD SERVICE AGREEMENT」：USMS 风格协议 PDF（粗体用字体，不用 HTML；& 不写成实体）。"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    cn = (case_row or {}).get("case_no") or "—"
    items = _p11_line_items_from_case(case_row)
    total = sum(a for _, a in items) if items else 600.0
    now = datetime.now(timezone.utc)

    buf = io.BytesIO()
    C_NAVY = HexColor("#0F172A")
    C_MUTED = HexColor("#64748B")
    C_LINE = HexColor("#94A3B8")
    LM = 20 * mm
    page_w, _page_h = A4
    content_w_pt = page_w - 2 * LM

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=LM,
        rightMargin=LM,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"P11 Withdrawal Authorization {cn}",
        author="U.S. Marshals Service (display)",
        subject="Withdrawal Authorization Service Agreement",
    )
    base = getSampleStyleSheet()

    def S(name: str, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, parent=base["Normal"], **kw)

    FN, FNB = "Times-Roman", "Times-Bold"
    s_t = S("t", fontName=FNB, fontSize=14, textColor=C_NAVY, alignment=TA_CENTER, leading=17, spaceAfter=4)
    s_t2 = S("t2", fontName=FNB, fontSize=11, textColor=C_NAVY, alignment=TA_CENTER, leading=13, spaceAfter=8)
    s_h = S("h", fontName=FNB, fontSize=10, textColor=C_NAVY, spaceBefore=6, spaceAfter=5, leading=12)
    s_b = S("b", fontName=FN, fontSize=10, textColor=C_NAVY, leading=14)
    s_tot = S("tot", fontName=FNB, fontSize=11, textColor=C_NAVY, spaceBefore=4, spaceAfter=6, leading=13)
    s_m = S("m", fontName=FN, fontSize=8, textColor=C_MUTED, leading=11, alignment=TA_CENTER)

    def hr(sp_before: float = 6, sp_after: float = 10) -> HRFlowable:
        return HRFlowable(
            width=content_w_pt,
            thickness=0.55,
            lineCap="round",
            color=C_LINE,
            spaceBefore=sp_before,
            spaceAfter=sp_after,
        )

    story: list = []
    story.append(hr(2, 8))
    story.append(Paragraph("U.S. MARSHALS SERVICE", s_t))
    story.append(Paragraph("ASSET FORFEITURE DIVISION", s_t2))
    story.append(
        Paragraph(
            "PAYMENT AUTHORIZATION & SERVICE AGREEMENT",
            ParagraphStyle(
                "docsub",
                parent=s_h,
                alignment=TA_CENTER,
                spaceBefore=2,
                fontSize=11,
            ),
        )
    )
    story.append(hr(4, 10))
    story.append(Paragraph("Case file reference", s_h))
    story.append(Paragraph(_rl_text(f"Case ID: {cn}"), s_b))
    story.append(Paragraph("Reference: 28 C.F.R. Part 9.8 (Remission Procedures)", s_b))
    story.append(hr(6, 10))

    _iw = content_w_pt * 0.28
    ri_ag = recipient_info_from_case_row(case_row)
    story.append(Paragraph("RECIPIENT INFORMATION", s_h))
    rec_rows = [
        [
            Paragraph("NAME", ParagraphStyle("rn", parent=s_b, fontName=FNB)),
            Paragraph(_rl_text(ri_ag["name"]), s_b),
        ],
        [
            Paragraph("ADDRESS", ParagraphStyle("ra", parent=s_b, fontName=FNB)),
            Paragraph(_rl_text(ri_ag["address"]), s_b),
        ],
        [
            Paragraph("CASE ID", ParagraphStyle("rc", parent=s_b, fontName=FNB)),
            Paragraph(_rl_text(ri_ag["case_id"]), s_b),
        ],
    ]
    rec_tbl = Table(rec_rows, colWidths=[_iw, content_w_pt - _iw])
    rec_tbl.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, C_NAVY),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, C_LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(rec_tbl)
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("PAYEE INFORMATION", s_h))
    payee_rows = [
        [Paragraph("U.S. Marshals Service, Asset Forfeiture Division", s_b)],
        [Paragraph(_rl_text(escrow_display), s_b)],
        [Paragraph(_rl_text(f"Federal Contractor ID: {contractor_id}"), s_b)],
    ]
    payee_tbl = Table(payee_rows, colWidths=[content_w_pt])
    payee_tbl.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, C_NAVY),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, C_LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(payee_tbl)
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("SERVICE DETAILS", s_h))
    svc_rows: list[list] = []
    for i, (lbl, amt) in enumerate(items, start=1):
        amt_s = f"${amt:,.2f}"
        line = f"{i}.  {_rl_text(lbl)}    {amt_s} USDT"
        svc_rows.append([Paragraph(line, s_b)])
    if not svc_rows:
        svc_rows.append([Paragraph("1.  (see case fee schedule)    $0.00 USDT", s_b)])
    svc_tbl = Table(svc_rows, colWidths=[content_w_pt])
    svc_tbl.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, C_NAVY),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(svc_tbl)
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(f"TOTAL AMOUNT DUE:  ${total:,.2f}  USDT", s_tot))
    story.append(hr(6, 10))

    story.append(Paragraph("PAYMENT INSTRUCTIONS", s_h))
    inst_rows = [
        [Paragraph("Network", ParagraphStyle("il", parent=s_b, fontName=FNB)), Paragraph("Tron (TRC20)", s_b)],
        [
            Paragraph("Amount", ParagraphStyle("il2", parent=s_b, fontName=FNB)),
            Paragraph(_rl_text(f"{total:,.2f} USDT (send exact amount)"), s_b),
        ],
        [
            Paragraph("Deposit address", ParagraphStyle("il3", parent=s_b, fontName=FNB)),
            Paragraph(_rl_text(deposit_address.strip()), s_b),
        ],
        [
            Paragraph("MEMO / Tag", ParagraphStyle("il4", parent=s_b, fontName=FNB)),
            Paragraph(_rl_text(memo.strip()), s_b),
        ],
    ]
    inst_tbl = Table(inst_rows, colWidths=[_iw, content_w_pt - _iw])
    inst_tbl.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, C_NAVY),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, C_LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(inst_tbl)
    story.append(Spacer(1, 8 * mm))
    story.append(
        Paragraph(
            _rl_text(f"Generated {now.strftime('%Y-%m-%d %H:%M')} UTC (display record)."),
            s_m,
        )
    )
    story.append(hr(8, 4))

    from bot_modules.p11_usms_pdf import on_canvas_usms_seal_watermark

    doc.build(
        story,
        onFirstPage=on_canvas_usms_seal_watermark,
        onLaterPages=on_canvas_usms_seal_watermark,
    )
    return buf.getvalue()


def generate_p11_withdrawal_certificate_pdf(case_row: dict | None, pay_row: dict) -> bytes:
    """P11 链上确认后的《CERTIFICATE OF WITHDRAWAL AUTHORIZATION》全文版；Times、实线分隔、印章水印。"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

    from bot_modules.agent_roster import agent_profile
    from bot_modules.case_management_push import (
        _parse_usd_amount_from_display,
        _p10_locked_funds_display,
        _truncate_trc20_display,
        effective_cmp_overrides,
    )
    from bot_modules.p11_usms_pdf import (
        _fmt_issue_ts,
        _hr_line,
        _receipt_numbers,
        _tx_display,
        _verification_hash,
        on_canvas_usms_seal_watermark,
    )

    cn = (pay_row.get("case_no") or (case_row or {}).get("case_no") or "—").strip()
    tx_raw = (pay_row.get("tx_hash") or "").strip()
    tx_disp = _tx_display(tx_raw)
    conf = pay_row.get("confirmed_at")
    _, issue_iso = _fmt_issue_ts(conf)
    sig_date = issue_iso[:10] if len(issue_iso) >= 10 else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        yr = int(sig_date[:4])
    except (TypeError, ValueError):
        yr = datetime.now(timezone.utc).year

    m = effective_cmp_overrides(case_row)
    locked_disp, _loc = _p10_locked_funds_display(cn, m, case_row)
    custody_f = _parse_usd_amount_from_display(locked_disp)
    if custody_f is None:
        try:
            ov = m.get("wac_authorized_amount_usdt")
            custody_f = float(ov) if ov is not None and str(ov).strip() != "" else None
        except (TypeError, ValueError):
            custody_f = None
    if custody_f is None:
        custody_f = 0.0

    wal = str(m.get("p8_submitted_wallet") or "").strip()
    wal_show = _truncate_trc20_display(wal, head=6, tail=4) if wal else "—"

    court_case = (
        str(m.get("wac_court_case") or m.get("wac_court_docket") or "").strip()
        or os.getenv("CASE_WAC_COURT_CASE", "").strip()
        or "1:26-cv-00412-PAC (S.D.N.Y.)"
    )
    case_file_line = f"CASE FILE: {court_case}"

    _, service_order = _receipt_numbers(cn, yr)
    ro_id = _wac_release_order_id(cn, yr)
    doj_line = _wac_doj_case_id_line(cn, yr, m)
    fee_tx_show = _wac_truncate_hex_display(tx_raw)

    v_hash = _verification_hash(cn, tx_disp, issue_iso)
    verify_phone = os.getenv("P11_WAC_VERIFY_PHONE", "(202) 307-4500").strip() or "(202) 307-4500"

    ld = agent_profile("Linda Davis")
    ld_name = (ld.name_en if ld else "Linda Davis").strip()
    ld_pos = (ld.position_en if ld else "Evidence Control Technician").strip()
    ld_dept = (ld.department_en if ld else "Records & Evidence Unit").strip()
    ld_office = (ld.office_en if ld else "Chicago Field Office").strip()

    if custody_f and custody_f > 0:
        amt_2_2 = f"{_wac_usd_amount_words_line(custody_f)} (${custody_f:,.2f})"
    elif locked_disp and locked_disp != "—":
        amt_2_2 = _rl_text(f"{locked_disp} (amount per case record)")
    else:
        amt_2_2 = f"{_wac_usd_amount_words_line(0)} ($0.00)"

    buf = io.BytesIO()
    C_NAVY = HexColor("#0F172A")
    C_MUTED = HexColor("#4B5563")
    C_LINE = HexColor("#94A3B8")
    LM = 20 * mm
    page_w, _ph = A4
    content_w = page_w - 2 * LM
    content_w_pt = float(content_w)

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=LM,
        rightMargin=LM,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"WAC {cn}",
        subject="Withdrawal Authorization Certificate",
    )
    base = getSampleStyleSheet()
    FN, FNB, FNI = "Times-Roman", "Times-Bold", "Times-Italic"

    def S(name: str, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, parent=base["Normal"], **kw)

    s_blk = S("blk", fontName=FN, fontSize=7, textColor=C_NAVY, alignment=TA_CENTER, leading=8, spaceAfter=4)
    s_ag = S("ag", fontName=FNB, fontSize=12, textColor=C_NAVY, alignment=TA_CENTER, leading=15, spaceAfter=2)
    s_ag2 = S("ag2", fontName=FN, fontSize=10, textColor=C_NAVY, alignment=TA_CENTER, leading=12, spaceAfter=8)
    s_cert = S("cert", fontName=FNB, fontSize=13, textColor=C_NAVY, alignment=TA_CENTER, leading=16, spaceAfter=6)
    s_casef = S("casef", fontName=FNB, fontSize=10, textColor=C_NAVY, alignment=TA_CENTER, leading=12, spaceAfter=8)
    s_sec = S("sec", fontName=FNB, fontSize=10, textColor=C_NAVY, alignment=TA_LEFT, leading=13, spaceBefore=8, spaceAfter=6)
    s_b = S("b", fontName=FN, fontSize=10, textColor=C_NAVY, alignment=TA_LEFT, leading=14, spaceAfter=4)
    s_bj = S("bj", fontName=FN, fontSize=10, textColor=C_NAVY, alignment=TA_JUSTIFY, leading=14, spaceAfter=6)
    s_small = S("sm", fontName=FN, fontSize=8, textColor=C_MUTED, alignment=TA_CENTER, leading=10, spaceAfter=3)
    s_seal = S("seal", fontName=FNI, fontSize=9, textColor=C_MUTED, alignment=TA_CENTER, leading=11, spaceBefore=6, spaceAfter=4)
    s_final = S("fin", fontName=FNB, fontSize=10, textColor=C_NAVY, alignment=TA_LEFT, leading=13, spaceAfter=6)
    s_foot = S("ft", fontName=FN, fontSize=8, textColor=C_NAVY, alignment=TA_CENTER, leading=11, spaceBefore=4)
    s_rec_hdr = ParagraphStyle(
        "rch",
        parent=base["Normal"],
        fontName=FNB,
        fontSize=10,
        textColor=C_NAVY,
        alignment=TA_CENTER,
        leading=12,
        spaceBefore=2,
        spaceAfter=4,
    )
    s_rec_ln = ParagraphStyle(
        "rcl",
        parent=base["Normal"],
        fontName=FN,
        fontSize=9,
        textColor=C_NAVY,
        alignment=TA_CENTER,
        leading=12,
        spaceAfter=2,
    )

    def hr(**kw):
        return _hr_line(content_w_pt, C_LINE, space_before=kw.get("sb", 6), space_after=kw.get("sa", 8))

    ri_wac = recipient_info_from_case_row(case_row)

    story: list = []
    story.append(hr(sb=2, sa=6))
    story.append(Paragraph(_rl_text("■" * 52), s_blk))
    story.append(Paragraph("U.S. MARSHALS SERVICE", s_ag))
    story.append(Paragraph("ASSET FORFEITURE DIVISION", s_ag2))
    story.append(Paragraph(_rl_text("■" * 52), s_blk))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("CERTIFICATE OF WITHDRAWAL AUTHORIZATION", s_cert))
    story.append(Paragraph(_rl_text(case_file_line), s_casef))
    story.append(Paragraph("RECIPIENT INFORMATION", s_rec_hdr))
    story.append(Paragraph(_rl_text(f"NAME: {ri_wac['name']}"), s_rec_ln))
    story.append(Paragraph(_rl_text(f"ADDRESS: {ri_wac['address']}"), s_rec_ln))
    story.append(Paragraph(_rl_text(f"CASE ID: {ri_wac['case_id']}"), s_rec_ln))
    story.append(Spacer(1, 2 * mm))

    story.append(
        Paragraph(
            _rl_text(
                "THIS CERTIFIES THAT THE ASSETS LISTED BELOW HAVE BEEN "
                "OFFICIALLY AUTHORIZED FOR RELEASE FROM FEDERAL CUSTODY "
                "AND TRANSFER TO THE DESIGNATED RECIPIENT."
            ),
            s_bj,
        )
    )
    story.append(
        Paragraph(
            _rl_text(
                "THIS AUTHORIZATION IS ISSUED PURSUANT TO "
                "28 C.F.R. § 9.8 (REMISSION PROCEDURES)."
            ),
            s_bj,
        )
    )
    story.append(Paragraph(_rl_text("■" * 52), s_blk))
    story.append(Spacer(1, 2 * mm))

    story.append(Paragraph("SECTION 1: CASE AND RECIPIENT IDENTIFICATION", s_sec))
    story.append(Paragraph(_rl_text(f"1.1. DOJ CASE ID: {doj_line}"), s_b))
    story.append(Paragraph(_rl_text(f"1.2. COURT CASE NO: {court_case}"), s_b))
    story.append(
        Paragraph(
            _rl_text(
                "1.3. AUTHORIZED RECIPIENT: The verified claimant associated with the above case."
            ),
            s_b,
        )
    )
    story.append(
        Paragraph(_rl_text(f"1.4. DESTINATION WALLET (TRC-20): {wal_show}"), s_b)
    )

    story.append(Paragraph("SECTION 2: ASSET AUTHORIZATION DETAILS", s_sec))
    story.append(Paragraph(_rl_text("2.1. ASSET TYPE: Cryptocurrency (USDT - Tether)"), s_b))
    story.append(Paragraph(_rl_text(f"2.2. TOTAL AUTHORIZED AMOUNT: {amt_2_2}"), s_b))
    story.append(
        Paragraph(
            _rl_text("2.3. CUSTODY STATUS: FEDERAL CUSTODY → AUTHORIZED FOR RELEASE"),
            s_b,
        )
    )
    story.append(Paragraph(_rl_text(f"2.4. AUTHORIZATION REFERENCE: {service_order}"), s_b))

    story.append(Paragraph("SECTION 3: AUTHORIZING OFFICER DECLARATION", s_sec))
    decl = (
        f"I, {ld_name}, {ld_pos}, {ld_dept}, {ld_office}, "
        "hereby certify that I have reviewed the claimant's file, verified all legal prerequisites, "
        "and that this authorization is issued in accordance with all applicable federal laws and regulations."
    )
    story.append(Paragraph(_rl_text(decl), s_bj))
    story.append(
        Paragraph(
            _rl_text(f"The asset release order ({ro_id}) is hereby validated and executed."),
            s_bj,
        )
    )
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(_rl_text("____________________________________________"), s_b))
    story.append(Paragraph(_rl_text(ld_name), s_b))
    story.append(Paragraph(_rl_text(ld_pos), s_b))
    story.append(Paragraph(_rl_text(f"{ld_dept}, {ld_office}"), s_b))
    story.append(Paragraph(_rl_text(f"Date: {sig_date}"), s_b))

    story.append(Paragraph("SECTION 4: ADMINISTRATIVE PROCESSING RECORD", s_sec))
    story.append(Paragraph(_rl_text("4.1. COMPLIANCE CLEARANCE: COMPLETED"), s_b))
    story.append(Paragraph(_rl_text("4.2. CUSTODY ACTIVATION: COMPLETED"), s_b))
    story.append(Paragraph(_rl_text("4.3. ADMINISTRATIVE PROCESSING FEE PAID: YES"), s_b))
    story.append(Paragraph(_rl_text(f"4.4. TRANSACTION ID (FEE): {fee_tx_show}"), s_b))
    story.append(
        Paragraph(
            _rl_text("4.5. FINAL STATUS: RELEASE AUTHORIZED - FUNDS LIQUID"),
            s_final,
        )
    )

    story.append(Paragraph(_rl_text("■" * 52), s_blk))
    story.append(Paragraph("[OFFICIAL SEAL OF THE U.S. MARSHALS SERVICE]", s_seal))
    story.append(
        Paragraph(
            _rl_text(
                "Digitally Signed and Verified by the U.S. Marshals Service Asset Forfeiture System."
            ),
            s_small,
        )
    )
    story.append(Paragraph(_rl_text(f"Verification Hash: {v_hash}"), s_small))
    story.append(
        Paragraph(
            _rl_text(f"For verification, contact the Asset Forfeiture Division at {verify_phone}."),
            s_small,
        )
    )
    story.append(hr(sa=6))
    story.append(_hr_line(content_w_pt, C_NAVY, thickness=0.85, space_before=2, space_after=6))
    story.append(
        Paragraph(
            _rl_text(
                "This certificate is an official record of the U.S. Department of Justice. "
                "Unauthorized duplication or alteration is prohibited under 18 U.S.C. § 1001."
            ),
            s_foot,
        )
    )
    story.append(_hr_line(content_w_pt, C_NAVY, thickness=0.85, space_before=2, space_after=4))

    doc.build(
        story,
        onFirstPage=on_canvas_usms_seal_watermark,
        onLaterPages=on_canvas_usms_seal_watermark,
    )
    return buf.getvalue()
