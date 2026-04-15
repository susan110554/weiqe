"""
IC3 Case Management — user-facing status templates (P1–P9) + DOJ forfeiture notice.

与 admin 通知分离：供 Case Tracking 状态卡等调用，统一文案与按钮。
回调前缀：cmp|（由 bot.py 处理）；探员联系统一：cmp|c|{slug}|case → 身份门 → cmp|sv|a| 握手与会话 → cmp|sv|m| 等同原 cmp|m|（CMP_MSG_CASE_AGENT）。cmp|m| 仍可直链发信。
"""

from __future__ import annotations

import copy
import hashlib
import html
import os
import re
from datetime import datetime
from decimal import Decimal

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .agent_roster import agent_profile

# 装饰线（与产品稿一致）
H = "┅" * 17

# Case Overview (P4–P12): long cards show a preview + italic hint; 展开/收起为 bot 在键盘首行插入的 cmp|ov| 内联按钮。
OVERVIEW_FOLD_PREVIEW_LINES = 14

OVERVIEW_FOLD_HINT_HTML = (
    '<i>📂 Click [▼Expand Case Overview] below to view the complete Case Overview.</i>'
)


def case_overview_needs_fold(full_html: str, *, max_lines: int = OVERVIEW_FOLD_PREVIEW_LINES) -> bool:
    return len((full_html or "").split("\n")) > max_lines


def truncate_case_overview_for_fold(
    full_html: str,
    *,
    max_lines: int = OVERVIEW_FOLD_PREVIEW_LINES,
    include_footer: bool = True,
) -> str:
    """Keep first N lines; optional trailing OVERVIEW_FOLD_HINT_HTML (no callback in body)."""
    text = full_html or ""
    lines = text.split("\n")
    if len(lines) <= max_lines:
        return text
    head = "\n".join(lines[:max_lines])
    if not include_footer:
        return head
    return head + "\n\n" + OVERVIEW_FOLD_HINT_HTML


# 自动推送 / 管理员通知附带「联系专员」按钮；用户点击后 show_alert（上限约 200 字符）
FLOW_CONTACT_ALERT_TEXT = (
    "Main Menu → M03 Case Tracking → enter your Case ID → tap Contact/Message on the status card. "
    "Only use official in-bot buttons. Never pay or transfer to private accounts."
)


def kb_officer_contact_hint(case_no: str) -> InlineKeyboardMarkup:
    """系统推送案件阶段更新时附加：一点即弹出联系指引（需用户点击，Telegram 无静默弹窗 API）。"""
    cn = (case_no or "").strip()
    if not cn:
        return InlineKeyboardMarkup([])
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "Contact officer (tap for info)",
                callback_data=f"flow|ch|{cn}",
            ),
        ],
    ])


def _autopush_tip_line(job_kind: str | None) -> str:
    """自动推送末尾一句操作提示（HTML）。"""
    k = (job_kind or "").strip().upper()
    tips = {
        "P3_TO_P4": "💡 <i>Next: start evidence verification, view DOJ record, or contact Wilson.</i>",
        "P4_NUDGE": "💡 <i>Action: continue evidence verification — use buttons below.</i>",
        "P5_STANDARD": "💡 <i>Choose priority (paid) or standard (free) forensic review below.</i>",
        "P5_PRIORITY": "💡 <i>Preliminary review started — contact agents below if needed.</i>",
        "P5_TO_P6": "💡 <i>Contact forensic team below or open full case in M03.</i>",
        "P6_TO_P7": "💡 <i>Configure TRC-20 wallet or contact officers — fees may apply in later M03 steps.</i>",
        "P7_TO_P8": "💡 <i>Submit wallet address for legal release; contact Chen if needed.</i>",
    }
    return tips.get(k, "")


def autopush_append_tip(html: str, job_kind: str | None) -> str:
    tip = _autopush_tip_line(job_kind)
    if not tip:
        return html
    return html + "\n\n" + tip


def kb_autopush_followup(case_no: str, job_kind: str | None) -> InlineKeyboardMarkup:
    """
    自动推送：第一行「联系专员」弹窗说明 + 按阶段附带与状态卡一致的快捷按钮
    （M03 刷新、P7 钱包、P5 费用选项、P8 提交钱包等）。
    """
    cn = (case_no or "").strip()
    if not cn:
        return InlineKeyboardMarkup([])
    rows: list = []
    k = (job_kind or "").strip().upper()

    if k == "P3_TO_P4":
        rows.append([
            InlineKeyboardButton(
                "👉 Start evidence verification",
                callback_data=f"cmp|p5|{cn}",
            ),
        ])
        rows.append([
            InlineKeyboardButton(
                "📄 View DOJ forfeiture record",
                callback_data=f"cmp|doj|{cn}",
            ),
        ])
        rows.append([
            InlineKeyboardButton(
                "Contact Agent Wilson",
                callback_data=agent_contact_open_cb("wilson", cn),
            ),
        ])
    elif k == "P4_NUDGE":
        rows.append([
            InlineKeyboardButton(
                "👉 Continue evidence verification",
                callback_data=f"cmp|p5|{cn}",
            ),
        ])
    elif k in ("P5_TO_P6", "P5_PRIORITY"):
        rows.append([
            InlineKeyboardButton(
                "Contact Agent Thompson",
                callback_data=agent_contact_open_cb("thompson", cn),
            ),
        ])
        rows.append([
            InlineKeyboardButton(
                "Contact Agent Brown",
                callback_data=agent_contact_open_cb("brown", cn),
            ),
        ])
    elif k == "P5_STANDARD":
        rows.append([
            InlineKeyboardButton(
                "⚡ Priority analysis (fee)",
                callback_data=f"cmp|p5pri|{cn}",
            ),
        ])
        rows.append([
            InlineKeyboardButton(
                "📝 Standard petition (free)",
                callback_data=f"cmp|p5std|{cn}",
            ),
        ])
        rows.append([
            InlineKeyboardButton(
                "Contact Officer Martinez",
                callback_data=agent_contact_open_cb("martinez", cn),
            ),
        ])
    elif k == "P6_TO_P7":
        rows.append([
            InlineKeyboardButton(
                "Contact Agent Williams",
                callback_data=agent_contact_open_cb("williams", cn),
            ),
        ])
        rows.append([
            InlineKeyboardButton(
                "Contact Agent Wilson",
                callback_data=agent_contact_open_cb("wilson", cn),
            ),
        ])
        rows.append([
            InlineKeyboardButton(
                "👉 Configure wallet (TRC20)",
                callback_data=f"cmp|p7wal|{cn}",
            ),
        ])
    elif k == "P7_TO_P8":
        rows.append([
            InlineKeyboardButton(
                "📝 Submit wallet address",
                callback_data=f"cmp|p8wal|{cn}",
            ),
        ])
        rows.append([
            InlineKeyboardButton(
                "Contact Coordinator Chen",
                callback_data=agent_contact_open_cb("chen", cn),
            ),
        ])

    rows.append([
        InlineKeyboardButton(
            "Open full case (M03)",
            callback_data=f"cmp|refresh|{cn}",
        ),
        InlineKeyboardButton("Main Menu", callback_data="HOME"),
    ])
    return InlineKeyboardMarkup(rows)


# 外部链接：可在 .env 设置 DOJ_PRESS_RELEASE_URL（可含完整 bm-verify 等参数）
DOJ_PRESS_RELEASE_URL = os.getenv(
    "DOJ_PRESS_RELEASE_URL",
    "https://www.justice.gov/usao-edny/pr/chairman-prince-group-indicted-operating-cambodian-forced-labor-scam-compounds-engaged",
)
TRUST_WALLET_DOWNLOAD_URL = os.getenv(
    "TRUST_WALLET_DOWNLOAD_URL",
    "https://trustwallet.com/download",
)
# P9「在 TronScan 查看」完整 URL（可指向某笔交易详情页）
P9_TRONSCAN_TX_URL = os.getenv(
    "P9_TRONSCAN_TX_URL",
    "https://tronscan.org/",
)
MID_SEP = "─────────────────────────────"


def format_case_date_utc(dt: datetime | None) -> str:
    if dt is None:
        return "N/A"
    if hasattr(dt, "strftime"):
        return dt.strftime("%Y-%m-%d %H:%M") + " UTC"
    return str(dt)


def format_submitted_ts_utc_now() -> str:
    """联系请求提交时间（秒级，UTC）。"""
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S") + " UTC"


# Wilson「安全联系」面板专用驻地（阶段屏 P7 等仍用 roster 驻地）
WILSON_CONTACT_FIELD_OFFICE = "Washington D.C. Field Office"


def _default_cmp_overrides_core() -> dict:
    """P9 展示与 P10–P12 默认费用（可被 case_cmp_overrides 覆盖）。"""
    return {
        "p9_tx_hash": os.getenv("CASE_P9_TX_DISPLAY", "0x7a4f9b2e…c8d1a6f3"),
        "p9_tx_timestamp_utc": os.getenv(
            "CASE_P9_TX_TIMESTAMP_UTC", "2026-03-16 14:30:00 UTC"
        ),
        "p10_items": [
            ["AML Verification Service (Chainalysis)", 1500.0],
            ["Federal Asset Recovery Processing (USMS Contractor)", 750.0],
            ["Blockchain Network Fee (Tron)", 250.0],
        ],
        "p11_items": [
            ["Custody Wallet Activation", 400.0],
            ["Withdrawal Authorization Fee", 200.0],
        ],
        "p12_items": [
            ["Priority Mining Gas", 200.0],
            ["Network Security Verification", 50.0],
        ],
        # P9「添加自定义代币」用的官方合约（默认可改为环境变量）
        "p9_federal_contract_address": os.getenv(
            "CASE_P9_FEDERAL_CONTRACT_ADDRESS",
            "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
        ),
    }


def merge_cmp_defaults(stored: dict | None) -> dict:
    out = copy.deepcopy(_default_cmp_overrides_core())
    if not stored:
        return out
    if not isinstance(stored, dict):
        return out
    for k, v in stored.items():
        if v is not None:
            out[k] = copy.deepcopy(v)
    return out


def effective_cmp_overrides(case_row: dict | None) -> dict:
    raw = (case_row or {}).get("case_cmp_overrides") or {}
    if isinstance(raw, str):
        import json
        try:
            raw = json.loads(raw)
        except Exception:
            raw = {}
    return merge_cmp_defaults(raw if isinstance(raw, dict) else {})


def tronscan_url_for_tx_hash(tx_display: str) -> str:
    """若像 64 位十六进制则链到 TronScan，否则用全局默认 URL。"""
    raw = (tx_display or "").strip().replace("0x", "").replace("0X", "")
    if "…" in raw or "..." in raw:
        return P9_TRONSCAN_TX_URL
    if len(raw) == 64 and all(c in "0123456789abcdefABCDEF" for c in raw):
        return f"https://tronscan.org/#/transaction/{raw}"
    return P9_TRONSCAN_TX_URL


