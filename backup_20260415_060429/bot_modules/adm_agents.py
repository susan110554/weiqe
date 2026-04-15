"""管理后台 — 探员调度（含 IC3 团队、案件列表、联络记录入口）。"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import database as db
from .agent_roster import AGENT_PROFILES_ORDERED
from .i18n_admin import (
    BTN_BACK,
    AGENTS_MENU_TITLE,
    BTN_VIEW_AGENTS, BTN_AGENTS_ASSIGN, BTN_REASSIGN,
    AGENTS_LIST_HEADER, AGENT_ITEM, NO_AGENTS,
)


async def _edit_or_send(q, text: str, **kwargs):
    try:
        await q.message.edit_text(text, **kwargs)
    except Exception as e:
        if "There is no text in the message to edit" in str(e):
            await q.message.reply_text(text, **kwargs)
            return
        raise


def kb_agents_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_VIEW_AGENTS, callback_data="adm|agents|list")],
        [InlineKeyboardButton("🧭 IC3 团队面板", callback_data="adm|agents|team")],
        [InlineKeyboardButton(BTN_AGENTS_ASSIGN, callback_data="adm|agents|assign_menu")],
        [InlineKeyboardButton(BTN_REASSIGN, callback_data="adm|agents|reassign")],
        [InlineKeyboardButton(BTN_BACK, callback_data="adm|main")],
    ])


async def handle(data: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """处理 adm|agents|* 回调"""
    if not data.startswith("adm|agents|"):
        return False
    q = update.callback_query

    if data == "adm|agents|menu":
        await _edit_or_send(q, AGENTS_MENU_TITLE, parse_mode="HTML", reply_markup=kb_agents_menu())
        return True

    if data == "adm|agents|list":
        agents = await db.get_agents()
        if not agents:
            agents = [
                {"agent_code": r["agent_code"], "office_name_zh": None, "office_name_en": None, "is_active": True}
                for r in await db.get_agents_from_cases()
            ]
        lines = [AGENTS_LIST_HEADER]
        for a in agents:
            office = a.get("office_name_zh") or a.get("office_name_en") or "—"
            active = "✓" if a.get("is_active", True) else "✗"
            lines.append(AGENT_ITEM.format(
                agent_code=a.get("agent_code", "?"),
                office=office,
                active=active,
            ))
        if not agents:
            lines.append(NO_AGENTS)
        btns = [[InlineKeyboardButton(BTN_BACK, callback_data="adm|agents|menu")]]
        await _edit_or_send(q, "\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))
        return True

    if data == "adm|agents|team":
        counts = await db.get_agent_unread_counts()
        lines = [
            "🧭 <b>IC3 Cybercrime Investigation Team</b>",
            "━━━━━━━━━━━━━━━━━━",
            "",
            "选择探员查看：名下案件、用户资料、联络记录。",
            "",
        ]
        rows = []
        for idx, p in enumerate(AGENT_PROFILES_ORDERED):
            unread = int(counts.get(p.name_en, 0))
            badge = f" ({unread})" if unread > 0 else ""
            rows.append([InlineKeyboardButton(
                f"{idx+1}. {p.name_en}{badge}",
                callback_data=f"adm|agents|team|{idx}",
            )])
        rows.append([InlineKeyboardButton(BTN_BACK, callback_data="adm|agents|menu")])
        await _edit_or_send(
            q,
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return True

    if data.startswith("adm|agents|team|"):
        try:
            idx = int(data.split("|")[3])
            prof = AGENT_PROFILES_ORDERED[idx]
        except Exception:
            await q.answer("探员索引无效", show_alert=True)
            return True
        cases = await db.get_cases_for_agent(prof.name_en, limit=30)
        lines = [
            f"👤 <b>{prof.name_en}</b>",
            f"职位: {prof.position_en}",
            f"部门: {prof.department_en} · <code>{prof.department_code}</code>",
            f"探员编号: <code>{prof.agent_id}</code>",
            f"驻地: {prof.office_en}",
            f"负责阶段: P{prof.stage_from}–P{prof.stage_to}",
            "━━━━━━━━━━━━━━━━━━",
            "案件列表（按最近联络排序）:",
            "",
        ]
        rows = []
        if not cases:
            lines.append("暂无分配案件。")
        else:
            for c in cases[:20]:
                case_no = c.get("case_no") or c.get("case_number") or "N/A"
                unread = int(c.get("unread_count") or 0)
                prefix = f"🔔{unread} " if unread > 0 else ""
                rows.append([InlineKeyboardButton(
                    f"{prefix}{case_no}",
                    callback_data=f"adm|agents|case|{idx}|{case_no}",
                )])
        rows.append([InlineKeyboardButton("⬅️ 返回团队", callback_data="adm|agents|team")])
        await _edit_or_send(
            q,
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return True

    if data.startswith("adm|agents|case|"):
        parts = data.split("|", 4)
        if len(parts) < 5:
            await q.answer("参数错误", show_alert=True)
            return True
        idx = int(parts[3])
        case_no = parts[4]
        c = await db.get_case_by_no(case_no)
        if not c:
            await q.answer("案件不存在", show_alert=True)
            return True
        await db.mark_agent_inbox_read(case_no, str(update.effective_user.id))
        logs = await db.get_liaison_messages(case_no, limit=6)
        user_id = c.get("tg_user_id") or c.get("user_id") or "N/A"
        username = c.get("tg_username") or "—"
        lines = [
            f"📋 <b>案件资料</b> <code>{case_no}</code>",
            "━━━━━━━━━━━━━━━━━━",
            f"👤 用户UID: <code>{user_id}</code>",
            f"👤 用户名: @{username}" if username != "—" else "👤 用户名: —",
            f"📌 状态: {c.get('status') or 'N/A'}",
            f"🏛 平台: {c.get('platform') or '—'}",
            f"💰 金额: {c.get('amount') or '—'} {c.get('coin') or ''}".strip(),
            f"📞 联系: {c.get('contact') or '—'}",
            "",
            "🧾 最近联络记录:",
        ]
        if not logs:
            lines.append("暂无聊天记录。")
        else:
            for m in reversed(logs):
                who = m.get("sender_type", "SYSTEM")
                txt = (m.get("message_text") or "").replace("\n", " ").strip()
                if len(txt) > 80:
                    txt = txt[:80] + "..."
                lines.append(f"• [{who}] {txt or '(empty)'}")
        await _edit_or_send(
            q,
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 回复用户", callback_data=f"agentmsg|{case_no}")],
                [InlineKeyboardButton("🔔 发送状态通知", callback_data=f"notify|{case_no}")],
                [InlineKeyboardButton("⬅️ 返回探员案件", callback_data=f"adm|agents|team|{idx}")],
            ]),
        )
        return True

    if data == "adm|agents|assign_menu" or data == "adm|agents|reassign":
        await _edit_or_send(
            q,
            "👮 派遣探员\n━━━━━━━━━━━━━━━━━━\n\n请先进入「案件管理」→「查看案件」选择案件，在案件详情页点击「派遣探员」。",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("查看案件", callback_data="adm|cases|view")],
                [InlineKeyboardButton(BTN_BACK, callback_data="adm|agents|menu")],
            ]),
        )
        return True

    return False
