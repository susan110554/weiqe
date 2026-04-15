"""
TRC20 USDT 承包商支付流程（P5 优先费 / P10–P12 等）
- 地址池：环境变量 CRYPTOPAY_TRC20_POOL（逗号分隔）
- 链上检测：TronScan 公开 API（可选 Tokenview 扩展位）
"""

from __future__ import annotations

import asyncio
import html
import io
import json
import logging
import os
import secrets
import time
from datetime import datetime, timedelta, timezone

import httpx
import qrcode
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, ContextTypes

import database as db
from chain_apis import (
    fetch_tron_latest_block,
    fetch_tron_trc20_transfers,
    fetch_tron_trx_incoming,
)
from bot_modules.config import qa_bypass_rate_limits
from bot_modules.case_management_push import (
    effective_cmp_overrides,
    format_cmp_fee_button_usd,
    p10_chainalysis_reference_ids,
    p11_portal_success_snapshot,
    p11_withdrawal_reference_ids,
    tronscan_url_for_tx_hash,
)

logger = logging.getLogger(__name__)


async def _ops_recon_session(
    row: dict,
    event_type: str,
    detail: dict | None = None,
    *,
    open_review: bool = False,
) -> None:
    try:
        from bot_modules import ops_cycle

        await ops_cycle.record_payment_event(
            public_id=row.get("public_id"),
            case_no=(row.get("case_no") or "").strip().upper(),
            event_type=event_type,
            detail=detail or {},
            open_review=open_review,
        )
    except Exception:
        logger.debug("[ops] payment recon", exc_info=True)

USDT_TRC20_MAINNET = os.getenv(
    "CRYPTOPAY_USDT_CONTRACT", "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
)
TOKENVIEW_API_KEY = os.getenv("TOKENVIEW_API_KEY", "").strip()
# 等款 / 等确认轮询间隔（秒），默认均为 15；可通过环境变量分别覆盖
POLL_AWAIT_SEC = float(os.getenv("CRYPTOPAY_POLL_ACTIVE_SEC", "15"))
POLL_CONFIRM_SEC = float(os.getenv("CRYPTOPAY_POLL_CONFIRM_SEC", "15"))
CONFIRMATIONS_REQUIRED = int(os.getenv("CRYPTOPAY_CONFIRMATIONS", "3"))
P5_EXPECT_USD = float(os.getenv("CRYPTOPAY_P5_AMOUNT_USD", "50"))
CTS03_EXPECT_USD = float(os.getenv("CRYPTOPAY_CTS03_AMOUNT_USD", "2800"))
SESSION_TTL_MIN = int(os.getenv("CRYPTOPAY_SESSION_MINUTES", "30"))
MANUAL_RL_WINDOW_SEC = int(os.getenv("CRYPTOPAY_MANUAL_RL_WINDOW_SEC", "300"))
MANUAL_RL_MAX = int(os.getenv("CRYPTOPAY_MANUAL_RL_MAX", "3"))
MIN_TRX_SUN_NOTIFY = int(os.getenv("CRYPTOPAY_MIN_TRX_SUN", "1000000"))  # 1 TRX

# 轮询地址分配（进程内）
_addr_rr: int = 0


def _row_extra(row: dict) -> dict:
    ex = row.get("extra")
    if ex is None:
        return {}
    if isinstance(ex, str):
        try:
            ex = json.loads(ex)
        except Exception:
            return {}
    return ex if isinstance(ex, dict) else {}


def _pool_addresses() -> list[str]:
    raw = os.getenv("CRYPTOPAY_TRC20_POOL", "").strip()
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    out: list[str] = []
    for p in parts:
        if p.startswith("T") and len(p) == 34:
            out.append(p)
        else:
            logger.warning("[cryptopay] skip invalid pool address: %s", p[:20])
    return out


def _next_deposit_address() -> str | None:
    global _addr_rr
    pool = _pool_addresses()
    if not pool:
        return None
    _addr_rr = (_addr_rr + 1) % len(pool)
    return pool[_addr_rr]


def next_trc20_deposit_address() -> str | None:
    """从 CRYPTOPAY_TRC20_POOL 轮询下一个收款地址（供 P10 授权页与门户复用）。"""
    return _next_deposit_address()


def peek_trc20_deposit_address() -> str | None:
    """只读查看池中第一个 TRC20 地址（不推进轮询；供 P10 PDF 等预览）。"""
    pool = _pool_addresses()
    return pool[0] if pool else None


def _deposit_address_is_in_pool(addr: str) -> bool:
    a = (addr or "").strip()
    return bool(a) and a in _pool_addresses()


def _fee_total_usd(items) -> float:
    s = format_cmp_fee_button_usd(items)
    try:
        return float(str(s).replace(",", "").strip() or "0")
    except ValueError:
        return 0.0


def _amount_bounds(payment_kind: str, case_row: dict | None) -> tuple[float, float, float]:
    """(expected, min, max) in USD (USDT 1:1)."""
    m = effective_cmp_overrides(case_row) if case_row else {}
    if payment_kind == "p5_priority":
        exp = P5_EXPECT_USD
        return exp, max(0.01, exp - 2.0), exp + 2.0
    if payment_kind == "cts03_pay":
        exp = CTS03_EXPECT_USD
        delta = max(5.0, round(exp * 0.02, 2))
        return exp, max(0.01, exp - delta), exp + delta
    key = {"p10_pay": "p10_items", "p11_pay": "p11_items", "p12_pay": "p12_items"}.get(
        payment_kind
    )
    exp = _fee_total_usd(m.get(key)) if key else 0.0
    if exp <= 0:
        exp = P5_EXPECT_USD
    delta = max(2.0, round(exp * 0.02, 2))
    return exp, max(0.01, exp - delta), exp + delta


def _service_label(payment_kind: str) -> str:
    return {
        "p5_priority": "Priority Blockchain Tracing",
        "cts03_pay":   "Federal Administrative Fee Assessment (CTS-03)",
        "p10_pay":     "SANCTION / OFAC Clearance",
        "p11_pay":     "Fund Activation & Withdrawal Authorization",
        "p12_pay":     "Final Authorization",
    }.get(payment_kind, "Federal Blockchain Service")


def build_authorization_text(
    case_no: str, payment_kind: str, *, amount_usd: float
) -> str:
    svc = _service_label(payment_kind)
    amt_line = f"Amount Due:      <code>${amount_usd:,.2f} USD</code>\n"
    return (
        "🛡️ <b>THIRD-PARTY SERVICE AUTHORIZATION</b>\n"
        "Chainalysis Federal Solutions\n"
        "<code>┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅</code>\n\n"
        "💳 <b>SERVICE AUTHORIZATION</b>\n\n"
        f"CASE ID:  <code>{case_no}</code>\n"
        f"SERVICE: <code>{svc}</code>\n\n"
        "<code>┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅</code>\n\n"
        "<b>SERVICE PROVIDER:</b>\n"
        "Chainalysis Inc.\n"
        "(Federal Law Enforcement Contractor)\n"
        "Contract #: DOJ-2024-BC-7829\n\n"
        "<code>┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅</code>\n\n"
        "<b>PAYMENT DETAILS:</b>\n\n"
        "Item Description:\n"
        "Federal Blockchain Analysis API Access\n\n"
        f"{amt_line}"
        "Payment Method:  USDT (Tether)\n"
        "Blockchain:      TRC20 (TRON Network)\n\n"
        "Payee:          Chainalysis Inc.\n"
        "Tax ID:         82-3456789\n\n"
        "<code>┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅</code>\n\n"
        "⚠️ <b>IMPORTANT NOTICE:</b>\n\n"
        "This payment is NOT made to the FBI.\n"
        "You are paying a private contractor that\n"
        "provides blockchain forensic services to\n"
        "federal law enforcement agencies.\n\n"
        "Per federal procurement regulations, all\n"
        "contractor payments must be made via\n"
        "digital currency for security purposes.\n\n"
        f"The FBI has authorized this service on\n"
        f"your behalf under case <code>{case_no}</code>\n\n"
        "<code>┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅</code>"
    )


def _confirmed_keyboard(public_id: str, case_no: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📥 Download Receipt", callback_data=f"pay|rcpt|{public_id}"),
                InlineKeyboardButton(
                    "👉 Continue to Dashboard", callback_data=f"pay|dash|{public_id}"
                ),
            ],
        ]
    )


def _p11_confirmed_keyboard(public_id: str, row: dict) -> InlineKeyboardMarkup:
    tx = (row.get("tx_hash") or "").strip()
    url = tronscan_url_for_tx_hash(tx)
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://tronscan.org/"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📄 DOWNLOAD WITHDRAWAL CERTIFICATE (PDF)",
                    callback_data=f"pay|p11wac|{public_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "📥 PAYMENT RECEIPT (PDF)",
                    callback_data=f"pay|rcpt|{public_id}",
                )
            ],
            [InlineKeyboardButton("🔗 VIEW TRANSACTION ON TRONSCAN", url=url)],
            [InlineKeyboardButton("🏠 RETURN TO MAIN MENU", callback_data=f"pay|home|{public_id}")],
        ]
    )


def _portal_keyboard_active(
    public_id: str, payment_kind: str | None = None
) -> InlineKeyboardMarkup:
    refresh_lbl = (
        "🔄 MANUAL REFRESH"
        if (payment_kind or "").strip() == "p11_pay"
        else "🔄 Refresh Status"
    )
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📋 Copy Address", callback_data=f"pay|copy|{public_id}")],
            [
                InlineKeyboardButton(refresh_lbl, callback_data=f"pay|refresh|{public_id}"),
                InlineKeyboardButton("❌ Cancel Payment", callback_data=f"pay|cancel|{public_id}"),
            ],
            [
                InlineKeyboardButton(
                    "📧 I Sent But Not Detected", callback_data=f"pay|notdet|{public_id}"
                )
            ],
        ]
    )


