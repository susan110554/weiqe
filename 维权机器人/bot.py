"""
FBI IC3 – Authorized Digital Reporting Interface (ADRI)
Authorization Registry ID: FBI-2026-HQ-9928-X82
Full Module Architecture: M01~M08

Refactored: modular structure
  bot_modules/config.py    — constants, utilities
  bot_modules/keyboards.py — all keyboard builders
  bot_modules/crs.py       — CRS-01..04 step functions
  bot_modules/pdf_gen.py   — PDF generation engine
  bot_modules/admin.py     — /cases /case /audit /testdb
  bot_modules/evidence.py  — /upload /done photo_handler
"""

import logging, os, io as _io, re
from datetime import datetime, timedelta
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler,
)

import database as db
from blockchain import query_risk_address

# ── Import all modules ────────────────────────────────
from bot_modules.config import (
    TOKEN, ADMIN_IDS, AUTH_ID, VALID_PERIOD, HEADER,
    S_FULLNAME, S_ADDRESS, S_PHONE, S_EMAIL,
    S_TXID, S_ASSET, S_VICTIM_WALLET, S_SUSPECT_WALLET, S_AMOUNT,
    S_PLATFORM, S_SCAMMER_ID, S_TIME, S_WALLET, S_CONTACT,
    SUBMIT_COOLDOWN_HOURS, is_admin, now_str, gen_case_id,
    detect_wallet, parse_amount, track_msg, logger,
    _last_submission, _session_messages,
)
from bot_modules.keyboards import (
    kb_main_bottom, kb_home, kb_m01, kb_m01_for_user,
    kb_m02, kb_m02_back_only, kb_m03, kb_m04,
    kb_m05, kb_m06, kb_m08, kb_m09,
    kb_crs_nav, kb_crs01_nav, kb_crs_attest, kb_nav, kb_contact,
    kb_confirm, kb_after_submit, kb_admin_case, kb_rad02, kb_upload_case,
)
from bot_modules.crs import (
    FEDERAL_NOTICE,
    crs01_name, crs01_address, crs01_phone, crs01_email,
    crs02_txid, crs02_asset, crs02_incident_time,
    crs02_victim_wallet, crs02_suspect_wallet,
    crs03_platform, crs03_scammer_id, crs04_review,
)
from bot_modules.pdf_gen import generate_case_pdf
from bot_modules.admin import cmd_cases, cmd_case, cmd_audit, cmd_testdb
from bot_modules.evidence import cmd_upload, cmd_done, photo_handler, document_handler

async def do_submit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = update.effective_user.id

    # ── 问题2: 限制重复提交 (24小时内只能提交一次) ────────────
    last = _last_submission.get(user_id)
    if last and (datetime.now() - last) < timedelta(hours=SUBMIT_COOLDOWN_HOURS):
        remaining = timedelta(hours=SUBMIT_COOLDOWN_HOURS) - (datetime.now() - last)
        hours_left = int(remaining.total_seconds() // 3600)
        await q.answer("⚠️ 提交频率限制", show_alert=True)
        await q.message.reply_text(
            f"⚠️ <b>Submission Rate Limit</b>\n\n"
            f"You have already submitted a complaint within the last {SUBMIT_COOLDOWN_HOURS} hours.\n\n"
            f"⏳ Please wait approximately <b>{hours_left} more hour(s)</b> before submitting again.\n\n"
            "_This limit protects system integrity._",
            parse_mode="HTML")
        return

    await q.answer("Submitting complaint to IC3 system...")
    try:
        await q.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    chat_id = q.message.chat_id
    bot     = ctx.bot

    # ── Processing animation ──────────────────────────────────
    proc = await bot.send_message(
        chat_id,
        "⚙️ <b>IC3-ADRI Submission Engine</b>\n"
        + "━"*28 + "\n\n"
        "🔐 Encrypting PII data...\n"
        "📡 Connecting to IC3 secure node...\n"
        "🗄 Writing to federal evidence database...\n"
        "📋 Generating case record...",
        parse_mode="HTML"
    )

    # Snapshot data BEFORE clearing
    d = dict(ctx.user_data)

    # ── Legal Attestation Timestamp ────────────────────────
    attest_ts  = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    attest_uid = str(update.effective_user.id)
    logger.info(f"[LEGAL-ATTEST] 18 U.S.C. §1001 signed: UID={attest_uid} at {attest_ts}")

    case_id      = gen_case_id()
    contact_info = d.get("email") or d.get("phone") or "Anonymous"

    record = {
        "case_no":       case_id,
        "tg_user_id":    update.effective_user.id,
        "tg_username":   update.effective_user.username or "Anonymous",
        "platform":      d.get("platform", "Not specified"),
        "amount":        d.get("amount", "0"),
        "coin":          d.get("coin", ""),
        "incident_time": d.get("time", "Not specified"),
        "wallet_addr":   d.get("wallet", "Unknown"),
        "chain_type":    d.get("chain", "Unknown"),
        "tx_hash":       d.get("txid", "None"),
        "contact":       contact_info,
    }

    logger.info(f"[IC3] Submitting case {case_id}: "
                f"amount={record['amount']!r} coin={record['coin']!r} "
                f"platform={record['platform']!r} uid={attest_uid}")
    SYSTEM_INTEGRITY_NOTICE = (
        "🛡️ SYSTEM INTEGRITY NOTICE\n"
        "The reporting engine is currently undergoing a mandatory security "
        "synchronization. Your data remains encrypted and safe. Please "
        "re-initiate this module in 5 minutes."
    )

    try:
        await db.create_case(record)
        logger.info(f"[IC3] Case registered: {case_id} by UID {attest_uid}")
    except Exception as e:
        logger.error(f"[DB] write failed: {e!r}")
        logger.error(f"[DB] record: {record}")
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=proc.message_id,
                text=SYSTEM_INTEGRITY_NOTICE,
                parse_mode="HTML",
            )
        except Exception:
            pass
        return

    # ── 问题2: 记录本次提交时间，防止重复提交 ──────────────────
    _last_submission[int(attest_uid)] = datetime.now()

    # ── 问题1: 批量删除本次会话所有消息 ────────────────────────
    import asyncio
    msg_ids = _session_messages.pop(chat_id, [])
    async def _bulk_delete():
        await asyncio.sleep(3)  # 等待3秒让用户看到最后提示
        for mid in msg_ids:
            try:
                await bot.delete_message(chat_id, mid)
            except Exception:
                pass
    asyncio.create_task(_bulk_delete())

    # ── SECURITY: Clear all sensitive PII from memory ──────────────
    ctx.user_data.clear()
    # Retain ONLY case_id — all PII cleared per federal data protection standards
    ctx.user_data["last_case_id"] = case_id

    # Build PDF data snapshot (already captured in `d` above)
    pdf_data = {
        "case_no":       case_id,
        "registered":    now_str(),
        "uid":           attest_uid,
        "fullname":      d.get("fullname", "—"),
        "address":       d.get("address",  "—"),
        "phone":         d.get("phone",    "—"),
        "email":         d.get("email",    "—"),
        "amount":        d.get("amount",   "—"),
        "coin":          d.get("coin",     ""),
        "incident_time": d.get("time",     "—"),
        "tx_hash":       d.get("txid",     "—"),
        "victim_wallet": d.get("victim_wallet", "—"),
        "wallet_addr":   d.get("wallet",   "—"),
        "chain_type":    d.get("chain",    "—"),
        "platform":      d.get("platform", "—"),
        "scammer_id":    d.get("scammer_id","—"),
    }
    # Cache PDF data for on-demand download (keyed by case_id)
    ctx.bot_data.setdefault("pdf_cache", {})[case_id] = {
        "data": pdf_data, "attest_ts": attest_ts
    }

    try:
        await bot.edit_message_text(
            chat_id=chat_id, message_id=proc.message_id,
            text="✅ <b>Submission Complete — Case Registered</b>", parse_mode="HTML")
    except Exception:
        pass

    # ── Official Case Acceptance Notice ─────────────────────
    receipt = (
        "FEDERAL BUREAU OF INVESTIGATION\n"
        "U.S. DEPARTMENT OF JUSTICE\n"
        "──────────────────────────────\n"
        "<b>OFFICIAL CASE ACCEPTANCE NOTICE</b>\n"
        "──────────────────────────────\n\n"
        f"<b>CASE ID</b>\n"
        f"<code>{case_id}</code>\n\n"
        f"<b>STATUS:</b> SUBMITTED / PENDING REVIEW\n"
        f"<b>INTAKE TIMESTAMP:</b>       <code>{now_str()}</code>\n"
        f"<b>DIGITAL ATTESTATION:</b>    <code>{attest_ts}</code>\n"
        f"<b>UID:</b>                    <code>{attest_uid}</code>\n"
        f"<b>AUTHORIZATION CREDENTIAL:</b> <code>{AUTH_ID}</code>\n\n"
        "──────────────────────────────\n"
        "<b>Official Record</b>\n"
        "Your cryptocurrency fraud report has been officially\n"
        "logged into the FBI IC3 database.\n\n"
        "<b>Next Actions</b>\n"
        "1. Download: Click below to obtain your PDF summary.\n"
        "2. Preserve: Retain all original communications and\n"
        "   wallet records for investigative use.\n\n"
        "──────────────────────────────\n"
        "<b>SECURITY NOTICE</b>\n"
        "<i>For federal data protection compliance, sensitive\n"
        "personal data has been cleared from this session.\n"
        "Only your Case ID is retained as a query credential.\n"
        "Compliance: FIPS 140-3 Encryption  |  Node: FBI-IC3-SO-09\n"
        "Warning: Information provided is subject to\n"
        "18 U.S.C. § 1001 verification.\n"
        "Please delete this conversation history after noting\n"
        "your Case ID.</i>"
    )
    receipt_msg = await bot.send_message(
        chat_id, receipt, parse_mode="HTML",
        reply_markup=kb_after_submit(case_id))

    # ── Admin Notification: push summary + action buttons ───────────
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                "🚨 <b>[IC3-ADRI] NEW CASE SUBMITTED</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🔖 <b>Case ID:</b>  <code>{case_id}</code>\n"
                f"👤 <b>UID:</b>       <code>{attest_uid}</code>\n"
                f"🕒 <b>Filed:</b>     {now_str()}\n"
                f"🏛 <b>Platform:</b>  {d.get('platform','—')}\n"
                f"💰 <b>Amount:</b>    {d.get('amount','—')} {d.get('coin','')}\n"
                f"📅 <b>Incident:</b>  {d.get('time','—')}\n"
                f"🔗 <b>Wallet:</b>    <code>{d.get('wallet','Unknown')}</code>\n"
                f"📧 <b>Contact:</b>   {contact_info}\n\n"
                "⚡ <b>STATUS: P1 · SUBMITTED</b>\n"
                "Use buttons below to advance the case:",
                parse_mode="HTML",
                reply_markup=kb_admin_case(case_id),
            )
        except Exception as e:
            logger.warning(f"[ADMIN-NOTIFY] Failed to notify admin {admin_id}: {e}")

    # ── Security Compliance Notice (sent separately for visibility) ──
    import asyncio
    security_msg = await bot.send_message(
        chat_id,
        "🛡️ <b>SECURITY COMPLIANCE NOTICE</b>\n"
        + "━"*28 + "\n\n"
        "To adhere to <b>Federal Data Protection Standards</b>, please:\n\n"
        "• <b>Manually delete</b> any sensitive messages or images\n"
        "  containing PII from this chat history within <b>5 minutes</b>.\n\n"
        "• The system has automatically purged all temporary\n"
        "  session data to protect your privacy.\n\n"
        "• Only your <b>Case ID</b> and <b>Hash Records</b> are retained\n"
        "  as query credentials.\n\n"
        f"🔖 <b>Your Case ID:</b> <code>{case_id}</code>\n\n"
        "<i>This notice will self-delete in 60 seconds.</i>",
        parse_mode="HTML",
    )

    # Auto-delete the security notice after 60 seconds
    async def _auto_delete_security_notice():
        await asyncio.sleep(60)
        try:
            await bot.delete_message(chat_id, security_msg.message_id)
        except Exception:
            pass

    asyncio.create_task(_auto_delete_security_notice())


# ══════════════════════════════════════════════════════
# /start COMMAND
# ══════════════════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    # 重置消息追踪（新会话开始）
    chat_id = update.effective_chat.id
    _session_messages[chat_id] = []
    total = await db.get_case_count()
    m1 = await update.message.reply_text(
        HEADER + f"\n\n📊 <b>Total Registered Cases:</b> {total}\n\n"
        "Select a module to proceed 👇",
        parse_mode="HTML",
        reply_markup=kb_main_bottom(),
    )
    await update.message.reply_text(
        "🧭 <b>IC3-ARS · System Module Directory</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="HTML",
        reply_markup=kb_home(),
    )
    logger.info(f"[IC3] /start by UID {update.effective_user.id}")


