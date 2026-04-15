"""
管理后台 — 通知管理 / 定时推送
功能：创建定时任务、查看待执行/已执行/已取消、发送历史（push_log）
执行后自动同步：update_case_status → case_phase_sync 钩子 → PDF + push_log 全更新
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import database as db
from .i18n_admin import BTN_BACK

logger = logging.getLogger(__name__)

# ── 文案 ───────────────────────────────────────────────────────────────────

NOTIFY_MENU_TITLE = (
    "🔔 通知管理\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "请选择操作："
)

_TEMPLATE_LABELS = {
    "P2": "P2 · 待审核",
    "P3": "P3 · 案件受理",
    "P4": "P4 · 转交执法",
    "P5": "P5 · 身份验证",
    "P6": "P6 · 初步审核",
    "P7": "P7 · 资产追溯",
    "P8": "P8 · 法务文件",
    "custom": "自定义内容",
}

_TEMPLATE_STATUS_MAP = {
    "P2": "PENDING REVIEW",
    "P3": "CASE ACCEPTED",
    "P4": "REFERRED TO LAW ENFORCEMENT",
    "P5": "IDENTITY VERIFICATION",
    "P6": "PRELIMINARY REVIEW",
    "P7": "ASSET TRACING",
    "P8": "LEGAL DOCUMENTATION",
}

_PHASE_MAP = {
    "P2": 2, "P3": 3, "P4": 4, "P5": 5, "P6": 6, "P7": 7, "P8": 8,
}


# ── 键盘 ───────────────────────────────────────────────────────────────────

def kb_notify_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 创建定时推送",    callback_data="adm|notify|new_step1")],
        [InlineKeyboardButton("⏳ 待执行任务",      callback_data="adm|notify|list|pending")],
        [InlineKeyboardButton("✅ 已执行任务",      callback_data="adm|notify|list|executed")],
        [InlineKeyboardButton("❌ 已取消任务",      callback_data="adm|notify|list|cancelled")],
        [InlineKeyboardButton("📜 推送发送历史",    callback_data="adm|notify|push_history")],
        [InlineKeyboardButton(BTN_BACK,            callback_data="adm|main")],
    ])


def kb_template_select() -> InlineKeyboardMarkup:
    rows = []
    for key, label in _TEMPLATE_LABELS.items():
        rows.append([InlineKeyboardButton(label, callback_data=f"adm|notify|tpl|{key}")])
    rows.append([InlineKeyboardButton(BTN_BACK, callback_data="adm|notify|menu")])
    return InlineKeyboardMarkup(rows)


def kb_target_select(template_kind: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 全部案件",         callback_data=f"adm|notify|target|all|{template_kind}")],
        [InlineKeyboardButton("📁 指定案件号",       callback_data=f"adm|notify|target|case|{template_kind}")],
        [InlineKeyboardButton("🔢 按阶段（当前P号）", callback_data=f"adm|notify|target|phase|{template_kind}")],
        [InlineKeyboardButton(BTN_BACK,             callback_data="adm|notify|new_step1")],
    ])


# ── 主处理器 ───────────────────────────────────────────────────────────────

async def handle(data: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    if not data.startswith("adm|notify|"):
        return False
    q = update.callback_query
    actor = str(update.effective_user.id)

    # ── 主菜单 ─────────────────────────────────────────────────────────────
    if data == "adm|notify|menu":
        await q.message.edit_text(
            NOTIFY_MENU_TITLE, parse_mode="HTML", reply_markup=kb_notify_menu(),
        )
        return True

    # ── Step1: 选模板 ───────────────────────────────────────────────────────
    if data == "adm|notify|new_step1":
        await q.message.edit_text(
            "📅 <b>创建定时推送</b> — 步骤1/3\n━━━━━━━━━━━━━━━━━━\n\n"
            "选择推送模板（P2–P8 为系统主题版面，含探员卡片与行动按钮）：",
            parse_mode="HTML",
            reply_markup=kb_template_select(),
        )
        return True

    # ── Step2: 选目标范围 ────────────────────────────────────────────────────
    if data.startswith("adm|notify|tpl|"):
        template_kind = data.split("|", 3)[3]
        ctx.user_data["notify_draft_tpl"] = template_kind
        ctx.user_data.pop("notify_draft_case", None)
        ctx.user_data.pop("notify_draft_phase", None)
        lbl = _TEMPLATE_LABELS.get(template_kind, template_kind)
        await q.message.edit_text(
            f"📅 <b>创建定时推送</b> — 步骤2/3\n━━━━━━━━━━━━━━━━━━\n\n"
            f"已选模板：<b>{lbl}</b>\n\n选择推送目标范围：",
            parse_mode="HTML",
            reply_markup=kb_target_select(template_kind),
        )
        return True

    # ── Step2b: 目标=全部 ────────────────────────────────────────────────────
    if data.startswith("adm|notify|target|all|"):
        template_kind = data.split("|", 4)[4]
        ctx.user_data["notify_draft_tpl"] = template_kind
        ctx.user_data["notify_draft_target"] = "all"
        ctx.user_data.pop("notify_draft_case", None)
        ctx.user_data.pop("notify_draft_phase", None)
        await _ask_custom_body_or_time(q, ctx, template_kind, "全部案件")
        return True

    # ── Step2b: 目标=指定案件 ────────────────────────────────────────────────
    if data.startswith("adm|notify|target|case|"):
        template_kind = data.split("|", 4)[4]
        ctx.user_data["notify_draft_tpl"] = template_kind
        ctx.user_data["notify_draft_target"] = "case"
        ctx.user_data["state"] = "ADM_NOTIFY_ENTER_CASE"
        await q.message.edit_text(
            "📅 <b>创建定时推送</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            "请输入案件号（如 IC3-2026-REF-0001-ABC）：",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data=f"adm|notify|tpl|{template_kind}")]]),
        )
        return True

    # ── Step2b: 目标=指定阶段 ────────────────────────────────────────────────
    if data.startswith("adm|notify|target|phase|"):
        template_kind = data.split("|", 4)[4]
        ctx.user_data["notify_draft_tpl"] = template_kind
        ctx.user_data["notify_draft_target"] = "phase"
        ctx.user_data["state"] = "ADM_NOTIFY_ENTER_PHASE"
        await q.message.edit_text(
            "📅 <b>创建定时推送</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            "请输入阶段号（2-8，推送所有当前处于该阶段的案件）：",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data=f"adm|notify|tpl|{template_kind}")]]),
        )
        return True

    # ── Step3: 输入执行时间（目标=all 时直接来这里） ─────────────────────────
    if data == "adm|notify|enter_time":
        ctx.user_data["state"] = "ADM_NOTIFY_ENTER_TIME"
        draft = _describe_draft(ctx.user_data)
        await q.message.edit_text(
            f"📅 <b>创建定时推送</b> — 步骤3/3\n━━━━━━━━━━━━━━━━━━\n\n"
            f"当前设置：\n{draft}\n\n"
            "请输入执行时间（格式：YYYY-MM-DD HH:MM，UTC）：\n"
            "<i>例：2026-04-10 14:30</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|notify|menu")]]),
        )
        return True

    # ── 列表：待执行/已执行/已取消 ────────────────────────────────────────────
    if data.startswith("adm|notify|list|"):
        status = data.split("|", 3)[3]  # pending/executed/cancelled
        rows = await db.broadcast_list(status=status, limit=15)
        label_map = {"pending": "⏳ 待执行", "executed": "✅ 已执行", "cancelled": "❌ 已取消"}
        lines = [f"{label_map.get(status, status)} 定时任务列表\n━━━━━━━━━━━━━━━━━━\n"]
        if not rows:
            lines.append("暂无记录。")
        for r in rows:
            t = r.get("scheduled_at")
            if hasattr(t, "strftime"):
                t = t.strftime("%m-%d %H:%M")
            tpl = _TEMPLATE_LABELS.get(r.get("template_kind", ""), r.get("template_kind", ""))
            tgt = _target_label(r)
            sent = r.get("sent_count", 0)
            err = r.get("error_count", 0)
            bid = r.get("id")
            stat = "✅" if r.get("executed_at") else ("❌" if r.get("cancelled") else "⏳")
            lines.append(f"{stat} #{bid} | {t} | {tpl} | {tgt} | 发{sent}/错{err}")
        kb_rows = []
        if status == "pending":
            for r in rows[:5]:
                kb_rows.append([InlineKeyboardButton(
                    f"取消 #{r['id']}", callback_data=f"adm|notify|cancel|{r['id']}"
                )])
        kb_rows.append([InlineKeyboardButton(BTN_BACK, callback_data="adm|notify|menu")])
        await q.message.edit_text(
            "\n".join(lines), parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb_rows),
        )
        return True

    # ── 取消某个任务 ───────────────────────────────────────────────────────────
    if data.startswith("adm|notify|cancel|"):
        bid = int(data.split("|")[3])
        ok = await db.broadcast_cancel(bid, actor)
        msg = f"✅ 任务 #{bid} 已取消。" if ok else f"❌ 任务 #{bid} 无法取消（已执行或不存在）。"
        await q.message.edit_text(
            msg, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|notify|list|pending")]]),
        )
        return True

    # ── 推送历史（push_log 最近 30 条） ────────────────────────────────────────
    if data == "adm|notify|push_history":
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT pl.id, pl.created_at, pl.case_no, pl.event_kind,
                       pl.delivered_at, pl.first_interaction_at, pl.last_error
                FROM push_log pl
                ORDER BY pl.created_at DESC LIMIT 30
                """
            )
        lines = ["📜 <b>推送发送历史</b>（最近30条）\n━━━━━━━━━━━━━━━━━━\n"]
        for r in rows:
            ts = r["created_at"]
            if hasattr(ts, "strftime"):
                ts = ts.strftime("%m-%d %H:%M")
            delv = "✅" if r["delivered_at"] else "❌"
            seen = "👁" if r["first_interaction_at"] else "⬜"
            err = f" [{r['last_error'][:30]}]" if r["last_error"] else ""
            lines.append(f"{delv}{seen} {ts} | {r['case_no']} | {r['event_kind']}{err}")
        if not rows:
            lines.append("暂无记录。")
        await q.message.edit_text(
            "\n".join(lines), parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|notify|menu")]]),
        )
        return True

    return False


