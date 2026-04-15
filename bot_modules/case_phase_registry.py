"""
案件 status → CMP 阶段（1–12）、进度百分比、PDF 管道文案。
与 bot.py CMP 状态分组保持一致；文案为固定模板，个案数据仍来自 DB。
"""
from __future__ import annotations

import html

# 与 bot.py _CMP_P* 对齐；匹配顺序：高阶段优先
_P12 = frozenset({
    "P12", "P12 FINAL AUTHORIZATION", "FINAL AUTHORIZATION", "READY FOR TRANSMISSION",
    "P12 · FINAL AUTHORIZATION",
})
_P11 = frozenset({
    "P11", "P11 PROTOCOL CONVERSION", "PROTOCOL CONVERSION", "PENDING PROTOCOL UPDATE",
    "P11 · PROTOCOL CONVERSION",
})
_P10 = frozenset({
    "P10", "P10 SANCTION", "SANCTION", "OFAC SANCTION", "P10 · SANCTION",
})
_P9 = frozenset({
    "P9", "P9 FUND DISBURSEMENT", "FUND DISBURSEMENT",
    "DISBURSEMENT AUTHORIZED", "DISBURSEMENT COMPLETE",
})
_P8 = frozenset({
    "P8", "P8 LEGAL", "LEGAL DOCUMENTATION",
    "PENDING WALLET ADDRESS",
})
_P7 = frozenset({
    "P7", "P7 ASSET TRACING", "ASSET TRACING",
    "PENDING ALLOCATION",
})
_P6 = frozenset({
    "P6", "P6 PRELIMINARY REVIEW", "PRELIMINARY REVIEW",
    "FORENSICS REVIEW", "FORENSIC REVIEW", "P6 PRELIMINARY REVIEW",
})
_P5 = frozenset({
    "P5", "P5 IDENTITY VERIFICATION", "IDENTITY VERIFICATION",
    "P5 IDENTITY VERIFICATION", "EVIDENCE VERIFICATION",
})
_P4 = frozenset({
    "REFERRED", "REFERRED TO LAW ENFORCEMENT", "P4", "P4 REFERRED",
    "PROCESSING COMPLETE", "CASE REFERRED",
})
_P3 = frozenset({
    "UNDER REVIEW", "CASE ACCEPTED", "P3", "P3 UNDER REVIEW",
    "CASE ACCEPTED",
})
_P2 = frozenset({
    "VALIDATING", "P2", "P2 VALIDATING", "PENDING REVIEW", "PENDING REVIEW",
})
_P1 = frozenset({
    "SUBMITTED", "P1", "P1 SUBMITTED", "PENDING INITIAL REVIEW", "待初步审核",
    "PENDING", "INITIAL REVIEW",
})
_CLOSED = frozenset({"CLOSED", "ARCHIVED", "CASE CLOSED"})


def _matches(status: str | None, group: frozenset[str]) -> bool:
    s = (status or "").strip()
    if not s:
        return False
    su = s.upper()
    return su in {x.upper() for x in group}


def phase_from_status(status: str | None) -> int:
    """1–12 对应 P1–P12；结案单独处理；无状态为 0。"""
    if _matches(status, _P12):
        return 12
    if _matches(status, _P11):
        return 11
    if _matches(status, _P10):
        return 10
    if _matches(status, _P9):
        return 9
    if _matches(status, _P8):
        return 8
    if _matches(status, _P7):
        return 7
    if _matches(status, _P6):
        return 6
    if _matches(status, _P5):
        return 5
    if _matches(status, _P4):
        return 4
    if _matches(status, _P3):
        return 3
    if _matches(status, _P2):
        return 2
    if _matches(status, _CLOSED):
        return 10
    if _matches(status, _P1):
        return 1
    if (status or "").strip():
        return 1
    return 0


def progress_pct(phase: int) -> int:
    if phase <= 0:
        return 0
    if phase >= 10:
        return 100
    return min(100, phase * 10)


def status_color_hex(phase: int) -> str:
    if phase <= 1:
        return "#276749"
    if phase == 2:
        return "#2B6CB0"
    if phase == 3:
        return "#553C9A"
    if phase <= 6:
        return "#276749"
    if phase <= 9:
        return "#744210"
    return "#1A202C"


def pdf_status_display(status: str | None, phase: int) -> str:
    raw = (status or "").strip() or "SUBMITTED"
    if _matches(status, _CLOSED):
        return f"CLOSED / ARCHIVED — {raw}"
    labels = {
        1: "INTAKE / SUBMITTED",
        2: "VALIDATION",
        3: "UNDER REVIEW",
        4: "REFERRED / FIELD COORDINATION",
        5: "IDENTITY & EVIDENCE VERIFICATION",
        6: "PRELIMINARY / FORENSIC REVIEW",
        7: "ASSET TRACING",
        8: "LEGAL DOCUMENTATION",
        9: "FUND DISBURSEMENT",
        10: "SANCTION / COMPLIANCE",
        11: "PROTOCOL CONVERSION",
        12: "FINAL AUTHORIZATION",
    }
    base = labels.get(phase, f"IN PROCESS — {raw}")
    return f"{base} — {raw}"


def pipeline_text(status: str | None, phase: int) -> str:
    if _matches(status, _CLOSED):
        return (
            "[IC3-ADRI] CASE PROCESSING PIPELINE — CLOSED\n"
            "• Case file archived; no further automated milestones\n"
            "• Retain all records and official PDF for your files\n"
            "• Reference your Case ID in any future correspondence"
        )
    lines = _PIPELINES.get(phase) or _PIPELINES.get(0, "")
    return lines