def _amount_error_keyboard(public_id: str, shortage: float) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"💳 Send Remaining ${shortage:,.2f}",
                    callback_data=f"pay|remain|{public_id}",
                )
            ],
            [InlineKeyboardButton("📧 Contact Support", callback_data=f"pay|sup|{public_id}")],
            [
                InlineKeyboardButton("🔄 Refresh Status", callback_data=f"pay|refresh|{public_id}"),
            ],
        ]
    )


def _wrong_token_keyboard(public_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💳 Send Correct Token", callback_data=f"pay|tokfix|{public_id}")],
            [
                InlineKeyboardButton(
                    "📧 Request Manual Review", callback_data=f"pay|wrongsup|{public_id}"
                )
            ],
        ]
    )


def _expired_keyboard(row: dict) -> InlineKeyboardMarkup:
    pid = row["public_id"]
    kind = row["payment_kind"]
    case_no = row["case_no"]
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔄 Generate New Address", callback_data=f"pay|newaddr|{kind}|{case_no}")],
            [InlineKeyboardButton("📧 Submit Transaction Hash", callback_data=f"pay|notdet|{pid}")],
            [InlineKeyboardButton("Return to Main Menu", callback_data=f"pay|home|{pid}")],
        ]
    )


def _manual_scan_keyboard(public_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📧 I Sent But Not Detected", callback_data=f"pay|notdet|{public_id}")],
            [InlineKeyboardButton("🔄 Scan Again", callback_data=f"pay|mscan|{public_id}")],
        ]
    )


def _manual_verify_panel_keyboard(public_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📤 Upload Screenshot", callback_data=f"pay|upss|{public_id}")],
            [InlineKeyboardButton("📝 Enter Transaction Hash", callback_data=f"pay|enth|{public_id}")],
            [InlineKeyboardButton("🚫 Cancel Request", callback_data=f"pay|canreq|{public_id}")],
        ]
    )


def _hash_fail_keyboard(public_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📝 Enter Hash Again", callback_data=f"pay|enth|{public_id}")],
            [InlineKeyboardButton("📧 Contact Support", callback_data=f"pay|sup|{public_id}")],
        ]
    )


def _hash_ok_keyboard(public_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔄 Refresh Status", callback_data=f"pay|refresh|{public_id}"),
                InlineKeyboardButton("⏳ Set Auto-Notify", callback_data=f"pay|autonotify|{public_id}"),
            ],
        ]
    )


def _bar_pct(confirmations: int, need: int) -> str:
    confirmations = max(0, min(confirmations, need))
    filled = int(round(20 * confirmations / need)) if need else 0
    return "[" + ("█" * filled) + ("░" * (20 - filled)) + f"] {confirmations}/{need}"


def _quant_to_usdt(quant: str) -> float:
    try:
        return int(quant) / 1_000_000.0
    except (TypeError, ValueError):
        return 0.0


def _p11_usms_portal_header(sep: str) -> str:
    return (
        "🛡️ <b>U.S. MARSHALS SERVICE</b>\n"
        "<b>ASSET RECOVERY — WITHDRAWAL AUTHORIZATION</b>\n"
        f"{sep}\n\n"
    )


def _build_p11_marshals_portal_caption(
    *,
    case_no: str,
    deposit_address: str,
    amount: float,
    status: str,
    tx_hash: str | None,
    confirmations: int,
    expires_at: datetime,
    block_number: int | None,
    extra: dict | None,
) -> str:
    """P11 支付门户：与产品稿一致的分阶段 / 成功文案（HTML）。"""
    ex = extra or {}
    need = CONFIRMATIONS_REQUIRED
    exp = expires_at.astimezone(timezone.utc).strftime("%H:%M UTC")
    sep = "<code>┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅</code>"
    memo_val = (ex.get("p11_memo") or "").strip()
    memo_note = ""
    if memo_val:
        memo_note = (
            f"<b>REFERENCE (MEMO/Tag):</b> <code>{html.escape(memo_val)}</code>\n\n"
        )
    header = _p11_usms_portal_header(sep)
    bar = _bar_pct(confirmations, need)
    now_utc = datetime.now(timezone.utc)
    t_log = now_utc.strftime("%H:%M UTC")

    if status == "wrong_token":
        tok = ex.get("wrong_token_label") or "TRX"
        return (
            header
            + "❌ <b>INVALID TOKEN DETECTED</b>\n\n"
            + f"{sep}\n\n"
            + f"CASE ID: <code>{html.escape(case_no)}</code>\n\n"
            + f"<b>Expected:</b> USDT (TRC20)\n"
            + f"<b>Received:</b> {html.escape(str(tok))}\n\n"
            + f"<b>PAYMENT ADDRESS (USDT TRC20):</b>\n<pre>{html.escape(deposit_address)}</pre>\n"
        )

    if status == "amount_shortfall":
        recv = float(ex.get("usdt_total") or 0)
        shortage = max(0.0, float(amount) - recv)
        if ex.get("overpaid"):
            return (
                header
                + "⚠️ <b>PAYMENT ERROR — OVERPAID</b>\n\n"
                + f"CASE ID: <code>{html.escape(case_no)}</code>\n\n"
                + f"<b>Received (sum):</b> ${recv:,.2f} USDT\n\n"
                + f"<pre>{html.escape(deposit_address)}</pre>\n"
            )
        return (
            header
            + "⚠️ <b>PAYMENT ERROR</b>\n\n"
            + f"CASE ID: <code>{html.escape(case_no)}</code>\n\n"
            + f"<b>Expected:</b> ${amount:,.2f} USDT\n"
            + f"<b>Received:</b> ${recv:,.2f} USDT\n"
            + f"<b>Shortage:</b> ${shortage:,.2f} USDT\n\n"
            + f"<b>PAYMENT ADDRESS:</b>\n<pre>{html.escape(deposit_address)}</pre>\n\n"
            + f"⏱️ Window ends ~{exp}\n"
        )

    if status == "expired":
        return (
            header
            + "⚠️ <b>PAYMENT WINDOW EXPIRED</b>\n\n"
            + f"CASE ID: <code>{html.escape(case_no)}</code>\n\n"
            + "If you already sent USDT, contact support with your transaction hash.\n\n"
            + f"{sep}\n"
        )

    if status == "awaiting_transfer":
        return (
            header
            + "💳 <b>PAYMENT INSTRUCTIONS</b>\n\n"
            + f"<b>WITHDRAWAL AUTHORIZATION</b>\n\n"
            + f"CASE ID: <code>{html.escape(case_no)}</code>\n"
            + f"AMOUNT: <code>${amount:,.2f} USDT (TRC20)</code>\n\n"
            + memo_note
            + f"{sep}\n\n"
            + f"<b>PAYMENT ADDRESS:</b>\n<pre>{html.escape(deposit_address)}</pre>\n\n"
            + f"⏱️ <b>TRANSACTION WINDOW:</b> until ~{exp}\n\n"
            + f"Send <b>EXACTLY ${amount:,.2f} USDT</b> on <b>TRC20</b>.\n\n"
            + "<b>PAYEE:</b> U.S. Marshals Service (Federal Escrow)\n"
            + "<b>PURPOSE:</b> Custody activation & withdrawal authorization\n\n"
            + f"{sep}\n\n"
            + "STATUS: ⏳ <b>Waiting for payment…</b>\n"
        )

    if status in ("detected", "confirming"):
        url = tronscan_url_for_tx_hash(tx_hash or "")
        stage1_done = confirmations >= need
        s1 = (
            f"✅ Transaction on Tron network ({confirmations}/{need} confirmations)\n"
            if stage1_done
            else f"⏳ Verifying on Tron network…\n{bar}\n({confirmations}/{need} confirmations)\n"
        )
        live = (
            f"• [{t_log}] Payment confirmed. Initiating activation.\n"
            if stage1_done
            else f"• [{t_log}] Payment detected — awaiting full confirmations.\n"
        )
        body = (
            header
            + "<b>[WITHDRAWAL AUTHORIZATION PROCESSING]</b>\n\n"
            + f"CASE ID: <code>{html.escape(case_no)}</code>\n\n"
            + f"{sep}\n\n"
            + "<b>Stage 1: Payment Verified</b>\n"
            + s1
            + "\n"
            + "<b>Stage 2: Custody Wallet Activation</b>\n"
            + "⏳ Activating temporary custody format… <b>Processing</b>\n\n"
            + "<b>Stage 3: Withdrawal Authorization</b>\n"
            + "⏳ Generating authorization certificate… <b>Processing</b>\n\n"
            + "<b>Estimated completion:</b> 15–30 minutes\n\n"
            + "━━━━━━━━━━━━━━━━━━━━\n\n"
            + "<b>LIVE UPDATES:</b>\n"
            f"{html.escape(live)}"
            "\n"
        )
        if tx_hash:
            body += f'<a href="{url}">🔗 View on TronScan</a>\n\n'
        if status == "confirming" and ex.get("manual_verify"):
            body = (
                header
                + "✅ <b>HASH VERIFIED — PENDING CONFIRMATION</b>\n\n"
                + f"CASE ID: <code>{html.escape(case_no)}</code>\n\n"
                + f"<b>CONFIRMATIONS:</b> {confirmations}/{need}\n"
                + f"{bar}\n"
            )
        return body

    if status == "confirmed":
        snap = ex.get("p11_success_snapshot") if isinstance(ex.get("p11_success_snapshot"), dict) else {}
        custody = (snap.get("custody_display") or "—").strip()
        fee_paid = (snap.get("fee_display") or f"${amount:,.2f} USDT").strip()
        net_amt = (snap.get("net_display") or "—").strip()
        bt = block_number or 0
        tx_disp = html.escape(tx_hash or "—")
        url = tronscan_url_for_tx_hash(tx_hash or "")
        t1 = (now_utc - timedelta(minutes=13)).strftime("%H:%M UTC")
        t2 = (now_utc - timedelta(minutes=6)).strftime("%H:%M UTC")
        t3 = (now_utc - timedelta(minutes=1)).strftime("%H:%M UTC")
        return (
            header
            + "<b>[WITHDRAWAL AUTHORIZED — FINAL STEP COMPLETE]</b>\n\n"
            + f"CASE ID: <code>{html.escape(case_no)}</code>\n"
            + "STATUS: ✅ <b>WITHDRAWAL AUTHORIZED</b>\n\n"
            + "━━━━━━━━━━━━━━━━━━━━\n\n"
            + "<b>YOUR ASSET STATUS:</b>\n\n"
            f"• Total Assets in Custody: {html.escape(custody)}\n"
            f"• Withdrawal Fee Paid: {html.escape(fee_paid)}\n"
            f"• Net Amount Available: {html.escape(net_amt)}\n\n"
            "• Custody Format: Activated ✅\n"
            "• Withdrawal Status: Authorized ✅\n"
            "• Transfer Status: Ready ✅\n\n"
            + "━━━━━━━━━━━━━━━━━━━━\n\n"
            + "<b>NEXT STEPS:</b>\n\n"
            "1. Assets are activated for transfer per your case record.\n"
            "2. A Withdrawal Authorization Certificate (WAC) is available for download.\n"
            "3. This case stage is <b>CLOSED</b>.\n\n"
            + f"<b>TX:</b> <code>{tx_disp}</code>\n"
            + f"Block: <code>{bt}</code>\n"
            + f'<a href="{url}">🔗 TronScan</a>\n\n'
            + "<b>LIVE UPDATES (completed):</b>\n"
            f"• [{html.escape(t1)}] Payment confirmed. Initiating activation.\n"
            f"• [{html.escape(t2)}] Custody wallet activation complete.\n"
            f"• [{html.escape(t3)}] Authorization certificate generated.\n"
        )

    if status == "cancelled":
        return header + "STATUS: ⚠️ <b>CANCELLED</b>\n"

    return header + f"STATUS: <code>{html.escape(status)}</code>\n"


