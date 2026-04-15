"""
管理后台 — 消息中心
功能：单发消息、群发消息、消息模板、发送历史
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import database as db
from .i18n_admin import BTN_BACK


async def _edit_or_send(q, text: str, **kwargs):
    try:
        await q.message.edit_text(text, **kwargs)
    except Exception as e:
        if "There is no text in the message to edit" in str(e):
            await q.message.reply_text(text, **kwargs)
            return
        raise


MSG_MENU_TITLE = (
    "📨 消息中心\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "请选择操作："
)
BTN_SEND_SINGLE = "📤 单发消息"
BTN_SEND_BATCH = "📤 群发消息"
BTN_MSG_TEMPLATE = "📋 消息模板"
BTN_SEND_HISTORY = "📜 发送历史"
BTN_CHAT_LOG = "💬 对话记录"


def kb_msg_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_SEND_SINGLE, callback_data="adm|msg|send_single")],
        [InlineKeyboardButton(BTN_SEND_BATCH, callback_data="adm|msg|send_batch")],
        [InlineKeyboardButton(BTN_MSG_TEMPLATE, callback_data="adm|msg|template")],
        [InlineKeyboardButton(BTN_SEND_HISTORY, callback_data="adm|msg|history")],
        [InlineKeyboardButton(BTN_CHAT_LOG, callback_data="adm|msg|chat_log")],
        [InlineKeyboardButton(BTN_BACK, callback_data="adm|main")],
    ])


async def handle(data: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """处理 adm|msg|* 回调"""
    if not data.startswith("adm|msg|"):
        return False
    q = update.callback_query

    if data == "adm|msg|menu":
        await _edit_or_send(
            q,
            MSG_MENU_TITLE,
            parse_mode="HTML",
            reply_markup=kb_msg_menu(),
        )
        return True

    if data == "adm|msg|send_single":
        ctx.user_data["state"] = "ADM_MSG_SEND_SINGLE_UID"
        await _edit_or_send(
            q,
            "📤 <b>单发消息</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            "第一步：请输入目标用户的 Telegram User ID（数字）：",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|msg|menu")]]),
        )
        return True

    if data == "adm|msg|send_batch":
        ctx.user_data["state"] = "ADM_MSG_SEND_BATCH"
        await _edit_or_send(
            q,
            "📤 <b>群发消息</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            "请输入要群发的消息内容（支持 HTML）：\n\n"
            "将发送给所有活跃用户。",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|msg|menu")]]),
        )
        return True

    if data == "adm|msg|template":
        await _edit_or_send(
            q,
            "📋 <b>消息模板</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            "预设模板：\n"
            "• 案件状态更新通知\n"
            "• 探员分配通知\n"
            "• 系统维护公告\n"
            "• 自定义模板\n\n"
            "该功能即将开放。",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|msg|menu")]]),
        )
        return True

    if data == "adm|msg|chat_log":
        msgs = await db.get_recent_liaison_messages(limit=40)
        admin_msgs = [
            m for m in msgs
            if (m.get("sender_type") or "").upper() in ("ADMIN", "AGENT")
        ]
        lines = [
            "💬 <b>管理员操作聊天记录</b>",
            "━━━━━━━━━━━━━━━━━━",
            "",
            "显示最近由管理员/探员发送的联络消息：",
            "",
        ]
        if not admin_msgs:
            lines.append("• 暂无管理员操作记录。")
        else:
            for m in admin_msgs[:20]:
                ts = str(m.get("created_at") or "")[:16].replace("T", " ")
                case_no = m.get("case_no") or "N/A"
                sender_id = m.get("sender_id") or "system"
                txt = (m.get("message_text") or "").replace("\n", " ").strip()
                if len(txt) > 60:
                    txt = txt[:60] + "..."
                lines.append(
                    f"• {ts}\n"
                    f"  案件: <code>{case_no}</code>  管理员ID: <code>{sender_id}</code>\n"
                    f"  消息: {txt or '(空)'}"
                )
        await _edit_or_send(
            q,
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 刷新", callback_data="adm|msg|chat_log")],
                [InlineKeyboardButton(BTN_BACK, callback_data="adm|msg|menu")],
            ]),
        )
        return True

    if data == "adm|msg|history":
        audits = await db.get_audit_logs(limit=8)
        liaison = await db.get_recent_liaison_messages(limit=8)
        lines = [
            "📜 <b>发送历史 / 操作日志</b>",
            "━━━━━━━━━━━━━━━━━━",
            "",
            "<b>最近管理操作:</b>",
        ]
        if audits:
            for a in audits:
                at = (a.get("logged_at") or "")
                action = a.get("action") or "N/A"
                actor = a.get("actor_id") or "N/A"
                lines.append(f"• {at} | {action} | by <code>{actor}</code>")
        else:
            lines.append("• 暂无")
        lines.extend(["", "<b>最近探员/用户联络:</b>"])
        if liaison:
            for m in liaison:
                at = (m.get("created_at") or "")
                case_no = m.get("case_no") or "N/A"
                who = m.get("sender_type") or "N/A"
                txt = (m.get("message_text") or "").replace("\n", " ").strip()
                if len(txt) > 60:
                    txt = txt[:60] + "..."
                lines.append(f"• {at} | {case_no} | {who} | {txt}")
        else:
            lines.append("• 暂无")
        await _edit_or_send(
            q,
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|msg|menu")]]),
        )
        return True

    return False
