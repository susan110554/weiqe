"""
状态变更后：仅合并 case_pdf_snapshot（不主动向用户强制推送弹窗）。
由 database.register_case_status_change_hook 在 update_case_status 成功后触发。

case_pdf_snapshot.last_phase_sync_notified：持久化阶段同步记录，重启后不丢失
（与 cases.status 一起作为「当前进度」依据；自动推进队列修复见 case_progress_scheduler）。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from telegram.ext import Application

import database as db
from .case_phase_registry import (
    pdf_phase_patch,
    phase_from_status,
    format_confirmation_email_plain,
)

logger = logging.getLogger(__name__)


def register_case_status_sync(app: Application) -> None:
    async def _hook(case_no: str, old_status: str, new_status: str) -> None:
        await run_phase_sync(app, case_no, old_status, new_status)

    db.register_case_status_change_hook(_hook)


async def run_phase_sync(
    app: Application,
    case_no: str,
    old_status: str,
    new_status: str,
) -> None:
    key = (case_no or "").strip().upper()
    if not key:
        return
    if (old_status or "").strip() == (new_status or "").strip():
        return

    c = await db.get_case_by_no(key)
    if not c:
        return

    patch = pdf_phase_patch(new_status)
    try:
        await db.merge_case_pdf_snapshot(key, patch)
    except Exception:
        logger.exception("merge_case_pdf_snapshot failed for %s", key)

    ph_old = phase_from_status(old_status)
    ph_new = phase_from_status(new_status)
    if ph_old == ph_new:
        return

    ph = patch.get("cmp_phase") or ph_new
    try:
        await db.merge_case_pdf_snapshot(
            key,
            {
                "last_phase_sync_notified": int(ph),
                "last_phase_sync_at": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%d %H:%M:%S UTC"
                ),
            },
        )
    except Exception:
        logger.exception("merge last_phase_sync_notified failed case=%s", key)


def confirmation_email_body_for_case_row(c: dict) -> str:
    cid = (c.get("case_no") or c.get("case_number") or "").strip().upper()
    st = c.get("status")
    return format_confirmation_email_plain(cid or "UNKNOWN", st)
