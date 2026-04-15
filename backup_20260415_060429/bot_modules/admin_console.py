"""
Telegram 中文管理后台 — 主菜单、子菜单、回调分发
管理端全部中文，用户端通知仅英文（见 i18n_user）
代码已拆分为独立模块：adm_main_menu, adm_users, adm_cases, adm_msg, adm_agents, adm_pdf
"""
from telegram import Update
from telegram.ext import ContextTypes

from .config import is_admin
from .i18n_admin import ACCESS_DENIED

# 子模块
from . import adm_main_menu
from . import adm_ops
from . import adm_security
from . import adm_notifications
from . import adm_fees
from . import adm_dashboard
from . import adm_users
from . import adm_cases
from . import adm_msg
from . import adm_agents
from . import adm_pdf


async def handle_callback(data: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """处理 adm| 开头的回调，返回 True 表示已处理。"""
    q = update.callback_query
    if not is_admin(update.effective_user.id):
        await q.answer(ACCESS_DENIED, show_alert=True)
        return True

    parts = data.split("|")
    if parts[0] != "adm":
        return False

    try:
        await q.answer()
    except Exception:
        pass

    if len(parts) >= 3 and parts[1] == "cmp":
        from . import adm_cmp_pipeline
        if await adm_cmp_pipeline.handle(data, update, ctx):
            return True

    # 按顺序委托给各子模块（security/notify/dashboard 在 main 之前，覆盖占位）
    if await adm_security.handle(data, update, ctx):
        return True
    if await adm_notifications.handle(data, update, ctx):
        return True
    if await adm_fees.handle(data, update, ctx):
        return True
    if await adm_dashboard.handle(data, update, ctx):
        return True
    if await adm_ops.handle(data, update, ctx):
        return True
    if await adm_main_menu.handle(data, update, ctx):
        return True
    if await adm_pdf.handle(data, update, ctx):
        return True
    if await adm_msg.handle(data, update, ctx):
        return True
    if await adm_users.handle(data, update, ctx):
        return True
    if await adm_cases.handle(data, update, ctx):
        return True
    if await adm_agents.handle(data, update, ctx):
        return True

    return False


# 从子模块导出，供 bot.py 使用
from .adm_main_menu import cmd_console
from .adm_cases import kb_case_actions, kb_back_to_cases