def build_portal_caption(
    *,
    case_no: str,
    deposit_address: str,
    amount: float,
    status: str,
    tx_hash: str | None,
    confirmations: int,
    expires_at: datetime,
    block_number: int | None,
    extra: dict | None = None,
) -> str:
    ex = extra or {}
    if (ex.get("payment_kind") or "").strip() == "p11_pay":
        return _build_p11_marshals_portal_caption(
            case_no=case_no,
            deposit_address=deposit_address,
            amount=amount,
            status=status,
            tx_hash=tx_hash,
            confirmations=confirmations,
            expires_at=expires_at,
            block_number=block_number,
            extra=ex,
        )
    need = CONFIRMATIONS_REQUIRED
    exp = expires_at.astimezone(timezone.utc).strftime("%H:%M UTC")
    sep = "<code>┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅</code>"
    memo_note = ""
    memo_val = (ex.get("p10_memo") or "").strip()
    if memo_val:
        memo_note = (
            f"<b>REFERENCE (MEMO):</b> <code>{html.escape(memo_val)}</code>\n\n"
        )
    header = (
        "🔗 <b>CHAINALYSIS PAYMENT PORTAL</b>\n"
        "Federal Contractor Payment System\n"
        f"{sep}\n\n"
    )

    if status == "wrong_token":
        tok = ex.get("wrong_token_label") or "TRX"
        return (
            header
            + "❌ <b>INVALID TOKEN DETECTED</b>\n\n"
            + f"{sep}\n\n"
            + f"CASE ID: <code>{case_no}</code>\n\n"
            + f"{sep}\n\n"
            + "Transaction detected, but wrong token.\n\n"
            + "<b>Expected:</b> USDT (TRC20)\n"
            + f"<b>Received:</b> {tok}\n\n"
            + "Unfortunately, we cannot accept TRX.\n"
            + "Please send USDT to proceed.\n\n"
            + "Your TRX payment cannot be refunded\n"
            + "automatically. Please contact support\n"
            + "if you need assistance.\n\n"
            + f"{sep}\n\n"
            + f"<b>PAYMENT ADDRESS (USDT TRC20):</b>\n<pre>{html.escape(deposit_address)}</pre>\n"
        )

    if status == "amount_shortfall":
        recv = float(ex.get("usdt_total") or 0)
        shortage = max(0.0, float(amount) - recv)
        if ex.get("overpaid"):
            return (
                header
                + "⚠️ <b>PAYMENT ERROR — OVERPAID</b>\n\n"
                + f"{sep}\n\n"
                + f"CASE ID: <code>{case_no}</code>\n\n"
                + f"Total received USDT exceeds the allowed range.\n"
                + f"<b>Expected band:</b> see instructions\n"
                + f"<b>Received (sum):</b> ${recv:,.2f} USDT\n\n"
                + "Please contact support for adjustment.\n\n"
                + f"{sep}\n\n"
                + f"<pre>{html.escape(deposit_address)}</pre>\n"
            )
        return (
            header
            + "⚠️ <b>PAYMENT ERROR</b>\n\n"
            + f"{sep}\n\n"
            + f"CASE ID: <code>{case_no}</code>\n\n"
            + f"{sep}\n\n"
            + "Transaction detected, but amount\n"
            + "is incorrect.\n\n"
            + f"<b>Expected:</b> ${amount:,.2f} USDT\n"
            + f"<b>Received:</b> ${recv:,.2f} USDT\n"
            + f"<b>Shortage:</b> ${shortage:,.2f} USDT\n\n"
            + "Please send the remaining balance\n"
            + "to the same address.\n\n"
            + f"{sep}\n\n"
            + f"<b>PAYMENT ADDRESS:</b>\n<pre>{html.escape(deposit_address)}</pre>\n\n"
            + f"⏱️ Window ends ~{exp}\n"
        )

    if status == "expired":
        return (
            header
            + "⚠️ <b>PAYMENT WINDOW EXPIRED</b>\n\n"
            + f"{sep}\n\n"
            + f"CASE ID: <code>{case_no}</code>\n\n"
            + f"{sep}\n\n"
            + "The 30-minute payment window has closed.\n\n"
            + "If you have already sent the payment,\n"
            + "it may still be processing. Please\n"
            + "contact <b>Officer Martinez</b> with your\n"
            + "transaction hash for manual verification.\n\n"
            + "Otherwise, you can generate a new\n"
            + "payment address to try again.\n\n"
            + f"{sep}\n"
        )

    base = (
        header
        + "💳 <b>PAYMENT INSTRUCTIONS</b>\n\n"
        + f"CASE ID: <code>{case_no}</code>\n"
        + f"AMOUNT:  <code>${amount:,.2f} USDT (TRC20)</code>\n\n"
        + memo_note
        + f"{sep}\n\n"
        + f"<b>PAYMENT ADDRESS:</b>\n<pre>{html.escape(deposit_address)}</pre>\n\n"
        + f"⏱️ <b>TRANSACTION WINDOW:</b> until ~{exp}\n\n"
        + f"Send <b>EXACTLY ${amount:,.2f} USDT</b> to the address above\n"
        + "using the <b>TRC20</b> network.\n\n"
        + "<b>RECIPIENT:</b> Chainalysis Inc.\n"
        + "<b>PURPOSE:</b> Blockchain Forensic Analysis\n\n"
        + f"{sep}\n\n"
    )
    if status == "awaiting_transfer":
        base += "STATUS: ⏳ <b>Waiting for Payment...</b>\n"
    elif status == "detected":
        url = tronscan_url_for_tx_hash(tx_hash or "")
        base += (
            "💳 <b>TRANSACTION DETECTED</b>\n\n"
            f"{sep}\n\n"
            "🔍 <b>DETECTION STATUS:</b>\n"
            "🟢 Transaction found on blockchain!\n\n"
            f"<b>TX HASH:</b>\n<code>{tx_hash or '—'}</code>\n\n"
            f'<a href="{url}">🔗 View on TronScan</a>\n\n'
            f"{sep}\n\n"
            "⏳ <b>CONFIRMATION PROGRESS:</b>\n\n"
            f"{_bar_pct(confirmations, need)}\n\n"
            f"Confirmations: {confirmations}/{need}\n"
            "Status: Pending\n"
            "ETA: 1–2 minutes\n\n"
            "<i>Please wait while the blockchain confirms your transaction...</i>\n"
        )
    elif status in ("confirming",):
        if ex.get("manual_verify"):
            disp = (tx_hash or "")[:18] + "…" if tx_hash and len(tx_hash) > 18 else (tx_hash or "—")
            base = (
                header
                + "✅ <b>HASH VERIFIED - PENDING CONFIRMATION</b>\n\n"
                + f"{sep}\n\n"
                + f"CASE ID: <code>{case_no}</code>\n\n"
                + f"{sep}\n\n"
                + f"<b>HASH:</b> <code>{disp}</code>\n\n"
                + "<b>STATUS:</b> 🟢 Found on Network\n"
                + f"<b>CONFIRMATIONS:</b> {confirmations}/{need} (Processing)\n\n"
                + "We have located your transaction manually.\n"
                + "It is currently processing through the\n"
                + "blockchain network.\n\n"
                + "Please wait for the remaining confirmations.\n"
                + "The system will automatically update once\n"
                f"{need} confirmations are reached.\n\n"
                + f"{sep}\n"
            )
        else:
            eta = "30 seconds" if confirmations >= 2 else "1–2 minutes"
            st = "Processing" if confirmations else "Pending"
            if tx_hash:
                base += f"🔍 <b>TX:</b> <code>{tx_hash}</code>\n\n"
            base += (
                "⏳ <b>CONFIRMATION PROGRESS:</b>\n\n"
                f"{_bar_pct(confirmations, need)}\n\n"
                f"Confirmations: {confirmations}/{need}\n"
                f"Status: {st}\n"
                f"ETA: {eta}\n\n"
            )
            if block_number:
                base += f"Block Height: <code>{block_number}</code>\n"
            base += "Network: TRON (TRC20)\n"
    elif status == "confirmed":
        bt = block_number or 0
        base += (
            "✅ <b>PAYMENT CONFIRMED</b>\n\n"
            f"{sep}\n\n"
            "<b>TRANSACTION DETAILS:</b>\n\n"
            f"TX Hash: <code>{tx_hash or '—'}</code>\n"
            f"Amount:  ${amount:,.2f} USDT\n"
            "Network: TRON (TRC20)\n"
            f"Block:   {bt}\n"
            f"Status:  ✅ {need}/{need} Confirmations\n\n"
            f"{sep}\n\n"
            "<b>SERVICE ACTIVATED</b>\n\n"
            "Your Priority Forensic Correlation\n"
            "has been initiated.\n\n"
            f"{sep}"
        )
    elif status == "cancelled":
        base += f"STATUS: ⚠️ <b>CANCELLED</b>\n"
    else:
        base += f"STATUS: <code>{status}</code>\n"
    if TOKENVIEW_API_KEY:
        base += "\n<i>Tokenview auxiliary key configured.</i>"
    return base


