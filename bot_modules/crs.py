"""
FBI IC3 – ADRI Bot
CRS Module: Complaint Reporting System (CRS-01 to CRS-04)
"""
import hashlib
import re
from html import unescape as _html_unescape
from typing import List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .config import (
    AUTH_ID, VALID_PERIOD, logger,
    S_FULLNAME, S_ADDRESS, S_PHONE, S_EMAIL, S_DOB,
    S_TXID, S_ASSET, S_VICTIM_WALLET, S_SUSPECT_WALLET,
    S_PLATFORM, S_SCAMMER_ID, S_TIME, S_WALLET,
)
from .keyboards import (
    kb_crs_nav, kb_m01, kb_crs_attest, kb_crs01_menu, kb_crs03_menu, kb_phone, kb_crs03_crime,
)

# 地址验证后 callback_data，供 bot 注册回调
ADDR_CONFIRM = "ADDR_CONFIRM"
ADDR_EDIT = "ADDR_EDIT"
ADDR_USE_SUGGESTED = "ADDR_USE_SUGGESTED"
ADDR_KEEP_MINE = "ADDR_KEEP_MINE"
ADDR_REENTER = "ADDR_REENTER"
ADDR_SKIP_VERIFY = "ADDR_SKIP_VERIFY"

# 姓名验证失败后 callback_data
NAME_REENTER = "NAME_REENTER"
NAME_BACK = "NAME_BACK"

MAIN_SEP = "━━━━━━━━━━━━━━━━━━"
FEDERAL_INDEX_VERSION = "3.4.0"
FEDERAL_INDEX_LINE = f"FEDERAL INDEX VER. {FEDERAL_INDEX_VERSION}"


def _crs_reporting_title(section: int = 0) -> str:
    """主行：主菜单为 Case Reporting System (CRS)；分节为 CRS-1 … CRS-4。"""
    suf = str(section) if section else ""
    if not suf:
        return "Case Reporting System (CRS)"
    return f"Case Reporting System (CRS-{suf})"


def _module_session_hash(module_id: str) -> str:
    h = hashlib.sha256((module_id or "").encode()).hexdigest()[:8]
    return f"{h[:4]}...{h[4:]}"


# ── 抬头格式规范（锁定，请勿随意改动）────────────────────────────────────
# CRS 主菜单: crs_header_select(0) →
#   IC3 | Internet Crime Complaint Center
#   Case Reporting System (CRS)
#   MAIN_SEP
#   FEDERAL INDEX VER. 3.4.0
#   MAIN_SEP
#   Select a function to continue.
#
# CRS-02B 入口: 固定格式 →
#   IC3 | Internet Crime Complaint Center
#   ⛓️ SECTION CRS-02B
#   CRYPTOCURRENCY TRANSACTION
#   MAIN_SEP
#   FEDERAL INDEX VER. x.x.x (M02B)
#   MAIN_SEP
#
# CRS-03 入口: 固定格式 →
#   IC3 | Internet Crime Complaint Center
#   📱 SECTION CRS-03
#   SUBJECT IDENTIFICATION
#   MAIN_SEP
#   Processed under 18 U.S.C. § 1343.
#   MAIN_SEP
#
# 其他 CRS 子页若需统一抬头，请沿用上述结构，勿删改第一行、MAIN_SEP、法律声明等。
# ─────────────────────────────────────────────────────────────────────


def _tx_no(ctx) -> int:
    """Current transaction number (1-based)."""
    return ctx.user_data.get("current_tx_num", 1)


def _tx_snapshot(ctx):
    """Save all tx1_* working keys into tx_data[current_tx_num]."""
    n = _tx_no(ctx)
    ctx.user_data.setdefault("tx_data", {})[n] = {
        k: v for k, v in ctx.user_data.items() if k.startswith("tx1_")
    }


def _tx_restore(ctx, n: int):
    """Load tx_data[n] back into tx1_* working keys and set current_tx_num."""
    # Clear existing tx1_* keys
    for k in [k for k in list(ctx.user_data.keys()) if k.startswith("tx1_")]:
        del ctx.user_data[k]
    # Restore saved data for transaction n
    saved = ctx.user_data.get("tx_data", {}).get(n, {})
    ctx.user_data.update(saved)
    ctx.user_data["current_tx_num"] = n
    # Also clear accordion/expanded state when switching
    ctx.user_data.pop("wire_s5_expanded", None)
    ctx.user_data.pop("other_s6_expanded", None)


def module_header(_module_id: str, title_line: str, prompt_line: str) -> str:
    """八个主模块通用标题：含 FEDERAL INDEX VER.。_module_id：M01…M09（路由占位）。"""
    return (
        "IC3 | Internet Crime Complaint Center\n"
        f"{title_line}\n"
        f"{MAIN_SEP}\n"
        f"{FEDERAL_INDEX_LINE}\n"
        f"{MAIN_SEP}\n"
        f"{prompt_line}\n\n"
    )


def _section_to_num(section) -> int:
    """CRS-01→1, CRS-02/02A/02B→2, CRS-03→3, CRS-04→4, 其他→0"""
    if not section:
        return 0
    s = str(section).strip().upper()
    if s == "CRS-01":
        return 1
    if s in ("CRS-02", "CRS-02A", "CRS-02B"):
        return 2
    if s == "CRS-03":
        return 3
    if s == "CRS-04":
        return 4
    return 0


def crs_header(section: int = 0) -> str:
    """section: 0=主菜单, 1–4=CRS1–CRS4"""
    return (
        "IC3 | Internet Crime Complaint Center\n"
        f"{_crs_reporting_title(section)}\n"
        f"{MAIN_SEP}\n\n"
    )


def crs_header_select(section: int = 0) -> str:
    """section: 0=主菜单, 1–4=CRS1–CRS4；含 FEDERAL INDEX VER.。"""
    return (
        "IC3 | Internet Crime Complaint Center\n"
        f"{_crs_reporting_title(section)}\n"
        f"{MAIN_SEP}\n"
        f"{FEDERAL_INDEX_LINE}\n"
        f"{MAIN_SEP}\n"
        "Select a function to continue.\n\n"
    )


# 兼容旧导入
CRS_HEADER = crs_header(0)
CRS_HEADER_SELECT = crs_header_select(0)


def _crs_footer(sig_hash: str) -> str:
    """页脚：认证与哈希信息。"""
    return f"\n\nAuth ID: <code>{AUTH_ID}</code> | Hash: <code>{sig_hash}</code>"


FEDERAL_NOTICE = (
    "<b>FEDERAL NOTICE</b>\n"
    " ━━━━━━━━━━━━━━━━━━━\n\n"
    "This interface is part of the\n"
    "<b>IC3 Authorized Digital Reporting\n"
    "Interface (ADRI)</b>. Information\n"
    "collected here will be used for\n"
    "official law enforcement\n"
    "investigations.\n\n"
    "<b>Privacy Act of 1974:</b>\n"
    "Providing this information is\n"
    "voluntary, but necessary for case\n"
    "processing.\n\n"
    f"Auth ID: <code>{AUTH_ID}</code>\n"
    f"Valid: {VALID_PERIOD}"
)


# ─── CRS01: Complainant Information ─────────────────────

CRS01_INTRO_TEMPLATE = (
    "IC3 | Internet Crime Complaint Center\n"
    "COMPLAINANT INFORMATION — CRS-01\n"
    f"{MAIN_SEP}\n\n"
    "All listed fields are required unless marked optional.\n"
    "Enter each item as it appears on your government-issued identification\n"
    "or other official documentation.\n\n"
    "Processed under 28 C.F.R. § 16.\n"
    f"{MAIN_SEP}\n\n"
    "<i>Select a field below to continue.</i>"
)


# ─── Physical Address 提交后：LocationIQ 验证流程 ─────────────────────
# API Key 从 .env 读取 LOCATIONIQ_API_KEY


def _kb_address_confirm_edit() -> InlineKeyboardMarkup:
    """✅ 完全匹配：确认或编辑"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm Address", callback_data=ADDR_CONFIRM)],
        [InlineKeyboardButton("✏️ Edit Address", callback_data=ADDR_EDIT)],
    ])


def _kb_address_use_suggested_keep() -> InlineKeyboardMarkup:
    """⚠️ 部分匹配：使用建议或保留原输入"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Use Suggested Address", callback_data=ADDR_USE_SUGGESTED)],
        [InlineKeyboardButton("✏️ Keep My Address", callback_data=ADDR_KEEP_MINE)],
    ])


def _kb_address_reenter_skip() -> InlineKeyboardMarkup:
    """❌ 无法识别：重新输入或跳过验证"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Re-enter Address", callback_data=ADDR_REENTER)],
        [InlineKeyboardButton("⏭️ Skip Verification", callback_data=ADDR_SKIP_VERIFY)],
    ])


def _format_address_display(display_name: str) -> str:
    """将 display_name 按逗号/换行整理为多行显示"""
    if not display_name:
        return ""
    parts = [p.strip() for p in display_name.split(",") if p.strip()]
    return "\n    ".join(parts) if parts else display_name


async def crs01_address_validate_and_respond(target, ctx, address_text: str):
    """
    用户提交 Physical Address 后调用：使用 LocationIQ check_address() 验证，
    根据结果展示 ✅完全匹配 / ⚠️部分匹配 / ❌无法识别 的文案与按钮。

    集成说明：bot 需在 state==S_ADDRESS 且用户发送文本时，改为调用
    await crs01_address_validate_and_respond(update.message, ctx, text.strip())；
    并处理 callback_data: ADDR_CONFIRM, ADDR_EDIT, ADDR_USE_SUGGESTED,
    ADDR_KEEP_MINE, ADDR_REENTER, ADDR_SKIP_VERIFY（可调用 crs01_handle_address_callback）。
    """
    from validation.val_address import check_address

    addr = (address_text or "").strip()
    if len(addr) < 3:
        await target.reply_text(
            "Please enter a valid address (at least 3 characters).",
            parse_mode="HTML",
            reply_markup=kb_crs_nav(),
        )
        return

    ctx.user_data["address"] = addr
    result = await check_address(addr)

    # ✅ 完全匹配
    if result.valid and not result.suggestions:
        display = _format_address_display(result.value or addr)
        await target.reply_text(
            "✅ <b>Address verified:</b>\n\n    " + (display or addr),
            parse_mode="HTML",
            reply_markup=_kb_address_confirm_edit(),
        )
        ctx.user_data["address_verified"] = result.value
        ctx.user_data["state"] = None
        return

    # ⚠️ 部分匹配（城市+邮编已与校验逻辑一致，直接展示建议）
    if result.valid and result.suggestions:
        suggested = result.suggestions[0] if result.suggestions else result.value
        if suggested:
            display = _format_address_display(suggested)
            ctx.user_data["address_suggested"] = suggested
            ctx.user_data["address_verified"] = None
            ctx.user_data["state"] = None
            await target.reply_text(
                "⚠️ <b>Did you mean?</b>\n\n    " + (display or suggested),
                parse_mode="HTML",
                reply_markup=_kb_address_use_suggested_keep(),
            )
            return

    # ❌ 无法识别：保持 S_ADDRESS，使用户停留在此界面直到点击 Re-enter 或 Skip，不会因发文字就回到主菜单
    ctx.user_data["address_verified"] = None
    ctx.user_data["address_suggested"] = None
    ctx.user_data["state"] = S_ADDRESS
    await target.reply_text(
        "❌ <b>Address not found.</b>\n\n"
        "Please check and re-enter your address.",
        parse_mode="HTML",
        reply_markup=_kb_address_reenter_skip(),
    )


async def crs01_handle_address_callback(target, ctx, data: str):
    """
    处理地址验证后的按钮回调。data 为 ADDR_CONFIRM / ADDR_EDIT / ADDR_USE_SUGGESTED /
    ADDR_KEEP_MINE / ADDR_REENTER / ADDR_SKIP_VERIFY。
    """
    if data == ADDR_CONFIRM:
        verified = ctx.user_data.get("address_verified")
        if verified:
            ctx.user_data["address"] = verified
        ctx.user_data.pop("address_verified", None)
        ctx.user_data.pop("address_suggested", None)
        addr = ctx.user_data.get("address", "")
        await target.reply_text(
            "<b>Recorded — physical address</b>\n\n" + addr,
            parse_mode="HTML",
        )
        await crs01_phone(target, ctx)
        return
    if data == ADDR_EDIT:
        ctx.user_data["state"] = S_ADDRESS
        await crs01_address(target, ctx)
        return
    if data == ADDR_USE_SUGGESTED:
        suggested = ctx.user_data.get("address_suggested")
        if suggested:
            ctx.user_data["address"] = suggested
        ctx.user_data.pop("address_verified", None)
        ctx.user_data.pop("address_suggested", None)
        addr = ctx.user_data.get("address", "")
        await target.reply_text(
            "<b>Recorded — physical address</b>\n\n" + addr,
            parse_mode="HTML",
        )
        await crs01_phone(target, ctx)
        return
    if data == ADDR_KEEP_MINE:
        ctx.user_data.pop("address_verified", None)
        ctx.user_data.pop("address_suggested", None)
        addr = ctx.user_data.get("address", "")
        await target.reply_text(
            "<b>Recorded — physical address</b>\n\n" + addr,
            parse_mode="HTML",
        )
        await crs01_phone(target, ctx)
        return
    if data == ADDR_REENTER:
        ctx.user_data["state"] = S_ADDRESS
        await crs01_address(target, ctx)
        return
    if data == ADDR_SKIP_VERIFY:
        ctx.user_data.pop("address_verified", None)
        ctx.user_data.pop("address_suggested", None)
        addr = ctx.user_data.get("address", "")
        await target.reply_text(
            "<b>Recorded — physical address</b>\n\n" + addr,
            parse_mode="HTML",
        )
        await crs01_phone(target, ctx)
        return


# ─── Full Legal Name 提交后：check_name() 验证流程 ─────────────────────


async def crs01_name_validate_and_respond(target, ctx, name_text: str):
    """
    用户提交 Full Legal Name 后调用：使用 val_profile.check_name() 验证，
    通过则显示 ✅ Full Legal Name recorded. + 姓名；失败则显示错误文案与 [Re-enter Name] [Back]。

    集成说明：bot 需在 state==S_FULLNAME 且用户发送文本时，改为调用
    await crs01_name_validate_and_respond(update.message, ctx, text.strip())；
    并处理 callback_data: NAME_REENTER, NAME_BACK（可调用 crs01_handle_name_callback）。
    """
    from validation.val_profile import check_name

    name = (name_text or "").strip()
    if not name:
        ctx.user_data["state"] = S_FULLNAME
        from validation.val_profile import MSG_NAME_INVALID_EN
        await target.reply_text(
            MSG_NAME_INVALID_EN,
            parse_mode="HTML",
            reply_markup=kb_crs_nav(show_back=False),
        )
        return

    result = check_name(name)

    if result.valid:
        ctx.user_data["fullname"] = result.value or name
        ctx.user_data["state"] = None
        await target.reply_text(
            "<b>Recorded — full legal name</b>\n\n"
            f"{result.value or name}",
            parse_mode="HTML",
        )
        await crs01_dob(target, ctx)
        return

    # ❌ 验证失败：保持输入状态，可直接重试；✖️ Cancel 见 kb_crs_nav
    ctx.user_data["state"] = S_FULLNAME
    await target.reply_text(
        result.msg_en,
        parse_mode="HTML",
        reply_markup=kb_crs_nav(show_back=False),
    )


async def crs01_handle_name_callback(target, ctx, data: str):
    """处理姓名验证失败后的按钮回调。data 为 NAME_REENTER 或 NAME_BACK。"""
    if data == NAME_REENTER:
        ctx.user_data["state"] = S_FULLNAME
        await crs01_name(target, ctx)
        return
    if data == NAME_BACK:
        await crs01_intro(target, ctx)
        return


async def crs01_intro(target, ctx):
    """CRS01 入口：展示 4 个子按钮菜单（CRS01-A/B/C/D）。"""
    ctx.user_data["state"] = None
    await target.reply_text(
        CRS01_INTRO_TEMPLATE,
        parse_mode="HTML",
        reply_markup=kb_crs01_menu(ctx.user_data),
    )


async def crs01_name(target, ctx):
    ctx.user_data["state"] = S_FULLNAME
    await target.reply_text(
        "Complainant Information\n"
        "<b>Step 1 – Full Legal Name</b>\n"
        f"{MAIN_SEP}\n\n"
        "Enter your full legal name exactly as it appears\n"
        "on your government-issued identification.\n\n"
        "Example: <code>John Michael Smith</code>",
        parse_mode="HTML", reply_markup=kb_crs_nav(show_back=False),
    )


async def crs01_dob(target, ctx):
    ctx.user_data["state"] = S_DOB
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ Skip", callback_data="CRS01_AGE_SKIP"),
        InlineKeyboardButton("↩️ Back", callback_data="CRS01_AGE_BACK"),
    ]])
    await target.reply_text(
        "Complainant Information\n"
        "<b>Step 2 – Age</b>\n"
        f"{MAIN_SEP}\n\n"
        "Enter your age or age range.\n\n"
        "Accepted formats:\n"
        "<code>45</code>\n"
        "<code>45-50</code>\n"
        "<code>Unknown</code>\n\n"
        f"{MAIN_SEP}",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def crs01_address(target, ctx):
    ctx.user_data["state"] = S_ADDRESS
    await target.reply_text(
        "Complainant Information\n"
        "<b>Step 3 – Physical Address</b>\n"
        f"{MAIN_SEP}\n\n"
        "Enter your complete mailing address, including postal or ZIP code.\n\n"
        "Example: <code>123 Main St, Miami, FL 33101</code>",
        parse_mode="HTML", reply_markup=kb_crs_nav(),
    )


async def crs01_phone(target, ctx):
    """CRS01-C 联系方式：直接输入电话号码或用户名。"""
    ctx.user_data["state"] = S_PHONE
    ctx.user_data["phone_platform"] = "Phone"
    await target.reply_text(
        "Complainant Information\n"
        "<b>Step 4 – Contact Number</b>\n"
        f"{MAIN_SEP}\n\n"
        "Enter a telephone number or platform identifier for contact.\n\n"
        "Telephone: <code>+1-305-555-0100</code>\n"
        "Username: <code>@username</code>\n\n"
        "Example: <code>+1-305-555-0100</code>",
        parse_mode="HTML",
        reply_markup=kb_crs_nav(),
    )


async def crs01_phone_input(target, ctx, platform: str):
    """CRS01-C 联系方式：输入指定平台的号码/ID 或邮箱。"""
    ctx.user_data["state"] = S_PHONE
    ctx.user_data["phone_platform"] = platform
    if platform == "Email":
        await target.reply_text(
            "Complainant Information\n"
            "<b>Step 4 – Email Address (Required)</b>\n"
            f"{MAIN_SEP}\n\n"
            "Enter your email address.\n\n"
            "Example: <code>john.smith@email.com</code>",
            parse_mode="HTML",
            reply_markup=kb_crs_nav(),
        )
    else:
        await target.reply_text(
            "Complainant Information\n"
            f"<b>Step 4 – {platform} Contact</b>\n"
            f"{MAIN_SEP}\n\n"
            f"Enter your {platform} number or identifier.\n\n"
            "Telephone: <code>+1-305-555-0100</code>\n"
            "Username: <code>@username</code>",
            parse_mode="HTML",
            reply_markup=kb_crs_nav(),
        )


async def crs01_email(target, ctx):
    ctx.user_data["state"] = S_EMAIL
    await target.reply_text(
        "Complainant Information\n"
        "<b>Step 5 – Email Address</b>\n"
        f"{MAIN_SEP}\n\n"
        "Enter the email address for official case correspondence.\n\n"
        "Example: <code>john.smith@email.com</code>",
        parse_mode="HTML", reply_markup=kb_crs_nav(),
    )


# ─── CRS-02: Financial Transaction(s) ─────────────────────

async def crs02_financial_entry(target, ctx):
    """
    CRS-02-1: Financial Transaction(s) — Step 1
    问题：Did you send or lose money in the incident?
    """
    ctx.user_data["section"] = "CRS-02"
    ctx.user_data["state"] = None
    text = (
        "IC3 | Internet Crime Complaint Center\n"
        "Financial Transaction(s) CRS-02-1\n"
        f"{MAIN_SEP}\n"
        "*Did you send or lose money in the incident?*\n"
        f"{MAIN_SEP}"
    )
    from .keyboards import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes", callback_data="CRS02_FIN_YES"),
            InlineKeyboardButton("❌ No",  callback_data="CRS02_FIN_NO"),
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="CRS01_BACK")],
    ])
    await target.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def crs02_financial_amount_prompt(target, ctx):
    """
    CRS-02-2: Step 2 — Total Loss Amount
    仅输入总损失金额（单位 USD，文本提示中说明）。
    """
    ctx.user_data["state"] = "CRS02_FIN_AMOUNT"
    text = (
        "IC3 | Internet Crime Complaint Center\n"
        "Financial Transaction(s) CRS-02-01\n"
        f"{MAIN_SEP}\n"
        "Step 2: Total Loss Amount\n"
        f"{MAIN_SEP}\n\n"
        "Please enter your exact total loss amount.\n"
        "All amounts will be treated as US Dollars (USD).\n\n"
        "Example: <code>2500.00</code>\n"
        "If unsure, enter your best estimate."
    )
    await target.reply_text(text, parse_mode="HTML", reply_markup=kb_crs_nav())


async def crs02_financial_transactions_menu(target, ctx):
    """CRS-02-3: Step 3 — Transaction overview."""
    ctx.user_data["state"] = None
    from .keyboards import InlineKeyboardMarkup, InlineKeyboardButton

    d = ctx.user_data
    tx_count = d.get("tx_count", 1)
    tx_done  = d.get("tx_done", {})

    text = (
        "IC3 | Internet Crime Complaint Center\n"
        "Financial Transaction(s) CRS-02-02\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    if d.get("crs02_has_money") is not False:
        tl = d.get("crs02_total_loss")
        if not tl and not d.get("tx_data") and d.get("amount"):
            tl = d.get("amount")
        if tl:
            text += f"<b>Total Loss Amount:</b> <code>{tl} USD</code>\n"
        else:
            text += "<b>Total Loss Amount:</b> <code>—</code>\n"
        text += f"{MAIN_SEP}\n"
    text += (
        "Specify amounts in USD\n"
        "Originating = funds sent from (your account)\n"
        "Recipient = funds sent to (subject's account)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )

    # Build transaction buttons in rows of 2
    tx_buttons = []
    for n in range(1, tx_count + 1):
        label = f"✅ Transaction #{n}" if tx_done.get(n) else f"Transaction #{n}"
        tx_buttons.append(InlineKeyboardButton(label, callback_data=f"CRS02_FIN_TX|{n}"))

    rows = []
    for i in range(0, len(tx_buttons), 2):
        rows.append(tx_buttons[i:i+2])

    if tx_count < 10:
        rows.append([InlineKeyboardButton("➕ Add Transaction", callback_data="CRS02_FIN_ADD")])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="CRS-02-TYPE")])
    rows.append([InlineKeyboardButton("✅ Confirm", callback_data="M01")])

    await target.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))


async def crs02_financial_tx1_type(target, ctx):
    """
    CRS-02#1: Transaction #1 Step 1 — select transaction type.
    """
    ctx.user_data["state"] = None
    text = (
        "IC3 | Internet Crime Complaint Center\n"
        "Financial Transaction(s) CRS-02#1\n"
        f"Transaction #{_tx_no(ctx)} Step 1\n"
        f"{MAIN_SEP}\n"
        f"Select the transaction type for Transaction #{_tx_no(ctx)}:"
    )
    from .keyboards import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Cash",                       callback_data="CRS02_FIN_TX1_TYPE|CASH"),
            InlineKeyboardButton("Check/Cashier's Check",      callback_data="CRS02_FIN_TX1_TYPE|CHECK"),
        ],
        [
            InlineKeyboardButton("Money Order",                callback_data="CRS02_FIN_TX1_TYPE|MONEY_ORDER"),
            InlineKeyboardButton("Cryptocurrency/Crypto ATM",  callback_data="CRS02_FIN_TX1_TYPE|CRYPTO"),
        ],
        [
            InlineKeyboardButton("Wire Transfer",              callback_data="CRS02_FIN_TX1_TYPE|WIRE"),
            InlineKeyboardButton("Other",                      callback_data="CRS02_FIN_TX1_TYPE|OTHER"),
        ],
        [
            InlineKeyboardButton("⬅️ Back",   callback_data="CRS02_FIN_BACK"),
            InlineKeyboardButton("✖️ Cancel", callback_data="CRS02_FIN_CANCEL"),
        ],
    ])
    await target.reply_text(text, parse_mode="HTML", reply_markup=kb)


# ─── CRS-02#1 通用前三步（所有 Transaction #1 类型共用）────────────────────
TX1_S1_YES = "TX1_S1_YES"
TX1_S1_NO = "TX1_S1_NO"

# Cash flow callbacks
CASH_S4_YES = "CASH_S4_YES"
CASH_S4_NO = "CASH_S4_NO"
CASH_S5_ADDR1 = "CASH_S5_ADDR1"
CASH_S5_ADDR2 = "CASH_S5_ADDR2"
CASH_S5_SUITE = "CASH_S5_SUITE"
CASH_S5_CITY = "CASH_S5_CITY"
CASH_S5_COUNTRY = "CASH_S5_COUNTRY"
CASH_S5_STATE = "CASH_S5_STATE"
CASH_S5_ZIP = "CASH_S5_ZIP"
CASH_S5_SAVE = "CASH_S5_SAVE"
CASH_S5_BACK = "CASH_S5_BACK"
CASH_S6_EDIT = "CASH_S6_EDIT"
CASH_S6_SAVE = "CASH_S6_SAVE"

# Check/Cashier's Check flow callbacks
CHECK_S4_YES = "CHECK_S4_YES"
CHECK_S4_NO = "CHECK_S4_NO"
CHECK_S5_OBANK = "CHECK_S5_OBANK"
CHECK_S5_OCITY = "CHECK_S5_OCITY"
CHECK_S5_OCOUNTRY = "CHECK_S5_OCOUNTRY"
CHECK_S5_ONAME = "CHECK_S5_ONAME"
CHECK_S5_OACCT = "CHECK_S5_OACCT"
CHECK_S5_RBANK = "CHECK_S5_RBANK"
CHECK_S5_RCITY = "CHECK_S5_RCITY"
CHECK_S5_RCOUNTRY = "CHECK_S5_RCOUNTRY"
CHECK_S5_RNAME = "CHECK_S5_RNAME"
CHECK_S5_RACCT = "CHECK_S5_RACCT"
CHECK_S5_RROUTING = "CHECK_S5_RROUTING"
CHECK_S5_RSWIFT = "CHECK_S5_RSWIFT"
CHECK_S5_SAVE         = "CHECK_S5_SAVE"
CHECK_S5_BACK         = "CHECK_S5_BACK"
CHECK_S5_TOGGLE_ORIG  = "CHECK_S5_TOGGLE_ORIG"
CHECK_S5_TOGGLE_RECIP = "CHECK_S5_TOGGLE_RECIP"
CHECK_S6_EDIT = "CHECK_S6_EDIT"
CHECK_S6_SAVE = "CHECK_S6_SAVE"

# Money Order flow callbacks
MO_S4_YES = "MO_S4_YES"
MO_S4_NO = "MO_S4_NO"
MO_S5_OBANK = "MO_S5_OBANK"
MO_S5_OADDR = "MO_S5_OADDR"
MO_S5_OCITY = "MO_S5_OCITY"
MO_S5_OCOUNTRY = "MO_S5_OCOUNTRY"
MO_S5_OSTATE = "MO_S5_OSTATE"
MO_S5_ONAME = "MO_S5_ONAME"
MO_S5_OACCT = "MO_S5_OACCT"
MO_S5_RBANK = "MO_S5_RBANK"
MO_S5_RADDR = "MO_S5_RADDR"
MO_S5_RCITY = "MO_S5_RCITY"
MO_S5_RCOUNTRY = "MO_S5_RCOUNTRY"
MO_S5_RSTATE = "MO_S5_RSTATE"
MO_S5_RNAME = "MO_S5_RNAME"
MO_S5_RACCT = "MO_S5_RACCT"
MO_S5_RROUTING = "MO_S5_RROUTING"
MO_S5_RSWIFT = "MO_S5_RSWIFT"
MO_S5_SAVE = "MO_S5_SAVE"
MO_S5_BACK = "MO_S5_BACK"
MO_S5_TOGGLE_ORIG  = "MO_S5_TOGGLE_ORIG"
MO_S5_TOGGLE_RECIP = "MO_S5_TOGGLE_RECIP"
MO_S6_EDIT = "MO_S6_EDIT"
MO_S6_SAVE = "MO_S6_SAVE"


def _tx1_label(tx1_type: str) -> str:
    m = {
        "CASH": "Cash",
        "CHECK": "Check/Cashier's Check",
        "MONEY_ORDER": "Money Order",
        "CRYPTO": "Cryptocurrency/Crypto ATM",
        "WIRE": "Wire Transfer",
        "CARD": "Debit Card/Credit Card",
        "P2P": "Peer-to-peer Transfer",
        "OTHER": "Other",
    }
    return m.get((tx1_type or "").upper(), tx1_type or "Transaction")


def _tx_data_review_view(d: dict) -> dict:
    """合并 tx_data 快照与当前正在编辑的 tx1_*，供 Review 展示（不修改 user_data）。"""
    out = {}
    for k, v in (d.get("tx_data") or {}).items():
        try:
            nk = int(k)
        except (TypeError, ValueError):
            continue
        if isinstance(v, dict):
            out[nk] = dict(v)
    n_cur = int(d.get("current_tx_num") or 1)
    cur = {kk: vv for kk, vv in d.items() if kk.startswith("tx1_")}
    if cur:
        prev = out.get(n_cur, {})
        out[n_cur] = {**prev, **cur}
    return out


def _tx_snapshot_nonempty(tx: dict) -> bool:
    if not tx:
        return False
    for v in tx.values():
        if v is None:
            continue
        s = str(v).strip()
        if s and s != "—":
            return True
    return False


def _format_tx_review_block(n: int, tx: dict, h) -> str:
    """单笔交易在 Review 中的 HTML 块（完整 TXID/钱包，不截断；无装饰性 emoji）。"""
    if not _tx_snapshot_nonempty(tx):
        return f"<b>Transaction #{n}</b>\n<i>No data recorded.</i>\n\n"
    ttype = (tx.get("tx1_type") or "").upper()
    label = _tx1_label(tx.get("tx1_type") or "")

    def _line(lab: str, val) -> str | None:
        if val is None:
            return None
        if isinstance(val, bool):
            return f"{lab}: <code>{'Yes' if val else 'No'}</code>"
        s = str(val).strip()
        if not s or s == "—":
            return None
        return f"{lab}: <code>{h(s)}</code>"

    if ttype == "CRYPTO":
        amt = tx.get("tx1_amount") or tx.get("tx1_crypto_amount") or "—"
        dt = tx.get("tx1_date") or tx.get("tx1_crypto_date") or "—"
        cur = tx.get("tx1_crypto_currency") or "—"
        th = tx.get("tx1_crypto_txhash") or "—"
        ow = tx.get("tx1_crypto_orig_wallet") or "—"
        rw = tx.get("tx1_crypto_recip_wallet") or "—"
        lines = [f"<b>Transaction #{n}</b> — {h(label)}"]
        for extra in (
            _line("Money Sent/Lost", tx.get("tx1_sent_lost")),
            _line("Bank Contacted", tx.get("tx1_crypto_bank_contacted")),
        ):
            if extra:
                lines.append(extra)
        lines.extend([
            f"Amount (USD): <code>{h(str(amt))}</code>",
            f"Incident Date: <code>{h(str(dt))}</code>",
            f"Asset Type: <code>{h(str(cur))}</code>",
            f"TXID / Hash: <code>{h(str(th))}</code>",
            f"Victim (Originating) Wallet: <code>{h(str(ow))}</code>",
            f"Suspect (Recipient) Wallet: <code>{h(str(rw))}</code>",
        ])
        for lab, key in [
            ("ATM/Kiosk Name", "tx1_crypto_atm_name"),
            ("ATM/Kiosk Address", "tx1_crypto_atm_address"),
            ("ATM/Kiosk City", "tx1_crypto_atm_city"),
            ("ATM/Kiosk Country", "tx1_crypto_atm_country"),
            ("ATM/Kiosk State", "tx1_crypto_atm_state"),
            ("ATM/Kiosk Zip", "tx1_crypto_atm_zip"),
        ]:
            ln = _line(lab, tx.get(key))
            if ln:
                lines.append(ln)
        return "\n".join(lines) + "\n\n"

    amt = tx.get("tx1_amount") or "—"
    dt = tx.get("tx1_date") or "—"
    lines = [
        f"<b>Transaction #{n}</b> — {h(label)}",
    ]
    y_sl = _line("Money Sent/Lost", tx.get("tx1_sent_lost"))
    if y_sl:
        lines.append(y_sl)
    if ttype == "OTHER" and _review_field_filled(tx.get("tx1_amount")):
        cur = (tx.get("tx1_currency") or "USD").strip()
        lines.append(f"Amount: <code>{h(str(tx.get('tx1_amount')))} {h(cur)}</code>")
    else:
        lines.append(f"Amount (USD): <code>{h(str(amt))}</code>")
    lines.append(f"Date: <code>{h(str(dt))}</code>")

    if ttype == "CASH":
        yb = _line("Bank Contacted", tx.get("tx1_cash_bank_contacted"))
        if yb:
            lines.append(yb)
        for lab, key in [
            ("Recipient Address", "tx1_cash_recipient_addr1"),
            ("Recipient Address (cont.)", "tx1_cash_recipient_addr2"),
            ("Suite/Mail Stop", "tx1_cash_recipient_suite"),
            ("City", "tx1_cash_recipient_city"),
            ("Country", "tx1_cash_recipient_country"),
            ("State", "tx1_cash_recipient_state"),
            ("Zip/Route", "tx1_cash_recipient_zip"),
        ]:
            ln = _line(lab, tx.get(key))
            if ln:
                lines.append(ln)
    elif ttype == "CHECK":
        yb = _line("Bank Contacted", tx.get("tx1_check_bank_contacted"))
        if yb:
            lines.append(yb)
        for lab, key in [
            ("Originating Bank Name", "tx1_check_orig_bank_name"),
            ("Originating Bank City", "tx1_check_orig_bank_city"),
            ("Originating Bank Country", "tx1_check_orig_bank_country"),
            ("Originating Name on Account", "tx1_check_orig_name_on_acct"),
            ("Originating Account Number", "tx1_check_orig_account_no"),
            ("Recipient Bank Name", "tx1_check_recip_bank_name"),
            ("Recipient Bank City", "tx1_check_recip_bank_city"),
            ("Recipient Bank Country", "tx1_check_recip_bank_country"),
            ("Recipient Name on Account", "tx1_check_recip_name_on_acct"),
            ("Recipient Account Number", "tx1_check_recip_account_no"),
            ("Recipient Routing Number", "tx1_check_recip_routing_no"),
            ("Recipient SWIFT Code", "tx1_check_recip_swift"),
        ]:
            ln = _line(lab, tx.get(key))
            if ln:
                lines.append(ln)
    elif ttype == "MONEY_ORDER":
        yb = _line("Bank Contacted", tx.get("tx1_mo_bank_contacted"))
        if yb:
            lines.append(yb)
        for lab, key in [
            ("Originating Bank Name", "tx1_mo_orig_bank_name"),
            ("Originating Bank Address", "tx1_mo_orig_bank_address"),
            ("Originating Bank City", "tx1_mo_orig_bank_city"),
            ("Originating Bank Country", "tx1_mo_orig_bank_country"),
            ("Originating Bank State", "tx1_mo_orig_bank_state"),
            ("Originating Name on Account", "tx1_mo_orig_name_on_acct"),
            ("Originating Account Number", "tx1_mo_orig_account_no"),
            ("Recipient Bank Name", "tx1_mo_recip_bank_name"),
            ("Recipient Bank Address", "tx1_mo_recip_bank_address"),
            ("Recipient Bank City", "tx1_mo_recip_bank_city"),
            ("Recipient Bank Country", "tx1_mo_recip_bank_country"),
            ("Recipient Bank State", "tx1_mo_recip_bank_state"),
            ("Recipient Name on Account", "tx1_mo_recip_name_on_acct"),
            ("Recipient Account Number", "tx1_mo_recip_account_no"),
            ("Recipient Routing Number", "tx1_mo_recip_routing_no"),
            ("Recipient SWIFT Code", "tx1_mo_recip_swift"),
        ]:
            ln = _line(lab, tx.get(key))
            if ln:
                lines.append(ln)
    elif ttype == "WIRE":
        yb = _line("Bank Contacted", tx.get("tx1_wire_bank_contacted"))
        if yb:
            lines.append(yb)
        for lab, key in [
            ("Originating Bank Name", "tx1_wire_orig_bank_name"),
            ("Originating Bank Address", "tx1_wire_orig_bank_address"),
            ("Originating Bank City", "tx1_wire_orig_bank_city"),
            ("Originating Bank Country", "tx1_wire_orig_bank_country"),
            ("Originating Bank State", "tx1_wire_orig_bank_state"),
            ("Originating Name on Account", "tx1_wire_orig_name_on_acct"),
            ("Recipient Bank Name", "tx1_wire_recip_bank_name"),
            ("Recipient Bank Address", "tx1_wire_recip_bank_address"),
            ("Recipient Bank City", "tx1_wire_recip_bank_city"),
            ("Recipient Bank Country", "tx1_wire_recip_bank_country"),
            ("Recipient Bank State", "tx1_wire_recip_bank_state"),
            ("Recipient Name on Account", "tx1_wire_recip_name_on_acct"),
            ("Recipient Routing Number", "tx1_wire_recip_routing_no"),
            ("Recipient Account Number", "tx1_wire_recip_account_no"),
            ("Recipient SWIFT Code", "tx1_wire_recip_swift"),
        ]:
            ln = _line(lab, tx.get(key))
            if ln:
                lines.append(ln)
    elif ttype == "OTHER":
        yb = _line("Bank Contacted", tx.get("tx1_other_bank_contacted"))
        if yb:
            lines.append(yb)
        sp = tx.get("tx1_other_specify")
        if _review_field_filled(sp):
            lines.append(f"Specified Type: <code>{h(str(sp))}</code>")
        for lab, key in [
            ("Originating Bank Name", "tx1_other_orig_bank_name"),
            ("Originating Bank Address", "tx1_other_orig_bank_address"),
            ("Originating Bank City", "tx1_other_orig_bank_city"),
            ("Originating Bank Country", "tx1_other_orig_bank_country"),
            ("Originating Bank State", "tx1_other_orig_bank_state"),
            ("Originating Name on Account", "tx1_other_orig_name_on_acct"),
            ("Recipient Bank Name", "tx1_other_recip_bank_name"),
            ("Recipient Bank Address", "tx1_other_recip_bank_address"),
            ("Recipient Bank City", "tx1_other_recip_bank_city"),
            ("Recipient Bank Country", "tx1_other_recip_bank_country"),
            ("Recipient Bank State", "tx1_other_recip_bank_state"),
            ("Recipient Name on Account", "tx1_other_recip_name_on_acct"),
            ("Recipient Routing Number", "tx1_other_recip_routing_no"),
            ("Recipient Account Number", "tx1_other_recip_account_no"),
            ("Recipient SWIFT Code", "tx1_other_recip_swift"),
        ]:
            ln = _line(lab, tx.get(key))
            if ln:
                lines.append(ln)

    return "\n".join(lines) + "\n\n"


def _legacy_flat_m02_block(d: dict, h) -> str:
    """无 tx_data 时的旧版单笔字段展示。"""
    amt_val = d.get("amount") or "—"
    coin_val = d.get("coin") or ""
    amt_raw = str(amt_val).strip()
    coin_raw = str(coin_val).strip()
    if coin_raw and coin_raw.lower() in amt_raw.lower().split():
        amt = h(amt_raw)
    else:
        amt = h(f"{amt_raw} {coin_raw}".strip())
    tm = h(d.get("time") or "—")
    txid = d.get("txid", "Not provided")
    if str(txid).startswith("file:"):
        txid = "📷 Screenshot uploaded"
    txid_h = h(txid)
    vw = h(d.get("victim_wallet", "—"))
    sw = h(d.get("wallet", "—"))
    return (
        "<b>Financial record (summary)</b>\n"
        f"Disputed Assets:   <code>{amt}</code>\n"
        f"Incident Time:     <code>{tm}</code>\n"
        f"TXID:              <code>{txid_h}</code>\n"
        f"Victim Wallet:     <code>{vw}</code>\n"
        f"Suspect Wallet:    <code>{sw}</code>\n\n"
    )


def _total_loss_display(d: dict, h) -> str:
    """Step 2 总损失金额；多笔交易后仍优先 crs02_total_loss。"""
    if d.get("crs02_has_money") is False:
        return "<code>N/A (no funds reported)</code>"
    tl = d.get("crs02_total_loss")
    if not tl and not d.get("tx_data") and d.get("amount"):
        tl = d.get("amount")
    if not tl:
        return "<code>—</code>"
    coin = (d.get("coin") or "USD").strip() or "USD"
    return f"<code>{h(str(tl).strip())} {h(coin)}</code>"


async def crs02_tx1_common_step1(target, ctx):
    """
    Transaction #1 Step 1 (Common) — Was the money sent or lost?
    文案与布局在所有 CRS-02#1 类型下保持一致。
    """
    ctx.user_data["state"] = None
    tx1_type = (ctx.user_data.get("tx1_type") or "").upper()
    label = _tx1_label(tx1_type)
    text = (
        f"Transaction #{_tx_no(ctx)}\n"
        f"{label}\n"
        "Step 1 • Financial Transaction(s)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "* Required field\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Was the money sent or lost? *"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes", callback_data=TX1_S1_YES),
            InlineKeyboardButton("❌ No",  callback_data=TX1_S1_NO),
        ],
    ])
    await target.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def crs02_tx1_common_step2(target, ctx):
    """Transaction #1 *Step 2 • Transaction Amount (Common)"""
    ctx.user_data["state"] = "CRS02_TX1_COMMON_AMOUNT"
    label = _tx1_label((ctx.user_data.get("tx1_type") or "").upper())
    text = (
        f"Transaction #{_tx_no(ctx)}\n"
        f"{label}\n"
        "*Step 2 • Transaction Amount\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "*Transaction Amount:\n\n"
        "Please specify in US Dollars (USD)\n"
        "Please reply with the amount:\n\n"
        "Example: 5000"
    )
    await target.reply_text(text, parse_mode="HTML", reply_markup=kb_crs_nav())


