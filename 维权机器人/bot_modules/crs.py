"""
FBI IC3 – ADRI Bot
CRS Module: Complaint Reporting System (CRS-01 to CRS-04)
"""
from .config import (
    AUTH_ID, VALID_PERIOD, logger,
    S_FULLNAME, S_ADDRESS, S_PHONE, S_EMAIL,
    S_TXID, S_ASSET, S_VICTIM_WALLET, S_SUSPECT_WALLET,
    S_PLATFORM, S_SCAMMER_ID, S_TIME, S_WALLET,
)
from .keyboards import kb_crs_nav, kb_m01, kb_m01_for_user, kb_crs_attest

FEDERAL_NOTICE = (
    "⚠️ <b>FEDERAL NOTICE</b>\n"
    + "━" * 28 + "\n\n"
    "This interface is part of the <i>IC3 Authorized Digital\n"
    "Reporting Interface (ADRI)</i>. Information collected here\n"
    "will be used for official law enforcement investigations.\n\n"
    "📜 <b>Privacy Act of 1974:</b> Providing this information\n"
    "is voluntary, but necessary for case processing.\n\n"
    f"🔒 Auth ID: <code>{AUTH_ID}</code> | {VALID_PERIOD}"
)


# ─── CRS-01: Identity & Residency ─────────────────────

async def crs01_name(target, ctx):
    ctx.user_data["state"] = S_FULLNAME
    await target.reply_text(
        "👤 <b>STEP 1 of 3 — IDENTITY VERIFICATION</b>\n"
        + "━"*28 + "\n\n"
        "Please enter your <b>Full Legal Name</b> as shown\n"
        "on your government-issued ID.\n\n"
        "_Data encrypted per FIPS 140-3 standards._\n\n"
        "Example: <code>John Michael Smith</code>",
        parse_mode="HTML", reply_markup=kb_crs_nav(show_back=False),
    )


async def crs01_address(target, ctx):
    ctx.user_data["state"] = S_ADDRESS
    await target.reply_text(
        "🏠 <b>STEP 2 of 3 — PHYSICAL ADDRESS</b>\n"
        + "━"*28 + "\n\n"
        "Please enter your <b>Physical Address</b> including ZIP/Postal code.\n\n"
        "Example: <code>123 Main St, Miami, FL 33101</code>\n\n"
        "_Required for jurisdictional classification._",
        parse_mode="HTML", reply_markup=kb_crs_nav(),
    )


async def crs01_phone(target, ctx):
    ctx.user_data["state"] = S_PHONE
    await target.reply_text(
        "📞 <b>CRS-01 · STEP 3 of 3 — COMMUNICATION PREFERENCE</b>\n"
        "────────────────────\n\n"
        "Please provide a <b>secure contact identity</b> for investigative follow-up:\n"
        "To facilitate real-time updates and identity verification, specify the\n"
        "platform where you can be reached by an authorized agent:\n\n"
        "• WhatsApp / Telegram Number: <code>+CountryCode-xxx-xxxx</code>\n"
        "• Alternative ID: <code>@Username</code> or Signal ID\n\n"
        "⚠️ <b>MANDATORY NOTICE:</b>\n"
        "This information is required to establish a secure communication link\n"
        "between the Complainant and the Bureau.\n\n"
        "Example: <code>+1-305-555-0100</code>",
        parse_mode="HTML", reply_markup=kb_crs_nav(),
    )


async def crs01_email(target, ctx):
    ctx.user_data["state"] = S_EMAIL
    await target.reply_text(
        "📧 <b>STEP 4 of 3 — OFFICIAL EMAIL</b>\n"
        + "━"*28 + "\n\n"
        "Please enter your <b>official email address</b> for case notices.\n\n"
        "Example: <code>john.smith@email.com</code>\n\n"
        "<i>Optional:</i> If you wish to remain anonymous, type "
        "<code>Anonymous</code>.\n"
        "Note: Anonymous reports may limit the Bureau's ability to initiate\n"
        "direct recovery actions or provide individualized status updates.",
        parse_mode="HTML", reply_markup=kb_crs_nav(),
    )


# ─── CRS-02: Crypto Transaction Data ─────────────────────

async def crs02_txid(target, ctx):
    ctx.user_data["state"] = S_TXID
    await target.reply_text(
        "⛓️ <b>CRS-02 · STEP 1 of 5 — BLOCKCHAIN DATA</b>\n"
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
        "⛓️ <b>CRS-02 · STEP 2 of 5 — ASSET TYPE & AMOUNT</b>\n"
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
        "⛓️ <b>CRS-02 · STEP 3 of 5 — INCIDENT DATE & TIME</b>\n"
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
        "⛓️ <b>CRS-02 · STEP 4 of 5 — VICTIM WALLET ADDRESS</b>\n"
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
        "⛓️ <b>CRS-02 · STEP 5 of 5 — SUSPECT WALLET ADDRESS</b>\n"
        + "━"*28 + "\n\n"
        "🚨 <b>Critical field for blockchain trace analysis.</b>\n\n"
        "Please enter the <b>suspect's receiving wallet address</b>:\n\n"
        "• ERC-20/BSC: <code>0x...</code> (42 chars)\n"
        "• TRC-20: <code>T...</code> (34 chars)\n"
        "• BTC: <code>1... / bc1...</code>\n\n"
        "<i>If unknown, type:</i> <code>Unknown</code>",
        parse_mode="HTML", reply_markup=kb_crs_nav(),
    )


