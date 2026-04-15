"""
管理后台 — 安全与 PIN
功能：重置PIN码、解锁账户、登录记录、黑名单管理（关联 blacklist 表）、管理员2FA
黑名单：软删除 + banned_by 审计，每次操作写入 audit_logs
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import database as db
from .i18n_admin import BTN_BACK


SECURITY_MENU_TITLE = (
    "🔐 安全与PIN\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "请选择操作："
)
BTN_RESET_PIN = "🔑 重置PIN码"
BTN_UNLOCK_ACCOUNT = "🔓 解锁账户"
BTN_LOGIN_RECORDS = "📋 登录记录"
BTN_BLACKLIST = "🚫 黑名单管理"
BTN_ADMIN_2FA = "🛡️ 管理员2FA"


def kb_security_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_RESET_PIN,      callback_data="adm|security|reset_pin")],
        [InlineKeyboardButton(BTN_UNLOCK_ACCOUNT, callback_data="adm|security|unlock")],
        [InlineKeyboardButton(BTN_LOGIN_RECORDS,  callback_data="adm|security|login_records")],
        [InlineKeyboardButton(BTN_BLACKLIST,       callback_data="adm|security|blacklist")],
        [InlineKeyboardButton(BTN_ADMIN_2FA,       callback_data="adm|security|admin_2fa")],
        [InlineKeyboardButton(BTN_BACK,            callback_data="adm|main")],
    ])


def kb_blacklist_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ 封禁用户",   callback_data="adm|security|bl_add")],
        [InlineKeyboardButton("➖ 解除封禁",   callback_data="adm|security|bl_remove")],
        [InlineKeyboardButton("📋 黑名单列表", callback_data="adm|security|bl_list")],
        [InlineKeyboardButton(BTN_BACK,        callback_data="adm|security|menu")],
    ])


async def handle(data: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """处理 adm|security|* 回调"""
    if not data.startswith("adm|security|"):
        return False
    q = update.callback_query
    actor = str(update.effective_user.id)

    if data == "adm|security|menu":
        await q.message.edit_text(
            SECURITY_MENU_TITLE, parse_mode="HTML", reply_markup=kb_security_menu(),
        )
        return True

    if data == "adm|security|reset_pin":
        ctx.user_data["state"] = "ADM_SECURITY_RESET_PIN_UID"
        await q.message.edit_text(
            "🔑 <b>重置PIN码</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            "请输入要重置 PIN 的 Telegram User ID（数字）：",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|security|menu")]]),
        )
        return True

    if data == "adm|security|unlock":
        ctx.user_data["state"] = "ADM_SECURITY_UNLOCK_UID"
        await q.message.edit_text(
            "🔓 <b>解锁账户</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            "请输入要解锁的 Telegram User ID（数字）：",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|security|menu")]]),
        )
        return True

    if data == "adm|security|login_records":
        logs = await db.get_audit_logs(limit=30)
        lines = ["📋 <b>登录记录</b>\n━━━━━━━━━━━━━━━━━━\n"]
        login_actions = {"LOGIN", "PIN_VERIFY", "SESSION_START"}
        filtered = [r for r in logs if (r.get("action") or "").upper() in login_actions]
        if not filtered:
            filtered = logs[:15]
        for r in filtered[:15]:
            ts = r.get("logged_at", "")
            if hasattr(ts, "strftime"):
                ts = ts.strftime("%Y-%m-%d %H:%M")
            lines.append(f"• {ts} | {r.get('actor_id','—')} | {r.get('action','—')}")
        if len(lines) == 2:
            lines.append("暂无登录记录。")
        await q.message.edit_text(
            "\n".join(lines), parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|security|menu")]]),
        )
        return True

    # ── 黑名单入口 ─────────────────────────────────────────────────────────
    if data == "adm|security|blacklist":
        await q.message.edit_text(
            "🚫 <b>黑名单管理</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            "封禁用户将无法发送任何消息或触发任何回调。\n"
            "所有操作均记录在审计日志中（含操作管理员 ID）。",
            parse_mode="HTML",
            reply_markup=kb_blacklist_menu(),
        )
        return True

    # ── 封禁：输入 UID ─────────────────────────────────────────────────────
    if data == "adm|security|bl_add":
        ctx.user_data["state"] = "ADM_BL_ADD_UID"
        await q.message.edit_text(
            "🚫 <b>封禁用户</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            "请输入要封禁的 Telegram User ID（数字）：",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|security|blacklist")]]),
        )
        return True

    # ── 解封：输入 UID ─────────────────────────────────────────────────────
    if data == "adm|security|bl_remove":
        ctx.user_data["state"] = "ADM_BL_REMOVE_UID"
        await q.message.edit_text(
            "➖ <b>解除封禁</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            "请输入要解封的 Telegram User ID（数字）：",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|security|blacklist")]]),
        )
        return True

    # ── 黑名单列表 ─────────────────────────────────────────────────────────
    if data == "adm|security|bl_list":
        rows = await db.blacklist_list(limit=25)
        lines = ["🚫 <b>黑名单列表</b>\n━━━━━━━━━━━━━━━━━━\n"]
        if not rows:
            lines.append("黑名单为空。")
        else:
            for r in rows:
                ts = r.get("banned_at")
                if hasattr(ts, "strftime"):
                    ts = ts.strftime("%Y-%m-%d %H:%M")
                status = "🔴 封禁中" if r.get("is_active") else "🟢 已解封"
                lines.append(
                    f"{status} | UID: <code>{r['tg_user_id']}</code> | "
                    f"封禁者: {r.get('banned_by','—')} | {ts}\n"
                    f"  原因: {r.get('reason','—')}"
                )
        await q.message.edit_text(
            "\n".join(lines), parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|security|blacklist")]]),
        )
        return True

    if data == "adm|security|admin_2fa":
        await q.message.edit_text(
            "🛡️ <b>管理员2FA</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            "管理员双因素认证设置。\n\n该功能即将开放。",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|security|menu")]]),
        )
        return True

    return False


async def handle_text(text: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE, actor: str) -> bool:
    """处理黑名单流程文本输入。返回 True 表示已消耗。"""
    state = ctx.user_data.get("state", "")

    if state == "ADM_BL_ADD_UID":
        try:
            uid = int(text.strip())
        except ValueError:
            await update.message.reply_text("❌ 请输入纯数字的 Telegram User ID：")
            return True
        ctx.user_data["bl_pending_uid"] = uid
        ctx.user_data["state"] = "ADM_BL_ADD_REASON"
        await update.message.reply_text(
            f"用户 ID：<code>{uid}</code>\n\n请输入封禁原因（可留空直接回车）：",
            parse_mode="HTML",
        )
        return True

    if state == "ADM_BL_ADD_REASON":
        uid = ctx.user_data.pop("bl_pending_uid", None)
        ctx.user_data.pop("state", None)
        if not uid:
            return True
        reason = text.strip() or "管理员封禁"
        ok = await db.blacklist_add(uid, reason, actor)
        if ok:
            await update.message.reply_text(
                f"✅ 用户 <code>{uid}</code> 已封禁。\n原因：{reason}\n操作者：{actor}",
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text(f"❌ 封禁失败（可能已在黑名单中）：UID {uid}")
        return True

    if state == "ADM_BL_REMOVE_UID":
        ctx.user_data.pop("state", None)
        try:
            uid = int(text.strip())
        except ValueError:
            await update.message.reply_text("❌ 请输入纯数字的 Telegram User ID：")
            return True
        ok = await db.blacklist_remove(uid, actor)
        if ok:
            await update.message.reply_text(
                f"✅ 用户 <code>{uid}</code> 已解封。操作者：{actor}",
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text(f"❌ 解封失败（用户不在黑名单或已解封）：UID {uid}")
        return True

    return False