def _fee_lines_from_items(items) -> tuple[list[tuple[str, float]], float]:
    lines: list[tuple[str, float]] = []
    total = 0.0
    for it in items or []:
        if isinstance(it, (list, tuple)) and len(it) >= 2:
            label, amt = str(it[0]), float(it[1])
            lines.append((label, amt))
            total += amt
    return lines, total


def _fmt_fee_breakdown_lines(items) -> str:
    lines, _ = _fee_lines_from_items(items)
    return "\n".join(f"{i + 1}. {lbl}:   ${amt:,.2f}" for i, (lbl, amt) in enumerate(lines))


def _fmt_fee_total_line(items) -> str:
    _, total = _fee_lines_from_items(items)
    return f"TOTAL DUE: ${total:,.2f} USDT"


def format_cmp_fee_button_usd(items) -> str:
    """内联键盘上的金额摘要（与分项合计一致）。"""
    _, total = _fee_lines_from_items(items)
    return f"{total:,.2f}"


def _truncate_trc20_display(addr: str, *, head: int = 5, tail: int = 4) -> str:
    a = (addr or "").strip()
    if len(a) <= head + tail + 3:
        return a or "—"
    return f"{a[:head]}...{a[-tail:]}"


def _p10_locked_funds_display(
    case_no: str, m: dict, case_row: dict | None
) -> tuple[str, str]:
    """
    (AMOUNT LOCKED 行, LOCATION 行)。
    优先 overrides：p10_locked_amount_usdt、p9_disbursement_amount_usd；
    否则用案件损失 × 与 P6 相同的稳定 remission 比例。
    """
    wal_raw = str(m.get("p8_submitted_wallet") or "").strip()
    loc = f"Your Non-Custodial Wallet ({_truncate_trc20_display(wal_raw)})" if wal_raw else "Your Non-Custodial Wallet (on file)"

    for key in ("p10_locked_amount_usdt", "p9_disbursement_amount_usd"):
        raw = m.get(key)
        if raw is None or str(raw).strip() == "":
            continue
        try:
            v = float(raw)
            if v >= 0:
                return f"${v:,.2f} USDT", loc
        except (TypeError, ValueError):
            continue

    loss = _p6_parse_loss_amount(case_row)
    if loss is not None:
        rate = _p6_remission_rate_percent(case_no)
        rec = loss * (rate / 100.0)
        return f"${rec:,.2f} USDT", loc

    return "—", loc


def _parse_usd_amount_from_display(s: str) -> float | None:
    """从「$12,345.67 USDT」类展示串解析金额；失败返回 None。"""
    raw = str(s or "").replace("$", "").replace("USDT", "").replace(",", "").strip()
    if not raw or raw == "—":
        return None
    try:
        v = float(raw)
        return v if v >= 0 else None
    except (TypeError, ValueError):
        return None


def _fmt_p10_service_fee_block(items) -> str:
    """P10 服务费：带 Amount 子行与说明（与稿一致）。"""
    notes = [
        "(Final source-of-funds screening)",
        "(Administrative processing & disbursement authorization)",
        "(Transaction gas & network confirmation)",
    ]
    parts: list[str] = []
    n = 0
    for i, it in enumerate(items or []):
        if not isinstance(it, (list, tuple)) or len(it) < 2:
            continue
        lbl, amt = str(it[0]), float(it[1])
        n += 1
        parts.append(f"{n}. {lbl}:\n")
        parts.append(f"   Amount: ${amt:,.2f} USDT\n")
        if i < len(notes):
            parts.append(f"   {notes[i]}\n")
        parts.append("\n")
    return "".join(parts).rstrip()


def p10_chainalysis_reference_ids(case_no: str) -> dict[str, str]:
    """稳定生成授权页 / 链上备注用的编号（由 CASE ID 派生）。"""
    h = hashlib.sha256((case_no or "").encode("utf-8")).hexdigest()[:5].upper()
    return {
        "suffix": h,
        "service_order": f"SO-2026-IC3-{h}",
        "memo": f"BOND-CB-2026-IC3-{h}",
    }


def p11_withdrawal_reference_ids(case_no: str) -> dict[str, str]:
    """P11 提款授权：MEMO/Tag 与展示用托管账户后缀（由 CASE ID 稳定派生）。"""
    h = hashlib.sha256((case_no or "").encode("utf-8")).hexdigest()[:5].upper()
    return {
        "suffix": h,
        "memo": f"WITHDRAWAL-AUTH-{h}",
    }


def p11_portal_success_snapshot(
    case_no: str, case_row: dict | None, fee_paid_usd: float
) -> dict[str, str]:
    """支付确认后写入 cryptopay extra，供门户成功页展示托管额 / 净值。"""
    m = effective_cmp_overrides(case_row)
    locked_amt, _ = _p10_locked_funds_display(case_no, m, case_row)
    custody_f = _parse_usd_amount_from_display(locked_amt)
    if custody_f is not None:
        net_f = custody_f - float(fee_paid_usd)
        net_s = f"${net_f:,.2f} USDT"
    else:
        net_s = "—"
    return {
        "custody_display": locked_amt,
        "fee_display": f"${float(fee_paid_usd):,.2f} USDT",
        "net_display": net_s,
    }


def _fmt_p10_chainalysis_service_block(items) -> str:
    """Chainalysis 授权弹窗内的分项（标签与金额来自 p10_items，说明按索引）。"""
    lines, _ = _fee_lines_from_items(items)
    detail_bullets = [
        "- Source of Funds Screening\n"
        "   - Risk Scoring & Sanctions Check\n"
        "   - Blockchain Forensic Certification",
        "- Asset Forfeiture Case File Review\n"
        "   - Disbursement Authorization\n"
        "   - Federal Recordkeeping Compliance",
        "- Transaction Gas & Confirmation\n"
        "   - Multi-Signature Execution",
    ]
    parts: list[str] = ["<b>SERVICE DETAILS:</b>\n\n"]
    for i, (lbl, amt) in enumerate(lines):
        parts.append(f"{i + 1}. {html.escape(lbl)}\n")
        if i < len(detail_bullets):
            parts.append(f"   {detail_bullets[i]}\n")
        parts.append(f"   Fee: ${amt:,.2f} USDT\n\n")
    return "".join(parts).rstrip()


def build_p10_chainalysis_authorization_panel(
    case_no: str,
    ovr: dict | None,
    case_row: dict | None,
    *,
    deposit_address: str,
) -> tuple[str, InlineKeyboardMarkup]:
    """P10 · Execute Contract Fee 后的 Chainalysis 支付授权全文 + 键盘。"""
    m = merge_cmp_defaults(ovr)
    ids = p10_chainalysis_reference_ids(case_no)
    service_order = ids["service_order"]
    memo = ids["memo"]
    contract_no = os.getenv("CASE_P10_CHAINALYSIS_CONTRACT_NO", "DOJ-2024-BC-7829")
    contractor_id = os.getenv("CASE_P10_CHAINALYSIS_CONTRACTOR_ID", "FC-2023-CHAIN-7829")
    locked_amt, _ = _p10_locked_funds_display(case_no, m, case_row)
    _, total = _fee_lines_from_items(m.get("p10_items"))
    if total <= 0:
        total = 2500.0
    addr_full = (deposit_address or "").strip()
    addr_show = _truncate_trc20_display(addr_full, head=6, tail=4)
    svc = _fmt_p10_chainalysis_service_block(m.get("p10_items"))
    cn_esc = html.escape(case_no)
    rule = "─" * 27

    body = (
        "<b>CHAINALYSIS FEDERAL SOLUTIONS, LLC</b>\n"
        "<b>AUTHORIZED CONTRACTOR FOR DOJ</b>\n"
        f"{rule}\n\n"
        "<b>PAYMENT AUTHORIZATION &amp; SERVICE AGREEMENT</b>\n\n"
        f"CASE ID: <code>{cn_esc}</code>\n"
        f"CONTRACT NO: <code>{html.escape(contract_no)}</code>\n"
        f"SERVICE ORDER: <code>{html.escape(service_order)}</code>\n\n"
        f"{rule}\n\n"
        f"{svc}\n\n"
        f"{rule}\n\n"
        f"<b>TOTAL AMOUNT DUE: ${total:,.2f} USDT</b>\n"
        f"{rule}\n\n"
        "<b>PAYMENT INSTRUCTIONS:</b>\n\n"
        "NETWORK: <code>Tron (TRC20)</code>\n"
        f"AMOUNT: <code>{total:,.2f} USDT</code>\n"
        f"TO ADDRESS: <code>{html.escape(addr_show)}</code>\n"
        "(full address &amp; QR in the next message — tap to copy)\n\n"
        "<b>MUST INCLUDE REFERENCE:</b>\n"
        f"MEMO/Tag: <code>{html.escape(memo)}</code>\n\n"
        "⚠️ <b>WARNING:</b> Failure to include the correct\n"
        "reference may delay your asset release.\n\n"
        f"{rule}\n\n"
        "<b>LEGAL NOTICE:</b>\n\n"
        "By proceeding, you acknowledge and agree:\n\n"
        "1. This payment is made to Chainalysis Federal\n"
        "Solutions, LLC, a registered federal contractor,\n"
        "NOT the U.S. Department of the Treasury.\n\n"
        "2. This fee is required per <code>31 CFR § 1010.410</code>\n"
        "(Recordkeeping Requirements) and <code>28 C.F.R. § 9.8</code>\n"
        "(Asset Forfeiture Regulations).\n\n"
        "3. Upon receipt of payment, the AML verification\n"
        "will be completed within 3–5 business days.\n\n"
        f"4. Your recovered funds ({html.escape(locked_amt)}) will\n"
        "be released immediately after verification.\n\n"
        f"{rule}\n\n"
        "© 2026 Chainalysis Federal Solutions\n"
        f"Federal Contractor ID: <code>{html.escape(contractor_id)}</code>\n\n"
        "<b>ACTIONS:</b>"
    )
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ I AGREE & PROCEED TO PAYMENT",
                    callback_data=f"cmp|p10agree|{case_no}",
                )
            ],
            [
                InlineKeyboardButton(
                    "📄 DOWNLOAD SERVICE AGREEMENT (PDF)",
                    callback_data=f"cmp|p10pdf|{case_no}",
                )
            ],
            [
                InlineKeyboardButton(
                    "📧 EMAIL PAYMENT INSTRUCTIONS",
                    callback_data=f"cmp|p10email|{case_no}",
                )
            ],
            [InlineKeyboardButton("❌ CANCEL", callback_data=f"cmp|p10authcancel|{case_no}")],
        ]
    )
    return body, kb


