"""
FBI IC3 – ADRI Bot
All InlineKeyboardMarkup / ReplyKeyboardMarkup builders.
"""
from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton,
)

from .config import is_admin

# ── CRS 按钮状态显示：空=icon+名称，已填=✅+短名·值 ─────────────────
def _field_btn(icon: str, label: str, short: str, callback: str, value=None) -> InlineKeyboardButton:
    """空: [icon Label]；已填: [✅ Short · value]"""
    if value and str(value).strip():
        v = str(value).strip()[:20]
        if len(str(value).strip()) > 20:
            v = v + "…"
        text = f"✅ {short} · {v}"
    else:
        text = f"{icon} {label}".lstrip()
    return InlineKeyboardButton(text, callback_data=callback)


def kb_main_bottom(user_id=None):
    """主底部菜单；管理员可见「管理后台」按钮。"""
    rows = [
        [KeyboardButton("Case Reporting"),  KeyboardButton("Evidence Upload")],
        [KeyboardButton("Case Tracking"),   KeyboardButton("Risk Analysis")],
        [KeyboardButton("Knowledge Base"),  KeyboardButton("User Center")],
    ]
    if user_id is not None and is_admin(user_id):
        rows.append([KeyboardButton("管理后台")])
    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
        input_field_placeholder="Select a module or type a command...",
    )


def kb_home(user_id=None):
    """主菜单；管理员可见「管理后台」按钮。"""
    rows = [
        [InlineKeyboardButton("Case Reporting",  callback_data="M01"),
         InlineKeyboardButton("Evidence Upload", callback_data="M02")],
        [InlineKeyboardButton("Case Tracking",   callback_data="M03"),
         InlineKeyboardButton("Risk Analysis",   callback_data="M04")],
        [InlineKeyboardButton("Knowledge Base",  callback_data="M05"),
         InlineKeyboardButton("User Center",     callback_data="M09")],
    ]
    if user_id is not None and is_admin(user_id):
        rows.append([InlineKeyboardButton("管理后台", callback_data="adm|main")])
    return InlineKeyboardMarkup(rows)


def kb_m01():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Complainant Information",       callback_data="CRS-01")],
        [InlineKeyboardButton("Crypto Transaction Data",   callback_data="CRS-02")],
        [InlineKeyboardButton("Platform & Suspect Info",   callback_data="CRS-03")],
        [InlineKeyboardButton("Other Information",         callback_data="CRS-04-OTHER")],
        [InlineKeyboardButton("[🔐 Privacy & Signature]",       callback_data="CRS-04")],
        [InlineKeyboardButton("⬅️ Return to System Root",     callback_data="HOME")],
    ])


def kb_m01_for_user(completed_sections=None):
    """
    Dynamic M01 keyboard — 根据用户已完成的模块隐藏对应按钮。
    completed_sections: 可包含 "CRS-01" / "CRS-02" / "CRS-03"
    """
    completed = set(completed_sections or [])
    rows = []
    if "CRS-01" not in completed:
        rows.append([InlineKeyboardButton("Complainant Information", callback_data="CRS-01")])
    if "CRS-02" not in completed:
        rows.append([InlineKeyboardButton("Financial Transaction(s)", callback_data="CRS-02-TYPE")])
    if "CRS-03" not in completed:
        rows.append([InlineKeyboardButton("Platform & Suspect Info", callback_data="CRS-03")])
    if "CRS-04" not in completed:
        rows.append([InlineKeyboardButton("Other Information",   callback_data="CRS-04-OTHER")])
    rows.append([InlineKeyboardButton("[🔐 Privacy & Signature]", callback_data="CRS-04")])
    rows.append([InlineKeyboardButton("⬅️ Return to System Root", callback_data="HOME")])
    return InlineKeyboardMarkup(rows)


def kb_crs01_menu(d=None):
    """CRS01 子菜单：按钮不显示编码，仅显示名称。d=user_data"""
    d = d or {}
    return InlineKeyboardMarkup([
        [_field_btn("", "Full Legal Name",  "Name",    "CRS01_NAME",  d.get("fullname"))],
        [_field_btn("", "Age",              "Age",     "CRS01_DOB",   d.get("dob"))],
        [_field_btn("", "Physical Address", "Address", "CRS01_ADDR",  d.get("address"))],
        [_field_btn("", "Contact Number",   "Contact", "CRS01_PHONE", d.get("phone"))],
        [_field_btn("", "Email Address",    "Email",   "CRS01_EMAIL", d.get("email"))],
        [InlineKeyboardButton("✅ Submit", callback_data="CRS01_DONE"),
         InlineKeyboardButton("⬅️ Back", callback_data="CRS01_BACK")],
    ])


