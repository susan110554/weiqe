"""
P5 及之后阶段：记录用户回调与文本活动，供管理端「活动日志」查看。
"""
from __future__ import annotations

import database as db
from .config import is_admin, logger


def _status_qualifies_for_activity(status: str | None) -> bool:
    s = (status or "").upper()
    markers = (
        "IDENTITY VERIFICATION",
        "PRELIMINARY REVIEW",
        "ASSET TRACING",
        "LEGAL DOCUMENTATION",
        "SANCTION CLEARANCE",
        "CUSTODY TRANSFER",
        "CUSTODY WALLET",
        "FUND DISBURSEMENT",
        "DISBURSEMENT",
        "AUTHORIZED",
    )
    if any(m in s for m in markers):
        return True
    for p in ("P5", "P6", "P7", "P8", "P9", "P10", "P11", "P12"):
        if p in s:
            return True
    return False


def _extract_case_no_from_callback(data: str, ctx) -> str | None:
    d = (data or "").strip()
    if d.startswith("cmp|"):
        parts = d.split("|")
        if len(parts) >= 3:
            tail = (parts[-1] or "").strip().upper()
            if tail.startswith("IC3-"):
                return tail
    for key in ("last_case_id", "upload_case_no", "evid_auth_case"):
        v = ctx.user_data.get(key)
        if v and str(v).strip().upper().startswith("IC3-"):
            return str(v).strip().upper()
    return None


async def log_user_p5_phase_start(tg_user_id: int | None, case_no: str) -> None:
    if not tg_user_id or not case_no:
        return
    try:
        await db.log_user_activity(
            int(tg_user_id),
            case_no.strip().upper(),
            "p5_phase_start",
            "status→IDENTITY VERIFICATION",
        )
    except Exception as e:
        logger.warning("log_user_p5_phase_start: %s", e)


async def try_log_user_callback_activity(update, ctx, data: str) -> None:
    try:
        uid = update.effective_user.id if update.effective_user else None
        if not uid or is_admin(uid):
            return
        cn = _extract_case_no_from_callback(data, ctx)
        if not cn:
            return
        row = await db.get_case_by_no(cn)
        if not row or not _status_qualifies_for_activity(row.get("status")):
            return
        await db.log_user_activity(
            uid,
            cn,
            "callback_button",
            (data or "")[:900],
        )
    except Exception as e:
        logger.debug("try_log_user_callback_activity: %s", e)


async def try_log_user_text_activity(update, ctx, text: str) -> None:
    try:
        uid = update.effective_user.id if update.effective_user else None
        if not uid or is_admin(uid):
            return
        t = (text or "").strip()
        if not t:
            return
        cases = await db.get_cases_by_user_id(uid)
        qualifying: list[str] = []
        for row in cases:
            cn = (row.get("case_no") or "").strip().upper()
            st = row.get("status") or ""
            if cn.startswith("IC3-") and _status_qualifies_for_activity(st):
                qualifying.append(cn)
        if not qualifying:
            return
        pref = (
            (ctx.user_data.get("last_case_id") or ctx.user_data.get("upload_case_no") or "")
            .strip()
            .upper()
        )
        cn = pref if pref in qualifying else qualifying[0]
        await db.log_user_activity(
            uid,
            cn,
            "text_message",
            t[:500],
        )
    except Exception as e:
        logger.debug("try_log_user_text_activity: %s", e)
