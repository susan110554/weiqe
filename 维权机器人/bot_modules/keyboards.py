"""
FBI IC3 – ADRI Bot
All InlineKeyboardMarkup / ReplyKeyboardMarkup builders.
"""
from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton,
)


def kb_main_bottom():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📋 Case Reporting"),   KeyboardButton("🗂 Evidence Upload")],
        [KeyboardButton("🔍 Case Tracking"),    KeyboardButton("⚠️ Risk Analysis")],
        [KeyboardButton("📘 Knowledge Base"),   KeyboardButton("⚖️ Legal Referral")],
        [KeyboardButton("🏛 About & Contact"),  KeyboardButton("🛡 Compliance")],
    ], resize_keyboard=True, input_field_placeholder="Select a module or type a command...")


def kb_home():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Case Reporting",   callback_data="M01"),
         InlineKeyboardButton("🗂 Evidence Upload",  callback_data="M02")],
        [InlineKeyboardButton("🔍 Case Tracking",    callback_data="M03"),
         InlineKeyboardButton("⚠️ Risk Analysis",   callback_data="M04")],
        [InlineKeyboardButton("📘 Knowledge Base",   callback_data="M05"),
         InlineKeyboardButton("⚖️ Legal Referral",  callback_data="M06")],
        [InlineKeyboardButton("🏛 About & Contact",  callback_data="M09"),
         InlineKeyboardButton("🛡 Compliance",       callback_data="M08")],
    ])


def kb_m01():
    """Static M01 keyboard (legacy, shows all CRS sections)."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Identity & Residency",      callback_data="CRS-01")],
        [InlineKeyboardButton("⛓️ Crypto Transaction Data",   callback_data="CRS-02")],
        [InlineKeyboardButton("📱 Platform & Suspect Info",   callback_data="CRS-03")],
        [InlineKeyboardButton("⚖️ Review & Submit Case",      callback_data="CRS-04")],
        [InlineKeyboardButton("⬅️ Return to System Root",     callback_data="HOME")],
    ])


def kb_m01_for_user(completed_sections=None):
    """
    Dynamic M01 keyboard.

    根据用户已经完成的模块，移除对应的按钮。
    completed_sections: 可包含 "CRS-01" / "CRS-02" / "CRS-03"
    """
    completed = set(completed_sections or [])
    rows = []

    if "CRS-01" not in completed:
        rows.append([InlineKeyboardButton("👤 Identity & Residency", callback_data="CRS-01")])
    if "CRS-02" not in completed:
        rows.append([InlineKeyboardButton("⛓️ Crypto Transaction Data", callback_data="CRS-02")])
    if "CRS-03" not in completed:
        rows.append([InlineKeyboardButton("📱 Platform & Suspect Info", callback_data="CRS-03")])

    # Review & Submit 始终保留
    rows.append([InlineKeyboardButton("⚖️ Review & Submit Case",  callback_data="CRS-04")])
    rows.append([InlineKeyboardButton("⬅️ Return to System Root", callback_data="HOME")])
    return InlineKeyboardMarkup(rows)


def kb_crs01_nav():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Previous", callback_data="go_back"),
         InlineKeyboardButton("✖️ Cancel",   callback_data="go_cancel")],
    ])


def kb_crs_attest():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I CERTIFY — TRANSMIT REPORT", callback_data="confirm_submit")],
        [InlineKeyboardButton("✏️ REVISE INFORMATION",          callback_data="CRS-01")],
        [InlineKeyboardButton("❌ TERMINATE SESSION",           callback_data="go_cancel")],
    ])


def kb_m02():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛡️ Identity & Residency Verification",        callback_data="EVM-01")],
        [InlineKeyboardButton("⚖️ Financial Asset & Ledger Evidence",        callback_data="EVM-02")],
        [InlineKeyboardButton("📥 Adversary Communication Records",           callback_data="EVM-03")],
        [InlineKeyboardButton("🔒 Cryptographic Integrity Validation",       callback_data="EVM-04")],
        [InlineKeyboardButton("📂 Addendum to Case Documentation",           callback_data="EVM-05")],
        [InlineKeyboardButton("⬅️ Return to Main Menu", callback_data="HOME")],
    ])


def kb_m02_back_only():
    """仅包含返回 Evidence Upload 菜单的按钮，用于各 EVM 子模块完成后返回上一页。"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Return to Evidence Upload", callback_data="EVM-MENU")],
    ])


def kb_m03():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 Status Inquiry",         callback_data="CTS-01")],
        [InlineKeyboardButton("📊 Processing Timeline",  callback_data="CTS-02")],
        [InlineKeyboardButton("📋 Case Stage Explanation",        callback_data="CTS-03")],
        [InlineKeyboardButton("🏛 Federal Review Guidance",       callback_data="CTS-04")],
        [InlineKeyboardButton("⬅️ Return to Main Menu", callback_data="HOME")],
    ])


def kb_m04():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🕵️ Scam Pattern Identification",   callback_data="RAD-01")],
        [InlineKeyboardButton("🔗 Cryptocurrency Trace Analysis", callback_data="RAD-02")],
        [InlineKeyboardButton("📊 Fraud Severity Scoring",        callback_data="RAD-03")],
        [InlineKeyboardButton("🌐 Cross-border Risk Evaluation",  callback_data="RAD-04")],
        [InlineKeyboardButton("🛡 Victim Exposure Assessment",    callback_data="RAD-05")],
        [InlineKeyboardButton("⬅️ Return to Main Menu", callback_data="HOME")],
    ])