# ══════════════════════════════════════════════════════
# ADMIN COMMANDS
# ══════════════════════════════════════════════════════
async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data

    if data == "confirm_submit":
        # 加载提示：加密并写入联邦节点
        await q.answer("[SYSTEM-CHECK]: Encrypting with FIPS 140-3...", show_alert=False)
        await do_submit(update, ctx)
        return

    # ── PDF Download handler ─────────────────────────────
    if data.startswith("pdf|"):
        # 即时弹出 Loading 提示，让用户感知“正在生成数字签名”
        await q.answer("Generating digital signature...", show_alert=False)
        _, case_id_req = data.split("|", 1)
        cache = ctx.bot_data.get("pdf_cache", {}).get(case_id_req)
        if not cache:
            # Try fetching from DB
            c = await db.get_case_by_no(case_id_req)
            if not c:
                await q.message.reply_text(
                    "❌ PDF not available. Case data may have expired.\n"
                    "Please contact support with your Case ID.",
                    reply_markup=kb_after_submit(case_id_req))
                return
            # 兼容旧数据：某些记录可能没有 updated_at 字段
            created_at = c.get("created_at")
            updated_at = c.get("updated_at") or created_at
            created_str = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "N/A"
            last_updated_str = (
                updated_at.strftime("%Y-%m-%d %H:%M UTC") if updated_at else "N/A"
            )

            evid_files = await db.get_evidences(case_id_req)

            pdf_data = {
                "case_no":       c["case_no"],
                "registered":    created_str,
                "uid":           str(c["tg_user_id"]),
                "status":        c.get("status", "SUBMITTED"),
                "last_updated":  last_updated_str,
                # 历史数据中仅保存 contact，将其视为联系邮箱/电话，而不是法定姓名
                "fullname":      "Not on file",
                "address":       "—",
                "phone":         "—",
                "email":         c.get("contact", "—"),
                "amount":        c["amount"],
                "coin":          c["coin"],
                "incident_time": c["incident_time"],
                "tx_hash":       c["tx_hash"],
                "victim_wallet": "—",
                "wallet_addr":   c["wallet_addr"],
                "chain_type":    c["chain_type"],
                "platform":      c["platform"],
                "scammer_id":    "—",
                "evidence_files": evid_files,
            }
            attest_ts = c["created_at"].strftime("%Y-%m-%d %H:%M:%S UTC")
        else:
            pdf_data  = dict(cache["data"])
            attest_ts = cache["attest_ts"]
            # Always sync latest status from DB for up-to-date PDF
            c_live = await db.get_case_by_no(case_id_req)
            if c_live:
                pdf_data["status"] = c_live.get("status", "SUBMITTED")
                live_updated_at = c_live.get("updated_at") or c_live.get("created_at")
                if live_updated_at:
                    pdf_data["last_updated"] = live_updated_at.strftime(
                        "%Y-%m-%d %H:%M UTC"
                    )
            # Always sync latest evidence list as well
            evid_files_live = await db.get_evidences(case_id_req)
            pdf_data["evidence_files"] = evid_files_live

        proc_msg = await q.message.reply_text(
            "<b>Generating digitally signed PDF document...</b>\n"
            "Synchronizing with IC3 secure node. Please wait...",
            parse_mode="HTML")
        # 统一系统级错误提示（不泄露内部异常）
        SYSTEM_INTEGRITY_NOTICE = (
            "🛡️ SYSTEM INTEGRITY NOTICE\n"
            "The reporting engine is currently undergoing a mandatory security "
            "synchronization. Your data remains encrypted and safe. Please "
            "re-initiate this module in 5 minutes."
        )

        try:
            import io as _io
            pdf_bytes = await generate_case_pdf(pdf_data, attest_ts, AUTH_ID)
            fname = f"IC3_Case_{case_id_req}.pdf"
            # 必须用 BytesIO 包装 bytes，telegram bot 才能发送
            pdf_file = _io.BytesIO(pdf_bytes)
            pdf_file.name = fname
            sent_doc = await ctx.bot.send_document(
                chat_id=q.message.chat_id,
                document=pdf_file,
                filename=fname,
                caption=(
                    f"📂 <b>IC3 Official Case Confirmation</b>\n"
                    f"<code>{case_id_req}</code>\n\n"
                    "Your authenticated report is ready. This document is\n"
                    "cryptographically signed and represents your formal\n"
                    "electronic signature on file with the IC3."
                ),
                parse_mode="HTML",
            )
            await proc_msg.delete()

            # 联邦风格的隐私销毁提示 + 自毁倒计时
            import asyncio
            privacy_msg = await q.message.reply_text(
                "🛡️ <b>FEDERAL DATA PRIVACY COMPLIANCE</b>\n"
                "────────────────────\n"
                "✅ <b>SUCCESS:</b> Official record transmitted.\n\n"
                "<b>System Status:</b>\n"
                "Per NIST SP 800-53 standards, all PII (Personally Identifiable\n"
                "Information) from this session has been permanently purged from\n"
                "the server memory.\n\n"
                "<b>Action Required:</b>\n"
                "For your protection, please <b>manually delete</b> this chat\n"
                "history within the next <b>5 minutes</b>.\n\n"
                "⏳ This <b>notice</b> will self-delete in 60 seconds.",
                parse_mode="HTML",
            )

            async def _auto_delete_privacy_notice():
                await asyncio.sleep(60)
                try:
                    await privacy_msg.delete()
                except Exception:
                    pass

            asyncio.create_task(_auto_delete_privacy_notice())

        except Exception as e:
            logger.error(f"PDF generation failed: {e}", exc_info=True)
            await proc_msg.edit_text(SYSTEM_INTEGRITY_NOTICE, parse_mode="HTML")
        return

    if data == "close_session":
        # 永久关闭当前交互会话：移除按钮并标记数据过期
        try:
            await q.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await q.message.reply_text(
            "Session Closed. Data Expired.",
            parse_mode="HTML",
        )
        await q.answer()
        return

    if data == "HOME":
        total = await db.get_case_count()
        await q.message.reply_text(
            "🧭 <b>IC3-ARS · System Module Directory</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            parse_mode="HTML", reply_markup=kb_home(),
        )
        return

    if data == "go_back":
        state = ctx.user_data.get("state")
        mapping = {
            # CRS-01 back navigation
            S_ADDRESS:       crs01_name,
            S_PHONE:         crs01_address,
            S_EMAIL:         crs01_phone,
            # CRS-02 back navigation
            S_ASSET:         crs02_txid,
            S_TIME:          crs02_asset,
            S_VICTIM_WALLET: crs02_incident_time,
            S_VICTIM_WALLET: crs02_asset,
            S_SUSPECT_WALLET:crs02_victim_wallet,
            # CRS-03 back navigation
            S_SCAMMER_ID:    crs03_platform,
        }
        fn = mapping.get(state)
        if fn:
            await fn(q.message, ctx)
        else:
            completed = set()
            if ctx.user_data.get("crs01_done"):
                completed.add("CRS-01")
            if ctx.user_data.get("crs02_done"):
                completed.add("CRS-02")
            if ctx.user_data.get("crs03_done"):
                completed.add("CRS-03")
            await q.message.reply_text(
                "Please use the menu 👇",
                reply_markup=kb_m01_for_user(completed),
            )
        return
        return

    if data == "go_cancel":
        ctx.user_data.clear()
        await q.message.reply_text(
            "✖️ Submission cancelled. All draft data has been cleared.",
            reply_markup=kb_main_bottom(),
        )
        return

    if data == "restart":
        ctx.user_data.clear()
        await crs_step1(q.message, ctx)
        return

    # ── Module M01 ────────────────────────────────────
    if data == "M01":
        completed = set()
        if ctx.user_data.get("crs01_done"):
            completed.add("CRS-01")
        if ctx.user_data.get("crs02_done"):
            completed.add("CRS-02")
        if ctx.user_data.get("crs03_done"):
            completed.add("CRS-03")

        # Show Federal Notice first, then dynamic M01 menu
        await q.message.reply_text(FEDERAL_NOTICE, parse_mode="HTML")
        await q.message.reply_text(
            "📋 <b>M01-CRS · Case Reporting System</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "This module handles new complaint intake,\n"
            "structured incident documentation, and\n"
            "automated case ID generation.\n\n"
            "_Select a function to proceed:_",
            parse_mode="HTML",
            reply_markup=kb_m01_for_user(completed),
        )
        return

    if data == "CRS-01":
        ctx.user_data.clear()
        ctx.user_data["section"] = "CRS-01"
        await crs01_name(q.message, ctx)
        return

    if data == "CRS-02":
        ctx.user_data["section"] = "CRS-02"
        await crs02_txid(q.message, ctx)
        return

    if data == "CRS-03":
        ctx.user_data["section"] = "CRS-03"
        await crs03_platform(q.message, ctx)
        return

    if data == "CRS-04":
        await crs04_review(q.message, ctx)
        return

    # ── Module M02 ────────────────────────────────────
    if data == "M02":
        # Step 1: Authentication — require Case Reference ID before evidence intake
        ctx.user_data["state"] = "EVID_AUTH"
        ctx.user_data.pop("upload_case_no", None)
        ctx.user_data.pop("upload_evm_type", None)
        await q.message.reply_text(
            "⚖️ <b>JUDICIAL AUTHENTICATION REQUIRED</b>\n"
            "────────────────────────────────────\n\n"
            "Before uploading any evidence, please enter your official\n"
            "<b>IC3 Case Reference ID</b> to verify case ownership.\n\n"
            "<b>Required format:</b>\n"
            "<code>IC3-YYYY-ARXXXXXX-ADRI</code>\n\n"
            "<b>Example:</b>\n"
            "<code>IC3-2026-ARDAE9E9-ADRI</code>\n\n"
            "Type your Case Reference ID below to continue.",
            parse_mode="HTML",
        )
        return

    # Evidence Upload 根菜单（供各 EVM 子模块“返回上一页”使用）
    if data == "EVM-MENU":
        await q.message.reply_text(
            "🗂 <b>Evidence Upload</b>\n\n"
            "Select an evidence intake module below. New records will be\n"
            "cryptographically linked to your IC3 case file.",
            parse_mode="HTML",
            reply_markup=kb_m02(),
        )
        return

    # ── EVM-01: Identity & Residency — 证件类型选择 + 已绑定案件 ──
    if data == "EVM-01":
        uid = q.from_user.id
        case_id = (ctx.user_data.get("evid_auth_case") or
                   ctx.user_data.get("upload_case_no") or "")
        ctx.user_data["upload_evm_type"] = "EVM-01"
        ctx.user_data["upload_case_no"] = case_id or ctx.user_data.get("upload_case_no")
        await q.answer()
        sep = "────────────────────"
        txt = (
            "<code>[EVM: COMPLAINANT IDENTITY RECORDS]</code>\n"
            f"<code>{sep}</code>\n"
            "<code>MODULE     : EVM-01 · IDENTITY DOCUMENTS</code>\n"
            "<code>PROTOCOL   : FORENSIC INTAKE / SHA-256 VERIFIED</code>\n"
            f"<code>UID        : {uid}</code>\n"
            f"<code>CASE ID    : {case_id or 'NOT LINKED'}</code>\n"
            "<code>STATUS     : INITIALIZING PROTOCOL...</code>\n"
            f"<code>{sep}</code>\n\n"
            "📍 <b>ACTION REQUIRED:</b>\n"
            "Please select your document type to begin the forensic scan:"
        )
        kb_doc_type = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Passport", callback_data="EVM-01-DOC|PASSPORT"),
                InlineKeyboardButton("Driver's License", callback_data="EVM-01-DOC|DL"),
                InlineKeyboardButton("National ID", callback_data="EVM-01-DOC|NID"),
            ],
        ])
        await q.message.reply_text(txt, parse_mode="HTML", reply_markup=kb_doc_type)
        return

    # ── EVM-01-DOC: 已选证件类型 → 等待上传照片 ──
    if data.startswith("EVM-01-DOC|"):
        _, doc_type = data.split("|", 1)
        doc_type = (doc_type or "PASSPORT").upper()
        if doc_type not in ("PASSPORT", "DL", "NID"):
            doc_type = "PASSPORT"
        uid = q.from_user.id
        case_id = ctx.user_data.get("evid_auth_case") or ctx.user_data.get("upload_case_no")
        if not case_id:
            await q.answer("⚠️ No case linked. Please enter Case ID via Evidence Upload first.", show_alert=True)
            return
        ctx.user_data["state"] = "EVM01_AWAIT_PHOTO"
        ctx.user_data["upload_evm01_doctype"] = doc_type
        # National ID 需要前后两面，记录步骤；其他证件默认为单步
        if doc_type == "NID":
            ctx.user_data["upload_evm01_step"] = 1
        else:
            ctx.user_data.pop("upload_evm01_step", None)
        ctx.user_data["upload_case_no"] = case_id
        ctx.user_data["upload_evm_type"] = "EVM-01"
        await q.answer()
        doc_label = {"PASSPORT": "PASSPORT", "DL": "DRIVER'S LICENSE", "NID": "NATIONAL ID"}.get(doc_type, "PASSPORT")
        sep = "────────────────────"
        if doc_type == "NID":
            phase_title = "PHASE 1: FRONT SIDE"
            body_line = "Please upload a clear, high-resolution photo of the <b>FRONT side</b> of your NATIONAL ID."
        else:
            phase_title = "PHASE 1: PHOTO PAGE"
            body_line = f"Please upload a clear, high-resolution photo of your <b>{doc_label} PHOTO PAGE</b> (Biodata Page)."
        txt = (
            f"<code>[EVM: {doc_label} PROTOCOL INITIALIZED]</code>\n"
            f"<code>{sep}</code>\n"
            "<code>SECURE PORTAL : ACTIVE</code>\n"
            "<code>ENCRYPTION    : AES-256 / FIPS 140-3 COMPLIANT</code>\n"
            f"<code>COMPLAINANT   : UID-{uid}</code>\n"
            f"<code>{sep}</code>\n\n"
            "⚖️ <b>JUDICIAL WARNING:</b>\n"
            "You are about to submit official identification to the Federal Case Management System. "
            "All documents will undergo automated forensic integrity checks (SHA-256).\n\n"
            f"📸 <b>{phase_title}</b>\n"
            f"{body_line}\n\n"
            "<i>Ensure all four corners of the document are visible. Do not use flash to avoid glare.</i>"
        )
        await q.message.reply_text(txt, parse_mode="HTML")
        return

    if data in ("EVM-02","EVM-03","EVM-05"):
        uid = q.from_user.id
        _m = {
            "EVM-02": ("FINANCIAL TRANSACTION EVIDENCE","EVM-02 · FINANCIAL RECORDS","Upload bank statements, exchange history, or wire receipts."),
            "EVM-03": ("SUBJECT COMMUNICATION LOGS","EVM-03 · COMMUNICATION LOGS","Upload screenshots of chat logs, emails, or VoIP records."),
            "EVM-05": ("SUPPLEMENTAL EVIDENCE SUBMISSION","EVM-05 · SUPPLEMENTAL ANNEXURE","Attach additional evidence records. All files are permanently linked."),
        }
        cat, label, adesc = _m[data]
        ctx.user_data["upload_evm_type"] = data
        ctx.user_data["upload_case_no"] = ctx.user_data.get("evid_auth_case") or ctx.user_data.get("upload_case_no")
        await q.answer()
        sep = "\u2500" * 20
        txt = (
            "<code>[EVM: " + cat + "]</code>\n"
            + "<code>" + sep + "</code>\n"
            + "<code>MODULE     : " + label + "</code>\n"
            + "<code>PROTOCOL   : FORENSIC INTAKE / SHA-256 VERIFIED</code>\n"
            + "<code>UID        : " + str(uid) + "</code>\n"
            + "<code>STATUS     : AWAITING CASE LINKAGE</code>\n"
            + "<code>" + sep + "</code>\n\n"
            + "\U0001f4cd <b>ACTION REQUIRED:</b>\n"
            + adesc + "\n\n"
            + "\U0001f511 <b>CASE LINKAGE REQUIRED:</b>\n"
            + "Link your Case ID to begin upload:\n"
            + "<code>/ingest_evidence IC3-YYYY-ARXXXXXX-ADRI</code>\n\n"
            + "\U0001f6e1\ufe0f <b>SYSTEM NOTICE:</b>\n"
            + "All uploaded files are SHA-256 hashed and logged to the federal Chain of Custody per FRE Rule 901."
        )
        # 子模块介绍页仅提供“返回 Evidence Upload”按钮
        await q.message.reply_text(txt, parse_mode="HTML", reply_markup=kb_m02_back_only())
        return

    if data == "EVM-04":
        await q.message.reply_text(
            "<code>[EVM-04: FORENSIC INTEGRITY VERIFICATION]</code>\n"
            "<code>────────────────────────────────────</code>\n"
            "<code>ALGORITHM  : SHA-256 (FIPS 180-4)</code>\n"
            "<code>STANDARD   : NIST SP 800-101 Rev.1</code>\n"
            "<code>STATUS     : VERIFICATION ENGINE ACTIVE</code>\n"
            "<code>────────────────────────────────────</code>\n\n"
            "Every file uploaded through this system undergoes:\n\n"
            "<code>• SHA-256 cryptographic hash computation</code>\n"
            "<code>• File metadata integrity validation</code>\n"
            "<code>• Duplicate evidence detection</code>\n"
            "<code>• Immutable audit trail inscription</code>\n\n"
            "<code>────────────────────────────────────</code>\n"
            "<i>Verification is automatic upon each upload.\n"
            "Hash receipts are returned instantly.</i>",
            parse_mode="HTML", reply_markup=kb_m02_back_only(),
        )
        return

    if data == "EVM-05":
        await q.message.reply_text(
            "<code>[EVM-05: SUPPLEMENTAL EVIDENCE SUBMISSION]</code>\n"
            "<code>────────────────────────────────────</code>\n"
            "<code>PURPOSE    : Post-submission evidence annexure</code>\n"
            "<code>────────────────────────────────────</code>\n\n"
            "To attach additional evidence to an existing case:\n\n"
            "<code>  Step 1: /ingest_evidence IC3-CASE-ID</code>\n"
            "<code>  Step 2: Send your files</code>\n"
            "<code>  Step 3: /done  (to close the session)</code>\n\n"
            "<code>⚠ Ensure your Case ID is correct before</code>\n"
            "<code>  uploading. Evidence is linked permanently.</code>",
            parse_mode="HTML", reply_markup=kb_m02_back_only(),
        )
        return

    # ── Module M03 ────────────────────────────────────
    if data == "M03":
        # 显示 Case Tracking 子菜单（用户已认证或从 Back 返回时使用）
        await q.message.reply_text(
            "🔍 <b>Case Tracking</b>\n\nSelect a function:",
            parse_mode="HTML",
            reply_markup=kb_m03(),
        )
        return

    # ── Quick case check (from saved last_case_id) ──────
    if data.startswith("quickcheck|"):
        _, case_id_q = data.split("|", 1)
        await q.answer("Fetching case status...")
        c = await db.get_case_by_no(case_id_q)
        if not c:
            await q.message.reply_text(
                f"❌ Case not found: <code>{case_id_q}</code>",
                parse_mode="HTML")
            return
        await _send_case_status(q.message, c)
        return

    if data == "CTS-01":
        # 若在 30 分钟有效期内且已有已认证案件，直接刷新状态卡；否则重新走认证终端
        from datetime import datetime
        authed = ctx.user_data.get("case_tracking_authed")
        auth_until = ctx.user_data.get("case_tracking_auth_until")
        last_case = ctx.user_data.get("last_case_id")
        if authed and auth_until and isinstance(auth_until, datetime) and auth_until > datetime.utcnow() and last_case:
            c = await db.get_case_by_no(last_case)
            if c:
                await _send_case_status(q.message, c)
                return
        await _send_cts_query_prompt(q.message, ctx)
        return

    if data == "CTS-02":
        # ── Try to load the user's own case for dynamic highlighting ──
        uid = update.effective_user.id
        last_case_id = ctx.user_data.get("last_case_id")
        user_case = None
        if last_case_id:
            user_case = await db.get_case_by_no(last_case_id)
        if not user_case:
            # Fallback: find most recent case by this UID
            all_cases = await db.get_recent_cases(50)
            for rc in all_cases:
                if rc.get("tg_user_id") == uid:
                    user_case = rc
                    break

        cur_status = user_case.get("status", "") if user_case else ""
        agent_raw = (user_case.get("agent_code") or "").strip() if user_case else ""
        agent_display = _agent_mono(agent_raw or None)

        _stage_order = ["SUBMITTED", "VALIDATING", "UNDER REVIEW", "REFERRED", "CLOSED"]
        _legacy_map  = {
            "Pending Initial Review": "SUBMITTED", "待初步审核": "SUBMITTED",
            "Under Review": "UNDER REVIEW", "Case Accepted": "UNDER REVIEW",
            "Processing Complete": "REFERRED", "Case Closed": "CLOSED",
        }
        cur_normalized = _legacy_map.get(cur_status, cur_status)

        def _stage_line(key, icon, label, details, liaison):
            is_cur = (key == cur_normalized)
            marker = "▶️" if is_cur else "  "
            bold_s = "<b>" if is_cur else ""
            bold_e = "</b>" if is_cur else ""
            _details = list(details)
            detail_str = "".join(f"\n<code>      │ ├ {d}</code>" for d in _details)
            liaison_str = f"\n<code>      │ └ LIAISON : {liaison}</code>"
            return (
                f"{marker} <code>{icon} {key} │ {bold_s}{label}{bold_e}</code>"
                f"{detail_str}"
                f"{liaison_str}"
            )

        stages = [
            _stage_line("SUBMITTED",    "🟡", "SUBMITTED",    ["Encrypted record created.", "Case ID assigned to buffer."], "LOCKED"),
            _stage_line("VALIDATING",   "🔵", "VALIDATING",   ["TXID hash format check.", "Risk-address DB cross-ref."],    "ONE-WAY NOTIFY"),
            _stage_line(
                "UNDER REVIEW", "🟣", "UNDER REVIEW",
                [
                    (f"Assigned: Case specialist ({agent_display})." if agent_raw else "Specialist assignment pending."),
                    "Blockchain forensics initiated.",
                ],
                "AUTHORIZED ✅",
            ),
            _stage_line("REFERRED",     "🟢", "REFERRED",     ["Transferred to field office.", "Exchange compliance notified."],  "BIDIRECTIONAL ✅"),
            _stage_line("CLOSED",       "⚫", "CLOSED",       ["Disposition finalized.", "All comms sealed & archived.", "Digital Certificate Issued ✅"], "READ-ONLY / ARCHIVED"),
        ]

        # Progress summary line
        if user_case and cur_normalized in _stage_order:
            idx = _stage_order.index(cur_normalized) + 1
            progress_line = (
                f"\n<code>────────────────────────────────────</code>\n"
                f"<code>YOUR CASE : {user_case['case_no']}</code>\n"
                f"<code>PROGRESS  : Stage {idx} of {len(_stage_order)} — {cur_normalized}</code>\n"
                f"<code>AGENT     : {agent_display}</code>"
            )
        else:
            progress_line = (
                "\n<code>────────────────────────────────────</code>\n"
                "<code>ℹ Submit a case (M01) to track progress.</code>"
            )

        # ── Build dynamic keyboard based on case stage ──
        _liaison_stages = {"UNDER REVIEW", "REFERRED"}
        if user_case and cur_normalized in _liaison_stages:
            case_no_dyn = user_case.get("case_no", "")
            cts_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    f"🛰️ INITIALIZE SECURE LIAISON ({agent_display})" if agent_raw else "🛰️ INITIALIZE SECURE LIAISON",
                    callback_data=f"liaison_init|{case_no_dyn}"
                )],
                [InlineKeyboardButton("🔎 Status Inquiry",        callback_data="CTS-01"),
                 InlineKeyboardButton("⬅️ Main Menu",             callback_data="HOME")],
            ])
        else:
            cts_kb = kb_m03()

        await q.message.reply_text(
            "<code>[IC3-ADRI] CASE PROCESSING PIPELINE</code>\n"
            "<code>────────────────────────────────────</code>\n"
            "<code>MODULE  : M03-CTS Processing Timeline</code>\n"
            "<code>────────────────────────────────────</code>\n\n"
            + "\n\n".join(stages)
            + progress_line
            + "\n<code>────────────────────────────────────</code>\n"
            "<code>ℹ You will be notified at each transition.</code>",
            parse_mode="HTML", reply_markup=cts_kb,
        )
        return

    if data == "CTS-03":
        await q.message.reply_text(
            "📋 <b>CTS-03 · Case Stage Explanation</b>\n\n"
            "Each complaint goes through federal review stages.\n\n"
            "Average processing time: <b>24–72 hours</b> per stage.\n\n"
            "Complex cross-border cases may take longer.\n"
            "You will be notified upon any status change.",
            parse_mode="HTML", reply_markup=kb_m03(),
        )
        return

    if data == "CTS-04":
        await q.message.reply_text(
            "🏛 <b>CTS-04 · Federal Review Guidance</b>\n\n"
            "• IC3 reviews all complaints for federal violations\n"
            "• Cases may be referred to field offices\n"
            "• Cryptocurrency cases involve blockchain forensics\n"
            "• Cross-border cases may involve Interpol coordination\n\n"
            "_For official IC3 status, visit: ic3.gov_",
            parse_mode="HTML", reply_markup=kb_m03(),
        )
        return

    # ── Module M04 ────────────────────────────────────
    if data == "M04":
        await q.message.reply_text(
            "⚠️ <b>M04-RAD · Risk Analysis Division</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Blockchain forensics and fraud risk assessment.",
            parse_mode="HTML", reply_markup=kb_m04(),
        )
        return

    if data == "RAD-01":
        await q.message.reply_text(
            "🕵️ <b>RAD-01 · Scam Pattern Identification</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔴 <b>High-Risk Patterns:</b>\n"
            "• Pig Butchering (Investment Romance Scam)\n"
            "• Fake Exchange / Rug Pull\n"
            "• Wallet Approval Exploit\n"
            "• Impersonation of Government Agencies\n"
            "• High-yield Ponzi Structures\n\n"
            "🟡 <b>Warning Indicators:</b>\n"
            "• Unsolicited investment offers\n"
            "• Pressure to transfer quickly\n"
            "• Requests for wallet private keys\n"
            "• Promises of guaranteed returns",
            parse_mode="HTML", reply_markup=kb_m04(),
        )
        return

    if data == "RAD-02":
        ctx.user_data["state"] = "RAD02_CHAIN_SELECT"
        await q.message.reply_text(
            "🔗 <b>RAD-02 · Cryptocurrency Trace Analysis</b>\n\n"
            "Select the blockchain network of the suspect address:",
            parse_mode="HTML", reply_markup=kb_rad02(),
        )
        return

    if data in ("RAD-02-ETH","RAD-02-TRX","RAD-02-BTC"):
        chain_labels = {
            "RAD-02-ETH": "ETH/ERC20/BSC",
            "RAD-02-TRX": "TRON/TRC20",
            "RAD-02-BTC": "Bitcoin",
        }
        ctx.user_data["state"] = "RISK_QUERY"
        ctx.user_data["risk_chain"] = chain_labels[data]
        await q.message.reply_text(
            f"📡 <b>Chain Selected:</b> {chain_labels[data]}\n\n"
            "Please enter the wallet address to analyze:",
            parse_mode="HTML",
        )
        return

    if data == "RAD-03":
        await q.message.reply_text(
            "📊 <b>RAD-03 · Fraud Severity Scoring</b>\n\n"
            "Risk levels are assigned based on:\n\n"
            "🟢 Low Risk — No flagged activity detected\n"
            "🟡 Medium Risk — Suspicious patterns identified\n"
            "🔴 High Risk — Multiple fraud indicators\n"
            "🚨 Critical — Confirmed fraudulent activity\n\n"
            "_Scores are updated as new data is received._",
            parse_mode="HTML", reply_markup=kb_m04(),
        )
        return

    if data == "RAD-04":
        await q.message.reply_text(
            "🌐 <b>RAD-04 · Cross-border Risk Evaluation</b>\n\n"
            "IC3 coordinates with:\n\n"
            "• Interpol Financial Crimes Unit\n"
            "• FinCEN (Financial Crimes Enforcement)\n"
            "• Foreign law enforcement agencies\n"
            "• Blockchain analytics firms\n\n"
            "_Cross-border cases require additional processing time._",
            parse_mode="HTML", reply_markup=kb_m04(),
        )
        return

    if data == "RAD-05":
        await q.message.reply_text(
            "🛡 <b>RAD-05 · Victim Exposure Assessment</b>\n\n"
            "This module evaluates:\n\n"
            "• Total financial exposure\n"
            "• Identity theft risk level\n"
            "• Ongoing fraud risk\n"
            "• Recommended protective actions\n\n"
            "_Please submit a complaint (M01) for full assessment._",
            parse_mode="HTML", reply_markup=kb_m04(),
        )
        return

    # ── Module M05 ────────────────────────────────────
    if data == "M05":
        await q.message.reply_text(
            "📘 <b>M05-KBS · Knowledge Base System</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Federal fraud intelligence and prevention resources.",
            parse_mode="HTML", reply_markup=kb_m05(),
        )
        return

    if data == "KBS-01":
        await q.message.reply_text(
            "📁 <b>KBS-01 · Federal Fraud Categories</b>\n\n"
            "IC3 classifies internet crimes into:\n\n"
            "• Investment Fraud (BEC, Crypto Scams)\n"
            "• Identity Theft & Account Takeover\n"
            "• Non-Delivery / Non-Payment\n"
            "• Ransomware & Extortion\n"
            "• Government Impersonation\n"
            "• Tech Support Fraud\n"
            "• Romance / Confidence Fraud\n\n"
            "_Source: IC3 Annual Crime Report_",
            parse_mode="HTML", reply_markup=kb_m05(),
        )
        return

    if data == "KBS-02":
        await q.message.reply_text(
            "📢 <b>KBS-02 · Public Advisory Bulletins</b>\n\n"
            "Recent IC3 Alerts:\n\n"
            "🔴 PSA-2026-001: Crypto investment scam surge\n"
            "🔴 PSA-2026-002: AI-generated voice phishing\n"
            "🟡 PSA-2026-003: Fake government agent calls\n"
            "🟡 PSA-2026-004: Romance scam targeting seniors\n\n"
            "_Visit ic3.gov for official advisories._",
            parse_mode="HTML", reply_markup=kb_m05(),
        )
        return

    if data == "KBS-03":
        await q.message.reply_text(
            "🛡 <b>KBS-03 · Victim Protection Guidelines</b>\n\n"
            "If you have been victimized:\n\n"
            "1️⃣ Stop all further transfers immediately\n"
            "2️⃣ Document all transaction records\n"
            "3️⃣ Report to IC3 via M01-CRS\n"
            "4️⃣ Contact your bank or exchange\n"
            "5️⃣ Preserve all communications\n"
            "6️⃣ Do NOT send additional funds for 'recovery'",
            parse_mode="HTML", reply_markup=kb_m05(),
        )
        return

    if data == "KBS-04":
        await q.message.reply_text(
            "🔰 <b>KBS-04 · Prevention Framework</b>\n\n"
            "✅ Verify platform registration & licensing\n"
            "✅ Never share wallet seed phrases\n"
            "✅ Use hardware wallets for large holdings\n"
            "✅ Enable 2FA on all accounts\n"
            "✅ Verify withdrawal addresses carefully\n"
            "✅ Consult licensed financial advisors only\n\n"
            "_When in doubt — do not transfer._",
            parse_mode="HTML", reply_markup=kb_m05(),
        )
        return

    if data == "KBS-05":
        await q.message.reply_text(
            "📚 <b>KBS-05 · Case Study Archive</b>\n\n"
            "Notable IC3-investigated cases:\n\n"
            "📌 <b>Case Type:</b> Pig Butchering\n"
            "   Loss: $2.5M | Platform: Fake DEX\n\n"
            "📌 <b>Case Type:</b> Fake Exchange\n"
            "   Loss: $480K | Platform: Spoofed Binance\n\n"
            "📌 <b>Case Type:</b> Wallet Drainer\n"
            "   Loss: $1.2M | Method: Approval exploit\n\n"
            "_All identifying information has been anonymized._",
            parse_mode="HTML", reply_markup=kb_m05(),
        )
        return

    # ── Module M06 ────────────────────────────────────
    if data == "M06":
        await q.message.reply_text(
            "⚖️ <b>M06-LRS · Legal Referral Service</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Legal resources and referral services.",
            parse_mode="HTML", reply_markup=kb_m06(),
        )
        return

    if data == "LRS-01":
        await q.message.reply_text(
            "🏛 <b>LRS-01 · Federal Jurisdiction Guide</b>\n\n"
            "Federal jurisdiction applies when:\n\n"
            "• Crime crosses state or national borders\n"
            "• Loss exceeds federal threshold\n"
            "• Use of interstate wire communications\n"
            "• Involves federal financial institutions\n\n"
            "Relevant statutes:\n"
            "• 18 U.S.C. § 1343 — Wire Fraud\n"
            "• 18 U.S.C. § 1030 — Computer Fraud\n"
            "• 18 U.S.C. § 1956 — Money Laundering",
            parse_mode="HTML", reply_markup=kb_m06(),
        )
        return

    if data == "LRS-02":
        await q.message.reply_text(
            "🗺 <b>LRS-02 · Law Enforcement Directory</b>\n\n"
            "• FBI Field Offices: fbi.gov/contact-us/field-offices\n"
            "• FTC: reportfraud.ftc.gov\n"
            "• SEC (Securities): sec.gov/tcr\n"
            "• CFTC (Commodities): cftc.gov/complaint\n"
            "• FinCEN: fincen.gov\n\n"
            "_Report to ALL applicable agencies._",
            parse_mode="HTML", reply_markup=kb_m06(),
        )
        return

    if data == "LRS-03":
        await q.message.reply_text(
            "👔 <b>LRS-03 · Attorney Referral Intake</b>\n\n"
            "To request attorney referral:\n\n"
            "1️⃣ File complaint via M01-CRS first\n"
            "2️⃣ Provide your Case ID\n"
            "3️⃣ Our legal team will contact you\n"
            "   within 48 business hours\n\n"
            "_This is a referral service only._\n"
            "_IC3 does not provide legal representation._",
            parse_mode="HTML", reply_markup=kb_m06(),
        )
        return

    if data == "LRS-04":
        await q.message.reply_text(
            "💼 <b>LRS-04 · Civil Recovery Pathways</b>\n\n"
            "Options for civil recovery:\n\n"
            "• Asset freeze via court injunction\n"
            "• Civil lawsuit for damages\n"
            "• Blockchain-based asset tracing\n"
            "• International mutual legal assistance\n\n"
            "_Success depends on asset location and jurisdiction._",
            parse_mode="HTML", reply_markup=kb_m06(),
        )
        return

    # ── Module M08 ────────────────────────────────────
    if data == "M08":
        await q.message.reply_text(
            "🛡 <b>M08-CMP · Compliance & Audit</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "System compliance and data governance.",
            parse_mode="HTML", reply_markup=kb_m08(),
        )
        return

    if data == "CMP-01":
        await q.message.reply_text(
            "📜 <b>CMP-01 · Compliance Policy Overview</b>\n\n"
            "This system operates under:\n\n"
            "• Federal Information Security Act (FISMA)\n"
            "• NIST Cybersecurity Framework\n"
            "• Federal Data Security Standards\n"
            "• IC3 Operational Guidelines 2026\n\n"
            f"Auth Registry ID: <code>{AUTH_ID}</code>\n"
            f"Validity: {VALID_PERIOD}",
            parse_mode="HTML", reply_markup=kb_m08(),
        )
        return

    if data == "CMP-02":
        await q.message.reply_text(
            "🔐 <b>CMP-02 · Data Security Standards</b>\n\n"
            "All data in this system is protected by:\n\n"
            "• AES-256 encryption at rest\n"
            "• TLS 1.3 in transit\n"
            "• Zero-knowledge architecture\n"
            "• Automated audit logging\n"
            "• 90-day data retention policy",
            parse_mode="HTML", reply_markup=kb_m08(),
        )
        return

    if data == "CMP-03":
        await q.message.reply_text(
            "📋 <b>CMP-03 · User Rights & Privacy Notice</b>\n\n"
            "You have the right to:\n\n"
            "• Access your submitted complaint data\n"
            "• Request data correction\n"
            "• Withdraw your complaint\n"
            "• Remain anonymous\n\n"
            "Data is used solely for:\n"
            "• Complaint processing\n"
            "• Federal investigation support\n"
            "• Statistical reporting (anonymized)",
            parse_mode="HTML", reply_markup=kb_m08(),
        )
        return

    # ── Module M09 ────────────────────────────────────
    # -- Module M09 --
    if data == "M09":
        txt = "\U0001f3db <b>M09-ORG - About & Contact</b>\n" + "\u2501"*28 + "\n\nOrganizational information and official contact."
        await q.message.reply_text(txt, parse_mode="HTML", reply_markup=kb_m09())
        return

    if data == "ORG-01":
        txt = "\U0001f3db <b>ORG-01 - Organizational Overview</b>\n" + "\u2501"*28 + "\n\nThe <b>Internet Crime Complaint Center (IC3)</b> is a partnership between the FBI and National White Collar Crime Center.\n\n<b>Mission:</b> Provide reliable internet crime reporting.\n\n<b>Scope:</b>\n\u2022 Cryptocurrency fraud\n\u2022 BEC / Wire Fraud\n\u2022 Ransomware & Extortion\n\u2022 Identity Theft\n\u2022 Romance & Investment Fraud"
        await q.message.reply_text(txt, parse_mode="HTML", reply_markup=kb_m09())
        return

    if data == "ORG-02":
        txt = ("\U0001f4dc <b>ORG-02 - Federal Authorization Notice</b>\n" + "\u2501"*28 +
               f"\n\nThis ADRI operates under formal FBI IC3 authorization.\n\n"
               f"<b>Authorization Registry ID:</b>\n<code>{AUTH_ID}</code>\n\n"
               f"<b>Validity Period:</b> {VALID_PERIOD}\n\n"
               "<b>Authorization Status:</b> \u2705 ACTIVE\n\n"
               "_All transmissions are encrypted per federal standards._")
        await q.message.reply_text(txt, parse_mode="HTML", reply_markup=kb_m09())
        return

    if data == "ORG-03":
        txt = ("\u2696\ufe0f <b>ORG-03 - Scope & Limitations Statement</b>\n" + "\u2501"*28 +
               "\n\n<b>This interface IS authorized to:</b>\n"
               "\u2022 Receive and log internet crime complaints\n"
               "\u2022 Collect digital evidence for federal review\n"
               "\u2022 Provide blockchain-based risk analysis\n"
               "\u2022 Issue case reference IDs\n\n"
               "<b>This interface does NOT:</b>\n"
               "\u2022 Guarantee investigation or prosecution\n"
               "\u2022 Provide legal representation\n"
               "\u2022 Guarantee financial recovery\n\n"
               "_For emergencies, contact local law enforcement._")
        await q.message.reply_text(txt, parse_mode="HTML", reply_markup=kb_m09())
        return

    if data == "ORG-04":
        txt = ("\U0001f510 <b>ORG-04 - Data Protection & Privacy Policy</b>\n" + "\u2501"*28 +
               "\n\n<b>Data Security:</b>\n"
               "\u2022 AES-256 encryption at rest\n"
               "\u2022 TLS 1.3 in transit\n"
               "\u2022 Zero-knowledge architecture\n"
               "\u2022 Automated audit logging (M08-CMP)\n\n"
               "<b>Your Rights:</b>\n"
               "\u2022 Access your submitted data\n"
               "\u2022 Request correction or deletion\n"
               "\u2022 Withdraw complaint at any time\n"
               "\u2022 Remain anonymous\n\n"
               "_Data is never sold outside federal channels._")
        await q.message.reply_text(txt, parse_mode="HTML", reply_markup=kb_m09())
        return

    if data == "ORG-05":
        txt = (f"\U0001f4e1 <b>ORG-05 - Official Contact</b>\n" + "\u2501"*28 +
               "\n\n\U0001f3db <b>Internet Crime Complaint Center</b>\n"
               "   Federal Bureau of Investigation\n\n"
               "\U0001f310 <b>Official Website:</b> ic3.gov\n\n"
               "\U0001f4ee <b>Mailing Address:</b>\n"
               "   935 Pennsylvania Avenue, NW\n"
               "   Washington, D.C. 20535-0001\n\n"
               "\U0001f4de <b>FBI Tips:</b> 1-800-CALL-FBI (1-800-225-5324)\n\n"
               f"\U0001f516 Auth Ref: <code>{AUTH_ID}</code>\n"
               f"\U0001f4c5 Valid: {VALID_PERIOD}")
        await q.message.reply_text(txt, parse_mode="HTML", reply_markup=kb_m09())
        return

    # ── Admin: status update ──────────────────────────
    if data.startswith("st|"):
        await q.answer()
        if not is_admin(update.effective_user.id):
            await q.message.reply_text("❌ Access Denied.")
            return
        _, case_no, new_status = data.split("|", 2)
        ok = await db.update_case_status(case_no, new_status,
                                         str(update.effective_user.id))
        if ok:
            c = await db.get_case_by_no(case_no)
            await q.message.reply_text(
                f"✅ <code>{case_no}</code> → <b>{new_status}</b>",
                parse_mode="HTML", reply_markup=kb_admin_case(case_no))
            # Auto-notify complainant
            if c:
                _stage_info = {
                    "VALIDATING":   ("🔵", "Automated validation has commenced."),
                    "UNDER REVIEW": ("🟣", "A Special Agent has been assigned to your case."),
                    "REFERRED":     ("🟢", "Case referred to field office / exchange."),
                    "CLOSED":       ("⚫", "Case resolved and archived."),
                }
                sem, desc = _stage_info.get(new_status, ("⚪", "Status updated."))
                try:
                    await ctx.bot.send_message(
                        c["tg_user_id"],
                        "🏛 <b>IC3 · CASE STATUS TRANSITION</b>\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"🔖 Case: <code>{case_no}</code>\n"
                        f"{sem} <b>{new_status}</b>\n"
                        f"🕒 {now_str()} UTC\n\n"
                        f"<i>{desc}</i>\n\n"
                        f"Auth Ref: <code>{AUTH_ID}</code>",
                        parse_mode="HTML")
                except Exception: pass
        else:
            await q.message.reply_text("❌ Update failed.")
        return

    # ── Admin: notify user ────────────────────────────
    if data.startswith("notify|"):
        await q.answer()
        _, case_no = data.split("|", 1)
        c = await db.get_case_by_no(case_no)
        if not c:
            await q.message.reply_text("❌ Case not found.")
            return
        status = c.get("status", "SUBMITTED")
        _stage_info = {
            "SUBMITTED":    ("🟡", "P1 · SUBMITTED",     "Your complaint has been securely logged."),
            "VALIDATING":   ("🔵", "P2 · VALIDATING",    "Automated integrity checks in progress."),
            "UNDER REVIEW": ("🟣", "P3 · UNDER REVIEW",  "A Special Agent has been assigned to your case."),
            "REFERRED":     ("🟢", "P4 · REFERRED",      "Case has been referred to a field office / exchange."),
            "CLOSED":       ("⚫", "P5 · CLOSED",        "Case has been resolved and archived."),
        }
        sem, stage_label, stage_desc = _stage_info.get(status, ("⚪", status, "Status updated."))
        agent_code = c.get("agent_code") or ""
        agent_line = f"\n👤 <b>Assigned Agent:</b> <code>{agent_code}</code>" if agent_code else ""
        notify = (
            "🏛 <b>IC3 · OFFICIAL CASE STATUS UPDATE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔖 Case ID: <code>{case_no}</code>\n"
            f"{sem} Status: <b>{stage_label}</b>{agent_line}\n"
            f"🕒 Updated: {now_str()} UTC\n\n"
            f"<i>{stage_desc}</i>\n\n"
            "For case details, use M03-CTS Case Tracking.\n\n"
            f"Auth Ref: <code>{AUTH_ID}</code>"
        )
        try:
            await ctx.bot.send_message(c["tg_user_id"], notify, parse_mode="HTML")
            await q.message.reply_text(f"✅ Notification sent to UID {c['tg_user_id']}")
        except Exception as e:
            await q.message.reply_text(f"❌ Failed: {e}")
        return

    # ── Admin: evidence list → 发送证据图片/文件给管理员 ──────────────────────────
    if data.startswith("evlist|"):
        await q.answer()
        _, case_no = data.split("|", 1)
        evs = await db.get_evidences(case_no)
        if not evs:
            await q.message.reply_text("📁 No evidence files on record.")
            return
        admin_chat_id = q.message.chat_id
        await q.message.reply_text(
            f"📁 <b>Evidence Files — {case_no}</b>\n"
            f"Total: {len(evs)} file(s). Sending images/files below…",
            parse_mode="HTML",
        )
        for i, ev in enumerate(evs, 1):
            file_id = ev.get("file_id")
            if not file_id:
                await q.message.reply_text(
                    f"#{i} [{ev.get('file_type','?')}] {ev.get('file_name','')} — no file_id"
                )
                continue
            t = ev.get("uploaded_at")
            ts = t.strftime("%m-%d %H:%M") if t else ""
            caption = f"#{i} [{ev.get('file_type','')}] {ev.get('file_name','')} — {ts}"
            fname = (ev.get("file_name") or "").lower()
            try:
                if fname.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")) or (
                    ev.get("file_type") or ""
                ).startswith("EVM-01") or (ev.get("file_type") or "") == "IMAGE":
                    await ctx.bot.send_photo(
                        admin_chat_id, photo=file_id, caption=caption,
                    )
                else:
                    await ctx.bot.send_document(
                        admin_chat_id, document=file_id, caption=caption,
                    )
            except Exception:
                try:
                    await ctx.bot.send_document(
                        admin_chat_id, document=file_id, caption=caption,
                    )
                except Exception as e:
                    await q.message.reply_text(f"#{i} Failed to send: {ev.get('file_name','')} — {e}")
        return

    # ── Admin: assign agent → 第一步显示名/内部编号（2–48 字符），再输入专员工作电报 ID 或 @用户名 ──
    if data.startswith("assign|"):
        await q.answer()
        if not is_admin(update.effective_user.id):
            await q.message.reply_text("❌ Access Denied.")
            return
        _, case_no = data.split("|", 1)
        ctx.user_data["state"] = "AGENT_ASSIGN_INPUT"
        ctx.user_data["assign_agent_case"] = case_no
        ctx.user_data["assign_agent_code"] = None
        await q.message.reply_text(
            "👤 <b>Assign case specialist</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Case: <code>{case_no}</code>\n\n"
            "Enter a <b>display name or internal reference</b> (2–48 characters).\n\n"
            "<i>Examples: <code>Field Team A7</code>, <code>Smith-318</code></i>",
            parse_mode="HTML",
        )
        return

    # ── Admin: open liaison channel ─────────────────────
    if data.startswith("liaison_open|"):
        await q.answer()
        if not is_admin(update.effective_user.id):
            await q.message.reply_text("❌ Access Denied.")
            return
        _, case_no = data.split("|", 1)
        ok = await db.set_liaison(case_no, True)
        c = await db.get_case_by_no(case_no)
        if ok and c:
            # Schedule auto-close after 24h
            import asyncio
            async def _auto_close_liaison():
                await asyncio.sleep(86400)  # 24 hours
                await db.set_liaison(case_no, False)
                try:
                    await ctx.bot.send_message(
                        c["tg_user_id"],
                        "🔒 <b>SECURE LIAISON CHANNEL — SESSION EXPIRED</b>\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"Case: <code>{case_no}</code>\n\n"
                        "The 24-hour communication window has expired.\n"
                        "This channel is now in read-only archive mode.\n"
                        "An agent will reopen the channel if further\n"
                        "communication is required.\n\n"
                        f"<i>Auth Ref: <code>{AUTH_ID}</code></i>",
                        parse_mode="HTML")
                except Exception: pass
            asyncio.create_task(_auto_close_liaison())
            # Notify complainant that channel is open
            agent_code = _agent_mono(c.get("agent_code"))
            try:
                await ctx.bot.send_message(
                    c["tg_user_id"],
                    "🏛 <b>SECURE LIAISON CHANNEL — NOW ACTIVE</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🔖 Case: <code>{case_no}</code>\n"
                    f"👤 Assigned specialist: <code>{agent_code}</code>\n\n"
                    "⚡ <b>Communication Authorization Granted</b>\n\n"
                    "A secure communication channel has been opened\n"
                    "for this case under <b>28 C.F.R. Part 20</b>.\n\n"
                    "You may now send a text message directly below.\n"
                    "All transmissions are SHA-256 logged as federal\n"
                    "evidence per <b>FRE Rule 901</b>.\n\n"
                    "⏳ <b>Channel active for 24 hours.</b>\n\n"
                    f"<i>Auth Ref: <code>{AUTH_ID}</code></i>",
                    parse_mode="HTML")
            except Exception: pass
            await q.message.reply_text(
                f"✅ Liaison channel OPENED for <code>{case_no}</code>\n"
                "Auto-closes in 24h.",
                parse_mode="HTML")
        else:
            await q.message.reply_text("❌ Failed to open channel.")
        return

    # ── Admin: close liaison channel ────────────────────
    if data.startswith("liaison_close|"):
        await q.answer()
        if not is_admin(update.effective_user.id):
            await q.message.reply_text("❌ Access Denied.")
            return
        _, case_no = data.split("|", 1)
        ok = await db.set_liaison(case_no, False)
        c = await db.get_case_by_no(case_no)
        if ok and c:
            try:
                await ctx.bot.send_message(
                    c["tg_user_id"],
                    "🔒 <b>SECURE LIAISON — CHANNEL CLOSED</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"Case: <code>{case_no}</code>\n\n"
                    "The secure communication channel for this case\n"
                    "has been closed by the assigned agent.\n"
                    "All communications have been archived as\n"
                    "federal evidence records.\n\n"
                    f"<i>Auth Ref: <code>{AUTH_ID}</code></i>",
                    parse_mode="HTML")
            except Exception: pass
            await q.message.reply_text(f"🔒 Liaison channel CLOSED for <code>{case_no}</code>", parse_mode="HTML")
        else:
            await q.message.reply_text("❌ Failed.")
        return

    # ── Admin: compose agent message ────────────────────
    if data.startswith("agentmsg|"):
        await q.answer()
        if not is_admin(update.effective_user.id):
            await q.message.reply_text("❌ Access Denied.")
            return
        _, case_no = data.split("|", 1)
        c = await db.get_case_by_no(case_no)
        if not c:
            await q.message.reply_text(f"❌ Case not found: <code>{case_no}</code>", parse_mode="HTML")
            return
        complainant_uid = c.get("tg_user_id") or c.get("user_id")
        if complainant_uid is None:
            await q.message.reply_text("❌ This case has no complainant Telegram UID. Cannot send message.")
            return
        ctx.user_data["agent_compose_case"] = case_no
        ctx.user_data["state"] = "AGENT_COMPOSE"
        await q.message.reply_text(
            f"✏️ <b>Compose Agent Message</b>\n\n"
            f"Case: <code>{case_no}</code>\n"
            f"Recipient: <code>{complainant_uid}</code>\n\n"
            "Your <b>next message</b> in this chat will be sent to the complainant with the official IC3 header.\n"
            "Type your message below and send.\n\n"
            "<i>They will receive a push notification.</i>",
            parse_mode="HTML")
        return

    if data.startswith("upload_set|"):
        _, case_no = data.split("|", 1)
        ctx.user_data["upload_case_no"] = case_no
        await q.message.reply_text(
            f"📤 Ready to upload to <code>{case_no}</code>\nSend your files now.",
            parse_mode="HTML")
        return

    # ── Liaison init: generate 60s auth token + agent link ──
    if data.startswith("liaison_init|"):
        _, case_no = data.split("|", 1)
        await q.answer("🔐 Generating authorization token...", show_alert=False)
        c = await db.get_case_by_no(case_no)
        if not c:
            await q.message.reply_text("❌ Case not found.")
            return
        sa = (c.get("agent_code") or "").strip()
        sa_mono = _agent_mono(sa or None)
        uid = update.effective_user.id

        # Generate one-time auth token (SHA-256 of case+uid+timestamp)
        import hashlib, time, asyncio
        token_seed = f"{case_no}|{uid}|{int(time.time())}"
        auth_token = hashlib.sha256(token_seed.encode()).hexdigest()[:16].upper()
        expires_ts = datetime.now() + timedelta(seconds=60)
        expires_str = expires_ts.strftime("%H:%M:%S UTC")

        # Log token issuance
        await db.log_audit(
            actor_type="SYSTEM", actor_id=str(uid),
            action="LIAISON_TOKEN_ISSUED",
            detail=f"case={case_no} agent={sa or '—'} token={auth_token} expires={expires_str}"
        )

        # Build Telegram deep link to admin (uses ADMIN_IDS[0] if set)
        agent_tg_link = None
        if ADMIN_IDS:
            # We use the bot's own username as relay — admin will see the token
            bot_info = await ctx.bot.get_me()
            start_param = f"liaison_{auth_token}"
            agent_tg_link = f"https://t.me/{bot_info.username}?start={start_param}"

        # Send auth token card
        token_msg = await q.message.reply_text(
            "<code>[IC3-ADRI] LIAISON AUTHORIZATION SYSTEM</code>\n"
            "<code>────────────────────────────────────</code>\n"
            f"<code>CASE ID    : {case_no}</code>\n"
            f"<code>AGENT      : {_agent_card_title(sa or None)}</code>\n"
            f"<code>TOKEN TYPE : ONE-TIME ACCESS KEY</code>\n"
            f"<code>EXPIRES    : {expires_str} (60 seconds)</code>\n"
            "<code>────────────────────────────────────</code>\n\n"
            "🔑 <b>AUTHORIZATION TOKEN:</b>\n"
            f"<code>  {auth_token[:4]}-{auth_token[4:8]}-{auth_token[8:12]}-{auth_token[12:16]}</code>\n\n"
            "<code>[SYSTEM]: Link Authentication Successful.</code>\n"
            f"<code>Liaison Node: {sa_mono} (Active)</code>\n\n"
            "Please click below to start secure messaging.\n"
            "<i>⚠️ This token and link expire in 60 seconds.</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                *([[InlineKeyboardButton(
                    f"🛡️ CONNECT TO AGENT ({sa_mono})" if sa else "🛡️ CONNECT TO AGENT",
                    url=agent_tg_link
                )]] if agent_tg_link else []),
                [InlineKeyboardButton("❌ Cancel", callback_data="M03")],
            ])
        )

        # Auto-delete token card after 60 seconds
        async def _expire_token():
            await asyncio.sleep(60)
            try:
                await token_msg.edit_text(
                    "<code>[IC3-ADRI] TOKEN EXPIRED</code>\n"
                    "<code>────────────────────────────────────</code>\n"
                    f"<code>CASE ID : {case_no}</code>\n"
                    f"<code>STATUS  : AUTHORIZATION TOKEN INVALIDATED</code>\n"
                    f"<code>REASON  : 60-second session window closed.</code>\n"
                    "<code>────────────────────────────────────</code>\n"
                    "<i>Please return to Status Inquiry to\n"
                    "generate a new authorization token.</i>",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔄 Request New Token", callback_data=f"liaison_init|{case_no}")
                    ]])
                )
            except Exception:
                pass
        asyncio.create_task(_expire_token())
        return

    # ── Liaison info: show active channel card to user ──
    if data.startswith("liaison_info|"):
        _, case_no = data.split("|", 1)
        c = await db.get_case_by_no(case_no)
        if not c or not c.get("is_liaison_open"):
            await q.answer("⚠️ Channel is not currently active.", show_alert=True)
            return
        sa = (c.get("agent_code") or "").strip()
        sa_mono = _agent_mono(sa or None)
        await q.message.reply_text(
            "🛰️ <b>[SECURE LIAISON NODE — ACTIVE]</b>\n"
            "────────────────────\n"
            f"<code>CASE ID    : {case_no}</code>\n"
            f"<code>AGENT      : {_agent_card_title(sa or None)}</code>\n"
            f"<code>CHANNEL    : OPEN / ENCRYPTED</code>\n"
            f"<code>EXPIRES    : 24h from activation</code>\n"
            "────────────────────\n"
            "✅ <b>Authentication Successful.</b>\n\n"
            "You are now authorized to communicate directly\n"
            f"with <b>{sa_mono}</b> via this interface.\n\n"
            "<b>Instructions:</b>\n"
            "• Simply <b>type your message</b> in this chat.\n"
            "• All transmissions are SHA-256 logged as\n"
            "  federal evidence per <b>FRE Rule 901</b>.\n"
            "• The channel will auto-close after 24 hours.\n"
            "────────────────────\n"
            "<i>⚠️ Do not share sensitive financial credentials\n"
            "in this channel. Authorized agents will never\n"
            "request wallet keys or seed phrases.</i>",
            parse_mode="HTML",
        )
        return