async def crs02_tx1_common_step3(target, ctx):
    """Transaction #1 *Step 3 • Transaction Date (Common)"""
    ctx.user_data["state"] = "CRS02_TX1_COMMON_DATE"
    label = _tx1_label((ctx.user_data.get("tx1_type") or "").upper())
    text = (
        f"Transaction #{_tx_no(ctx)}\n"
        f"{label}\n"
        "*Step 3 • Transaction Date\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "*Transaction Date:\n\n"
        "Please reply with the date:\n\n"
        "Format  : MM/DD/YYYY\n"
        "Example : 3/17/2025"
    )
    await target.reply_text(text, parse_mode="HTML", reply_markup=kb_crs_nav())


async def crs02_tx1_cash_step4(target, ctx):
    """Transaction #1 Cash • Step 4 — bank/exchange contacted"""
    ctx.user_data["state"] = None
    text = (
        f"Transaction #{_tx_no(ctx)}\n"
        "Cash • Step 4\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Did you contact your bank, financial \n"
        "institution, or cryptocurrency exchange?\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes", callback_data=CASH_S4_YES),
            InlineKeyboardButton("❌ No",  callback_data=CASH_S4_NO),
        ],
    ])
    await target.reply_text(text, parse_mode="HTML", reply_markup=kb)


def _is_us_country(val: str) -> bool:
    v = (val or "").strip().lower()
    return v in ("united states", "united states of america", "usa", "u.s.", "u.s.a.", "us")


# ─── Generic sequential field helpers ─────────────────────────────────────
def _seq_field_prompt_text(ctx, seq, field_idx: int, icon: str = "🏦") -> str:
    """Build a sequential field prompt with accumulated ✅ context."""
    d = ctx.user_data
    tx_no = _tx_no(ctx)
    data_key, short_label, field_no, title, body = seq[field_idx]
    context_lines = []
    for i in range(field_idx):
        prev_key, prev_short, _, _, _ = seq[i]
        v = d.get(prev_key)
        if v and str(v).strip():
            context_lines.append(f"✅ {prev_short:<14}: {str(v).strip()}")
    context = "\n".join(context_lines)
    if context:
        context = f"\n{context}\n"
    return (
        f"Transaction #{tx_no}\n"
        f"{field_no} · {title}\n"
        f"{MAIN_SEP}\n"
        f"{icon} {title}{context}\n"
        f"{body}\n"
        f"{MAIN_SEP}"
    )


async def _seq_field_show(target, ctx, seq, states, field_idx: int,
                          skip_cb: str, back_cb: str, icon: str = "🏦"):
    """Show a single sequential field prompt at the given index."""
    if field_idx < 0 or field_idx >= len(seq):
        return
    ctx.user_data["state"] = states[field_idx]
    text = _seq_field_prompt_text(ctx, seq, field_idx, icon)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭ Skip", callback_data=skip_cb),
        InlineKeyboardButton("↩️ Back", callback_data=back_cb),
    ]])
    await target.reply_text(text, parse_mode="HTML", reply_markup=kb)


# ─── Generic edit menu helpers ────────────────────────────────────────────
async def _seq_edit_menu_show(target, ctx, seq, orig_count, type_label, step_label,
                               edit_prefix, toggle_orig_cb, toggle_recip_cb, done_cb,
                               expanded="orig"):
    """Show an edit menu with accordion sections for bank fields."""
    d = ctx.user_data
    ctx.user_data["state"] = None
    tx_no = _tx_no(ctx)
    rows = []

    if orig_count > 0:
        rows.append([
            InlineKeyboardButton(
                f"{'✅' if expanded == 'orig' else '▶'} Originating Bank",
                callback_data=toggle_orig_cb),
            InlineKeyboardButton(
                f"{'✅' if expanded == 'recip' else '▶'} Recipient Bank",
                callback_data=toggle_recip_cb),
        ])
        if expanded == "orig":
            field_range = range(orig_count)
        else:
            field_range = range(orig_count, len(seq))
        for i in field_range:
            data_key, short_label, *_ = seq[i]
            val = d.get(data_key)
            if val and str(val).strip() and str(val).strip() != "Not Provided":
                btn_text = f"✅ {str(val).strip()}"
            else:
                btn_text = short_label
            rows.append([InlineKeyboardButton(btn_text, callback_data=f"{edit_prefix}{i}")])
    else:
        for i in range(len(seq)):
            data_key, short_label, *_ = seq[i]
            val = d.get(data_key)
            if val and str(val).strip() and str(val).strip() != "Not Provided":
                btn_text = f"✅ {str(val).strip()}"
            else:
                btn_text = short_label
            rows.append([InlineKeyboardButton(btn_text, callback_data=f"{edit_prefix}{i}")])

    rows.append([InlineKeyboardButton("✅ Done", callback_data=done_cb)])

    text = (
        f"Transaction #{tx_no}\n"
        f"{type_label}\n"
        f"{step_label} • Add Bank Account\n"
        f"{MAIN_SEP}"
    )
    await target.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))


async def _seq_edit_field_show(target, ctx, seq, states, field_idx, cancel_cb, icon="🏦"):
    """Show a single field prompt in edit mode with a Back button only."""
    if field_idx < 0 or field_idx >= len(seq):
        return
    ctx.user_data["state"] = states[field_idx]
    text = _seq_field_prompt_text(ctx, seq, field_idx, icon)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("↩️ Back", callback_data=cancel_cb),
    ]])
    await target.reply_text(text, parse_mode="HTML", reply_markup=kb)


# ─── Cash Step 5 sequential fields ───────────────────────────────────────
_CASH_S5_SEQ = [
    ("tx1_cash_recipient_addr1",   "Address",   "Field 1", "Recipient Bank Address",
     "Please enter the recipient bank\nstreet address.\n\nExample: 456 Wall Street"),
    ("tx1_cash_recipient_addr2",   "Address 2", "Field 2", "Recipient Bank Address (cont.)",
     "Please enter additional address\ninformation (if applicable).\n\nExample: Floor 12"),
    ("tx1_cash_recipient_suite",   "Suite",     "Field 3", "Recipient Bank Suite/Mail Stop",
     "Please enter the suite or\nmail stop number.\n\nExample: Suite 800"),
    ("tx1_cash_recipient_city",    "City",      "Field 4", "Recipient Bank City",
     "Please enter the city where\nthe recipient bank is located.\n\nExample: New York"),
    ("tx1_cash_recipient_country", "Country",   "Field 5", "Recipient Bank Country",
     "Please enter the country where\nthe recipient bank is located.\n\nExample: United States"),
    ("tx1_cash_recipient_state",   "State",     "Field 6", "Recipient Bank State",
     "Please enter the state where\nthe recipient bank is located.\n\nExample: New York"),
    ("tx1_cash_recipient_zip",     "Zip/Route", "Field 7", "Recipient Bank Zip Code/Route",
     "Please enter the zip code or route\nfor the recipient bank.\n\nExample: 10001"),
]

_CASH_S5_STATE_TO_IDX = {
    "CRS02_TX1_CASH_RECIP_ADDR1":   0,
    "CRS02_TX1_CASH_RECIP_ADDR2":   1,
    "CRS02_TX1_CASH_RECIP_SUITE":   2,
    "CRS02_TX1_CASH_RECIP_CITY":    3,
    "CRS02_TX1_CASH_RECIP_COUNTRY": 4,
    "CRS02_TX1_CASH_RECIP_STATE":   5,
    "CRS02_TX1_CASH_RECIP_ZIP":     6,
}

_CASH_S5_STATES = [
    "CRS02_TX1_CASH_RECIP_ADDR1", "CRS02_TX1_CASH_RECIP_ADDR2",
    "CRS02_TX1_CASH_RECIP_SUITE", "CRS02_TX1_CASH_RECIP_CITY",
    "CRS02_TX1_CASH_RECIP_COUNTRY", "CRS02_TX1_CASH_RECIP_STATE",
    "CRS02_TX1_CASH_RECIP_ZIP",
]


async def crs02_tx1_cash_step5_field(target, ctx, field_idx: int):
    """Show a single Cash Step 5 recipient field prompt."""
    await _seq_field_show(target, ctx, _CASH_S5_SEQ, _CASH_S5_STATES,
                          field_idx, "CASH_S5_SKIP", "CASH_S5_FIELD_BACK")


async def crs02_tx1_cash_step5(target, ctx):
    """Transaction #1 Cash Step 5 • Add Recipient — start from first unfilled."""
    d = ctx.user_data
    for idx, (data_key, *_) in enumerate(_CASH_S5_SEQ):
        if not (d.get(data_key) and str(d.get(data_key)).strip()):
            await crs02_tx1_cash_step5_field(target, ctx, idx)
            return
    await crs02_tx1_cash_step6(target, ctx)


async def crs02_tx1_cash_step5_edit(target, ctx):
    """Cash Step 5 edit menu — all recipient fields as buttons."""
    await _seq_edit_menu_show(target, ctx, _CASH_S5_SEQ, 0,
        "Cash", "Step 5", "CASH_E_F", None, None, "CASH_E_DONE")


async def crs02_tx1_cash_step5_edit_field(target, ctx, field_idx):
    """Show a single Cash field prompt in edit mode."""
    ctx.user_data["_edit_mode"] = "cash_s5"
    await _seq_edit_field_show(target, ctx, _CASH_S5_SEQ, _CASH_S5_STATES,
                                field_idx, "CASH_E_BACK")


async def crs02_tx1_cash_step6(target, ctx):
    """Transaction #1 Cash Step 6 • Transaction Summary"""
    ctx.user_data["state"] = None
    d = ctx.user_data
    sent_lost_val = d.get("tx1_sent_lost")
    sent_lost = "✅ Yes" if sent_lost_val is True else ("❌ No" if sent_lost_val is False else "—")
    amount = d.get("tx1_amount") or "—"
    date = d.get("tx1_date") or "—"
    bank_contacted = "✅ Yes" if d.get("tx1_cash_bank_contacted") is True else ("❌ No" if d.get("tx1_cash_bank_contacted") is False else "—")
    try:
        amt_fmt = f"${float(amount):,.2f}" if amount != "—" else "—"
    except Exception:
        amt_fmt = str(amount)

    addr1 = d.get("tx1_cash_recipient_addr1") or "—"
    addr2 = d.get("tx1_cash_recipient_addr2") or "—"
    suite = d.get("tx1_cash_recipient_suite") or "—"
    city = d.get("tx1_cash_recipient_city") or "—"
    country = d.get("tx1_cash_recipient_country") or "—"
    state = d.get("tx1_cash_recipient_state") or "—"
    zipc = d.get("tx1_cash_recipient_zip") or "—"

    text = (
        "IC3 | Internet Crime Complaint Center\n"
        "Financial Transaction(s) CRS-02#1\n"
        f"Transaction #{_tx_no(ctx)} - Cash\n"
        "Step 6 • Transaction Summary\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Transaction Type  : Cash\n"
        f"*Money Sent/Lost  : {sent_lost}\n"
        f"*Amount           : {amt_fmt} USD\n"
        f"*Date             : {date}\n"
        f"Bank Contacted    : {bank_contacted}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Recipient\n"
        f"Address           : {addr1}\n"
        f"Address (cont.)   : {addr2}\n"
        f"Suite/Mail Stop   : {suite}\n"
        f"City              : {city}\n"
        f"Country           : {country}\n"
        f"State             : {state}\n"
        f"Zip/Route         : {zipc}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Edit", callback_data=CASH_S6_EDIT),
            InlineKeyboardButton("✅ Submit", callback_data=CASH_S6_SAVE),
        ],
    ])
    await target.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def crs02_tx1_check_step4(target, ctx):
    """Transaction #1 Check/Cashier's Check • Step 4 — bank/exchange contacted"""
    ctx.user_data["state"] = None
    text = (
        f"Transaction #{_tx_no(ctx)}\n"
        "Step 4• Check/Cashier's Check \n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Did you contact your bank, financial \n"
        "institution, or cryptocurrency exchange?\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes", callback_data=CHECK_S4_YES),
            InlineKeyboardButton("❌ No",  callback_data=CHECK_S4_NO),
        ],
    ])
    await target.reply_text(text, parse_mode="HTML", reply_markup=kb)


