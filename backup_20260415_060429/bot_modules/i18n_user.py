"""
用户端英文文案 — 管理员操作触发推送给报案用户时使用，仅英文
"""

# ── 案件状态变更通知 ───────────────────────────────────
def status_update_notify(case_no: str, status: str, desc: str, updated_ts: str = "", auth_id: str = "") -> str:
    return (
        "IC3 · CASE STATUS UPDATE\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Case ID: <code>{case_no}</code>\n"
        f"Status: <b>{status}</b>\n"
        f"Updated: {updated_ts}\n\n"
        f"<i>{desc}</i>\n\n"
        f"Auth Ref: <code>{auth_id}</code>"
    )

STATUS_DESCRIPTIONS = {
    "SUBMITTED": "Your complaint has been securely logged.",
    "VALIDATING": "Automated validation has commenced.",
    "UNDER REVIEW": "A case specialist has been assigned to your case.",
    "REFERRED": "Case referred to field office / exchange.",
    "CLOSED": "Case resolved and archived.",
}

# ── 探员分配通知 ────────────────────────────────────────
def agent_assigned_notify(case_no: str, agent_code: str) -> str:
    return (
        "IC3 · CASE STATUS UPDATE\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Case ID: <code>{case_no}</code>\n"
        f"Assigned Agent: <code>{agent_code}</code>\n\n"
        "A case specialist has been assigned to your case.\n"
        "You may receive further communication from the assigned agent."
    )

# ── 联络通道 ────────────────────────────────────────────
LIAISON_OPENED = (
    "SECURE LIAISON CHANNEL — NOW ACTIVE\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "Case: {case_no}\n"
    "Assigned Agent: {agent_code}\n\n"
    "A secure communication channel has been opened\n"
    "for this case. You may reply directly below.\n\n"
    "Channel active for 24 hours."
)

LIAISON_CLOSED = (
    "SECURE LIAISON — CHANNEL CLOSED\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "Case: {case_no}\n\n"
    "The secure communication channel has been closed.\n"
    "All communications have been archived."
)

# ── 用户管理操作通知（管理员触发，仅英文）────────────────
USER_SUSPENDED_NOTIFY = (
    "IC3 · ACCOUNT NOTICE\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "Your account has been temporarily suspended.\n\n"
    "Contact support for details."
)
USER_RESUMED_NOTIFY = (
    "IC3 · ACCOUNT NOTICE\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "Your account access has been restored."
)