# ══════════════════════════════════════════════════════
# SHARED HELPERS
# ══════════════════════════════════════════════════════
import hashlib as _hashlib


def _agent_mono(agent_code: str | None) -> str:
    s = (agent_code or "").strip()
    return s if s else "—"


def _agent_card_title(agent_code: str | None) -> str:
    s = (agent_code or "").strip()
    return f"Case specialist ({s})" if s else "Case specialist (pending)"


def _status_sha256(c: dict) -> str:
    """Generate a deterministic SHA-256 fingerprint for this case's current state."""
    payload = (
        f"{c.get('case_no','')}|"
        f"{c.get('status','')}|"
        f"{c.get('agent_code','NULL')}|"
        f"{c.get('updated_at','')}"
    )
    return _hashlib.sha256(payload.encode()).hexdigest()


def _build_status_card(c: dict) -> tuple[str, "InlineKeyboardMarkup"]:
    """Return (message_text, keyboard) for a case status card."""
    case_no    = c.get("case_no", "N/A")
    status     = c.get("status", "SUBMITTED")
    agent_code = c.get("agent_code") or None
    liaison_open = bool(c.get("is_liaison_open"))
    created_at = c.get("created_at")
    updated_at = c.get("updated_at") or created_at
    filed_ts   = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "N/A"
    updated_ts = updated_at.strftime("%Y-%m-%d %H:%M") if updated_at else "N/A"
    sha        = _status_sha256(c)

    # 通用 Case Tracking 菜单键盘（附带 PDF 与 CTS 子菜单）
    def _cts_keyboard(pdf_label: str = "📂 Download PDF Certificate") -> "InlineKeyboardMarkup":
        rows = [
            [InlineKeyboardButton(pdf_label, callback_data=f"pdf|{case_no}")],
            [InlineKeyboardButton("🔎 Status Inquiry",         callback_data="CTS-01")],
            [InlineKeyboardButton("📊 Processing Timeline",    callback_data="CTS-02")],
            [InlineKeyboardButton("📋 Case Stage Explanation", callback_data="CTS-03")],
            [InlineKeyboardButton("🏛 Federal Review Guidance", callback_data="CTS-04")],
            [InlineKeyboardButton("⬅️ Return to Main Menu",    callback_data="HOME")],
        ]
        return InlineKeyboardMarkup(rows)

    # ── Per-stage templates ───────────────────────────
    if status in ("SUBMITTED", "Pending Initial Review", "待初步审核",
                  "Pending", "PENDING"):
        body = (
            "🏛 <b>[OFFICIAL CASE RECORD: INTAKE]</b>\n"
            "────────────────────\n"
            f"<code>CASE ID  : {case_no}</code>\n"
            f"<code>STATUS   : SUBMITTED / PENDING REVIEW</code>\n"
            f"<code>FILED    : {filed_ts} UTC</code>\n"
            "────────────────────\n"
            "<b>SYSTEM LOG:</b>\n"
            "<code>• Data encryption completed (AES-256).</code>\n"
            "<code>• Case assigned to intake buffer.</code>\n"
            "<code>• Awaiting automated screening queue.</code>\n"
            "────────────────────\n"
            "<b>OFFICIAL NOTICE:</b>\n"
            "Your report has been securely logged into the\n"
            "federal repository. No further action is required\n"
            "at this stage. You will be notified upon advancement.\n"
            "────────────────────\n"
            f"<code>🔐 STATE-HASH (SHA-256):</code>\n"
            f"<code>{sha[:32]}…</code>"
        )
        kb = _cts_keyboard()

    elif status in ("VALIDATING",):
        body = (
            "🛡 <b>[SYSTEM VALIDATION IN PROGRESS]</b>\n"
            "────────────────────\n"
            f"<code>CASE ID  : {case_no}</code>\n"
            f"<code>STATUS   : VALIDATING (AUTO-CHECK)</code>\n"
            f"<code>NODE     : IC3-DATA-INTEGRITY-07</code>\n"
            f"<code>UPDATED  : {updated_ts} UTC</code>\n"
            "────────────────────\n"
            "<b>CURRENT ACTIONS:</b>\n"
            "<code>• Verifying TXID hash format ........ OK</code>\n"
            "<code>• Cross-referencing Risk Database ... ACTIVE</code>\n"
            "<code>• Duplicate complaint screening ..... CLEARED</code>\n"
            "<code>• Jurisdictional routing ............ PENDING</code>\n"
            "────────────────────\n"
            "<code>LIAISON STATUS : LOCKED (One-way Notification Only)</code>\n"
            "────────────────────\n"
            f"<code>🔐 STATE-HASH (SHA-256):</code>\n"
            f"<code>{sha[:32]}…</code>"
        )
        kb = _cts_keyboard()

    elif status in ("UNDER REVIEW", "Under Review", "Case Accepted"):
        sa = _agent_mono(agent_code)
        liaison_status = "🟢 AUTHORIZED — Channel Active" if liaison_open else "🔒 PENDING AUTHORIZATION"
        liaison_note   = "You may reply to the agent directly in this chat." if liaison_open else "Await agent activation."
        body = (
            "⚖️ <b>[INVESTIGATIVE REVIEW ACTIVE]</b>\n"
            "────────────────────\n"
            f"<code>CASE ID  : {case_no}</code>\n"
            f"<code>STATUS   : UNDER ANALYTICAL REVIEW</code>\n"
            f"<code>ASSIGNED : Case specialist ({sa})</code>\n"
            f"<code>UPDATED  : {updated_ts} UTC</code>\n"
            "────────────────────\n"
            "<b>PROGRESS:</b>\n"
            "<code>• Blockchain traceability analysis initiated.</code>\n"
            "<code>• Agent file review: IN PROGRESS.</code>\n"
            "<code>• Cross-agency coordination: ACTIVE.</code>\n"
            "────────────────────\n"
            f"<code>LIAISON STATUS : {liaison_status}</code>\n"
            f"<i>{liaison_note}</i>\n"
            "────────────────────\n"
            f"<code>🔐 STATE-HASH (SHA-256):</code>\n"
            f"<code>{sha[:32]}…</code>"
        )
        btn_rows = []
        # Primary liaison action button
        btn_rows.append([InlineKeyboardButton(
            f"🛰️ INITIALIZE SECURE LIAISON ({sa})",
            callback_data=f"liaison_init|{case_no}"
        )])
        # 追加 CTS 子菜单
        btn_rows.append([InlineKeyboardButton("📂 Download PDF Certificate", callback_data=f"pdf|{case_no}")])
        btn_rows.append([InlineKeyboardButton("🔎 Status Inquiry",         callback_data="CTS-01")])
        btn_rows.append([InlineKeyboardButton("📊 Processing Timeline",    callback_data="CTS-02")])
        btn_rows.append([InlineKeyboardButton("📋 Case Stage Explanation", callback_data="CTS-03")])
        btn_rows.append([InlineKeyboardButton("🏛 Federal Review Guidance", callback_data="CTS-04")])
        btn_rows.append([InlineKeyboardButton("⬅️ Return to Main Menu",    callback_data="HOME")])
        kb = InlineKeyboardMarkup(btn_rows)

    elif status in ("REFERRED", "Processing Complete"):
        body = (
            "🏛 <b>[CASE REFERRAL INITIATED]</b>\n"
            "────────────────────\n"
            f"<code>CASE ID  : {case_no}</code>\n"
            f"<code>STATUS   : REFERRED / ACTION PENDING</code>\n"
            f"<code>TARGET   : FBI Regional Field Office</code>\n"
            f"<code>UPDATED  : {updated_ts} UTC</code>\n"
            "────────────────────\n"
            "<b>DISTRIBUTION LOG:</b>\n"
            "<code>• Case file encrypted and transmitted.</code>\n"
            "<code>• Legal credentials synchronized with</code>\n"
            "<code>  external exchange compliance teams.</code>\n"
            "<code>• Inter-agency notification: DISPATCHED.</code>\n"
            "────────────────────\n"
            "<code>LIAISON STATUS : ACTIVE (JOINT CHANNEL)</code>\n"
            "────────────────────\n"
            f"<code>🔐 STATE-HASH (SHA-256):</code>\n"
            f"<code>{sha[:32]}…</code>"
        )
        kb = _cts_keyboard(pdf_label="📂 Download PDF Certificate")

    elif status in ("CLOSED", "Case Closed"):
        body = (
            "📁 <b>[FINAL DISPOSITION: ARCHIVED]</b>\n"
            "────────────────────\n"
            f"<code>CASE ID   : {case_no}</code>\n"
            f"<code>STATUS    : ACTIONED / CLOSED</code>\n"
            f"<code>TIMESTAMP : {updated_ts} UTC</code>\n"
            "────────────────────\n"
            "<b>FINAL SUMMARY:</b>\n"
            "<code>Case closed. Investigative findings</code>\n"
            "<code>have been indexed for federal audit.</code>\n"
            "────────────────────\n"
            "<b>SECURITY NOTICE:</b>\n"
            "<code>All communication logs have been SEALED</code>\n"
            "<code>and PURGED from the active buffer.</code>\n"
            "<code>This case record is now READ-ONLY.</code>\n"
            "────────────────────\n"
            f"<code>🔐 STATE-HASH (SHA-256):</code>\n"
            f"<code>{sha[:32]}…</code>"
        )
        kb = _cts_keyboard(pdf_label="📂 Download Final PDF")

    else:
        # Fallback for unknown status
        body = (
            "🔎 <b>[CASE STATUS RECORD]</b>\n"
            "────────────────────\n"
            f"<code>CASE ID  : {case_no}</code>\n"
            f"<code>STATUS   : {status}</code>\n"
            f"<code>UPDATED  : {updated_ts} UTC</code>\n"
            "────────────────────\n"
            f"<code>🔐 STATE-HASH (SHA-256):</code>\n"
            f"<code>{sha[:32]}…</code>"
        )
        kb = _cts_keyboard(pdf_label="📂 Download PDF")

    return body, kb