# ─── Check Step 5 sequential fields ──────────────────────────────────────
_CHECK_S5_SEQ = [
    # Originating Bank (5 fields)
    ("tx1_check_orig_bank_name",    "Orig Bank",    "Field 1",  "Originating Bank Name",
     "Please reply with the originating\nbank name.\n\nExample: Bank of America"),
    ("tx1_check_orig_bank_city",    "Orig City",    "Field 2",  "Originating Bank City",
     "Please reply with the originating\nbank city.\n\nExample: New York"),
    ("tx1_check_orig_bank_country", "Orig Country", "Field 3",  "Originating Bank Country",
     "Please reply with the originating\nbank country.\n\nExample: United States"),
    ("tx1_check_orig_name_on_acct", "Orig Name",    "Field 4",  "Originating Name on Account",
     "Please reply with the name on the\noriginating account.\n\nExample: John Doe"),
    ("tx1_check_orig_account_no",   "Orig Acct#",   "Field 5",  "Originating Account Number",
     "Please reply with the originating\naccount number.\n\nExample: <code>123456789</code>"),
    # Recipient Bank (7 fields)
    ("tx1_check_recip_bank_name",    "Recip Bank",    "Field 6",  "Recipient Bank Name",
     "Please reply with the recipient\nbank name.\n\nExample: Chase Bank"),
    ("tx1_check_recip_bank_city",    "Recip City",    "Field 7",  "Recipient Bank City",
     "Please reply with the recipient\nbank city.\n\nExample: Los Angeles"),
    ("tx1_check_recip_bank_country", "Recip Country", "Field 8",  "Recipient Bank Country",
     "Please reply with the recipient\nbank country.\n\nExample: United States"),
    ("tx1_check_recip_name_on_acct", "Recip Name",    "Field 9",  "Recipient Name on Account",
     "Please reply with the name on the\nrecipient account.\n\nExample: Jane Smith"),
    ("tx1_check_recip_account_no",   "Recip Acct#",   "Field 10", "Recipient Account Number",
     "Please reply with the recipient\naccount number.\n\nExample: <code>987654321</code>"),
    ("tx1_check_recip_routing_no",   "Routing#",      "Field 11", "Recipient Routing Number",
     "Please reply with the recipient\nrouting number.\n\nExample: <code>021000021</code>"),
    ("tx1_check_recip_swift",        "SWIFT",         "Field 12", "Recipient SWIFT Code",
     "Please reply with the recipient\nSWIFT/BIC code.\n\nExample: <code>CHASUS33</code>"),
]

_CHECK_S5_STATE_TO_IDX = {
    "CRS02_TX1_CHECK_OBANK":    0,
    "CRS02_TX1_CHECK_OCITY":    1,
    "CRS02_TX1_CHECK_OCOUNTRY": 2,
    "CRS02_TX1_CHECK_ONAME":    3,
    "CRS02_TX1_CHECK_OACCT":    4,
    "CRS02_TX1_CHECK_RBANK":    5,
    "CRS02_TX1_CHECK_RCITY":    6,
    "CRS02_TX1_CHECK_RCOUNTRY": 7,
    "CRS02_TX1_CHECK_RNAME":    8,
    "CRS02_TX1_CHECK_RACCT":    9,
    "CRS02_TX1_CHECK_RROUTING": 10,
    "CRS02_TX1_CHECK_RSWIFT":   11,
}

_CHECK_S5_STATES = [
    "CRS02_TX1_CHECK_OBANK", "CRS02_TX1_CHECK_OCITY",
    "CRS02_TX1_CHECK_OCOUNTRY", "CRS02_TX1_CHECK_ONAME",
    "CRS02_TX1_CHECK_OACCT",
    "CRS02_TX1_CHECK_RBANK", "CRS02_TX1_CHECK_RCITY",
    "CRS02_TX1_CHECK_RCOUNTRY", "CRS02_TX1_CHECK_RNAME",
    "CRS02_TX1_CHECK_RACCT", "CRS02_TX1_CHECK_RROUTING",
    "CRS02_TX1_CHECK_RSWIFT",
]


async def crs02_tx1_check_step5_field(target, ctx, field_idx: int):
    """Show a single Check Step 5 bank field prompt."""
    await _seq_field_show(target, ctx, _CHECK_S5_SEQ, _CHECK_S5_STATES,
                          field_idx, "CHECK_S5_SKIP", "CHECK_S5_FIELD_BACK")


async def crs02_tx1_check_step5(target, ctx):
    """Transaction #1 Check Step 5 • Add Bank Account — start from first unfilled."""
    d = ctx.user_data
    for idx, (data_key, *_) in enumerate(_CHECK_S5_SEQ):
        if not (d.get(data_key) and str(d.get(data_key)).strip()):
            await crs02_tx1_check_step5_field(target, ctx, idx)
            return
    await crs02_tx1_check_step6(target, ctx)


async def crs02_tx1_check_step5_edit(target, ctx, expanded="orig"):
    """Check Step 5 edit menu — accordion with Originating/Recipient sections."""
    await _seq_edit_menu_show(target, ctx, _CHECK_S5_SEQ, 5,
        "Check/Cashier's Check", "Step 5", "CHK_E_F", "CHK_E_O", "CHK_E_R", "CHK_E_DONE", expanded)


async def crs02_tx1_check_step5_edit_field(target, ctx, field_idx):
    """Show a single Check field prompt in edit mode."""
    ctx.user_data["_edit_mode"] = "check_s5"
    await _seq_edit_field_show(target, ctx, _CHECK_S5_SEQ, _CHECK_S5_STATES,
                                field_idx, "CHK_E_BACK")


async def crs02_tx1_check_step6(target, ctx):
    """Transaction #1 Check/Cashier's Check Step 6 • Transaction Summary"""
    ctx.user_data["state"] = None
    d = ctx.user_data
    sent_lost_val = d.get("tx1_sent_lost")
    sent_lost = "✅ Yes" if sent_lost_val is True else ("❌ No" if sent_lost_val is False else "—")
    amount = d.get("tx1_amount") or "—"
    date = d.get("tx1_date") or "—"
    bank_contacted = "✅ Yes" if d.get("tx1_check_bank_contacted") is True else ("❌ No" if d.get("tx1_check_bank_contacted") is False else "—")
    try:
        amt_fmt = f"${float(amount):,.2f}" if amount != "—" else "—"
    except Exception:
        amt_fmt = str(amount)

    text = (
        "IC3 | Internet Crime Complaint Center\n"
        "Financial Transaction(s) CRS-02#1\n"
        f"Transaction #{_tx_no(ctx)} - Check/Cashier's Check\n"
        "Step 6 • Transaction Summary\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Transaction Type  : Check/Cashier's Check\n"
        f"*Money Sent/Lost  : {sent_lost}\n"
        f"*Amount           : {amt_fmt} USD\n"
        f"*Date             : {date}\n"
        f"Bank Contacted    : {bank_contacted}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Originating\n"
        f"Bank Name         : {d.get('tx1_check_orig_bank_name') or '—'}\n"
        f"Bank City         : {d.get('tx1_check_orig_bank_city') or '—'}\n"
        f"Bank Country      : {d.get('tx1_check_orig_bank_country') or '—'}\n"
        f"Name on Acct      : {d.get('tx1_check_orig_name_on_acct') or '—'}\n"
        f"Account Number    : {d.get('tx1_check_orig_account_no') or '—'}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Recipient\n"
        f"Bank Name         : {d.get('tx1_check_recip_bank_name') or '—'}\n"
        f"Bank City         : {d.get('tx1_check_recip_bank_city') or '—'}\n"
        f"Bank Country      : {d.get('tx1_check_recip_bank_country') or '—'}\n"
        f"Name on Acct      : {d.get('tx1_check_recip_name_on_acct') or '—'}\n"
        f"Account Number    : {d.get('tx1_check_recip_account_no') or '—'}\n"
        f"Routing Number    : {d.get('tx1_check_recip_routing_no') or '—'}\n"
        f"SWIFT Code        : {d.get('tx1_check_recip_swift') or '—'}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Edit", callback_data=CHECK_S6_EDIT),
            InlineKeyboardButton("✅ Submit", callback_data=CHECK_S6_SAVE),
        ],
    ])
    await target.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def crs02_tx1_money_order_step4(target, ctx):
    """Transaction #1 Money Order • Step 4 — bank/exchange contacted"""
    ctx.user_data["state"] = None
    text = (
        f"Transaction #{_tx_no(ctx)}\n"
        "Step 4• Money Order\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Did you contact your bank,\n"
        " financial institution,\n"
        "or cryptocurrency exchange?\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes", callback_data=MO_S4_YES),
            InlineKeyboardButton("❌ No",  callback_data=MO_S4_NO),
        ],
    ])
    await target.reply_text(text, parse_mode="HTML", reply_markup=kb)


# ─── Money Order Step 5 sequential fields ────────────────────────────────
_MO_S5_SEQ = [
    # Originating Bank (6 fields)
    ("tx1_mo_orig_bank_name",    "Orig Bank",    "Field 1",  "Originating Bank Name",
     "Please reply with the originating\nbank name.\n\nExample: Wells Fargo"),
    ("tx1_mo_orig_bank_address", "Orig Addr",    "Field 2",  "Originating Bank Address",
     "Please reply with the originating\nbank address.\n\nExample: 123 Main Street"),
    ("tx1_mo_orig_bank_city",    "Orig City",    "Field 3",  "Originating Bank City",
     "Please reply with the originating\nbank city.\n\nExample: San Francisco"),
    ("tx1_mo_orig_bank_country", "Orig Country", "Field 4",  "Originating Bank Country",
     "Please reply with the originating\nbank country.\n\nExample: United States"),
    ("tx1_mo_orig_bank_state",   "Orig State",   "Field 5",  "Originating Bank State",
     "Please reply with the originating\nbank state.\n\nExample: California"),
    ("tx1_mo_orig_name_on_acct", "Orig Name",    "Field 6",  "Originating Name on Account",
     "Please reply with the name on the\noriginating account.\n\nExample: John Doe"),
    # Recipient Bank (9 fields)
    ("tx1_mo_recip_bank_name",    "Recip Bank",    "Field 7",  "Recipient Bank Name",
     "Please reply with the recipient\nbank name.\n\nExample: Bank of America"),
    ("tx1_mo_recip_bank_address", "Recip Addr",    "Field 8",  "Recipient Bank Address",
     "Please reply with the recipient\nbank address.\n\nExample: 456 Wall Street"),
    ("tx1_mo_recip_bank_city",    "Recip City",    "Field 9",  "Recipient Bank City",
     "Please reply with the recipient\nbank city.\n\nExample: New York"),
    ("tx1_mo_recip_bank_country", "Recip Country", "Field 10", "Recipient Bank Country",
     "Please reply with the recipient\nbank country.\n\nExample: United States"),
    ("tx1_mo_recip_bank_state",   "Recip State",   "Field 11", "Recipient Bank State",
     "Please reply with the recipient\nbank state.\n\nExample: New York"),
    ("tx1_mo_recip_name_on_acct", "Recip Name",    "Field 12", "Recipient Name on Account",
     "Please reply with the name on the\nrecipient account.\n\nExample: Jane Smith"),
    ("tx1_mo_recip_routing_no",   "Routing#",      "Field 13", "Recipient Routing Number",
     "Please reply with the recipient\nrouting number.\n\nExample: <code>021000021</code>"),
    ("tx1_mo_recip_account_no",   "Recip Acct#",   "Field 14", "Recipient Account Number",
     "Please reply with the recipient\naccount number.\n\nExample: <code>987654321</code>"),
    ("tx1_mo_recip_swift",        "SWIFT",         "Field 15", "Recipient SWIFT Code",
     "Please reply with the recipient\nSWIFT/BIC code.\n\nExample: <code>BOFAUS3N</code>"),
]

_MO_S5_STATE_TO_IDX = {
    "CRS02_TX1_MO_OBANK":    0, "CRS02_TX1_MO_OADDR":    1,
    "CRS02_TX1_MO_OCITY":    2, "CRS02_TX1_MO_OCOUNTRY": 3,
    "CRS02_TX1_MO_OSTATE":   4, "CRS02_TX1_MO_ONAME":    5,
    "CRS02_TX1_MO_RBANK":    6, "CRS02_TX1_MO_RADDR":    7,
    "CRS02_TX1_MO_RCITY":    8, "CRS02_TX1_MO_RCOUNTRY": 9,
    "CRS02_TX1_MO_RSTATE":  10, "CRS02_TX1_MO_RNAME":   11,
    "CRS02_TX1_MO_RROUTING":12, "CRS02_TX1_MO_RACCT":   13,
    "CRS02_TX1_MO_RSWIFT":  14,
}

_MO_S5_STATES = [
    "CRS02_TX1_MO_OBANK", "CRS02_TX1_MO_OADDR",
    "CRS02_TX1_MO_OCITY", "CRS02_TX1_MO_OCOUNTRY",
    "CRS02_TX1_MO_OSTATE", "CRS02_TX1_MO_ONAME",
    "CRS02_TX1_MO_RBANK", "CRS02_TX1_MO_RADDR",
    "CRS02_TX1_MO_RCITY", "CRS02_TX1_MO_RCOUNTRY",
    "CRS02_TX1_MO_RSTATE", "CRS02_TX1_MO_RNAME",
    "CRS02_TX1_MO_RROUTING", "CRS02_TX1_MO_RACCT",
    "CRS02_TX1_MO_RSWIFT",
]


async def crs02_tx1_money_order_step5_field(target, ctx, field_idx: int):
    """Show a single Money Order Step 5 bank field prompt."""
    await _seq_field_show(target, ctx, _MO_S5_SEQ, _MO_S5_STATES,
                          field_idx, "MO_S5_SKIP", "MO_S5_FIELD_BACK")


async def crs02_tx1_money_order_step5(target, ctx):
    """Transaction #1 Money Order Step 5 • Add Bank Account — start from first unfilled."""
    d = ctx.user_data
    for idx, (data_key, *_) in enumerate(_MO_S5_SEQ):
        if not (d.get(data_key) and str(d.get(data_key)).strip()):
            await crs02_tx1_money_order_step5_field(target, ctx, idx)
            return
    await crs02_tx1_money_order_step6(target, ctx)


async def crs02_tx1_mo_step5_edit(target, ctx, expanded="orig"):
    """Money Order Step 5 edit menu — accordion with Originating/Recipient."""
    await _seq_edit_menu_show(target, ctx, _MO_S5_SEQ, 6,
        "Money Order", "Step 5", "MO_E_F", "MO_E_O", "MO_E_R", "MO_E_DONE", expanded)


async def crs02_tx1_mo_step5_edit_field(target, ctx, field_idx):
    """Show a single MO field prompt in edit mode."""
    ctx.user_data["_edit_mode"] = "mo_s5"
    await _seq_edit_field_show(target, ctx, _MO_S5_SEQ, _MO_S5_STATES,
                                field_idx, "MO_E_BACK")


async def crs02_tx1_money_order_step6(target, ctx):
    """Transaction #1 Money Order Step 6 • Transaction Summary"""
    ctx.user_data["state"] = None
    d = ctx.user_data
    sent_lost_val = d.get("tx1_sent_lost")
    sent_lost = "✅ Yes" if sent_lost_val is True else ("❌ No" if sent_lost_val is False else "—")
    amount = d.get("tx1_amount") or "—"
    date = d.get("tx1_date") or "—"
    bank_contacted = "✅ Yes" if d.get("tx1_mo_bank_contacted") is True else ("❌ No" if d.get("tx1_mo_bank_contacted") is False else "—")
    try:
        amt_fmt = f"${float(amount):,.2f}" if amount != "—" else "—"
    except Exception:
        amt_fmt = str(amount)

    text = (
        "IC3 | Internet Crime Complaint Center\n"
        "Financial Transaction(s) CRS-02#1\n"
        f"Transaction #{_tx_no(ctx)} - Money Order\n"
        "Step 6 • Transaction Summary\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Transaction Type  : Money Order\n"
        f"*Money Sent/Lost  : {sent_lost}\n"
        f"*Amount           : {amt_fmt} USD\n"
        f"*Date             : {date}\n"
        f"Bank Contacted    : {bank_contacted}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Originating Bank\n"
        f"Bank Name         : {d.get('tx1_mo_orig_bank_name') or '—'}\n"
        f"Bank Address      : {d.get('tx1_mo_orig_bank_address') or '—'}\n"
        f"Bank City         : {d.get('tx1_mo_orig_bank_city') or '—'}\n"
        f"Bank Country      : {d.get('tx1_mo_orig_bank_country') or '—'}\n"
        f"Bank State        : {d.get('tx1_mo_orig_bank_state') or '—'}\n"
        f"Name on Account   : {d.get('tx1_mo_orig_name_on_acct') or '—'}\n"
        f"Account Number    : {d.get('tx1_mo_orig_account_no') or '—'}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Recipient Bank\n"
        f"Bank Name         : {d.get('tx1_mo_recip_bank_name') or '—'}\n"
        f"Bank Address      : {d.get('tx1_mo_recip_bank_address') or '—'}\n"
        f"Bank City         : {d.get('tx1_mo_recip_bank_city') or '—'}\n"
        f"Bank Country      : {d.get('tx1_mo_recip_bank_country') or '—'}\n"
        f"Bank State        : {d.get('tx1_mo_recip_bank_state') or '—'}\n"
        f"Name on Account   : {d.get('tx1_mo_recip_name_on_acct') or '—'}\n"
        f"Account Number    : {d.get('tx1_mo_recip_account_no') or '—'}\n"
        f"Routing Number    : {d.get('tx1_mo_recip_routing_no') or '—'}\n"
        f"SWIFT Code        : {d.get('tx1_mo_recip_swift') or '—'}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Edit", callback_data=MO_S6_EDIT),
            InlineKeyboardButton("✅ Submit", callback_data=MO_S6_SAVE),
        ],
    ])
    await target.reply_text(text, parse_mode="HTML", reply_markup=kb)


# ─── Transaction #1 · Wire Transfer 子流程 ───────────────────────────────
WIRE_S4_YES     = "WIRE_S4_YES"
WIRE_S4_NO      = "WIRE_S4_NO"
WIRE_S5_OBANK   = "WIRE_S5_OBANK"
WIRE_S5_OADDR   = "WIRE_S5_OADDR"
WIRE_S5_OCITY   = "WIRE_S5_OCITY"
WIRE_S5_OCOUNTRY = "WIRE_S5_OCOUNTRY"
WIRE_S5_OSTATE  = "WIRE_S5_OSTATE"
WIRE_S5_ONAME   = "WIRE_S5_ONAME"
WIRE_S5_RBANK   = "WIRE_S5_RBANK"
WIRE_S5_RADDR   = "WIRE_S5_RADDR"
WIRE_S5_RCITY   = "WIRE_S5_RCITY"
WIRE_S5_RCOUNTRY = "WIRE_S5_RCOUNTRY"
WIRE_S5_RSTATE  = "WIRE_S5_RSTATE"
WIRE_S5_RNAME   = "WIRE_S5_RNAME"
WIRE_S5_RROUTING = "WIRE_S5_RROUTING"
WIRE_S5_RACCT   = "WIRE_S5_RACCT"
WIRE_S5_RSWIFT  = "WIRE_S5_RSWIFT"
WIRE_S5_SAVE         = "WIRE_S5_SAVE"
WIRE_S5_BACK         = "WIRE_S5_BACK"
WIRE_S5_TOGGLE_ORIG  = "WIRE_S5_TOGGLE_ORIG"
WIRE_S5_TOGGLE_RECIP = "WIRE_S5_TOGGLE_RECIP"
WIRE_S6_EDIT    = "WIRE_S6_EDIT"
WIRE_S6_SAVE    = "WIRE_S6_SAVE"


# ─── Wire Transfer Step 5 sequential fields ──────────────────────────────
_WIRE_S5_SEQ = [
    # Originating Bank (6 fields)
    ("tx1_wire_orig_bank_name",    "Orig Bank",    "Field 1",  "Originating Bank Name",
     "Please reply with the originating\nbank name.\n\nExample: Chase Bank"),
    ("tx1_wire_orig_bank_address", "Orig Addr",    "Field 2",  "Originating Bank Address",
     "Please reply with the originating\nbank address.\n\nExample: 123 Main Street"),
    ("tx1_wire_orig_bank_city",    "Orig City",    "Field 3",  "Originating Bank City",
     "Please reply with the originating\nbank city.\n\nExample: New York"),
    ("tx1_wire_orig_bank_country", "Orig Country", "Field 4",  "Originating Bank Country",
     "Please reply with the originating\nbank country.\n\nExample: United States"),
    ("tx1_wire_orig_bank_state",   "Orig State",   "Field 5",  "Originating Bank State",
     "Please reply with the originating\nbank state.\n\nExample: NY"),
    ("tx1_wire_orig_name_on_acct", "Orig Name",    "Field 6",  "Originating Name on Account",
     "Please reply with the name on the\noriginating account.\n\nExample: John Doe"),
    # Recipient Bank (9 fields)
    ("tx1_wire_recip_bank_name",    "Recip Bank",    "Field 7",  "Recipient Bank Name",
     "Please reply with the recipient\nbank name.\n\nExample: Bank of America"),
    ("tx1_wire_recip_bank_address", "Recip Addr",    "Field 8",  "Recipient Bank Address",
     "Please reply with the recipient\nbank address.\n\nExample: 456 Wall Street"),
    ("tx1_wire_recip_bank_city",    "Recip City",    "Field 9",  "Recipient Bank City",
     "Please reply with the recipient\nbank city.\n\nExample: Los Angeles"),
    ("tx1_wire_recip_bank_country", "Recip Country", "Field 10", "Recipient Bank Country",
     "Please reply with the recipient\nbank country.\n\nExample: United States"),
    ("tx1_wire_recip_bank_state",   "Recip State",   "Field 11", "Recipient Bank State",
     "Please reply with the recipient\nbank state.\n\nExample: CA"),
    ("tx1_wire_recip_name_on_acct", "Recip Name",    "Field 12", "Recipient Name on Account",
     "Please reply with the name on the\nrecipient account.\n\nExample: Jane Smith"),
    ("tx1_wire_recip_routing_no",   "Routing#",      "Field 13", "Recipient Routing Number",
     "Please reply with the recipient\nrouting number.\n\nExample: <code>021000021</code>"),
    ("tx1_wire_recip_account_no",   "Recip Acct#",   "Field 14", "Recipient Account Number",
     "Please reply with the recipient\naccount number.\n\nExample: <code>987654321</code>"),
    ("tx1_wire_recip_swift",        "SWIFT",         "Field 15", "Recipient SWIFT Code",
     "Please reply with the recipient\nSWIFT/BIC code.\n\nExample: <code>CHASUS33</code>"),
]

_WIRE_S5_STATE_TO_IDX = {
    "CRS02_TX1_WIRE_OBANK":    0, "CRS02_TX1_WIRE_OADDR":    1,
    "CRS02_TX1_WIRE_OCITY":    2, "CRS02_TX1_WIRE_OCOUNTRY": 3,
    "CRS02_TX1_WIRE_OSTATE":   4, "CRS02_TX1_WIRE_ONAME":    5,
    "CRS02_TX1_WIRE_RBANK":    6, "CRS02_TX1_WIRE_RADDR":    7,
    "CRS02_TX1_WIRE_RCITY":    8, "CRS02_TX1_WIRE_RCOUNTRY": 9,
    "CRS02_TX1_WIRE_RSTATE":  10, "CRS02_TX1_WIRE_RNAME":   11,
    "CRS02_TX1_WIRE_RROUTING":12, "CRS02_TX1_WIRE_RACCT":   13,
    "CRS02_TX1_WIRE_RSWIFT":  14,
}

_WIRE_S5_STATES = [
    "CRS02_TX1_WIRE_OBANK", "CRS02_TX1_WIRE_OADDR",
    "CRS02_TX1_WIRE_OCITY", "CRS02_TX1_WIRE_OCOUNTRY",
    "CRS02_TX1_WIRE_OSTATE", "CRS02_TX1_WIRE_ONAME",
    "CRS02_TX1_WIRE_RBANK", "CRS02_TX1_WIRE_RADDR",
    "CRS02_TX1_WIRE_RCITY", "CRS02_TX1_WIRE_RCOUNTRY",
    "CRS02_TX1_WIRE_RSTATE", "CRS02_TX1_WIRE_RNAME",
    "CRS02_TX1_WIRE_RROUTING", "CRS02_TX1_WIRE_RACCT",
    "CRS02_TX1_WIRE_RSWIFT",
]


async def crs02_tx1_wire_step5_field(target, ctx, field_idx: int):
    """Show a single Wire Transfer Step 5 bank field prompt."""
    await _seq_field_show(target, ctx, _WIRE_S5_SEQ, _WIRE_S5_STATES,
                          field_idx, "WIRE_S5_SKIP", "WIRE_S5_FIELD_BACK")