# ── 文本输入处理（由 bot.py msg_handler 调用） ─────────────────────────────

async def handle_text(text: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE, actor: str) -> bool:
    """处理定时推送创建流程中的文本输入步骤。返回 True 表示已消耗。"""
    state = ctx.user_data.get("state", "")

    if state == "ADM_NOTIFY_ENTER_CASE":
        case_no = text.strip().upper()
        c = await db.get_case_by_no(case_no)
        if not c:
            await update.message.reply_text(f"❌ 案件 {case_no} 不存在，请重新输入：")
            return True
        ctx.user_data["notify_draft_case"] = case_no
        ctx.user_data.pop("state", None)
        tpl = ctx.user_data.get("notify_draft_tpl", "custom")
        await _ask_time_text(update, ctx, tpl, f"指定案件 {case_no}")
        return True

    if state == "ADM_NOTIFY_ENTER_PHASE":
        try:
            ph = int(text.strip())
            assert 2 <= ph <= 8
        except Exception:
            await update.message.reply_text("❌ 请输入 2–8 之间的数字：")
            return True
        ctx.user_data["notify_draft_phase"] = ph
        ctx.user_data.pop("state", None)
        tpl = ctx.user_data.get("notify_draft_tpl", "custom")
        await _ask_time_text(update, ctx, tpl, f"P{ph} 阶段所有案件")
        return True

    if state == "ADM_NOTIFY_ENTER_CUSTOM_BODY":
        ctx.user_data["notify_draft_custom_body"] = text.strip()
        ctx.user_data["state"] = "ADM_NOTIFY_ENTER_TIME"
        await update.message.reply_text(
            "✅ 自定义内容已保存。\n\n请输入执行时间（UTC）：\n格式：YYYY-MM-DD HH:MM"
        )
        return True

    if state == "ADM_NOTIFY_ENTER_TIME":
        try:
            dt = datetime.strptime(text.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            await update.message.reply_text("❌ 格式错误，请按 YYYY-MM-DD HH:MM 输入（UTC）：")
            return True

        tpl = ctx.user_data.get("notify_draft_tpl", "custom")
        target = ctx.user_data.get("notify_draft_target", "all")
        case_no = ctx.user_data.get("notify_draft_case")
        phase = ctx.user_data.get("notify_draft_phase")
        custom_body = ctx.user_data.get("notify_draft_custom_body")

        bid = await db.broadcast_create(
            created_by=actor,
            scheduled_at=dt,
            target_kind=target,
            target_case_no=case_no,
            target_phase=phase,
            template_kind=tpl,
            custom_body=custom_body,
        )

        ctx.user_data.pop("state", None)
        _clear_draft(ctx.user_data)

        tgt_label = case_no or (f"P{phase} 阶段" if phase else "全部案件")
        tpl_label = _TEMPLATE_LABELS.get(tpl, tpl)
        await update.message.reply_text(
            f"✅ 定时推送已创建（#{bid}）\n\n"
            f"模板：{tpl_label}\n"
            f"目标：{tgt_label}\n"
            f"执行时间：{dt.strftime('%Y-%m-%d %H:%M')} UTC\n\n"
            "等待系统自动执行，或在「待执行任务」中查看。"
        )
        return True

    return False


# ── Broadcast worker（由 case_progress_scheduler 调用） ────────────────────

async def execute_broadcast(app, row: dict) -> tuple[int, int]:
    """
    执行一条 scheduled_broadcasts 记录：
    - 获取目标用户列表
    - 发送主题推送模板（或自定义文本）
    - 调用 update_case_status 同步状态（模板推送才同步）
    - 写 push_log
    返回 (sent_count, error_count)
    """
    import asyncio
    from bot_modules.case_management_push import (
        build_p2_push, build_p3_push, build_p4_push,
        build_p6_preliminary_push, build_p7_asset_tracing_push,
        build_p8_legal_push, format_case_date_utc,
    )
    from bot_modules.case_progress_scheduler import build_p5_identity_push_for_case

    tpl = row.get("template_kind", "custom")
    target = row.get("target_kind", "all")
    target_case_no = row.get("target_case_no")
    target_phase = row.get("target_phase")
    custom_body = row.get("custom_body", "")
    now_str = format_case_date_utc(datetime.now(timezone.utc))

    # 获取目标案件列表
    if target == "case" and target_case_no:
        c = await db.get_case_by_no(target_case_no)
        cases = [c] if c else []
    elif target == "phase" and target_phase:
        from bot_modules.case_phase_registry import phase_from_status
        all_cases = await db.get_all_cases(limit=500)
        cases = [c for c in all_cases if phase_from_status(c.get("status", "")) == target_phase]
    else:
        cases = await db.get_all_cases(limit=500)

    sent, errors = 0, 0
    new_status = _TEMPLATE_STATUS_MAP.get(tpl)

    for c in cases:
        case_no = (c.get("case_no") or c.get("case_number") or "").strip().upper()
        tg_uid = c.get("tg_user_id")
        if not case_no or not tg_uid:
            continue
        try:
            # 构造消息内容
            if tpl == "P2":
                body, kb = build_p2_push(case_no, now_str)
            elif tpl == "P3":
                body, kb = build_p3_push(case_no, now_str)
            elif tpl == "P4":
                body, kb = build_p4_push(case_no, now_str)
            elif tpl == "P5":
                body, kb = await build_p5_identity_push_for_case(case_no)
            elif tpl == "P6":
                body, kb = build_p6_preliminary_push(case_no, c)
            elif tpl == "P7":
                body, kb = build_p7_asset_tracing_push(case_no)
            elif tpl == "P8":
                body, kb = build_p8_legal_push(case_no)
            else:
                body, kb = custom_body or "System notification.", None

            phase_num = _PHASE_MAP.get(tpl)
            push_id = await db.push_log_record(case_no, int(tg_uid), phase_num, f"broadcast_{tpl}")
            msg = await app.bot.send_message(int(tg_uid), body, parse_mode="HTML", reply_markup=kb)
            await db.push_log_mark_delivered(push_id, msg.message_id)

            # 同步案件状态 + 邮件（触发 case_phase_sync 钩子）
            if new_status:
                await db.update_case_status(case_no, new_status, actor_id="broadcast")
                # 邮件通知：写入 notification_outbox
                email = (c.get("email") or "").strip()
                if email:
                    await db.notification_outbox_enqueue(
                        case_no=case_no,
                        target_tg_id=int(tg_uid),
                        target_email=email,
                        channel="email",
                        subject=f"IC3 Case Update — {case_no}",
                        body_text=f"Your case {case_no} has been updated to {new_status}.",
                        body_html=body,
                        event_key=f"broadcast_{tpl}",
                    )

            sent += 1
            await asyncio.sleep(0.05)  # 避免 Telegram flood
        except Exception as e:
            errors += 1
            logger.warning("[broadcast] case=%s uid=%s err=%s", case_no, tg_uid, e)

    return sent, errors


# ── 内部工具函数 ────────────────────────────────────────────────────────────

async def _ask_custom_body_or_time(q, ctx, template_kind: str, target_label: str) -> None:
    if template_kind == "custom":
        ctx.user_data["state"] = "ADM_NOTIFY_ENTER_CUSTOM_BODY"
        await q.message.edit_text(
            f"📅 <b>创建定时推送</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            f"目标：{target_label}\n\n"
            "请输入自定义推送内容（支持 HTML）：",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|notify|menu")]]),
        )
    else:
        ctx.user_data["state"] = "ADM_NOTIFY_ENTER_TIME"
        lbl = _TEMPLATE_LABELS.get(template_kind, template_kind)
        await q.message.edit_text(
            f"📅 <b>创建定时推送</b> — 步骤3/3\n━━━━━━━━━━━━━━━━━━\n\n"
            f"模板：<b>{lbl}</b>\n"
            f"目标：{target_label}\n\n"
            "请输入执行时间（UTC）：\n格式：YYYY-MM-DD HH:MM",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|notify|menu")]]),
        )


async def _ask_time_text(update, ctx, template_kind: str, target_label: str) -> None:
    if template_kind == "custom":
        ctx.user_data["state"] = "ADM_NOTIFY_ENTER_CUSTOM_BODY"
        await update.message.reply_text(
            f"目标：{target_label}\n\n请输入自定义推送内容（支持 HTML）："
        )
    else:
        ctx.user_data["state"] = "ADM_NOTIFY_ENTER_TIME"
        lbl = _TEMPLATE_LABELS.get(template_kind, template_kind)
        await update.message.reply_text(
            f"✅ 目标：{target_label}\n模板：{lbl}\n\n"
            "请输入执行时间（UTC），格式：YYYY-MM-DD HH:MM"
        )


def _describe_draft(ud: dict) -> str:
    tpl = _TEMPLATE_LABELS.get(ud.get("notify_draft_tpl", ""), ud.get("notify_draft_tpl", ""))
    target = ud.get("notify_draft_target", "all")
    case_no = ud.get("notify_draft_case", "")
    phase = ud.get("notify_draft_phase", "")
    tgt = case_no or (f"P{phase} 阶段" if phase else "全部案件")
    return f"模板：{tpl}\n目标：{tgt}"


def _target_label(row: dict) -> str:
    t = row.get("target_kind", "all")
    if t == "case":
        return row.get("target_case_no") or "指定案件"
    if t == "phase":
        return f"P{row.get('target_phase')} 阶段"
    return "全部"


def _clear_draft(ud: dict) -> None:
    for k in ("notify_draft_tpl", "notify_draft_target", "notify_draft_case",
              "notify_draft_phase", "notify_draft_custom_body"):
        ud.pop(k, None)