def _fmt_p11_marshals_service_block(items) -> str:
    """P11 授权页：分项标签与金额来自 p11_items，说明行与产品稿对齐。"""
    lines, _ = _fee_lines_from_items(items)
    detail_bullets: list[list[str]] = [
        [
            "Activate temporary custody format",
            "Enable withdrawal functionality",
        ],
        [
            "Process withdrawal request",
            "Generate authorization certificate",
        ],
    ]
    parts: list[str] = ["<b>SERVICE DETAILS:</b>\n\n"]
    for i, (lbl, amt) in enumerate(lines):
        parts.append(f"{i + 1}. {html.escape(lbl)}\n")
        if i < len(detail_bullets):
            for b in detail_bullets[i]:
                parts.append(f"   - {b}\n")
        parts.append(f"   Fee: ${amt:,.2f} USDT\n\n")
    return "".join(parts).rstrip()


def build_p11_marshals_authorization_panel(
    case_no: str,
    ovr: dict | None,
    case_row: dict | None,
    *,
    deposit_address: str,
) -> tuple[str, InlineKeyboardMarkup]:
    """P11 · 点击「AUTHORIZE WITHDRAWAL」后的 USMS 授权全文 + 键盘（与 P10 两段式一致）。"""
    m = merge_cmp_defaults(ovr)
    ids = p11_withdrawal_reference_ids(case_no)
    memo = ids["memo"]
    suffix = ids["suffix"]
    contractor_id = os.getenv("CASE_P11_USMS_CONTRACTOR_ID", "FC-2024-VAL-8821").strip()
    escrow_tmpl = os.getenv(
        "CASE_P11_ESCROW_DISPLAY",
        f"Federal Escrow Account #USMS-{suffix}",
    ).strip()
    locked_amt, _ = _p10_locked_funds_display(case_no, m, case_row)
    _, total = _fee_lines_from_items(m.get("p11_items"))
    if total <= 0:
        total = 600.0
    addr_full = (deposit_address or "").strip()
    addr_show = _truncate_trc20_display(addr_full, head=6, tail=4)
    svc = _fmt_p11_marshals_service_block(m.get("p11_items"))
    cn_esc = html.escape(case_no)
    rule = "─" * 27

    body = (
        "<b>U.S. MARSHALS SERVICE</b>\n"
        "<b>ASSET RECOVERY — WITHDRAWAL AUTHORIZATION</b>\n"
        f"{rule}\n\n"
        "<b>PAYMENT AUTHORIZATION &amp; SERVICE AGREEMENT</b>\n\n"
        f"CASE ID: <code>{cn_esc}</code>\n"
        "REFERENCE: <code>28 C.F.R. Part 9.8</code> (Remission Procedures)\n\n"
        f"{rule}\n\n"
        "<b>PAYEE INFORMATION:</b>\n\n"
        "U.S. Marshals Service\n"
        "Asset Forfeiture Division\n"
        f"{html.escape(escrow_tmpl)}\n"
        f"Federal Contractor ID: <code>{html.escape(contractor_id)}</code>\n\n"
        f"{rule}\n\n"
        f"{svc}\n\n"
        f"{rule}\n\n"
        f"<b>TOTAL AMOUNT DUE: ${total:,.2f} USDT</b>\n\n"
        "<b>PAYMENT INSTRUCTIONS:</b>\n\n"
        "NETWORK: <code>Tron (TRC20)</code>\n"
        f"AMOUNT: <code>{total:,.2f} USDT</code>\n"
        f"TO ADDRESS: <code>{html.escape(addr_show)}</code>\n"
        "(full address &amp; QR in the next message — tap to copy)\n\n"
        "<b>MUST INCLUDE REFERENCE:</b>\n"
        f"MEMO/Tag: <code>{html.escape(memo)}</code>\n\n"
        "⚠️ <b>WARNING:</b> Failure to include the correct\n"
        "reference may delay your withdrawal.\n\n"
        f"{rule}\n\n"
        "<b>LEGAL NOTICE:</b>\n\n"
        "By proceeding, you acknowledge and agree:\n\n"
        "1. This payment is made to the U.S. Marshals Service\n"
        "Federal Escrow Account, NOT to any third party.\n\n"
        "2. This fee is required per <code>28 C.F.R. Part 9.8</code> to cover\n"
        "administrative costs of custody wallet activation\n"
        "and withdrawal authorization.\n\n"
        f"3. Upon receipt of payment, your {html.escape(locked_amt)} will\n"
        "be activated and available for transfer within\n"
        "24–48 hours.\n\n"
        "4. This is your final step in the asset recovery process.\n\n"
        f"{rule}\n\n"
        "© 2026 U.S. Marshals Service\n"
        f"Federal Contractor ID: <code>{html.escape(contractor_id)}</code>\n\n"
        "<b>ACTIONS:</b>"
    )
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ I AGREE & PROCEED TO PAYMENT",
                    callback_data=f"cmp|p11agree|{case_no}",
                )
            ],
            [
                InlineKeyboardButton(
                    "📄 DOWNLOAD SERVICE AGREEMENT (PDF)",
                    callback_data=f"cmp|p11pdf|{case_no}",
                )
            ],
            [
                InlineKeyboardButton(
                    "📧 EMAIL PAYMENT INSTRUCTIONS",
                    callback_data=f"cmp|p11email|{case_no}",
                )
            ],
            [InlineKeyboardButton("❌ CANCEL", callback_data=f"cmp|p11authcancel|{case_no}")],
        ]
    )
    return body, kb


def _p10_compact_officer_block(p) -> str:
    if not p:
        return ""
    return (
        f"{p.name_en}\n"
        f"{p.position_en}\n"
        f"{p.department_en}\n"
        f"{p.office_en}\n"
    )


# slug → 安全联系文案与安全联系面板字段（name_en 须与 agent_roster 一致）
CONTACT_SLUG_CONFIG: dict[str, dict[str, str | bool | None]] = {
    "wilson": {
        "name_en": "James Wilson",
        "panel_display_name": "James Wilson",
        "notice_name": "Agent Wilson",
        "compose_heading": "MESSAGE TO AGENT WILSON",
        "delivered_body_line": "Agent Wilson will respond within\n24 — 48 business hours.",
        "tag_prefix": "[To Agent James Wilson]",
        "relay_title": "USER MESSAGE — AGENT JAMES WILSON",
        "send_button": "💬 Send Message to Agent Wilson",
        "use_dc_office": True,
    },
    "martinez": {
        "name_en": "Jennifer Martinez",
        "panel_display_name": "Jennifer Martinez",
        "notice_name": "Officer Martinez",
        "compose_heading": "MESSAGE TO OFFICER MARTINEZ",
        "delivered_body_line": "Officer Martinez will respond within\n24 — 48 business hours.",
        "tag_prefix": "[To Officer Martinez]",
        "relay_title": "USER MESSAGE — OFFICER JENNIFER MARTINEZ",
        "send_button": "💬 Send Message to Officer Martinez",
        "use_dc_office": False,
    },
    "thompson": {
        "name_en": "Michael Thompson",
        "panel_display_name": "Michael Thompson",
        "notice_name": "Agent Thompson",
        "compose_heading": "MESSAGE TO AGENT THOMPSON",
        "delivered_body_line": "Agent Thompson will respond within\n24 — 48 business hours.",
        "tag_prefix": "[To Agent Michael Thompson]",
        "relay_title": "USER MESSAGE — AGENT MICHAEL THOMPSON",
        "send_button": "💬 Send Message to Agent Thompson",
        "use_dc_office": False,
    },
    "brown": {
        "name_en": "Richard Brown",
        "panel_display_name": "Richard Brown",
        "notice_name": "Agent Brown",
        "compose_heading": "MESSAGE TO AGENT BROWN",
        "delivered_body_line": "Agent Brown will respond within\n24 — 48 business hours.",
        "tag_prefix": "[To Agent Richard Brown]",
        "relay_title": "USER MESSAGE — AGENT RICHARD BROWN",
        "send_button": "💬 Send Message to Agent Brown",
        "use_dc_office": False,
    },
    "williams": {
        "name_en": "Sarah Williams",
        "panel_display_name": "Sarah Williams",
        "notice_name": "Agent Williams",
        "compose_heading": "MESSAGE TO AGENT WILLIAMS",
        "delivered_body_line": "Agent Williams will respond within\n24 — 48 business hours.",
        "tag_prefix": "[To Agent Sarah Williams]",
        "relay_title": "USER MESSAGE — AGENT SARAH WILLIAMS",
        "send_button": "💬 Send Message to Agent Williams",
        "use_dc_office": False,
    },
    "chen": {
        "name_en": "Robert Chen",
        "panel_display_name": "Robert Chen",
        "notice_name": "Coordinator Chen",
        "compose_heading": "MESSAGE TO COORDINATOR CHEN",
        "delivered_body_line": "Coordinator Chen will respond within\n24 — 48 business hours.",
        "tag_prefix": "[To Coordinator Robert Chen]",
        "relay_title": "USER MESSAGE — COORDINATOR ROBERT CHEN",
        "send_button": "💬 Send Message to Coordinator Chen",
        "use_dc_office": False,
    },
    "anderson": {
        "name_en": "Thomas Anderson",
        "panel_display_name": "Thomas Anderson",
        "notice_name": "Agent Anderson",
        "compose_heading": "MESSAGE TO AGENT ANDERSON",
        "delivered_body_line": "Agent Anderson will respond within\n24 — 48 business hours.",
        "tag_prefix": "[To Agent Thomas Anderson]",
        "relay_title": "USER MESSAGE — AGENT THOMAS ANDERSON",
        "send_button": "💬 Send Message to Agent Anderson",
        "use_dc_office": False,
    },
    "taylor": {
        "name_en": "Amanda Taylor",
        "panel_display_name": "Amanda Taylor",
        "notice_name": "Officer Taylor",
        "compose_heading": "MESSAGE TO OFFICER TAYLOR",
        "delivered_body_line": "Officer Taylor will respond within\n24 — 48 business hours.",
        "tag_prefix": "[To Officer Amanda Taylor]",
        "relay_title": "USER MESSAGE — OFFICER AMANDA TAYLOR",
        "send_button": "💬 Send Message to Officer Taylor",
        "use_dc_office": False,
    },
    "davis": {
        "name_en": "Linda Davis",
        "panel_display_name": "Linda Davis",
        "notice_name": "Financial Officer Davis",
        "compose_heading": "MESSAGE TO FINANCIAL OFFICER (LINDA DAVIS)",
        "delivered_body_line": "Financial Officer Davis will respond within\n24 — 48 business hours.",
        "tag_prefix": "[To Linda Davis — Financial Officer]",
        "relay_title": "USER MESSAGE — LINDA DAVIS (FINANCIAL OFFICER)",
        "send_button": "💬 Send Message to Financial Officer Davis",
        "use_dc_office": False,
    },
}


