"""
管理后台 — 用户管理
从 admin_console 拆分的独立模块，仅做代码搬移，无逻辑修改。
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import database as db
from .i18n_admin import (
    BTN_BACK,
    USERS_MENU_TITLE,
    BTN_VIEW_USERS, BTN_SEARCH_USER, BTN_SUSPEND_USER, BTN_RESUME_USER, BTN_ACTIVITY_LOG,
    USERS_LIST_HEADER, USER_ITEM, NO_USERS,
    BTN_ALL_USERS, BTN_ACTIVE_USERS, BTN_SUSPENDED_USERS,
    USER_SUSPEND_PROMPT, USER_RESUME_PROMPT,
    USER_SEARCH_PROMPT,
)
from .i18n_user import USER_SUSPENDED_NOTIFY, USER_RESUMED_NOTIFY

PAGE_SIZE = 8
BTN_RESET_PIN = "🔑 重置PIN码"


def _placeholder_menu(module: str, title: str) -> tuple[str, InlineKeyboardMarkup]:
    return (
        f"{title}\n━━━━━━━━━━━━━━━━━━\n\n该模块即将开放。",
        InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|main")]]),
    )


def kb_users_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_VIEW_USERS, callback_data="adm|users|view")],
        [InlineKeyboardButton(BTN_SEARCH_USER, callback_data="adm|users|search")],
        [InlineKeyboardButton(BTN_SUSPEND_USER, callback_data="adm|users|suspend")],
        [InlineKeyboardButton(BTN_RESUME_USER, callback_data="adm|users|resume")],
        [InlineKeyboardButton(BTN_ACTIVITY_LOG, callback_data="adm|users|activity")],
        [InlineKeyboardButton(BTN_BACK, callback_data="adm|main")],
    ])


def kb_users_filter() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_ALL_USERS, callback_data="adm|users|list|all|0")],
        [
            InlineKeyboardButton(BTN_ACTIVE_USERS, callback_data="adm|users|list|active|0"),
            InlineKeyboardButton(BTN_SUSPENDED_USERS, callback_data="adm|users|list|suspended|0"),
        ],
        [InlineKeyboardButton(BTN_BACK, callback_data="adm|users|menu")],
    ])


def kb_users_list_nav(filter_key: str, page: int, total_pages: int) -> list:
    row = []
    if page > 0:
        row.append(InlineKeyboardButton("◀️ 上一页", callback_data=f"adm|users|list|{filter_key}|{page-1}"))
    if page < total_pages - 1:
        row.append(InlineKeyboardButton("下一页 ▶️", callback_data=f"adm|users|list|{filter_key}|{page+1}"))
    return [row] if row else []


async def handle(data: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """处理 adm|users|* 回调"""
    q = update.callback_query
    if data == "adm|users|menu":
        await q.message.edit_text(USERS_MENU_TITLE, parse_mode="HTML", reply_markup=kb_users_menu())
        return True

    if data == "adm|users|view":
        await q.message.edit_text(
            "👥 查看用户\n━━━━━━━━━━━━━━━━━━\n\n请选择筛选条件：",
            parse_mode="HTML",
            reply_markup=kb_users_filter(),
        )
        return True

    if data.startswith("adm|users|list|"):
        parts = data.split("|")
        filter_key = parts[3] if len(parts) > 3 else "all"
        page = int(parts[4]) if len(parts) > 4 else 0
        status_filter = None if filter_key == "all" else filter_key
        await db.sync_users_from_cases()
        total = await db.get_user_count(status_filter)
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))
        offset = page * PAGE_SIZE
        users = await db.get_users_paginated(PAGE_SIZE, offset, status_filter)
        lines = [USERS_LIST_HEADER]
        for u in users:
            icon = "🔴" if (u.get("status") == "suspended" or u.get("suspended_until")) else "🟢"
            lines.append(USER_ITEM.format(
                icon=icon,
                tg_user_id=u.get("tg_user_id", "?"),
                username=u.get("username") or "—",
                status=u.get("status") or "active",
            ))
        if not users:
            lines.append(NO_USERS)
        from .i18n_admin import PAGE_FMT
        lines.append(PAGE_FMT.format(page=page + 1, total_pages=total_pages))
        btns = []
        for u in users:
            uid = u.get("tg_user_id", "")
            uname = (u.get("username") or "—")[:15]
            btns.append([InlineKeyboardButton(
                f"{'🔴' if u.get('status')=='suspended' else '🟢'} {uid} @{uname}",
                callback_data=f"adm|users|detail|{uid}",
            )])
        for r in kb_users_list_nav(filter_key, page, total_pages):
            btns.append(r)
        btns.append([InlineKeyboardButton(BTN_BACK, callback_data="adm|users|view")])
        await q.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))
        return True

    if data.startswith("adm|users|detail|"):
        uid = data.split("|", 3)[3]
        u = await db.get_user_by_tg_id(int(uid)) or await db.get_user_from_cases(int(uid))
        if not u:
            await q.message.edit_text("❌ 用户不存在。", parse_mode="HTML", reply_markup=kb_users_menu())
            return True
        status = u.get("status") or "active"
        suspended = u.get("suspended_until")
        body = (
            f"👤 用户详情\n━━━━━━━━━━━━━━━━━━\n\n"
            f"🆔 TG ID: <code>{u.get('tg_user_id','—')}</code>\n"
            f"📛 用户名: @{u.get('username') or '—'}\n"
            f"📌 状态: {status}\n"
            f"⏸ 暂停至: {suspended or '—'}\n"
        )
        btns = [
            [InlineKeyboardButton(BTN_SUSPEND_USER, callback_data=f"adm|users|suspend|{uid}")],
            [InlineKeyboardButton(BTN_RESUME_USER, callback_data=f"adm|users|resume|{uid}")],
            [InlineKeyboardButton(BTN_RESET_PIN, callback_data=f"adm|users|reset_pin|{uid}")],
            [InlineKeyboardButton(BTN_BACK, callback_data="adm|users|menu")],
        ]
        await q.message.edit_text(body, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))
        return True

    if data == "adm|users|search":
        ctx.user_data["state"] = "ADM_USER_SEARCH"
        ctx.user_data.pop("adm_user_uid", None)
        await q.message.edit_text(
            USER_SEARCH_PROMPT,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|users|menu")]]),
        )
        return True

    if data == "adm|users|suspend":
        ctx.user_data["state"] = "ADM_USER_SUSPEND"
        ctx.user_data.pop("adm_user_uid", None)
        await q.message.edit_text(
            USER_SUSPEND_PROMPT,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|users|menu")]]),
        )
        return True

    if data.startswith("adm|users|suspend|"):
        uid_str = data.split("|", 3)[3]
        try:
            uid = int(uid_str)
            from datetime import datetime, timedelta
            await db.suspend_user(uid, "管理员操作", datetime.utcnow() + timedelta(days=30), str(update.effective_user.id))
            try:
                await ctx.bot.send_message(uid, USER_SUSPENDED_NOTIFY, parse_mode="HTML")
            except Exception:
                pass
            await q.message.edit_text(f"✅ 用户 {uid} 已暂停。", parse_mode="HTML", reply_markup=kb_users_menu())
        except Exception as e:
            await q.message.edit_text(f"❌ 操作失败: {e}", parse_mode="HTML", reply_markup=kb_users_menu())
        return True

    if data == "adm|users|resume":
        ctx.user_data["state"] = "ADM_USER_RESUME"
        ctx.user_data.pop("adm_user_uid", None)
        await q.message.edit_text(
            USER_RESUME_PROMPT,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|users|menu")]]),
        )
        return True

    if data.startswith("adm|users|resume|"):
        uid_str = data.split("|", 3)[3]
        try:
            uid = int(uid_str)
            await db.resume_user(uid, str(update.effective_user.id))
            try:
                await ctx.bot.send_message(uid, USER_RESUMED_NOTIFY, parse_mode="HTML")
            except Exception:
                pass
            await q.message.edit_text(f"✅ 用户 {uid} 已恢复。", parse_mode="HTML", reply_markup=kb_users_menu())
        except Exception as e:
            await q.message.edit_text(f"❌ 操作失败: {e}", parse_mode="HTML", reply_markup=kb_users_menu())
        return True

    if data == "adm|users|activity":
        txt, kb = _placeholder_menu("users", "📋 活动日志")
        await q.message.edit_text(txt, parse_mode="HTML", reply_markup=kb)
        return True

    if data.startswith("adm|users|reset_pin|"):
        uid_str = data.split("|", 3)[3]
        await q.message.edit_text(
            f"🔑 <b>重置PIN码</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            f"确认重置用户 <code>{uid_str}</code> 的账户PIN码？\n\n"
            f"此操作将清除该用户的现有PIN，用户下次登录时须重新设置。",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ 确认重置", callback_data=f"adm|users|reset_pin_confirm|{uid_str}")],
                [InlineKeyboardButton(BTN_BACK, callback_data=f"adm|users|detail|{uid_str}")],
            ]),
        )
        return True

    if data.startswith("adm|users|reset_pin_confirm|"):
        uid_str = data.split("|", 3)[3]
        try:
            uid = int(uid_str)
            ok = await db.reset_user_pin(uid, str(update.effective_user.id))
            if ok:
                await q.message.edit_text(
                    f"✅ 用户 <code>{uid}</code> 的PIN码已重置。",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|users|menu")]]),
                )
            else:
                await q.message.edit_text(
                    f"⚠️ 用户 <code>{uid}</code> 未设置PIN码，无需重置。",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|users|menu")]]),
                )
        except Exception as e:
            await q.message.edit_text(
                f"❌ 操作失败: {e}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|users|menu")]]),
            )
        return True

    return False
