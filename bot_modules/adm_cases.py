"""
管理后台 — 案件管理
从 admin_console 拆分的独立模块，仅做代码搬移，无逻辑修改。
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import database as db
from .i18n_admin import (
    BTN_BACK,
    CASES_MENU_TITLE,
    BTN_VIEW_CASES, BTN_SEARCH_CASE, BTN_CHANGE_STATUS, BTN_ASSIGN_AGENT,
    BTN_GEN_REPORT, BTN_CLOSE_CASE,
    BTN_ALL_CASES, BTN_PENDING, BTN_IN_PROGRESS, BTN_CLOSED,
    STATUS_P0, STATUS_P1, STATUS_P2, STATUS_P3, STATUS_P4, STATUS_P5, STATUS_P6,
    STATUS_P7, STATUS_P8, STATUS_CLOSED, STATUS_CUSTOM,
    CASES_LIST_HEADER, CASE_ITEM, NO_CASES, PAGE_FMT,
    CASE_DETAIL_HEADER, CASE_DETAIL_FIELDS,
    STATUS_CUSTOM_PROMPT,
)

PAGE_SIZE = 8
STATUS_ICONS = {
    "SUBMITTED": "⚪",
    "PENDING REVIEW": "🟡",
    "CASE ACCEPTED": "🔵",
    "REFERRED TO LAW ENFORCEMENT": "🟢",
    "IDENTITY VERIFICATION": "⚫",
    "PRELIMINARY REVIEW": "🟠",
    "ASSET TRACING": "🔴",
    "LEGAL DOCUMENTATION": "🟣",
    "Pending Initial Review": "🟡", "待初步审核": "🟡",
}


def kb_cases_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_VIEW_CASES, callback_data="adm|cases|view")],
        [InlineKeyboardButton(BTN_SEARCH_CASE, callback_data="adm|cases|search")],
        [InlineKeyboardButton(BTN_CHANGE_STATUS, callback_data="adm|cases|status_menu")],
        [InlineKeyboardButton(BTN_ASSIGN_AGENT, callback_data="adm|cases|assign_menu")],
        [InlineKeyboardButton(BTN_GEN_REPORT, callback_data="adm|cases|report")],
        [InlineKeyboardButton(BTN_CLOSE_CASE, callback_data="adm|cases|close")],
        [InlineKeyboardButton(BTN_BACK, callback_data="adm|main")],
    ])


def kb_cases_filter() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_ALL_CASES, callback_data="adm|cases|list|all|0")],
        [
            InlineKeyboardButton(BTN_PENDING, callback_data="adm|cases|list|待审核|0"),
            InlineKeyboardButton(BTN_IN_PROGRESS, callback_data="adm|cases|list|进行中|0"),
        ],
        [InlineKeyboardButton(BTN_CLOSED, callback_data="adm|cases|list|已关闭|0")],
        [InlineKeyboardButton(BTN_BACK, callback_data="adm|cases|menu")],
    ])


def kb_cases_list_nav(filter_key: str, page: int, total_pages: int) -> list:
    row = []
    if page > 0:
        row.append(InlineKeyboardButton("◀️ 上一页", callback_data=f"adm|cases|list|{filter_key}|{page-1}"))
    if page < total_pages - 1:
        row.append(InlineKeyboardButton("下一页 ▶️", callback_data=f"adm|cases|list|{filter_key}|{page+1}"))
    if not row:
        return []
    return [row]


def kb_case_actions(case_no: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟡 P2审核", callback_data=f"st|{case_no}|PENDING REVIEW"),
            InlineKeyboardButton("🔵 P3受理", callback_data=f"st|{case_no}|CASE ACCEPTED"),
        ],
        [
            InlineKeyboardButton("🟢 P4转交", callback_data=f"st|{case_no}|REFERRED TO LAW ENFORCEMENT"),
            InlineKeyboardButton("⚫ P5验证", callback_data=f"st|{case_no}|IDENTITY VERIFICATION"),
        ],
        [
            InlineKeyboardButton("🟠 P6初审", callback_data=f"st|{case_no}|PRELIMINARY REVIEW"),
            InlineKeyboardButton("🔴 P7溯源", callback_data=f"st|{case_no}|ASSET TRACING"),
        ],
        [InlineKeyboardButton("🟣 P8法务", callback_data=f"st|{case_no}|LEGAL DOCUMENTATION")],
        [
            InlineKeyboardButton("📤 推送当前状态", callback_data=f"notify|{case_no}"),
            InlineKeyboardButton("🔑 P9费用配置", callback_data=f"adm|cmp|p9|{case_no}"),
        ],
        [InlineKeyboardButton("👤 派遣探员", callback_data=f"assign|{case_no}")],
        [
            InlineKeyboardButton("💬 联络通道", callback_data=f"liaison_open|{case_no}"),
            InlineKeyboardButton("📨 发消息", callback_data=f"agentmsg|{case_no}"),
        ],
        [InlineKeyboardButton("📁 证据文件", callback_data=f"evlist|{case_no}")],
        [InlineKeyboardButton("📊 生成报告", callback_data=f"adm|cases|report|{case_no}")],
        [InlineKeyboardButton(BTN_BACK, callback_data="adm|cases|menu")],
    ])


def kb_status_options(case_no: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(STATUS_P0, callback_data=f"st|{case_no}|SUBMITTED")],
        [InlineKeyboardButton(STATUS_P1, callback_data=f"st|{case_no}|PENDING REVIEW")],
        [InlineKeyboardButton(STATUS_P2, callback_data=f"st|{case_no}|CASE ACCEPTED")],
        [InlineKeyboardButton(STATUS_P3, callback_data=f"st|{case_no}|REFERRED TO LAW ENFORCEMENT")],
        [InlineKeyboardButton(STATUS_P4, callback_data=f"st|{case_no}|IDENTITY VERIFICATION")],
        [InlineKeyboardButton(STATUS_P5, callback_data=f"st|{case_no}|PRELIMINARY REVIEW")],
        [InlineKeyboardButton(STATUS_P6, callback_data=f"st|{case_no}|ASSET TRACING")],
        [InlineKeyboardButton(STATUS_P7, callback_data=f"st|{case_no}|LEGAL DOCUMENTATION")],
        [InlineKeyboardButton(STATUS_P8, callback_data=f"st|{case_no}|FUND DISBURSEMENT")],
        [InlineKeyboardButton(STATUS_CLOSED, callback_data=f"st|{case_no}|CASE CLOSED")],
        [InlineKeyboardButton(STATUS_CUSTOM, callback_data=f"adm|cases|status_custom|{case_no}")],
        [InlineKeyboardButton(BTN_BACK, callback_data=f"adm|cases|detail|{case_no}")],
    ])


def kb_back_to_cases() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_BACK, callback_data="adm|cases|menu")],
    ])


async def handle(data: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """处理 adm|cases|* 回调"""
    q = update.callback_query
    if data == "adm|cases|menu":
        await q.message.edit_text(
            CASES_MENU_TITLE,
            parse_mode="HTML",
            reply_markup=kb_cases_menu(),
        )
        return True

    if data == "adm|cases|view":
        await q.message.edit_text(
            "📋 查看案件\n━━━━━━━━━━━━━━━━━━\n\n请选择筛选条件：",
            parse_mode="HTML",
            reply_markup=kb_cases_filter(),
        )
        return True

    if data.startswith("adm|cases|list|"):
        _, _, _, filter_key, page_str = data.split("|", 4)
        page = int(page_str)
        filter_val = None if filter_key == "all" else filter_key
        total = await db.get_case_count_by_status(filter_val)
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))
        offset = page * PAGE_SIZE
        cases = await db.get_cases_paginated(PAGE_SIZE, offset, filter_val)

        lines = [CASES_LIST_HEADER]
        for c in cases:
            icon = STATUS_ICONS.get(c.get("status", ""), "⚪")
            lines.append(CASE_ITEM.format(
                icon=icon,
                case_no=c.get("display_case_no") or c.get("case_no", "?"),
                platform=c.get("platform", "—"),
                amount=c.get("amount") or "—",
                coin=c.get("coin") or "",
                status=c.get("status", "—"),
            ))
        if not cases:
            lines.append(NO_CASES)
        lines.append(PAGE_FMT.format(page=page + 1, total_pages=total_pages))

        btns = []
        for c in cases:
            cn = c.get("display_case_no") or c.get("case_no", "")
            btns.append([InlineKeyboardButton(f"{STATUS_ICONS.get(c.get('status',''),'⚪')} {cn}", callback_data=f"adm|cases|detail|{cn}")])
        nav = kb_cases_list_nav(filter_key, page, total_pages)
        for r in nav:
            btns.append(r)
        btns.append([InlineKeyboardButton(BTN_BACK, callback_data="adm|cases|view")])
        await q.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(btns),
        )
        return True

    if data.startswith("adm|cases|detail|"):
        case_no = data.split("|", 3)[3]
        c = await db.get_case_by_no(case_no)
        if not c:
            await q.message.edit_text("❌ 案件不存在。", parse_mode="HTML", reply_markup=kb_back_to_cases())
            return True
        created = c.get("created_at")
        updated = c.get("updated_at") or created
        created_str = created.strftime("%Y-%m-%d %H:%M") if created else "—"
        updated_str = updated.strftime("%Y-%m-%d %H:%M") if updated else "—"
        body = CASE_DETAIL_HEADER + CASE_DETAIL_FIELDS.format(
            case_no=c.get("case_no", "—"),
            status=c.get("status", "—"),
            created_at=created_str,
            updated_at=updated_str,
            platform=c.get("platform", "—"),
            amount=c.get("amount", "—"),
            coin=c.get("coin", ""),
            incident_time=c.get("incident_time", "—"),
            wallet_addr=(c.get("wallet_addr") or "—")[:30] + "..." if (c.get("wallet_addr") or "") and len(c.get("wallet_addr", "")) > 30 else (c.get("wallet_addr") or "—"),
            chain_type=c.get("chain_type", "—"),
            contact=c.get("contact", "—"),
            tg_user_id=c.get("tg_user_id", "—"),
        )
        await q.message.edit_text(body, parse_mode="HTML", reply_markup=kb_case_actions(case_no))
        return True

    if data == "adm|cases|status_menu":
        await q.message.edit_text(
            "📋 修改状态\n━━━━━━━━━━━━━━━━━━\n\n请先进入「查看案件」选择要修改的案件。",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("查看案件", callback_data="adm|cases|view")],
                [InlineKeyboardButton(BTN_BACK, callback_data="adm|cases|menu")],
            ]),
        )
        return True

    if data.startswith("adm|cases|status_custom|"):
        case_no = data.split("|", 3)[3]
        ctx.user_data["state"] = "ADM_STATUS_CUSTOM"
        ctx.user_data["adm_status_case"] = case_no
        await q.message.edit_text(
            STATUS_CUSTOM_PROMPT.format(case_no=case_no),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data=f"adm|cases|detail|{case_no}")]]),
        )
        return True

    if data == "adm|cases|assign_menu":
        await q.message.edit_text(
            "👤 派遣探员\n━━━━━━━━━━━━━━━━━━\n\n请先进入「查看案件」选择案件，在案件详情页点击「派遣探员」。",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("查看案件", callback_data="adm|cases|view")],
                [InlineKeyboardButton(BTN_BACK, callback_data="adm|cases|menu")],
            ]),
        )
        return True

    if data.startswith("adm|cases|report"):
        # adm|cases|report or adm|cases|report|{case_no}
        parts_r = data.split("|", 4)
        cn_r = parts_r[3] if len(parts_r) > 3 else None
        if cn_r:
            c = await db.get_case_by_no(cn_r)
            if not c:
                await q.message.edit_text("❌ 案件不存在。", parse_mode="HTML", reply_markup=kb_back_to_cases())
                return True
            created = c.get("created_at")
            updated = c.get("updated_at") or created
            created_str = created.strftime("%Y-%m-%d %H:%M") if created else "—"
            updated_str = updated.strftime("%Y-%m-%d %H:%M") if updated else "—"
            report = (
                "📊 <b>案件报告</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"案件编号: <code>{c.get('case_no','—')}</code>\n"
                f"当前状态: <b>{c.get('status','—')}</b>\n"
                f"提交时间: {created_str}\n"
                f"最后更新: {updated_str}\n"
                f"平台: {c.get('platform','—')}\n"
                f"金额: {c.get('amount','—')} {c.get('coin','')}\n"
                f"钱包: {(c.get('wallet_addr') or '—')[:40]}\n"
                f"链: {c.get('chain_type','—')}\n"
                f"探员: {c.get('agent_code') or '未分配'}\n"
            )
            await q.message.edit_text(
                report,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(BTN_BACK, callback_data=f"adm|cases|detail|{cn_r}")],
                ]),
            )
        else:
            await q.message.edit_text(
                "📊 生成报告\n━━━━━━━━━━━━━━━━━━\n\n请先进入「查看案件」选择案件，在案件详情页点击「生成报告」。",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("查看案件", callback_data="adm|cases|view")],
                    [InlineKeyboardButton(BTN_BACK, callback_data="adm|cases|menu")],
                ]),
            )
        return True

    if data == "adm|cases|close":
        await q.message.edit_text(
            "🔒 关闭案件\n━━━━━━━━━━━━━━━━━━\n\n请先进入「查看案件」选择案件，在案件详情页设置状态为 CASE CLOSED。",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("查看案件", callback_data="adm|cases|view")],
                [InlineKeyboardButton(BTN_BACK, callback_data="adm|cases|menu")],
            ]),
        )
        return True

    if data == "adm|cases|search":
        ctx.user_data["state"] = "ADM_CASE_SEARCH"
        await q.message.edit_text(
            "📋 搜索案件\n━━━━━━━━━━━━━━━━━━\n\n请输入 Case ID（如 IC3-2026-REF-1234-XXX）：",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|cases|menu")]]),
        )
        return True

    return False