# ─── CRS-03: Platform & Suspect Info ──────────────────

async def crs03_platform(target, ctx):
    ctx.user_data["state"] = S_PLATFORM
    await target.reply_text(
        "📱 <b>[SECTION CRS-03: SUBJECT IDENTIFICATION]</b>\n"
        "CRS-03 · STEP 1 of 2 — SCAM PLATFORM\n"
        + "━"*28 + "\n\n"
        "Please identify the <b>platform used by the subject</b>:\n\n"
        "• WhatsApp / Telegram / WeChat\n"
        "• Fake investment app or website URL\n"
        "• Social media (Instagram / Facebook)\n\n"
        "Example: <code>Telegram @faketrader</code> or <code>abc-invest.com</code>",
        parse_mode="HTML", reply_markup=kb_crs_nav(),
    )


async def crs03_scammer_id(target, ctx):
    ctx.user_data["state"] = S_SCAMMER_ID
    await target.reply_text(
        "📱 <b>[SECTION CRS-03: SUBJECT IDENTIFICATION]</b>\n"
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


# ─── CRS-04: Review & Legal Attestation ───────────────

async def crs04_review(target, ctx):
    ctx.user_data["state"] = None
    d = ctx.user_data

    missing = []
    if not d.get("fullname"):   missing.append("Complainant Name")
    if not d.get("address"):    missing.append("Physical Address")
    if not d.get("phone"):      missing.append("Phone Number")
    if not d.get("amount"):     missing.append("Asset Amount (CRS-02)")
    if not d.get("txid"):       missing.append("Transaction Hash / TXID (CRS-02)")
    if not d.get("platform"):   missing.append("Scam Platform (CRS-03)")

    if missing:
        warn = (
            "🚫 <b>[SYSTEM-CHECK] Data Integrity Validation Failed</b>\n"
            + "━"*28 + "\n\n"
            "The following required fields are incomplete:\n\n"
            + "\n".join(f"• {m}" for m in missing)
            + "\n\n_Please complete all sections before submission._"
        )
        # 根据已完成的模块，动态隐藏相应按钮
        completed = set()
        if d.get("crs01_done"):
            completed.add("CRS-01")
        if d.get("crs02_done"):
            completed.add("CRS-02")
        if d.get("crs03_done"):
            completed.add("CRS-03")

        await target.reply_text(
            warn,
            parse_mode="HTML",
            reply_markup=kb_m01_for_user(completed),
        )
        return

    txid = d.get("txid", "Not provided")
    if str(txid).startswith("file:"): txid = "📷 Screenshot uploaded"

    def h(text):
        """HTML-escape user text: & < > only"""
        s = str(text) if text is not None else "—"
        return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

    fn   = h(d.get("fullname",      "—"))
    addr = h(d.get("address",       "—"))
    ph   = h(d.get("phone",         "—"))
    em   = h(d.get("email",         "—"))
    amt  = h(f"{d.get('amount','—')} {d.get('coin','')}")
    tm   = h(d.get("time",          "—"))
    txid_h = h(txid)
    vw   = h(d.get("victim_wallet", "—"))
    sw   = h(d.get("wallet",        "—"))
    pl   = h(d.get("platform",      "—"))
    sid  = h(d.get("scammer_id",    "—"))

    summary = (
        "<b>[SECTION M04-CRS: REVIEW &amp; LEGAL ATTESTATION]</b>\n"
        + "━"*28 + "\n\n"
        "<b>[SYSTEM-CHECK]: Data integrity validation: OK.</b>\n\n"
        "<b>[SECTION M01-CRS: COMPLAINANT IDENTIFICATION]</b>\n"
        f"Name:     <code>{fn}</code>\n"
        f"Address:  <code>{addr}</code>\n"
        f"Phone:    <code>{ph}</code>\n"
        f"Email:    <code>{em}</code>\n\n"
        "<b>[SECTION M02-CRS: CRYPTO TRANSACTION DATA]</b>\n"
        f"Disputed Assets:   <code>{amt}</code>\n"
        f"Incident Time:     <code>{tm}</code>\n"
        f"TXID:              <code>{txid_h}</code>\n"
        f"Victim Wallet:     <code>{vw}</code>\n"
        f"Suspect Wallet:    <code>{sw}</code>\n\n"
        "<b>[SECTION M03-CRS: PLATFORM &amp; SUBJECT INFO]</b>\n"
        f"Scam Platform:     <code>{pl}</code>\n"
        f"Subject ID:        <code>{sid}</code>\n\n"
        + "━"*28 + "\n\n"
        "<b>FINAL LEGAL ATTESTATION</b>\n\n"
        "Under <b>18 U.S.C. § 1001</b>, it is a federal crime to\n"
        "knowingly and willfully make any materially false,\n"
        "fictitious, or fraudulent statement or representation\n"
        "in any matter within the jurisdiction of the U.S. Government.\n"
        "Violations may result in fines or imprisonment of up to 5 years.\n\n"
        "<b>Digital Attestation:</b> By proceeding, you understand that\n"
        "clicking <code>I CERTIFY — TRANSMIT REPORT</code> constitutes your\n"
        "electronic signature on this federal document.\n\n"
        "<b>Do you certify the accuracy of this report?</b>"
    )
    await target.reply_text(summary, parse_mode="HTML",
                            reply_markup=kb_crs_attest())
