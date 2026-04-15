"""
bot_modules/user_center.py
M09 · User Center  (replaces legacy ORG module)

UC-01  My Profile
UC-02  My Cases
UC-03  Case Progress Tracker
UC-04  Notifications & Email
UC-05  Security & Verification
UC-06  Settings
"""
from __future__ import annotations

import hashlib
import html
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import database as db
from .case_phase_registry import phase_from_status
from .crs import FEDERAL_INDEX_LINE, MAIN_SEP

logger = logging.getLogger(__name__)

SEP_LINE = "────────────────────────────────────"

# ── Helpers ────────────────────────────────────────────

def _uc_hdr(title: str) -> str:
    return (
        "IC3 | Internet Crime Complaint Center\n"
        f"User Center \u00b7 {title}\n"
        f"{MAIN_SEP}\n"
        f"{FEDERAL_INDEX_LINE}\n"
        f"{MAIN_SEP}\n\n"
    )


def _fmt_dt(dt) -> str:
    if dt is None:
        return "\u2014"
    if isinstance(dt, str):
        return dt[:16].replace("T", " ")
    try:
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(dt)[:16]


def _progress_bar(phase: int, total: int = 10) -> str:
    filled = max(0, min(phase, total))
    empty = total - filled
    return f"[{'█' * filled}{'░' * empty}] {filled * 10}%"


# ── Phase label map ────────────────────────────────────

# UC-03 时间线过长时折叠（与 Case Overview 折叠按钮风格一致）
UC03_TIMELINE_PREVIEW_LINES = 6

_PHASE_LABELS = {
    1:  "SUBMITTED",
    2:  "PENDING REVIEW",
    3:  "CASE ACCEPTED",
    4:  "REFERRED TO LAW ENFORCEMENT",
    5:  "IDENTITY VERIFICATION",
    6:  "PRELIMINARY REVIEW",
    7:  "ASSET TRACING",
    8:  "LEGAL DOCUMENTATION",
    9:  "FUND DISBURSEMENT",
    10: "CASE CLOSED",
}


# ── Keyboards ──────────────────────────────────────────

def kb_uc_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("My Profile",              callback_data="UC-01")],
        [InlineKeyboardButton("My Cases",                callback_data="UC-02")],
        [InlineKeyboardButton("Case Progress Tracker",   callback_data="UC-03")],
        [InlineKeyboardButton("Notifications & Email",   callback_data="UC-04")],
        [InlineKeyboardButton("Security & Verification", callback_data="UC-05")],
        [InlineKeyboardButton("Settings",                callback_data="UC-06")],
        [InlineKeyboardButton("About IC3 & Official Contact", callback_data="ORG-MENU")],
        [InlineKeyboardButton("⬅️ Return to Main Menu",  callback_data="HOME")],
    ])


def _kb_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ User Center", callback_data="M09")],
    ])


def _kb_uc01() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Edit Notification Email", callback_data="UC01_EDIT_EMAIL")],
        [InlineKeyboardButton("Edit Phone",              callback_data="UC01_EDIT_PHONE")],
        [InlineKeyboardButton("⬅️ User Center",          callback_data="M09")],
    ])


def _kb_uc02(cases: list) -> InlineKeyboardMarkup:
    rows = []
    for c in cases[:8]:
        no = c.get("case_no") or c.get("case_number") or "—"
        st = (c.get("status") or "SUBMITTED")[:20]
        rows.append([InlineKeyboardButton(
            f"{no}  |  {st}",
            callback_data=f"UC02_CASE|{no}",
        )])
    rows.append([InlineKeyboardButton("⬅️ User Center", callback_data="M09")])
    return InlineKeyboardMarkup(rows)


def _kb_uc03(cases: list) -> InlineKeyboardMarkup:
    rows = []
    for c in cases[:8]:
        no = c.get("case_no") or c.get("case_number") or "—"
        rows.append([InlineKeyboardButton(
            f"Track: {no}",
            callback_data=f"UC03_CASE|{no}",
        )])
    rows.append([InlineKeyboardButton("⬅️ User Center", callback_data="M09")])
    return InlineKeyboardMarkup(rows)


def _uc03_timeline_needs_fold(n_entries: int) -> bool:
    return n_entries > UC03_TIMELINE_PREVIEW_LINES