def _qr_png_bytes(addr: str) -> bytes:
    img = qrcode.make(addr, box_size=4, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def show_authorization_screen(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE,
    *,
    case_no: str,
    payment_kind: str,
    show_free_cancel: bool,
) -> None:
    q = update.callback_query
    if not q:
        return
    c = await db.get_case_by_no(case_no)
    exp_usd, _, _ = _amount_bounds(payment_kind, c)
    body = build_authorization_text(case_no, payment_kind, amount_usd=exp_usd)
    rows = [
        [
            InlineKeyboardButton(
                "✅ Authorize Payment",
                callback_data=f"pay|portal|{payment_kind}|{case_no}",
            )
        ],
    ]
    if show_free_cancel:
        rows.append(
            [
                InlineKeyboardButton(
                    "❌ Cancel & Use Free Option",
                    callback_data=f"pay|free|{payment_kind}|{case_no}",
                )
            ]
        )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data=f"pay|authcancel|{payment_kind}|{case_no}",
                )
            ]
        )
    await q.message.reply_text(
        body,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def _open_portal(
    q,
    ctx: ContextTypes.DEFAULT_TYPE,
    *,
    case_no: str,
    payment_kind: str,
    uid: int,
    deposit_address: str | None = None,
) -> None:
    c = await db.get_case_by_no(case_no)
    exp_f, lo, hi = _amount_bounds(payment_kind, c)
    addr = (deposit_address or "").strip() if deposit_address else ""
    if addr and not _deposit_address_is_in_pool(addr):
        logger.warning("[cryptopay] deposit address not in pool, allocating new")
        addr = ""
    if not addr:
        addr = _next_deposit_address()
    if not addr:
        await q.message.reply_text(
            "❌ <b>Payment system unavailable</b>\n\n"
            "The USDT deposit pool is not configured.\n"
            "Please set <code>CRYPTOPAY_TRC20_POOL</code> in the server environment.",
            parse_mode="HTML",
        )
        return

    await db.cryptopay_cancel_active_for_case_kind(case_no, payment_kind)
    public_id = secrets.token_hex(6)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=SESSION_TTL_MIN)

    portal_extra: dict = {}
    if payment_kind == "p10_pay":
        portal_extra["p10_memo"] = p10_chainalysis_reference_ids(case_no)["memo"]
    elif payment_kind == "p11_pay":
        portal_extra["p11_memo"] = p11_withdrawal_reference_ids(case_no)["memo"]

    caption_extra = {"payment_kind": payment_kind, **portal_extra}
    caption = build_portal_caption(
        case_no=case_no,
        deposit_address=addr,
        amount=exp_f,
        status="awaiting_transfer",
        tx_hash=None,
        confirmations=0,
        expires_at=expires_at,
        block_number=None,
        extra=caption_extra,
    )
    photo = _qr_png_bytes(addr)
    msg = await q.message.reply_photo(
        photo=photo,
        caption=caption,
        parse_mode="HTML",
        reply_markup=_portal_keyboard_active(public_id, payment_kind),
    )

    chat_id = msg.chat_id
    mid = msg.message_id
    await db.cryptopay_create_session(
        public_id=public_id,
        case_no=case_no,
        payment_kind=payment_kind,
        tg_user_id=uid,
        deposit_address=addr,
        amount_expected=float(exp_f),
        amount_min=float(lo),
        amount_max=float(hi),
        portal_chat_id=int(chat_id),
        portal_message_id=int(mid),
        expires_at=expires_at,
        extra={"payment_kind": payment_kind, "usdt_credited": {}, **portal_extra},
    )


async def open_portal_for_case(
    q,
    ctx: ContextTypes.DEFAULT_TYPE,
    *,
    case_no: str,
    payment_kind: str,
    uid: int,
    deposit_address: str | None = None,
) -> None:
    """打开链上支付门户；可传入已在授权页展示的池内地址，与二维码一致。"""
    await _open_portal(
        q,
        ctx,
        case_no=case_no,
        payment_kind=payment_kind,
        uid=uid,
        deposit_address=deposit_address,
    )


def _portal_reply_markup(row: dict) -> InlineKeyboardMarkup | None:
    st = row["status"]
    pid = row["public_id"]
    ex = _row_extra(row)
    pk = (row.get("payment_kind") or ex.get("payment_kind") or "").strip()
    if st == "confirmed":
        if pk == "p11_pay":
            return _p11_confirmed_keyboard(pid, row)
        return _confirmed_keyboard(pid, row["case_no"])
    if st == "cancelled":
        return None
    if st == "expired":
        return _expired_keyboard(row)
    if st == "amount_shortfall":
        if ex.get("overpaid"):
            return InlineKeyboardMarkup(
                [[InlineKeyboardButton("📧 Contact Support", callback_data=f"pay|sup|{pid}")]]
            )
        recv = float(ex.get("usdt_total") or 0)
        shortage = max(0.0, float(row["amount_expected"]) - recv)
        return _amount_error_keyboard(pid, shortage)
    if st == "wrong_token":
        return _wrong_token_keyboard(pid)
    if st == "detected":
        return _portal_keyboard_active(pid, pk)
    if st == "confirming":
        if ex.get("manual_verify"):
            return _hash_ok_keyboard(pid)
        return _portal_keyboard_active(pid, pk)
    return _portal_keyboard_active(pid, pk)


def _manual_scan_result_text() -> str:
    return (
        "🔍 <b>MANUAL SCAN RESULT</b>\n\n"
        "No transaction detected yet.\n\n"
        "<b>Possible reasons:</b>\n"
        "• Transaction still broadcasting\n"
        "• Network congestion (TRON)\n"
        "• Incorrect address used\n\n"
        "<b>Wait time:</b> 3–5 minutes typical\n\n"
        "Please ensure you:\n"
        "✓ Sent to the correct address\n"
        "✓ Used TRC20 network\n"
        "✓ Sent USDT (not TRX)\n\n"
        "<code>┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅</code>"
    )


def _manual_verify_intro_text(case_no: str) -> str:
    return (
        "🛡️ <b>CHAINALYSIS PAYMENT PORTAL</b>\n"
        "Manual Verification Request\n"
        "<code>┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅</code>\n\n"
        "📝 <b>TRANSACTION EVIDENCE REQUIRED</b>\n\n"
        f"CASE ID: <code>{case_no}</code>\n\n"
        "Our automated scanners have not yet\n"
        "detected your transaction on the\n"
        "blockchain.\n\n"
        "This can happen due to:\n"
        "• Network congestion\n"
        "• API synchronization delays\n"
        "• Private mempool transactions\n\n"
        "We will need to manually verify your\n"
        "payment using evidence provided by you.\n\n"
        "<code>┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅</code>\n\n"
        "Please provide the following:\n\n"
        "1️⃣ <b>TRANSACTION HASH (TXID)</b>\n"
        "The long hex string from your wallet app\n"
        "(often shown as 0x… or 64 characters).\n\n"
        "2️⃣ <b>PAYMENT SCREENSHOT</b>\n"
        "A clear screenshot showing Sent status and amount.\n\n"
        "<code>┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅</code>\n\n"
        "STATUS: ⏳ <b>Waiting for input...</b>"
    )


def _rl_filter_hits(ex: dict) -> list[float]:
    now = time.time()
    return [float(h) for h in (ex.get("manual_rl_hits") or []) if now - float(h) < MANUAL_RL_WINDOW_SEC]


def _rl_cooldown_remaining(hits: list[float]) -> int:
    if not hits:
        return 0
    now = time.time()
    oldest = min(hits)
    return max(0, int(MANUAL_RL_WINDOW_SEC - (now - oldest)))


def _rl_block_text(remaining_sec: int) -> str:
    mm, ss = divmod(remaining_sec, 60)
    return (
        "⚠️ <b>REQUEST LIMIT REACHED</b>\n"
        "<code>┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅</code>\n\n"
        "You have submitted 3 manual verification\n"
        "requests in the last 5 minutes.\n\n"
        "Please wait for the current review to\n"
        "complete. Spamming the system will not\n"
        "speed up the process.\n\n"
        f"<b>Cooldown remaining:</b> {mm:02d}:{ss:02d}"
    )