async def crs02_tx1_wire_step4(target, ctx):
    """Transaction #1 Wire Transfer • Step 4 — bank/exchange contacted"""
    ctx.user_data["state"] = None
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Yes", callback_data=WIRE_S4_YES),
        InlineKeyboardButton("❌ No",  callback_data=WIRE_S4_NO),
    ]])
    await target.reply_text(
        f"Transaction #{_tx_no(ctx)}\n"
        "Step 4 • Wire Transfer\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Did you contact your bank, financial\n"
        "institution, or cryptocurrency exchange?\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def crs02_tx1_wire_step5(target, ctx):
    """Transaction #1 Wire Transfer Step 5 • Add Bank Account — start from first unfilled."""
    d = ctx.user_data
    for idx, (data_key, *_) in enumerate(_WIRE_S5_SEQ):
        if not (d.get(data_key) and str(d.get(data_key)).strip()):
            await crs02_tx1_wire_step5_field(target, ctx, idx)
            return
    await crs02_tx1_wire_step6(target, ctx)


async def crs02_tx1_wire_step5_edit(target, ctx, expanded="orig"):
    """Wire Transfer Step 5 edit menu — accordion with Originating/Recipient."""
    await _seq_edit_menu_show(target, ctx, _WIRE_S5_SEQ, 6,
        "Wire Transfer", "Step 5", "WR_E_F", "WR_E_O", "WR_E_R", "WR_E_DONE", expanded)


async def crs02_tx1_wire_step5_edit_field(target, ctx, field_idx):
    """Show a single Wire field prompt in edit mode."""
    ctx.user_data["_edit_mode"] = "wire_s5"
    await _seq_edit_field_show(target, ctx, _WIRE_S5_SEQ, _WIRE_S5_STATES,
                                field_idx, "WR_E_BACK")


async def crs02_tx1_wire_step6(target, ctx):
    """Transaction #1 Wire Transfer Step 6 • Transaction Summary"""
    ctx.user_data["state"] = None
    d = ctx.user_data
    sent_lost_val = d.get("tx1_sent_lost")
    sent_lost = "✅ Yes" if sent_lost_val is True else ("❌ No" if sent_lost_val is False else "—")
    amount = d.get("tx1_amount") or "—"
    bank_contacted = "✅ Yes" if d.get("tx1_wire_bank_contacted") is True else ("❌ No" if d.get("tx1_wire_bank_contacted") is False else "—")
    try:
        amt_fmt = f"${float(amount):,.2f}" if amount != "—" else "—"
    except Exception:
        amt_fmt = str(amount)

    text = (
        "IC3 | Internet Crime Complaint Center\n"
        "Financial Transaction(s) CRS-02#1\n"
        f"Transaction #{_tx_no(ctx)} - Wire Transfer\n"
        "Step 6 • Transaction Summary\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Transaction Type  : Wire Transfer\n"
        f"*Money Sent/Lost  : {sent_lost}\n"
        f"*Amount           : {amt_fmt} USD\n"
        f"*Date             : {d.get('tx1_date') or '—'}\n"
        f"Bank Contacted    : {bank_contacted}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Originating Bank\n"
        f"Bank Name         : {d.get('tx1_wire_orig_bank_name') or '—'}\n"
        f"Bank Address      : {d.get('tx1_wire_orig_bank_address') or '—'}\n"
        f"Bank City         : {d.get('tx1_wire_orig_bank_city') or '—'}\n"
        f"Bank Country      : {d.get('tx1_wire_orig_bank_country') or '—'}\n"
        f"Bank State        : {d.get('tx1_wire_orig_bank_state') or '—'}\n"
        f"Name on Account   : {d.get('tx1_wire_orig_name_on_acct') or '—'}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Recipient Bank\n"
        f"Bank Name         : {d.get('tx1_wire_recip_bank_name') or '—'}\n"
        f"Bank Address      : {d.get('tx1_wire_recip_bank_address') or '—'}\n"
        f"Bank City         : {d.get('tx1_wire_recip_bank_city') or '—'}\n"
        f"Bank Country      : {d.get('tx1_wire_recip_bank_country') or '—'}\n"
        f"Bank State        : {d.get('tx1_wire_recip_bank_state') or '—'}\n"
        f"Name on Account   : {d.get('tx1_wire_recip_name_on_acct') or '—'}\n"
        f"Routing Number    : {d.get('tx1_wire_recip_routing_no') or '—'}\n"
        f"Account Number    : {d.get('tx1_wire_recip_account_no') or '—'}\n"
        f"SWIFT Code        : {d.get('tx1_wire_recip_swift') or '—'}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✏️ Edit", callback_data=WIRE_S6_EDIT),
        InlineKeyboardButton("✅ Submit", callback_data=WIRE_S6_SAVE),
    ]])
    await target.reply_text(text, parse_mode="HTML", reply_markup=kb)


# ─── Transaction #1 · Other 子流程 ──────────────────────────────────
OTHER_S4_SKIP         = "OTHER_S4_SKIP"
OTHER_S5_YES          = "OTHER_S5_YES"
OTHER_S5_NO           = "OTHER_S5_NO"
OTHER_S6_TOGGLE_ORIG  = "OTHER_S6_TOGGLE_ORIG"
OTHER_S6_TOGGLE_RECIP = "OTHER_S6_TOGGLE_RECIP"
OTHER_S6_OBANK        = "OTHER_S6_OBANK"
OTHER_S6_OADDR        = "OTHER_S6_OADDR"
OTHER_S6_OCITY        = "OTHER_S6_OCITY"
OTHER_S6_OCOUNTRY     = "OTHER_S6_OCOUNTRY"
OTHER_S6_OSTATE       = "OTHER_S6_OSTATE"
OTHER_S6_ONAME        = "OTHER_S6_ONAME"
OTHER_S6_RBANK        = "OTHER_S6_RBANK"
OTHER_S6_RADDR        = "OTHER_S6_RADDR"
OTHER_S6_RCITY        = "OTHER_S6_RCITY"
OTHER_S6_RCOUNTRY     = "OTHER_S6_RCOUNTRY"
OTHER_S6_RSTATE       = "OTHER_S6_RSTATE"
OTHER_S6_RNAME        = "OTHER_S6_RNAME"
OTHER_S6_RROUTING     = "OTHER_S6_RROUTING"
OTHER_S6_RACCT        = "OTHER_S6_RACCT"
OTHER_S6_RSWIFT       = "OTHER_S6_RSWIFT"
OTHER_S6_SAVE         = "OTHER_S6_SAVE"
OTHER_S6_BACK         = "OTHER_S6_BACK"
OTHER_S7_EDIT         = "OTHER_S7_EDIT"
OTHER_S7_SAVE         = "OTHER_S7_SAVE"

# ─── Other Step 6 sequential fields ──────────────────────────────────────
_OTHER_S6_SEQ = [
    # Originating Bank (6 fields)
    ("tx1_other_orig_bank_name",    "Orig Bank",    "Field 1",  "Originating Bank Name",
     "Please reply with the originating\nbank name.\n\nExample: Wells Fargo"),
    ("tx1_other_orig_bank_address", "Orig Addr",    "Field 2",  "Originating Bank Address",
     "Please reply with the originating\nbank address.\n\nExample: 123 Main Street"),
    ("tx1_other_orig_bank_city",    "Orig City",    "Field 3",  "Originating Bank City",
     "Please reply with the originating\nbank city.\n\nExample: San Francisco"),
    ("tx1_other_orig_bank_country", "Orig Country", "Field 4",  "Originating Bank Country",
     "Please reply with the originating\nbank country.\n\nExample: United States"),
    ("tx1_other_orig_bank_state",   "Orig State",   "Field 5",  "Originating Bank State",
     "Please reply with the originating\nbank state.\n\nExample: California"),
    ("tx1_other_orig_name_on_acct", "Orig Name",    "Field 6",  "Originating Name on Account",
     "Please reply with the name on the\noriginating account.\n\nExample: John Doe"),
    # Recipient Bank (9 fields)
    ("tx1_other_recip_bank_name",    "Recip Bank",    "Field 7",  "Recipient Bank Name",
     "Please reply with the recipient\nbank name.\n\nExample: Bank of America"),
    ("tx1_other_recip_bank_address", "Recip Addr",    "Field 8",  "Recipient Bank Address",
     "Please reply with the recipient\nbank address.\n\nExample: 456 Wall Street"),
    ("tx1_other_recip_bank_city",    "Recip City",    "Field 9",  "Recipient Bank City",
     "Please reply with the recipient\nbank city.\n\nExample: New York"),
    ("tx1_other_recip_bank_country", "Recip Country", "Field 10", "Recipient Bank Country",
     "Please reply with the recipient\nbank country.\n\nExample: United States"),
    ("tx1_other_recip_bank_state",   "Recip State",   "Field 11", "Recipient Bank State",
     "Please reply with the recipient\nbank state.\n\nExample: New York"),
    ("tx1_other_recip_name_on_acct", "Recip Name",    "Field 12", "Recipient Name on Account",
     "Please reply with the name on the\nrecipient account.\n\nExample: Jane Smith"),
    ("tx1_other_recip_routing_no",   "Routing#",      "Field 13", "Recipient Routing Number",
     "Please reply with the recipient\nrouting number.\n\nExample: <code>021000021</code>"),
    ("tx1_other_recip_account_no",   "Recip Acct#",   "Field 14", "Recipient Account Number",
     "Please reply with the recipient\naccount number.\n\nExample: <code>987654321</code>"),
    ("tx1_other_recip_swift",        "SWIFT",         "Field 15", "Recipient SWIFT Code",
     "Please reply with the recipient\nSWIFT/BIC code.\n\nExample: <code>BOFAUS3N</code>"),
]

_OTHER_S6_STATE_TO_IDX = {
    "CRS02_TX1_OTHER_OBANK":    0, "CRS02_TX1_OTHER_OADDR":    1,
    "CRS02_TX1_OTHER_OCITY":    2, "CRS02_TX1_OTHER_OCOUNTRY": 3,
    "CRS02_TX1_OTHER_OSTATE":   4, "CRS02_TX1_OTHER_ONAME":    5,
    "CRS02_TX1_OTHER_RBANK":    6, "CRS02_TX1_OTHER_RADDR":    7,
    "CRS02_TX1_OTHER_RCITY":    8, "CRS02_TX1_OTHER_RCOUNTRY": 9,
    "CRS02_TX1_OTHER_RSTATE":  10, "CRS02_TX1_OTHER_RNAME":   11,
    "CRS02_TX1_OTHER_RROUTING":12, "CRS02_TX1_OTHER_RACCT":   13,
    "CRS02_TX1_OTHER_RSWIFT":  14,
}

_OTHER_S6_STATES = [
    "CRS02_TX1_OTHER_OBANK", "CRS02_TX1_OTHER_OADDR",
    "CRS02_TX1_OTHER_OCITY", "CRS02_TX1_OTHER_OCOUNTRY",
    "CRS02_TX1_OTHER_OSTATE", "CRS02_TX1_OTHER_ONAME",
    "CRS02_TX1_OTHER_RBANK", "CRS02_TX1_OTHER_RADDR",
    "CRS02_TX1_OTHER_RCITY", "CRS02_TX1_OTHER_RCOUNTRY",
    "CRS02_TX1_OTHER_RSTATE", "CRS02_TX1_OTHER_RNAME",
    "CRS02_TX1_OTHER_RROUTING", "CRS02_TX1_OTHER_RACCT",
    "CRS02_TX1_OTHER_RSWIFT",
]


async def crs02_tx1_other_step6_field(target, ctx, field_idx: int):
    """Show a single Other Step 6 bank field prompt."""
    await _seq_field_show(target, ctx, _OTHER_S6_SEQ, _OTHER_S6_STATES,
                          field_idx, "OTHER_S6_SKIP", "OTHER_S6_FIELD_BACK")


async def crs02_tx1_other_step4(target, ctx):
    """Transaction #1 Other *Step 4 • Please Specify (required)"""
    ctx.user_data["state"] = "CRS02_TX1_OTHER_SPECIFY"
    await target.reply_text(
        f"Transaction #{_tx_no(ctx)}\n"
        "Other\n"
        "<b>*Step 4 • Please Specify</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>*If other, please specify:</i>\n"
        "Please describe the transaction type\n"
        "since you selected \"Other\"\n\n"
        "Please reply with the description:\n\n"
        "Example: Online Bank Transfer\n"
        "         Mobile Payment\n"
        "         Crypto Wallet Transfer\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="HTML",
    )


async def crs02_tx1_other_step5(target, ctx):
    """Transaction #1 Other Step 5 • Bank contacted Yes/No"""
    ctx.user_data["state"] = None
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Yes", callback_data=OTHER_S5_YES),
        InlineKeyboardButton("❌ No",  callback_data=OTHER_S5_NO),
    ]])
    await target.reply_text(
        f"Transaction #{_tx_no(ctx)}\n"
        "Other • Step 5\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Did you contact your bank, financial institution,\n"
        "or cryptocurrency exchange?\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def crs02_tx1_other_step6(target, ctx):
    """Transaction #1 Other Step 6 • Add Bank Account — start from first unfilled."""
    d = ctx.user_data
    for idx, (data_key, *_) in enumerate(_OTHER_S6_SEQ):
        if not (d.get(data_key) and str(d.get(data_key)).strip()):
            await crs02_tx1_other_step6_field(target, ctx, idx)
            return
    await crs02_tx1_other_step7(target, ctx)


async def crs02_tx1_other_step6_edit(target, ctx, expanded="orig"):
    """Other Step 6 edit menu — accordion with Originating/Recipient."""
    await _seq_edit_menu_show(target, ctx, _OTHER_S6_SEQ, 6,
        "Other", "Step 6", "OT_E_F", "OT_E_O", "OT_E_R", "OT_E_DONE", expanded)


async def crs02_tx1_other_step6_edit_field(target, ctx, field_idx):
    """Show a single Other field prompt in edit mode."""
    ctx.user_data["_edit_mode"] = "other_s6"
    await _seq_edit_field_show(target, ctx, _OTHER_S6_SEQ, _OTHER_S6_STATES,
                                field_idx, "OT_E_BACK")


async def crs02_tx1_other_step7(target, ctx):
    """Transaction #1 Other Step 7 • Transaction Summary"""
    ctx.user_data["state"] = None
    d = ctx.user_data
    sent_lost_val = d.get("tx1_sent_lost")
    sent_lost = "✅ Yes" if sent_lost_val is True else ("❌ No" if sent_lost_val is False else "—")
    amount = d.get("tx1_amount") or "—"
    try:
        amt_fmt = f"${float(amount):,.2f}" if amount != "—" else "—"
    except Exception:
        amt_fmt = str(amount)
    currency = d.get("tx1_currency") or "USD"
    date = d.get("tx1_date") or "—"
    contacted = "✅ Yes" if d.get("tx1_other_bank_contacted") is True else ("❌ No" if d.get("tx1_other_bank_contacted") is False else "—")
    specify = d.get("tx1_other_specify") or "—"

    text = (
        "IC3 | Internet Crime Complaint Center\n"
        "Financial Transaction(s) CRS-02#1\n"
        f"Transaction #{_tx_no(ctx)} - Other\n"
        "Step 7 • Transaction Summary\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Transaction Type  : Other\n"
        f"Specified Type    : {specify}\n"
        f"*Money Sent/Lost  : {sent_lost}\n"
        f"*Amount           : {amt_fmt} {currency}\n"
        f"*Date             : {date}\n"
        f"Bank Contacted    : {contacted}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Originating Bank\n"
        f"Bank Name         : {d.get('tx1_other_orig_bank_name') or '—'}\n"
        f"Bank Address      : {d.get('tx1_other_orig_bank_address') or '—'}\n"
        f"Bank City         : {d.get('tx1_other_orig_bank_city') or '—'}\n"
        f"Bank Country      : {d.get('tx1_other_orig_bank_country') or '—'}\n"
        f"Bank State        : {d.get('tx1_other_orig_bank_state') or '—'}\n"
        f"Name on Account   : {d.get('tx1_other_orig_name_on_acct') or '—'}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Recipient Bank\n"
        f"Bank Name         : {d.get('tx1_other_recip_bank_name') or '—'}\n"
        f"Bank Address      : {d.get('tx1_other_recip_bank_address') or '—'}\n"
        f"Bank City         : {d.get('tx1_other_recip_bank_city') or '—'}\n"
        f"Bank Country      : {d.get('tx1_other_recip_bank_country') or '—'}\n"
        f"Bank State        : {d.get('tx1_other_recip_bank_state') or '—'}\n"
        f"Name on Account   : {d.get('tx1_other_recip_name_on_acct') or '—'}\n"
        f"Routing Number    : {d.get('tx1_other_recip_routing_no') or '—'}\n"
        f"Account Number    : {d.get('tx1_other_recip_account_no') or '—'}\n"
        f"SWIFT Code        : {d.get('tx1_other_recip_swift') or '—'}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✏️ Edit", callback_data=OTHER_S7_EDIT),
        InlineKeyboardButton("✅ Submit", callback_data=OTHER_S7_SAVE),
    ]])
    await target.reply_text(text, parse_mode="HTML", reply_markup=kb)


# ─── Transaction #1 · Cryptocurrency/Crypto ATM 子流程 (Step 1~7) ───
CRYPTO_S1_YES = "CRYPTO_S1_YES"
CRYPTO_S1_NO = "CRYPTO_S1_NO"
CRYPTO_S4_YES = "CRYPTO_S4_YES"
CRYPTO_S4_NO = "CRYPTO_S4_NO"
CRYPTO_S5_CUR = "CRYPTO_S5_CUR"
CRYPTO_S5_TXHASH = "CRYPTO_S5_TXHASH"
CRYPTO_S5_ORIG = "CRYPTO_S5_ORIG"
CRYPTO_S5_RECIP = "CRYPTO_S5_RECIP"
CRYPTO_S5_SAVE = "CRYPTO_S5_SAVE"
CRYPTO_S5_BACK = "CRYPTO_S5_BACK"
CRYPTO_S5_CUR_BACK = "CRYPTO_S5_CUR_BACK"
CRYPTO_S6_NAME = "CRYPTO_S6_NAME"
CRYPTO_S6_ADDR = "CRYPTO_S6_ADDR"
CRYPTO_S6_CITY = "CRYPTO_S6_CITY"
CRYPTO_S6_COUNTRY = "CRYPTO_S6_CTRY"
CRYPTO_S6_STATE = "CRYPTO_S6_STATE"
CRYPTO_S6_ZIP = "CRYPTO_S6_ZIP"
CRYPTO_S6_SAVE = "CRYPTO_S6_SAVE"
CRYPTO_S6_BACK = "CRYPTO_S6_BACK"
CRYPTO_S7_EDIT = "CRYPTO_S7_EDIT"
CRYPTO_S7_SAVE = "CRYPTO_S7_SAVE"


def _tx1_crypto(d):
    """user_data 下 tx1_crypto_* 前缀的字典视图"""
    return {k.replace("tx1_crypto_", ""): v for k, v in d.items() if k.startswith("tx1_crypto_") and v is not None}


async def crs02_tx1_crypto_step1(target, ctx):
    """Transaction #1 Cryptocurrency/Crypto ATM Step 1 — Was the money sent or lost?"""
    # 兼容旧回调：转到通用 Step 1
    ctx.user_data["tx1_type"] = "CRYPTO"
    await crs02_tx1_common_step1(target, ctx)


async def crs02_tx1_crypto_step2(target, ctx):
    """Transaction #1 Cryptocurrency/Crypto ATM *Step 2 • Transaction Amount"""
    # 兼容旧状态：转到通用 Step 2
    ctx.user_data["tx1_type"] = "CRYPTO"
    await crs02_tx1_common_step2(target, ctx)


async def crs02_tx1_crypto_step3(target, ctx):
    """Transaction #1 Cryptocurrency/Crypto ATM *Step 3 • Transaction Date"""
    # 兼容旧状态：转到通用 Step 3
    ctx.user_data["tx1_type"] = "CRYPTO"
    await crs02_tx1_common_step3(target, ctx)


async def crs02_tx1_crypto_step4(target, ctx):
    """Transaction #1 Cryptocurrency/Crypto ATM Step 4 — Bank/Exchange contact"""
    ctx.user_data["state"] = None
    text = (
        f"Transaction #{_tx_no(ctx)}\n"
        "Cryptocurrency/Crypto ATM • Step 4\n"
        f"{MAIN_SEP}\n"
        "Did you contact your bank, financial institution, or cryptocurrency exchange?\n"
        f"{MAIN_SEP}"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes", callback_data=CRYPTO_S4_YES),
            InlineKeyboardButton("❌ No",  callback_data=CRYPTO_S4_NO),
        ],
    ])
    await target.reply_text(text, parse_mode="HTML", reply_markup=kb)


def _kb_crypto_step5(d):
    """Step 5 • Crypto Details — 4 fields, Confirm/Save + Back. All filled → Save."""
    from .keyboards import InlineKeyboardMarkup, InlineKeyboardButton
    def btn(label, key, cb):
        val = d.get(key)
        if val and str(val).strip():
            v = str(val).strip()
            display = v[:20] + ("…" if len(v) > 20 else "")
            return InlineKeyboardButton(f"✅ {display}", callback_data=cb)
        return InlineKeyboardButton(label, callback_data=cb)
    keys = ["tx1_crypto_currency", "tx1_crypto_txhash", "tx1_crypto_orig_wallet", "tx1_crypto_recip_wallet"]
    labels = ["Type of Cryptocurrency", "Transaction ID/Hash", "Originating Wallet Address", "Recipient Wallet Address"]
    cbs = [CRYPTO_S5_CUR, CRYPTO_S5_TXHASH, CRYPTO_S5_ORIG, CRYPTO_S5_RECIP]
    rows = [[btn(labels[i], keys[i], cbs[i])] for i in range(4)]
    all_filled = all(d.get(k) and str(d.get(k)).strip() for k in keys)
    rows.append([
        InlineKeyboardButton("✅ Submit" if all_filled else "✅ Confirm", callback_data=CRYPTO_S5_SAVE),
        InlineKeyboardButton("↩️ Back", callback_data=CRYPTO_S5_BACK),
    ])
    return InlineKeyboardMarkup(rows)


async def crs02_tx1_crypto_step5(target, ctx):
    """Transaction #1 Cryptocurrency/Crypto ATM Step 5 • Crypto Details"""
    ctx.user_data["state"] = None
    d = ctx.user_data
    text = (
        f"Transaction #{_tx_no(ctx)}\n"
        "Cryptocurrency/Crypto ATM\n"
        "Step 5 • Crypto Details\n"
        f"{MAIN_SEP}"
    )
    await target.reply_text(text, parse_mode="HTML", reply_markup=_kb_crypto_step5(d))


def _kb_crypto_step5_currency():
    """Step 5 sub — Type of Cryptocurrency"""
    from .keyboards import InlineKeyboardMarkup, InlineKeyboardButton
    currencies = [
        ("Bitcoin (BTC)", "CRYPTO_S5_CUR_BTC"),
        ("Ethereum (ETH)", "CRYPTO_S5_CUR_ETH"),
        ("Tether (USDT)", "CRYPTO_S5_CUR_USDT"),
        ("USDC", "CRYPTO_S5_CUR_USDC"),
        ("BNB", "CRYPTO_S5_CUR_BNB"),
        ("XRP", "CRYPTO_S5_CUR_XRP"),
    ]
    rows = [[InlineKeyboardButton(t, callback_data=c)] for t, c in currencies]
    rows.append([InlineKeyboardButton("[Othe]", callback_data="CRYPTO_S5_CUR_OTHER")])
    rows.append([InlineKeyboardButton("↩️ Back", callback_data=CRYPTO_S5_CUR_BACK)])
    return InlineKeyboardMarkup(rows)


async def crs02_tx1_crypto_step5_currency(target, ctx):
    """Step 5 • Type of Cryptocurrency"""
    ctx.user_data["state"] = None
    text = (
        f"Transaction #{_tx_no(ctx)}\n"
        "Cryptocurrency/Crypto ATM\n"
        "Step 5 • Type of Cryptocurrency\n"
        f"{MAIN_SEP}\n"
        "Type of Cryptocurrency\n"
        f"{MAIN_SEP}"
    )
    await target.reply_text(text, parse_mode="HTML", reply_markup=_kb_crypto_step5_currency())


async def crs02_tx1_crypto_step5_txhash_prompt(target, ctx):
    """Step 5 • Transaction ID/Hash — text input"""
    ctx.user_data["state"] = "CRS02_TX1_CRYPTO_TXHASH"
    text = (
        f"Transaction #{_tx_no(ctx)}\n"
        "Cryptocurrency/Crypto ATM\n"
        "Step 5 • Transaction ID/Hash\n"
        f"{MAIN_SEP}\n"
        "Transaction ID/Hash\n\n"
        "Please reply with the Transaction ID or Hash:\n\n"
        "Example:\n0xabc123...def456"
    )
    await target.reply_text(text, parse_mode="HTML", reply_markup=kb_crs_nav())


async def crs02_tx1_crypto_step5_orig_wallet_prompt(target, ctx):
    """Step 5 • Originating Wallet Address — text input"""
    ctx.user_data["state"] = "CRS02_TX1_CRYPTO_ORIG_WALLET"
    text = (
        f"Transaction #{_tx_no(ctx)}\n"
        "Cryptocurrency/Crypto ATM\n"
        "Step 5 • Originating Wallet Address\n"
        f"{MAIN_SEP}\n"
        "Originating Wallet Address\n\n"
        "Please reply with your (sender) wallet address.\n\n"
        "Example: 0x... or 1A2B3C... or T..."
    )
    await target.reply_text(text, parse_mode="HTML", reply_markup=kb_crs_nav())


async def crs02_tx1_crypto_step5_recip_wallet_prompt(target, ctx):
    """Step 5 • Recipient Wallet Address — text input"""
    ctx.user_data["state"] = "CRS02_TX1_CRYPTO_RECIP_WALLET"
    text = (
        f"Transaction #{_tx_no(ctx)}\n"
        "Cryptocurrency/Crypto ATM\n"
        "Step 5 • Recipient Wallet Address\n"
        f"{MAIN_SEP}\n"
        "Recipient Wallet Address\n\n"
        "Please reply with the recipient (suspect) wallet address.\n\n"
        "Example: 0x... or 9Z8Y7X..."
    )
    await target.reply_text(text, parse_mode="HTML", reply_markup=kb_crs_nav())


# ATM/Kiosk sequential field definitions: (data_key, short_label, field_no, prompt_body)
_CRYPTO_ATM_SEQ = [
    ("tx1_crypto_atm_name",    "ATM/Kiosk",  "Field 1", "Cryptocurrency ATM/Kiosk",
     "Which ATM/Kiosk brand or network\nwas used for this transaction?\n\nExample: Bitcoin Depot, CoinFlip,\nCoinstar, RockItCoin"),
    ("tx1_crypto_atm_address", "Address",     "Field 2", "ATM/Kiosk Address",
     "Please enter the street address\nwhere the ATM/Kiosk is located.\n\nExample: 1234 Main St"),
    ("tx1_crypto_atm_city",    "City",        "Field 3", "ATM/Kiosk City",
     "Please enter the city where\nthe ATM/Kiosk is located.\n\nExample: Los Angeles"),
    ("tx1_crypto_atm_country", "Country",     "Field 4", "ATM/Kiosk Country",
     "Please enter the country where\nthe ATM/Kiosk is located.\n\nExample: United States"),
    ("tx1_crypto_atm_state",   "State",       "Field 5", "ATM/Kiosk State",
     "Please enter the state or region\nwhere the ATM/Kiosk is located.\n\nExample: California"),
    ("tx1_crypto_atm_zip",     "Zip/Route",   "Field 6", "ATM/Kiosk Zip Code/Route",
     "Please enter the zip code or route\nfor the ATM/Kiosk location.\n\nExample: 90001"),
]

# State string → (data_key, field_index)
_CRYPTO_ATM_STATE_TO_IDX = {
    "CRS02_TX1_CRYPTO_ATM_NAME":    0,
    "CRS02_TX1_CRYPTO_ATM_ADDR":    1,
    "CRS02_TX1_CRYPTO_ATM_CITY":    2,
    "CRS02_TX1_CRYPTO_ATM_COUNTRY": 3,
    "CRS02_TX1_CRYPTO_ATM_STATE":   4,
    "CRS02_TX1_CRYPTO_ATM_ZIP":     5,
}

_CRYPTO_ATM_STATES = [
    "CRS02_TX1_CRYPTO_ATM_NAME", "CRS02_TX1_CRYPTO_ATM_ADDR",
    "CRS02_TX1_CRYPTO_ATM_CITY", "CRS02_TX1_CRYPTO_ATM_COUNTRY",
    "CRS02_TX1_CRYPTO_ATM_STATE", "CRS02_TX1_CRYPTO_ATM_ZIP",
]