def _kb_uc03_case(case_no: str, *, need_fold: bool, timeline_expanded: bool) -> InlineKeyboardMarkup:
    cn = (case_no or "").strip()
    rows: list = []
    if need_fold:
        if timeline_expanded:
            rows.append(
                [
                    InlineKeyboardButton(
                        "[▲Collapse Timeline]",
                        callback_data=f"UC03_TL|c|{cn}",
                    )
                ]
            )
        else:
            rows.append(
                [
                    InlineKeyboardButton(
                        "[▼Expand Timeline]",
                        callback_data=f"UC03_TL|e|{cn}",
                    )
                ]
            )
    rows.append([InlineKeyboardButton("Notifications", callback_data="UC-04")])
    rows.append([InlineKeyboardButton("⬅️ User Center", callback_data="M09")])
    return InlineKeyboardMarkup(rows)


def _build_uc03_case_message(
    c: dict,
    history: list,
    *,
    timeline_expanded: bool,
) -> tuple[str, InlineKeyboardMarkup]:
    """UC-03 正文（HTML）与键盘；时间线过长时折叠。"""
    case_no = c.get("case_no") or c.get("case_number") or "—"
    st = c.get("status") or "SUBMITTED"
    phase = phase_from_status(st)
    bar = _progress_bar(phase)
    updated = _fmt_dt(c.get("updated_at"))

    hdr = _uc_hdr(f"UC-03 — Progress · {case_no}")
    lines_before_tl = [
        hdr,
        "[ CASE PROGRESS TRACKER ]",
        SEP_LINE,
        f"CASE ID      : {case_no}",
        f"CURRENT      : {st}",
        f"LAST UPDATED : {updated}",
        SEP_LINE,
        "REAL-TIME PROGRESS:",
        f"  {bar}",
        SEP_LINE,
        "PHASE TIMELINE:",
    ]

    timeline_lines: list[str] = []
    if history:
        for h in history:
            dt = _fmt_dt(h.get("changed_at"))
            ns = h.get("new_status") or "—"
            p = phase_from_status(ns)
            lbl = _PHASE_LABELS.get(p, ns)
            timeline_lines.append(f"  [{dt}]  {lbl}")
    else:
        timeline_lines.append(f"  [{_fmt_dt(c.get('created_at'))}]  SUBMITTED")

    n_tl = len(timeline_lines)
    need_fold = _uc03_timeline_needs_fold(n_tl)
    if need_fold and not timeline_expanded:
        display_tl = timeline_lines[:UC03_TIMELINE_PREVIEW_LINES]
    else:
        display_tl = timeline_lines

    html_parts: list[str] = []
    for line in lines_before_tl + display_tl:
        html_parts.append(html.escape(line))
    if need_fold and not timeline_expanded:
        html_parts.append(
            '<i>📂 Click [▼Expand Timeline] below to view the full phase timeline.</i>'
        )
    html_parts.append(html.escape(SEP_LINE))
    text = "\n".join(html_parts)
    kb = _kb_uc03_case(case_no, need_fold=need_fold, timeline_expanded=timeline_expanded)
    return text, kb


def _kb_uc04(cases: list) -> InlineKeyboardMarkup:
    rows = []
    for c in cases[:4]:
        no = c.get("case_no") or c.get("case_number") or "—"
        rows.append([InlineKeyboardButton(
            f"Resend Email: {no}",
            callback_data=f"UC04_RESEND|{no}",
        )])
    rows.append([InlineKeyboardButton("⬅️ User Center", callback_data="M09")])
    return InlineKeyboardMarkup(rows)


def _kb_uc05() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ User Center", callback_data="M09")],
    ])


def _kb_uc06(current_tz: str = "UTC") -> InlineKeyboardMarkup:
    options = [
        ("UTC",           "UTC"),
        ("US/Eastern",    "US/Eastern"),
        ("US/Pacific",    "US/Pacific"),
        ("Europe/London", "Europe/London"),
        ("Asia/Tokyo",    "Asia/Tokyo"),
    ]
    rows = []
    for label, tz_val in options:
        marker = "  [CURRENT]" if current_tz == tz_val else ""
        rows.append([InlineKeyboardButton(label + marker, callback_data=f"UC06_TZ|{tz_val}")])
    rows.append([InlineKeyboardButton("⬅️ User Center", callback_data="M09")])
    return InlineKeyboardMarkup(rows)


# ── UC-01 My Profile ───────────────────────────────────