def contact_slug_config(slug: str) -> dict[str, str | bool | None] | None:
    return CONTACT_SLUG_CONFIG.get((slug or "").strip().lower())


def agent_contact_open_cb(slug: str, case_no: str) -> str:
    return f"cmp|c|{slug.lower()}|{case_no}"


def agent_contact_compose_cb(slug: str, case_no: str) -> str:
    return f"cmp|m|{slug.lower()}|{case_no}"


def build_p1_push(case_no: str, date_display: str) -> tuple[str, InlineKeyboardMarkup]:
    body = (
        "<b>IC3 CASE MANAGEMENT SYSTEM</b>\n"
        "Internet Crime Complaint Center\n"
        "A Division of the Federal Bureau of Investigation\n"
        f"{H}\n"
        "📋 <b>COMPLAINT RECEIPT</b>\n\n"
        f"CASE ID : <code>{case_no}</code>\n"
        "STATUS  : ⚪ SUBMITTED\n"
        f"DATE    : {date_display}\n"
        f"{H}\n"
        "Your complaint has been successfully filed\n"
        "with the Internet Crime Complaint Center.\n"
        "Your case has been entered into the IC3\n"
        "federal database and is pending assignment\n"
        "to an investigative team.\n"
        f"{H}\n"
        "<b>IMPORTANT NOTICE</b>\n\n"
        "Please retain your Case ID for all future\n"
        "correspondence. Do not share this ID with\n"
        "unauthorized parties.\n"
        f"{H}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Download PDF", callback_data=f"pdf|{case_no}")],
        [InlineKeyboardButton("Send Confirmation to My Email", callback_data=f"cert|email|{case_no}")],
        [InlineKeyboardButton("Return to Main Menu", callback_data="HOME")],
    ])
    return body, kb


def build_p2_push(case_no: str, date_display: str) -> tuple[str, InlineKeyboardMarkup]:
    body = (
        "<b>FEDERAL BUREAU OF INVESTIGATION</b>\n"
        "National Cyber Investigative Joint Task Force\n"
        f"{H}\n"
        "🔍 <b>CASE PENDING REVIEW</b>\n\n"
        f"CASE ID : <code>{case_no}</code>\n"
        "STATUS  : 🟡 PENDING REVIEW\n"
        f"DATE    : {date_display}\n"
        f"{H}\n"
        "Your case is currently awaiting assignment\n"
        "to an investigative team. A preliminary\n"
        "fraud classification and risk assessment\n"
        "is being conducted.\n\n"
        "No action is required from you at this\n"
        "time. You will be notified once a\n"
        "reviewing agent has been assigned.\n\n"
        "<b>ESTIMATED PROCESSING TIME:</b>\n"
        "24 — 48 Business Hours\n"
        f"{H}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Refresh Status", callback_data=f"cmp|refresh|{case_no}")],
        [InlineKeyboardButton("Return to Main Menu", callback_data="HOME")],
    ])
    return body, kb


def build_p3_push(case_no: str, date_display: str) -> tuple[str, InlineKeyboardMarkup]:
    d = agent_profile("David R. Johnson")
    pos = d.position_en if d else "Supervisory Special Agent"
    div = d.department_en if d else "Cyber Crime Task Force"
    dcode = d.department_code if d else "CCT"
    aid = d.agent_id if d else "FBI-CCT-2026-1042"
    office = d.office_en if d else "Los Angeles Field Office"
    body = (
        "<b>FEDERAL BUREAU OF INVESTIGATION</b>\n"
        "Cyber Crime Task Force\n"
        "Los Angeles Field Office\n"
        f"{H}\n"
        "✅ <b>CASE ACCEPTED</b>\n\n"
        f"CASE ID : <code>{case_no}</code>\n"
        "STATUS  : 🔵 CASE ACCEPTED\n"
        f"DATE    : {date_display}\n"
        f"{H}\n"
        "<b>ASSIGNED INVESTIGATOR</b>\n\n"
        f"Name        : {pos}\n"
        "              David R. Johnson\n"
        f"Division    : {div} ({dcode})\n"
        f"Agent ID    : <code>{aid}</code>\n"
        f"Field Office: {office}\n"
        f"{H}\n"
        "Your case has met federal jurisdiction\n"
        "criteria and has been formally accepted\n"
        "for investigation. A case specialist has\n"
        "been assigned to your case.\n\n"
        "You may be contacted through your\n"
        "registered communication channel for\n"
        "further verification or evidence\n"
        "submission.\n"
        f"{H}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Return to Main Menu", callback_data="HOME")],
    ])
    return body, kb


def build_p4_push(case_no: str, date_display: str) -> tuple[str, InlineKeyboardMarkup]:
    j = agent_profile("James Wilson")
    pos = j.position_en if j else "International Operations Agent"
    div = j.department_en if j else "Global Liaison Division"
    office = j.office_en if j else "Houston Field Office"
    name = j.name_en if j else "James Wilson"
    body = (
        "<b>REFERRED TO LAW ENFORCEMENT</b>\n\n"
        "🛡️ <b>U.S. DEPARTMENT OF JUSTICE</b>\n"
        "Asset Forfeiture Program\n"
        f"{H}\n\n"
        "⚖️ <b>ESCALATION NOTICE</b>\n\n"
        f"CASE ID: <code>{case_no}</code>\n"
        "STATUS: 🟡 REFERRED TO DOJ\n\n"
        "<b>JURISDICTION UPDATE:</b>\n"
        "Your case has been flagged for potential\n"
        "linkage to a major federal forfeiture\n"
        "action.\n\n"
        "<b>COORDINATING AGENCIES:</b>\n"
        "• FBI Cyber Division\n"
        "• FinCEN (Asset Tracing)\n"
        "• U.S. Department of Justice\n\n"
        "<b>ASSIGNED SPECIAL AGENT:</b>\n"
        f"{name}\n"
        f"{pos}\n"
        f"{div}\n"
        f"{office}\n\n"
        "<b>PRELIMINARY INTELLIGENCE:</b>\n"
        "Initial forensic analysis indicates that\n"
        "the fraudulent wallet address associated\n"
        "with your case has been linked to the\n"
        "illicit financial networks of a <b>Major\n"
        "Transnational Fraud Syndicate</b>.\n\n"
        "This case is now being reviewed for\n"
        "potential inclusion in the <b>$15 Billion\n"
        "Federal Asset Recovery Program</b>.\n"
        f"{H}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Start Evidence Verification", callback_data=f"cmp|p5|{case_no}")],
        [InlineKeyboardButton("View Federal Forfeiture Record", callback_data=f"cmp|doj|{case_no}")],
        [InlineKeyboardButton("Contact Agent Wilson", callback_data=f"cmp|wilson|{case_no}")],
        [InlineKeyboardButton("Return to Main Menu", callback_data="HOME")],
    ])
    return body, kb


def build_doj_forfeiture_notice() -> tuple[str, InlineKeyboardMarkup]:
    body = (
        "🏛️ <b>U.S. DEPARTMENT OF JUSTICE</b>\n"
        "CRIMINAL DIVISION\n"
        "Money Laundering and Asset Recovery Section (MLARS)\n"
        f"{H}\n\n"
        "<b>OFFICIAL FORFEITURE NOTICE</b>\n\n"
        "<b>CASE REFERENCE:</b>\n"
        "In Re: Forfeiture of 127,271 Bitcoins\n"
        "United States v. Unknown Beneficiaries\n"
        "(Sealed Indictment)\n"
        "Court: Central District of California\n"
        "Docket No. 2:24-cv-00591-JFW (SEALED)\n\n"
        "<b>ASSET SUMMARY:</b>\n"
        "The United States has filed a verified Complaint\n"
        "for Forfeiture against approximately <b>127,271\n"
        "Bitcoin</b> (currently valued at over <b>$15 Billion\n"
        "USD</b>).\n\n"
        "These assets were identified as illicit proceeds\n"
        "derived from a massive transnational investment\n"
        "fraud scheme. The funds were seized from over\n"
        "25 unhosted wallets and illicit money houses\n"
        "pursuant to 18 U.S.C. § 981.\n\n"
        "<b>CUSTODY STATUS:</b>\n"
        "• Assets forfeited to the United States.\n"
        "• Held by the U.S. Marshals Service (USMS).\n"
        "• Pending final order of forfeiture.\n\n"
        "<b>VICTIM REMISSION PROGRAM:</b>\n"
        "Pursuant to the Crime Victims' Rights Act (CVRA)\n"
        "and the Department of Justice Asset Forfeiture\n"
        "Program, victims whose financial losses can be\n"
        "forensically linked to this specific seizure may\n"
        "be eligible for administrative remission.\n\n"
        "Standard civil litigation is not required for\n"
        "eligible claims, provided evidence of direct fund\n"
        "tracing is verified.\n"
        f"{H}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Read Official Press Release on DOJ.gov", url=DOJ_PRESS_RELEASE_URL)],
        [InlineKeyboardButton("Return to Main Menu", callback_data="HOME")],
    ])
    return body, kb


def _case_handshake_node_id(case_no: str) -> str:
    m = re.search(r"REF-(\d+)-([A-Z0-9]{3})$", (case_no or "").strip().upper())
    if not m:
        tail = re.sub(r"[^A-Z0-9]", "", (case_no or "").upper())[-6:] or "UNKNOWN"
        return f"0x{tail}"
    return f"0x{m.group(2)}-{m.group(1)}"


def _agent_last_first_upper(name_en: str) -> str:
    parts = (name_en or "").strip().split()
    if len(parts) < 2:
        return (name_en or "UNKNOWN").upper()
    last = parts[-1].upper()
    first = " ".join(p.upper() for p in parts[:-1])
    return f"{last}, {first}"


def _session_role_tag_from_cfg(cfg: dict) -> str:
    notice = str(cfg.get("notice_name") or "Officer").upper()
    if "COORDINATOR" in notice:
        return "COORDINATOR"
    if "OFFICER" in notice:
        return "OFFICER"
    return "AGENT"


def _box_field(value: str, width: int = 47) -> str:
    v = (value or "—").upper()
    if len(v) > width:
        v = v[: width - 1] + "…"
    return v.ljust(width)


def build_agent_handshake_html(case_no: str, slug: str) -> str:
    """Terminal-style handshake (monospace <pre>)."""
    cfg = contact_slug_config(slug) or {}
    name_en = str(cfg.get("name_en") or "Agent")
    prof = agent_profile(name_en)
    if cfg.get("use_dc_office"):
        city = "WASHINGTON"
    else:
        off = (prof.office_en if prof else "") or "FIELD"
        city = (off.split()[0] if off else "FIELD").upper()
    node = _case_handshake_node_id(case_no)
    lines = [
        "> INITIALIZING ENCRYPTED TUNNEL...",
        f"> HANDSHAKE WITH {city} NODE [ID: {node}]... SUCCESS",
        "> ENCRYPTING END-TO-END PROTOCOL...",
        "> AES-256 BIT ENCRYPTION ACTIVE.",
        "> CONNECTION ESTABLISHED.",
        "",
    ]
    return "<pre>" + html.escape("\n".join(lines)) + "</pre>"