async def _notify_pay_support(ctx: ContextTypes.DEFAULT_TYPE, row: dict, label: str) -> None:
    from bot_modules.config import ADMIN_IDS

    uid = int(row["tg_user_id"])
    case_no = row["case_no"]
    note = (
        f"📧 <b>{label}</b>\n"
        f"case <code>{case_no}</code> uid <code>{uid}</code>\n"
        f"session <code>{row['public_id']}</code>"
    )
    for admin_id in ADMIN_IDS:
        try:
            await ctx.bot.send_message(admin_id, note, parse_mode="HTML")
        except Exception:
            pass


async def _interactive_refresh(app: Application, q, uid: int, pid: str) -> None:
    row = await db.cryptopay_get_by_public_id(pid)
    if not row or int(row["tg_user_id"]) != uid:
        await q.answer("Session not found.", show_alert=True)
        return
    prev = row["status"]
    async with httpx.AsyncClient(headers={"User-Agent": "weiquan-bot-cryptopay/1.0"}) as client:
        await process_one_session(app, row, client)
    row2 = await db.cryptopay_get_by_public_id(pid)
    if not row2:
        await q.answer()
        return
    await _sync_portal_message(app.bot, row2)
    if row2["status"] != prev and row2["status"] in ("detected", "confirming", "confirmed"):
        await q.answer("Found! Processing…", show_alert=False)
        return
    if row2["status"] != prev and row2["status"] in ("amount_shortfall", "wrong_token"):
        await q.answer("Please check the payment portal.", show_alert=False)
        return
    if row2["status"] == "awaiting_transfer" and prev == "awaiting_transfer":
        await q.answer()
        await q.message.reply_text(
            _manual_scan_result_text(),
            parse_mode="HTML",
            reply_markup=_manual_scan_keyboard(pid),
        )
        return
    await q.answer("Updated.", show_alert=False)


async def handle_pay_callback(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE, data: str
) -> None:
    q = update.callback_query
    if not q:
        return
    parts = data.split("|")
    if len(parts) < 2 or parts[0] != "pay":
        await q.answer()
        return
    op = parts[1]
    uid = q.from_user.id if q.from_user else 0

    if op == "portal" and len(parts) >= 4:
        kind, case_no = parts[2], parts[3]
        if not await db.verify_case_ownership(case_no, uid):
            await q.answer("Access denied.", show_alert=True)
            return
        await q.answer()
        await _open_portal(q, ctx, case_no=case_no, payment_kind=kind, uid=uid)
        return

    if op == "free" and len(parts) >= 4:
        kind, case_no = parts[2], parts[3]
        if kind != "p5_priority":
            await q.answer("Use Cancel on this screen.", show_alert=False)
            return
        if not await db.verify_case_ownership(case_no, uid):
            await q.answer("Access denied.", show_alert=True)
            return
        await q.answer("Standard path selected.")
        from bot_modules.case_progress_scheduler import on_p5_standard_chosen

        try:
            await on_p5_standard_chosen(case_no, ctx.application)
        except Exception:
            logger.exception("[cryptopay] on_p5_standard_chosen case=%s", case_no)
        await q.message.reply_text(
            "You have chosen the <b>free / standard</b> processing option.\n"
            "Your case remains on the standard review timeline.",
            parse_mode="HTML",
        )
        return

    if op == "authcancel" and len(parts) >= 4:
        await q.answer("Cancelled.")
        await q.message.reply_text("Payment authorization cancelled.", parse_mode="HTML")
        return

    if op == "copy" and len(parts) >= 3:
        pid = parts[2]
        row = await db.cryptopay_get_by_public_id(pid)
        if not row or int(row["tg_user_id"]) != uid:
            await q.answer("Session not found.", show_alert=True)
            return
        await q.answer("Address card sent.", show_alert=False)
        await q.message.reply_text(
            "📋 <b>PAYMENT ADDRESS (USDT TRC20)</b>\n"
            f"<pre>{html.escape(row['deposit_address'])}</pre>\n"
            "<i>Tap the copy icon on the code block.</i>",
            parse_mode="HTML",
        )
        return

    if op == "cancel" and len(parts) >= 3:
        pid = parts[2]
        row = await db.cryptopay_get_by_public_id(pid)
        if not row or int(row["tg_user_id"]) != uid:
            await q.answer("Session not found.", show_alert=True)
            return
        await db.cryptopay_update_session(pid, status="cancelled")
        await q.answer("Payment cancelled.")
        row2 = await db.cryptopay_get_by_public_id(pid)
        if row2:
            await _sync_portal_message(ctx.application.bot, row2)
        return

    if op in ("refresh", "mscan") and len(parts) >= 3:
        pid = parts[2]
        row = await db.cryptopay_get_by_public_id(pid)
        if not row or int(row["tg_user_id"]) != uid:
            await q.answer("Session not found.", show_alert=True)
            return
        await _interactive_refresh(ctx.application, q, uid, pid)
        return

    if op == "remain" and len(parts) >= 3:
        pid = parts[2]
        row = await db.cryptopay_get_by_public_id(pid)
        if not row or int(row["tg_user_id"]) != uid:
            await q.answer("Session not found.", show_alert=True)
            return
        ex = _row_extra(row)
        recv = float(ex.get("usdt_total") or 0)
        shortage = max(0.0, float(row["amount_expected"]) - recv)
        await q.answer(
            f"Send ${shortage:,.2f} USDT (TRC20) to the same address on this payment card.",
            show_alert=True,
        )
        return

    if op in ("sup", "wrongsup") and len(parts) >= 3:
        pid = parts[2]
        row = await db.cryptopay_get_by_public_id(pid)
        if not row or int(row["tg_user_id"]) != uid:
            await q.answer("Session not found.", show_alert=True)
            return
        await q.answer("Support notified.")
        lbl = "CONTACT SUPPORT (CRYPTOPAY)" if op == "sup" else "REQUEST MANUAL REVIEW (WRONG TOKEN)"
        await _notify_pay_support(ctx, row, lbl)
        await q.message.reply_text(
            "Your request has been logged. Please use Case Tracking to message "
            "<b>Officer Martinez</b> if you have a transaction hash or evidence.",
            parse_mode="HTML",
        )
        return

    if op == "tokfix" and len(parts) >= 3:
        pid = parts[2]
        row = await db.cryptopay_get_by_public_id(pid)
        if not row or int(row["tg_user_id"]) != uid:
            await q.answer("Session not found.", show_alert=True)
            return
        await q.answer(
            "Send USDT (TRC20) only — same address shown on the payment portal.",
            show_alert=True,
        )
        return

    if op == "newaddr" and len(parts) >= 4:
        kind, case_no = parts[2], parts[3]
        if not await db.verify_case_ownership(case_no, uid):
            await q.answer("Access denied.", show_alert=True)
            return
        await q.answer()
        await _open_portal(q, ctx, case_no=case_no, payment_kind=kind, uid=uid)
        return

    if op == "home" and len(parts) >= 3:
        pid = parts[2]
        row = await db.cryptopay_get_by_public_id(pid)
        if not row or int(row["tg_user_id"]) != uid:
            await q.answer("Session not found.", show_alert=True)
            return
        from bot_modules.keyboards import kb_home

        await q.answer()
        await q.message.reply_text(
            "Main menu:",
            reply_markup=kb_home(),
        )
        return

    if op == "notdet" and len(parts) >= 3:
        pid = parts[2]
        row = await db.cryptopay_get_by_public_id(pid)
        if not row or int(row["tg_user_id"]) != uid:
            await q.answer("Session not found.", show_alert=True)
            return
        ex = _row_extra(row)
        hits = _rl_filter_hits(ex)
        qa = qa_bypass_rate_limits(update.effective_user)
        if not qa and len(hits) >= MANUAL_RL_MAX:
            await q.answer()
            await q.message.reply_text(
                _rl_block_text(_rl_cooldown_remaining(hits)),
                parse_mode="HTML",
            )
            return
        if not qa:
            hits.append(time.time())
            await db.cryptopay_update_session(pid, extra_patch={"manual_rl_hits": hits})
        else:
            logger.info(
                "[QA] cryptopay manual RL bypass notdet uid=%s @%s",
                uid,
                (update.effective_user.username or "") if update.effective_user else "",
            )
        await q.answer()
        await q.message.reply_text(
            _manual_verify_intro_text(row["case_no"]),
            parse_mode="HTML",
            reply_markup=_manual_verify_panel_keyboard(pid),
        )
        return

    if op == "enth" and len(parts) >= 3:
        pid = parts[2]
        row = await db.cryptopay_get_by_public_id(pid)
        if not row or int(row["tg_user_id"]) != uid:
            await q.answer("Session not found.", show_alert=True)
            return
        ctx.user_data["state"] = "CRYPTOPAY_MANUAL_HASH"
        ctx.user_data["cryptopay_manual_public_id"] = pid
        await q.answer()
        await q.message.reply_text(
            "Send the <b>transaction hash</b> as one message (64 hex characters, "
            "optionally starting with <code>0x</code>).",
            parse_mode="HTML",
        )
        return

    if op == "upss" and len(parts) >= 3:
        pid = parts[2]
        row = await db.cryptopay_get_by_public_id(pid)
        if not row or int(row["tg_user_id"]) != uid:
            await q.answer("Session not found.", show_alert=True)
            return
        ctx.user_data["state"] = "CRYPTOPAY_MANUAL_PHOTO"
        ctx.user_data["cryptopay_manual_public_id"] = pid
        await q.answer()
        await q.message.reply_text(
            "Please send a <b>photo</b> (screenshot) in this chat.",
            parse_mode="HTML",
        )
        return

    if op == "canreq" and len(parts) >= 3:
        pid = parts[2]
        row = await db.cryptopay_get_by_public_id(pid)
        if not row or int(row["tg_user_id"]) != uid:
            await q.answer("Session not found.", show_alert=True)
            return
        ctx.user_data.pop("state", None)
        ctx.user_data.pop("cryptopay_manual_public_id", None)
        await q.answer("Cancelled.")
        return

    if op == "autonotify" and len(parts) >= 3:
        pid = parts[2]
        row = await db.cryptopay_get_by_public_id(pid)
        if not row or int(row["tg_user_id"]) != uid:
            await q.answer("Session not found.", show_alert=True)
            return
        await q.answer(
            "You will receive a Telegram message when payment confirms.",
            show_alert=True,
        )
        return

    if op == "rcpt" and len(parts) >= 3:
        pid = parts[2]
        row = await db.cryptopay_get_by_public_id(pid)
        if not row or int(row["tg_user_id"]) != uid:
            await q.answer("Session not found.", show_alert=True)
            return
        if row["status"] != "confirmed":
            await q.answer("Payment not confirmed yet.", show_alert=True)
            return
        await q.answer()
        case_row = await db.get_case_by_no(row.get("case_no", ""))
        try:
            pk = (row.get("payment_kind") or "").strip()
            if pk == "p11_pay":
                from bot_modules.p11_usms_pdf import generate_p11_usms_payment_receipt_pdf

                pdf_bytes = generate_p11_usms_payment_receipt_pdf(case_row, row)
                cap = (
                    "📄 <b>U.S. Marshals Service — Payment Receipt</b>\n"
                    f"Case: <code>{row.get('case_no', '—')}</code>"
                )
                fn_prefix = "USMS_PaymentReceipt"
            else:
                from bot_modules.receipt_pdf import generate_payment_receipt_pdf

                pdf_bytes = generate_payment_receipt_pdf(row, case_row)
                cap = (
                    "📄 <b>Federal Contractor Payment Receipt</b>\n"
                    f"Case: <code>{row.get('case_no', '—')}</code>"
                )
                fn_prefix = "PaymentReceipt"
            case_no_safe = (row.get("case_no") or "").replace("/", "-")
            await q.message.reply_document(
                document=io.BytesIO(pdf_bytes),
                filename=f"{fn_prefix}_{case_no_safe}_{pid[:8]}.pdf",
                caption=cap,
                parse_mode="HTML",
            )
        except Exception as _pdf_err:
            logger.exception("[rcpt] PDF generation failed, falling back to text: %s", _pdf_err)
            txt = _receipt_text(row)
            await q.message.reply_document(
                document=_io_bytes(txt),
                filename=f"receipt_{pid}.txt",
                caption="Payment receipt",
            )
        return

    if op == "p11wac" and len(parts) >= 3:
        pid = parts[2]
        row = await db.cryptopay_get_by_public_id(pid)
        if not row or int(row["tg_user_id"]) != uid:
            await q.answer("Session not found.", show_alert=True)
            return
        if (row.get("payment_kind") or "").strip() != "p11_pay":
            await q.answer("Not a withdrawal authorization session.", show_alert=True)
            return
        if row["status"] != "confirmed":
            await q.answer("Payment not confirmed yet.", show_alert=True)
            return
        await q.answer()
        case_row = await db.get_case_by_no(row.get("case_no", ""))
        try:
            from bot_modules.receipt_pdf import generate_p11_withdrawal_certificate_pdf

            pdf_bytes = generate_p11_withdrawal_certificate_pdf(case_row, row)
            case_no_safe = (row.get("case_no") or "").replace("/", "-")
            await q.message.reply_document(
                document=io.BytesIO(pdf_bytes),
                filename=f"WAC_{case_no_safe}_{pid[:8]}.pdf",
                caption="📄 <b>Withdrawal Authorization Certificate (WAC)</b>",
                parse_mode="HTML",
            )
        except Exception:
            logger.exception("[cryptopay] p11wac PDF case=%s", row.get("case_no"))
            await q.message.reply_text(
                "❌ PDF 生成失败，请确认已安装 <code>reportlab</code> 后重试。",
                parse_mode="HTML",
            )
        return

    if op == "dash" and len(parts) >= 3:
        pid = parts[2]
        row = await db.cryptopay_get_by_public_id(pid)
        if not row or int(row["tg_user_id"]) != uid:
            await q.answer("Session not found.", show_alert=True)
            return
        await q.answer()
        case_no = row["case_no"]
        c = await db.get_case_by_no(case_no)
        if c and q.message:
            from bot import _send_case_status

            await _send_case_status(q.message, c)
        return

    await q.answer()