def kb_crs03_menu(d=None):
    """CRS-03 子菜单：4 个字段入口。d=user_data"""
    d = d or {}
    return InlineKeyboardMarkup([
        [_field_btn("", "Contact Info / Platform", "Platform", "CRS03_CONTACT", d.get("platform"))],
        [_field_btn("", "Profile URL", "Profile", "CRS03_PROFILE", d.get("profile_url"))],
        [_field_btn("", "Crime Type", "Crime", "CRS03_CRIME", d.get("crime_type"))],
        [InlineKeyboardButton("✅ Continue", callback_data="CRS03_DONE"),
         InlineKeyboardButton("⬅️ Back", callback_data="go_back")],
    ])


def _crs04_witnesses_field_value(d):
    """Witnesses 行：优先结构化列表 / 跳过标记。"""
    if d.get("crs04_witnesses_skipped"):
        return "Skipped"
    lst = d.get("crs04_witnesses_list") or []
    if lst:
        return f"{len(lst)} witness(es)"
    return d.get("witnesses")


def kb_crs04_other(d=None):
    """CRS-04 Other Information 子菜单。d=user_data"""
    d = d or {}
    return InlineKeyboardMarkup([
        [_field_btn("", "Incident Narrative",       "Narrative", "CRS04_NARRATIVE", d.get("incident_story"))],
        [_field_btn("", "Prior Reports to Agencies","Reports",   "CRS04_PRIOR",     d.get("prior_reports_flag"))],
        [_field_btn("", "Witnesses & Others",       "Witnesses", "CRS04_WITNESSES", _crs04_witnesses_field_value(d))],
        [InlineKeyboardButton("✅ Submit", callback_data="CRS04_OTHER_SAVE"),
         InlineKeyboardButton("⬅️ Back",    callback_data="CRS04_OTHER_BACK")],
    ])


def kb_phone():
    """CRS-01 联系方式选择。仅保留 Email（必填）与 Phone（选填）。"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Email (Required)", callback_data="PHONE_EMAIL"),
         InlineKeyboardButton("Phone", callback_data="PHONE_DIRECT")],
        [InlineKeyboardButton("✅ Done", callback_data="PHONE_DONE"),
         InlineKeyboardButton("⬅️ Back", callback_data="PHONE_BACK")],
    ])


def kb_crs03_crime():
    """CRS-03 犯罪类型选择。"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Investment Fraud", callback_data="CRS03_CRIME_INVEST")],
        [InlineKeyboardButton("Impersonation Scam", callback_data="CRS03_CRIME_IMPERSON")],
        [InlineKeyboardButton("Crypto / Mining Fraud", callback_data="CRS03_CRIME_CRYPTO")],
        [InlineKeyboardButton("Payment / Wire Fraud", callback_data="CRS03_CRIME_WIRE")],
        [InlineKeyboardButton("Account Takeover", callback_data="CRS03_CRIME_TAKEOVER")],
        [InlineKeyboardButton("Non-Delivery of Goods", callback_data="CRS03_CRIME_NOND")],
        [InlineKeyboardButton("Other", callback_data="CRS03_CRIME_OTHER")],
        [InlineKeyboardButton("⬅️ Back", callback_data="go_back")],
    ])