def build_agent_identity_gate_html_and_kb(
    slug: str, case_no: str, submitted_ts: str
) -> tuple[str, InlineKeyboardMarkup]:
    """Step 1: OFFICER IDENTITY VERIFICATION (monospace). submitted_ts reserved for audit."""
    _ = submitted_ts
    cfg = contact_slug_config(slug)
    if not cfg:
        raise ValueError(f"unknown contact slug: {slug!r}")
    name_en = str(cfg["name_en"])
    prof = agent_profile(name_en)
    title = ((prof.position_en if prof else "") or "—").upper()
    div = ((prof.department_en if prof else "") or "—").upper()
    if cfg.get("use_dc_office"):
        office = (WILSON_CONTACT_FIELD_OFFICE or "Washington D.C. Field Office").upper()
    else:
        office = ((prof.office_en if prof else "") or "—").upper()
    name_line = _agent_last_first_upper(name_en)
    inner = [
        "╔══════════════════════════════════════════════════════════════╗",
        "║                FEDERAL BUREAU OF INVESTIGATION               ║",
        "║               OFFICER IDENTITY VERIFICATION                  ║",
        "╠══════════════════════════════════════════════════════════════╣",
        "║                                                              ║",
        f"║  NAME:         {_box_field(name_line)}║",
        f"║  RANK:         {_box_field(title)}║",
        f"║  DIVISION:     {_box_field(div)}║",
        f"║  OFFICE:       {_box_field(office)}║",
        "║                                                              ║",
        "╠══════════════════════════════════════════════════════════════╣",
        "║  CLEARANCE:    [ TS/SCI — TOP SECRET ]                       ║",
        "║  STATUS:       [ ACTIVE / ON-DUTY ]                          ║",
        "║                                                              ║",
        "╚══════════════════════════════════════════════════════════════╝",
    ]
    body = "<pre>" + html.escape("\n".join(inner)) + "</pre>"
    slug_l = slug.strip().lower()
    cn = (case_no or "").strip().upper()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("ACCEPT SECURE CONNECTION", callback_data=f"cmp|sv|a|{slug_l}|{cn}")],
        [InlineKeyboardButton("CANCEL / RETURN", callback_data=f"cmp|sv|x|{slug_l}|{cn}")],
    ])
    return body, kb


def build_agent_secure_contact_panel(
    slug: str, case_no: str, submitted_ts: str
) -> tuple[str, InlineKeyboardMarkup]:
    """统一入口：身份核验门 → ACCEPT 后握手与会话 UI（后端留言逻辑仍为 cmp|sv|m| / CMP_MSG_CASE_AGENT）。"""
    return build_agent_identity_gate_html_and_kb(slug, case_no, submitted_ts)


def build_wilson_secure_contact_panel(
    case_no: str, submitted_ts: str
) -> tuple[str, InlineKeyboardMarkup]:
    return build_agent_secure_contact_panel("wilson", case_no, submitted_ts)


def build_agent_compose_prompt(slug: str) -> str:
    cfg = contact_slug_config(slug)
    heading = str(cfg["compose_heading"]) if cfg else "MESSAGE"
    sep = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    return (
        f"💬 <b>{heading}</b>\n"
        f"{sep}\n"
        "Please type your message below.\n\n"
        f"{sep}\n"
        "🤖 IC3-SYSTEM · NODE-09 · VERIFIED"
    )


def build_wilson_compose_prompt() -> str:
    return build_agent_compose_prompt("wilson")


def build_agent_message_delivered(slug: str) -> tuple[str, InlineKeyboardMarkup]:
    cfg = contact_slug_config(slug)
    line = str(cfg["delivered_body_line"]) if cfg else "Your message has been received."
    sep = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    body = (
        "✅ <b>MESSAGE DELIVERED</b>\n"
        f"{sep}\n"
        f"{line}\n\n"
        f"{sep}\n"
        "🤖 IC3-SYSTEM · NODE-09 · VERIFIED\n"
        f"{sep}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Return to Main Menu", callback_data="HOME")],
    ])
    return body, kb


def build_wilson_message_delivered() -> tuple[str, InlineKeyboardMarkup]:
    return build_agent_message_delivered("wilson")


def _fmt_agent_block(p) -> str:
    if not p:
        return ""
    aid = f"Agent ID : <code>{p.agent_id}</code>\n" if p.agent_id else ""
    return (
        f"Name : {p.name_en}\n"
        f"{aid}"
        f"Title : {p.position_en}\n"
        f"Division : {p.department_en}\n"
        f"Field Office : {p.office_en}\n"
        "Clearance : TS/SCI — TOP SECRET\n"
    )


def build_p5_identity_push(case_no: str, fee_override: float | None = None) -> tuple[str, InlineKeyboardMarkup]:
    jm = agent_profile("Jennifer Martinez")
    name = jm.name_en if jm else "Jennifer Martinez"
    title = jm.position_en if jm else "Identity Verification Manager"
    div = jm.department_en if jm else "Intake & Verification Center"
    office = jm.office_en if jm else "Miami Field Office"
    body = (
        "🛡️ <b>FEDERAL BUREAU OF INVESTIGATION</b>\n"
        "<b>EVIDENCE SUBMISSION PORTAL</b>\n"
        f"{H}\n\n"
        "⚖️ <b>EVIDENCE CORROBORATION REQUIRED</b>\n\n"
        f"CASE ID : <code>{case_no}</code>\n"
        "STATUS : 🟡 PENDING VERIFICATION\n\n"
        f"Name : {name}\n"
        f"Title : {title}\n"
        f"Division : {div}\n"
        f"Field Office : {office}\n"
        "Clearance : TS/SCI — TOP SECRET\n\n"
        "<b>CONTEXT:</b>\n\n"
        "The federal forfeiture involves over\n"
        "127,000 Bitcoin and complex off-chain\n"
        "transaction logs.\n\n"
        "To establish your legal claim, your specific\n"
        "loss must be forensically traced and\n"
        "correlated to the seized wallet addresses.\n\n"
        "Please select your verification method:\n"
        f"{H}\n\n"
        "<b>OPTION 1: PRIORITY FORENSIC CORRELATION</b>\n"
        "• Automated Blockchain Tracing API\n"
        "• Direct Link to Seized Wallet (Chain ID)\n"
        "• Instant Chain-of-Custody Generation\n"
        "• Bypasses Manual Review Queue\n\n"
        f"💳 <b>FEE: ${fee_override if fee_override is not None else 50.00:.2f} USDT</b>\n"
        "(Federal Analysis Network Usage Fee)\n\n"
        f"{MID_SEP}\n\n"
        "<b>OPTION 2: STANDARD PETITION (FREE)</b>\n"
        "• Manual Evidence Review\n"
        "• Standard Administrative Processing\n"
        "• Estimated Wait: 5-7 Business Days\n"
        "• No Technical Fees Required\n\n"
        "💳 <b>FEE: $0.00</b>\n\n"
        f"{H}\n\n"
        "⚠️ <b>NOTICE:</b>\n"
        "The FBI does NOT charge victims for case\n"
        "processing. This fee is paid directly to\n"
        "our contracted blockchain analytics provider\n"
        "to cover API access and data retrieval costs.\n\n"
        "<b>ACTIONS:</b>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Activate Priority Analysis", callback_data=f"cmp|p5pri|{case_no}")],
        [InlineKeyboardButton("Submit Standard Petition", callback_data=f"cmp|p5std|{case_no}")],
        [InlineKeyboardButton("Contact Officer Martinez", callback_data=agent_contact_open_cb("martinez", case_no))],
        [InlineKeyboardButton("Return to Main Menu", callback_data="HOME")],
    ])
    return body, kb


def _p6_remission_rate_percent(case_no: str) -> float:
    """按案号稳定哈希，返还费率 78.00%–89.00%（含）。"""
    key = (case_no or "").strip().upper().encode()
    h = int(hashlib.sha256(key).hexdigest()[:12], 16)
    return round(78.0 + (h % 1101) / 100.0, 2)


def _p6_parse_loss_amount(case_row: dict | None) -> float | None:
    if not case_row:
        return None
    raw = case_row.get("amount")
    if raw is None:
        return None
    try:
        if isinstance(raw, Decimal):
            v = float(raw)
        elif isinstance(raw, (int, float)):
            v = float(raw)
        else:
            s = str(raw).strip().replace(",", "")
            if not s:
                return None
            m = re.search(r"[\d.]+", s)
            if not m:
                return None
            v = float(m.group(0))
        return v if v >= 0 else None
    except (TypeError, ValueError):
        return None


def _p6_incident_display(case_row: dict | None) -> str:
    if not case_row:
        return "Not specified"
    t = (case_row.get("incident_time") or "").strip()
    return t if t else "Not specified"


def _p6_asset_type_line(case_row: dict | None) -> str:
    coin = (case_row.get("coin") or "").strip() if case_row else ""
    if coin:
        return f"Cryptocurrency ({coin})"
    return "Cryptocurrency"


def admin_p6_recovery_summary(case_row: dict | None, case_no: str) -> dict[str, str]:
    """
    管理员后台展示用：与 P6 同一公式（User Reported Loss × Remission Rate）。
    """
    cn = (case_no or "").strip().upper()
    loss = _p6_parse_loss_amount(case_row)
    rate = _p6_remission_rate_percent(cn)
    rate_s = f"{rate:.2f}%"
    if loss is not None:
        loss_s = f"${loss:,.2f} USD"
        recovery_s = f"${loss * (rate / 100.0):,.2f} USD"
    else:
        loss_s = "—"
        recovery_s = "—"
    return {
        "reported_loss": loss_s,
        "remission_rate": rate_s,
        "calculated_recovery": recovery_s,
    }