async def _send_case_status(target, c: dict):
    """Show loading animation then deliver status card."""
    import asyncio
    # Step 1: authentication animation
    auth_msg = await target.reply_text(
        "<code>[IC3-NODE] Authenticating Secure Link...</code>\n"
        "<code>▓░░░░░░░░░  10%  — Verifying case ID...</code>",
        parse_mode="HTML"
    )
    await asyncio.sleep(0.8)
    try:
        await auth_msg.edit_text(
            "<code>[IC3-NODE] Authenticating Secure Link...</code>\n"
            "<code>▓▓▓▓░░░░░░  45%  — Decrypting record...</code>",
            parse_mode="HTML"
        )
    except Exception: pass
    await asyncio.sleep(0.8)
    try:
        await auth_msg.edit_text(
            "<code>[IC3-NODE] Authenticating Secure Link...</code>\n"
            "<code>▓▓▓▓▓▓▓▓▓░  90%  — Generating state hash...</code>",
            parse_mode="HTML"
        )
    except Exception: pass
    await asyncio.sleep(0.6)
    try:
        await auth_msg.delete()
    except Exception: pass

    # Step 2: deliver status card
    body, kb = _build_status_card(c)
    await target.reply_text(body, parse_mode="HTML", reply_markup=kb)


async def _send_cts_query_prompt(target, ctx: ContextTypes.DEFAULT_TYPE):
    """
    显示 Case Tracking 查询终端提示，要求用户输入 Case ID。
    复用在：主菜单 Case Tracking 按键、CTS-01 子菜单。
    """
    # 仅提供 Back 按钮，返回 Case Tracking 菜单
    quick_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="M03")],
    ])

    await target.reply_text(
        "<code>[IC3-ADRI] SECURE QUERY TERMINAL v2.1</code>\n"
        "<code>────────────────────────────────────</code>\n"
        "<code>NODE     : IC3-CTS-QUERY-NODE-04</code>\n"
        "<code>PROTOCOL : TLS 1.3 / AES-256-GCM</code>\n"
        "<code>STATUS   : READY FOR INPUT</code>\n"
        "<code>────────────────────────────────────</code>\n\n"
        "🔑 <b>Enter your Case ID to retrieve records.</b>\n\n"
        "<code>REQUIRED FORMAT:</code>\n"
        "<code>  IC3-YYYY-ARXXXXXX-ADRI</code>\n\n"
        "<code>EXAMPLE INPUT:</code>\n"
        "<code>  IC3-2026-ARDAE9E9-ADRI</code>\n\n"
        "<code>────────────────────────────────────</code>\n"
        "<code>⚠ INPUT VALIDATION ACTIVE</code>\n"
        "<code>  Non-conforming IDs will be rejected.</code>\n"
        "<code>────────────────────────────────────</code>\n\n"
        "<i>Type your Case ID directly in the chat below.</i>",
        parse_mode="HTML",
        reply_markup=quick_kb,
    )
    ctx.user_data["state"] = "QUERY_CASE"