def kb_fraud_type():
    """欺诈类型选择按钮 — CRS-03 第一步。"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Investment Fraud", callback_data="FRAUD-TYPE|INVESTMENT")],
        [InlineKeyboardButton("Impersonation Scam", callback_data="FRAUD-TYPE|IMPERSONATION")],
        [InlineKeyboardButton("Crypto / Mining Fraud", callback_data="FRAUD-TYPE|CRYPTO_MINING")],
        [InlineKeyboardButton("Payment / Wire Fraud", callback_data="FRAUD-TYPE|PAYMENT_WIRE")],
        [InlineKeyboardButton("Account Takeover", callback_data="FRAUD-TYPE|ACCOUNT_TAKEOVER")],
        [InlineKeyboardButton("Non-Delivery of Goods", callback_data="FRAUD-TYPE|NON_DELIVERY")],
        [InlineKeyboardButton("Other", callback_data="FRAUD-TYPE|OTHER")],
        [InlineKeyboardButton("⬅️ Previous", callback_data="go_back"),
         InlineKeyboardButton("✖️ Cancel", callback_data="go_cancel")],
    ])


def kb_crs01_nav():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Previous", callback_data="go_back"),
         InlineKeyboardButton("✖️ Cancel",   callback_data="go_cancel")],
    ])


def kb_crs_attest():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I CERTIFY — TRANSMIT REPORT", callback_data="confirm_submit")],
        [InlineKeyboardButton("✏️ REVISE INFORMATION",          callback_data="CRS-01")],
        [InlineKeyboardButton("TERMINATE SESSION",           callback_data="go_cancel")],
    ])


def kb_signature_request(expanded: bool = False):
    """Digital Signature Request: 展开/收起全文 + Sign & Submit / Cancel。"""
    toggle = (
        InlineKeyboardButton("📕 Hide full statement", callback_data="SIGREQ_COLLAPSE")
        if expanded
        else InlineKeyboardButton(
            "📖 Show full privacy & signature statement",
            callback_data="SIGREQ_EXPAND",
        )
    )
    return InlineKeyboardMarkup([
        [toggle],
        [InlineKeyboardButton("✅ Digital Signature", callback_data="sign_and_submit")],
        [InlineKeyboardButton("Cancel", callback_data="cancel_submit")],
    ])


def kb_pin_pad(show_forgot: bool = False):
    """6-digit PIN entry: number pad + Delete + Confirm (+ optional Forgot PIN)."""
    rows = [
        [
            InlineKeyboardButton("1", callback_data="pin|1"),
            InlineKeyboardButton("2", callback_data="pin|2"),
            InlineKeyboardButton("3", callback_data="pin|3"),
        ],
        [
            InlineKeyboardButton("4", callback_data="pin|4"),
            InlineKeyboardButton("5", callback_data="pin|5"),
            InlineKeyboardButton("6", callback_data="pin|6"),
        ],
        [
            InlineKeyboardButton("7", callback_data="pin|7"),
            InlineKeyboardButton("8", callback_data="pin|8"),
            InlineKeyboardButton("9", callback_data="pin|9"),
        ],
        [InlineKeyboardButton("0", callback_data="pin|0")],
        [
            InlineKeyboardButton("⌫ Delete", callback_data="pin|del"),
            InlineKeyboardButton("✅ Confirm", callback_data="pin|confirm"),
        ],
    ]
    if show_forgot:
        rows.append([InlineKeyboardButton("Forgot PIN?", callback_data="pin|forgot")])
    return InlineKeyboardMarkup(rows)


def kb_recovery_menu():
    """Account Recovery: Email, Case ID, Back."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Email Verification", callback_data="recovery|email")],
        [InlineKeyboardButton("Case ID Verification", callback_data="recovery|caseid")],
        [InlineKeyboardButton("⬅️ Back", callback_data="recovery|back")],
    ])


def kb_recovery_email_resend():
    """Resend Code, Back."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Resend Code", callback_data="recovery|resend"),
            InlineKeyboardButton("⬅️ Back", callback_data="recovery|back"),
        ],
    ])


def kb_recovery_back():
    """Back only."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="recovery|back")],
    ])


def kb_recovery_try_again():
    """Try Again, Back (for wrong code)."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Try Again", callback_data="recovery|tryagain"),
            InlineKeyboardButton("⬅️ Back", callback_data="recovery|back"),
        ],
    ])


def kb_recovery_main_menu():
    """Return to Main Menu."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Return to Main Menu", callback_data="recovery|main")],
    ])


def kb_certificate_actions(case_id: str):
    """STEP 3 — Certificate actions."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Download PDF", callback_data=f"pdf|{case_id}")],
        [InlineKeyboardButton("Verify Signature", callback_data="cert|verify")],
        [InlineKeyboardButton("Send to My Email", callback_data=f"cert|email|{case_id}")],
        [InlineKeyboardButton("✅ Done", callback_data="cert|done")],
    ])


def kb_cert_email_existing(case_id: str):
    """STEP 1 — 发送到已有邮箱：确认/更换/取消。"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Send to This Email", callback_data=f"cert|email_yes|{case_id}")],
        [InlineKeyboardButton("✏️ Use a Different Email",  callback_data=f"cert|email_other|{case_id}")],
        [InlineKeyboardButton("Cancel",                  callback_data=f"cert|email_cancel|{case_id}")],
    ])


def kb_cert_email_confirm_new(case_id: str):
    """STEP 2B — 新邮箱确认发送。"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm", callback_data=f"cert|email_confirm_new|{case_id}")],
        [InlineKeyboardButton("Cancel",  callback_data=f"cert|email_cancel|{case_id}")],
    ])


def kb_m02():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Submit Certified Identity Credentials", callback_data="EVM-01")],
        [InlineKeyboardButton("Upload Financial Transaction History", callback_data="EVM-02")],
        [InlineKeyboardButton("Upload Subject Correspondence Files", callback_data="EVM-03")],
        [InlineKeyboardButton("Submit Additional Evidence Materials", callback_data="EVM-05")],
        [InlineKeyboardButton("Return to Main Menu", callback_data="HOME")],
    ])


def kb_m02_back_only():
    """仅包含返回 Evidence Upload 菜单的按钮。"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Return to Evidence Upload", callback_data="EVM-MENU")],
    ])