def _crypto_atm_field_prompt_text(ctx, field_idx: int) -> str:
    """Build ATM/Kiosk field prompt with accumulated ✅ context."""
    d = ctx.user_data
    tx_no = _tx_no(ctx)
    data_key, short_label, field_no, title, body = _CRYPTO_ATM_SEQ[field_idx]

    # Accumulated context lines
    context_lines = []
    for i in range(field_idx):
        prev_key, prev_short, _, _, _ = _CRYPTO_ATM_SEQ[i]
        v = d.get(prev_key)
        if v and str(v).strip():
            context_lines.append(f"✅ {prev_short:<10}: {str(v).strip()}")

    context = "\n".join(context_lines)
    if context:
        context = f"\n{context}\n"

    return (
        f"Transaction #{tx_no}\n"
        f"{field_no} · {title}\n"
        f"{MAIN_SEP}\n"
        f"🏧 {title}{context}\n"
        f"{body}\n"
        f"{MAIN_SEP}"
    )


async def crs02_tx1_crypto_step6_field(target, ctx, field_idx: int):
    """Show a single ATM/Kiosk field prompt at the given index."""
    if field_idx < 0 or field_idx >= len(_CRYPTO_ATM_SEQ):
        return
    state_str = _CRYPTO_ATM_STATES[field_idx]
    ctx.user_data["state"] = state_str
    text = _crypto_atm_field_prompt_text(ctx, field_idx)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭ Skip", callback_data="CRYPTO_S6_SKIP"),
        InlineKeyboardButton("↩️ Back", callback_data="CRYPTO_S6_FIELD_BACK"),
    ]])
    await target.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def crs02_tx1_crypto_step6(target, ctx):
    """Transaction #N Crypto Step 6 • ATM/Kiosk — start from first unfilled field."""
    d = ctx.user_data
    # Find first unfilled field
    for idx, (data_key, *_) in enumerate(_CRYPTO_ATM_SEQ):
        if not (d.get(data_key) and str(d.get(data_key)).strip()):
            await crs02_tx1_crypto_step6_field(target, ctx, idx)
            return
    # All filled → go to Step 7
    from bot_modules.crs import crs02_tx1_crypto_step7
    await crs02_tx1_crypto_step7(target, ctx)


async def crs02_tx1_crypto_step7(target, ctx):
    """Transaction #1 Cryptocurrency/Crypto ATM Step 7 • Transaction Summary"""
    ctx.user_data["state"] = None
    d = ctx.user_data
    amount = d.get("tx1_amount") or d.get("tx1_crypto_amount") or "—"
    date = d.get("tx1_crypto_date") or "—"
    bank_contacted = "✅ Yes" if d.get("tx1_crypto_bank_contacted") is True else ("❌ No" if d.get("tx1_crypto_bank_contacted") is False else "—")
    sent_lost_val = d.get("tx1_sent_lost")
    if sent_lost_val is True:
        sent_lost = "✅ Yes"
    elif sent_lost_val is False:
        sent_lost = "❌ No"
    else:
        sent_lost = "—"
    currency = d.get("tx1_crypto_currency") or "—"
    txhash = (d.get("tx1_crypto_txhash") or "—")[:40] + ("…" if len(d.get("tx1_crypto_txhash") or "") > 40 else "")
    orig_w = (d.get("tx1_crypto_orig_wallet") or "—")[:20] + ("…" if len(d.get("tx1_crypto_orig_wallet") or "") > 20 else "")
    recip_w = (d.get("tx1_crypto_recip_wallet") or "—")[:20] + ("…" if len(d.get("tx1_crypto_recip_wallet") or "") > 20 else "")
    atm_name = d.get("tx1_crypto_atm_name") or "—"
    atm_addr = d.get("tx1_crypto_atm_address") or "—"
    atm_city = d.get("tx1_crypto_atm_city") or "—"
    atm_country = d.get("tx1_crypto_atm_country") or "—"
    atm_state = d.get("tx1_crypto_atm_state") or "—"
    atm_zip = d.get("tx1_crypto_atm_zip") or "—"
    try:
        amt_fmt = f"${float(amount):,.2f}" if amount != "—" else "—"
    except Exception:
        amt_fmt = amount
    text = (
        "IC3 | Internet Crime Complaint Center\n"
        "Financial Transaction(s) CRS-02#1\n"
        f"Transaction #{_tx_no(ctx)} - Cryptocurrency/Crypto ATM\n"
        "Step 7 • Transaction Summary\n"
        f"{MAIN_SEP}\n"
        "Transaction Type  : Cryptocurrency/Crypto ATM\n"
        f"*Money Sent/Lost  : {sent_lost}\n"
        f"*Amount           : {amt_fmt} USD\n"
        f"*Date             : {date}\n"
        f"Bank Contacted    : {bank_contacted}\n"
        f"{MAIN_SEP}\n"
        "Crypto Details\n"
        f"Type              : {currency}\n"
        f"Transaction Hash  : {txhash}\n"
        f"Originating Wallet: {orig_w}\n"
        f"Recipient Wallet  : {recip_w}\n"
        f"{MAIN_SEP}\n"
        "ATM/Kiosk\n"
        f"ATM/Kiosk Name    : {atm_name}\n"
        f"ATM/Kiosk Address : {atm_addr}\n"
        f"ATM/Kiosk City    : {atm_city}\n"
        f"ATM/Kiosk Country : {atm_country}\n"
        f"ATM/Kiosk State   : {atm_state}\n"
        f"ATM/Kiosk Zip     : {atm_zip}\n"
        f"{MAIN_SEP}"
    )
    from .keyboards import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Edit", callback_data=CRYPTO_S7_EDIT),
            InlineKeyboardButton("✅ Submit", callback_data=CRYPTO_S7_SAVE),
        ],
    ])
    await target.reply_text(text, parse_mode="HTML", reply_markup=kb)


"""
旧版 CRS-02A/CRS-02B（Bank/Wire vs Crypto）分支已移除。
当前 CRS-02 仅保留新的 Financial Transaction(s) 结构。
"""


# ── CRS-02 原线性流程（保留供兼容）──────────────────────────────

async def crs02_txid(target, ctx):
    ctx.user_data["state"] = S_TXID
    await target.reply_text(
        "<b>CRS-02 · STEP 1 of 5 — BLOCKCHAIN DATA</b>\n"
        + "━"*28 + "\n\n"
        "Please provide the <b>Transaction Hash (TXID)</b>.\n\n"
        "• 64-character alphanumeric string\n"
        "• Ensure TXID matches the specific asset lost\n"
        "• Example: <code>a1b2c3d4...</code> (ERC-20 / TRC-20 / BTC)\n\n"
        "_You may also upload a screenshot instead._\n\n"
        "<i>If unavailable, type:</i> <code>None</code>",
        parse_mode="HTML", reply_markup=kb_crs_nav(),
    )


async def crs02_asset(target, ctx):
    ctx.user_data["state"] = S_ASSET
    await target.reply_text(
        "<b>CRS-02 · STEP 2 of 5 — ASSET TYPE & AMOUNT</b>\n"
        + "━"*28 + "\n\n"
        "Please specify the <b>total amount lost</b> and <b>asset type</b>.\n\n"
        "• Format: <code>[amount] [asset]</code>\n"
        "• Supported: <code>USDT · BTC · ETH · BNB · TRX · USDC · SOL</code>\n\n"
        "<b>Examples:</b>\n"
        "<code>5000 USDT</code>  |  <code>1.2 BTC</code>  |  <code>0.5 ETH</code>\n\n"
        "_Ensure this matches the TXID provided above._",
        parse_mode="HTML", reply_markup=kb_crs_nav(),
    )


async def crs02_incident_time(target, ctx):
    ctx.user_data["state"] = S_TIME
    await target.reply_text(
        "<b>CRS-02 · STEP 3 of 5 — INCIDENT DATE & TIME</b>\n"
        + "━"*28 + "\n\n"
        "Please provide the <b>date and time</b> when the fraudulent\n"
        "transaction occurred.\n\n"
        "• Exact date preferred: <code>2026-01-15</code>\n"
        "• Approximate: <code>Mid-January 2026</code>\n"
        "• Date + Time: <code>2026-01-15 14:30 UTC</code>\n\n"
        "_This is critical for law enforcement timeline analysis._",
        parse_mode="HTML", reply_markup=kb_crs_nav(),
    )


async def crs02_victim_wallet(target, ctx):
    ctx.user_data["state"] = S_VICTIM_WALLET
    await target.reply_text(
        "<b>CRS-02 · STEP 4 of 5 — VICTIM WALLET ADDRESS</b>\n"
        + "━"*28 + "\n\n"
        "Please enter <b>your own wallet address</b>\n"
        "(the sending address used in the transaction).\n\n"
        "• ERC-20/BSC: <code>0x...</code> (42 chars)\n"
        "• TRC-20: <code>T...</code> (34 chars)\n"
        "• BTC: <code>1... / 3... / bc1...</code>\n\n"
        "<i>If unknown, type:</i> <code>Unknown</code>",
        parse_mode="HTML", reply_markup=kb_crs_nav(),
    )


async def crs02_suspect_wallet(target, ctx):
    ctx.user_data["state"] = S_SUSPECT_WALLET
    await target.reply_text(
        "<b>CRS-02 · STEP 5 of 5 — SUSPECT WALLET ADDRESS</b>\n"
        + "━"*28 + "\n\n"
        "<b>Critical field for blockchain trace analysis.</b>\n\n"
        "Please enter the <b>suspect's receiving wallet address</b>:\n\n"
        "• ERC-20/BSC: <code>0x...</code> (42 chars)\n"
        "• TRC-20: <code>T...</code> (34 chars)\n"
        "• BTC: <code>1... / bc1...</code>\n\n"
        "<i>If unknown, type:</i> <code>Unknown</code>",
        parse_mode="HTML", reply_markup=kb_crs_nav(),
    )


# ─── CRS-02A: Bank / Wire Transfer (Legacy Compatibility) ──────────────────

async def crs02a_bank_intro(target, ctx):
    """CRS-02A 主菜单：Victim / Subject / Financial 三栏入口。"""
    ctx.user_data["state"] = None
    d = ctx.user_data
    vic_bank = d.get("crs02a_vic_bank_name", "—")
    vic_acct = d.get("crs02a_vic_account_no", "—")
    sub_name = d.get("crs02a_sub_name", "—")
    com_bank = d.get("crs02a_com_bank_name", "—")
    com_acct = d.get("crs02a_com_account_no", "—")
    fin_amt  = d.get("fin_amount", "—")
    fin_cur  = d.get("fin_currency", "—")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏦 Victim Info",  callback_data="CRS02A_VICTIM"),
         InlineKeyboardButton("👤 Subject Info", callback_data="CRS02A_SUBJECT")],
        [InlineKeyboardButton("💵 Financial",    callback_data="CRS02A_FINANCIAL")],
        [InlineKeyboardButton("✅ Done",          callback_data="CRS02A_DONE")],
        [InlineKeyboardButton("⬅️ Back",          callback_data="CRS_MAIN")],
    ])
    await target.reply_text(
        "IC3 | Internet Crime Complaint Center\n"
        "<b>SECTION CRS-02A</b>\n"
        "<b>BANK / WIRE TRANSFER</b>\n"
        f"{MAIN_SEP}\n\n"
        f"Victim Bank: <code>{vic_bank}</code>  |  Acct: <code>{vic_acct}</code>\n"
        f"Subject: <code>{sub_name}</code>\n"
        f"Subject Bank: <code>{com_bank}</code>  |  Acct: <code>{com_acct}</code>\n"
        f"Amount: <code>{fin_amt} {fin_cur}</code>\n\n"
        "Select a section to complete:",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def crs02a_victim_menu(target, ctx):
    """CRS-02A 受害人银行信息菜单。"""
    ctx.user_data["state"] = None
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏦 Bank Name",   callback_data="CRS02A_VIC_BANK"),
         InlineKeyboardButton("💳 Account No.", callback_data="CRS02A_VIC_ACCT")],
        [InlineKeyboardButton("⬅️ Back",         callback_data="CRS02A_MENU")],
    ])
    await target.reply_text(
        "<b>CRS-02A · VICTIM BANK INFO</b>\n"
        f"{MAIN_SEP}\n\n"
        "Provide the <b>victim's</b> bank details.",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def crs02a_subject_menu(target, ctx):
    """CRS-02A 嫌疑人信息菜单。"""
    ctx.user_data["state"] = None
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Subject Name", callback_data="CRS02A_SUB_NAME")],
        [InlineKeyboardButton("🏦 Bank Name",    callback_data="CRS02A_COM_BANK"),
         InlineKeyboardButton("💳 Account No.",  callback_data="CRS02A_COM_ACCT")],
        [InlineKeyboardButton("⬅️ Back",          callback_data="CRS02A_MENU")],
    ])
    await target.reply_text(
        "<b>CRS-02A · SUBJECT INFO</b>\n"
        f"{MAIN_SEP}\n\n"
        "Provide the <b>subject's</b> (suspected fraudster's) details.",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def crs02a_fin_intro(target, ctx):
    """CRS-02A 财务信息菜单（金额/币种/日期/方式）。"""
    ctx.user_data["state"] = None
    d = ctx.user_data
    amt = d.get("fin_amount", "—")
    cur = d.get("fin_currency", "—")
    dt  = d.get("fin_date", "—")
    mtd = d.get("fin_method", "—")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💵 Amount",   callback_data="FIN_AMOUNT"),
         InlineKeyboardButton("🪙 Currency", callback_data="FIN_CURRENCY")],
        [InlineKeyboardButton("📅 Date",     callback_data="FIN_DATE"),
         InlineKeyboardButton("🔀 Method",   callback_data="FIN_METHOD")],
        [InlineKeyboardButton("✅ Submit",      callback_data="FIN_DONE")],
        [InlineKeyboardButton("⬅️ Back",      callback_data="FIN_BACK")],
    ])
    await target.reply_text(
        "<b>CRS-02A · FINANCIAL DETAILS</b>\n"
        f"{MAIN_SEP}\n\n"
        f"Amount  : <code>{amt}</code>\n"
        f"Currency: <code>{cur}</code>\n"
        f"Date    : <code>{dt}</code>\n"
        f"Method  : <code>{mtd}</code>\n\n"
        "Select a field to enter or update:",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def crs02a_fin_amount_prompt(target, ctx):
    """CRS-02A 提示输入总金额。"""
    ctx.user_data["state"] = "CRS02A_FIN_AMOUNT"
    await target.reply_text(
        "<b>CRS-02A · Total Amount Lost</b>\n"
        f"{MAIN_SEP}\n\n"
        "Enter the total amount lost in this transaction.\n\n"
        "Example: <code>12500.00</code>",
        parse_mode="HTML",
        reply_markup=kb_crs_nav(),
    )


async def crs02a_fin_currency_prompt(target, ctx):
    """CRS-02A 选择币种。"""
    ctx.user_data["state"] = None
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇺🇸 USD",  callback_data="FIN_CUR_USD"),
         InlineKeyboardButton("💲 USDT", callback_data="FIN_CUR_USDT")],
        [InlineKeyboardButton("₿ BTC",   callback_data="FIN_CUR_BTC"),
         InlineKeyboardButton("Ξ ETH",   callback_data="FIN_CUR_ETH")],
        [InlineKeyboardButton("🔢 Other", callback_data="FIN_CUR_OTHER")],
    ])
    await target.reply_text(
        "<b>CRS-02A · Currency Type</b>\n"
        f"{MAIN_SEP}\n\n"
        "Select the currency of the lost funds:",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def crs02a_fin_date_prompt(target, ctx):
    """CRS-02A 提示输入交易日期。"""
    ctx.user_data["state"] = "CRS02A_FIN_DATE"
    await target.reply_text(
        "<b>CRS-02A · Transaction Date</b>\n"
        f"{MAIN_SEP}\n\n"
        "Enter the date of the transaction.\n\n"
        "Format: <code>MM/DD/YYYY</code>  e.g. <code>03/15/2026</code>",
        parse_mode="HTML",
        reply_markup=kb_crs_nav(),
    )


async def crs02a_fin_method_prompt(target, ctx):
    """CRS-02A 选择转账方式。"""
    ctx.user_data["state"] = None
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏦 Wire Transfer",    callback_data="FIN_MTD_WIRE"),
         InlineKeyboardButton("🔁 ACH / Bank",       callback_data="FIN_MTD_ACH")],
        [InlineKeyboardButton("🪙 Cryptocurrency",   callback_data="FIN_MTD_CRYPTO"),
         InlineKeyboardButton("💵 Cash / MO",        callback_data="FIN_MTD_CASH")],
        [InlineKeyboardButton("🔢 Other",             callback_data="FIN_MTD_OTHER")],
    ])
    await target.reply_text(
        "<b>CRS-02A · Transfer Method</b>\n"
        f"{MAIN_SEP}\n\n"
        "Select the method used for the transaction:",
        parse_mode="HTML",
        reply_markup=kb,
    )


# ─── CRS-02B: Cryptocurrency Transaction ──────────────────────────────────

def kb_crs02_type(bank_done: bool = False, crypto_done: bool = False) -> InlineKeyboardMarkup:
    """CRS-02 类型选择键盘：银行汇款(02A) vs 加密货币(02B)。"""
    bank_label   = "✅ Bank / Wire Transfer"   if bank_done   else "Bank / Wire Transfer"
    crypto_label = "✅ Cryptocurrency / ATM"   if crypto_done else "Cryptocurrency / ATM"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(bank_label,   callback_data="CRS-02A")],
        [InlineKeyboardButton(crypto_label, callback_data="CRS-02B")],
        [InlineKeyboardButton("⬅️ Back",    callback_data="CRS_MAIN")],
    ])


async def crs02b_intro(target, ctx):
    """CRS-02B 主菜单：显示交易/钱包/财务各项填写状态。"""
    ctx.user_data["state"] = None
    d = ctx.user_data

    def _tick(key):
        v = d.get(key)
        return "✅" if (v and str(v).strip()) else "▫️"

    tx_ok  = all(d.get(k) for k in ("txid", "crs02b_network", "time"))
    wlt_ok = d.get("victim_wallet") and d.get("wallet")
    fin_ok = (d.get("crypto_currency") or d.get("coin")) and (d.get("crypto_amount") or d.get("amount"))

    tx_icon  = "✅" if tx_ok else "▫️"
    wlt_icon = "✅" if wlt_ok else "▫️"
    fin_icon = "✅" if fin_ok else "▫️"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{tx_icon}  Transaction Details",  callback_data="CRYPTO_TX"),
         InlineKeyboardButton(f"{wlt_icon}  Wallet Info",         callback_data="CRYPTO_WALLET")],
        [InlineKeyboardButton(f"{_tick('crypto_currency')}  Currency",  callback_data="CRYPTO_FIN_CURRENCY"),
         InlineKeyboardButton(f"{_tick('crypto_amount')}  Amount",      callback_data="CRYPTO_FIN_AMOUNT")],
        [InlineKeyboardButton(f"{_tick('crypto_date')}  Date",          callback_data="CRYPTO_FIN_DATE"),
         InlineKeyboardButton(f"{_tick('crypto_method')}  Method",      callback_data="CRYPTO_FIN_METHOD")],
        [InlineKeyboardButton("✅ Done",  callback_data="CRS02B_DONE")],
        [InlineKeyboardButton("⬅️ Back",  callback_data="CRS02B_BACK")],
    ])
    await target.reply_text(
        "IC3 | Internet Crime Complaint Center\n"
        "<b>SECTION CRS-02B</b>\n"
        "<b>CRYPTOCURRENCY TRANSACTION</b>\n"
        f"{MAIN_SEP}\n\n"
        f"{tx_icon}  Transaction Details\n"
        f"  TXID    : <code>{d.get('txid') or '—'}</code>\n"
        f"  Network : {d.get('crs02b_network') or '—'}\n"
        f"  Time    : {d.get('time') or '—'}\n\n"
        f"{wlt_icon}  Wallet Info\n"
        f"  Victim  : <code>{d.get('victim_wallet') or '—'}</code>\n"
        f"  Suspect : <code>{d.get('wallet') or '—'}</code>\n\n"
        f"{fin_icon}  Financial\n"
        f"  Amount  : {d.get('crypto_amount') or d.get('amount') or '—'}"
        f"  {d.get('crypto_currency') or d.get('coin') or ''}\n"
        f"  Date    : {d.get('crypto_date') or '—'}\n"
        f"  Method  : {d.get('crypto_method') or '—'}\n\n"
        "Select a section to complete:",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def crs02b_tx_menu(target, ctx):
    """CRS-02B 交易详情子菜单（TXID / Network / Time）。"""
    ctx.user_data["state"] = None
    d = ctx.user_data

    def _btn(label, key, cb):
        v = d.get(key)
        if v and str(v).strip():
            display = str(v).strip()[:20] + ("…" if len(str(v).strip()) > 20 else "")
            return InlineKeyboardButton(f"✅ {display}", callback_data=cb)
        return InlineKeyboardButton(f"[ {label} ]", callback_data=cb)

    kb = InlineKeyboardMarkup([
        [_btn("Transaction Hash", "txid",           "CRS02B_TXID")],
        [_btn("Blockchain Network", "crs02b_network","CRS02B_NET")],
        [_btn("Transaction Time",   "time",          "CRS02B_TIME")],
        [InlineKeyboardButton("⬅️ Back", callback_data="CRS02B_MENU")],
    ])
    await target.reply_text(
        "<b>CRS-02B · Transaction Details</b>\n"
        f"{MAIN_SEP}\n\n"
        "Provide the on-chain transaction information.\n\n"
        f"  Hash    : <code>{d.get('txid') or '—'}</code>\n"
        f"  Network : {d.get('crs02b_network') or '—'}\n"
        f"  Time    : {d.get('time') or '—'}",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def crs02b_wallet_menu(target, ctx):
    """CRS-02B 钱包信息子菜单（Victim / Suspect）。"""
    ctx.user_data["state"] = None
    d = ctx.user_data

    def _btn(label, key, cb):
        v = d.get(key)
        if v and str(v).strip():
            display = str(v).strip()[:20] + ("…" if len(str(v).strip()) > 20 else "")
            return InlineKeyboardButton(f"✅ {display}", callback_data=cb)
        return InlineKeyboardButton(f"[ {label} ]", callback_data=cb)

    kb = InlineKeyboardMarkup([
        [_btn("Victim Wallet",  "victim_wallet", "CRS02B_VW")],
        [_btn("Suspect Wallet", "wallet",         "CRS02B_SW")],
        [InlineKeyboardButton("⬅️ Back", callback_data="CRS02B_MENU")],
    ])
    await target.reply_text(
        "<b>CRS-02B · Wallet Information</b>\n"
        f"{MAIN_SEP}\n\n"
        f"Victim  : <code>{d.get('victim_wallet') or '—'}</code>\n"
        f"Suspect : <code>{d.get('wallet') or '—'}</code>",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def crs02b_txid_prompt(target, ctx):
    """CRS-02B 提示输入交易哈希。"""
    ctx.user_data["state"] = "CRS02B_TXID"
    await target.reply_text(
        "<b>CRS-02B · Transaction Hash</b>\n"
        f"{MAIN_SEP}\n\n"
        "Please enter the <b>on-chain transaction hash</b> (TxID).\n\n"
        "Example:\n"
        "<code>a1b2c3d4e5f6...0123456789abcdef</code>\n\n"
        "Type <code>Unknown</code> if unavailable.",
        parse_mode="HTML",
        reply_markup=kb_crs_nav(),
    )


async def crs02b_network_prompt(target, ctx):
    """CRS-02B 选择区块链网络。"""
    ctx.user_data["state"] = None
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Ethereum (ETH)",  callback_data="NET|Ethereum"),
         InlineKeyboardButton("Bitcoin (BTC)",   callback_data="NET|Bitcoin")],
        [InlineKeyboardButton("BSC (BNB)",       callback_data="NET|BSC"),
         InlineKeyboardButton("TRON (TRX)",      callback_data="NET|TRON")],
        [InlineKeyboardButton("Solana (SOL)",    callback_data="NET|Solana"),
         InlineKeyboardButton("Polygon (MATIC)", callback_data="NET|Polygon")],
        [InlineKeyboardButton("Other",           callback_data="NET|Other")],
        [InlineKeyboardButton("⬅️ Back",          callback_data="CRS02B_MENU")],
    ])
    await target.reply_text(
        "🌐 <b>CRS-02B · Blockchain Network</b>\n"
        f"{MAIN_SEP}\n\n"
        "Select the blockchain network used for this transaction:",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def crs02b_time_prompt(target, ctx):
    """CRS-02B 提示输入交易时间。"""
    ctx.user_data["state"] = "CRS02B_TIME"
    await target.reply_text(
        "🕐 <b>CRS-02B · Transaction Time</b>\n"
        f"{MAIN_SEP}\n\n"
        "Please enter the <b>date and time</b> of the transaction.\n\n"
        "Format: <code>MM/DD/YYYY HH:MM</code>\n"
        "Example: <code>3/17/2025 14:30</code>\n\n"
        "Type <code>Unknown</code> if unavailable.",
        parse_mode="HTML",
        reply_markup=kb_crs_nav(),
    )


async def crs02b_victim_wallet_prompt(target, ctx):
    """CRS-02B 提示输入受害人钱包地址。"""
    ctx.user_data["state"] = "CRS02B_VW"
    await target.reply_text(
        "<b>CRS-02B · Victim Wallet Address</b>\n"
        f"{MAIN_SEP}\n\n"
        "Please enter the <b>victim's sending wallet address</b>:\n\n"
        "• ERC-20/BSC : <code>0x...</code> (42 chars)\n"
        "• TRC-20     : <code>T...</code>  (34 chars)\n"
        "• BTC        : <code>1... / bc1...</code>\n\n"
        "Type <code>Unknown</code> if unavailable.",
        parse_mode="HTML",
        reply_markup=kb_crs_nav(),
    )


async def crs02b_suspect_wallet_prompt(target, ctx):
    """CRS-02B 提示输入嫌疑人钱包地址。"""
    ctx.user_data["state"] = "CRS02B_SW"
    await target.reply_text(
        "<b>CRS-02B · Suspect Wallet Address</b>\n"
        f"{MAIN_SEP}\n\n"
        "Please enter the <b>suspect's receiving wallet address</b>:\n\n"
        "• ERC-20/BSC : <code>0x...</code> (42 chars)\n"
        "• TRC-20     : <code>T...</code>  (34 chars)\n"
        "• BTC        : <code>1... / bc1...</code>\n\n"
        "Type <code>Unknown</code> if unavailable.",
        parse_mode="HTML",
        reply_markup=kb_crs_nav(),
    )


async def crs02b_fin_amount_prompt(target, ctx):
    """CRS-02B 提示输入加密货币损失金额。"""
    ctx.user_data["state"] = "CRYPTO_FIN_AMOUNT"
    cur = ctx.user_data.get("crypto_currency") or ctx.user_data.get("coin") or "USD"
    await target.reply_text(
        "<b>CRS-02B · Amount Lost</b>\n"
        f"{MAIN_SEP}\n\n"
        f"Currency selected: <b>{cur}</b>\n\n"
        "Please enter the total value lost.\n"
        "Example: <code>2500.00</code>\n\n"
        "Type <code>Unknown</code> if unsure.",
        parse_mode="HTML",
        reply_markup=kb_crs_nav(),
    )


async def crs02b_fin_currency_prompt(target, ctx):
    """CRS-02B 选择加密货币类型。"""
    ctx.user_data["state"] = None
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💲 USDT", callback_data="CFIN_CUR_USDT"),
         InlineKeyboardButton("₿ BTC",  callback_data="CFIN_CUR_BTC")],
        [InlineKeyboardButton("Ξ ETH",  callback_data="CFIN_CUR_ETH"),
         InlineKeyboardButton("🇺🇸 USD", callback_data="CFIN_CUR_USD")],
        [InlineKeyboardButton("🔢 Other", callback_data="CFIN_CUR_OTHER")],
        [InlineKeyboardButton("⬅️ Back",  callback_data="CRS02B_MENU")],
    ])
    await target.reply_text(
        "<b>CRS-02B · Currency Type</b>\n"
        f"{MAIN_SEP}\n\n"
        "Select the cryptocurrency involved:",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def crs02b_fin_date_prompt(target, ctx):
    """CRS-02B 提示输入交易日期。"""
    ctx.user_data["state"] = "CRYPTO_FIN_DATE"
    await target.reply_text(
        "<b>CRS-02B · Transaction Date</b>\n"
        f"{MAIN_SEP}\n\n"
        "Please enter the <b>date of the transaction</b>.\n\n"
        "Format: <code>MM/DD/YYYY</code>\n"
        "Example: <code>3/17/2025</code>",
        parse_mode="HTML",
        reply_markup=kb_crs_nav(),
    )


async def crs02b_fin_method_prompt(target, ctx):
    """CRS-02B 选择转账方式。"""
    ctx.user_data["state"] = None
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🪙 Cryptocurrency",   callback_data="CFIN_MTD_CRYPTO"),
         InlineKeyboardButton("🏦 Wire Transfer",    callback_data="CFIN_MTD_WIRE")],
        [InlineKeyboardButton("🔁 ACH / Bank",       callback_data="CFIN_MTD_ACH"),
         InlineKeyboardButton("💵 Cash / MO",        callback_data="CFIN_MTD_CASH")],
        [InlineKeyboardButton("🔢 Other",             callback_data="CFIN_MTD_OTHER")],
        [InlineKeyboardButton("⬅️ Back",              callback_data="CRS02B_MENU")],
    ])
    await target.reply_text(
        "<b>CRS-02B · Transfer Method</b>\n"
        f"{MAIN_SEP}\n\n"
        "Select the method used to send the funds:",
        parse_mode="HTML",
        reply_markup=kb,
    )