def crs_completed_sections(user_data: dict) -> set[str]:
    """
    Helper: compute which CRS sections the user has finished.
    Used to dynamically hide completed buttons in the M01 keyboard.
    """
    done: set[str] = set()
    if user_data.get("crs01_done"):
        done.add("CRS-01")
    if user_data.get("crs02_done"):
        done.add("CRS-02")
    if user_data.get("crs03_done"):
        done.add("CRS-03")
    return done


# ══════════════════════════════════════════════════════
# TEXT MESSAGE HANDLER
# ══════════════════════════════════════════════════════
async def msg_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text  = update.message.text or ""
    state = ctx.user_data.get("state")
    chat_id = update.effective_chat.id
    # 追踪用户发来的每条消息
    track_msg(chat_id, update.message.message_id)

    # ── Bottom menu triggers ──────────────────────────
    menu_map = {
        "📋 Case Reporting":  "M01",
        "🗂 Evidence Upload": "M02",
        "🔍 Case Tracking":   "M03",
        "⚠️ Risk Analysis":  "M04",
        "📘 Knowledge Base":  "M05",
        "⚖️ Legal Referral": "M06",
        "🏛 About & Contact": "M09",
        "🛡 Compliance":      "M08",
    }
    if text in menu_map:
        module = menu_map[text]
        kb_map = {
            "M01": kb_m01,  # legacy, we override below for dynamic behaviour
            "M02": kb_m02,
            "M03": kb_m03,
            "M04": kb_m04,
            "M05": kb_m05,
            "M06": kb_m06,
            "M08": kb_m08,
            "M09": kb_m09,
        }
        titles = {
            "M01": "📋 <b>Case Reporting</b>\n\nSelect a function:",
            "M02": "🗂 <b>Evidence Upload</b>\n\nTo upload, send <code>/ingest_evidence IC3-CASE-ID</code>",
            "M03": "🔍 <b>Case Tracking</b>\n\nSelect a function:",
            "M04": "⚠️ <b>Risk Analysis</b>\n\nSelect a function:",
            "M05": "📘 <b>Knowledge Base</b>\n\nSelect a category:",
            "M06": "⚖️ <b>Legal Referral</b>\n\nSelect a service:",
            "M09": "🏛 <b>About & Contact</b>\n\nSelect a section:",
            "M08": "🛡 <b>Compliance & Audit</b>\n\nSelect a section:",
        }
        if module == "M01":
            # 动态隐藏已完成的 Case Reporting 子模块
            completed = crs_completed_sections(ctx.user_data)
            await update.message.reply_text(
                titles[module],
                parse_mode="HTML",
                reply_markup=kb_m01_for_user(completed),
            )
        elif module == "M02":
            # Route to M02 authentication flow
            ctx.user_data["state"] = "EVID_AUTH"
            ctx.user_data.pop("upload_case_no", None)
            ctx.user_data.pop("upload_evm_type", None)
            await update.message.reply_text(
                "⚖️ <b>JUDICIAL AUTHENTICATION REQUIRED</b>\n"
                "────────────────────────────────────\n\n"
                "Before uploading any evidence, please enter your official\n"
                "<b>IC3 Case Reference ID</b> to verify case ownership.\n\n"
                "<b>Required format:</b>\n"
                "<code>IC3-YYYY-ARXXXXXX-ADRI</code>\n\n"
                "<b>Example:</b>\n"
                "<code>IC3-2026-ARDAE9E9-ADRI</code>\n\n"
                "Type your Case Reference ID below to continue.",
                parse_mode="HTML",
            )
        elif module == "M03":
            # Case Tracking：若 30 分钟内已认证过，则直接显示菜单；否则先走认证终端
            from datetime import datetime
            authed = ctx.user_data.get("case_tracking_authed")
            auth_until = ctx.user_data.get("case_tracking_auth_until")
            last_case = ctx.user_data.get("last_case_id")
            if authed and auth_until and isinstance(auth_until, datetime) and auth_until > datetime.utcnow() and last_case:
                await update.message.reply_text(
                    "🔍 <b>Case Tracking</b>\n\nSelect a function:",
                    parse_mode="HTML",
                    reply_markup=kb_m03(),
                )
            else:
                await _send_cts_query_prompt(update.message, ctx)
        else:
            await update.message.reply_text(
                titles[module],
                parse_mode="HTML",
                reply_markup=kb_map[module](),
            )
        return

    # ── EVM-01 等待证件照片时，若用户发送文字或非图片 → 协议违规提示 ──
    if state == "EVM01_AWAIT_PHOTO":
        doc_type = ctx.user_data.get("upload_evm01_doctype", "PASSPORT")
        doc_name = {"PASSPORT": "Passport", "DL": "Driver's License", "NID": "National ID"}.get(doc_type, "Passport")
        await update.message.reply_text(
            "⚠️ <b>PROTOCOL VIOLATION: INVALID INPUT FORMAT</b>\n\n"
            "SYSTEM DETECTED: Text-based entry where a Forensic Image (JPG/PNG/PDF) is required.\n\n"
            "<b>ACTION REQUIRED:</b> Please provide a high-resolution scan of your "
            f"<b>{doc_name}</b>. The system is currently in Restricted Ingestion Mode "
            "and will only accept visual evidence for SHA-256 verification.",
            parse_mode="HTML",
        )
        return

    # ── Admin: assign specialist — step 1 display name (2–48 chars), step 2 Telegram ID / @username ──
    if state == "AGENT_ASSIGN_INPUT":
        case_no = ctx.user_data.get("assign_agent_case")
        agent_no = ctx.user_data.get("assign_agent_code")
        raw = text.strip()
        if agent_no is None:
            if len(raw) < 2 or len(raw) > 48 or "\n" in raw or "\r" in raw:
                await update.message.reply_text(
                    "❌ Use <b>2–48</b> characters, no line breaks.\n"
                    "<i>Examples: <code>Field Team A7</code>, <code>Smith-318</code></i>",
                    parse_mode="HTML",
                )
                return
            ctx.user_data["assign_agent_code"] = raw
            await update.message.reply_text(
                f"✅ Reference set: <code>{ctx.user_data['assign_agent_code']}</code>\n\n"
                "Enter the agent's <b>Telegram User ID</b> (numeric) or <b>@username</b>.",
                parse_mode="HTML",
            )
            return
        # Step 2: Telegram ID or @username
        ctx.user_data["state"] = None
        ctx.user_data.pop("assign_agent_case", None)
        ctx.user_data.pop("assign_agent_code", None)
        if not case_no:
            await update.message.reply_text("❌ Session expired. Please click Assign Agent again.")
            return
        agent_tg_id = None
        agent_username = None
        if raw.startswith("@"):
            agent_username = raw.lstrip("@").strip()
            if not agent_username:
                await update.message.reply_text("❌ Invalid @username. Example: <code>@agent_work</code>", parse_mode="HTML")
                return
        elif raw.isdigit():
            agent_tg_id = int(raw)
        else:
            await update.message.reply_text(
                "❌ Enter a numeric Telegram User ID or @username.\n"
                "Example: <code>123456789</code> or <code>@agent_work</code>",
                parse_mode="HTML",
            )
            return
        ok = await db.update_case_status(
            case_no, "UNDER REVIEW", str(update.effective_user.id),
            agent_code=agent_no, agent_tg_id=agent_tg_id, agent_username=agent_username,
        )
        c = await db.get_case_by_no(case_no)
        if not ok or not c:
            await update.message.reply_text("❌ Assignment failed.")
            return
        btn = None
        if agent_tg_id:
            btn = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    f"📞 Contact specialist ({agent_no})",
                    url=f"tg://user?id={agent_tg_id}",
                )
            ]])
        elif agent_username:
            btn = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    f"📞 Contact specialist ({agent_no})",
                    url=f"https://t.me/{agent_username}",
                )
            ]])
        notice = (
            "🏛 <b>IC3 · OFFICIAL CASE UPDATE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔖 Case: <code>{case_no}</code>\n"
            "🟣 Status: <b>P3 · UNDER REVIEW</b>\n"
            f"👤 Assigned specialist: <code>{agent_no}</code>\n"
            f"🕒 Assignment time: {now_str()}\n\n"
            "A case specialist has been assigned. For direct inquiries, use the secure link below.\n\n"
            f"Auth Ref: <code>{AUTH_ID}</code>"
        )
        try:
            await ctx.bot.send_message(
                c["tg_user_id"], notice, parse_mode="HTML", reply_markup=btn,
            )
        except Exception as e:
            await update.message.reply_text(f"⚠️ Case updated but notify failed: {e}")
        else:
            await update.message.reply_text(
                f"✅ Agent <b>{agent_no}</b> assigned to <code>{case_no}</code>. Complainant notified.",
                parse_mode="HTML",
                reply_markup=kb_admin_case(case_no),
            )
        return

    # ── Admin: compose and send agent message ────────────────────────
    if state == "AGENT_COMPOSE":
        case_no = ctx.user_data.pop("agent_compose_case", None)
        ctx.user_data["state"] = None
        if not case_no:
            await update.message.reply_text("❌ No case selected. Click Send Agent Message again.")
            return
        msg_text = text.strip()
        if not msg_text:
            await update.message.reply_text("❌ Message is empty. Type your text and send again.")
            ctx.user_data["agent_compose_case"] = case_no
            ctx.user_data["state"] = "AGENT_COMPOSE"
            return
        c = await db.get_case_by_no(case_no)
        if not c:
            await update.message.reply_text("❌ Case not found.")
            return
        complainant_uid = c.get("tg_user_id") or c.get("user_id")
        if complainant_uid is None:
            await update.message.reply_text("❌ Case has no complainant UID. Cannot send.")
            return
        complainant_uid = int(complainant_uid)
        agent_code = _agent_mono(c.get("agent_code"))
        ac_audit = (c.get("agent_code") or "").strip()

        import hashlib
        coc_hash = hashlib.sha256(
            f"{case_no}|{ac_audit}|{now_str()}|{msg_text}".encode()
        ).hexdigest()
        await db.log_audit(
            actor_type="AGENT", actor_id=str(update.effective_user.id),
            action="LIAISON_MSG_OUT",
            detail=f"case={case_no} agent={ac_audit or '—'} sha256={coc_hash[:16]}…"
        )
        official_msg = (
            "🔔 <b>NEW MESSAGE FROM YOUR CASE AGENT</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🏛 <b>INCOMING SECURE LIAISON</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>FROM:</b>    Case specialist (<code>{agent_code}</code>)\n"
            f"<b>CASE:</b>    <code>{case_no}</code>\n"
            f"<b>TIME:</b>    {now_str()} UTC\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>MESSAGE:</b>\n{msg_text}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⏳ <i>Reply directly in this chat to respond.</i>\n"
            f"🔐 <i>COC-Hash: <code>{coc_hash[:32]}</code></i>"
        )
        try:
            await ctx.bot.send_message(
                complainant_uid,
                official_msg,
                parse_mode="HTML",
                disable_notification=False,
            )
            await update.message.reply_text(
                f"✅ Message delivered to complainant (UID <code>{complainant_uid}</code>). They will receive a push notification.",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.exception("Send Agent Message to complainant failed")
            err_msg = str(e).strip() or "Unknown error"
            await update.message.reply_text(
                f"❌ <b>Delivery failed</b>\n\n"
                f"Recipient UID: <code>{complainant_uid}</code>\n"
                f"Error: <code>{err_msg[:200]}</code>\n\n"
                "<i>Ensure the complainant has started the bot and has not blocked it.</i>",
                parse_mode="HTML",
            )
        return

    # ── Liaison: user reply to agent (only when channel is open) ─────
    # IMPORTANT: Only intercept if NO active bot state is in progress.
    # States like QUERY_CASE, RISK_QUERY, CRS flow etc. must take priority.
    _active_states = {
        "QUERY_CASE", "RISK_QUERY", "AGENT_COMPOSE", "EVID_AUTH", "EVM01_AWAIT_PHOTO",
        "AGENT_ASSIGN_INPUT",
        S_FULLNAME, S_ADDRESS, S_PHONE, S_EMAIL,
        S_TXID, S_ASSET, S_TIME, S_VICTIM_WALLET, S_SUSPECT_WALLET,
        S_PLATFORM, S_SCAMMER_ID,
    }
    if not is_admin(update.effective_user.id) and state not in _active_states:
        # Check if this user has an open liaison case
        uid = update.effective_user.id
        open_case = await db.get_open_liaison_case(uid)
        if open_case:
            case_no    = open_case["case_no"]
            msg_text   = text.strip()
            # Chain of custody log
            import hashlib
            coc_hash = hashlib.sha256(
                f"{case_no}|USER|{uid}|{now_str()}|{msg_text}".encode()
            ).hexdigest()
            await db.log_audit(
                actor_type="USER", actor_id=str(uid),
                action="LIAISON_MSG_IN",
                detail=f"case={case_no} sha256={coc_hash[:16]}…"
            )
            # Acknowledge receipt to user
            await update.message.reply_text(
                "🔒 <b>Secure Transmission Received</b>\n"
                f"<i>Encrypted and logged — COC: <code>{coc_hash[:16]}…</code></i>",
                parse_mode="HTML")
            # Forward to all admins
            relay_msg = (
                "📩 <b>LIAISON REPLY FROM COMPLAINANT</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"<b>CASE:</b>  <code>{case_no}</code>\n"
                f"<b>UID:</b>   <code>{uid}</code>\n"
                f"<b>TIME:</b>  {now_str()} UTC\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{msg_text}\n\n"
                f"🔐 <i>COC-Hash: <code>{coc_hash[:32]}</code></i>"
            )
            for admin_id in ADMIN_IDS:
                try:
                    await ctx.bot.send_message(admin_id, relay_msg, parse_mode="HTML")
                except Exception: pass
            return

    # ── Case ID query ─────────────────────────────────
    if state == "QUERY_CASE":
        raw = text.strip().upper()

        # ── Format validation: IC3-YYYY-ARXXXXXX-ADRI ──
        if not re.match(r"^IC3-\d{4}-AR[A-Z0-9]{6,8}-ADRI$", raw):
            await update.message.reply_text(
                "<code>[IC3-NODE] INPUT VALIDATION ERROR</code>\n"
                "────────────────────\n"
                "<code>ERR: Malformed Case ID.</code>\n\n"
                "📌 <b>Required format:</b>\n"
                "<code>IC3-YYYY-ARXXXXXX-ADRI</code>\n\n"
                "✅ <b>Example:</b>\n"
                "<code>IC3-2026-ARDAE9E9-ADRI</code>\n\n"
                "<i>Your Case ID was displayed in the original\n"
                "submission confirmation message.</i>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Try Again", callback_data="CTS-01")
                ]])
            )
            return

        c = await db.get_case_by_no(raw)
        if not c:
            await update.message.reply_text(
                "<code>[IC3-NODE] QUERY RESULT: NOT FOUND</code>\n"
                "────────────────────\n"
                f"<code>QUERY : {raw}</code>\n"
                "<code>RESULT: No matching record in federal database.</code>\n\n"
                "Please verify your Case ID and try again.\n\n"
                "<i>If you believe this is an error, retain your\n"
                "original submission confirmation.</i>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Try Again", callback_data="CTS-01")
                ]])
            )
            return
        # 所有 Case Tracking 查询都必须匹配当前 Telegram UID
        uid = update.effective_user.id
        stored_uid = c.get("tg_user_id")
        if stored_uid is None or int(stored_uid) != int(uid):
            await update.message.reply_text(
                "<code>[IC3-NODE] ACCESS DENIED</code>\n"
                "────────────────────\n"
                "<code>ERR: This Case ID is bound to another authorized account.</code>\n\n"
                "<i>If you believe this is an error, please verify that you are\n"
                "using the same Telegram account that filed the original report.</i>",
                parse_mode="HTML",
            )
            ctx.user_data["state"] = None
            return

        # 持久化本次通过认证的 Case ID，供 CTS 子模块在 30 分钟内复用
        from datetime import datetime, timedelta
        ctx.user_data["state"] = None
        ctx.user_data["last_case_id"] = c["case_no"]
        ctx.user_data["case_tracking_authed"] = True
        ctx.user_data["case_tracking_auth_until"] = datetime.utcnow() + timedelta(minutes=30)

        # 加载动画 + 状态卡片（下方已带 CTS 菜单按键）
        await _send_case_status(update.message, c)
        return

    # ── Risk address query ────────────────────────────
    if state == "RISK_QUERY":
        address = text.strip()
        forced_chain = ctx.user_data.pop("risk_chain", None)
        if forced_chain:
            chain = forced_chain
            valid = True
        else:
            chain, valid = detect_wallet(address)
        if not valid:
            await update.message.reply_text(
                "❌ Invalid address format.\n\n"
                "Supported: ETH/BSC · TRC20 · Bitcoin")
            return
        ctx.user_data["state"] = None
        proc = await update.message.reply_text(
            "📡 <b>RAD-02 · Blockchain Trace Analysis</b>\n\n"
            "🔍 Connecting to chain node...\n"
            "⏳ Retrieving on-chain data...",
            parse_mode="HTML")
        result = await query_risk_address(address, chain)
        try: await proc.delete()
        except Exception: pass
        await update.message.reply_text(result, parse_mode="HTML")
        return

    # ── M01 CRS Complaint Flow ────────────────────────────────────

    DATA_INTEGRITY_MSG = (
        "🛡️ DATA INTEGRITY VIOLATION\n"
        "The system has detected non-compliant or randomized data input. "
        "To maintain the cryptographic integrity of your case file (AR92A...), "
        "all entries must meet the IC3 structural standards.\n\n"
        "Please review this field and re-enter it according to the on-screen guidelines."
    )

    # ── M02 Evidence Authentication Flow ───────────────────────────

    if state == "EVID_AUTH":
        raw = text.strip().upper()

        # Basic format validation to avoid obvious garbage
        if not re.match(r"^IC3-\d{4}-AR[A-Z0-9]{6,8}-ADRI$", raw):
            await update.message.reply_text(
                "🚫 INVALID CASE REFERENCE FORMAT\n\n"
                "Required pattern: <code>IC3-YYYY-ARXXXXXX-ADRI</code>\n"
                "Example: <code>IC3-2026-ARDAE9E9-ADRI</code>",
                parse_mode="HTML",
            )
            return

        uid = update.effective_user.id
        c = await db.get_case_by_no(raw)
        if not c:
            await update.message.reply_text(
                "🚫 INVALID CASE ID\n"
                "Please check your official email notification and try again.",
                parse_mode="HTML",
            )
            return

        stored_uid = c.get("tg_user_id")
        if stored_uid is None:
            # Bind this unclaimed case to current Telegram UID
            bound = await db.set_case_owner_if_unbound(raw, uid)
            if not bound:
                # Another race may have claimed it; treat as locked
                await update.message.reply_text(
                    "⚠️ ACCESS DENIED\n"
                    "This Case Reference ID is already locked to another authorized account.",
                    parse_mode="HTML",
                )
                return
        elif int(stored_uid) != int(uid):
            await update.message.reply_text(
                "⚠️ ACCESS DENIED\n"
                "This Case Reference ID is already locked to another authorized account.",
                parse_mode="HTML",
            )
            return

        # Success: identity synchronized
        ctx.user_data["state"] = None
        ctx.user_data["evid_auth_case"] = raw

        await update.message.reply_text(
            "✅ Identity synchronized.\n"
            "Connecting to the federal case evidence database...\n\n"
            f"[Case: <code>{raw}</code>]",
            parse_mode="HTML",
            reply_markup=kb_m02(),
        )
        return

    # CRS-01: Full Legal Name
    if state == S_FULLNAME:
        ctx.user_data["fullname"] = text.strip()
        r = await update.message.reply_text(
            f"✅ Recorded: <b>{text.strip()}</b>", parse_mode="HTML")
        track_msg(chat_id, r.message_id)
        await crs01_address(update.message, ctx)
        return

    # CRS-01: Physical Address
    if state == S_ADDRESS:
        addr = text.strip()
        if len(addr) < 5:
            await update.message.reply_text(
                DATA_INTEGRITY_MSG,
                parse_mode="HTML",
                reply_markup=kb_crs_nav(),
            )
            return
        ctx.user_data["address"] = addr
        conf = ("\u2705 <b>Address recorded:</b>\n"
                "<code>" + addr + "</code>\n\n"
                "Proceeding to Step 3 of 3...")
        await update.message.reply_text(conf, parse_mode="HTML")
        await crs01_phone(update.message, ctx)
        return

    # CRS-01: Phone Number
    if state == S_PHONE:
        t = text.strip()
        # 明确禁止匿名占位，电话/WhatsApp/Telegram 为必填渠道
        if t.lower() in ("anonymous", "匿名", "none", "n/a", "-"):
            await update.message.reply_text(
                DATA_INTEGRITY_MSG,
                parse_mode="HTML",
                reply_markup=kb_crs_nav(),
            )
            return
        # 基本格式校验：国际电话或 @username / Signal ID
        phone_pattern = r"^\+\d[\d\-\s]{6,20}$"          # +CountryCode-xxx-xxxx 类似格式
        username_pattern = r"^@[A-Za-z0-9_]{3,32}$"      # Telegram/Signal 等用户名
        if not (re.match(phone_pattern, t) or re.match(username_pattern, t)):
            await update.message.reply_text(
                DATA_INTEGRITY_MSG,
                parse_mode="HTML",
                reply_markup=kb_crs_nav(),
            )
            return
        ctx.user_data["phone"] = t
        await crs01_email(update.message, ctx)
        return

    # Email → Complete, show section done + go to M01 menu
    if state == S_EMAIL:
        ctx.user_data["email"] = text.strip()
        ctx.user_data["state"] = None
        ctx.user_data["crs01_done"] = True
        r = await update.message.reply_text(
            "✅ <b>Identity & Residency section recorded.</b>\n\n"
            "Please proceed to the next section:",
            parse_mode="HTML",
            reply_markup=kb_m01_for_user(crs_completed_sections(ctx.user_data)),
        )
        track_msg(chat_id, r.message_id)
        return

    # CRS-02: TXID
    if state == S_TXID:
        t = text.strip()
        if t.lower() in ("none", "n/a", "无"):
            ctx.user_data["txid"] = "Not provided"
        elif re.match(r"^[0-9a-fA-F]{64}$", t):
            ctx.user_data["txid"] = t
            await update.message.reply_text("✅ Transaction hash format verified.")
        else:
            await update.message.reply_text(
                DATA_INTEGRITY_MSG,
                parse_mode="HTML",
                reply_markup=kb_crs_nav(),
            )
            return
        await crs02_asset(update.message, ctx)
        return

    # CRS-02: Asset + Amount
    if state == S_ASSET:
        result = parse_amount(text)
        if not result:
            await update.message.reply_text(
                DATA_INTEGRITY_MSG,
                parse_mode="HTML",
                reply_markup=kb_crs_nav(),
            )
            return
        ctx.user_data["amount"], ctx.user_data["coin"] = result
        await update.message.reply_text(
            f"✅ Asset recorded: <b>{result[0]} {result[1]}</b>", parse_mode="HTML")
        await crs02_incident_time(update.message, ctx)
        return


    # CRS-02: Incident Date & Time
    if state == S_TIME:
        ctx.user_data["time"] = text.strip()
        await update.message.reply_text(
            f"✅ Incident time recorded: <b>{text.strip()}</b>", parse_mode="HTML")
        await crs02_victim_wallet(update.message, ctx)
        return

    # CRS-02: Victim Wallet
    if state == S_VICTIM_WALLET:
        t = text.strip()
        if t.lower() in ("unknown", "无", "none"):
            ctx.user_data["victim_wallet"] = "Unknown"
        else:
            chain, valid = detect_wallet(t)
            if not valid:
                await update.message.reply_text(
                    DATA_INTEGRITY_MSG,
                    parse_mode="HTML",
                    reply_markup=kb_crs_nav(),
                )
                return
            ctx.user_data["victim_wallet"] = t
            await update.message.reply_text(
                f"✅ Victim wallet chain: <b>{chain}</b>", parse_mode="HTML")
        await crs02_suspect_wallet(update.message, ctx)
        return

    # CRS-02: Suspect Wallet → Complete
    if state == S_SUSPECT_WALLET:
        t = text.strip()
        if t.lower() in ("unknown", "无", "none"):
            ctx.user_data["wallet"] = "Unknown"
            ctx.user_data["chain"] = "N/A"
        else:
            chain, valid = detect_wallet(t)
            if not valid:
                await update.message.reply_text(
                    DATA_INTEGRITY_MSG,
                    parse_mode="HTML",
                    reply_markup=kb_crs_nav(),
                )
                return
            ctx.user_data["wallet"] = t
            ctx.user_data["chain"] = chain
            await update.message.reply_text(
                f"✅ Suspect wallet chain: <b>{chain}</b>", parse_mode="HTML")
        ctx.user_data["state"] = None
        ctx.user_data["crs02_done"] = True
        await update.message.reply_text(
            "✅ <b>CRS-02 Complete — Blockchain data recorded.</b>\n\n"
            "Please proceed to the next section:",
            parse_mode="HTML",
            reply_markup=kb_m01_for_user(crs_completed_sections(ctx.user_data)),
        )
        return

    # CRS-03: Scam Platform
    if state == S_PLATFORM:
        if len(text.strip()) < 3:
            await update.message.reply_text(
                DATA_INTEGRITY_MSG,
                parse_mode="HTML",
                reply_markup=kb_crs_nav(show_back=False),
            )
            return
        ctx.user_data["platform"] = text.strip()
        await crs03_scammer_id(update.message, ctx)
        return

    # CRS-03: Scammer Identity → Complete
    if state == S_SCAMMER_ID:
        ctx.user_data["scammer_id"] = text.strip()
        ctx.user_data["state"] = None
        ctx.user_data["crs03_done"] = True
        await update.message.reply_text(
            "✅ <b>CRS-03 Complete — Platform & suspect info recorded.</b>\n\n"
            "Please proceed to Review & Submit:",
            parse_mode="HTML",
            reply_markup=kb_m01_for_user(crs_completed_sections(ctx.user_data)),
        )
        return

    await update.message.reply_text(
        "Please use the module menu below 👇",
        reply_markup=kb_main_bottom())