def build_p6_preliminary_push(
    case_no: str, case_row: dict | None = None
) -> tuple[str, InlineKeyboardMarkup]:
    mt = agent_profile("Michael Thompson")
    rb = agent_profile("Richard Brown")
    p6_sep = "─" * 28

    loss = _p6_parse_loss_amount(case_row)
    incident = _p6_incident_display(case_row)
    asset_type = _p6_asset_type_line(case_row)
    rate = _p6_remission_rate_percent(case_no)

    if loss is not None:
        loss_s = f"${loss:,.2f} USD"
        recovery = loss * (rate / 100.0)
        recovery_s = f"${recovery:,.2f} USD"
        rate_s = f"{rate:.2f}%"
    else:
        loss_s = "—"
        recovery_s = "—"
        rate_s = f"{rate:.2f}%"

    mt_n = mt.name_en if mt else "Michael Thompson"
    mt_t = mt.position_en if mt else "Forensic Computer Examiner"
    mt_d = mt.department_en if mt else "Digital Forensics Laboratory"
    mt_o = mt.office_en if mt else "Washington Field Office"
    rb_n = rb.name_en if rb else "Richard Brown"
    rb_t = rb.position_en if rb else "Cyber Division Supervisor"
    rb_d = rb.department_en if rb else "Cyber Security Division"
    rb_o = rb.office_en if rb else "Seattle Field Office"

    body = (
        "<b>Preliminary Review</b>\n\n"
        "<b>FBI REGIONAL COMPUTER FORENSICS LABORATORY</b>\n"
        "Washington Field Office\n"
        f"{H}\n\n"
        "<b>ASSET ORIGIN CONFIRMED</b>\n\n"
        f"CASE ID: <code>{case_no}</code>\n"
        "STATUS: LINKED TO FEDERAL SEIZURE\n\n"
        f"{p6_sep}\n\n"
        "<b>FORENSIC REVIEW TEAM:</b>\n\n"
        f"<b>{mt_n}</b> · <b>{rb_n}</b>\n"
        f"{mt_t} · {rb_t}\n"
        f"{mt_d} · {rb_d}\n"
        f"{mt_o} · {rb_o}\n\n"
        f"{p6_sep}\n\n"
        "<b>VERIFIED ASSETS</b>\n\n"
        "<b>ORIGINAL CLAIM DATA:</b>\n"
        f"User Reported Loss: <code>{loss_s}</code>\n"
        f"Date of Incident: <code>{incident}</code>\n"
        f"Asset Type: <code>{asset_type}</code>\n\n"
        "<b>RECOVERY CALCULATION:</b>\n"
        f"Remission Rate: <code>{rate_s}</code>\n"
        "(Net Judicial Costs &amp; Seized Asset Distribution)\n\n"
        f"<b>CALCULATED RECOVERY AMOUNT:</b> <code>{recovery_s}</code>\n\n"
        f"{p6_sep}\n\n"
        "<b>LEGAL DESIGNATION:</b>\n\n"
        "LEGAL STATUS: Seized Asset (Pending Release)\n"
        "CASE NO: <code>1:26-cv-00412-PAC (S.D.N.Y.)</code>\n"
        "CUSTODIAN: U.S. Marshals Service\n"
        "(Asset Forfeiture Division)\n\n"
        f"{p6_sep}\n\n"
        "<b>CASE STATUS SUMMARY:</b>\n\n"
        "Your specific funds have been identified and verified\n"
        "within this federal forfeiture pool. The calculated\n"
        "remission amount has been approved for administrative\n"
        "release pending final compliance verification.\n"
        f"{H}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Contact Agent Thompson", callback_data=agent_contact_open_cb("thompson", case_no))],
        [InlineKeyboardButton("Contact Agent Brown", callback_data=agent_contact_open_cb("brown", case_no))],
        [InlineKeyboardButton("Return to Main Menu", callback_data="HOME")],
    ])
    return body, kb


def build_p7_asset_tracing_push(case_no: str) -> tuple[str, InlineKeyboardMarkup]:
    sw = agent_profile("Sarah Williams")
    jw = agent_profile("James Wilson")
    sep = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    def _p7_officer_lines(p) -> str:
        if not p:
            return ""
        return (
            f"Name : {p.name_en}\n"
            f"Title : {p.position_en}\n"
            f"Division : {p.department_en}\n"
            f"Field Office : {p.office_en}\n"
            "Clearance : TS/SCI — TOP SECRET\n"
        )

    williams_blk = _p7_officer_lines(sw)
    wilson_blk = _p7_officer_lines(jw)
    body = (
        "<b>Asset Tracing</b>\n\n"
        "<b>FINANCIAL CRIMES SECTION</b>\n"
        f"{H}\n\n"
        "⚖️ <b>DIRECT REMISSION AUTHORIZED</b>\n\n"
        f"CASE ID: <code>{case_no}</code>\n"
        "STATUS: 🟡 PENDING ALLOCATION\n\n"
        f"<b>FINANCIAL INTELLIGENCE OFFICER</b>\n"
        f"{sep}\n"
        f"{williams_blk}\n"
        f"<b>GLOBAL LIAISON OFFICER</b>\n"
        f"{sep}\n"
        f"{wilson_blk}\n"
        "<b>EXPEDITED PROCESSING:</b>\n"
        "Standard civil litigation is NOT required.\n\n"
        "Since the assets are already in U.S.\n"
        "custody as part of the federal seizure\n"
        "action, the DOJ has authorized a Direct\n"
        "Administrative Remission process for\n"
        "identified victims.\n\n"
        "This allows you to recover your share\n"
        "directly from the government holding\n"
        "without court hearings or attorney fees.\n\n"
        "Your funds have been pre-allocated for\n"
        "release upon compliance verification.\n"
        f"{H}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Contact Agent Williams", callback_data=agent_contact_open_cb("williams", case_no))],
        [InlineKeyboardButton("Contact Agent Wilson", callback_data=agent_contact_open_cb("wilson", case_no))],
        [InlineKeyboardButton("Configure Wallet Now", callback_data=f"cmp|p7wal|{case_no}")],
        [InlineKeyboardButton("Return to Main Menu", callback_data="HOME")],
    ])
    return body, kb


def _fmt_p8_legal_agent_block(p) -> str:
    """P8 法律屏：不含 Agent ID。"""
    if not p:
        return ""
    return (
        f"Name : {html.escape(p.name_en)}\n"
        f"Title : {html.escape(p.position_en)}\n"
        f"Division : {html.escape(p.department_en)}\n"
        f"Field Office : {html.escape(p.office_en)}\n"
        "Clearance : TS/SCI — TOP SECRET\n"
    )


def build_p8_legal_push(case_no: str) -> tuple[str, InlineKeyboardMarkup]:
    rc = agent_profile("Robert Chen")
    cn_esc = html.escape((case_no or "").strip())
    sep = MID_SEP
    body = (
        "<b>Legal Documentation</b>\n\n"
        "<b>LEGAL LIAISON DIVISION</b>\n"
        f"{H}\n\n"
        "⚖️ <b>DISBURSEMENT DOCUMENTATION</b>\n\n"
        f"CASE ID: <code>{cn_esc}</code>\n"
        "STATUS: 🟡 PENDING WALLET ADDRESS\n\n"
        f"{_fmt_p8_legal_agent_block(rc)}\n"
        f"{sep}\n"
        "<b>WALLET COMPATIBILITY REQUIREMENTS</b>\n"
        f"{sep}\n\n"
        "Per DOJ Asset Forfeiture Regulations 28 C.F.R. § 9.8, recovered\n"
        "assets must be transferred to a wallet where the claimant holds\n"
        "exclusive control of the private keys.\n\n"
        "❌ <b>PROHIBITED WALLETS (Centralized Exchanges):</b>\n"
        " • Binance\n"
        " • Coinbase\n"
        " • Kraken\n"
        " • Gemini\n"
        " • KuCoin\n\n"
        "✅ <b>APPROVED WALLETS (Non-Custodial):</b>\n"
        "• Trust Wallet (Mobile)\n"
        " • MetaMask (Mobile/Browser)\n"
        " • Exodus (Desktop/Mobile)\n"
        " • Ledger Live (Hardware Wallet)\n"
        " • Phantom (Mobile)\n"
        " • SafePal (Hardware/Mobile)\n\n"
        "Please submit your TRC-20 (USDT) wallet\n"
        "address below to finalize the release\n"
        "order. Ensure the address is correct\n"
        "before submission.\n\n"
        "⚠️ <b>WARNING:</b>\n"
        "Incorrect wallet addresses may result\n"
        "in permanent loss of allocated funds.\n"
        "The DOJ assumes no liability for\n"
        "user-submitted address errors.\n"
        f"{H}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Submit Wallet Address", callback_data=f"cmp|p8wal|{case_no}")],
        [InlineKeyboardButton("Contact Coordinator Chen", callback_data=agent_contact_open_cb("chen", case_no))],
        [InlineKeyboardButton("Return to Main Menu", callback_data="HOME")],
    ])
    return body, kb


def _fmt_p9_assigned_agent_block(p) -> str:
    """P9 拨款屏 — ASSIGNED AGENT 块（无 Agent ID）。"""
    if not p:
        return ""
    return (
        "<b>ASSIGNED AGENT:</b>\n"
        f"{html.escape(p.name_en)}\n"
        f"{html.escape(p.position_en)}\n"
        f"{html.escape(p.department_en)}\n"
        f"{html.escape(p.office_en)}\n"
    )


