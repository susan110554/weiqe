"""
FBI IC3 – ADRI Bot
Admin Module: Admin commands (/cases, /case, /audit, /testdb)
"""
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

import database as db
from .config import is_admin, now_str, logger, AUTH_ID
from .keyboards import kb_admin_case


async def cmd_cases(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Access Denied — Insufficient clearance level.")
        return
    cases = await db.get_recent_cases(10)
    if not cases:
        await update.message.reply_text("📂 No cases on record.")
        return
    sem = {
        "Pending Initial Review": "🟡", "Under Review": "🔵",
        "Case Accepted": "🟢", "Processing Complete": "✅",
        "Case Closed": "⚫", "待初步审核": "🟡",
    }
    lines = ["📊 <b>M07-ADM · Case Registry</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    for c in cases:
        e = sem.get(c["status"], "⚪")
        lines.append(
            f"\n{e} <code>{c['case_no']}</code>"
            f"\n   Platform: {c['platform']}"
            f"\n   Amount:   {c['amount']} {c['coin']}"
            f"\n   Status:   {c['status']}"
        )
    total = await db.get_case_count()
    lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nTotal: {total} cases registered")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_case(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Access Denied.")
        return
    if not ctx.args:
        await update.message.reply_text(
            "Usage: <code>/case IC3-XXXXXXXX-XXXXXXXX</code>", parse_mode="HTML")
        return
    case_no = ctx.args[0].upper()
    c = await db.get_case_by_no(case_no)
    if not c:
        await update.message.reply_text(
            f"❌ Case not found: <code>{case_no}</code>", parse_mode="HTML")
        return
    evs = await db.get_evidences(case_no)
    text = (
        "📋 <b>M07-ADM · Case Detail Report</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔖 Case ID:        <code>{c['case_no']}</code>\n"
        f"📌 Status:         {c['status']}\n"
        f"🕒 Filed:          {c['created_at'].strftime('%Y-%m-%d %H:%M')}\n"
        f"🔄 Last Updated:   {c['updated_at'].strftime('%Y-%m-%d %H:%M')}\n\n"
        f"🏛 Platform:       {c['platform']}\n"
        f"💰 Loss Amount:    {c['amount']} {c['coin']}\n"
        f"📅 Incident Date:  {c['incident_time']}\n"
        f"🔗 Wallet Address: <code>{c['wallet_addr'] or 'N/A'}</code>\n"
        f"⛓ Chain Type:     {c['chain_type'] or 'N/A'}\n"
        f"🔎 TX Evidence:    {c['tx_hash'] or 'N/A'}\n"
        f"📞 Contact:        {c['contact']}\n"
        f"👤 Complainant UID: {c['tg_user_id']}\n"
        f"📁 Evidence Files: {len(evs)} file(s)\n"
    )
    await update.message.reply_text(text, parse_mode="HTML",
                                    reply_markup=kb_admin_case(case_no))


async def cmd_audit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Access Denied.")
        return
    logs = await db.get_audit_logs(15)
    lines = ["📜 <b>Audit Log Viewer</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    for log in logs:
        t = log["logged_at"].strftime("%m-%d %H:%M")
        lines.append(
            f"<code>{t}</code> [{log['actor_type']}] <b>{log['action']}</b>\n"
            f"   › {log['detail']}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_testdb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin diagnostic: test DB connectivity and schema."""
    if not is_admin(update.effective_user.id):
        return
    try:
        await db.init_db()
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            cols = await conn.fetch("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'cases'
                ORDER BY ordinal_position
            """)
            count = await conn.fetchval("SELECT COUNT(*) FROM cases")
            test_no = f"TEST-{datetime.now().strftime('%H%M%S')}"
            try:
                row = await conn.fetchrow("""
                    INSERT INTO cases (
                        id,
                        case_number, case_no,
                        user_id, tg_user_id, tg_username,
                        platform, amount, coin, incident_time,
                        wallet_addr, chain_type, tx_hash, contact
                    ) VALUES (gen_random_uuid(),$1::text,$1::text,$2,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                    RETURNING id, case_no
                """,
                    test_no, 999999, "test_user",
                    "Test Platform", 5000.0, "USDT", "2026-01-15",
                    "Unknown", "Unknown", "None", "test@email.com"
                )
                await conn.execute("DELETE FROM cases WHERE case_no=$1", test_no)
                insert_result = "INSERT OK id=" + str(row["id"])
            except Exception as ie:
                insert_result = "INSERT FAILED: " + str(ie)

        col_lines = [r["column_name"] + " (" + r["data_type"] + ")" for r in cols]
        report = (
            "DB DIAGNOSTIC REPORT\n"
            "====================\n"
            f"Connection: OK\n"
            f"Rows in cases: {count}\n"
            f"Insert test: {insert_result}\n"
            "--------------------\n"
            "Columns:\n" + "\n".join("  " + c for c in col_lines)
        )
        await update.message.reply_text(report)
    except Exception as e:
        await update.message.reply_text(
            "DB DIAGNOSTIC FAILED\n"
            "====================\n"
            "Connection error: " + str(e)
        )