# ─── CRS-03: Platform & Suspect Info ──────────────────

async def crs03_platform(target, ctx):
    """CRS-03 入口：展示 4 个子按钮菜单。"""
    ctx.user_data["state"] = None
    await target.reply_text(
        "IC3 | Internet Crime Complaint Center\n"
        + "<b>SECTION CRS-03</b>\n"
        + "<b>SUBJECT IDENTIFICATION</b>\n"
        + f"{MAIN_SEP}\n"
        + "Processed under 18 U.S.C. § 1343.\n"
        + f"{MAIN_SEP}\n\n",
        parse_mode="HTML",
        reply_markup=kb_crs03_menu(ctx.user_data),
    )


async def crs03_contact_prompt(target, ctx):
    """CRS-03 平台/联系方式。"""
    ctx.user_data["state"] = S_PLATFORM
    await target.reply_text(
        "<b>CRS-03-1 · SUBJECT PLATFORM</b>\n"
        + f"{MAIN_SEP}\n\n"
        + "Provide the platform or application\n"
        + "used by the subject to contact you.\n\n"
        + "  Example:\n"
        + "  Telegram : <code>@faketrader</code>\n"
        + "  URL       : <code>abc-invest.com</code>\n\n"
        + "Type <code>Unknown</code> if unavailable.",
        parse_mode="HTML",
        reply_markup=kb_crs_nav(),
    )


async def crs03_profile_prompt(target, ctx):
    """CRS-03 嫌疑人资料/Profile URL。"""
    ctx.user_data["state"] = S_SCAMMER_ID
    await target.reply_text(
        "<b>CRS-03-2 · Profile URL</b>\n"
        + f"{MAIN_SEP}\n\n"
        + "Provide the subject's profile link\n"
        + "or application user ID.\n\n"
        + "  • Social media profile URL\n"
        + "  • Trading platform user ID\n"
        + "  • App registration number\n\n"
        + "Example:\n"
        + "  URL : <code>https://t.me/faketrader</code>\n"
        + "  ID  : <code>USR-481023</code>\n\n"
        + "Type <code>Unknown</code> if unavailable.",
        parse_mode="HTML",
        reply_markup=kb_crs_nav(),
    )


async def crs03_crime_type_prompt(target, ctx):
    """CRS-03 犯罪类型选择。"""
    ctx.user_data["state"] = "CRS03_CRIME"
    await target.reply_text(
        "<b>CRS-03-3 · Crime Type</b>\n"
        + f"{MAIN_SEP}\n\n"
        + "Select the primary crime type\n"
        + "involved in this incident.\n\n"
        + f"{MAIN_SEP}\n"
        + f"{FEDERAL_INDEX_LINE}\n"
        + f"{MAIN_SEP}",
        parse_mode="HTML",
        reply_markup=kb_crs03_crime(),
    )


async def crs03_scammer_id(target, ctx):
    ctx.user_data["state"] = S_SCAMMER_ID
    await target.reply_text(
        "<b>[SECTION CRS-03: SUBJECT IDENTIFICATION]</b>\n"
        "CRS-03 · STEP 2 of 2 — SUBJECT IDENTITY\n"
        + "━"*28 + "\n\n"
        "Please provide the <b>subject's contact identity</b>:\n\n"
        "• Telegram handle: <code>@username</code>\n"
        "• Phone number: <code>+1-xxx-xxx-xxxx</code>\n"
        "• Email: <code>name@domain.com</code>\n"
        "• App user ID or profile URL (e.g. <code>https://platform.com/profile/12345</code>)\n\n"
        "<i>If unknown, type:</i> <code>Unknown</code>",
        parse_mode="HTML", reply_markup=kb_crs_nav(),
    )


# ─── CRS-04 · Other Information ──────────────────────────────────────────────

async def crs04_other_menu(target, ctx, fallback_chat_id: Optional[int] = None):
    """CRS-04 Other Information menu。callback 无 q.message 时用 fallback_chat_id 发送。"""
    ctx.user_data["state"] = None
    from bot_modules.keyboards import kb_crs04_other
    text = (
        "IC3 | Internet Crime Complaint Center\n"
        "Other Information CRS-04\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    kb = kb_crs04_other(ctx.user_data)
    if target is not None:
        await target.reply_text(text, parse_mode="HTML", reply_markup=kb)
    elif fallback_chat_id is not None:
        await ctx.bot.send_message(
            chat_id=fallback_chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=kb,
        )
    else:
        raise ValueError("crs04_other_menu: need target or fallback_chat_id")


def crs04_witnesses_section_done(d: dict) -> bool:
    """Witnesses 区块是否已处理（跳过或至少一名证人）。"""
    if d.get("crs04_witnesses_skipped"):
        return True
    lst = d.get("crs04_witnesses_list") or []
    return bool(lst)


async def crs04_advance_after_narrative_saved(target, ctx):
    """保存 Incident Narrative 后：自上而下进入下一未完成区块（Prior → Witnesses → 主菜单）。"""
    d = ctx.user_data
    pr = d.get("prior_reports_flag")
    if pr not in ("Yes", "No"):
        await crs04_prior_reports_prompt(target, ctx)
    elif not crs04_witnesses_section_done(d):
        await crs04_witnesses_hub_menu(target, ctx)
    else:
        await crs04_other_menu(target, ctx)


def _truncate_crs04_summary_html(html: str, max_len: int) -> str:
    if len(html) <= max_len:
        return html
    cut = html[:max_len]
    idx = cut.rfind("\n")
    if idx > max_len // 2:
        cut = cut[:idx]
    return cut + "\n\n<i>(Summary truncated)</i>"


async def crs04_deliver_other_save_from_callback(update, ctx):
    """
    CRS-04 主菜单「Save」：先 answer callback，再发送汇总（防 HTML 过长 / 解析失败 / message 已删除）。
    """
    from telegram.error import BadRequest

    q = update.callback_query
    if not q:
        return
    await q.answer()
    html = format_crs04_other_summary_html(ctx.user_data)
    html = _truncate_crs04_summary_html(html, 4000)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✏️ Edit", callback_data="CRS04_OTHER_REVISE"),
        InlineKeyboardButton("✅ Submit", callback_data="CRS04_SUMMARY_SAVE"),
    ]])

    async def _send_pair(chat_id=None, msg=None):
        try:
            if msg is not None:
                await msg.reply_text(html, parse_mode="HTML", reply_markup=kb)
            else:
                await ctx.bot.send_message(chat_id=chat_id, text=html,
                                           parse_mode="HTML", reply_markup=kb)
        except BadRequest as e:
            logger.warning("CRS-04 Save HTML failed: %s", e)
            plain = _html_unescape(re.sub(r"<[^>]+>", "", html))
            if len(plain) > 4096:
                plain = plain[:4090] + "…"
            if msg is not None:
                await msg.reply_text(plain, reply_markup=kb)
            else:
                await ctx.bot.send_message(chat_id=chat_id, text=plain, reply_markup=kb)

    if q.message:
        await _send_pair(msg=q.message)
    else:
        cid = None
        if update.effective_chat:
            cid = update.effective_chat.id
        elif q.from_user:
            cid = q.from_user.id
        if cid:
            await _send_pair(chat_id=cid, msg=None)


async def crs04_narrative_prompt(target, ctx):
    """CRS-04 Incident Narrative (moved from CRS-03)."""
    ctx.user_data["state"] = "CRS04_NARRATIVE_TEXT"
    await target.reply_text(
        "IC3 | Internet Crime Complaint Center\n"
        "Other Information CRS-04\n"
        "<b>Incident Narrative</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Incident Narrative\n\n"
        "Describe what happened in your own words.\n"
        "Provide any information that may assist law\n"
        "enforcement in understanding what happened.\n\n"
        "Please reply with your description:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("↩️ Back", callback_data="CRS04_NARRATIVE_BACK"),
        ]]),
    )


async def crs04_prior_reports_prompt(target, ctx):
    """CRS-04 Prior Reports to Agencies — Yes/No."""
    ctx.user_data["state"] = None
    await target.reply_text(
        "IC3 | Internet Crime Complaint Center\n"
        "Other Information CRS-04\n"
        "<b>Prior Reports to Agencies</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Prior Reports to Agencies\n\n"
        "If you have reported this incident\n"
        "to other law enforcement or government\n"
        "agencies, please provide the following:\n\n"
        "- Agency Name\n"
        "- Phone Number\n"
        "- Email Address\n"
        "- Date Reported\n"
        "- Report Number\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Yes", callback_data="CRS04_PRIOR_YES"),
            InlineKeyboardButton("❌ No",  callback_data="CRS04_PRIOR_NO"),
        ]]),
    )


async def crs04_witnesses_prompt(target, ctx):
    """CRS-04 Witnesses & Others — 入口（hub）。"""
    await crs04_witnesses_hub_menu(target, ctx)


# ─── CRS-04: Review & Legal Attestation ───────────────

def _review_field_filled(v) -> bool:
    """Review/PDF：与未填写占位符等价的字段不展示。"""
    if v is None:
        return False
    s = str(v).strip()
    if not s or s in ("—", "-", "–", "―"):
        return False
    sl = s.lower()
    if sl in ("unknown", "n/a", "na", "none", "null", "not provided", "➖not provided"):
        return False
    return True


# ─── CRS-04: Prior Reports to Agencies (structured fields) ─────────────────────
CRS04_PRIOR_SEP = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

CRS04_PRIOR_F_AGENCY = "CRS04_PRIOR_F_AGENCY"
CRS04_PRIOR_F_PHONE = "CRS04_PRIOR_F_PHONE"
CRS04_PRIOR_F_EMAIL = "CRS04_PRIOR_F_EMAIL"
CRS04_PRIOR_F_DATE = "CRS04_PRIOR_F_DATE"
CRS04_PRIOR_F_REPORT = "CRS04_PRIOR_F_REPORT"
CRS04_PRIOR_CONFIRM = "CRS04_PRIOR_CONFIRM"
CRS04_PRIOR_SAVE = "CRS04_PRIOR_SAVE"
CRS04_PRIOR_FIELDS_BACK = "CRS04_PRIOR_FIELDS_BACK"
CRS04_PRIOR_FIELD_CANCEL = "CRS04_PRIOR_FIELD_CANCEL"

CRS04_PRIOR_ST_AGENCY = "CRS04_PRIOR_ST_AGENCY"
CRS04_PRIOR_ST_PHONE = "CRS04_PRIOR_ST_PHONE"
CRS04_PRIOR_ST_EMAIL = "CRS04_PRIOR_ST_EMAIL"
CRS04_PRIOR_ST_DATE = "CRS04_PRIOR_ST_DATE"
CRS04_PRIOR_ST_REPORT = "CRS04_PRIOR_ST_REPORT"

_PRIOR_FIELDS = (
    (CRS04_PRIOR_F_AGENCY, CRS04_PRIOR_ST_AGENCY, "crs04_prior_agency_name", "Agency Name"),
    (CRS04_PRIOR_F_PHONE, CRS04_PRIOR_ST_PHONE, "crs04_prior_phone", "Phone Number"),
    (CRS04_PRIOR_F_EMAIL, CRS04_PRIOR_ST_EMAIL, "crs04_prior_email", "Email Address"),
    (CRS04_PRIOR_F_DATE, CRS04_PRIOR_ST_DATE, "crs04_prior_date_reported", "Date Reported"),
    (CRS04_PRIOR_F_REPORT, CRS04_PRIOR_ST_REPORT, "crs04_prior_report_number", "Report Number"),
)

_PRIOR_PROMPT_BODY = {
    CRS04_PRIOR_ST_AGENCY: (
        "Agency Name\n\n"
        "Please reply with the agency name:\n\n"
        "Example: FBI / Local Police Department"
    ),
    CRS04_PRIOR_ST_PHONE: (
        "Phone Number\n\n"
        "Please reply with the phone number:\n\n"
        "Example: +1 202-324-3000"
    ),
    CRS04_PRIOR_ST_EMAIL: (
        "Email Address\n\n"
        "Please reply with the email address:\n\n"
        "Example: report@agency.gov"
    ),
    CRS04_PRIOR_ST_DATE: (
        "Date Reported\n\n"
        "Please reply with the date:\n\n"
        "Format  : MM/DD/YYYY\n"
        "Example : 03/17/2025"
    ),
    CRS04_PRIOR_ST_REPORT: (
        "Report Number\n\n"
        "Please reply with the report number:\n\n"
        "Example: 2025-031700123"
    ),
}


def crs04_prior_any_filled(d: dict) -> bool:
    return any(_review_field_filled(d.get(k)) for _, _, k, _ in _PRIOR_FIELDS)


def crs04_prior_all_filled(d: dict) -> bool:
    return all(_review_field_filled(d.get(k)) for _, _, k, _ in _PRIOR_FIELDS)


def build_prior_reports_text(d: dict) -> str:
    lines = []
    lbl_map = (
        ("Agency Name", "crs04_prior_agency_name"),
        ("Phone Number", "crs04_prior_phone"),
        ("Email Address", "crs04_prior_email"),
        ("Date Reported", "crs04_prior_date_reported"),
        ("Report Number", "crs04_prior_report_number"),
    )
    for lbl, key in lbl_map:
        v = d.get(key)
        if _review_field_filled(v):
            lines.append(f"{lbl}: {str(v).strip()}")
    return "\n".join(lines)


def clear_crs04_prior_detail_fields(d: dict) -> None:
    for _, _, k, _ in _PRIOR_FIELDS:
        d.pop(k, None)
    d.pop("prior_reports", None)


PRIOR_STATE_TO_KEY_LABEL = {st: (k, disp) for _, st, k, disp in _PRIOR_FIELDS}


def kb_crs04_prior_fields(d: dict) -> InlineKeyboardMarkup:
    d = d or {}
    rows = []
    for cb, _st, ukey, display in _PRIOR_FIELDS:
        v = d.get(ukey)
        label = f"✅ {display}" if _review_field_filled(v) else display
        rows.append([InlineKeyboardButton(label, callback_data=cb)])
    if crs04_prior_all_filled(d):
        rows.append([
            InlineKeyboardButton("✅ Submit", callback_data=CRS04_PRIOR_SAVE),
            InlineKeyboardButton("↩️ Back", callback_data=CRS04_PRIOR_FIELDS_BACK),
        ])
    else:
        rows.append([
            InlineKeyboardButton("✅ Confirm", callback_data=CRS04_PRIOR_CONFIRM),
            InlineKeyboardButton("↩️ Back", callback_data=CRS04_PRIOR_FIELDS_BACK),
        ])
    return InlineKeyboardMarkup(rows)


async def crs04_prior_reports_fields_menu(target, ctx):
    ctx.user_data["state"] = None
    d = ctx.user_data
    body = (
        "IC3 | Internet Crime Complaint Center\n"
        "Other Information CRS-04\n"
        "<b>Prior Reports to Agencies</b>\n"
        f"{CRS04_PRIOR_SEP}\n"
        "Prior Reports to Agencies\n\n"
        "If you have reported this incident\n"
        "to other law enforcement or government\n"
        "agencies, please provide the following:\n\n"
        f"{CRS04_PRIOR_SEP}\n"
        f"{CRS04_PRIOR_SEP}"
    )
    await target.reply_text(
        body,
        parse_mode="HTML",
        reply_markup=kb_crs04_prior_fields(d),
    )


async def crs04_prior_field_prompt(target, ctx, state_str: str):
    body = _PRIOR_PROMPT_BODY.get(state_str)
    if not body:
        return
    ctx.user_data["state"] = state_str
    hdr = (
        "IC3 | Internet Crime Complaint Center\n"
        "Other Information CRS-04\n"
        "<b>Prior Reports to Agencies</b>\n"
        f"{CRS04_PRIOR_SEP}\n"
    )
    await target.reply_text(
        hdr + body + f"\n{CRS04_PRIOR_SEP}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("↩️ Back", callback_data=CRS04_PRIOR_FIELD_CANCEL),
        ]]),
    )


async def crs04_prior_field_prompt_by_callback(target, ctx, cb: str):
    for c, st, _, _ in _PRIOR_FIELDS:
        if c == cb:
            await crs04_prior_field_prompt(target, ctx, st)
            return


async def crs04_prior_reports_finalize(target, ctx):
    d = ctx.user_data
    d["prior_reports_flag"] = "Yes"
    d["prior_reports"] = build_prior_reports_text(d)
    d["state"] = None
    await target.reply_text(
        "✅ <b>Prior Reports to Agencies</b> saved.",
        parse_mode="HTML",
    )
    await crs04_witnesses_hub_menu(target, ctx)


async def crs04_prior_auto_advance_next_field(target, ctx):
    """Prior Reports 分项保存后：按顺序打开下一空项，或回到字段总表（可 Save）。"""
    d = ctx.user_data
    for _cb, st, ukey, _disp in _PRIOR_FIELDS:
        if not _review_field_filled(d.get(ukey)):
            await crs04_prior_field_prompt(target, ctx, st)
            return
    await crs04_prior_reports_fields_menu(target, ctx)


async def crs04_prior_try_handle_text(update, ctx, text: str) -> bool:
    """CRS-04 分项 Prior Reports 文本输入；已处理则返回 True。"""
    state = ctx.user_data.get("state")
    meta = PRIOR_STATE_TO_KEY_LABEL.get(state)
    if not meta:
        return False
    key, disp = meta
    val = (text or "").strip()
    if not val:
        await update.message.reply_text("⚠️ Please enter a value.", parse_mode="HTML")
        return True
    ctx.user_data[key] = val[:500]
    await update.message.reply_text(f"✅ {disp} recorded.", parse_mode="HTML")
    ctx.user_data["state"] = None
    await crs04_prior_auto_advance_next_field(update.message, ctx)
    return True


# ─── CRS-04: Witnesses & Others (multi-step) ──────────────────────────────────
CRS04_WITNESS_SEP = CRS04_PRIOR_SEP

CRS04_WITNESS_ADD = "CRS04_WITNESS_ADD"
CRS04_WITNESS_HUB_BACK = "CRS04_WITNESS_HUB_BACK"
CRS04_WITNESS_DONE = "CRS04_WITNESS_DONE"
CRS04_WITNESS_F_NAME = "CRS04_WITNESS_F_NAME"
CRS04_WITNESS_F_PHONE = "CRS04_WITNESS_F_PHONE"
CRS04_WITNESS_F_EMAIL = "CRS04_WITNESS_F_EMAIL"
CRS04_WITNESS_F_REL = "CRS04_WITNESS_F_REL"
CRS04_WITNESS_CONFIRM = "CRS04_WITNESS_CONFIRM"
CRS04_WITNESS_SAVE_DRAFT = "CRS04_WITNESS_SAVE_DRAFT"
CRS04_WITNESS_SUMMARY_CONTINUE = "CRS04_WITNESS_SUMMARY_CONTINUE"
CRS04_WITNESS_SUMMARY_REVISE = "CRS04_WITNESS_SUMMARY_REVISE"
CRS04_WITNESS_DRAFT_DISCARD = "CRS04_WITNESS_DRAFT_DISCARD"
CRS04_WITNESS_SKIP_PHONE = "CRS04_WITNESS_SKIP_PHONE"
CRS04_WITNESS_SKIP_EMAIL = "CRS04_WITNESS_SKIP_EMAIL"
CRS04_WITNESS_SKIP_REL = "CRS04_WITNESS_SKIP_REL"
CRS04_WITNESS_REL_WITNESS = "CRS04_WITNESS_REL_WITNESS"
CRS04_WITNESS_REL_COVIC = "CRS04_WITNESS_REL_COVIC"
CRS04_WITNESS_REL_INFORM = "CRS04_WITNESS_REL_INFORM"
CRS04_WITNESS_REL_ASSOC = "CRS04_WITNESS_REL_ASSOC"
CRS04_WITNESS_BACK_NAME = "CRS04_WITNESS_BACK_NAME"
CRS04_WITNESS_BACK_PHONE = "CRS04_WITNESS_BACK_PHONE"
CRS04_WITNESS_BACK_EMAIL = "CRS04_WITNESS_BACK_EMAIL"
CRS04_WITNESS_BACK_REL = "CRS04_WITNESS_BACK_REL"

CRS04_WITNESS_ST_NAME = "CRS04_WITNESS_ST_NAME"
CRS04_WITNESS_ST_PHONE = "CRS04_WITNESS_ST_PHONE"
CRS04_WITNESS_ST_EMAIL = "CRS04_WITNESS_ST_EMAIL"

_REL_LABELS = {
    CRS04_WITNESS_REL_WITNESS: "Witness",
    CRS04_WITNESS_REL_COVIC: "Co-victim",
    CRS04_WITNESS_REL_INFORM: "Informant",
    CRS04_WITNESS_REL_ASSOC: "Associate",
}


def _witness_idx_display(d: dict) -> int:
    lst = d.get("crs04_witnesses_list") or []
    return len(lst) + 1


def _witness_draft(d: dict) -> dict:
    w = d.get("crs04_witness_draft")
    if not isinstance(w, dict):
        w = {}
        d["crs04_witness_draft"] = w
    return w


def sync_witnesses_flat_string(d: dict) -> None:
    d["witnesses"] = build_witnesses_storage_text(d)


def build_witnesses_storage_text(d: dict) -> str:
    if d.get("crs04_witnesses_skipped"):
        return "No witnesses provided (skipped)."
    lst = d.get("crs04_witnesses_list") or []
    if not lst:
        return ""
    blocks = []
    for i, w in enumerate(lst, 1):
        lines = [f"Witness #{i}"]
        for key, lbl in (
            ("name", "Name"),
            ("phone", "Phone"),
            ("email", "Email"),
            ("relation", "Relation"),
        ):
            v = w.get(key, "")
            vs = str(v).strip() if v is not None else ""
            if vs == "➖Not Provided":
                lines.append(f"  {lbl}: Not provided")
            elif _review_field_filled(vs):
                lines.append(f"  {lbl}: {vs}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _witness_field_btn_label(draft: dict, key: str, display: str) -> str:
    v = draft.get(key)
    if key == "name" and _review_field_filled(v):
        return f"✅ {display}"
    if key in ("phone", "email") and (v == "➖Not Provided" or _review_field_filled(v)):
        return f"✅ {display}"
    if key == "relation" and (v == "➖Not Provided" or _review_field_filled(v)):
        return f"✅ {display}"
    return display


def _witness_can_confirm(draft: dict) -> bool:
    return _review_field_filled(draft.get("name"))


def _witness_can_save(draft: dict) -> bool:
    if not _review_field_filled(draft.get("name")):
        return False
    if not _review_field_filled(draft.get("relation")):
        return False
    ph = draft.get("phone")
    em = draft.get("email")
    if ph is None or str(ph).strip() == "":
        return False
    if em is None or str(em).strip() == "":
        return False
    return True


def kb_crs04_witness_draft_grid(d: dict, draft: dict, wn: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            _witness_field_btn_label(draft, "name", "Name"),
            callback_data=CRS04_WITNESS_F_NAME,
        )],
        [InlineKeyboardButton(
            _witness_field_btn_label(draft, "phone", "Phone Number"),
            callback_data=CRS04_WITNESS_F_PHONE,
        )],
        [InlineKeyboardButton(
            _witness_field_btn_label(draft, "email", "Email Address"),
            callback_data=CRS04_WITNESS_F_EMAIL,
        )],
        [InlineKeyboardButton(
            _witness_field_btn_label(draft, "relation", "Relation"),
            callback_data=CRS04_WITNESS_F_REL,
        )],
    ]
    if _witness_can_save(draft):
        rows.append([
            InlineKeyboardButton("✅ Submit", callback_data=CRS04_WITNESS_SAVE_DRAFT),
            InlineKeyboardButton("↩️ Back", callback_data=CRS04_WITNESS_DRAFT_DISCARD),
        ])
    else:
        rows.append([
            InlineKeyboardButton("✅ Confirm", callback_data=CRS04_WITNESS_CONFIRM),
            InlineKeyboardButton("↩️ Back", callback_data=CRS04_WITNESS_DRAFT_DISCARD),
        ])
    return InlineKeyboardMarkup(rows)


def kb_crs04_witness_relation() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Witness", callback_data=CRS04_WITNESS_REL_WITNESS),
            InlineKeyboardButton("Co-victim", callback_data=CRS04_WITNESS_REL_COVIC),
        ],
        [
            InlineKeyboardButton("Informant", callback_data=CRS04_WITNESS_REL_INFORM),
            InlineKeyboardButton("Associate", callback_data=CRS04_WITNESS_REL_ASSOC),
        ],
        [
            InlineKeyboardButton("⏭ Skip", callback_data=CRS04_WITNESS_SKIP_REL),
            InlineKeyboardButton("↩️ Back", callback_data=CRS04_WITNESS_BACK_REL),
        ],
    ])