def build_p9_disbursement_push(
    case_no: str, ovr: dict | None = None
) -> tuple[str, InlineKeyboardMarkup]:
    m = merge_cmp_defaults(ovr)
    ta = agent_profile("Thomas Anderson")
    cn_esc = html.escape((case_no or "").strip())
    sep = MID_SEP

    amt_raw = m.get("p9_disbursement_amount_usd")
    amt_bullet = "• DISBURSEMENT AMOUNT: <code>—</code> (USDT)"
    if amt_raw is not None and str(amt_raw).strip() != "":
        try:
            v = float(amt_raw)
            amt_bullet = f"• DISBURSEMENT AMOUNT: <code>${v:,.2f}</code> (USDT)"
        except (TypeError, ValueError):
            pass

    wal_show = str(m.get("p8_submitted_wallet") or "").strip()
    recipient_extra = ""
    if wal_show:
        recipient_extra = f"\n<code>{html.escape(wal_show)}</code>"

    body = (
        "<b>Fund Disbursement</b>\n\n"
        "<b>U.S. DEPARTMENT OF JUSTICE</b>\n"
        "<b>U.S. MARSHALS SERVICE - ASSET RECOVERY UNIT</b>\n"
        f"{H}\n\n"
        "<b>DISBURSEMENT AUTHORIZATION &amp; CONFIRMATION</b>\n\n"
        f"CASE ID: <code>{cn_esc}</code>\n\n"
        "STATUS: DISBURSEMENT AUTHORIZED &amp; EXECUTING\n\n"
        f"{_fmt_p9_assigned_agent_block(ta)}"
        f"{sep}\n"
        "<b>DISBURSEMENT DETAILS</b>\n"
        f"{sep}\n\n"
        "Pursuant to the asset remission order authorized under\n"
        "Case No. <code>1:26-cv-00412-PAC</code> (S.D.N.Y.), the U.S. Marshals\n"
        "Service has initiated the transfer of seized and forfeited\n"
        "assets to the verified claimant.\n\n"
        f"{amt_bullet}\n"
        "• RECIPIENT: Designated Non-Custodial Wallet"
        f"{recipient_extra}\n"
        "• NETWORK: TRON (TRC-20 Protocol)\n"
        "• AUTHORITY: 28 C.F.R. § 9 (Victim Remission)\n\n"
        "This action is part of the U.S. Marshals Service's mandate\n"
        "to enforce the collection of criminal debts and return\n"
        "forfeited assets to victims of federal crime.\n"
        f"{sep}\n"
        "<b>READ CAREFULLY</b>\n"
        f"{sep}\n\n"
        "The remitted funds have been disbursed from a <b>U.S. Government\n"
        "Administrative Custody Contract</b>. Most commercial non-custodial\n"
        "wallet applications (e.g., Trust Wallet, TronLink) do not\n"
        "automatically display balances from such specialized contracts\n"
        "by default, as a security and classification measure.\n\n"
        "To view your balance, you must manually add the asset contract\n"
        "to your wallet's watch list. This is a standard procedure for\n"
        "assets released from federal custody.\n\n"
        "<b>OFFICIAL PROCEDURE:</b>\n\n"
        "1. <b>COPY CONTRACT ADDRESS:</b> Use the button below to copy the\n"
        "   official U.S. Government contract address to your clipboard.\n"
        "2. <b>OPEN WALLET APPLICATION:</b> Launch your wallet application\n"
        "   (e.g., Trust Wallet, TronLink) and ensure you are connected\n"
        "   to the <b>TRON Mainnet</b>.\n"
        "3. <b>ADD CUSTOM TOKEN:</b> Navigate to the \"Add Token\" or \"Custom\n"
        "   Token\" function within your wallet. Paste the copied address.\n"
        "   The token symbol (USDT) and decimal precision (6) should auto-populate.\n"
        "4. <b>CONFIRM &amp; REFRESH:</b> Confirm the addition and refresh your\n"
        "   wallet's asset view. Your remitted balance will then be visible.\n\n"
        f"{sep}\n"
        "<b>NEXT STEPS &amp; COMPLIANCE VERIFICATION</b>\n\n"
        "The disbursement of assets does not conclude the administrative\n"
        "process. All remitted funds are subject to a final <b>Anti-Money\n"
        "Laundering (AML) hold</b> as mandated by the Bank Secrecy Act\n"
        "(<code>31 U.S.C. § 5318</code>). You must initiate the final compliance\n"
        "verification to lift this hold and enable full control of the assets.\n\n"
        "Use the button below to verify your wallet's status and proceed\n"
        "with the mandatory compliance clearance.\n\n"
        f"{H}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("COPY OFFICIAL CONTRACT ADDRESS", callback_data=f"cmp|p9contract|{case_no}")],
        [
            InlineKeyboardButton(
                "🔍 Verify Wallet & Compliance",
                callback_data=f"cmp|p9verify|{case_no}",
            )
        ],
        [InlineKeyboardButton("Contact Agent Anderson", callback_data=agent_contact_open_cb("anderson", case_no))],
        [InlineKeyboardButton("Return to Main Menu", callback_data="HOME")],
    ])
    return body, kb


def build_p9_compliance_scan_phase1(case_no: str, ovr: dict | None = None) -> str:
    """步骤 1：模拟扫描中（INITIATING BLOCKCHAIN COMPLIANCE SCAN）。"""
    m = merge_cmp_defaults(ovr)
    cn = html.escape((case_no or "").strip())
    wal = str(m.get("p8_submitted_wallet") or "").strip()
    wshort = _truncate_trc20_display(wal, head=6, tail=4) if wal else "—"
    sep = MID_SEP
    return (
        "🔍 <b>INITIATING BLOCKCHAIN COMPLIANCE SCAN</b>\n\n"
        f"CASE ID: <code>{cn}</code>\n\n"
        f"<b>Target Wallet:</b> <code>{html.escape(wshort)}</code>\n"
        "Network: TRC-20 (Tron Mainnet)\n\n"
        f"{sep}\n\n"
        "<b>SCANNING PROTOCOLS:</b>\n"
        "✅ Wallet Connection...............Established\n"
        "✅ Transaction Hash.................Verified\n"
        "✅ Federal Custody Contract.........Active\n"
        "⏳ AML Clearance Status.............Checking...\n\n"
        "Please wait while the system queries\n"
        "the Federal Compliance Database..."
    )


def build_p9_compliance_scan_phase2(case_no: str, ovr: dict | None = None) -> str:
    """步骤 2：扫描结束 — COMPLIANCE HOLD DETECTED。"""
    m = merge_cmp_defaults(ovr)
    cn = html.escape((case_no or "").strip())
    amt_s = "—"
    amt_raw = m.get("p9_disbursement_amount_usd")
    if amt_raw is not None and str(amt_raw).strip() != "":
        try:
            amt_s = f"${float(amt_raw):,.2f} USDT"
        except (TypeError, ValueError):
            pass
    sep = MID_SEP
    return (
        "⚠️ <b>SCAN COMPLETE: COMPLIANCE HOLD DETECTED</b>\n\n"
        f"CASE ID: <code>{cn}</code>\n\n"
        f"{sep}\n\n"
        "<b>SCAN SUMMARY:</b>\n\n"
        f"✅ Funds Received: <code>{html.escape(amt_s)}</code>\n"
        "✅ Transaction Valid: Confirmed on Tron Network\n"
        "🔴 TRANSFER STATUS: <b>LOCKED</b>\n\n"
        f"{sep}\n\n"
        "<b>SYSTEM ALERT:</b>\n\n"
        "Your funds have been successfully deposited into your\n"
        "wallet but are currently under a <b>Federal Anti-Money\n"
        "Laundering (AML) Hold</b>.\n\n"
        "This lock is automatic for all funds released from\n"
        "seized criminal wallets per <code>31 U.S.C. § 5311</code>.\n\n"
        "You must clear this hold before the tokens can be\n"
        "traded or transferred."
    )


def build_p9_compliance_loading_text(percent: int) -> str:
    """步骤 3：加载动画文案（20 / 50 / 80 / 100）。"""
    if percent == 20:
        return (
            "⏳ <b>LOADING COMPLIANCE DETAILS...</b>\n\n"
            "<b>ACCESSING:</b>\n"
            "<code>▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰░░░░░░░░░░░░░░░░░░</code> 20%\n"
            "• FinCEN Compliance Database\n"
            "• Chainalysis Federal Solutions\n"
            "• U.S. Marshals Service Records\n\n"
            "Please hold while we retrieve your\n"
            "case specifics..."
        )
    if percent == 50:
        return (
            "⏳ <b>LOADING COMPLIANCE DETAILS...</b>\n\n"
            "<b>ACCESSING:</b>\n"
            "<code>▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰░░░░░░░░░░░░░░░░</code> 50%\n"
            "• FinCEN Compliance Database ✓\n"
            "• Chainalysis Federal Solutions\n"
            "• U.S. Marshals Service Records\n\n"
            "Retrieving AML verification requirements..."
        )
    if percent == 80:
        return (
            "⏳ <b>LOADING COMPLIANCE DETAILS...</b>\n\n"
            "<b>ACCESSING:</b>\n"
            "<code>▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰░░░░░░░░░░░░░░</code> 80%\n"
            "• FinCEN Compliance Database ✓\n"
            "• Chainalysis Federal Solutions ✓\n"
            "• U.S. Marshals Service Records\n\n"
            "Finalizing clearance protocols..."
        )
    if percent == 100:
        return (
            "✅ <b>COMPLIANCE DETAILS LOADED</b>\n\n"
            "Generating final clearance report..."
        )
    return "⏳ <b>LOADING...</b>"


def build_p10_sanction_push(
    case_no: str, ovr: dict | None = None, case_row: dict | None = None
) -> tuple[str, InlineKeyboardMarkup]:
    m = merge_cmp_defaults(ovr)
    ta = agent_profile("Thomas Anderson")
    am = agent_profile("Amanda Taylor")
    locked_amt, loc_line = _p10_locked_funds_display(case_no, m, case_row)
    fee_block = _fmt_p10_service_fee_block(m.get("p10_items"))
    total_line = _fmt_fee_total_line(m.get("p10_items"))
    p10_sep = "─" * 28

    body = (
        "<b>SANCTION / AML COMPLIANCE</b>\n\n"
        "<b>FINCEN COMPLIANCE DIVISION</b>\n"
        "U.S. Department of the Treasury\n"
        f"{H}\n\n"
        "<b>ANTI-MONEY LAUNDERING HOLD ACTIVE</b>\n\n"
        f"CASE ID: <code>{case_no}</code>\n"
        "STATUS: CLEARANCE REQUIRED\n\n"
        "<b>COMPLIANCE OFFICER:</b>\n"
        f"{_p10_compact_officer_block(ta)}\n"
        "<b>VICTIM ASSISTANCE:</b>\n"
        f"{_p10_compact_officer_block(am)}"
        f"{p10_sep}\n\n"
        "<b>LOCKED FUNDS DETAILS:</b>\n\n"
        f"AMOUNT LOCKED:  <code>{locked_amt}</code>\n"
        f"LOCATION:        <code>{loc_line}</code>\n\n"
        "<b>REASON FOR HOLD:</b>\n"
        "Mandatory AML Verification per Case No. <code>1:26-cv-00412-PAC</code>\n"
        "(S.D.N.Y.) and Bank Secrecy Act (<code>31 U.S.C. § 5311</code>).\n"
        f"{p10_sep}\n\n"
        "<b>COMPLIANCE EXPLANATION:</b>\n\n"
        "Because your funds originated from a seized criminal\n"
        "wallet flagged by FinCEN, federal regulations require\n"
        "a final Anti-Money Laundering (AML) verification before\n"
        "the tokens can be released for trading or transfer.\n\n"
        "This verification is performed by a federal contractor\n"
        "(Chainalysis Federal Solutions) and involves:\n"
        "- Source of Funds Screening\n"
        "- Wallet Address Whitelisting\n"
        "- Blockchain Forensic Certification\n\n"
        " ───────────────────────────────────────────\n"
        "<b>SERVICE FEE BREAKDOWN:</b>\n\n"
        "These fees are NOT paid to the U.S. Government.\n"
        "They are paid directly to federal contractors and\n"
        "blockchain network providers.\n\n"
        f"{fee_block}\n"
        f"{p10_sep}\n"
        f"{total_line}\n"
        f"{p10_sep}\n"
        "<b>IMPORTANT NOTICE:</b>\n\n"
        "The U.S. Government does NOT charge victims for asset\n"
        "recovery. However, federal contractors and blockchain\n"
        "service providers require payment for technical services.\n\n"
        "The administrative authorization for your specific asset\n"
        "remission is time-sensitive. Failure to complete the\n"
        "AML verification within 48 hours will result in the\n"
        "cancellation of your disbursement order.\n\n"
        "Upon cancellation, the allocation will be nullified, and\n"
        "your case will be closed without further action.\n\n"
        f"{p10_sep}\n\n"
        "<b>ACTIONS:</b>"
    )
    p10_amt = format_cmp_fee_button_usd(m.get("p10_items"))
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💳 Execute Contract Fee (${p10_amt})", callback_data=f"cmp|p10pay|{case_no}")],
        [InlineKeyboardButton("Contact Officer Taylor", callback_data=agent_contact_open_cb("taylor", case_no))],
        [InlineKeyboardButton("Return to Main Menu", callback_data="HOME")],
    ])
    return body, kb