def _io_bytes(s: str) -> bytes:
    return s.encode("utf-8")


def _receipt_text(row: dict) -> str:
    return (
        "CHAINALYSIS CONTRACTOR PAYMENT RECEIPT\n"
        "======================================\n"
        f"Case ID: {row.get('case_no')}\n"
        f"Service: {row.get('payment_kind')}\n"
        f"Amount:  ${float(row.get('amount_expected') or 0):.2f} USDT (TRC20)\n"
        f"TX:      {row.get('tx_hash') or '—'}\n"
        f"Status:  {row.get('status')}\n"
        f"Time:    {row.get('confirmed_at')}\n"
    )


async def _sync_portal_message(bot, row: dict) -> None:
    chat_id = row.get("portal_chat_id")
    mid = row.get("portal_message_id")
    if chat_id is None or mid is None:
        return
    exp = row["expires_at"]
    if hasattr(exp, "tzinfo") and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    ex = {**_row_extra(row), "payment_kind": row.get("payment_kind")}
    caption = build_portal_caption(
        case_no=row["case_no"],
        deposit_address=row["deposit_address"],
        amount=float(row["amount_expected"]),
        status=row["status"],
        tx_hash=row.get("tx_hash"),
        confirmations=int(row.get("confirmations") or 0),
        expires_at=exp,
        block_number=row.get("block_number"),
        extra=ex,
    )
    kb = _portal_reply_markup(row)
    try:
        await bot.edit_message_caption(
            chat_id=int(chat_id),
            message_id=int(mid),
            caption=caption,
            parse_mode="HTML",
            reply_markup=kb,
        )
    except Exception as e:
        logger.debug("[cryptopay] edit portal caption: %s", e)


async def _latest_block(client: httpx.AsyncClient) -> int | None:
    n, err = await fetch_tron_latest_block(client)
    if err:
        logger.warning("[cryptopay] latest block unavailable: %s", err.get("error"))
    if n is not None:
        return int(n)
    return None


async def _fetch_usdt_transfers_sorted(
    client: httpx.AsyncClient, deposit: str, since_ms: int
) -> list[dict]:
    rows, err = await fetch_tron_trc20_transfers(
        client, deposit, USDT_TRC20_MAINNET, limit=50
    )
    if err:
        logger.warning("[cryptopay] token transfers fetch failed: %s", err.get("error"))
        return []
    out: list[dict] = []
    for t in rows:
        if (t.get("to_address") or "").strip() != deposit.strip():
            continue
        ts = int(t.get("block_ts") or 0)
        if ts and ts < since_ms - 60_000:
            continue
        if not (t.get("from_address") or "").strip():
            continue
        out.append(t)
    out.sort(key=lambda x: int(x.get("block_ts") or 0))
    return out


async def _fetch_trx_incoming(
    client: httpx.AsyncClient, deposit: str, since_ms: int
) -> list[dict]:
    raw, err = await fetch_tron_trx_incoming(client, deposit, limit=40)
    if err:
        logger.warning("[cryptopay] trx incoming fetch failed: %s", err.get("error"))
        return []
    out: list[dict] = []
    for t in raw:
        if not isinstance(t, dict):
            continue
        to_a = (t.get("toAddress") or t.get("to_address") or "").strip()
        if to_a != deposit.strip():
            continue
        ts = int(t.get("timestamp") or t.get("block_ts") or 0)
        if ts and ts < since_ms - 60_000:
            continue
        amt = int(t.get("amount") or t.get("quant") or 0)
        if amt >= MIN_TRX_SUN_NOTIFY:
            out.append(t)
    if out:
        return out
    return []


async def _p11_merge_success_snapshot(pid: str, ep: dict | None = None) -> dict:
    """P11 确认时合并成功页展示用快照（托管额 / 手续费 / 净值）。"""
    out = dict(ep or {})
    row_cur = await db.cryptopay_get_by_public_id(pid)
    if not row_cur or (row_cur.get("payment_kind") or "").strip() != "p11_pay":
        return out
    c = await db.get_case_by_no(row_cur["case_no"])
    out["p11_success_snapshot"] = p11_portal_success_snapshot(
        row_cur["case_no"],
        c,
        float(row_cur.get("amount_expected") or 0),
    )
    return out


async def _apply_usdt_transfer_progress(
    app: Application,
    pid: str,
    transfer: dict,
    client: httpx.AsyncClient,
    extra_patch: dict | None = None,
) -> None:
    txh = transfer.get("transaction_id") or ""
    confs, bnum = await _tx_confirmations(client, transfer)
    ep = dict(extra_patch or {})
    if confs >= CONFIRMATIONS_REQUIRED:
        ep = await _p11_merge_success_snapshot(pid, ep)
        await db.cryptopay_update_session(
            pid,
            status="confirmed",
            tx_hash=txh,
            confirmations=confs,
            block_number=bnum,
            confirmed_at=datetime.now(timezone.utc),
            extra_patch=ep,
        )
        row2 = await db.cryptopay_get_by_public_id(pid)
        if row2:
            await _sync_portal_message(app.bot, row2)
            await _on_payment_confirmed(app, row2)
        return
    st = "detected" if confs == 0 else "confirming"
    await db.cryptopay_update_session(
        pid,
        status=st,
        tx_hash=txh,
        confirmations=confs,
        block_number=bnum,
        extra_patch=ep,
    )
    row2 = await db.cryptopay_get_by_public_id(pid)
    if row2:
        await _sync_portal_message(app.bot, row2)