def kb_evm_seal():
    """证据封存按钮：点击后执行 do_evm_seal。"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("SEAL & Finalize Module", callback_data="evm_seal")],
        [InlineKeyboardButton("Return to Evidence Upload", callback_data="EVM-MENU")],
    ])


def kb_evm_continue():
    """EVM-01 证件上传完成后：进入补充证据 EVM-05。"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Continue", callback_data="evm_continue")],
        [InlineKeyboardButton("Return to Evidence Upload", callback_data="EVM-MENU")],
    ])


def m03_federal_fees_unlocked(case_status: str | None) -> bool:
    """
    CTS-03 (Pending Federal Fees) unlocks when simulated progress >= 75%.
    Aligns with M03-CTS-02 pipeline stages in bot.py.
    """
    if not case_status:
        return False
    raw = str(case_status).strip()
    legacy = {
        "Pending Initial Review": "SUBMITTED",
        "待初步审核": "SUBMITTED",
        "Under Review": "UNDER REVIEW",
        "Case Accepted": "UNDER REVIEW",
        "Processing Complete": "REFERRED",
        "Case Closed": "CLOSED",
        "PENDING": "SUBMITTED",
        "Pending": "SUBMITTED",
    }
    cur = legacy.get(raw, raw)
    pct_map = {
        "SUBMITTED": 20,
        "VALIDATING": 40,
        "UNDER REVIEW": 75,
        "REFERRED": 88,
        "CLOSED": 100,
    }
    return pct_map.get(cur, 0) >= 75


def kb_m03(
    user_data: dict | None = None,
    case: dict | None = None,
    *,
    hide_cts02_nav: bool = False,
):
    """
    M03 Case Tracking — CTS-01..04 + HOME.
    CTS-03 only when federal-fee window unlocks (>=75% progress); 未解锁时不占位（无 [LOCKED] 假按钮）。
    hide_cts02_nav: 已在 CTS-02 流水线屏时置 True，避免与 [▼Expand Real-Time Progress] 重复。
    """
    ud = user_data or {}
    st = (case or {}).get("status") if case else None
    unlocked = m03_federal_fees_unlocked(st) or bool(ud.get("m03_cts_fees_unlocked"))

    rows: list = [
        [InlineKeyboardButton("Case Overview", callback_data="CTS-01")],
    ]
    if not hide_cts02_nav:
        rows.append(
            [InlineKeyboardButton("[▼ Real-Time Progress]", callback_data="CTS-02")]
        )
    if unlocked:
        rows.append(
            [
                InlineKeyboardButton(
                    "NEW · Pending Federal Fees",
                    callback_data="CTS-03",
                )
            ]
        )
    rows.append([InlineKeyboardButton("Evidence Files", callback_data="CTS-04")])
    rows.append([InlineKeyboardButton("⬅️ Return to Main Menu", callback_data="HOME")])
    return InlineKeyboardMarkup(rows)


def kb_cts03_fees():
    """CTS-03 · Pending Federal Fees — sub-menu (English labels)."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "Court Filing Fee — $450.00",
            callback_data="CTS03_FEE_FILING",
        )],
        [InlineKeyboardButton(
            "Bank Freeze Execution — $850.00",
            callback_data="CTS03_FEE_BANK",
        )],
        [InlineKeyboardButton(
            "Asset Release Processing — $1,500.00",
            callback_data="CTS03_FEE_UNFREEZE",
        )],
        [InlineKeyboardButton(
            "Pay All Fees ($2,800.00)",
            callback_data="CTS03_FEE_PAY_ALL",
        )],
        [InlineKeyboardButton("⬅️ Back to Case Tracking", callback_data="M03")],
    ])


def kb_m04():
    """M04 Risk Analysis — RAD-01 / RAD-02 / RAD-03."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Scam Pattern Identification",  callback_data="RAD-01")],
        [InlineKeyboardButton("Crypto Address Trace",         callback_data="RAD-02")],
        [InlineKeyboardButton("Case Risk Score Report",       callback_data="RAD-03")],
        [InlineKeyboardButton("⬅️ Return to Main Menu",       callback_data="HOME")],
    ])