async def show_uc01(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    uid = update.effective_user.id
    tg_name = (update.effective_user.username or update.effective_user.full_name or "—")[:30]

    user_row = await db.get_user_by_tg_id(uid)
    cases = await db.get_cases_by_tg_user(uid, limit=1)
    case = cases[0] if cases else {}
    settings = await db.get_user_settings(uid)

    email = case.get("contact") or "Not on file"
    reg_at = _fmt_dt((user_row or {}).get("created_at"))
    last_case_at = _fmt_dt(case.get("created_at"))
    tz = (settings or {}).get("timezone", "UTC")
    notif_email = (settings or {}).get("notification_email") or email

    hdr = _uc_hdr("UC-01 · My Profile")
    txt = (
        f"{hdr}"
        f"[ UC-01 · MY PROFILE ]\n"
        f"{SEP_LINE}\n"
        f"Telegram          : @{tg_name}\n"
        f"TG ID             : {uid}\n"
        f"Email on file     : {email}\n"
        f"{SEP_LINE}\n"
        f"Registered        : {reg_at}\n"
        f"Last Case Filed   : {last_case_at}\n"
        f"Timezone          : {tz}\n"
        f"Notification Email: {notif_email}\n"
        f"{SEP_LINE}\n"
    )
    await q.message.reply_text(txt, reply_markup=_kb_uc01())


async def prompt_uc01_edit_email(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    ctx.user_data["uc01_waiting"] = "email"
    await q.message.reply_text(
        "Enter new notification email address:\n(Type and send)",
        reply_markup=_kb_back(),
    )


async def prompt_uc01_edit_phone(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    ctx.user_data["uc01_waiting"] = "phone"
    await q.message.reply_text(
        "Enter new phone number:\n(Type and send)",
        reply_markup=_kb_back(),
    )


async def handle_uc01_text_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """Called from message handler when uc01_waiting is set. Returns True if handled."""
    waiting = ctx.user_data.get("uc01_waiting")
    if not waiting:
        return False
    uid = update.effective_user.id
    val = (update.message.text or "").strip()
    ctx.user_data.pop("uc01_waiting", None)
    if waiting == "email":
        await db.save_user_settings(uid, notification_email=val)
        await update.message.reply_text(
            f"Notification email updated: {val}",
            reply_markup=_kb_back(),
        )
    elif waiting == "phone":
        await db.save_user_settings(uid, notification_phone=val)
        await update.message.reply_text(
            f"Phone updated: {val}",
            reply_markup=_kb_back(),
        )
    return True


# ── UC-02 My Cases ─────────────────────────────────────

async def show_uc02(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    uid = update.effective_user.id
    cases = await db.get_cases_by_tg_user(uid)

    hdr = _uc_hdr("UC-02 · My Cases")
    if not cases:
        await q.message.reply_text(
            hdr + f"[ UC-02 · MY CASES ]\n{SEP_LINE}\nNo cases on file.\n{SEP_LINE}",
            reply_markup=_kb_back(),
        )
        return

    lines = [hdr, "[ UC-02 · MY CASES ]", SEP_LINE]
    for i, c in enumerate(cases[:8], 1):
        no = c.get("case_no") or c.get("case_number") or "—"
        st = c.get("status") or "SUBMITTED"
        cr = _fmt_dt(c.get("created_at"))
        lines += [f"{i}. {no}", f"   Status : {st}", f"   Filed  : {cr}", ""]
    lines += [SEP_LINE, f"Total: {len(cases)} case(s)"]
    await q.message.reply_text("\n".join(lines), reply_markup=_kb_uc02(cases))


async def show_uc02_case_detail(update: Update, ctx: ContextTypes.DEFAULT_TYPE, case_no: str) -> None:
    q = update.callback_query
    c = await db.get_case_by_no(case_no)
    if not c:
        await q.message.reply_text("Case not found.", reply_markup=_kb_back())
        return

    st = c.get("status") or "SUBMITTED"
    phase = phase_from_status(st)
    bar = _progress_bar(phase)
    agent = c.get("agent_code") or "Pending Assignment"

    hdr = _uc_hdr(f"UC-02 — Case Detail · {case_no}")
    txt = (
        f"{hdr}"
        f"[ CASE DETAIL ]\n"
        f"{SEP_LINE}\n"
        f"CASE ID      : {case_no}\n"
        f"STATUS       : {st}\n"
        f"FILED        : {_fmt_dt(c.get('created_at'))}\n"
        f"LAST UPDATED : {_fmt_dt(c.get('updated_at'))}\n"
        f"{SEP_LINE}\n"
        f"PROGRESS     : {bar}\n"
        f"{SEP_LINE}\n"
        f"PLATFORM     : {c.get('platform') or '—'}\n"
        f"AMOUNT       : {c.get('amount') or '—'} {c.get('coin') or ''}\n"
        f"ASSIGNED     : {agent}\n"
        f"{SEP_LINE}\n"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("[▼ Real-Time Progress]", callback_data=f"UC03_CASE|{case_no}")],
        [InlineKeyboardButton("⬅️ My Cases",         callback_data="UC-02")],
    ])
    await q.message.reply_text(txt, reply_markup=kb)


# ── UC-03 Case Progress Tracker ────────────────────────

async def show_uc03(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    uid = update.effective_user.id
    cases = await db.get_cases_by_tg_user(uid)

    hdr = _uc_hdr("UC-03 · Case Progress Tracker")
    if not cases:
        await q.message.reply_text(hdr + "No cases on file.", reply_markup=_kb_back())
        return
    if len(cases) == 1:
        no = cases[0].get("case_no") or cases[0].get("case_number") or ""
        await show_uc03_case(update, ctx, no)
        return
    await q.message.reply_text(hdr + "Select a case to view progress:", reply_markup=_kb_uc03(cases))


async def show_uc03_case(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE,
    case_no: str,
    *,
    timeline_expanded: bool = False,
    edit_message: bool = False,
) -> None:
    q = update.callback_query
    uid = update.effective_user.id
    c = await db.get_case_by_no(case_no)
    if not c:
        if edit_message:
            try:
                await q.message.edit_text("Case not found.", reply_markup=_kb_back())
            except Exception:
                await q.message.reply_text("Case not found.", reply_markup=_kb_back())
        else:
            await q.message.reply_text("Case not found.", reply_markup=_kb_back())
        return

    if int(c.get("tg_user_id") or 0) != uid:
        await q.answer("Access denied.", show_alert=True)
        return

    history = await db.get_status_history_for_case(case_no, limit=15)
    text, kb = _build_uc03_case_message(c, history, timeline_expanded=timeline_expanded)

    if edit_message:
        try:
            await q.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await q.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await q.message.reply_text(text, parse_mode="HTML", reply_markup=kb)


# ── UC-04 Notifications & Email ────────────────────────

async def show_uc04(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    uid = update.effective_user.id
    cases = await db.get_cases_by_tg_user(uid)

    hdr = _uc_hdr("UC-04 · Notifications & Email")
    if not cases:
        await q.message.reply_text(hdr + "No cases on file.", reply_markup=_kb_back())
        return

    lines = [hdr, "[ UC-04 · NOTIFICATIONS ]"]
    for c in cases[:3]:
        no = c.get("case_no") or c.get("case_number") or "—"
        lines += [SEP_LINE, f"CASE: {no}", ""]
        history = await db.get_status_history_for_case(no, limit=10)
        if history:
            for h in reversed(history):
                dt = _fmt_dt(h.get("changed_at"))
                ns = h.get("new_status") or "—"
                p = phase_from_status(ns)
                lbl = _PHASE_LABELS.get(p, ns)
                lines.append(f"  [{dt}]  {lbl}")
        else:
            cr = _fmt_dt(c.get("created_at"))
            lines.append(f"  [{cr}]  SUBMITTED")

    lines += [SEP_LINE, ""]
    await q.message.reply_text("\n".join(lines), reply_markup=_kb_uc04(cases))


async def handle_uc04_resend(update: Update, ctx: ContextTypes.DEFAULT_TYPE, case_no: str) -> None:
    q = update.callback_query
    await q.answer("Confirm to resend...")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Send Email", callback_data=f"cphase|email|{case_no}")],
        [InlineKeyboardButton("⬅️ Back",       callback_data="UC-04")],
    ])
    await q.message.reply_text(
        f"Resend confirmation email for:\n{case_no}\n\nTap Send Email to confirm.",
        reply_markup=kb,
    )


# ── UC-05 Security & Verification ─────────────────────

async def show_uc05(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    uid = update.effective_user.id

    user_row = await db.get_user_by_tg_id(uid)
    cases = await db.get_cases_by_tg_user(uid, limit=1)

    status = (user_row or {}).get("status", "active").upper()
    reg_at = _fmt_dt((user_row or {}).get("created_at"))
    last_case_at = _fmt_dt(cases[0].get("created_at") if cases else None)
    pin_row = await db.get_user_pin_hash(uid)
    pin_status = "SET" if pin_row else "NOT SET"

    hdr = _uc_hdr("UC-05 · Security & Verification")
    txt = (
        f"{hdr}"
        f"[ UC-05 · SECURITY ]\n"
        f"{SEP_LINE}\n"
        f"Account Status   : {status}\n"
        f"Registered       : {reg_at}\n"
        f"Last Case Filed  : {last_case_at}\n"
        f"PIN Status       : {pin_status}\n"
        f"{SEP_LINE}\n"
        "Session activity is monitored per\n"
        "federal audit compliance standards.\n"
        "All access is logged and traceable.\n"
        f"{SEP_LINE}\n"
    )
    await q.message.reply_text(txt, reply_markup=_kb_uc05())


# ── UC-06 Settings ─────────────────────────────────────

async def show_uc06(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    uid = update.effective_user.id
    settings = await db.get_user_settings(uid)
    tz = (settings or {}).get("timezone", "UTC")

    hdr = _uc_hdr("UC-06 · Settings")
    txt = (
        f"{hdr}"
        f"[ UC-06 · SETTINGS ]\n"
        f"{SEP_LINE}\n"
        f"Current Timezone : {tz}\n"
        f"{SEP_LINE}\n"
        "Select timezone to update:\n"
    )
    await q.message.reply_text(txt, reply_markup=_kb_uc06(tz))


async def handle_uc06_tz(update: Update, ctx: ContextTypes.DEFAULT_TYPE, tz_val: str) -> None:
    q = update.callback_query
    uid = update.effective_user.id
    await db.save_user_settings(uid, timezone=tz_val)
    hdr = _uc_hdr("UC-06 · Settings")
    txt = (
        f"{hdr}"
        f"[ UC-06 · SETTINGS ]\n"
        f"{SEP_LINE}\n"
        f"Timezone updated : {tz_val}\n"
        f"{SEP_LINE}\n"
        "Select timezone to update:\n"
    )
    await q.message.reply_text(txt, reply_markup=_kb_uc06(tz_val))


# ── Main dispatcher ────────────────────────────────────

async def handle_uc_callback(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE,
    data: str,
) -> bool:
    """Route UC-* callbacks. Returns True if handled."""
    q = update.callback_query

    if data == "UC-01":
        await q.answer()
        await show_uc01(update, ctx)
        return True

    if data == "UC01_EDIT_EMAIL":
        await q.answer()
        await prompt_uc01_edit_email(update, ctx)
        return True

    if data == "UC01_EDIT_PHONE":
        await q.answer()
        await prompt_uc01_edit_phone(update, ctx)
        return True

    if data == "UC-02":
        await q.answer()
        await show_uc02(update, ctx)
        return True

    if data.startswith("UC02_CASE|"):
        await q.answer()
        await show_uc02_case_detail(update, ctx, data.split("|", 1)[1])
        return True

    if data == "UC-03":
        await q.answer()
        await show_uc03(update, ctx)
        return True

    if data.startswith("UC03_TL|"):
        parts = data.split("|", 2)
        if len(parts) < 3:
            await q.answer()
            return True
        _, mode, cn = parts
        expanded = mode == "e"
        await q.answer()
        await show_uc03_case(
            update, ctx, cn, timeline_expanded=expanded, edit_message=True
        )
        return True

    if data.startswith("UC03_CASE|"):
        await q.answer()
        await show_uc03_case(update, ctx, data.split("|", 1)[1])
        return True

    if data == "UC-04":
        await q.answer()
        await show_uc04(update, ctx)
        return True

    if data.startswith("UC04_RESEND|"):
        await q.answer()
        await handle_uc04_resend(update, ctx, data.split("|", 1)[1])
        return True

    if data == "UC-05":
        await q.answer()
        await show_uc05(update, ctx)
        return True

    if data == "UC-06":
        await q.answer()
        await show_uc06(update, ctx)
        return True

    if data.startswith("UC06_TZ|"):
        await q.answer()
        await handle_uc06_tz(update, ctx, data.split("|", 1)[1])
        return True

    return False
