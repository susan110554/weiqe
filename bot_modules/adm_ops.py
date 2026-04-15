"""
管理后台 — 运营闭环：人工审核队列、通知规则只读列表。
回调前缀: adm|ops|*
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import database as db
from .i18n_admin import BTN_BACK
from .runtime_config import rt


def _kb_ops_main() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton("📋 待处理队列", callback_data="adm|ops|queue")],
    ]
    if rt.FEATURE_DLQ_ADMIN:
        rows.append(
            [InlineKeyboardButton("☠️ 自动推进死信 (DLQ)", callback_data="adm|ops|dlq")]
        )
    rows.append([InlineKeyboardButton("📜 通知规则（只读）", callback_data="adm|ops|rules")])
    rows.append([InlineKeyboardButton(BTN_BACK, callback_data="adm|main")])
    return InlineKeyboardMarkup(rows)


async def handle(data: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    if not data.startswith("adm|ops|"):
        return False
    q = update.callback_query
    if data == "adm|ops|menu":
        n_open = await db.ops_review_open_count()
        body = (
            "🧰 <b>运营闭环</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"待处理/已指派工单: <b>{n_open}</b>\n\n"
            "含：支付对账异常、SLA 超时等写入的队列。\n"
            "通知经 <code>notification_outbox</code> 异步投递，支持静默时段与重试。"
        )
        await q.message.edit_text(body, parse_mode="HTML", reply_markup=_kb_ops_main())
        return True

    if data == "adm|ops|dlq":
        dlq = await db.case_progress_dlq_list_unresolved(18)
        lines = ["☠️ <b>case_progress 死信</b>\n━━━━━━━━━━━━━━━━━━\n"]
        btns: list[list[InlineKeyboardButton]] = []
        if not dlq:
            lines.append("<i>暂无未结案死信。</i>\n")
        else:
            for r in dlq:
                did = r["id"]
                lines.append(
                    f"DLQ #{did} job={r.get('original_job_id')} "
                    f"<code>{r.get('case_no')}</code> {r.get('kind')}\n"
                    f"  失败次数 {r.get('failure_count')}\n"
                )
                btns.append(
                    [
                        InlineKeyboardButton(
                            f"✅ 已处理 #{did}",
                            callback_data=f"adm|ops|dlqok|{did}",
                        )
                    ]
                )
        lines.append(
            "\n<i>结案后请视情况执行 </i><code>/repair_case 案号</code><i> 补队列。</i>"
        )
        btns.append([InlineKeyboardButton(BTN_BACK, callback_data="adm|ops|menu")])
        await q.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(btns),
        )
        return True

    if data.startswith("adm|ops|dlqok|"):
        try:
            did = int(data.split("|")[-1])
        except ValueError:
            await q.answer("无效 ID", show_alert=True)
            return True
        uid = q.from_user.id if q.from_user else 0
        ok = await db.case_progress_dlq_mark_resolved(did, f"admin:{uid}")
        await q.answer("已标记死信结案" if ok else "记录不存在", show_alert=True)
        if ok:
            await handle("adm|ops|dlq", update, ctx)
        return True

    if data == "adm|ops|queue":
        rows = await db.ops_review_list(status="open", limit=12)
        rows2 = await db.ops_review_list(status="assigned", limit=12)
        combined = rows + rows2
        lines = ["📋 <b>人工审核队列</b>\n━━━━━━━━━━━━━━━━━━\n"]
        btns: list[list[InlineKeyboardButton]] = []
        if not combined:
            lines.append("<i>暂无 open/assigned 工单。</i>\n")
        else:
            for r in combined[:15]:
                cid = r["id"]
                lines.append(
                    f"#{cid} · <code>{r.get('case_no')}</code>\n"
                    f"  {r.get('queue_kind')} — {r.get('title', '')[:40]}\n"
                )
                btns.append(
                    [
                        InlineKeyboardButton(
                            f"✅ 结案 #{cid}",
                            callback_data=f"adm|ops|resolve|{cid}",
                        )
                    ]
                )
        btns.append([InlineKeyboardButton(BTN_BACK, callback_data="adm|ops|menu")])
        await q.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(btns),
        )
        return True

    if data == "adm|ops|rules":
        rules = await db.notification_rules_list_all()
        lines = ["📜 <b>通知规则</b>（数据库只读）\n━━━━━━━━━━━━━━━━━━\n"]
        for r in rules:
            en = "✅" if r.get("enabled") else "⛔"
            lines.append(
                f"{en} <code>{r.get('event_key')}</code>\n"
                f"   渠道: {r.get('channels')} · 重试 {r.get('max_retries')} · "
                f"退避 {r.get('retry_base_sec')}s\n"
            )
        if len(rules) == 0:
            lines.append("<i>无规则记录。</i>\n")
        lines.append("\n<i>修改请直接操作表 notification_rules。</i>")
        await q.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(BTN_BACK, callback_data="adm|ops|menu")]]
            ),
        )
        return True

    if data.startswith("adm|ops|resolve|"):
        try:
            rid = int(data.split("|")[-1])
        except ValueError:
            await q.answer("无效 ID", show_alert=True)
            return True
        uid = q.from_user.id if q.from_user else 0
        ok = await db.ops_review_resolve(rid, str(uid))
        await q.answer("已标记结案" if ok else "未找到或已结案", show_alert=True)
        if ok:
            await handle("adm|ops|queue", update, ctx)
        return True

    return False
