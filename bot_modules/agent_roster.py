"""
IC3 Cybercrime Investigation Team — agent roster (P1–P10)

与数据库 `agent_code` / 管理员「派遣专员」相互独立：本模块提供
「名义团队」编组、探员英文档案及按阶段查询，供文案 / PDF / 状态卡引用。

用法示例::

    from bot_modules.agent_roster import (
        PHASE_ROSTERS,
        roster_for_phase,
        roster_summary_html,
        AGENT_PROFILES,
        agents_active_in_phase,
        agent_profile,
        phase_from_case_status,
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re


class Engagement(str, Enum):
    """编组视图下成员在本阶段的参与方式（用于 P1–P10 分段展示）。"""

    CORE = "core"
    LEAD = "lead"
    COORDINATE = "coordinate"


@dataclass(frozen=True)
class RosterEntry:
    name_en: str
    title_zh: str
    engagement: Engagement = Engagement.CORE

    @property
    def engagement_zh(self) -> str:
        if self.engagement is Engagement.LEAD:
            return "主导"
        if self.engagement is Engagement.COORDINATE:
            return "介入协调"
        return ""


@dataclass(frozen=True)
class PhaseRoster:
    phase_from: int
    phase_to: int
    label_zh: str
    label_en: str
    members: tuple[RosterEntry, ...]


@dataclass(frozen=True)
class AgentProfile:
    """
    单名探员完整档案（英文为主，与对外说明一致）。
    stage_from / stage_to：主要职责区间（含端点）。
    """

    sort_key: int
    name_en: str
    position_en: str
    department_en: str
    department_code: str
    agent_id: str
    office_en: str
    role_en: str
    stage_from: int
    stage_to: int
    responsibilities: tuple[str, ...]
    expertise: tuple[str, ...]
    title_zh: str


# ── 探员档案（IC3 Cybercrime Investigation Team）────────────────

AGENT_PROFILES_ORDERED: tuple[AgentProfile, ...] = (
    AgentProfile(
        sort_key=1,
        name_en="David R. Johnson",
        position_en="Supervisory Special Agent",
        department_en="Cyber Crime Task Force",
        department_code="CCT",
        agent_id="FBI-CCT-2026-1042",
        office_en="Los Angeles Field Office",
        role_en=(
            "Overall case coordination; primary contact for users across phases."
        ),
        stage_from=3,
        stage_to=10,
        responsibilities=(
            "Sending case progress updates",
            "Explaining the reasons for charges at each stage",
            "Handling basic user inquiries",
        ),
        expertise=(
            "Cross-departmental coordination",
            "Case management",
        ),
        title_zh="督导特别探员",
    ),
    AgentProfile(
        sort_key=2,
        name_en="Michael Thompson",
        position_en="Forensic Computer Examiner",
        department_en="Digital Forensics Laboratory",
        department_code="DFL",
        agent_id="FBI-DFL-2026-2759",
        office_en="Washington Field Office",
        role_en=(
            "Digital forensics supporting blockchain analysis and asset tracing."
        ),
        stage_from=6,
        stage_to=7,
        responsibilities=(
            "Analyzing transaction hashes",
            "Tracking fund flows",
            "Providing technical reports",
        ),
        expertise=(
            "Blockchain forensics",
            "Cryptocurrency tracking",
        ),
        title_zh="法医计算机鉴定员",
    ),
    AgentProfile(
        sort_key=3,
        name_en="Sarah Williams",
        position_en="Financial Intelligence Specialist",
        department_en="Financial Crimes Section",
        department_code="FCS",
        agent_id="FBI-FCS-2026-3841",
        office_en="New York Field Office",
        role_en=(
            "Financial intelligence on money laundering patterns and fund paths."
        ),
        stage_from=7,
        stage_to=8,
        responsibilities=(
            "Identifying money laundering patterns",
            "Analyzing exchange compliance",
            "Assessing recovery feasibility",
        ),
        expertise=(
            "Anti-money laundering investigations",
            "Financial crime analysis",
        ),
        title_zh="金融情报专家",
    ),
    AgentProfile(
        sort_key=4,
        name_en="Robert Chen",
        position_en="DOJ Legal Coordinator",
        department_en="Legal Liaison Division",
        department_code="LLD",
        agent_id="FBI-LLD-2026-4921",
        office_en="San Francisco Field Office",
        role_en="Coordinating with DOJ, courts, and counsel on legal procedure.",
        stage_from=8,
        stage_to=9,
        responsibilities=(
            "Preparing legal documents",
            "Contacting federal prosecutors",
            "Explaining legal procedures",
        ),
        expertise=(
            "Electronic evidence law",
            "Cybercrime prosecution",
        ),
        title_zh="司法部法律协调员",
    ),
    AgentProfile(
        sort_key=5,
        name_en="Jennifer Martinez",
        position_en="Identity Verification Manager",
        department_en="Intake & Verification Center",
        department_code="IVC",
        agent_id="FBI-IVC-2026-5637",
        office_en="Miami Field Office",
        role_en=(
            "Victim identification and KYC at intake through identity phase."
        ),
        stage_from=1,
        stage_to=5,
        responsibilities=(
            "Verifying victim identity",
            "Processing identity verification documents",
            "Explaining privacy protection measures",
        ),
        expertise=(
            "Identity theft prevention",
            "KYC compliance",
        ),
        title_zh="身份核验主管",
    ),
    AgentProfile(
        sort_key=6,
        name_en="James Wilson",
        position_en="International Operations Agent",
        department_en="Global Liaison Division",
        department_code="GLD",
        agent_id="FBI-GLD-2026-6284",
        office_en="Houston Field Office",
        role_en=(
            "International operations and overseas law-enforcement coordination."
        ),
        stage_from=4,
        stage_to=7,
        responsibilities=(
            "Contacting overseas exchanges",
            "Coordinating with Interpol",
            "Handling cross-border legal issues",
        ),
        expertise=(
            "International law enforcement cooperation",
            "Cross-border investigations",
        ),
        title_zh="国际行动探员",
    ),
    AgentProfile(
        sort_key=7,
        name_en="Linda Davis",
        position_en="Evidence Control Technician",
        department_en="Records & Evidence Unit",
        department_code="REU",
        agent_id="FBI-REU-2026-7392",
        office_en="Chicago Field Office",
        role_en=(
            "Collecting, organizing, and preserving digital evidence."
        ),
        stage_from=2,
        stage_to=6,
        responsibilities=(
            "Collecting transaction records",
            "Organizing communication evidence",
            "Ensuring the integrity of the evidence chain",
        ),
        expertise=(
            "Digital evidence management",
            "Electronic forensics",
        ),
        title_zh="证据管控技术员",
    ),
    AgentProfile(
        sort_key=8,
        name_en="Richard Brown",
        position_en="Cyber Division Supervisor",
        department_en="Cyber Security Division",
        department_code="CSD",
        agent_id="FBI-CSD-2026-8473",
        office_en="Seattle Field Office",
        role_en=(
            "Supervisory technical review of fraudulent platforms and infrastructure."
        ),
        stage_from=6,
        stage_to=7,
        responsibilities=(
            "Analyzing fraudulent websites",
            "Identifying attack vectors",
            "Providing technical advice",
        ),
        expertise=(
            "Cybersecurity",
            "Threat assessment",
        ),
        title_zh="网络部门主管",
    ),
    AgentProfile(
        sort_key=9,
        name_en="Amanda Taylor",
        position_en="Victim Assistance Specialist",
        department_en="Victim Services Division",
        department_code="VSD",
        agent_id="FBI-VSD-2026-9182",
        office_en="Atlanta Field Office",
        role_en=(
            "Victim communication, support, and procedural guidance."
        ),
        stage_from=3,
        stage_to=10,
        responsibilities=(
            "Providing case updates",
            "Answering victims' questions",
            "Assisting in resolving procedural issues",
        ),
        expertise=(
            "Victim assistance",
            "Crisis management",
        ),
        title_zh="受害者援助专员",
    ),
    AgentProfile(
        sort_key=10,
        name_en="Thomas Anderson",
        position_en="Asset Forfeiture Agent",
        department_en="Asset Recovery Unit",
        department_code="ARU",
        agent_id="FBI-ARU-2026-0591",
        office_en="Dallas Field Office",
        role_en=(
            "Asset forfeiture and final execution of recovery and transfers."
        ),
        stage_from=9,
        stage_to=10,
        responsibilities=(
            "Executing asset unfreezing",
            "Processing fund transfers",
            "Ensuring funds reach designated victim accounts",
        ),
        expertise=(
            "Asset recovery",
            "Fund execution",
        ),
        title_zh="资产扣押探员",
    ),
)

AGENT_PROFILES: dict[str, AgentProfile] = {
    p.name_en: p for p in AGENT_PROFILES_ORDERED
}


def agent_profile(name_en: str) -> AgentProfile | None:
    return AGENT_PROFILES.get(name_en)


def agents_active_in_phase(phase: int) -> tuple[AgentProfile, ...]:
    """返回主要职责阶段覆盖当前 phase 的探员（按 sort_key 排序）。"""
    if phase < 1 or phase > 10:
        return ()
    out = [p for p in AGENT_PROFILES_ORDERED if p.stage_from <= phase <= p.stage_to]
    return tuple(out)


def format_agent_profile_plain(p: AgentProfile) -> str:
    """英文纯文本档案（段落）。"""
    lines = [
        f"{p.sort_key}. {p.name_en}",
        f"Position: {p.position_en}",
        f"Department: {p.department_en} ({p.department_code})",
        f"Agent ID: {p.agent_id}",
        f"Field Office: {p.office_en}",
        f"Primary stage span: P{p.stage_from}–P{p.stage_to}",
        f"Role: {p.role_en}",
        "Main Responsibilities:",
        *(f"  • {r}" for r in p.responsibilities),
        "Areas of Expertise:",
        *(f"  • {e}" for e in p.expertise),
    ]
    return "\n".join(lines)


def format_agent_profile_html(p: AgentProfile) -> str:
    """HTML 片段（Telegram HTML 需注意转义；此处不含用户输入）。"""
    resp_li = "<br/>".join(f"• {r}" for r in p.responsibilities)
    exp_li = "<br/>".join(f"• {e}" for e in p.expertise)
    return (
        f"<b>{p.sort_key}. {p.name_en}</b><br/>"
        f"<b>Position:</b> {p.position_en}<br/>"
        f"<b>Department:</b> {p.department_en} ({p.department_code})<br/>"
        f"<b>Agent ID:</b> <code>{p.agent_id}</code><br/>"
        f"<b>Field Office:</b> {p.office_en}<br/>"
        f"<b>Primary stage span:</b> P{p.stage_from}–P{p.stage_to}<br/>"
        f"<b>Role:</b> {p.role_en}<br/><br/>"
        f"<b>Main Responsibilities:</b><br/>{resp_li}<br/><br/>"
        f"<b>Areas of Expertise:</b><br/>{exp_li}"
    )


def full_team_dossier_plain() -> str:
    """全体探员英文档案（长文）。"""
    sep = "\n\n" + "─" * 48 + "\n\n"
    return sep.join(format_agent_profile_plain(p) for p in AGENT_PROFILES_ORDERED)


# ── P1–P10 分段编组（与档案并行；P1–P4 仍展示基础三人组）──────────

PHASE_ROSTERS: tuple[PhaseRoster, ...] = (
    PhaseRoster(
        1,
        4,
        "基础团队",
        "Core intake team",
        (
            RosterEntry(
                "Jennifer Martinez",
                AGENT_PROFILES["Jennifer Martinez"].title_zh,
                Engagement.CORE,
            ),
            RosterEntry(
                "Linda Davis",
                AGENT_PROFILES["Linda Davis"].title_zh,
                Engagement.CORE,
            ),
            RosterEntry(
                "James Wilson",
                AGENT_PROFILES["James Wilson"].title_zh,
                Engagement.CORE,
            ),
        ),
    ),
    PhaseRoster(
        5,
        5,
        "身份验证",
        "Identity verification",
        (
            RosterEntry(
                "Jennifer Martinez",
                AGENT_PROFILES["Jennifer Martinez"].title_zh,
                Engagement.LEAD,
            ),
            RosterEntry(
                "David R. Johnson",
                AGENT_PROFILES["David R. Johnson"].title_zh,
                Engagement.COORDINATE,
            ),
        ),
    ),
    PhaseRoster(
        6,
        7,
        "技术分析",
        "Technical analysis",
        (
            RosterEntry(
                "Michael Thompson",
                AGENT_PROFILES["Michael Thompson"].title_zh,
                Engagement.CORE,
            ),
            RosterEntry(
                "Richard Brown",
                AGENT_PROFILES["Richard Brown"].title_zh,
                Engagement.CORE,
            ),
            RosterEntry(
                "Sarah Williams",
                AGENT_PROFILES["Sarah Williams"].title_zh,
                Engagement.CORE,
            ),
        ),
    ),
    PhaseRoster(
        8,
        8,
        "法律程序",
        "Legal proceedings",
        (
            RosterEntry(
                "Robert Chen",
                AGENT_PROFILES["Robert Chen"].title_zh,
                Engagement.CORE,
            ),
            RosterEntry(
                "David R. Johnson",
                AGENT_PROFILES["David R. Johnson"].title_zh,
                Engagement.COORDINATE,
            ),
        ),
    ),
    PhaseRoster(
        9,
        10,
        "最终执行",
        "Final execution",
        (
            RosterEntry(
                "Thomas Anderson",
                AGENT_PROFILES["Thomas Anderson"].title_zh,
                Engagement.CORE,
            ),
            RosterEntry(
                "Amanda Taylor",
                AGENT_PROFILES["Amanda Taylor"].title_zh,
                Engagement.CORE,
            ),
        ),
    ),
)


def _phase_bounds(pr: PhaseRoster) -> range:
    return range(pr.phase_from, pr.phase_to + 1)


def roster_band_for_phase(phase: int) -> PhaseRoster | None:
    if phase < 1 or phase > 10:
        return None
    for pr in PHASE_ROSTERS:
        if phase in _phase_bounds(pr):
            return pr
    return None


def roster_for_phase(phase: int) -> tuple[RosterEntry, ...]:
    band = roster_band_for_phase(phase)
    return band.members if band else ()


def roster_label_for_phase(phase: int, *, lang: str = "zh") -> str:
    band = roster_band_for_phase(phase)
    if not band:
        return ""
    return band.label_zh if lang.startswith("zh") else band.label_en


def format_roster_lines(
    phase: int,
    *,
    lang: str = "zh",
    prefix: str = "• ",
) -> list[str]:
    band = roster_band_for_phase(phase)
    if not band:
        return []
    lines: list[str] = []
    head = band.label_zh if lang.startswith("zh") else band.label_en
    lines.append(head)
    for m in band.members:
        tag = m.title_zh if lang.startswith("zh") else _title_zh_to_en(m.title_zh)
        extra = m.engagement_zh
        if extra:
            lines.append(f"{prefix}{m.name_en}（{tag}）— {extra}")
        else:
            lines.append(f"{prefix}{m.name_en}（{tag}）")
    return lines


def roster_summary_plain(phase: int, *, lang: str = "zh") -> str:
    return "\n".join(format_roster_lines(phase, lang=lang))


def roster_summary_html(phase: int, *, lang: str = "zh") -> str:
    band = roster_band_for_phase(phase)
    if not band:
        return ""
    head = band.label_zh if lang.startswith("zh") else band.label_en
    parts = [f"<b>{head}</b>"]
    for m in band.members:
        tag = m.title_zh if lang.startswith("zh") else _title_zh_to_en(m.title_zh)
        extra = m.engagement_zh
        if extra:
            parts.append(f"• {m.name_en}（{tag}）— {extra}")
        else:
            parts.append(f"• {m.name_en}（{tag}）")
    return "\n".join(parts)


def all_named_agents() -> tuple[str, ...]:
    return tuple(p.name_en for p in AGENT_PROFILES_ORDERED)


def agent_titles_zh() -> dict[str, str]:
    return {p.name_en: p.title_zh for p in AGENT_PROFILES_ORDERED}


# ── case.status → P1–P10（粗映射）──────────────────────────────

_STATUS_PHASE_HINTS: tuple[tuple[str, int], ...] = (
    ("SUBMITTED", 1),
    ("PENDING", 1),
    ("待初步审核", 1),
    ("VALIDATING", 2),
    ("PENDING REVIEW", 2),
    ("UNDER REVIEW", 3),
    ("CASE ACCEPTED", 3),
    ("REFERRED", 4),
    ("REFERRED TO LAW ENFORCEMENT", 4),
    ("IDENTITY VERIFICATION", 5),
    ("PRELIMINARY REVIEW", 6),
    ("ASSET TRACING", 7),
    ("LEGAL DOCUMENTATION", 8),
    ("CLOSED", 10),
    ("Case Closed", 10),
)


def phase_from_case_status(status: str | None) -> int | None:
    if not status:
        return None
    s = status.strip()
    for key, ph in _STATUS_PHASE_HINTS:
        if s.upper() == key.upper():
            return ph
    m = re.match(r"^P(\d{1,2})\s*·", s, re.IGNORECASE)
    if m:
        p = int(m.group(1))
        if 1 <= p <= 10:
            return p
    return None


def roster_for_case_status(status: str | None) -> tuple[RosterEntry, ...]:
    p = phase_from_case_status(status)
    if p is None:
        return ()
    return roster_for_phase(p)


def _title_zh_to_en(title_zh: str) -> str:
    return agent_titles_zh_to_en().get(title_zh, title_zh)


def agent_titles_zh_to_en() -> dict[str, str]:
    return {p.title_zh: p.position_en for p in AGENT_PROFILES_ORDERED}


__all__ = [
    "AGENT_PROFILES",
    "AGENT_PROFILES_ORDERED",
    "Engagement",
    "AgentProfile",
    "PHASE_ROSTERS",
    "PhaseRoster",
    "RosterEntry",
    "agent_profile",
    "agent_titles_zh",
    "agent_titles_zh_to_en",
    "agents_active_in_phase",
    "all_named_agents",
    "format_agent_profile_html",
    "format_agent_profile_plain",
    "format_roster_lines",
    "full_team_dossier_plain",
    "phase_from_case_status",
    "roster_band_for_phase",
    "roster_for_case_status",
    "roster_for_phase",
    "roster_label_for_phase",
    "roster_summary_html",
    "roster_summary_plain",
]
