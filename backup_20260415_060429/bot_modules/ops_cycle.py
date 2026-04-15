"""
运营闭环：通知 outbox 投递、支付异常进人工队列、case_progress SLA 巡检。
与 database 中 notification_* / ops_review_* / sla_* / payment_reconciliation_log 配合。
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from telegram.ext import Application

import database as db
from bot_modules.config import ADMIN_IDS

logger = logging.getLogger(__name__)

# SLA：排队任务在 run_at 之后多久仍未处理则告警（小时）
SLA_PROGRESS_GRACE_HOURS = float(os.getenv("OPS_SLA_PROGRESS_GRACE_HOURS", "2"))
# 通知 worker 间隔
NOTIFY_POLL_SEC = float(os.getenv("OPS_NOTIFY_POLL_SEC", "12"))
SLA_POLL_SEC = float(os.getenv("OPS_SLA_POLL_SEC", "60"))


async def _rule_retries_async(event_key: str) -> tuple[int, int]:
    rule = await db.notification_rule_get(event_key)
    if not rule:
        return 5, 60
    return int(rule.get("max_retries") or 5), int(rule.get("retry_base_sec") or 60)


async def register_progress_sla(case_no: str, job_id: int | None, run_at) -> None:
    if not job_id or run_at is None:
        return
    try:
        await db.sla_ticket_upsert_progress_job(
            case_no=case_no,
            job_id=job_id,
            run_at=run_at,
            grace_hours=SLA_PROGRESS_GRACE_HOURS,
        )
    except Exception:
        logger.exception("[ops] register_progress_sla case=%s job=%s", case_no, job_id)


async def resolve_progress_sla(job_id: int) -> None:
    try:
        await db.sla_ticket_resolve_ref("progress_job", str(int(job_id)))
    except Exception:
        logger.exception("[ops] resolve_progress_sla job=%s", job_id)


async def _user_in_quiet_hours(tg_user_id: int | None) -> tuple[bool, datetime | None]:
    if tg_user_id is None:
        return False, None
    row = await db.get_user_settings(int(tg_user_id))
    if not row:
        return False, None
    if row.get("notify_telegram") is False:
        return True, None
    qs = row.get("quiet_hour_start")
    qe = row.get("quiet_hour_end")
    if qs is None or qe is None:
        return False, None
    try:
        h = datetime.now(timezone.utc).hour
        start = int(qs)
        end = int(qe)
    except (TypeError, ValueError):
        return False, None
    if start == end:
        return False, None
    if start < end:
        in_quiet = start <= h < end
    else:
        in_quiet = h >= start or h < end
    if not in_quiet:
        return False, None
    if start < end:
        next_ok = datetime.now(timezone.utc).replace(hour=end, minute=0, second=0, microsecond=0)
        if next_ok <= datetime.now(timezone.utc):
            next_ok += timedelta(days=1)
    else:
        next_ok = datetime.now(timezone.utc).replace(hour=end, minute=0, second=0, microsecond=0)
        if h >= start:
            next_ok += timedelta(days=1)
    return True, next_ok


async def enqueue_admin_payment_alert(html: str, case_no: str | None, *, public_id: str | None = None) -> None:
    rule = await db.notification_rule_get("admin_payment_alert")
    if rule and not rule.get("enabled", True):
        return
    for aid in ADMIN_IDS:
        await db.notification_outbox_enqueue(
            event_key="admin_payment_alert",
            channel="telegram",
            body_html=html,
            target_tg_id=int(aid),
            case_no=case_no,
            meta={"public_id": public_id},
        )


async def enqueue_user_sla_reminder(tg_user_id: int, html: str, case_no: str) -> None:
    await db.notification_outbox_enqueue(
        event_key="user_sla_reminder",
        channel="telegram",
        body_html=html,
        target_tg_id=int(tg_user_id),
        case_no=case_no,
    )


async def _send_outbox_email(to: str, subject: str, body: str) -> None:
    import importlib
    import sys

    main = sys.modules.get("__main__")
    if main is not None and hasattr(main, "_send_plain_transactional_email"):
        await main._send_plain_transactional_email(to, subject, body)
        return
    bot_mod = importlib.import_module("bot")
    fn = getattr(bot_mod, "_send_plain_transactional_email", None)
    if fn is None:
        raise RuntimeError("email sender not available")
    await fn(to, subject, body)


async def record_payment_event(
    *,
    public_id: str | None,
    case_no: str,
    event_type: str,
    detail: dict | None = None,
    open_review: bool = False,
    review_kind: str = "payment_verify",
    review_title: str | None = None,
) -> None:
    await db.payment_reconciliation_log(
        public_id=public_id,
        case_no=case_no,
        event_type=event_type,
        detail=detail or {},
    )
    if not open_review:
        return
    title = review_title or f"支付异常: {event_type}"
    detail_txt = ""
    if detail:
        import json

        try:
            detail_txt = json.dumps(detail, ensure_ascii=False)[:1500]
        except Exception:
            detail_txt = str(detail)[:1500]
    rid = await db.ops_review_create(
        case_no=case_no,
        queue_kind=review_kind,
        title=title[:500],
        detail=detail_txt or None,
        meta={"public_id": public_id, "event_type": event_type},
    )
    if rid:
        html = (
            f"🧾 <b>人工队列</b> #{rid}\n"
            f"类型: <code>{review_kind}</code>\n"
            f"案件: <code>{case_no}</code>\n"
            f"事件: <code>{event_type}</code>"
        )
        await enqueue_admin_payment_alert(html, case_no, public_id=public_id)


async def notification_worker_loop(app: Application) -> None:
    await asyncio.sleep(5)
    while True:
        try:
            rows = await db.notification_outbox_fetch_due(30)
            for row in rows:
                oid = int(row["id"])
                ch = (row["channel"] or "").lower()
                event_key = row.get("event_key") or ""
                max_r, base_s = await _rule_retries_async(event_key)
                if ch == "telegram":
                    tid = row.get("target_tg_id")
                    if not tid:
                        await db.notification_outbox_mark_sent(oid)
                        continue
                    quiet, next_ok = await _user_in_quiet_hours(int(tid))
                    if quiet and next_ok:
                        await db.notification_outbox_defer(oid, next_ok, "quiet_hours")
                        continue
                    if quiet and next_ok is None:
                        await db.notification_outbox_mark_skipped(oid, "notify_telegram_off")
                        continue
                    text = row.get("body_html") or row.get("body_text") or "—"
                    try:
                        await app.bot.send_message(
                            int(tid),
                            text,
                            parse_mode="HTML" if row.get("body_html") else None,
                        )
                        await db.notification_outbox_mark_sent(oid)
                    except Exception as e:
                        err = str(e)[:500]
                        nxt = datetime.now(timezone.utc) + timedelta(
                            seconds=base_s * (2 ** min(row.get("attempts") or 0, 8))
                        )
                        await db.notification_outbox_bump_retry(oid, err, nxt, max_r)
                elif ch == "email":
                    to = (row.get("target_email") or "").strip()
                    subj = (row.get("subject") or "IC3 Notice").strip()
                    body = row.get("body_text") or row.get("body_html") or ""
                    if not to or not body:
                        await db.notification_outbox_mark_sent(oid)
                        continue
                    try:
                        await _send_outbox_email(to, subj, body)
                        await db.notification_outbox_mark_sent(oid)
                    except Exception as e:
                        err = str(e)[:500]
                        nxt = datetime.now(timezone.utc) + timedelta(
                            seconds=base_s * (2 ** min(row.get("attempts") or 0, 8))
                        )
                        await db.notification_outbox_bump_retry(oid, err, nxt, max_r)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("[ops] notification_worker_loop")
        await asyncio.sleep(NOTIFY_POLL_SEC)


async def sla_worker_loop(app: Application) -> None:
    await asyncio.sleep(20)
    while True:
        try:
            due = await db.sla_fetch_due_admin_unnotified(25)
            for t in due:
                ref_id = (t.get("ref_id") or "").strip()
                if t.get("ref_type") != "progress_job" or not ref_id.isdigit():
                    await db.sla_mark_admin_notified(int(t["id"]))
                    continue
                jid = int(ref_id)
                if not await db.sla_progress_job_still_pending(jid):
                    await db.sla_ticket_resolve_ref("progress_job", ref_id)
                    continue
                case_no = t.get("case_no") or "—"
                html = (
                    "⏱ <b>SLA · 自动化任务未按时处理</b>\n"
                    f"案件: <code>{case_no}</code>\n"
                    f"job_id: <code>{jid}</code>\n"
                    f"截止: <code>{t.get('deadline_at')}</code>\n"
                    "<i>请检查 worker / 数据库 case_progress_jobs。</i>"
                )
                rule = await db.notification_rule_get("admin_sla_breach")
                if rule is None or rule.get("enabled", True):
                    for aid in ADMIN_IDS:
                        await db.notification_outbox_enqueue(
                            event_key="admin_sla_breach",
                            channel="telegram",
                            body_html=html,
                            target_tg_id=int(aid),
                            case_no=case_no,
                            meta={"sla_id": t["id"], "job_id": jid},
                        )
                await db.ops_review_create(
                    case_no=case_no,
                    queue_kind="sla_breach",
                    title=f"SLA: progress job {jid} overdue",
                    detail=html,
                    meta={"job_id": jid, "sla_id": t["id"]},
                )
                await db.sla_mark_admin_notified(int(t["id"]))

            due_u = await db.sla_fetch_due_user_unnotified(15)
            for t in due_u:
                ref_id = (t.get("ref_id") or "").strip()
                if t.get("ref_type") != "progress_job":
                    await db.sla_mark_user_notified(int(t["id"]))
                    continue
                case_no = (t.get("case_no") or "").strip().upper()
                c = await db.get_case_by_no(case_no) if case_no else None
                uid = c.get("tg_user_id") or c.get("user_id") if c else None
                if not uid:
                    await db.sla_mark_user_notified(int(t["id"]))
                    continue
                msg = (
                    "⏱ <b>Case processing notice</b>\n"
                    f"Case <code>{case_no}</code>: your file is still in an automated queue step "
                    "longer than expected. No action is required; staff have been notified."
                )
                await enqueue_user_sla_reminder(int(uid), msg, case_no)
                await db.sla_mark_user_notified(int(t["id"]))
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("[ops] sla_worker_loop")
        await asyncio.sleep(SLA_POLL_SEC)