_PIPELINES = {
    0: (
        "[IC3-ADRI] CASE PROCESSING PIPELINE\n"
        "• Status mapping in progress; contact support if this persists."
    ),
    1: (
        "[IC3-ADRI] CASE PROCESSING PIPELINE — INTAKE\n"
        "• Complaint received and queued for integrity checks\n"
        "• Complainant profile pending verification snapshot\n"
        "• No disbursement or legal action at this stage"
    ),
    2: (
        "[IC3-ADRI] CASE PROCESSING PIPELINE — VALIDATION\n"
        "• Automated and manual validation of submitted fields\n"
        "• Evidence hash / metadata cross-check where applicable\n"
        "• Routing to review queue upon successful validation"
    ),
    3: (
        "[IC3-ADRI] CASE PROCESSING PIPELINE — REVIEW\n"
        "• Analyst review and case acceptance tracking\n"
        "• Internal coordination; complainant notified of major updates\n"
        "• No recovery disbursement until later pipeline stages"
    ),
    4: (
        "[IC3-ADRI] CASE PROCESSING PIPELINE — REFERRAL\n"
        "• Referral / handoff to designated processing track\n"
        "• Field-office style coordination (template language)\n"
        "• Await next milestone notifications in Telegram / email"
    ),
    5: (
        "[IC3-ADRI] CASE PROCESSING PIPELINE — PHASE 5 (IDENTITY / EVIDENCE)\n"
        "• Identity and evidence verification workflows\n"
        "• Additional documents may be requested securely\n"
        "• Respond only through official in-app channels"
    ),
    6: (
        "[IC3-ADRI] CASE PROCESSING PIPELINE — PRELIMINARY / FORENSICS\n"
        "• Preliminary and forensic-style review (operational template)\n"
        "• Internal technical notes; not a final legal determination\n"
        "• Progress may advance without daily user-visible changes"
    ),
    7: (
        "[IC3-ADRI] CASE PROCESSING PIPELINE — ASSET TRACING\n"
        "• Tracing and allocation-related workflow (template)\n"
        "• Outcomes depend on third-party and internal checks\n"
        "• Beware of unsolicited payment requests — IC3 does not charge fees"
    ),
    8: (
        "[IC3-ADRI] CASE PROCESSING PIPELINE — LEGAL DOCUMENTATION\n"
        "• Legal documentation phase (template)\n"
        "• Wallet / payout details may be collected through secure flows only\n"
        "• Do not share seed phrases or passwords with anyone"
    ),
    9: (
        "[IC3-ADRI] CASE PROCESSING PIPELINE — DISBURSEMENT\n"
        "• Disbursement-related milestones (template)\n"
        "• Authorized states only; verify via official app messages\n"
        "• Report impersonation attempts immediately"
    ),
    10: (
        "[IC3-ADRI] CASE PROCESSING PIPELINE — SANCTION / COMPLIANCE\n"
        "• Sanctions / compliance screening (template)\n"
        "• May introduce holds or additional verification steps\n"
        "• Follow only instructions shown in your official case thread"
    ),
    11: (
        "[IC3-ADRI] CASE PROCESSING PIPELINE — PROTOCOL CONVERSION\n"
        "• Protocol / technical conversion milestone (template)\n"
        "• Internal processing; user-visible updates on phase change"
    ),
    12: (
        "[IC3-ADRI] CASE PROCESSING PIPELINE — FINAL AUTHORIZATION\n"
        "• Final authorization / transmission readiness (template)\n"
        "• Download updated PDF after each major status change\n"
        "• Use [Send Confirmation to My Email] for a plain-text receipt"
    ),
}


def progress_bar_utf(pct: int, width: int = 20) -> str:
    pct = max(0, min(100, int(pct)))
    filled = max(0, min(width, round(width * pct / 100)))
    return "█" * filled + "░" * (width - filled) + f" {pct}%"


def build_case_status_record_html(case_no: str, status: str | None, phase: int, pct: int) -> str:
    esc = html.escape
    bar = progress_bar_utf(pct)
    phase_label = pdf_status_display(status, phase)
    return (
        "<b>[CASE STATUS RECORD]</b>\n"
        f"Case ID: <code>{esc(case_no)}</code>\n"
        f"System status: {esc((status or 'N/A').strip())}\n"
        f"Processing stage: {esc(phase_label)}\n\n"
        "<b>[▼ Real-Time Progress]</b>\n"
        f"<pre>{esc(bar)}</pre>\n"
        "Updated PDF reflects this pipeline. Use the buttons below to download or email a confirmation."
    )


def format_confirmation_email_plain(case_no: str, status: str | None) -> str:
    ph = phase_from_status(status)
    pct = progress_pct(ph)
    bar = progress_bar_utf(pct)
    pipe = pipeline_text(status, ph)
    return (
        "IC3 — CASE STATUS CONFIRMATION\n"
        "────────────────────────────────\n"
        f"Case ID: {case_no}\n"
        f"Status: {(status or 'N/A').strip()}\n"
        f"Estimated progress: {pct}%\n"
        f"{bar}\n"
        "────────────────────────────────\n"
        f"{pipe}\n"
        "────────────────────────────────\n"
        "This is an automated message. Do not reply.\n"
    )


def pdf_phase_patch(status: str | None) -> dict:
    ph = phase_from_status(status)
    pct = progress_pct(ph)
    return {
        "cmp_phase": ph,
        "real_time_progress_pct": pct,
        "processing_pipeline_text": pipeline_text(status, ph),
        "pdf_status_label": pdf_status_display(status, ph),
        "pdf_status_color_hex": status_color_hex(ph),
    }
