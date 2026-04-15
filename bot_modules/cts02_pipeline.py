"""
M03-CTS-02 · Case Processing Pipeline (timeline copy + progress UI).

Renders HTML for Telegram (parse_mode=HTML). Collapsed view: progress bar only;
expanded: one line per stage (📂 🟢 TITLE ✅), no sub-bullets.
"""

from __future__ import annotations

import html
from typing import Literal

# Displayed after Federal Reference (e.g. IC3-2026-REF-xxxx-XXX V3.3)
CTS_PIPELINE_DOC_VERSION = "V3.3"

# Cumulative “overall” % when the case sits in that pipeline step (1–8)
_OVERALL_PCT: dict[int, float] = {
    1: 8.5,
    2: 15.2,
    3: 25.0,
    4: 35.0,
    5: 45.0,
    6: 55.0,
    7: 75.0,
    8: 90.0,
}

# Stage titles for compact lines (aligned with former P1–P8 blocks)
_STAGE_TITLES: dict[int, str] = {
    1: "SUBMITTED",
    2: "PENDING REVIEW",
    3: "CASE ACCEPTED",
    4: "REFERRED TO LAW ENFORCEMENT",
    5: "IDENTITY VERIFICATION",
    6: "PRELIMINARY REVIEW",
    7: "ASSET TRACING",
    8: "LEGAL DOCUMENTATION",
}


def _progress_bar(pct: float, width: int = 30) -> str:
    pct = max(0.0, min(100.0, pct))
    filled = int(round(width * pct / 100.0))
    filled = min(width, max(0, filled))
    return "█" * filled + "░" * (width - filled)


def _normalize_status(s: str) -> str:
    return (s or "").strip()


def resolve_pipeline_step(
    cur_status_raw: str,
    cur_normalized: str,
) -> tuple[int, Literal["pipeline", "closed"]]:
    """
    Returns (step 1–8, or 0 when closed).
    P7 = ASSET TRACING, P8 = LEGAL DOCUMENTATION.
    """
    raw = _normalize_status(cur_status_raw)
    norm = _normalize_status(cur_normalized)

    raw_up = raw.upper()
    if norm.upper() == "CLOSED" or raw in ("Case Closed", "CLOSED", "CASE CLOSED"):
        return 0, "closed"
    if "FUND DISBURSEMENT" in raw_up or raw_up in ("P9", "P10", "P11", "P12"):
        return 8, "pipeline"
    if "LEGAL DOCUMENTATION" in raw_up or norm == "LEGAL DOCUMENTATION":
        return 8, "pipeline"
    if "ASSET TRACING" in raw_up or norm == "ASSET TRACING":
        return 7, "pipeline"
    if "PRELIMINARY REVIEW" in raw_up or norm == "PRELIMINARY REVIEW":
        return 6, "pipeline"
    if "IDENTITY VERIFICATION" in raw_up or norm == "IDENTITY VERIFICATION":
        return 5, "pipeline"
    if "REFERRED TO LAW ENFORCEMENT" in raw_up or norm in ("REFERRED TO LAW ENFORCEMENT", "REFERRED") or raw == "Processing Complete":
        return 4, "pipeline"
    if "CASE ACCEPTED" in raw_up or norm in ("CASE ACCEPTED", "UNDER REVIEW") or raw in ("Under Review", "Case Accepted"):
        return 3, "pipeline"
    if "PENDING REVIEW" in raw_up or norm in ("PENDING REVIEW", "VALIDATING"):
        return 2, "pipeline"
    if norm == "SUBMITTED" or raw in ("Pending Initial Review", "待初步审核", "SUBMITTED"):
        return 1, "pipeline"
    return 1, "pipeline"


def _overall_percent(step: int, mode: str) -> float:
    if mode == "closed":
        return 100.0
    if step < 1:
        return 0.0
    return _OVERALL_PCT.get(min(step, 8), 55.0)


def _esc(s: str) -> str:
    return html.escape(s, quote=False)


def _compact_stage_lines(
    *,
    effective_step: int,
    mode: str,
) -> str:
    """One line per stage: 📂 🟢 <b>TITLE</b> ✅ — no 📋⏳🗺️ sub-bullets."""
    lines: list[str] = []
    for s in range(1, effective_step + 1):
        title = _STAGE_TITLES.get(s, f"STAGE {s}")
        completed = s < effective_step or mode == "closed"
        emoji = "🟢" if completed else "🟡"
        suffix = " ✅" if completed else ""
        lines.append(f"📂 {emoji} <b>{_esc(title)}</b>{suffix}")
    return "\n".join(lines)


def render_cts02_pipeline_html(
    *,
    case_no: str | None,
    cur_status_raw: str,
    cur_normalized: str,
    agent_masked: str = "#******",
    has_case: bool,
    expanded: bool = False,
) -> str:
    """
    Collapsed: header + Federal Reference + progress bar + % only.
    Expanded: same + compact stage lines (📂 🟢 TITLE ✅).
    """
    ref = _esc(case_no) if case_no else "—"
    ver = _esc(CTS_PIPELINE_DOC_VERSION)

    if not has_case:
        bar = _progress_bar(0.0)
        core = (
            "<b>[IC3-ADRI] CASE PROCESSING PIPELINE</b>\n"
            f"Federal Reference: <code>{ref}</code> {ver}\n"
            f"Overall Progress: 0.0%\n"
            f"{bar} 0.0%\n"
        )
        if not expanded:
            return core + "\n<i>Submit a case (M01) to enable the federal progress timeline.</i>"
        return core + "\n\n<i>Submit a case (M01) to enable the federal progress timeline.</i>"

    step, mode = resolve_pipeline_step(cur_status_raw, cur_normalized)
    overall = _overall_percent(step, mode)
    bar = _progress_bar(overall)

    core = (
        "<b>[IC3-ADRI] CASE PROCESSING PIPELINE</b>\n"
        f"Federal Reference: <code>{ref}</code> {ver}\n"
        f"Overall Progress: {overall:.1f}%\n"
        f"{bar} {overall:.1f}%\n"
    )

    if not expanded:
        return (
            core
            + '\n<i>📂 Click [▼Expand Real-Time Progress] below to view the stage list.</i>'
        )

    effective_step = step if mode != "closed" else 8
    stages = _compact_stage_lines(effective_step=effective_step, mode=mode)
    if mode == "closed":
        closure = (
            "\n────────────────────────────────────\n"
            "<b>Final disposition</b>\n"
            "Case file sealed / closed.\n"
        )
    else:
        closure = ""

    return core + "\n────────────────────────────────────\n" + stages + closure


__all__ = [
    "CTS_PIPELINE_DOC_VERSION",
    "render_cts02_pipeline_html",
    "resolve_pipeline_step",
]