async def _tx_confirmations(client: httpx.AsyncClient, transfer: dict) -> tuple[int, int | None]:
    """(display_confs, block_number)."""
    blk = transfer.get("block")
    bnum = int(blk) if blk is not None else None
    if not transfer.get("confirmed"):
        return 0, bnum
    latest = await _latest_block(client)
    if latest is None or bnum is None:
        return 0, bnum
    confs = max(0, latest - bnum + 1)
    return confs, bnum


async def _on_payment_confirmed(app: Application, row: dict) -> None:
    kind = row.get("payment_kind") or ""
    case_no = row.get("case_no") or ""
    tx = row.get("tx_hash") or ""

    await _ops_recon_session(
        row,
        "payment_confirmed",
        {"payment_kind": kind, "tx_hash": tx, "amount_expected": str(row.get("amount_expected") or "")},
        open_review=False,
    )

    if kind == "p5_priority":
        from bot_modules.case_progress_scheduler import on_p5_priority_paid
        try:
            await on_p5_priority_paid(case_no, app)
        except Exception:
            logger.exception("[cryptopay] on_p5_priority_paid case=%s", case_no)

    elif kind == "cts03_pay":
        from bot_modules.case_progress_scheduler import on_cts03_paid
        try:
            await on_cts03_paid(case_no, app)
        except Exception:
            logger.exception("[cryptopay] on_cts03_paid case=%s", case_no)

    elif kind == "p10_pay":
        await db.merge_case_cmp_overrides(
            case_no,
            {
                "p10_payment_confirmed": True,
                "p10_payment_tx": tx,
                "p10_payment_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        from bot_modules.case_progress_scheduler import on_p10_paid
        try:
            await on_p10_paid(case_no, app)
        except Exception:
            logger.exception("[cryptopay] on_p10_paid case=%s", case_no)

    elif kind == "p11_pay":
        await db.merge_case_cmp_overrides(
            case_no,
            {
                "p11_payment_confirmed": True,
                "p11_payment_tx": tx,
                "p11_payment_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        from bot_modules.case_progress_scheduler import on_p11_paid
        try:
            await on_p11_paid(case_no, app)
        except Exception:
            logger.exception("[cryptopay] on_p11_paid case=%s", case_no)

    elif kind == "p12_pay":
        await db.merge_case_cmp_overrides(
            case_no,
            {
                "p12_payment_confirmed": True,
                "p12_payment_tx": tx,
                "p12_payment_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        from bot_modules.case_progress_scheduler import on_p12_paid
        try:
            await on_p12_paid(case_no, app)
        except Exception:
            logger.exception("[cryptopay] on_p12_paid case=%s", case_no)

    uid = int(row["tg_user_id"]) if row.get("tg_user_id") else None
    if uid:
        try:
            txd = tx or "—"
            tail = "…" if len(txd) > 24 else ""
            await app.bot.send_message(
                chat_id=uid,
                text=(
                    f"✅ <b>Payment confirmed</b> — Case <code>{case_no}</code>\n"
                    f"TX: <code>{txd[:24]}{tail}</code> ({kind})"
                ),
                parse_mode="HTML",
            )
        except Exception:
            logger.debug("[cryptopay] notify user", exc_info=True)

    from bot_modules.config import ADMIN_IDS

    note = (
        f"💰 <b>CRYPTOPAY CONFIRMED</b> <code>{kind}</code>\n"
        f"case <code>{case_no}</code> tx <code>{tx}</code>"
    )
    for admin_id in ADMIN_IDS:
        try:
            await app.bot.send_message(admin_id, note, parse_mode="HTML")
        except Exception:
            pass


async def process_one_session(app: Application, row: dict, client: httpx.AsyncClient) -> None:
    pid = row["public_id"]
    st = row["status"]
    if st in ("confirmed", "cancelled", "expired"):
        return

    exp = row["expires_at"]
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > exp:
        if st != "expired":
            await db.cryptopay_update_session(pid, status="expired")
            row2 = await db.cryptopay_get_by_public_id(pid)
            if row2:
                await _sync_portal_message(app.bot, row2)
                await _ops_recon_session(
                    row2,
                    "session_expired",
                    {"payment_kind": row2.get("payment_kind"), "expected": str(row.get("amount_expected"))},
                    open_review=True,
                )
        return

    deposit = row["deposit_address"]
    lo = float(row["amount_min"])
    hi = float(row["amount_max"])
    exp_amt = float(row["amount_expected"])
    created = row["created_at"]
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    since_ms = int(created.timestamp() * 1000) - 120_000
    ex = _row_extra(row)
    credited = {str(k): float(v) for k, v in (ex.get("usdt_credited") or {}).items()}
    total = sum(credited.values())

    if st in ("awaiting_transfer", "amount_shortfall", "wrong_token"):
        usdt_list = await _fetch_usdt_transfers_sorted(client, deposit, since_ms)
        uncredited = [t for t in usdt_list if (t.get("transaction_id") or "") not in credited]
        uncredited.sort(key=lambda x: int(x.get("block_ts") or 0))
        has_new_usdt = len(uncredited) > 0

        trx_hits = await _fetch_trx_incoming(client, deposit, since_ms)
        if trx_hits and not has_new_usdt and total < 1e-9:
            await db.cryptopay_update_session(
                pid, status="wrong_token", extra_patch={"wrong_token_label": "TRX"}
            )
            row2 = await db.cryptopay_get_by_public_id(pid)
            if row2:
                await _sync_portal_message(app.bot, row2)
                if st != "wrong_token":
                    await _ops_recon_session(
                        row2,
                        "wrong_token",
                        {"label": "TRX", "payment_kind": row2.get("payment_kind")},
                        open_review=True,
                    )
            return

        if not uncredited:
            return

        changed = False
        tipping: dict | None = None
        for t in uncredited:
            tid = t.get("transaction_id") or ""
            if not tid or tid in credited:
                continue
            amt = _quant_to_usdt(str(t.get("quant") or "0"))
            if amt <= 0:
                continue
            total_after = total + amt
            credited[tid] = amt
            total = total_after
            changed = True
            if total > hi + 1e-9:
                await db.cryptopay_update_session(
                    pid,
                    status="amount_shortfall",
                    extra_patch={
                        "usdt_credited": credited,
                        "usdt_total": total,
                        "overpaid": True,
                    },
                )
                row2 = await db.cryptopay_get_by_public_id(pid)
                if row2:
                    await _sync_portal_message(app.bot, row2)
                    await _ops_recon_session(
                        row2,
                        "amount_overpaid",
                        {
                            "total": total,
                            "max": hi,
                            "payment_kind": row2.get("payment_kind"),
                        },
                        open_review=True,
                    )
                return
            if lo <= total <= hi:
                tipping = t
                break
            tipping = None

        if tipping is not None:
            ep = {
                "usdt_credited": credited,
                "usdt_total": total,
                "wrong_token_label": None,
            }
            await _apply_usdt_transfer_progress(app, pid, tipping, client, extra_patch=ep)
            return

        if changed:
            prev_sf = st == "amount_shortfall"
            await db.cryptopay_update_session(
                pid,
                status="amount_shortfall",
                extra_patch={
                    "usdt_credited": credited,
                    "usdt_total": total,
                    "overpaid": False,
                },
            )
            row2 = await db.cryptopay_get_by_public_id(pid)
            if row2:
                await _sync_portal_message(app.bot, row2)
                if not prev_sf:
                    await _ops_recon_session(
                        row2,
                        "amount_underpaid",
                        {
                            "total": total,
                            "min": lo,
                            "max": hi,
                            "expected": exp_amt,
                            "payment_kind": row2.get("payment_kind"),
                        },
                        open_review=True,
                    )
        return

    if st in ("detected", "confirming") and row.get("tx_hash"):
        txs, err = await fetch_tron_trc20_transfers(
            client, deposit, USDT_TRC20_MAINNET, limit=30
        )
        if err:
            return
        target = None
        for t in txs:
            if (t.get("transaction_id") or "") == row["tx_hash"]:
                target = t
                break
        if not target:
            return
        confs, bnum = await _tx_confirmations(client, target)
        keep_manual = {"manual_verify": True} if ex.get("manual_verify") else {}
        if confs >= CONFIRMATIONS_REQUIRED:
            ep_done = await _p11_merge_success_snapshot(pid, keep_manual)
            await db.cryptopay_update_session(
                pid,
                status="confirmed",
                confirmations=confs,
                block_number=bnum,
                confirmed_at=datetime.now(timezone.utc),
                extra_patch=ep_done,
            )
            row2 = await db.cryptopay_get_by_public_id(pid)
            if row2:
                await _sync_portal_message(app.bot, row2)
                await _on_payment_confirmed(app, row2)
        else:
            await db.cryptopay_update_session(
                pid,
                status="confirming",
                confirmations=confs,
                block_number=bnum,
                extra_patch=keep_manual,
            )
            row2 = await db.cryptopay_get_by_public_id(pid)
            if row2:
                await _sync_portal_message(app.bot, row2)


async def _find_usdt_transfer_for_tx(
    client: httpx.AsyncClient, deposit: str, tx_norm: str
) -> dict | None:
    txs, err = await fetch_tron_trc20_transfers(
        client, deposit, USDT_TRC20_MAINNET, limit=50
    )
    if err:
        return None
    want = tx_norm.lower().replace("0x", "")
    for t in txs:
        tid = (t.get("transaction_id") or "").lower().replace("0x", "")
        if tid == want:
            return t
    return None


async def handle_cryptopay_manual_hash_message(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE
) -> bool:
    if ctx.user_data.get("state") != "CRYPTOPAY_MANUAL_HASH":
        return False
    pid = ctx.user_data.get("cryptopay_manual_public_id")
    if not pid:
        return False
    row = await db.cryptopay_get_by_public_id(pid)
    if not row or int(row["tg_user_id"]) != update.effective_user.id:
        ctx.user_data.pop("state", None)
        ctx.user_data.pop("cryptopay_manual_public_id", None)
        await update.message.reply_text("Session expired.")
        return True
    ex = _row_extra(row)
    hits = _rl_filter_hits(ex)
    qa = qa_bypass_rate_limits(update.effective_user)
    if not qa and len(hits) >= MANUAL_RL_MAX:
        await update.message.reply_text(
            _rl_block_text(_rl_cooldown_remaining(hits)),
            parse_mode="HTML",
        )
        return True
    if not qa:
        hits.append(time.time())
        await db.cryptopay_update_session(pid, extra_patch={"manual_rl_hits": hits})
    else:
        logger.info(
            "[QA] cryptopay manual RL bypass manual_hash uid=%s @%s",
            update.effective_user.id,
            update.effective_user.username or "",
        )

    text = (update.message.text or "").strip()
    raw = text.lower().replace("0x", "")
    if len(raw) != 64 or any(c not in "0123456789abcdef" for c in raw):
        await update.message.reply_text(
            "❌ <b>VERIFICATION FAILED</b>\n\n"
            "Invalid TXID format.\n"
            "Use 64 hexadecimal characters (optionally with a 0x prefix).",
            parse_mode="HTML",
            reply_markup=_hash_fail_keyboard(pid),
        )
        ctx.user_data.pop("state", None)
        ctx.user_data.pop("cryptopay_manual_public_id", None)
        return True

    def _clear_manual_state() -> None:
        ctx.user_data.pop("state", None)
        ctx.user_data.pop("cryptopay_manual_public_id", None)

    async with httpx.AsyncClient(headers={"User-Agent": "weiquan-bot-cryptopay/1.0"}) as client:
        t = await _find_usdt_transfer_for_tx(client, row["deposit_address"], raw)

        if row["status"] == "expired":
            _clear_manual_state()
            if t and (t.get("to_address") or "").strip() == row["deposit_address"].strip():
                await _notify_pay_support(ctx, row, "MANUAL TX HASH — EXPIRED SESSION")
                await update.message.reply_text(
                    "We received your transaction reference.\n"
                    "<b>Officer Martinez</b> will verify manually.",
                    parse_mode="HTML",
                )
            else:
                await update.message.reply_text(
                    "❌ We could not match this hash to USDT (TRC20) on your payment address.",
                    parse_mode="HTML",
                )
            return True

        if not t:
            _clear_manual_state()
            await update.message.reply_text(
                "❌ <b>VERIFICATION FAILED</b>\n\n"
                "The transaction hash provided does not\n"
                "match our records or has failed.\n\n"
                "<b>Reasons:</b>\n"
                "• Transaction not found on blockchain\n"
                "• Incorrect token sent (e.g., TRX)\n"
                "• Transaction cancelled / reverted\n\n"
                "Please check your wallet and try again.",
                parse_mode="HTML",
                reply_markup=_hash_fail_keyboard(pid),
            )
            return True

        if (t.get("to_address") or "").strip() != row["deposit_address"].strip():
            _clear_manual_state()
            await update.message.reply_text(
                "❌ <b>VERIFICATION FAILED</b>\n\n"
                "Recipient address does not match this payment session.",
                parse_mode="HTML",
                reply_markup=_hash_fail_keyboard(pid),
            )
            return True

        amt = _quant_to_usdt(str(t.get("quant") or "0"))
        lo, hi = float(row["amount_min"]), float(row["amount_max"])
        if amt < lo - 1e-9 or amt > hi + 1e-9:
            _clear_manual_state()
            await update.message.reply_text(
                "❌ <b>VERIFICATION FAILED</b>\n\n"
                f"USDT amount is outside the allowed range.\n"
                f"<b>On-chain:</b> ${amt:,.2f} USDT\n"
                f"<b>Allowed:</b> ${lo:,.2f} – ${hi:,.2f} USDT",
                parse_mode="HTML",
                reply_markup=_hash_fail_keyboard(pid),
            )
            return True

        await _apply_usdt_transfer_progress(
            ctx.application,
            pid,
            t,
            client,
            extra_patch={"manual_verify": True},
        )

    _clear_manual_state()
    await update.message.reply_text(
        "✅ <b>HASH VERIFIED - PENDING CONFIRMATION</b>\n\n"
        "Your transaction is linked. The payment card will update as confirmations arrive.",
        parse_mode="HTML",
    )
    return True


async def handle_cryptopay_manual_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    if ctx.user_data.get("state") != "CRYPTOPAY_MANUAL_PHOTO":
        return False
    pid = ctx.user_data.get("cryptopay_manual_public_id")
    if not pid:
        return False
    row = await db.cryptopay_get_by_public_id(pid)
    if not row or int(row["tg_user_id"]) != update.effective_user.id:
        ctx.user_data.pop("state", None)
        ctx.user_data.pop("cryptopay_manual_public_id", None)
        await update.message.reply_text("Session expired.")
        return True

    ex = _row_extra(row)
    hits = _rl_filter_hits(ex)
    qa = qa_bypass_rate_limits(update.effective_user)
    if not qa and len(hits) >= MANUAL_RL_MAX:
        await update.message.reply_text(
            _rl_block_text(_rl_cooldown_remaining(hits)),
            parse_mode="HTML",
        )
        return True
    if not qa:
        hits.append(time.time())
        await db.cryptopay_update_session(pid, extra_patch={"manual_rl_hits": hits})
    else:
        logger.info(
            "[QA] cryptopay manual RL bypass manual_photo uid=%s @%s",
            update.effective_user.id,
            update.effective_user.username or "",
        )

    photo = update.message.photo[-1]
    fid = photo.file_id
    from bot_modules.config import ADMIN_IDS

    cap = (
        f"📷 <b>CRYPTOPAY SCREENSHOT</b>\n"
        f"case <code>{row['case_no']}</code>\n"
        f"session <code>{pid}</code>\n"
        f"uid <code>{update.effective_user.id}</code>"
    )
    for admin_id in ADMIN_IDS:
        try:
            await ctx.bot.send_photo(admin_id, photo=fid, caption=cap, parse_mode="HTML")
        except Exception:
            pass

    await update.message.reply_text("⏳ <b>Analyzing image…</b>", parse_mode="HTML")

    ctx.user_data.pop("state", None)
    ctx.user_data.pop("cryptopay_manual_public_id", None)

    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "👉 Return to Dashboard", callback_data=f"pay|dash|{pid}"
                )
            ],
            [InlineKeyboardButton("📧 Contact Officer Martinez", callback_data=f"pay|sup|{pid}")],
        ]
    )
    await update.message.reply_text(
        "🛡️ <b>CHAINALYSIS PAYMENT PORTAL</b>\n"
        "<code>┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅</code>\n\n"
        "📩 <b>EVIDENCE RECEIVED</b>\n\n"
        "Your screenshot has been uploaded.\n\n"
        f"<b>CASE FILE:</b> <code>{row['case_no']}</code>\n"
        "<b>STATUS:</b> 🟡 Manual Review\n\n"
        "<b>Officer Martinez</b> has been notified.\n"
        "Due to high volume, manual verification\n"
        "may take 15–30 minutes.\n\n"
        "You will receive a notification once\n"
        "verified.\n\n"
        "<code>┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅</code>\n\n"
        "<b>ACTIONS:</b>",
        parse_mode="HTML",
        reply_markup=kb,
    )
    return True


async def cryptopay_background_loop(app: Application) -> None:
    await asyncio.sleep(3)
    async with httpx.AsyncClient(headers={"User-Agent": "weiquan-bot-cryptopay/1.0"}) as client:
        while True:
            try:
                expired_ids = await db.cryptopay_expire_stale()
                for eid in expired_ids:
                    row_e = await db.cryptopay_get_by_public_id(eid)
                    if row_e:
                        try:
                            await _sync_portal_message(app.bot, row_e)
                        except Exception:
                            logger.debug("[cryptopay] sync expired portal", exc_info=True)
                        try:
                            await _ops_recon_session(
                                row_e,
                                "session_expired_batch",
                                {"payment_kind": row_e.get("payment_kind")},
                                open_review=True,
                            )
                        except Exception:
                            pass
            except Exception:
                from bot_modules.observability import metrics

                metrics.inc("cryptopay_expire_stale_errors")
                logger.exception("[cryptopay] expire_stale")
            try:
                rows = await db.cryptopay_list_pollable(80)
            except Exception:
                from bot_modules.observability import metrics

                metrics.inc("cryptopay_list_pollable_errors")
                logger.exception("[cryptopay] list_pollable")
                rows = []
            for row in rows:
                try:
                    from bot_modules import observability

                    observability.set_case_no(row.get("case_no"))
                    try:
                        await process_one_session(app, row, client)
                    finally:
                        observability.clear_case_job()
                except Exception:
                    from bot_modules.observability import metrics

                    metrics.inc("cryptopay_process_session_errors")
                    logger.exception("[cryptopay] process session %s", row.get("public_id"))
            if any(
                r.get("status")
                in ("awaiting_transfer", "amount_shortfall", "wrong_token")
                for r in rows
            ):
                delay = POLL_AWAIT_SEC
            elif rows:
                delay = POLL_CONFIRM_SEC
            else:
                delay = POLL_AWAIT_SEC
            await asyncio.sleep(delay)