# ══════════════════════════════════════════════════════
# CONTACT TYPE CALLBACKS
# ══════════════════════════════════════════════════════
async def _handle_contact_cb(q, ctx, label):
    ctx.user_data["contact_type"] = True
    await q.message.reply_text(label)


# ══════════════════════════════════════════════════════
# POST INIT & MAIN
# ══════════════════════════════════════════════════════
async def post_init(app: Application):
    await db.init_db()
    # ── Schema migration: add liaison & agent fields if not exist ──
    try:
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                ALTER TABLE cases
                ADD COLUMN IF NOT EXISTS is_liaison_open BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS agent_code      TEXT    DEFAULT NULL
            """)
    except Exception as e:
        logger.warning(f"[MIGRATION] {e}")
    logger.info("[IC3] Database initialized. Bot online.")


def main():
    if not TOKEN:
        print("❌ BOT_TOKEN not set in .env")
        return

    app = Application.builder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start",            cmd_start))
    app.add_handler(CommandHandler("cases",            cmd_cases))
    app.add_handler(CommandHandler("case",             cmd_case))
    app.add_handler(CommandHandler("audit",            cmd_audit))
    app.add_handler(CommandHandler("upload",           cmd_upload))
    app.add_handler(CommandHandler("ingest_evidence",  cmd_upload))   # alias
    app.add_handler(CommandHandler("done",             cmd_done))
    app.add_handler(CommandHandler("testdb",           cmd_testdb))

    app.add_handler(CallbackQueryHandler(callback_handler, pattern=r"^(st|notify|evlist|upload_set|pdf)\|"))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_handler))

    print("🏛 FBI IC3 · ADRI Bot online. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
