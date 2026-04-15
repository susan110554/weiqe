"""
管理后台 — 系统仪表盘
功能：用户统计、案件统计、探员统计、消息统计、系统状态、审计日志
"""
import html

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import database as db
from .i18n_admin import BTN_BACK


DASHBOARD_MENU_TITLE = (
    "📊 系统仪表盘\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "请选择查看："
)
BTN_USER_STATS = "👥 用户统计"
BTN_CASE_STATS = "📋 案件统计"
BTN_AGENT_STATS = "👮 探员统计"
BTN_MSG_STATS = "📨 消息统计"
BTN_SYSTEM_STATUS = "⚙️ 系统状态"
BTN_AUDIT_LOG = "📜 审计日志"
BTN_USER_ACTIVITY = "📱 活动日志（用户）"


def kb_dashboard_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_USER_STATS, callback_data="adm|dashboard|users")],
        [InlineKeyboardButton(BTN_CASE_STATS, callback_data="adm|dashboard|cases")],
        [InlineKeyboardButton(BTN_AGENT_STATS, callback_data="adm|dashboard|agents")],
        [InlineKeyboardButton(BTN_MSG_STATS, callback_data="adm|dashboard|messages")],
        [InlineKeyboardButton(BTN_SYSTEM_STATUS, callback_data="adm|dashboard|system")],
        [InlineKeyboardButton(BTN_AUDIT_LOG, callback_data="adm|dashboard|audit")],
        [InlineKeyboardButton(BTN_USER_ACTIVITY, callback_data="adm|dashboard|uact")],
        [InlineKeyboardButton(BTN_BACK, callback_data="adm|main")],
    ])