def build_p11_protocol_push(
    case_no: str,
    case_row: dict | None = None,
    ovr: dict | None = None,
) -> tuple[str, InlineKeyboardMarkup]:
    """
    P11 费用分项与按钮合计一律以数据库为准：
    有 `case_row` 时用 `effective_cmp_overrides(case_row)`（含管理员写入的 p11_items）；
    无案件行时（如单元测试）才用 `merge_cmp_defaults(ovr)`。
    """
    m = (
        effective_cmp_overrides(case_row)
        if case_row is not None
        else merge_cmp_defaults(ovr)
    )
    ld = agent_profile("Linda Davis")
    lines, fee_total = _fee_lines_from_items(m.get("p11_items"))
    fee_bullets = "\n".join(f"• {html.escape(lbl)}: ${amt:,.2f}" for lbl, amt in lines)
    total_fee_s = f"${fee_total:,.2f}"
    locked_amt, _ = _p10_locked_funds_display(case_no, m, case_row)
    custody_plain = (
        locked_amt.replace(" USDT", "").strip()
        if "USDT" in (locked_amt or "")
        else (locked_amt or "—")
    )
    custody_f = _parse_usd_amount_from_display(locked_amt)
    if custody_f is not None:
        net_f = custody_f - fee_total
        net_s = f"${net_f:,.2f}"
        fee_minus_s = f"-${fee_total:,.2f}"
    else:
        net_s = "—"
        fee_minus_s = f"-${fee_total:,.2f}"
    p11_sep = "─" * 35

    _para_open = (
        f"Your {html.escape(custody_plain)} in USDT has been legally cleared and\n"
        if custody_plain != "—"
        else "Your USDT has been legally cleared and\n"
    )
    _step1 = (
        f"1. Your {html.escape(custody_plain)} will be activated in the custody wallet\n"
        if custody_plain != "—"
        else "1. Your custody balance will be activated in the custody wallet\n"
    )
    body = (
        "<b>FUND ACTIVATION &amp; WITHDRAWAL AUTHORIZATION</b>\n\n"
        "<b>U.S. MARSHALS SERVICE</b>\n"
        "Asset Forfeiture Division\n"
        f"{H}\n\n"
        "🔓 <b>FUND ACTIVATION &amp; WITHDRAWAL AUTHORIZATION</b>\n\n"
        f"CASE ID: <code>{html.escape(case_no)}</code>\n"
        "STATUS: PENDING WITHDRAWAL AUTHORIZATION\n\n"
        "<b>ASSIGNED FINANCIAL OFFICER:</b>\n"
        f"{_p10_compact_officer_block(ld)}"
        f"{p11_sep}\n"
        "<b>CURRENT ASSET STATUS</b>\n"
        f"{p11_sep}\n\n"
        "✅ COMPLIANCE CLEARANCE: COMPLETE\n"
        f"✅ TOKENS IN WALLET: <code>{html.escape(locked_amt)}</code> (Visible)\n"
        "🔴 WITHDRAWAL STATUS: RESTRICTED\n\n"
        f"{_para_open}"
        "is currently held in a <b>Federal Custody Wallet</b>.\n\n"
        "<b>KEY FACT:</b> These funds are in a <b>temporary custody\n"
        "format</b> that requires final activation before they can\n"
        "be withdrawn or transferred to external addresses.\n\n"
        "This is standard protocol to prevent premature\n"
        "disbursement and ensure proper documentation.\n\n"
        f"{p11_sep}\n"
        "<b>ACTIVATION &amp; WITHDRAWAL FEE</b>\n"
        f"{p11_sep}\n\n"
        "To activate the funds and enable withdrawal, the following\n"
        "mandatory fees must be paid to the U.S. Marshals Service:\n\n"
        "<b>FEE BREAKDOWN:</b>\n"
        f"{fee_bullets}\n"
        f"• <b>TOTAL FEE: {total_fee_s} USDT</b>\n\n"
        "<b>AUTHORITY:</b>\n"
        "This fee is authorized under <b>28 C.F.R. Part 9.8</b> (Remission\n"
        "Procedures) to cover the administrative costs of:\n"
        "• Activating the custody wallet\n"
        "• Processing withdrawal authorization\n"
        "• Generating withdrawal documentation\n\n"
        "<b>IMPORTANT:</b> This fee is NOT a tax or fine. It is a\n"
        "processing fee for the withdrawal service.\n\n"
        f"{p11_sep}\n"
        "<b>WHAT HAPPENS AFTER PAYMENT:</b>\n\n"
        f"{_step1}"
        "2. You will receive a <b>Withdrawal Authorization Certificate</b>\n"
        "3. You can then transfer the funds to your external wallet\n"
        "   or exchange\n\n"
        "<b>TIME SENSITIVE:</b>\n"
        "This withdrawal authorization expires in <b>24 hours</b>.\n"
        "Failure to authorize will result in the funds being\n"
        "returned to the general forfeiture pool.\n\n"
        f"{p11_sep}\n"
        "<b>YOUR NET RECOVERY:</b>\n"
        f"• Assets in Custody: {html.escape(locked_amt)}\n"
        f"• Withdrawal Fee: <code>{html.escape(fee_minus_s)}</code>\n"
        f"• <b>Final Amount Available: {html.escape(net_s)}</b>\n\n"
        f"{H}\n\n"
        "<b>ACTIONS:</b>"
    )
    p11_amt = format_cmp_fee_button_usd(m.get("p11_items"))
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"💳 AUTHORIZE WITHDRAWAL & PAY FEE (${p11_amt})",
                    callback_data=f"cmp|p11pay|{case_no}",
                )
            ],
            [
                InlineKeyboardButton(
                    "📄 REVIEW WITHDRAWAL CERTIFICATE (PDF)",
                    callback_data=f"cmp|p11pdf|{case_no}",
                )
            ],
            [
                InlineKeyboardButton(
                    "📧 CONTACT FINANCIAL OFFICER",
                    callback_data=agent_contact_open_cb("davis", case_no),
                )
            ],
            [
                InlineKeyboardButton(
                    "🏠 RETURN TO CASE SUMMARY",
                    callback_data=f"cmp|refresh|{case_no}",
                )
            ],
        ]
    )
    return body, kb


def build_p12_final_auth_push(case_no: str, ovr: dict | None = None) -> tuple[str, InlineKeyboardMarkup]:
    m = merge_cmp_defaults(ovr)
    ta = agent_profile("Thomas Anderson")
    fee_body = _fmt_fee_breakdown_lines(m.get("p12_items"))
    total_line = _fmt_fee_total_line(m.get("p12_items"))
    body = (
        "<b>FINAL AUTHORIZATION</b>\n\n"
        "<b>FEDERAL RESERVE NETWORK</b>\n"
        "Final Authorization Node\n"
        f"{H}\n\n"
        "🚀 <b>FINAL RELEASE AUTHORIZATION</b>\n\n"
        f"CASE ID: <code>{case_no}</code>\n"
        "STATUS: 🟡 READY FOR TRANSMISSION\n\n"
        "<b>AUTHORIZATION OFFICER:</b>\n"
        f"{_fmt_agent_block(ta)}"
        "\n"
        "<b>FINAL STEP:</b>\n"
        "Your assets have been converted to Standard\n"
        "USDT and are ready for transfer.\n\n"
        "Due to the high value of the transaction,\n"
        "the network requires a <b>Final Node\n"
        "Authorization</b> to ensure the transfer is\n"
        "prioritized by miners and not flagged as\n"
        "spam or rejected by pool validators.\n\n"
        "This is the final step required to release\n"
        "funds to your personal control.\n\n"
        "🔓 <b>AUTHORIZATION FEE:</b>\n"
        f"{fee_body}\n"
        f"{MID_SEP}\n"
        f"{total_line}\n\n"
        "⚠️ <b>URGENT:</b>\n"
        "Authorization code expires in 1 hour.\n"
        "Payment authorizes the immediate release\n"
        "of funds to your wallet address.\n"
        f"{H}\n\n"
        "<b>ACTIONS:</b>"
    )
    p12_amt = format_cmp_fee_button_usd(m.get("p12_items"))
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💳 Pay Authorization Fee (${p12_amt})", callback_data=f"cmp|p12pay|{case_no}")],
        [InlineKeyboardButton("Contact Officer Anderson", callback_data=agent_contact_open_cb("anderson", case_no))],
        [InlineKeyboardButton("Return to Main Menu", callback_data="HOME")],
    ])
    return body, kb


__all__ = [
    "CONTACT_SLUG_CONFIG",
    "DOJ_PRESS_RELEASE_URL",
    "admin_p6_recovery_summary",
    "H",
    "MID_SEP",
    "P9_TRONSCAN_TX_URL",
    "TRUST_WALLET_DOWNLOAD_URL",
    "WILSON_CONTACT_FIELD_OFFICE",
    "agent_contact_compose_cb",
    "agent_contact_open_cb",
    "build_agent_compose_prompt",
    "build_agent_handshake_html",
    "build_agent_identity_gate_html_and_kb",
    "build_agent_message_delivered",
    "build_agent_secure_contact_panel",
    "build_doj_forfeiture_notice",
    "build_p1_push",
    "build_p2_push",
    "build_p3_push",
    "build_p4_push",
    "build_p5_identity_push",
    "build_p6_preliminary_push",
    "build_p7_asset_tracing_push",
    "build_p8_legal_push",
    "build_p9_compliance_loading_text",
    "build_p9_compliance_scan_phase1",
    "build_p9_compliance_scan_phase2",
    "build_p9_disbursement_push",
    "build_p10_chainalysis_authorization_panel",
    "build_p10_sanction_push",
    "p10_chainalysis_reference_ids",
    "p11_withdrawal_reference_ids",
    "p11_portal_success_snapshot",
    "build_p11_marshals_authorization_panel",
    "build_p11_protocol_push",
    "build_p12_final_auth_push",
    "effective_cmp_overrides",
    "format_cmp_fee_button_usd",
    "merge_cmp_defaults",
    "tronscan_url_for_tx_hash",
    "build_wilson_compose_prompt",
    "build_wilson_message_delivered",
    "build_wilson_secure_contact_panel",
    "contact_slug_config",
    "format_case_date_utc",
    "format_submitted_ts_utc_now",
    "FLOW_CONTACT_ALERT_TEXT",
    "autopush_append_tip",
    "kb_autopush_followup",
    "kb_officer_contact_hint",
]