def kb_m05():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📁 Federal Fraud Categories",      callback_data="KBS-01")],
        [InlineKeyboardButton("📢 Public Advisory Bulletins",     callback_data="KBS-02")],
        [InlineKeyboardButton("🛡 Victim Protection Guidelines",  callback_data="KBS-03")],
        [InlineKeyboardButton("🔰 Prevention Framework",          callback_data="KBS-04")],
        [InlineKeyboardButton("📚 Case Study Archive",            callback_data="KBS-05")],
        [InlineKeyboardButton("⬅️ Return to Main Menu", callback_data="HOME")],
    ])


def kb_m06():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏛 Federal Jurisdiction Guide",    callback_data="LRS-01")],
        [InlineKeyboardButton("🗺 Law Enforcement Directory",     callback_data="LRS-02")],
        [InlineKeyboardButton("👔 Attorney Referral Intake",      callback_data="LRS-03")],
        [InlineKeyboardButton("💼 Civil Recovery Pathways",       callback_data="LRS-04")],
        [InlineKeyboardButton("⬅️ Return to Main Menu", callback_data="HOME")],
    ])


def kb_m08():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 Compliance Policy Overview",    callback_data="CMP-01")],
        [InlineKeyboardButton("🔐 Data Security Standards",       callback_data="CMP-02")],
        [InlineKeyboardButton("📋 User Rights & Privacy Notice",  callback_data="CMP-03")],
        [InlineKeyboardButton("⬅️ Return to Main Menu", callback_data="HOME")],
    ])


def kb_m09():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏛 Organizational Overview",          callback_data="ORG-01")],
        [InlineKeyboardButton("📜 Federal Authorization Notice",     callback_data="ORG-02")],
        [InlineKeyboardButton("⚖️ Scope & Limitations",   callback_data="ORG-03")],
        [InlineKeyboardButton("🔐 Data Protection & Privacy", callback_data="ORG-04")],
        [InlineKeyboardButton("📡 Official Contact",                 callback_data="ORG-05")],
        [InlineKeyboardButton("⬅️ Return to Main Menu", callback_data="HOME")],
    ])


def kb_nav(show_back=True):
    row = []
    if show_back:
        row.append(InlineKeyboardButton("⬅️ Previous Step", callback_data="go_back"))
    row.append(InlineKeyboardButton("✖️ Cancel", callback_data="go_cancel"))
    return InlineKeyboardMarkup([row])


def kb_crs_nav(show_back=True):
    row = []
    if show_back:
        row.append(InlineKeyboardButton("⬅️ Previous", callback_data="go_back"))
    row.append(InlineKeyboardButton("✖️ Cancel", callback_data="go_cancel"))
    return InlineKeyboardMarkup([row])


def kb_contact():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Telegram Username", callback_data="ct_tg")],
        [InlineKeyboardButton("📧 Email Address",     callback_data="ct_email")],
        [InlineKeyboardButton("📱 WhatsApp Number",   callback_data="ct_wa")],
        [InlineKeyboardButton("⏭ Skip / Prefer Anonymity", callback_data="ct_skip")],
        [InlineKeyboardButton("⬅️ Previous Step", callback_data="go_back"),
         InlineKeyboardButton("✖️ Cancel",         callback_data="go_cancel")],
    ])


def kb_confirm():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm & Submit Complaint",  callback_data="confirm_submit")],
        [InlineKeyboardButton("✏️ Revise Information",         callback_data="restart")],
        [InlineKeyboardButton("✖️ Cancel Submission",          callback_data="go_cancel")],
    ])


def kb_after_submit(case_id: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📂 Download PDF Summary",        callback_data=f"pdf|{case_id}")],
        [InlineKeyboardButton("🔍 Check Case Status",           callback_data=f"quickcheck|{case_id}")],
        [InlineKeyboardButton("❌ PERMANENTLY CLOSE SESSION",   callback_data="close_session")],
    ])


def kb_admin_case(case_no):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟡 P2 · VALIDATING",          callback_data=f"st|{case_no}|VALIDATING")],
        [InlineKeyboardButton("🔵 P3 · UNDER REVIEW",        callback_data=f"st|{case_no}|UNDER REVIEW")],
        [InlineKeyboardButton("🟢 P4 · REFERRED",            callback_data=f"st|{case_no}|REFERRED")],
        [InlineKeyboardButton("⚫ P5 · CLOSED",              callback_data=f"st|{case_no}|CLOSED")],
        [InlineKeyboardButton("👤 Assign Agent", callback_data=f"assign|{case_no}")],
        [InlineKeyboardButton("💬 Open Liaison Channel",      callback_data=f"liaison_open|{case_no}"),
         InlineKeyboardButton("🔒 Close Channel",             callback_data=f"liaison_close|{case_no}")],
        [InlineKeyboardButton("📨 Send Agent Message",        callback_data=f"agentmsg|{case_no}")],
        [InlineKeyboardButton("📨 Send Status Notification",  callback_data=f"notify|{case_no}")],
        [InlineKeyboardButton("📁 View Evidence Files",       callback_data=f"evlist|{case_no}")],
    ])


def kb_rad02():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔷 ETH / BSC Address (0x...)",    callback_data="RAD-02-ETH")],
        [InlineKeyboardButton("🔴 TRON / TRC20 Address (T...)",  callback_data="RAD-02-TRX")],
        [InlineKeyboardButton("🟡 Bitcoin Address (1/3/bc1...)", callback_data="RAD-02-BTC")],
        [InlineKeyboardButton("⬅️ Return to M04",                callback_data="M04")],
    ])


def kb_upload_case(case_no):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📤 Upload to {case_no}", callback_data=f"upload_set|{case_no}")],
        [InlineKeyboardButton("⬅️ Cancel", callback_data="HOME")],
    ])
