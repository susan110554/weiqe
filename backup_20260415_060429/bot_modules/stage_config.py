"""
bot_modules/stage_config.py
P1-P10 阶段配置（纯代码，无需新建数据库表）
每个阶段定义：进度%、标签、流水线文本、收据正文、邮件模板、状态匹配集
"""
from __future__ import annotations

# ─── 单阶段数据结构 ────────────────────────────────────────────────────────────
# {
#   key, icon, pct, label, status_line, module,
#   pipeline_items: [(section_title, [line, ...]), ...],
#   receipt_body, email_subject, email_body,
#   status_set: frozenset
# }

STAGE_LIST: list[dict] = [

    # ── P1 ──────────────────────────────────────────────────────────────────────
    {
        "key":         "P1",
        "icon":        "⚪",
        "pct":         10,
        "label":       "P1 · SUBMITTED",
        "status_line": "SUBMITTED TO IC3",
        "module":      "M03-CTS Intake & Screening",
        "badge":       "🟡 SUBMITTED  │  PENDING INTAKE",
        "pipeline_items": [
            ("📥 DATA INGESTION", [
                "Encrypted record created. [{ts}]",
                "Case ID: {case_id} assigned.",
                "User notification sent via secure channel.",
            ]),
            ("🔍 INITIAL SCREENING", [
                "Fraud classification module loaded.",
                "Keyword match: [CRYPTO / INVESTMENT SCAM]",
                "(Match Confidence: High)",
            ]),
            ("🔄 NEXT STEPS", [
                "Routing to Intake Officer #2847 (Est. 24h).",
            ]),
        ],
        "receipt_body": (
            "Your complaint has been successfully filed\n"
            "with the Internet Crime Complaint Center.\n"
            "Your case has been entered into the IC3\n"
            "federal database and is pending assignment\n"
            "to an investigative team."
        ),
        "email_subject": "[IC3] Complaint Filed — Case {case_id}",
        "email_body": (
            "Your IC3 complaint has been successfully submitted.\n\n"
            "Case ID : {case_id}\n"
            "Status  : P1 · SUBMITTED\n"
            "Filed   : {ts}\n\n"
            "Your case is now in our federal database and pending\n"
            "assignment to an investigative team.\n\n"
            "Please retain your Case ID for all future correspondence."
        ),
        "status_set": frozenset({
            "SUBMITTED", "Pending Initial Review",
            "待初步审核", "PENDING", "Pending",
        }),
    },

    # ── P2 ──────────────────────────────────────────────────────────────────────
    {
        "key":         "P2",
        "icon":        "🔵",
        "pct":         20,
        "label":       "P2 · VALIDATING",
        "status_line": "RECORD VALIDATION IN PROGRESS",
        "module":      "M03-CTS Record Validation",
        "badge":       "🔵 VALIDATING  │  DATA VERIFICATION",
        "pipeline_items": [
            ("🗂 RECORD VALIDATION", [
                "CRS form data integrity confirmed. [{ts}]",
                "Case ID: {case_id} — schema validated.",
                "Timestamp cross-reference: PASS.",
            ]),
            ("⚖️ COMPLIANCE SCREENING", [
                "Duplicate case check: NO CONFLICT.",
                "Jurisdictional screening: US FEDERAL.",
                "Priority flag: STANDARD.",
            ]),
            ("🔄 NEXT STEPS", [
                "Queued for analyst assignment (Est. 48h).",
            ]),
        ],
        "receipt_body": (
            "Your case record is being validated by the\n"
            "IC3 Intake System. All submitted data is\n"
            "undergoing integrity and compliance checks\n"
            "before analyst assignment."
        ),
        "email_subject": "[IC3] Case Validation In Progress — {case_id}",
        "email_body": (
            "Your IC3 case is currently being validated.\n\n"
            "Case ID : {case_id}\n"
            "Status  : P2 · VALIDATING\n"
            "Updated : {ts}\n\n"
            "All submitted data is undergoing integrity and\n"
            "compliance checks. No action is required from you."
        ),
        "status_set": frozenset({"VALIDATING", "PENDING REVIEW"}),
    },

    # ── P3 ──────────────────────────────────────────────────────────────────────
    {
        "key":         "P3",
        "icon":        "🟡",
        "pct":         30,
        "label":       "P3 · UNDER REVIEW",
        "status_line": "CASE UNDER ACTIVE REVIEW",
        "module":      "M03-CTS Case Analysis",
        "badge":       "🟡 UNDER REVIEW  │  ANALYST ASSIGNED",
        "pipeline_items": [
            ("👤 ANALYST ASSIGNMENT", [
                "Senior analyst assigned. [{ts}]",
                "Case {case_id} — classification: PRIORITY.",
                "Evidence package opened for review.",
            ]),
            ("📋 PRELIMINARY ASSESSMENT", [
                "Fraud vector identified: CRYPTO SCAM.",
                "Transaction timeline reconstructed.",
                "Victim profile: VERIFIED.",
            ]),
            ("🔄 NEXT STEPS", [
                "Escalation decision pending (Est. 48–72h).",
            ]),
        ],
        "receipt_body": (
            "Your case has been assigned to an IC3 analyst\n"
            "and is currently under active review. Our team\n"
            "is analyzing all submitted evidence and data\n"
            "to build a complete case file."
        ),
        "email_subject": "[IC3] Case Under Review — {case_id}",
        "email_body": (
            "Your IC3 case is now under active review.\n\n"
            "Case ID : {case_id}\n"
            "Status  : P3 · UNDER REVIEW\n"
            "Updated : {ts}\n\n"
            "An analyst has been assigned to your case and is\n"
            "reviewing all submitted evidence. You will be\n"
            "notified of any updates."
        ),
        "status_set": frozenset({
            "UNDER REVIEW", "Under Review",
            "Case Accepted", "CASE ACCEPTED",
        }),
    },

    # ── P4 ──────────────────────────────────────────────────────────────────────
    {
        "key":         "P4",
        "icon":        "🟠",
        "pct":         40,
        "label":       "P4 · REFERRED",
        "status_line": "REFERRED TO LAW ENFORCEMENT",
        "module":      "M04-CTS Law Enforcement Referral",
        "badge":       "🟠 REFERRED  │  ENFORCEMENT NOTIFIED",
        "pipeline_items": [
            ("📤 REFERRAL PROCESSED", [
                "Case {case_id} forwarded. [{ts}]",
                "Receiving agency: FBI Cyber Division.",
                "Referral packet: ENCRYPTED & TRANSMITTED.",
            ]),
            ("🤝 AGENCY COORDINATION", [
                "Inter-agency contact established.",
                "Case priority flag: HIGH.",
                "Coordination reference: FBI-CYB-{case_id[:8]}.",
            ]),
            ("🔄 NEXT STEPS", [
                "Awaiting agency intake confirmation (Est. 72h).",
            ]),
        ],
        "receipt_body": (
            "Your case has been formally referred to a law\n"
            "enforcement agency for further action. The\n"
            "referring IC3 analyst has transmitted your\n"
            "complete case file to the receiving agency."
        ),
        "email_subject": "[IC3] Case Referred to Law Enforcement — {case_id}",
        "email_body": (
            "Your IC3 case has been referred to law enforcement.\n\n"
            "Case ID : {case_id}\n"
            "Status  : P4 · REFERRED\n"
            "Updated : {ts}\n\n"
            "Your complete case file has been transmitted to the\n"
            "FBI Cyber Division. Retain your Case ID for all\n"
            "future correspondence."
        ),
        "status_set": frozenset({
            "REFERRED", "REFERRED TO LAW ENFORCEMENT",
            "Processing Complete",
        }),
    },

    # ── P5 ──────────────────────────────────────────────────────────────────────
    {
        "key":         "P5",
        "icon":        "🔷",
        "pct":         50,
        "label":       "P5 · IDENTITY VERIFICATION",
        "status_line": "IDENTITY VERIFICATION REQUIRED",
        "module":      "M05-IDV Identity Verification",
        "badge":       "🔷 IDV ACTIVE  │  ACTION REQUIRED",
        "pipeline_items": [
            ("🪪 IDENTITY CHECK INITIATED", [
                "IDV protocol activated. [{ts}]",
                "Case {case_id} — KYC compliance required.",
                "Verification window: 72 hours.",
            ]),
            ("📋 REQUIREMENTS", [
                "Government-issued photo ID.",
                "Selfie verification (live capture).",
                "Address proof document.",
            ]),
            ("🔄 NEXT STEPS", [
                "Submit identity documents via secure portal.",
                "Processing time: 24–48h upon submission.",
            ]),
        ],
        "receipt_body": (
            "Identity verification is required to proceed\n"
            "with your case. This is a mandatory compliance\n"
            "step under federal anti-fraud protocols.\n"
            "Please submit your documents via the secure\n"
            "verification portal."
        ),
        "email_subject": "[IC3] Identity Verification Required — {case_id}",
        "email_body": (
            "Action required: Identity verification for your IC3 case.\n\n"
            "Case ID : {case_id}\n"
            "Status  : P5 · IDENTITY VERIFICATION\n"
            "Updated : {ts}\n\n"
            "Please submit your identity documents via the secure\n"
            "portal to proceed with your case. Failure to verify\n"
            "within 72 hours may result in case suspension."
        ),
        "status_set": frozenset({
            "P5", "P5 IDENTITY VERIFICATION", "IDENTITY VERIFICATION",
            "Identity Verification", "P5 Identity Verification",
            "EVIDENCE VERIFICATION",
        }),
    },

    # ── P6 ──────────────────────────────────────────────────────────────────────
    {
        "key":         "P6",
        "icon":        "🔬",
        "pct":         60,
        "label":       "P6 · FORENSIC REVIEW",
        "status_line": "FORENSIC ANALYSIS IN PROGRESS",
        "module":      "M06-FSR Forensic & Blockchain Review",
        "badge":       "🔬 FORENSICS  │  BLOCKCHAIN ANALYSIS",
        "pipeline_items": [
            ("⛓ BLOCKCHAIN ANALYSIS", [
                "Chainalysis engine activated. [{ts}]",
                "Case {case_id} — transaction graph loaded.",
                "On-chain attribution: IN PROGRESS.",
            ]),
            ("🗺 TRANSACTION MAPPING", [
                "Suspect wallet cluster identified.",
                "Cross-exchange tracing: 3 hops detected.",
                "Jurisdiction flag: OFFSHORE EXCHANGE.",
            ]),
            ("🔄 NEXT STEPS", [
                "Forensic report generation (Est. 48h).",
                "Asset recovery pathway assessment.",
            ]),
        ],
        "receipt_body": (
            "Forensic blockchain analysis has been initiated\n"
            "on your case. Our Chainalysis-powered system is\n"
            "tracing all associated transactions and mapping\n"
            "the suspect wallet cluster."
        ),
        "email_subject": "[IC3] Forensic Review Initiated — {case_id}",
        "email_body": (
            "Forensic blockchain analysis has been initiated for your case.\n\n"
            "Case ID : {case_id}\n"
            "Status  : P6 · FORENSIC REVIEW\n"
            "Updated : {ts}\n\n"
            "Our forensic system is actively tracing all transactions\n"
            "associated with your case. No action is required from you."
        ),
        "status_set": frozenset({
            "P6", "P6 PRELIMINARY REVIEW", "PRELIMINARY REVIEW",
            "Preliminary Review", "FORENSICS REVIEW",
            "Forensic Review", "P6 Preliminary Review",
        }),
    },

    # ── P7 ──────────────────────────────────────────────────────────────────────
    {
        "key":         "P7",
        "icon":        "🔍",
        "pct":         70,
        "label":       "P7 · ASSET TRACING",
        "status_line": "ASSET TRACING ACTIVE",
        "module":      "M07-ATR Asset Tracing & Recovery",
        "badge":       "🔍 TRACING  │  RECOVERY PATHWAY OPEN",
        "pipeline_items": [
            ("💰 ASSET IDENTIFICATION", [
                "Target wallets flagged. [{ts}]",
                "Case {case_id} — {amt} under trace.",
                "TRC20/ERC20 clusters: MAPPED.",
            ]),
            ("🧊 FREEZE REQUEST", [
                "Exchange freeze request: SUBMITTED.",
                "Cooperation status: PENDING RESPONSE.",
                "Legal hold reference: LH-{case_id[:6]}.",
            ]),
            ("🔄 NEXT STEPS", [
                "Wallet address verification required.",
                "Submit recovery wallet via secure portal.",
            ]),
        ],
        "receipt_body": (
            "Asset tracing is actively underway for your case.\n"
            "The suspect wallet cluster has been identified and\n"
            "freeze requests have been submitted to the\n"
            "relevant exchanges."
        ),
        "email_subject": "[IC3] Asset Tracing Active — {case_id}",
        "email_body": (
            "Asset tracing is now active for your IC3 case.\n\n"
            "Case ID : {case_id}\n"
            "Status  : P7 · ASSET TRACING\n"
            "Updated : {ts}\n\n"
            "The suspect wallet cluster has been identified.\n"
            "Please provide your recovery wallet address\n"
            "via the secure portal when prompted."
        ),
        "status_set": frozenset({
            "P7", "P7 ASSET TRACING", "ASSET TRACING",
            "Asset Tracing", "PENDING ALLOCATION",
        }),
    },

    # ── P8 ──────────────────────────────────────────────────────────────────────
    {
        "key":         "P8",
        "icon":        "📜",
        "pct":         80,
        "label":       "P8 · LEGAL DOCUMENTATION",
        "status_line": "LEGAL DOCUMENTATION IN PROGRESS",
        "module":      "M08-LEG Legal Documentation",
        "badge":       "📜 LEGAL  │  DOCUMENTATION ACTIVE",
        "pipeline_items": [
            ("⚖️ LEGAL FRAMEWORK", [
                "Case brief prepared. [{ts}]",
                "Case {case_id} — DOJ coordination: ACTIVE.",
                "18 U.S.C. § 1343 — Wire Fraud: APPLICABLE.",
            ]),
            ("🏛 COMPLIANCE REVIEW", [
                "Forfeiture motion: DRAFTED.",
                "Inter-agency memo: TRANSMITTED.",
                "Court referral package: ASSEMBLED.",
            ]),
            ("🔄 NEXT STEPS", [
                "Complainant wallet address submission required.",
                "Recovery authorization pending legal sign-off.",
            ]),
        ],
        "receipt_body": (
            "Legal documentation is being prepared for your\n"
            "case. DOJ coordination is active and the legal\n"
            "framework for asset recovery is being assembled.\n"
            "Please submit your wallet address when prompted."
        ),
        "email_subject": "[IC3] Legal Documentation In Progress — {case_id}",
        "email_body": (
            "Legal documentation is being prepared for your IC3 case.\n\n"
            "Case ID : {case_id}\n"
            "Status  : P8 · LEGAL DOCUMENTATION\n"
            "Updated : {ts}\n\n"
            "DOJ coordination is active. You may be prompted to\n"
            "provide your wallet address for asset recovery processing."
        ),
        "status_set": frozenset({
            "P8", "P8 LEGAL", "LEGAL DOCUMENTATION",
            "Legal Documentation", "PENDING WALLET ADDRESS",
        }),
    },

    # ── P9 ──────────────────────────────────────────────────────────────────────
    {
        "key":         "P9",
        "icon":        "💸",
        "pct":         90,
        "label":       "P9 · FUND DISBURSEMENT",
        "status_line": "FUND DISBURSEMENT AUTHORIZED",
        "module":      "M09-DSB Fund Disbursement",
        "badge":       "💸 DISBURSEMENT  │  PROCESSING",
        "pipeline_items": [
            ("✅ DISBURSEMENT AUTHORIZED", [
                "Recovery package approved. [{ts}]",
                "Case {case_id} — disbursement order issued.",
                "Amount: {amt} — routing confirmed.",
            ]),
            ("🏦 PAYMENT PROCESSING", [
                "Contractor fee clearance: REQUIRED.",
                "Third-party verification: IN PROGRESS.",
                "Estimated processing: 24–48h.",
            ]),
            ("🔄 NEXT STEPS", [
                "Complete contractor fee payment to release funds.",
                "Reference your Case ID in all correspondence.",
            ]),
        ],
        "receipt_body": (
            "Fund disbursement has been authorized for your\n"
            "case. The recovery amount is being processed\n"
            "through the federal contractor payment system.\n"
            "Please complete any pending fee requirements."
        ),
        "email_subject": "[IC3] Fund Disbursement Authorized — {case_id}",
        "email_body": (
            "Fund disbursement has been authorized for your IC3 case.\n\n"
            "Case ID : {case_id}\n"
            "Status  : P9 · FUND DISBURSEMENT\n"
            "Updated : {ts}\n\n"
            "Your recovery package has been approved. Please\n"
            "complete any pending fee requirements to finalize\n"
            "the disbursement process."
        ),
        "status_set": frozenset({
            "P9", "P9 FUND DISBURSEMENT", "FUND DISBURSEMENT",
            "Fund Disbursement", "DISBURSEMENT AUTHORIZED",
            "DISBURSEMENT COMPLETE",
        }),
    },

    # ── P10 ─────────────────────────────────────────────────────────────────────
    {
        "key":         "P10",
        "icon":        "✅",
        "pct":         100,
        "label":       "P10 · CASE RESOLVED",
        "status_line": "CASE RESOLVED — DISBURSEMENT COMPLETE",
        "module":      "M10-FIN Final Authorization & Closure",
        "badge":       "✅ RESOLVED  │  DISBURSEMENT COMPLETE",
        "pipeline_items": [
            ("🏁 FINAL AUTHORIZATION", [
                "Final authorization issued. [{ts}]",
                "Case {case_id} — CLOSED.",
                "All legal obligations: FULFILLED.",
            ]),
            ("💳 DISBURSEMENT COMPLETE", [
                "Recovered funds: RELEASED.",
                "Transfer confirmation: ON RECORD.",
                "Federal audit trail: SEALED.",
            ]),
            ("📁 CASE CLOSURE", [
                "Case file archived. READ-ONLY.",
                "Reference number retained for 7 years.",
            ]),
        ],
        "receipt_body": (
            "Your IC3 case has been fully resolved. All\n"
            "authorized disbursements have been processed\n"
            "and the case file has been sealed for federal\n"
            "audit retention."
        ),
        "email_subject": "[IC3] Case Resolved — {case_id}",
        "email_body": (
            "Your IC3 case has been fully resolved.\n\n"
            "Case ID : {case_id}\n"
            "Status  : P10 · CASE RESOLVED\n"
            "Updated : {ts}\n\n"
            "All authorized disbursements have been processed.\n"
            "Your case file has been sealed and archived.\n"
            "Retain your Case ID for your records."
        ),
        "status_set": frozenset({
            "P10", "P10 SANCTION", "SANCTION", "OFAC SANCTION",
            "P10 · SANCTION",
        }),
    },
]

# ─── 快速查找 ──────────────────────────────────────────────────────────────────
def get_stage_by_status(status: str) -> dict | None:
    """从 status 字符串找到对应阶段配置，大小写不敏感。"""
    if not status:
        return None
    s_upper = status.strip().upper()
    for stage in STAGE_LIST:
        for sv in stage["status_set"]:
            if sv.upper() == s_upper:
                return stage
    # 前缀匹配（如 "P5 ..." 匹配 P5）
    for stage in STAGE_LIST:
        key = stage["key"]   # "P1"..."P10"
        if s_upper == key or s_upper.startswith(key + " ") or s_upper.startswith(key + "·"):
            return stage
    return None


def get_stage_by_key(key: str) -> dict | None:
    """按 key（"P1"..."P10"）直接获取阶段配置。"""
    k = (key or "").strip().upper()
    for stage in STAGE_LIST:
        if stage["key"] == k:
            return stage
    return None
