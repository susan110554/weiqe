"""
管理后台 — 主菜单与各主按钮入口
从 admin_console 拆分的独立模块，仅做代码搬移，无逻辑修改。
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from .config import is_admin
from .i18n_admin import (
    MAIN_MENU_TITLE,
    BTN_USERS, BTN_CASES, BTN_MSG, BTN_AGENTS, BTN_SECURITY, BTN_PDF, BTN_NOTIFY, BTN_DASHBOARD,
    BTN_BACK,
    ACCESS_DENIED,
)


async def _edit_or_send(q, text: str, **kwargs):
    try:
        await q.message.edit_text(text, **kwargs)
    except Exception as e:
        if "There is no text in the message to edit" in str(e):
            await q.message.reply_text(text, **kwargs)
            return
        raise


def kb_main_menu() -> InlineKeyboardMarkup:
    """主菜单：主功能按钮"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_USERS, callback_data="adm|users|menu")],
        [InlineKeyboardButton(BTN_CASES, callback_data="adm|cases|menu")],
        [InlineKeyboardButton(BTN_MSG, callback_data="adm|msg|menu")],
        [InlineKeyboardButton(BTN_AGENTS, callback_data="adm|agents|menu")],
        [InlineKeyboardButton(BTN_SECURITY, callback_data="adm|security|menu")],
        [InlineKeyboardButton(BTN_PDF, callback_data="adm|pdf|menu")],
        [InlineKeyboardButton(BTN_NOTIFY, callback_data="adm|notify|menu")],
        [InlineKeyboardButton(BTN_DASHBOARD, callback_data="adm|dashboard|menu")],
        [InlineKeyboardButton("💰 收费管理", callback_data="adm|fees|menu")],
        [InlineKeyboardButton("🧰 运营闭环", callback_data="adm|ops|menu")],
    ])


def _placeholder_menu(module: str, title: str) -> tuple[str, InlineKeyboardMarkup]:
    """占位菜单：该模块即将开放"""
    return (
        f"{title}\n━━━━━━━━━━━━━━━━━━\n\n该模块即将开放。",
        InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|main")]]),
    )


async def handle(data: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """处理 adm|main 及占位模块（security、pdf、notify、dashboard）"""
    q = update.callback_query
    if data == "adm|main":
        await _edit_or_send(
            q,
            MAIN_MENU_TITLE,
            parse_mode="HTML",
            reply_markup=kb_main_menu(),
        )
        return True
    return False


async def cmd_console(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """管理后台入口 /console"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(ACCESS_DENIED)
        return
    await update.message.reply_text(
        MAIN_MENU_TITLE,
        parse_mode="HTML",
        reply_markup=kb_main_menu(),
    )
