"""
CMP 安全联系会话：真实 liaison 记录展示、终止/超时/403 等英文模板（<pre> 等宽）。
"""

from __future__ import annotations

import html
import os
import re
import time
from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# 静默 10 分钟 → 60 秒警告 → 切断（可通过环境变量调整）
CMP_SECURE_IDLE_WARN_SEC = int(os.getenv("CMP_SECURE_IDLE_WARN_SEC", "600"))
CMP_SECURE_IDLE_GRACE_SEC = int(os.getenv("CMP_SECURE_IDLE_GRACE_SEC", "60"))


def _fmt_ts_utc(dt) -> str:
    if dt is None:
        return "00:00:00"
    if hasattr(dt, "strftime"):
        if getattr(dt, "tzinfo", None) is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%H:%M:%S")
    return str(dt)[:8]


def _sender_tag(sender_type: str | None) -> str:
    s = (sender_type or "SYSTEM").upper()
    if s == "USER":
        return "USER"
    if s in ("ADMIN", "AGENT"):
        return "OFFICER"
    return "SYSTEM"


def _strip_for_pre(text: str, max_len: int = 2000) -> str:
    t = (text or "").strip()
    t = re.sub(r"<[^>]+>", "", t)
    if len(t) > max_len:
        t = t[: max_len - 1] + "…"
    return t


async def build_secure_session_pre_body(case_no: str, slug: str) -> str:
    """真实 liaison_messages 转录（单调宽 <pre>）。"""
    import database as db

    _ = slug  # reserved for future role-specific filters
    cn = (case_no or "").strip().upper()
    rows = await db.get_liaison_messages(cn, limit=40)
    session_stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"[SECURE SESSION: {cn}] | [TIMESTAMP: {session_stamp}]",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]
    if not rows:
        lines.append("[SYSTEM] : No prior messages on file for this case.")
        lines.append("           Use INPUT COMMAND to transmit a secure message.")
    else:
        for m in reversed(rows):
            ts = _fmt_ts_utc(m.get("created_at"))
            tag = _sender_tag(m.get("sender_type"))
            body = _strip_for_pre(m.get("message_text") or "")
            blines = body.splitlines() or [""]
            for i, ln in enumerate(blines):
                if i == 0:
                    lines.append(f"[{ts}] [{tag}] : {ln}")
                else:
                    lines.append("                     " + ln)
        lines.append("")
    lines += [
        "────────────────────────────────────────────────────────────────",
        "[ COMMANDS ]",
        "【 1 】Request Expedited Forensic Trace (Requires API Fee)",
        "【 2 】Inquire about Case Status",
        "【 3 】Submit Manual Evidence",
        "────────────────────────────────────────────────────────────────",
    ]
    return "<pre>" + html.escape("\n".join(lines)) + "</pre>"


def secure_session_command_keyboard(case_no: str, slug: str) -> InlineKeyboardMarkup:
    slug_l = slug.strip().lower()
    cn = (case_no or "").strip().upper()
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("【1】Expedited Forensic Trace", callback_data=f"cmp|sv|1|{slug_l}|{cn}")],
            [InlineKeyboardButton("【2】Case Status", callback_data=f"cmp|sv|2|{slug_l}|{cn}")],
            [InlineKeyboardButton("【3】Submit Evidence", callback_data=f"cmp|sv|3|{slug_l}|{cn}")],
            [InlineKeyboardButton("INPUT COMMAND", callback_data=f"cmp|sv|m|{slug_l}|{cn}")],
            [InlineKeyboardButton("Terminate Secure Session", callback_data=f"cmp|sv|t|{slug_l}|{cn}")],
        ]
    )


def format_duration_mm_ss(start_ts: float | None, end_ts: float | None) -> str:
    if start_ts is None or end_ts is None:
        return "00m 00s"
    sec = max(0, int(end_ts - start_ts))
    m, s = divmod(sec, 60)
    return f"{m:02d}m {s:02d}s"


def format_user_terminate_success(
    *,
    log_id: str,
    duration_s: str,
    office_line: str = "Miami Field Office secure database",
) -> str:
    body = (
        "🔐 SESSION TERMINATED SUCCESSFULLY\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📁 STATUS: CLOSED\n"
        f"📝 LOG ID: {log_id}\n"
        f"⏱️ DURATION: {duration_s}\n\n"
        "🛡️ NOTICE: This session has been digitally signed and archived in the "
        f"{office_line}. No further inbound communication is permitted via this channel.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    return "<pre>" + html.escape(body) + "</pre>"


def kb_after_terminate() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("↩️ Back — Main Menu / Re-auth", callback_data="HOME")],
            [InlineKeyboardButton("Main Portal (Case Tracking)", callback_data="M03")],
        ]
    )


def format_inactivity_warning_html(seconds: int = 60) -> str:
    body = (
        "⚠️ SECURITY ALERT: INACTIVITY DETECTED\n\n"
        "For your protection, this secure channel will automatically terminate due to prolonged inactivity.\n\n"
        f"⏳ CONNECTION EXPIRING IN: {seconds} SECONDS"
    )
    return "<pre>" + html.escape(body) + "</pre>"


def format_timeout_cutoff_html() -> str:
    body = (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🛑 SESSION TIMEOUT: SECURITY PROTOCOL ACTIVATED\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "❌ STATUS: DISCONNECTED\n"
        "🛡️ REASON: SEC-TIMEOUT-PROTOCOL-04 (Inactivity)\n\n"
        "🔒 NOTICE: This encrypted channel has been automatically severed to prevent unauthorized access. "
        "To resume, please re-authenticate via the main Evidence Submission Portal.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    return "<pre>" + html.escape(body) + "</pre>"


def kb_timeout_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("RE-AUTHENTICATE / LOGIN", callback_data="HOME"),
                InlineKeyboardButton("Main Portal", callback_data="M03"),
            ],
        ]
    )


def format_officer_closed_session_html() -> str:
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "[14:45:22] [OFFICER] : Data/Selection recorded.",
        "[14:45:25] [OFFICER] : Your file has been transferred to the Forensic Processing Division for automated verification.",
        "[14:45:28] [OFFICER] : Further real-time communication is restricted to prevent data leakage during active analysis.",
        "[14:45:30] [SYSTEM] : SECURE SESSION TERMINATED BY OFFICER.",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "⚠️ NOTICE: Please await official notification via your registered contact method. "
        "Do not attempt to re-establish this secure link until instructed.",
    ]
    return "<pre>" + html.escape("\n".join(lines)) + "</pre>"


def format_access_denied_403_html() -> str:
    body = (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🚫 ACCESS DENIED\n\n"
        "ERROR CODE: 403-SEC-EXPIRED\n\n"
        "The requested secure channel is no longer active. Attempting to bypass the primary authentication gate is logged as a security incident.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    return "<pre>" + html.escape(body) + "</pre>"


def kb_access_denied() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("↩️ Main Menu / Re-auth", callback_data="HOME")],
            [InlineKeyboardButton("Main Portal", callback_data="M03")],
        ]
    )


def secure_log_id(auth_id: str) -> str:
    a = (auth_id or "AUTH").strip()
    tail = a[-12:] if len(a) >= 12 else a
    return f"SEC-LOG-{tail}"
