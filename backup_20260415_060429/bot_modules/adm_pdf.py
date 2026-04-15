"""
管理后台 — 文件与 PDF
功能：生成PDF、编辑模板、发送给用户、文件存档、签署文件、查看证据文件
PDF 生成逻辑从 pdf_gen 导入使用。
"""
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import database as db
from .i18n_admin import BTN_BACK
from .pdf_gen import generate_case_pdf


PDF_MENU_TITLE = (
    "📄 文件与PDF\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "请选择操作："
)
BTN_GEN_PDF = "📑 生成PDF"
BTN_EDIT_TEMPLATE = "✏️ 编辑模板"
BTN_SEND_TO_USER = "📤 发送给用户"
BTN_FILE_ARCHIVE = "📁 文件存档"
BTN_SIGN_FILE = "✍️ 签署文件"
BTN_VIEW_EVIDENCE = "📷 查看证据文件"


def kb_pdf_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_GEN_PDF, callback_data="adm|pdf|generate")],
        [InlineKeyboardButton(BTN_EDIT_TEMPLATE, callback_data="adm|pdf|edit_template")],
        [InlineKeyboardButton(BTN_SEND_TO_USER, callback_data="adm|pdf|send_user")],
        [InlineKeyboardButton(BTN_VIEW_EVIDENCE, callback_data="adm|pdf|view_evi")],
        [InlineKeyboardButton(BTN_FILE_ARCHIVE, callback_data="adm|pdf|archive")],
        [InlineKeyboardButton(BTN_SIGN_FILE, callback_data="adm|pdf|sign")],
        [InlineKeyboardButton(BTN_BACK, callback_data="adm|main")],
    ])


async def handle(data: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """处理 adm|pdf|* 回调"""
    if not data.startswith("adm|pdf|"):
        return False
    q = update.callback_query

    if data == "adm|pdf|menu":
        await q.message.edit_text(
            PDF_MENU_TITLE,
            parse_mode="HTML",
            reply_markup=kb_pdf_menu(),
        )
        return True

    if data == "adm|pdf|generate":
        ctx.user_data["state"] = "ADM_PDF_GENERATE_CASE"
        await q.message.edit_text(
            "📑 <b>生成PDF</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            "请输入案件编号（如 IC3-2026-REF-1234-XXX）：",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|pdf|menu")]]),
        )
        return True

    if data == "adm|pdf|edit_template":
        await q.message.edit_text(
            "✏️ <b>编辑模板</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            "PDF 报告模板编辑。\n\n"
            "该功能即将开放。",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|pdf|menu")]]),
        )
        return True

    if data == "adm|pdf|send_user":
        ctx.user_data["state"] = "ADM_PDF_SEND_USER"
        await q.message.edit_text(
            "📤 <b>发送给用户</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            "请输入案件编号，系统将生成 PDF 并发送给报案人：",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|pdf|menu")]]),
        )
        return True

    if data == "adm|pdf|archive":
        await q.message.edit_text(
            "📁 <b>文件存档</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            "已生成的 PDF 文件存档列表。\n\n"
            "暂无存档记录。",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|pdf|menu")]]),
        )
        return True

    if data == "adm|pdf|sign":
        await q.message.edit_text(
            "✍️ <b>签署文件</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            "数字签名与电子签署功能。\n\n"
            "该功能即将开放。",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|pdf|menu")]]),
        )
        return True

    if data == "adm|pdf|view_evi":
        rows = await db.list_case_nos_with_evidence_counts(limit=20)
        if not rows:
            await q.message.edit_text(
                "📷 <b>查看证据文件</b>\n━━━━━━━━━━━━━━━━━━\n\n"
                "当前没有已上传证据的案件记录。",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "✏️ 手动输入案件编号",
                                callback_data="adm|pdf|evmanual",
                            )
                        ],
                        [InlineKeyboardButton(BTN_BACK, callback_data="adm|pdf|menu")],
                    ]
                ),
            )
            return True
        lines = [
            "📷 <b>查看证据文件</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            "点击下方案件号读取图片/文件（与「案件详情」中证据列表同源）：\n",
        ]
        kb_rows: list = []
        for r in rows:
            cn = (r.get("case_no") or "").strip()
            n = int(r.get("n") or 0)
            if not cn:
                continue
            kb_rows.append(
                [
                    InlineKeyboardButton(
                        f"{cn} ({n} 文件)",
                        callback_data=f"adm|pdf|evcase|{cn}",
                    )
                ]
            )
        kb_rows.append(
            [
                InlineKeyboardButton(
                    "✏️ 手动输入案件编号",
                    callback_data="adm|pdf|evmanual",
                )
            ]
        )
        kb_rows.append([InlineKeyboardButton(BTN_BACK, callback_data="adm|pdf|menu")])
        await q.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb_rows),
        )
        return True

    if data == "adm|pdf|evmanual":
        ctx.user_data["state"] = "ADM_PDF_VIEW_EVIDENCE_CASE"
        await q.message.edit_text(
            "📷 <b>查看证据文件</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            "请输入案件编号（如 IC3-2026-REF-1234-XXX）：",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(BTN_BACK, callback_data="adm|pdf|view_evi")]]
            ),
        )
        return True

    prefix = "adm|pdf|evcase|"
    if data.startswith(prefix):
        case_no = data[len(prefix) :].strip().upper()
        if not case_no:
            await q.message.reply_text("❌ 案件号无效。")
            return True
        evs = await db.get_evidences(case_no)
        if not evs:
            await q.message.reply_text(
                f"📷 案件 <code>{case_no}</code> 暂无证据文件。",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(BTN_BACK, callback_data="adm|pdf|view_evi")]]
                ),
            )
            return True
        await q.message.reply_text(
            f"📷 <b>证据文件</b> — <code>{case_no}</code>\n"
            f"共 <b>{len(evs)}</b> 个文件，正在下发…",
            parse_mode="HTML",
        )
        await send_case_evidence_files_to_chat(ctx.bot, q.message.chat_id, case_no)
        await q.message.reply_text(
            f"✅ 案件 <code>{case_no}</code> 证据已发送完毕。",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(BTN_BACK, callback_data="adm|pdf|view_evi")]]
            ),
        )
        return True

    return False