async def handle(data: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """处理 adm|dashboard|* 回调"""
    if not data.startswith("adm|dashboard|"):
        return False
    q = update.callback_query

    if data == "adm|dashboard|menu":
        await q.message.edit_text(
            DASHBOARD_MENU_TITLE,
            parse_mode="HTML",
            reply_markup=kb_dashboard_menu(),
        )
        return True

    if data == "adm|dashboard|users":
        await db.sync_users_from_cases()
        total = await db.get_user_count()
        active = await db.get_user_count("active")
        suspended = await db.get_user_count("suspended")
        body = (
            "👥 <b>用户统计</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            f"总用户数: <b>{total}</b>\n"
            f"活跃用户: <b>{active}</b>\n"
            f"已暂停: <b>{suspended}</b>\n"
        )
        await q.message.edit_text(
            body,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|dashboard|menu")]]),
        )
        return True

    if data == "adm|dashboard|cases":
        total = await db.get_case_count()
        pending = await db.get_case_count_by_status("待审核")
        in_progress = await db.get_case_count_by_status("进行中")
        closed = await db.get_case_count_by_status("已关闭")
        body = (
            "📋 <b>案件统计</b>（数据库真实数量）\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "<i>说明：首页 Total Registered Cases 为展示模型（含时间有机增量与交互 bump），"
            "与下列真实库内案件数无关。</i>\n\n"
            f"总案件数: <b>{total}</b>\n"
            f"待审核: <b>{pending}</b>\n"
            f"进行中: <b>{in_progress}</b>\n"
            f"已关闭: <b>{closed}</b>\n"
        )
        await q.message.edit_text(
            body,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|dashboard|menu")]]),
        )
        return True

    if data == "adm|dashboard|agents":
        agents = await db.get_agents()
        if not agents:
            agents = await db.get_agents_from_cases()
        active_count = sum(1 for a in agents if a.get("is_active", True))
        body = (
            "👮 <b>探员统计</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            f"探员总数: <b>{len(agents)}</b>\n"
            f"在岗: <b>{active_count}</b>\n"
        )
        await q.message.edit_text(
            body,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|dashboard|menu")]]),
        )
        return True

    if data == "adm|dashboard|messages":
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) FILTER (WHERE logged_at >= NOW() - INTERVAL '1 day') AS today,
                    COUNT(*) FILTER (WHERE logged_at >= NOW() - INTERVAL '7 days') AS week,
                    COUNT(*) FILTER (WHERE logged_at >= NOW() - INTERVAL '30 days') AS month
                FROM audit_logs
                WHERE action IN ('STATUS_UPDATED','MSG_SENT','BATCH_MSG','NOTIFY_SENT')
                """
            )
        body = (
            "📨 <b>消息统计</b>（状态更新 + 批量通知）\n━━━━━━━━━━━━━━━━━━\n\n"
            f"今日: <b>{row['today']}</b>\n"
            f"近7天: <b>{row['week']}</b>\n"
            f"近30天: <b>{row['month']}</b>\n"
        )
        await q.message.edit_text(
            body,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|dashboard|menu")]]),
        )
        return True

    if data == "adm|dashboard|system":
        # 检测数据库连通性和自动推进队列状态
        try:
            pool = await db.get_pool()
            async with pool.acquire() as conn:
                pending_jobs = await conn.fetchval(
                    "SELECT COUNT(*) FROM case_progress_jobs WHERE processed_at IS NULL AND NOT cancelled"
                )
                dlq_jobs = await conn.fetchval(
                    "SELECT COUNT(*) FROM case_progress_jobs WHERE processed_at IS NULL AND cancelled"
                )
            db_status = "✅ 正常"
        except Exception as e:
            db_status = f"❌ 异常: {e}"
            pending_jobs = "N/A"
            dlq_jobs = "N/A"
        from datetime import datetime, timezone
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        body = (
            "⚙️ <b>系统状态</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            f"数据库: {db_status}\n"
            f"Bot API: ✅ 正常\n"
            f"自动推进队列（待处理）: <b>{pending_jobs}</b>\n"
            f"已取消任务: <b>{dlq_jobs}</b>\n"
            f"查询时间: {now_utc}\n"
        )
        await q.message.edit_text(
            body,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|dashboard|menu")]]),
        )
        return True

    if data == "adm|dashboard|audit":
        logs = await db.get_audit_logs(limit=20)
        lines = ["📜 <b>审计日志</b>\n━━━━━━━━━━━━━━━━━━\n\n"]
        for r in logs[:15]:
            ts = r.get("logged_at", "")
            if hasattr(ts, "strftime"):
                ts = ts.strftime("%Y-%m-%d %H:%M")
            lines.append(f"• {ts} | {r.get('actor_id','—')} | {r.get('action','—')} | {r.get('target_id','')}")
        if not lines[1:]:
            lines.append("暂无审计记录。")
        await q.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|dashboard|menu")]]),
        )
        return True

    if data == "adm|dashboard|uact":
        peers = await db.list_user_activity_peer_uids(limit=25)
        if not peers:
            await q.message.edit_text(
                "📱 <b>活动日志（用户）</b>\n━━━━━━━━━━━━━━━━━━\n\n"
                "暂无记录（用户进入 P5 后的按钮点击与消息会写入此处）。",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(BTN_BACK, callback_data="adm|dashboard|menu")]]
                ),
            )
            return True
        lines = [
            "📱 <b>活动日志（用户）</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            "点击用户 Telegram ID 查看最近操作：\n",
        ]
        kb_rows = []
        for p in peers:
            uid = int(p["tg_user_id"])
            la = p.get("last_at")
            ts = la.strftime("%m-%d %H:%M") if hasattr(la, "strftime") else str(la or "")
            kb_rows.append(
                [
                    InlineKeyboardButton(
                        f"UID {uid} · {ts}",
                        callback_data=f"adm|dashboard|uactu|{uid}",
                    )
                ]
            )
        kb_rows.append([InlineKeyboardButton(BTN_BACK, callback_data="adm|dashboard|menu")])
        await q.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb_rows),
        )
        return True

    if data.startswith("adm|dashboard|uactu|"):
        tail = data[len("adm|dashboard|uactu|") :].strip()
        if not tail.isdigit():
            await q.answer("无效用户 ID", show_alert=True)
            return True
        uid = int(tail)
        rows = await db.get_user_activity_for_uid(uid, limit=60)
        if not rows:
            await q.message.edit_text(
                f"📱 <b>UID {uid}</b>\n━━━━━━━━━━━━━━━━━━\n\n暂无活动记录。",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⬅️ 返回列表", callback_data="adm|dashboard|uact")]]
                ),
            )
            return True
        lines = [f"📱 <b>UID {uid}</b> 最近活动\n━━━━━━━━━━━━━━━━━━\n"]
        for r in rows[:40]:
            ts = r.get("logged_at")
            tss = ts.strftime("%m-%d %H:%M:%S") if hasattr(ts, "strftime") else str(ts)
            act = html.escape((r.get("action") or "")[:80])
            cn = html.escape(str(r.get("case_no") or "—"))
            det = html.escape((r.get("detail") or "")[:200])
            lines.append(f"• {tss} | <code>{cn}</code>\n  <i>{act}</i>\n  <code>{det}</code>\n")
        await q.message.edit_text(
            "\n".join(lines)[:3900],
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ 返回列表", callback_data="adm|dashboard|uact")]]
            ),
        )
        return True

    return False