async def _witness_hub_send(
    target,
    ctx,
    fallback_chat_id: Optional[int],
    text: str,
    reply_markup: InlineKeyboardMarkup,
) -> None:
    """reply_text 失败时（原消息过旧/已删等）回退到 send_message，避免回调无应答。"""
    if target is not None:
        try:
            await target.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)
            return
        except Exception:
            logger.exception("CRS-04 witnesses hub: reply_text failed")
    chat_id = fallback_chat_id
    if chat_id is None and target is not None:
        ch = getattr(target, "chat", None)
        if ch is not None:
            chat_id = ch.id
    if chat_id is None:
        raise ValueError("crs04_witnesses_hub_menu: need target or fallback_chat_id")
    await ctx.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="HTML",
        reply_markup=reply_markup,
    )


async def crs04_witnesses_hub_menu(target, ctx, fallback_chat_id: Optional[int] = None):
    ctx.user_data["state"] = None
    ctx.user_data.pop("crs04_witness_draft", None)
    d = ctx.user_data
    lst = d.get("crs04_witnesses_list") or []
    sep = CRS04_WITNESS_SEP
    parts = [
        "IC3 | Internet Crime Complaint Center\n",
        "Other Information  CRS-04\n",
        "<b>Witnesses & Others</b>\n",
        f"{sep}\n",
        "<b>Witnesses & Others</b>\n\n",
        "Please provide information about\n"
        "any witnesses or other individuals\n"
        "involved in this incident.\n\n",
    ]
    if lst:
        parts.append("")
        for i, w in enumerate(lst, 1):
            nm = w.get("name") or "—"
            nm_esc = str(nm).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            parts.append(f"✅ Witness #{i} — {nm_esc}\n")
        parts.append("")
    elif not d.get("crs04_witnesses_skipped"):
        parts.append("<i>No witnesses added yet.</i>\n")
    parts.append(sep)
    body = "".join(parts)
    if not lst:
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("➕ Add Witness", callback_data=CRS04_WITNESS_ADD),
                InlineKeyboardButton("⏭ Skip", callback_data="CRS04_WITNESSES_SKIP"),
                InlineKeyboardButton("↩️ Back", callback_data=CRS04_WITNESS_HUB_BACK),
            ],
        ])
    else:
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("➕ Add Another", callback_data=CRS04_WITNESS_ADD),
                InlineKeyboardButton("✅ Done", callback_data=CRS04_WITNESS_DONE),
                InlineKeyboardButton("↩️ Back", callback_data=CRS04_WITNESS_HUB_BACK),
            ],
        ])
    await _witness_hub_send(target, ctx, fallback_chat_id, body, kb)


def _witness_one_block_html(w: dict, idx: int, h) -> str:
    lines = [f"<b>Witness #{idx}</b>"]
    for key, lbl in (
        ("name", "Name"),
        ("phone", "Phone"),
        ("email", "Email"),
        ("relation", "Relation"),
    ):
        v = w.get(key, "")
        vs = str(v).strip() if v is not None else ""
        if vs == "➖Not Provided":
            lines.append(f"{lbl}: <i>Not provided</i>")
        elif _review_field_filled(vs):
            lines.append(f"{lbl}: <code>{h(vs)}</code>")
        else:
            lines.append(f"{lbl}: <code>—</code>")
    return "\n".join(lines)


async def crs04_witness_saved_summary_menu(
    target, ctx, witness_index: int, w: dict, fallback_chat_id: Optional[int] = None,
):
    """保存一名证人后：汇总供阅读/修订，再回证人列表。"""

    def h(t):
        s = str(t) if t is not None else "—"
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    sep = CRS04_WITNESS_SEP
    block = _witness_one_block_html(w, witness_index, h)
    text = (
        "IC3 | Internet Crime Complaint Center\n"
        "Other Information  CRS-04\n"
        "<b>Witness saved — Review</b>\n"
        f"{sep}\n"
        f"{block}\n"
        f"{sep}\n"
        "<i>Tap <b>Revise</b> to edit this entry, or <b>Continue</b> for the witnesses list.</i>"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Revise", callback_data=CRS04_WITNESS_SUMMARY_REVISE),
            InlineKeyboardButton("➡️ Continue", callback_data=CRS04_WITNESS_SUMMARY_CONTINUE),
        ],
    ])
    if target is not None:
        await target.reply_text(text, parse_mode="HTML", reply_markup=kb)
    elif fallback_chat_id is not None:
        await ctx.bot.send_message(
            chat_id=fallback_chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=kb,
        )
    else:
        raise ValueError("crs04_witness_saved_summary_menu: need target or fallback_chat_id")


def crs04_witness_summary_pop_last_to_draft(ctx) -> bool:
    """将刚保存的最后一名证人从列表移回草稿，供 Revise 使用。"""
    d = ctx.user_data
    lst = list(d.get("crs04_witnesses_list") or [])
    if not lst:
        return False
    last = lst.pop()
    d["crs04_witnesses_list"] = lst
    d["crs04_witness_draft"] = dict(last)
    sync_witnesses_flat_string(d)
    return True


async def crs04_witness_draft_review_menu(target, ctx, fallback_chat_id: Optional[int] = None):
    d = ctx.user_data
    draft = _witness_draft(d)
    wn = _witness_idx_display(d)
    sep = CRS04_WITNESS_SEP
    body = (
        "IC3 | Internet Crime Complaint Center\n"
        "Other Information  CRS-04\n"
        "<b>Witnesses & Others</b>\n"
        f"{sep}\n"
        "<b>Witnesses & Others</b>\n\n"
        f"<b>Witness #{wn}</b>\n"
        f"{sep}\n"
        f"{sep}"
    )
    if target is not None:
        await target.reply_text(
            body,
            parse_mode="HTML",
            reply_markup=kb_crs04_witness_draft_grid(d, draft, wn),
        )
    elif fallback_chat_id is not None:
        await ctx.bot.send_message(
            chat_id=fallback_chat_id,
            text=body,
            parse_mode="HTML",
            reply_markup=kb_crs04_witness_draft_grid(d, draft, wn),
        )
    else:
        raise ValueError("crs04_witness_draft_review_menu: need target or fallback_chat_id")


async def crs04_witness_prompt_name(target, ctx):
    d = ctx.user_data
    wn = _witness_idx_display(d)
    sep = CRS04_WITNESS_SEP
    ctx.user_data["state"] = CRS04_WITNESS_ST_NAME
    await target.reply_text(
        "IC3 | Internet Crime Complaint Center\n"
        f"Other Information  CRS-04 · Witness #{wn}\n"
        f"{sep}\n"
        "<b>Field 1 of 4 · Name</b>\n\n"
        "Please enter the witness's full name.\n\n"
        "Example: John Smith\n"
        f"{sep}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("↩️ Back", callback_data=CRS04_WITNESS_BACK_NAME),
        ]]),
    )


async def crs04_witness_start_add(target, ctx):
    d = ctx.user_data
    d["crs04_witnesses_skipped"] = False
    d["crs04_witness_draft"] = {
        "name": "",
        "phone": "",
        "email": "",
        "relation": "",
    }
    await crs04_witness_prompt_name(target, ctx)


def _recap_lines(draft: dict, h_fn) -> List[str]:
    lines = []
    if _review_field_filled(draft.get("name")):
        lines.append(f"✅ Name: {h_fn(str(draft['name']).strip())}")
    ph = draft.get("phone")
    if ph is not None and str(ph).strip() != "":
        lines.append(f"✅ Phone: {h_fn(str(ph).strip())}")
    em = draft.get("email")
    if em is not None and str(em).strip() != "":
        lines.append(f"✅ Email: {h_fn(str(em).strip())}")
    return lines


async def crs04_witness_prompt_phone(target, ctx):
    d = ctx.user_data
    draft = _witness_draft(d)
    wn = _witness_idx_display(d)
    sep = CRS04_WITNESS_SEP

    def h(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    recap = "\n".join(_recap_lines(draft, h))
    ctx.user_data["state"] = CRS04_WITNESS_ST_PHONE
    await target.reply_text(
        "IC3 | Internet Crime Complaint Center\n"
        f"Other Information  CRS-04 · Witness #{wn}\n"
        f"{sep}\n"
        "<b>Field 2 of 4 · Phone Number</b>\n\n"
        f"{recap}\n\n"
        "Please enter a contact phone number.\n"
        "Include country code.\n\n"
        "Example: +1 555-000-1234\n"
        f"{sep}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⏭ Skip", callback_data=CRS04_WITNESS_SKIP_PHONE),
                InlineKeyboardButton("↩️ Back", callback_data=CRS04_WITNESS_BACK_PHONE),
            ],
        ]),
    )


async def crs04_witness_prompt_email(target, ctx):
    d = ctx.user_data
    draft = _witness_draft(d)
    wn = _witness_idx_display(d)
    sep = CRS04_WITNESS_SEP

    def h(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    recap = "\n".join(_recap_lines(draft, h))
    ctx.user_data["state"] = CRS04_WITNESS_ST_EMAIL
    await target.reply_text(
        "IC3 | Internet Crime Complaint Center\n"
        f"Other Information  CRS-04 · Witness #{wn}\n"
        f"{sep}\n"
        "<b>Field 3 of 4 · Email Address</b>\n\n"
        f"{recap}\n\n"
        "Please enter a contact email address.\n\n"
        "Example: john@email.com\n"
        f"{sep}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⏭ Skip", callback_data=CRS04_WITNESS_SKIP_EMAIL),
                InlineKeyboardButton("↩️ Back", callback_data=CRS04_WITNESS_BACK_EMAIL),
            ],
        ]),
    )


async def crs04_witness_prompt_relation(target, ctx):
    d = ctx.user_data
    draft = _witness_draft(d)
    wn = _witness_idx_display(d)
    sep = CRS04_WITNESS_SEP

    def h(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    recap = "\n".join(_recap_lines(draft, h))
    ctx.user_data["state"] = None
    await target.reply_text(
        "IC3 | Internet Crime Complaint Center\n"
        f"Other Information  CRS-04 · Witness #{wn}\n"
        f"{sep}\n"
        "<b>Field 4 of 4 · Relation to Incident</b>\n\n"
        f"{recap}\n\n"
        "What is this person's role in the incident?\n"
        f"{sep}",
        parse_mode="HTML",
        reply_markup=kb_crs04_witness_relation(),
    )


async def crs04_witness_skip_phone(target, ctx):
    _witness_draft(ctx.user_data)["phone"] = "➖Not Provided"
    await crs04_witness_prompt_email(target, ctx)


async def crs04_witness_skip_email(target, ctx):
    _witness_draft(ctx.user_data)["email"] = "➖Not Provided"
    await crs04_witness_prompt_relation(target, ctx)


async def crs04_witness_set_relation(target, ctx, label: str):
    _witness_draft(ctx.user_data)["relation"] = label
    await crs04_witness_draft_review_menu(target, ctx)


async def crs04_witness_set_relation_by_cb(target, ctx, cb: str):
    lbl = _REL_LABELS.get(cb)
    if not lbl:
        return
    await crs04_witness_set_relation(target, ctx, lbl)


async def crs04_witness_skip_relation(target, ctx):
    _witness_draft(ctx.user_data)["relation"] = "➖Not Provided"
    await crs04_witness_draft_review_menu(target, ctx)


async def crs04_witness_commit_draft(ctx) -> bool:
    d = ctx.user_data
    draft = d.get("crs04_witness_draft")
    if not isinstance(draft, dict):
        return False
    if d.get("crs04_witnesses_list") is None:
        d["crs04_witnesses_list"] = []
    lst = d.get("crs04_witnesses_list") or []
    lst.append(dict(draft))
    d["crs04_witnesses_list"] = lst
    d.pop("crs04_witness_draft", None)
    d["state"] = None
    sync_witnesses_flat_string(d)
    return True


async def crs04_witness_try_handle_text(update, ctx, text: str) -> bool:
    state = ctx.user_data.get("state")
    if state not in (CRS04_WITNESS_ST_NAME, CRS04_WITNESS_ST_PHONE, CRS04_WITNESS_ST_EMAIL):
        return False
    draft = _witness_draft(ctx.user_data)
    val = (text or "").strip()
    if not val:
        await update.message.reply_text("⚠️ Please enter a value.", parse_mode="HTML")
        return True
    val = val[:500]
    if state == CRS04_WITNESS_ST_NAME:
        draft["name"] = val
        await update.message.reply_text("✅ Name recorded.", parse_mode="HTML")
        ctx.user_data["state"] = None
        await crs04_witness_prompt_phone(update.message, ctx)
        return True
    if state == CRS04_WITNESS_ST_PHONE:
        draft["phone"] = val
        await update.message.reply_text("✅ Phone Number recorded.", parse_mode="HTML")
        ctx.user_data["state"] = None
        await crs04_witness_prompt_email(update.message, ctx)
        return True
    if state == CRS04_WITNESS_ST_EMAIL:
        draft["email"] = val
        await update.message.reply_text("✅ Email Address recorded.", parse_mode="HTML")
        ctx.user_data["state"] = None
        await crs04_witness_prompt_relation(update.message, ctx)
        return True
    return False


def format_crs04_other_summary_html(d: dict) -> str:
    def h(t):
        s = str(t) if t is not None else "—"
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    sep = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    parts = [
        "IC3 | Internet Crime Complaint Center\n"
        "Other Information CRS-04\n"
        "<b>CRS-04 · Summary</b>\n"
        f"{sep}\n",
    ]

    # Incident Narrative
    story = d.get("incident_story")
    if _review_field_filled(story):
        parts.append(f"<b>Incident Narrative</b>\n{_html_multiline_br(str(story), h)}\n\n")
    else:
        parts.append("<b>Incident Narrative</b>\n<code>—</code>\n\n")

    # Prior Reports
    pf = d.get("prior_reports_flag") or "—"
    parts.append(f"<b>Prior Reports to Agencies:</b> {h(pf)}\n")
    if pf == "Yes":
        parts.append("<b>Prior Reports (details)</b>\n")
        for lbl, key in (
            ("Agency Name",   "crs04_prior_agency_name"),
            ("Phone Number",  "crs04_prior_phone"),
            ("Email Address", "crs04_prior_email"),
            ("Date Reported", "crs04_prior_date_reported"),
            ("Report Number", "crs04_prior_report_number"),
        ):
            v = d.get(key)
            parts.append(f"{lbl}: <code>{h(str(v).strip() if v else '—')}</code>\n")
        parts.append("\n")

    # Witnesses & Others
    lst = d.get("crs04_witnesses_list") or []
    if d.get("crs04_witnesses_skipped") or not lst:
        parts.append("<b>Witnesses &amp; Others</b>\n<code>—</code>\n")
    else:
        parts.append("<b>Witnesses &amp; Others</b>\n")
        for i, w in enumerate(lst, 1):
            parts.append(f"Witness #{i}\n")
            for key, lbl in (("name", "Name"), ("phone", "Phone"),
                              ("email", "Email"), ("relation", "Relation")):
                v = w.get(key, "")
                if v and str(v).strip():
                    parts.append(f"  {lbl}: <code>{h(str(v).strip())}</code>\n")
        parts.append("\n")

    parts.append(sep)
    return "".join(parts)


def _html_multiline_br(text, h_fn):
    """多行用户文本：逐行 HTML 转义后用换行拼接。
    Telegram parse_mode=HTML 的允许标签列表不含 &lt;br&gt;（&lt;br/&gt; 亦不可用），故用 \\n 换行。"""
    s = str(text) if text is not None else ""
    if not s.strip():
        return ""
    return "\n".join(h_fn(line) for line in s.splitlines())


def _crs03_subject_contact_html(d: dict, h_fn) -> str:
    """CRS-03 Step 1 Contact Info — 显示于 Review CRS-05-01。"""
    pairs = [
        ("Subject Contact Name", "crs03_subject_name"),
        ("Subject Phone", "crs03_subject_phone"),
        ("Subject Email", "crs03_subject_email"),
        ("Subject Address", "crs03_subject_address"),
        ("Subject City", "crs03_subject_city"),
        ("Subject Country", "crs03_subject_country"),
    ]
    lines = []
    for lbl, key in pairs:
        v = d.get(key)
        if not _review_field_filled(v):
            continue
        lines.append(f"{lbl}: <code>{h_fn(str(v).strip())}</code>")
    if not lines:
        return ""
    return "<b>Subject Contact (Step 1)</b>\n" + "\n".join(lines) + "\n\n"


def format_crs03_save_summary_html(d: dict) -> str:
    """CRS-03 主菜单 Save：汇总预览（HTML），供 Edit / Save 使用。"""

    def h(text):
        s = str(text) if text is not None else "—"
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def line_val(key: str) -> str:
        v = d.get(key)
        if _review_field_filled(v):
            return h(str(v).strip())
        if v == "➖Not Provided":
            return "➖Not Provided"
        return "—"

    parts = [
        "<b>IC3 | Internet Crime Complaint Center</b>",
        "<b>Subject Identification CRS-03</b>",
        SEP,
        "<b>CRS-03 · Subject Identification — Summary</b>",
        SEP,
        "<b>Subject Contact (Step 1)</b>",
    ]
    for lbl, key in (
        ("Subject Contact Name", "crs03_subject_name"),
        ("Subject Phone", "crs03_subject_phone"),
        ("Subject Email", "crs03_subject_email"),
        ("Subject Address", "crs03_subject_address"),
        ("Subject City", "crs03_subject_city"),
        ("Subject Country", "crs03_subject_country"),
    ):
        parts.append(f"{lbl}: {line_val(key)}")
    parts.append("")
    parts.append(f"Platform: {line_val('platform')}")
    parts.append(f"Profile URL: {line_val('profile_url')}")
    parts.append(f"Crime Type: {line_val('crime_type')}")
    parts.append(SEP)
    return "\n".join(parts)


def format_crs01_save_summary_html(d: dict) -> str:
    """CRS-01 菜单 Save：汇总预览（HTML），供 Edit / Save 使用。"""

    def h(text):
        s = str(text) if text is not None else "—"
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def lv(key: str) -> str:
        v = d.get(key)
        if v is None or str(v).strip() == "":
            return "—"
        return h(str(v).strip())

    parts = [
        "<b>IC3 | Internet Crime Complaint Center</b>",
        "<b>COMPLAINANT INFORMATION — CRS-01</b>",
        SEP,
        "<b>Summary — Review Before Saving</b>",
        SEP,
        f"<b>Full legal name:</b> {lv('fullname')}",
        f"<b>Age:</b> {lv('dob')}",
        f"<b>Physical address:</b> {lv('address')}",
        f"<b>Contact number:</b> {lv('phone')}",
        f"<b>Email address:</b> {lv('email')}",
        SEP,
    ]
    return "\n".join(parts)


async def crs04_review(target, ctx, fallback_chat_id: Optional[int] = None):
    ctx.user_data["state"] = None
    d = ctx.user_data

    async def _rv_send(text: str, **kwargs):
        if target is not None:
            await target.reply_text(text, **kwargs)
        elif fallback_chat_id is not None:
            await ctx.bot.send_message(chat_id=fallback_chat_id, text=text, **kwargs)
        else:
            raise ValueError("crs04_review: need target or fallback_chat_id")

    def h(text):
        """HTML-escape user text: & < > only"""
        s = str(text) if text is not None else "—"
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    fn = h(d.get("fullname", "—"))
    addr = h(d.get("address", "—"))
    ph = h(d.get("phone", "—"))
    em = h(d.get("email", "—"))

    tx_count = int(d.get("tx_count") or 1)
    tx_view = _tx_data_review_view(d)
    has_structured = any(
        _tx_snapshot_nonempty(tx_view.get(n) or {})
        for n in range(1, tx_count + 1)
    )
    if has_structured:
        m02_body = "".join(
            _format_tx_review_block(n, tx_view.get(n) or {}, h)
            for n in range(1, tx_count + 1)
        )
    else:
        m02_body = _legacy_flat_m02_block(d, h)

    total_loss_html = _total_loss_display(d, h)

    pl = h(d.get("platform", "—"))
    purl = h(d.get("profile_url", "—"))
    ct = h(d.get("crime_type", "—"))

    story_raw = d.get("incident_story")
    if story_raw is None or str(story_raw).strip() == "":
        story_str = "—"
    else:
        story_str = str(story_raw)
    narrative_pre = (
        f"<b>Incident Narrative</b>\n{_html_multiline_br(story_str, h)}\n\n"
        if story_str != "—"
        else "<b>Incident Narrative</b>\n<code>—</code>\n\n"
    )

    prior_flag = d.get("prior_reports_flag")
    prior_txt = d.get("prior_reports") or ""
    prior_block = f"<b>Prior Reports to Agencies:</b> <code>{h(str(prior_flag or '—'))}</code>\n"
    if prior_txt and str(prior_txt).strip():
        prior_block += f"<b>Details:</b>\n{_html_multiline_br(str(prior_txt), h)}\n"

    wit = d.get("witnesses")
    if _review_field_filled(wit):
        wit_block = f"<b>Witnesses &amp; Others:</b>\n{_html_multiline_br(str(wit), h)}\n"
    else:
        wit_block = "<b>Witnesses &amp; Others:</b> <code>—</code>\n"

    m04_full = (
        "<b>[SECTION CRS-04: OTHER INFORMATION]</b>\n"
        + narrative_pre
        + prior_block
        + wit_block
        + "\n"
    )

    body_top = (
        f"{MAIN_SEP}\n"
        "<b>IC3 | Internet Crime Complaint Center</b>\n"
        "<b>Privacy &amp; Signature</b>\n"
        "<b>Review &amp; Legal Attestation CRS-05-01</b>\n"
        f"{MAIN_SEP}\n\n"
        "<b>[SYSTEM-CHECK]: Data integrity validation: OK.</b>\n\n"
        "<b>[SECTION CRS-01: COMPLAINANT IDENTIFICATION]</b>\n"
        f"Name:     <code>{fn}</code>\n"
        f"Address:  <code>{addr}</code>\n"
        f"Phone:    <code>{ph}</code>\n"
        f"Email:    <code>{em}</code>\n\n"
        "<b>[SECTION CRS-02: FINANCIAL TRANSACTION(S)]</b>\n"
        f"<b>Total Loss Amount:</b> {total_loss_html}\n\n"
        + m02_body
        + "<b>[SECTION CRS-03: PLATFORM &amp; SUBJECT INFO]</b>\n"
        + _crs03_subject_contact_html(d, h)
        + f"Contact/Platform:  <code>{pl}</code>\n"
        + f"Profile URL:       <code>{purl}</code>\n"
        + f"Crime Type:        <code>{ct}</code>\n\n"
    )

    footer = (
        "━" * 61
        + "\n<b>IC3 | DIGITAL SIGNATURE (M04-CRS)</b>\n"
        + "━" * 61
        + "\n"
        + f"{FEDERAL_INDEX_LINE}\n"
        + "📄 Document will be digitally signed upon transmission.\n"
        + "━" * 61
    )

    summary = body_top + m04_full + footer
    tg_max = 4096
    if len(summary) <= tg_max:
        await _rv_send(summary, parse_mode="HTML", reply_markup=kb_crs_attest())
        return

    m04_split = (
        "<b>[SECTION CRS-04: OTHER INFORMATION]</b>\n"
        "<b>Incident Narrative</b>\n<i>Full text follows in the next message.</i>\n\n"
        + prior_block
        + wit_block
        + "\n"
    )
    part1 = body_top + m04_split
    narrative_body = (
        (
            "<b>Incident Narrative (full)</b>\n"
            f"{_html_multiline_br(story_str, h)}\n\n"
        )
        if story_str != "—"
        else ""
    )
    part2 = narrative_body + footer
    await _rv_send(part1, parse_mode="HTML")
    await _rv_send(part2, parse_mode="HTML", reply_markup=kb_crs_attest())


# ─── Digital Signature Request / PIN / Certificate (CERTIFY-TRANSMIT 新流程) ───

DIGSIG_PRIVACY_STATEMENT_FULL = """
Read the following statement below, and confirm your agreement by typing your
full name below in the box provided:

The collection of information on this form is authorized by one or more of the
following statutes: 18 U.S.C. § 1028 (false documents and identity theft); 1028A
(aggravated identity theft); 18 U.S.C. § 1029 (credit card fraud); 18 U.S.C. § 1030
(computer fraud); 18 U.S.C. § 1343 (wire fraud); 18 U.S.C 2318B (counterfeit and
illicit labels); 18 U.S.C. § 2319 (violation of intellectual property rights); 28 U.S.C. § 533
(FBI authorized to investigate violations of federal law for which it has primary
investigative jurisdiction); and 28 U.S.C. § 534 (FBI authorized to collect and
maintain identification, criminal information, crime, and other records).

The collection of this information is relevant and necessary to document and
investigate complaints of Internet-related crime. Submission of the information requested
is voluntary; however, your failure to supply requested information may impede or
preclude the investigation of your complaint by law enforcement agencies.

The information collected is maintained in one or more of the following Privacy
Act Systems of Records: the FBI Central Records System, Justice/FBI-002, notice of
which was published in the Federal Register at 63 Fed. Reg. 8671 (Feb. 20, 1998);
the FBI Data Warehouse System, DOJ/FBI-022, notice of which was published in the
Federal Register at 77 Fed. Reg. 40631 (July 10, 2012). Descriptions of these systems
may also be found at www.justice.gov/opcl/doj-systems-records#FBI. The information
collected may be disclosed in accordance with the routine uses referenced in those
notices or as otherwise permitted by law. For example, in accordance with those
routine uses, in certain circumstances, the FBI may disclose information from your
complaint to appropriate criminal, civil, or regulatory law enforcement authorities
(whether federal, state, local, territorial, tribal, foreign, or international). Information
also may be disclosed as a routine use to an organization or individual in both the public
or private sector if deemed necessary to elicit information or cooperation from the
recipient for use by the FBI in the performance of an authorized activity. "An example
would be where the activities of an individual are disclosed to a member
of the public in order to elicit his/her assistance in [FBI's] apprehension or detection
efforts." 63 Fed. Reg. 8671, 8682 (February 20, 1998).

By typing my name below, I understand and agree that this form of electronic
signature has the same legal force and effect as a manual signature. I affirm that
the information I provided is true and accurate to the best of my knowledge.
I understand that providing false information could make me subject to fine,
imprisonment, or both. (Title 18, U.S.Code, Section 1001)
""".strip()


def _digsig_privacy_statement_html() -> str:
    """完整法律正文：逐行 HTML 转义，Telegram HTML 用换行分段。"""
    from html import escape as _esc

    return "\n".join(_esc(line) for line in DIGSIG_PRIVACY_STATEMENT_FULL.splitlines())


def build_signature_request_text(
    case_id: str,
    submitted_utc: str,
    doc_hash_short: str = "",
    doc_hash_full: str = "",
    *,
    expanded: bool = False,
) -> str:
    """Digital Signature STEP 1 — IC3 | DIGITAL SIGNATURE REQUEST（默认折叠长文，expanded 展开全文）。"""
    from html import escape as _esc

    hash_display = _esc((doc_hash_full or "—") if expanded else (doc_hash_short or "—"))
    case_block = (
        f"{MAIN_SEP}\n"
        "<b>You are about to electronically sign the following submission:</b>\n\n"
        f"Case ID   : <code>{_esc(case_id)}</code>\n"
        f"Submitted : {_esc(submitted_utc)}\n"
        "Pages     : 1\n"
        f"Hash      : {hash_display}\n"
        f"{MAIN_SEP}\n"
    )
    header = (
        "<b>IC3 | DIGITAL SIGNATURE REQUEST</b>\n"
        "<b>[🔐 Privacy & Signature]</b>\n"
        f"{MAIN_SEP}\n"
    )
    if not expanded:
        return (
            header
            + "<i>The full statement covers statutory authority (18 U.S.C.), Privacy Act "
            "systems of records (Justice/FBI-002, DOJ/FBI-022), routine uses for disclosure, "
            "and your electronic signature attestation (Title 18, U.S. Code, Section 1001).</i>\n\n"
            "<b>Tap “Show full statement” below to read the complete text before signing.</b>\n\n"
            "When you continue, you will set or enter your security PIN to complete the signature.\n\n"
            + case_block
        )
    return header + _digsig_privacy_statement_html() + "\n\n" + case_block


def _attempts_remaining_phrase(attempts_left: int) -> str:
    """'1 attempt remaining' vs 'X attempts remaining' for wrong-PIN message."""
    return "1 attempt remaining." if attempts_left == 1 else f"{attempts_left} attempts remaining."


def build_pin_verification_text(pin_dots: str = "") -> str:
    """STEP 2 — PIN VERIFICATION. pin_dots e.g. '● ● ● _ _ _'."""
    return (
        "STEP 2 — PIN VERIFICATION\n"
        f"{MAIN_SEP}\n\n"
        "Enter your 6-digit security PIN\n"
        "to confirm your identity.\n\n"
        f"  {pin_dots or '_ _ _ _ _ _'}\n\n"
        f"{MAIN_SEP}\n"
    )


def build_pin_incorrect_text(attempts_left: int, pin_dots: str = "") -> str:
    """Wrong PIN: show attempts remaining (1 attempt vs X attempts)."""
    phrase = _attempts_remaining_phrase(attempts_left)
    return (
        "STEP 2 — PIN VERIFICATION\n"
        f"{MAIN_SEP}\n\n"
        f"❌ Incorrect. <b>{phrase}</b>\n\n"
        "Enter your 6-digit security PIN\n"
        "to confirm your identity.\n\n"
        f"  {pin_dots or '_ _ _ _ _ _'}\n\n"
        f"{MAIN_SEP}\n"
    )


def build_pin_locked_text() -> str:
    """3 wrong attempts → session locked."""
    return (
        "🔒 <b>Session locked for security.</b>\n\n"
        "Please contact ic3.gov/support"
    )


def build_set_pin_text(pin_dots: str = "") -> str:
    """设置 PIN 文案（所有用户统一显示）。"""
    return (
        "[ 🔐 ] SET YOUR SECURITY PIN\n"
        f"{MAIN_SEP}\n\n"
        " Enter a new 6-digit PIN.\n"
        "  You will confirm it in the next step.\n\n"
        f"  {pin_dots or '_ _ _ _ _ _'}\n\n"
        f"{MAIN_SEP}\n"
    )


def build_confirm_pin_text(pin_dots: str = "") -> str:
    """确认 PIN 文案。与 build_set_pin_text 保持相同行数，页面大小统一。"""
    return (
        "[ 🔐 ] CONFIRM YOUR PIN\n"
        f"{MAIN_SEP}\n\n"
        " Re-enter your 6-digit PIN.\n"
        "  Confirm to proceed.\n\n"
        f"  {pin_dots or '_ _ _ _ _ _'}\n\n"
        f"{MAIN_SEP}\n"
    )


def build_certificate_text(
    case_id: str,
    signed_by: str,
    timestamp: str,
    signature_hex: str,
    auth_ref: str,
    session_hash: str,
) -> str:
    """IC3 | SIGNATURE CERTIFICATE 文案。signature_hex 完整十六进制，展示时每 4 字一组多行。"""
    sig = (signature_hex or "").replace(" ", "").upper()
    lines = []
    for i in range(0, len(sig), 16):
        chunk = sig[i : i + 16]
        lines.append("  " + " ".join(chunk[j : j + 4] for j in range(0, len(chunk), 4)))
    sig_block = "\n".join(lines) if lines else "  —"
    return (
        "IC3 | SIGNATURE CERTIFICATE\n"
        "[ ✅ ] SUCCESSFULLY SIGNED\n"
        f"{MAIN_SEP}\n\n"
        f"  Case ID   : <code>{case_id}</code>\n"
        f"  Signed by : {signed_by}\n"
        f"  Timestamp : {timestamp}\n"
        "  Algorithm : HMAC-SHA256\n\n"
        "─────────────────\n"
        "SIGNATURE\n"
        f"{sig_block}\n"
        "─────────────────\n\n"
        "  Doc Hash  : SHA-256\n"
        f"  Auth Ref  : {auth_ref}\n"
        "  Status    : ✅ VERIFIED & BOUND\n\n"
        f"{FEDERAL_INDEX_LINE}\n"
        f"🆔 SESSION HASH: [ {session_hash} ]\n"
        f"{MAIN_SEP}\n"
    )


def build_done_success_text(case_id: str) -> str:
    """STEP 4 — Done: success message before return to main menu."""
    return (
        "Your case has been successfully\n"
        "submitted to IC3.\n\n"
        f"  Case ID : <code>{case_id}</code>\n\n"
        "You will be notified when\n"
        "a case specialist is assigned."
    )


# ─── Account Recovery (Forgot PIN) ───────────────────────────────────────

def build_recovery_menu_text() -> str:
    return (
        f"{MAIN_SEP}\n"
        "IC3 | ACCOUNT RECOVERY\n"
        "[ 🔑 ] FORGOT PIN\n"
        f"{MAIN_SEP}\n\n"
        "Select recovery method:\n\n"
        f"{MAIN_SEP}"
    )


def build_recovery_email_sent_text(masked_email: str) -> str:
    return (
        f"{MAIN_SEP}\n"
        "A verification code has been\n"
        "sent to:\n\n"
        f"  <code>{masked_email}</code>\n\n"
        "Enter the 6-digit code below.\n"
        "Code expires in 10 minutes.\n"
        f"{MAIN_SEP}"
    )


def build_recovery_caseid_prompt_text() -> str:
    return (
        f"{MAIN_SEP}\n"
        "Enter your Case ID to verify\n"
        "your identity:\n\n"
        "  e.g. <code>IC3-2026-REF-9928-X82</code>\n"
        f"{MAIN_SEP}"
    )


def build_recovery_set_pin_text(pin_dots: str = "") -> str:
    return (
        f"{MAIN_SEP}\n"
        "IC3 | ACCOUNT RECOVERY\n"
        "[ 🔐 ] SET NEW PIN\n"
        f"{MAIN_SEP}\n\n"
        "Enter your new 6-digit PIN:\n\n"
        f"  {pin_dots or '_ _ _ _ _ _'}\n\n"
        f"{MAIN_SEP}"
    )


def build_recovery_confirm_pin_text(pin_dots: str = "") -> str:
    return (
        f"{MAIN_SEP}\n"
        "IC3 | ACCOUNT RECOVERY\n"
        "[ 🔐 ] CONFIRM NEW PIN\n"
        f"{MAIN_SEP}\n\n"
        "Re-enter your new PIN\n"
        "to confirm:\n\n"
        f"  {pin_dots or '_ _ _ _ _ _'}\n\n"
        f"{MAIN_SEP}"
    )


def build_recovery_success_text(reset_ts: str, auth_ref: str) -> str:
    return (
        f"{MAIN_SEP}\n"
        "✅ PIN SUCCESSFULLY RESET\n\n"
        f"  Reset at : {reset_ts}\n"
        f"  Auth Ref : {auth_ref}\n\n"
        "Your account is now secured.\n"
        f"{MAIN_SEP}"
    )


# ─── CRS-03 · Subject Identification (New Design) ────────────────────────────
SEP = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
HDR = "IC3 | Internet Crime Complaint Center\nSubject Identification CRS-03"

# ── Callback constants ────────────────────────────────────────────────────────
CRS03_CONTACT    = "CRS03_CONTACT"
CRS03_PLATFORM   = "CRS03_PLATFORM_NEW"
CRS03_PROFILE    = "CRS03_PROFILE_NEW"
CRS03_CRIME_TYPE = "CRS03_CRIME_TYPE_NEW"
CRS03_CONTINUE   = "CRS03_CONTINUE_NEW"
CRS03_BACK       = "CRS03_BACK_NEW"

CRS03_C_NAME    = "CRS03_C_NAME"
CRS03_C_PHONE   = "CRS03_C_PHONE"
CRS03_C_EMAIL   = "CRS03_C_EMAIL"
CRS03_C_ADDRESS = "CRS03_C_ADDRESS"
CRS03_C_CITY    = "CRS03_C_CITY"
CRS03_C_COUNTRY = "CRS03_C_COUNTRY"
CRS03_C_SAVE    = "CRS03_C_SAVE"
CRS03_C_SKIP    = "CRS03_C_SKIP"
CRS03_C_BACK    = "CRS03_C_BACK"

CRS03_FIELD_SKIP = "CRS03_FIELD_SKIP"
CRS03_FIELD_BACK = "CRS03_FIELD_BACK"

# Platform selection grid
CRS03_P_FACEBOOK  = "CRS03_P_FACEBOOK"
CRS03_P_INSTAGRAM = "CRS03_P_INSTAGRAM"
CRS03_P_WHATSAPP  = "CRS03_P_WHATSAPP"
CRS03_P_TELEGRAM  = "CRS03_P_TELEGRAM"
CRS03_P_TIKTOK    = "CRS03_P_TIKTOK"
CRS03_P_TWITTER   = "CRS03_P_TWITTER"
CRS03_P_YOUTUBE   = "CRS03_P_YOUTUBE"
CRS03_P_LINKEDIN  = "CRS03_P_LINKEDIN"
CRS03_P_DISCORD   = "CRS03_P_DISCORD"
CRS03_P_OTHER     = "CRS03_P_OTHER"
CRS03_P_SKIP      = "CRS03_P_SKIP"
CRS03_P_BACK      = "CRS03_P_BACK"
CRS03_P_ACCT_SKIP = "CRS03_P_ACCT_SKIP"
CRS03_P_ACCT_BACK = "CRS03_P_ACCT_BACK"

CRS03_CT_FRAUD      = "CRS03_CT_FRAUD"
CRS03_CT_IDENTITY   = "CRS03_CT_IDENTITY"
CRS03_CT_PHISHING   = "CRS03_CT_PHISHING"
CRS03_CT_RANSOMWARE = "CRS03_CT_RANSOMWARE"
CRS03_CT_ROMANCE    = "CRS03_CT_ROMANCE"
CRS03_CT_INVESTMENT = "CRS03_CT_INVESTMENT"
CRS03_CT_BEC        = "CRS03_CT_BEC"
CRS03_CT_OTHER      = "CRS03_CT_OTHER"
CRS03_CT_SKIP       = "CRS03_CT_SKIP"
CRS03_CT_BACK       = "CRS03_CT_BACK"

# ── State strings (used in msg_handler) ───────────────────────────────────────
STATE_C_NAME    = "CRS03_STATE_C_NAME"
STATE_C_PHONE   = "CRS03_STATE_C_PHONE"
STATE_C_EMAIL   = "CRS03_STATE_C_EMAIL"
STATE_C_ADDRESS = "CRS03_STATE_C_ADDRESS"
STATE_C_CITY    = "CRS03_STATE_C_CITY"
STATE_C_COUNTRY = "CRS03_STATE_C_COUNTRY"
STATE_PLATFORM            = "CRS03_STATE_PLATFORM"
STATE_PROFILE             = "CRS03_STATE_PROFILE"
STATE_PLATFORM_ACCT       = "CRS03_STATE_PLATFORM_ACCT"
STATE_PLATFORM_OTHER_NAME = "CRS03_STATE_PLATFORM_OTHER_NAME"
STATE_PLATFORM_OTHER_ACCT = "CRS03_STATE_PLATFORM_OTHER_ACCT"

ALL_STATES = {
    STATE_C_NAME, STATE_C_PHONE, STATE_C_EMAIL, STATE_C_ADDRESS,
    STATE_C_CITY, STATE_C_COUNTRY,
    STATE_PLATFORM, STATE_PROFILE,
    STATE_PLATFORM_ACCT, STATE_PLATFORM_OTHER_NAME, STATE_PLATFORM_OTHER_ACCT,
}

# Platform name lookup
_CRS03_PLATFORM_CB_TO_NAME = {
    CRS03_P_FACEBOOK:  "Facebook",
    CRS03_P_INSTAGRAM: "Instagram",
    CRS03_P_WHATSAPP:  "WhatsApp",
    CRS03_P_TELEGRAM:  "Telegram",
    CRS03_P_TIKTOK:    "TikTok",
    CRS03_P_TWITTER:   "Twitter/X",
    CRS03_P_YOUTUBE:   "YouTube",
    CRS03_P_LINKEDIN:  "LinkedIn",
    CRS03_P_DISCORD:   "Discord",
}

# Per-platform account prompt details: (step_title, prompt_header, prompt_body, example)
_CRS03_PLATFORM_PROMPTS = {
    "Facebook":  ("Step 2 • Facebook",  "Facebook Account",
                  "Please reply with the\nFacebook account:",
                  "john.doe\n         john.doe@email.com\n         https://facebook.com/john.doe"),
    "Instagram": ("Step 2 • Instagram", "Instagram Account",
                  "Please reply with the\nInstagram account:",
                  "@john_doe\n         https://instagram.com/john_doe"),
    "WhatsApp":  ("Step 2 • WhatsApp",  "WhatsApp Account",
                  "Please reply with the\nWhatsApp phone number:",
                  "+1 212 555 0100"),
    "Telegram":  ("Step 2 • Telegram",  "Telegram Account",
                  "Please reply with the\nTelegram username or phone number:",
                  "@john_doe\n         +1 212 555 0100"),
    "TikTok":    ("Step 2 • TikTok",    "TikTok Account",
                  "Please reply with the\nTikTok username:",
                  "@john_doe\n         https://tiktok.com/@john_doe"),
    "Twitter/X": ("Step 2 • Twitter/X", "Twitter/X Account",
                  "Please reply with the\nTwitter/X username:",
                  "@john_doe\n         https://x.com/john_doe"),
    "YouTube":   ("Step 2 • YouTube",   "YouTube Account",
                  "Please reply with the\nYouTube channel:",
                  "@john_doe\n         https://youtube.com/@john_doe"),
    "LinkedIn":  ("Step 2 • LinkedIn",  "LinkedIn Account",
                  "Please reply with the\nLinkedIn profile:",
                  "john.doe\n         https://linkedin.com/in/john-doe"),
    "Discord":   ("Step 2 • Discord",   "Discord Account",
                  "Please reply with the\nDiscord username:",
                  "john_doe#1234\n         @john_doe"),
}

# ── Contact field definitions ─────────────────────────────────────────────────
# (callback, state, data_key, label, step)
CONTACT_FIELDS = [
    (CRS03_C_NAME,    STATE_C_NAME,    "crs03_subject_name",    "Name",         "1-01"),
    (CRS03_C_PHONE,   STATE_C_PHONE,   "crs03_subject_phone",   "Phone Number", "1-02"),
    (CRS03_C_EMAIL,   STATE_C_EMAIL,   "crs03_subject_email",   "Email Address","1-03"),
    (CRS03_C_ADDRESS, STATE_C_ADDRESS, "crs03_subject_address", "Address",      "1-04"),
    (CRS03_C_CITY,    STATE_C_CITY,    "crs03_subject_city",    "City",         "1-05"),
    (CRS03_C_COUNTRY, STATE_C_COUNTRY, "crs03_subject_country", "Country",      "1-06"),
]

CONTACT_STATE_TO_KEY   = {s: k for _, s, k, _, _ in CONTACT_FIELDS}
CONTACT_STATE_TO_LABEL = {s: l for _, s, _, l, _ in CONTACT_FIELDS}

# ── Crime type map ─────────────────────────────────────────────────────────────
CRIME_TYPE_MAP = {
    CRS03_CT_FRAUD:      "Fraud",
    CRS03_CT_IDENTITY:   "Identity Theft",
    CRS03_CT_PHISHING:   "Phishing",
    CRS03_CT_RANSOMWARE: "Ransomware",
    CRS03_CT_ROMANCE:    "Romance Scam",
    CRS03_CT_INVESTMENT: "Investment Scam",
    CRS03_CT_BEC:        "Business Email Compromise",
    CRS03_CT_OTHER:      "Other",
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _contact_complete(d: dict) -> bool:
    return any(d.get(k) for _, _, k, _, _ in CONTACT_FIELDS)


def _vbtn(label: str, data_key: str, cb: str, d: dict) -> InlineKeyboardButton:
    """Button: ✅ value when filled, ➖Not Provided when skipped, plain label when empty."""
    v = d.get(data_key)
    if v == "➖Not Provided":
        return InlineKeyboardButton("➖Not Provided", callback_data=cb)
    if v and str(v).strip():
        display = str(v).strip()[:20] + ("…" if len(str(v).strip()) > 20 else "")
        return InlineKeyboardButton(f"✅ {display}", callback_data=cb)
    return InlineKeyboardButton(label, callback_data=cb)


# ── Keyboard builders ─────────────────────────────────────────────────────────
def kb_crs03_main(d: dict = None) -> InlineKeyboardMarkup:
    d = d or {}

    def _btn(label, key, cb):
        return _vbtn(label, key, cb, d)

    contact_label = "✅ Contact Info" if _contact_complete(d) else "Contact Info"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(contact_label, callback_data=CRS03_CONTACT),
         _btn("Platform",  "platform",    CRS03_PLATFORM)],
        [_btn("Profile URL", "profile_url", CRS03_PROFILE)],
        [_btn("Crime Type",  "crime_type",  CRS03_CRIME_TYPE)],
        [InlineKeyboardButton("✅ Submit", callback_data=CRS03_CONTINUE),
         InlineKeyboardButton("↩️ Back",  callback_data=CRS03_BACK)],
    ])