async def send_case_evidence_files_to_chat(bot: Bot, chat_id: int, case_no: str) -> int:
    """
    将某案件 evidences 表中的 file_id 发到指定聊天（与 /case → View Evidence Files 同源）。
    返回成功尝试发送的文件数。
    """
    evs = await db.get_evidences(case_no)
    if not evs:
        return 0
    for i, ev in enumerate(evs, 1):
        file_id = ev.get("file_id")
        if not file_id:
            await bot.send_message(
                chat_id,
                f"#{i} [{ev.get('file_type','?')}] {ev.get('file_name','')} — no file_id",
            )
            continue
        t = ev.get("uploaded_at")
        ts = t.strftime("%m-%d %H:%M") if t else ""
        caption = f"#{i} [{ev.get('file_type','')}] {ev.get('file_name','')} — {ts}"
        fname = (ev.get("file_name") or "").lower()
        try:
            if fname.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")) or (
                (ev.get("file_type") or "").startswith("EVM-01")
                or (ev.get("file_type") or "") == "IMAGE"
            ):
                await bot.send_photo(chat_id, photo=file_id, caption=caption)
            else:
                await bot.send_document(chat_id, document=file_id, caption=caption)
        except Exception:
            try:
                await bot.send_document(chat_id, document=file_id, caption=caption)
            except Exception as e:
                await bot.send_message(
                    chat_id,
                    f"#{i} Failed: {ev.get('file_name','')} — {e}",
                )
    return len(evs)


async def do_generate_pdf(case_no: str, attest_ts: str, auth_id: str) -> bytes | None:
    """根据案件编号生成 PDF，供 bot 或本模块调用。"""
    c = await db.get_case_by_no(case_no)
    if not c:
        return None
    evidences = await db.get_evidences(case_no)
    evid_list = [
        {"filename": e.get("file_name"), "file_name": e.get("file_name"), "sha256": e.get("sha256", "")}
        for e in evidences
    ] if evidences else []
    pdf_data = db.pdf_data_from_case_row(c, evidence_files=evid_list)
    pdf_data.setdefault("agent_code", c.get("agent_code", "N/A"))
    return await generate_case_pdf(pdf_data, attest_ts, auth_id)