def kb_m05():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Federal Fraud Categories",      callback_data="KBS-01")],
        [InlineKeyboardButton("Public Advisory Bulletins",     callback_data="KBS-02")],
        [InlineKeyboardButton("Victim Protection Guidelines",  callback_data="KBS-03")],
        [InlineKeyboardButton("Prevention Framework",          callback_data="KBS-04")],
        [InlineKeyboardButton("Case Study Archive",            callback_data="KBS-05")],
        [InlineKeyboardButton("⬅️ Return to Main Menu", callback_data="HOME")],
    ])




def kb_m09():
    """User Center main menu — delegates to user_center.kb_uc_main()."""
    from .user_center import kb_uc_main
    return kb_uc_main()


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
        [InlineKeyboardButton("Telegram Username", callback_data="ct_tg")],
        [InlineKeyboardButton("Email Address",     callback_data="ct_email")],
        [InlineKeyboardButton("WhatsApp Number",   callback_data="ct_wa")],
        [InlineKeyboardButton("Skip / Prefer Anonymity", callback_data="ct_skip")],
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
        [InlineKeyboardButton("Download PDF Summary",        callback_data=f"pdf|{case_id}")],
        [InlineKeyboardButton("Check Case Status",           callback_data=f"quickcheck|{case_id}")],
        [InlineKeyboardButton("PERMANENTLY CLOSE SESSION",   callback_data="close_session")],
    ])


def kb_admin_case(case_no):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚪ P1 · SUBMITTED",                  callback_data=f"st|{case_no}|SUBMITTED")],
        [InlineKeyboardButton("🟡 P2 · PENDING REVIEW",             callback_data=f"st|{case_no}|PENDING REVIEW")],
        [InlineKeyboardButton("🔵 P3 · CASE ACCEPTED",              callback_data=f"st|{case_no}|CASE ACCEPTED")],
        [InlineKeyboardButton("🟢 P4 · REFERRED TO LAW ENFORCEMENT",callback_data=f"st|{case_no}|REFERRED TO LAW ENFORCEMENT")],
        [InlineKeyboardButton("⚫ P5 · IDENTITY VERIFICATION",      callback_data=f"st|{case_no}|IDENTITY VERIFICATION")],
        [InlineKeyboardButton("🟠 P6 · PRELIMINARY REVIEW",         callback_data=f"st|{case_no}|PRELIMINARY REVIEW")],
        [InlineKeyboardButton("🔴 P7 · ASSET TRACING",              callback_data=f"st|{case_no}|ASSET TRACING")],
        [InlineKeyboardButton("🟣 P8 · LEGAL DOCUMENTATION",        callback_data=f"st|{case_no}|LEGAL DOCUMENTATION")],
        [InlineKeyboardButton("Assign Agent",     callback_data=f"assign|{case_no}")],
        [InlineKeyboardButton("Open Liaison Channel",      callback_data=f"liaison_open|{case_no}"),
         InlineKeyboardButton("🔒 Close Channel",             callback_data=f"liaison_close|{case_no}")],
        [InlineKeyboardButton("Send Agent Message",        callback_data=f"agentmsg|{case_no}")],
        [InlineKeyboardButton("Send Status Notification",  callback_data=f"notify|{case_no}")],
        [InlineKeyboardButton("View Evidence Files",       callback_data=f"evlist|{case_no}")],
        [InlineKeyboardButton("Refresh PDF",               callback_data=f"adm|case|refresh_pdf|{case_no}")],
    ])


def kb_rad02():
    """RAD-02 blockchain network selector."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ETH / ERC-20 / BSC",  callback_data="RAD-02-ETH")],
        [InlineKeyboardButton("TRON / TRC-20",        callback_data="RAD-02-TRX")],
        [InlineKeyboardButton("Bitcoin",              callback_data="RAD-02-BTC")],
        [InlineKeyboardButton("⬅️ Back to Risk Analysis", callback_data="M04")],
    ])


def kb_rad02_result_followup(explorer_url: str | None = None, case_id: str | None = None):
    """RAD-02 post-result actions."""
    rows = []
    if explorer_url:
        rows.append([InlineKeyboardButton("View on Block Explorer", url=explorer_url)])
    rows.append([InlineKeyboardButton("View Evidence Detail",    callback_data="view_evidence_detail")])
    rows.append([InlineKeyboardButton("⬅️ Back to Risk Analysis", callback_data="M04")])
    return InlineKeyboardMarkup(rows)


def kb_upload_case(case_no):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Upload to {case_no}", callback_data=f"upload_set|{case_no}")],
        [InlineKeyboardButton("⬅️ Cancel", callback_data="HOME")],
    ])