def kb_crs03_contact(d: dict = None) -> InlineKeyboardMarkup:
    d = d or {}
    rows = [[_vbtn(lbl, key, cb, d)] for cb, _, key, lbl, _ in CONTACT_FIELDS]
    rows.append([
        InlineKeyboardButton("✅ Submit",  callback_data=CRS03_C_SAVE),
        InlineKeyboardButton("⏭️ Skip", callback_data=CRS03_C_SKIP),
        InlineKeyboardButton("↩️ Back", callback_data=CRS03_C_BACK),
    ])
    return InlineKeyboardMarkup(rows)


def kb_crs03_crime(current: str = None) -> InlineKeyboardMarkup:
    rows = []
    for cb, val in CRIME_TYPE_MAP.items():
        tick = "✅ " if current == val else ""
        rows.append([InlineKeyboardButton(f"{tick}{val}", callback_data=cb)])
    rows.append([
        InlineKeyboardButton("⏭️ Skip", callback_data=CRS03_CT_SKIP),
        InlineKeyboardButton("↩️ Back", callback_data=CRS03_CT_BACK),
    ])
    return InlineKeyboardMarkup(rows)


# ── Step functions ─────────────────────────────────────────────────────────────
async def crs03_main_menu(target, ctx):
    ctx.user_data["state"] = None
    await target.reply_text(
        f"{HDR}\n{SEP}\n"
        "Do not provide complainant Personally\n"
        "Identifiable Information (PII)\n"
        "such as Social Security numbers\n"
        "or dates of birth anywhere in this form.\n"
        f"{SEP}",
        parse_mode="HTML",
        reply_markup=kb_crs03_main(ctx.user_data),
    )


async def crs03_contact_menu(target, ctx):
    ctx.user_data["state"] = None
    await target.reply_text(
        f"{HDR}\nStep 1-01  • Contact Info\n{SEP}",
        parse_mode="HTML",
        reply_markup=kb_crs03_contact(ctx.user_data),
    )


async def crs03_contact_field_prompt(target, ctx, cb: str):
    entry = next((e for e in CONTACT_FIELDS if e[0] == cb), None)
    if not entry:
        return
    _, state, _, label, step = entry
    ctx.user_data["state"] = state

    body_map = {
        STATE_C_NAME: (
            "Subject Name\n\nPlease provide the name of the\n"
            "individual or organization involved\nin the incident.\n\n"
            "Please reply with the name:\n\nExample: John Smith\n         ABC Company Ltd"
        ),
        STATE_C_PHONE: (
            "Phone Number\n\nPlease provide the subject's\nphone number.\n\n"
            "Please reply with the number:\n\nExample: +1-305-555-0100"
        ),
        STATE_C_EMAIL: (
            "Email Address\n\nPlease provide the subject's\nemail address.\n\n"
            "Please reply with the email:\n\nExample: subject@email.com"
        ),
        STATE_C_ADDRESS: (
            "Address\n\nPlease provide the subject's\nstreet address.\n\n"
            "Please reply with the address:\n\nExample: 123 Main Street"
        ),
        STATE_C_CITY: (
            "City\n\nPlease provide the subject's city.\n\n"
            "Please reply with the city:\n\nExample: New York"
        ),
        STATE_C_COUNTRY: (
            "Country\n\nPlease provide the subject's country.\n\n"
            "Please reply with the country:\n\nExample: United States"
        ),
    }
    body = body_map.get(state, f"{label}\n\nPlease reply with the value:")
    step_title = f"Step {step} • Contact Info • {label}"

    await target.reply_text(
        f"{HDR}\n{step_title}\n{SEP}\n{body}\n{SEP}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⏭️ Skip", callback_data=CRS03_FIELD_SKIP),
            InlineKeyboardButton("↩️ Back", callback_data=CRS03_C_BACK),
        ]]),
    )


def _crs03_first_unfilled_contact_index(d: dict) -> int:
    """自上而下第一个未填写（含未跳过）的联系字段索引；均已填则 -1。"""
    for i, e in enumerate(CONTACT_FIELDS):
        key = e[2]
        v = d.get(key)
        if not _review_field_filled(v) and v != "➖Not Provided":
            return i
    return -1


async def crs03_contact_advance(target, ctx, current_state: str):
    """保存/跳过某一字段后：跳到下方第一个未填项，或回到联系信息菜单。"""
    ctx.user_data["state"] = None
    next_i = _crs03_first_unfilled_contact_index(ctx.user_data)
    if next_i < 0:
        await crs03_contact_menu(target, ctx)
    else:
        next_cb = CONTACT_FIELDS[next_i][0]
        await crs03_contact_field_prompt(target, ctx, next_cb)


def kb_crs03_platform_select() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Facebook",  callback_data=CRS03_P_FACEBOOK),
         InlineKeyboardButton("Instagram", callback_data=CRS03_P_INSTAGRAM)],
        [InlineKeyboardButton("WhatsApp",  callback_data=CRS03_P_WHATSAPP),
         InlineKeyboardButton("Telegram",  callback_data=CRS03_P_TELEGRAM)],
        [InlineKeyboardButton("TikTok",    callback_data=CRS03_P_TIKTOK),
         InlineKeyboardButton("Twitter/X", callback_data=CRS03_P_TWITTER)],
        [InlineKeyboardButton("YouTube",   callback_data=CRS03_P_YOUTUBE),
         InlineKeyboardButton("LinkedIn",  callback_data=CRS03_P_LINKEDIN)],
        [InlineKeyboardButton("Discord",   callback_data=CRS03_P_DISCORD),
         InlineKeyboardButton("Other",  callback_data=CRS03_P_OTHER)],
        [InlineKeyboardButton("⏭️ Skip",   callback_data=CRS03_P_SKIP),
         InlineKeyboardButton("↩️ Back",   callback_data=CRS03_P_BACK)],
    ])


async def crs03_platform_prompt(target, ctx):
    """CRS-03 Step 2 • Platform — selection grid."""
    ctx.user_data["state"] = None
    await target.reply_text(
        f"{HDR}\nStep 2 • Platform\n{SEP}\n"
        "Platform\n\nPlease provide the name of the\n"
        "platform or website used in\nthe incident.\n"
        f"{SEP}",
        parse_mode="HTML",
        reply_markup=kb_crs03_platform_select(),
    )


async def crs03_platform_account_prompt(target, ctx, platform_name: str):
    """CRS-03 Step 2 • [Platform] — account input."""
    ctx.user_data["state"] = STATE_PLATFORM_ACCT
    ctx.user_data["crs03_platform_selected"] = platform_name
    info = _CRS03_PLATFORM_PROMPTS.get(platform_name)
    if info:
        step_title, prompt_header, prompt_body, example = info
    else:
        step_title    = f"Step 2 • {platform_name}"
        prompt_header = f"{platform_name} Account"
        prompt_body   = f"Please reply with the\n{platform_name} account:"
        example       = "@john_doe"
    await target.reply_text(
        f"{HDR}\n{step_title}\n{SEP}\n"
        f"{prompt_header}\n\n{prompt_body}\n\n"
        f"Example: {example}\n"
        f"{SEP}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("↩️ Back", callback_data=CRS03_P_ACCT_BACK),
            InlineKeyboardButton("⏭️ Skip", callback_data=CRS03_P_ACCT_SKIP),
        ]]),
    )


async def crs03_platform_other_name_prompt(target, ctx):
    """CRS-03 Step 2 • Other Platform — name input."""
    ctx.user_data["state"] = STATE_PLATFORM_OTHER_NAME
    await target.reply_text(
        f"{HDR}\nStep 2 • Other Platform\n{SEP}\n"
        "Other Platform Name\n\n"
        "Please reply with the\nplatform or website name:\n\n"
        "Example: Zalo\n         Line\n         Viber\n"
        f"{SEP}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("↩️ Back", callback_data=CRS03_P_BACK),
            InlineKeyboardButton("⏭️ Skip", callback_data=CRS03_P_SKIP),
        ]]),
    )


async def crs03_platform_other_acct_prompt(target, ctx):
    """CRS-03 Step 2 • Other Platform — account input."""
    ctx.user_data["state"] = STATE_PLATFORM_OTHER_ACCT
    await target.reply_text(
        f"{HDR}\nStep 2 • Other Platform\n{SEP}\n"
        "Other Platform Account\n\n"
        "Please reply with the\naccount or username:\n\n"
        "Example: @john_doe\n         john.doe@email.com\n"
        f"{SEP}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("↩️ Back", callback_data=CRS03_P_BACK),
        ]]),
    )


async def crs03_profile_url_prompt(target, ctx):
    ctx.user_data["state"] = STATE_PROFILE
    await target.reply_text(
        f"{HDR}\nStep 2 • Profile URL\n{SEP}\n"
        "Profile URL\n\nPlease provide the URL or link\n"
        "to the subject's profile or webpage\ninvolved in the incident.\n\n"
        "Please reply with the URL:\n\n"
        "Example: https://www.facebook.com/username\n         https://t.me/username\n"
        f"{SEP}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⏭️ Skip", callback_data=CRS03_FIELD_SKIP),
            InlineKeyboardButton("↩️ Back", callback_data=CRS03_BACK),
        ]]),
    )


async def crs03_crime_type_menu(target, ctx):
    ctx.user_data["state"] = None
    current = ctx.user_data.get("crime_type")
    await target.reply_text(
        f"{HDR}\nStep 3 • Crime Type\n{SEP}\n"
        "Please select the type of crime\ninvolved in this incident:\n"
        f"{SEP}",
        parse_mode="HTML",
        reply_markup=kb_crs03_crime(current),
    )
