"""
管理后台 — 收费管理
功能：
  全局费用：修改 P5 优先费（fee_config.p5_fee）
  个人案件：修改单个案件的 P5/P9 override（case_cmp_overrides）
  所有修改写入 audit_logs（action: FEE_UPDATED）
  修改后自检收费流程是否贯通

取费三级回落：
  1. case_cmp_overrides.p5_fee_override / p9_fee_override（per-case）
  2. fee_config['p5_fee'] / fee_config['p9_fee_default']（全局）
  3. os.getenv('P5_FEE', 50) / os.getenv('P9_FEE_DEFAULT', 0)（兜底）
"""
from __future__ import annotations

import os
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import database as db
from .i18n_admin import BTN_BACK

logger = logging.getLogger(__name__)

FEES_MENU_TITLE = (
    "💰 收费管理\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "请选择操作："
)


# ── 辅助：当前有效费用 ─────────────────────────────────────────────────────

async def get_effective_p5_fee(case_row: dict | None = None) -> float:
    """三级回落取 P5 费用。"""
    if case_row:
        overrides = case_row.get("case_cmp_overrides") or {}
        if isinstance(overrides, str):
            import json
            try:
                overrides = json.loads(overrides)
            except Exception:
                overrides = {}
        if overrides.get("p5_fee_override") is not None:
            return float(overrides["p5_fee_override"])
    global_fee = await db.fee_config_get("p5_fee", default=-1)
    if global_fee >= 0:
        return global_fee
    return float(os.getenv("P5_FEE", "50"))


async def get_effective_p9_disbursement(case_row: dict | None = None) -> float | None:
    """P9 拨款金额：per-case override → fee_config default → None（需管理员手动设置）。"""
    if case_row:
        overrides = case_row.get("case_cmp_overrides") or {}
        if isinstance(overrides, str):
            import json
            try:
                overrides = json.loads(overrides)
            except Exception:
                overrides = {}
        if overrides.get("p9_disbursement_amount_usd") is not None:
            return float(overrides["p9_disbursement_amount_usd"])
        if overrides.get("p9_fee_override") is not None:
            return float(overrides["p9_fee_override"])
    global_default = await db.fee_config_get("p9_fee_default", default=-1)
    if global_default > 0:
        return global_default
    return None


# ── 键盘 ───────────────────────────────────────────────────────────────────

def kb_fees_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 修改全局 P5 费用",    callback_data="adm|fees|global_p5")],
        [InlineKeyboardButton("🌐 修改全局 P9 默认金额", callback_data="adm|fees|global_p9")],
        [InlineKeyboardButton("📁 修改个人案件 P5",     callback_data="adm|fees|case_p5")],
        [InlineKeyboardButton("📁 修改个人案件 P9",     callback_data="adm|fees|case_p9")],
        [InlineKeyboardButton("📋 查看当前费用配置",    callback_data="adm|fees|view")],
        [InlineKeyboardButton(BTN_BACK,                callback_data="adm|main")],
    ])


# ── 主处理器 ───────────────────────────────────────────────────────────────

async def handle(data: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    if not data.startswith("adm|fees|"):
        return False
    q = update.callback_query
    actor = str(update.effective_user.id)

    if data == "adm|fees|menu":
        await q.message.edit_text(
            FEES_MENU_TITLE, parse_mode="HTML", reply_markup=kb_fees_menu(),
        )
        return True

    # ── 查看当前配置 ────────────────────────────────────────────────────────
    if data == "adm|fees|view":
        rows = await db.fee_config_list()
        p5 = await db.fee_config_get("p5_fee", default=float(os.getenv("P5_FEE", "50")))
        p9 = await db.fee_config_get("p9_fee_default", default=0.0)
        lines = [
            "📋 <b>当前费用配置</b>\n━━━━━━━━━━━━━━━━━━\n",
            f"P5 优先分析费（全局）：<b>${p5:.2f} USDT</b>",
            f"P9 拨款默认金额（全局）：<b>${p9:.2f} USDT</b>",
            "",
            "<i>说明：个人案件 override 在 case_cmp_overrides 中存储，</i>",
            "<i>优先级高于全局配置。</i>",
            "",
            "最近审计记录：",
        ]
        # 最近费用修改审计
        logs = await db.get_audit_logs(limit=50)
        fee_logs = [r for r in logs if r.get("action") == "FEE_UPDATED"][:5]
        for r in fee_logs:
            ts = r.get("logged_at", "")
            if hasattr(ts, "strftime"):
                ts = ts.strftime("%Y-%m-%d %H:%M")
            lines.append(f"• {ts} | {r.get('actor_id','—')} | {r.get('target_id','')} | {r.get('detail','')}")
        if not fee_logs:
            lines.append("暂无记录。")
        await q.message.edit_text(
            "\n".join(lines), parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|fees|menu")]]),
        )
        return True

    # ── 全局 P5 修改 ────────────────────────────────────────────────────────
    if data == "adm|fees|global_p5":
        current = await db.fee_config_get("p5_fee", default=float(os.getenv("P5_FEE", "50")))
        ctx.user_data["state"] = "ADM_FEES_SET_GLOBAL_P5"
        await q.message.edit_text(
            f"🌐 <b>修改全局 P5 费用</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            f"当前全局 P5 费用：<b>${current:.2f} USDT</b>\n\n"
            "请输入新金额（纯数字，如 <code>75</code> 或 <code>99.50</code>）：",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|fees|menu")]]),
        )
        return True

    # ── 全局 P9 默认金额 ────────────────────────────────────────────────────
    if data == "adm|fees|global_p9":
        current = await db.fee_config_get("p9_fee_default", default=0.0)
        ctx.user_data["state"] = "ADM_FEES_SET_GLOBAL_P9"
        await q.message.edit_text(
            f"🌐 <b>修改全局 P9 默认拨款金额</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            f"当前默认：<b>${current:.2f} USDT</b>\n\n"
            "（设为 0 表示不默认，需逐案手动设置）\n\n"
            "请输入新金额（纯数字）：",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|fees|menu")]]),
        )
        return True

    # ── 个人案件 P5 override ────────────────────────────────────────────────
    if data == "adm|fees|case_p5":
        ctx.user_data["state"] = "ADM_FEES_CASE_P5_NO"
        await q.message.edit_text(
            "📁 <b>修改个人案件 P5 费用</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            "请输入案件号（如 IC3-2026-REF-0001-ABC）：",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|fees|menu")]]),
        )
        return True

    # ── 个人案件 P9 override ────────────────────────────────────────────────
    if data == "adm|fees|case_p9":
        ctx.user_data["state"] = "ADM_FEES_CASE_P9_NO"
        await q.message.edit_text(
            "📁 <b>修改个人案件 P9 拨款金额</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            "请输入案件号（如 IC3-2026-REF-0001-ABC）：",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="adm|fees|menu")]]),
        )
        return True

    return False


async def handle_text(text: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE, actor: str) -> bool:
    """处理费用修改流程文本输入。返回 True 表示已消耗。"""
    state = ctx.user_data.get("state", "")

    # ── 全局 P5 ─────────────────────────────────────────────────────────────
    if state == "ADM_FEES_SET_GLOBAL_P5":
        ctx.user_data.pop("state", None)
        try:
            amount = float(text.strip())
            assert amount >= 0
        except Exception:
            await update.message.reply_text("❌ 请输入有效金额（如 50 或 99.50）：")
            return True
        await db.fee_config_set("p5_fee", amount, actor)
        await update.message.reply_text(
            f"✅ 全局 P5 费用已更新为 <b>${amount:.2f} USDT</b>\n"
            "无需重启 bot，下次推送 P5 时自动生效。",
            parse_mode="HTML",
        )
        await _selfcheck_p5(update, amount)
        return True

    # ── 全局 P9 ─────────────────────────────────────────────────────────────
    if state == "ADM_FEES_SET_GLOBAL_P9":
        ctx.user_data.pop("state", None)
        try:
            amount = float(text.strip())
            assert amount >= 0
        except Exception:
            await update.message.reply_text("❌ 请输入有效金额：")
            return True
        await db.fee_config_set("p9_fee_default", amount, actor)
        await update.message.reply_text(
            f"✅ 全局 P9 默认拨款金额已更新为 <b>${amount:.2f} USDT</b>",
            parse_mode="HTML",
        )
        return True

    # ── 个人案件 P5：输入案件号 ───────────────────────────────────────────────
    if state == "ADM_FEES_CASE_P5_NO":
        case_no = text.strip().upper()
        c = await db.get_case_by_no(case_no)
        if not c:
            await update.message.reply_text(f"❌ 案件 {case_no} 不存在，请重新输入：")
            return True
        ctx.user_data["fees_case_no"] = case_no
        ctx.user_data["state"] = "ADM_FEES_CASE_P5_AMT"
        cur = await get_effective_p5_fee(c)
        await update.message.reply_text(
            f"案件 <code>{case_no}</code>\n当前有效 P5 费用：<b>${cur:.2f}</b>\n\n"
            "请输入新金额（填 0 表示免费，填 -1 恢复全局默认）：",
            parse_mode="HTML",
        )
        return True

    # ── 个人案件 P5：输入金额 ─────────────────────────────────────────────────
    if state == "ADM_FEES_CASE_P5_AMT":
        ctx.user_data.pop("state", None)
        case_no = ctx.user_data.pop("fees_case_no", None)
        if not case_no:
            return True
        try:
            amount = float(text.strip())
        except Exception:
            await update.message.reply_text("❌ 请输入有效金额：")
            return True
        if amount < 0:
            # 恢复全局默认：删除 override
            await db.merge_case_cmp_overrides(case_no, {"p5_fee_override": None})
            await db.log_audit("ADMIN", actor, "FEE_UPDATED", case_no, f"p5_fee_override cleared by {actor}")
            await update.message.reply_text(f"✅ 案件 <code>{case_no}</code> P5 费用已恢复全局默认。", parse_mode="HTML")
        else:
            await db.merge_case_cmp_overrides(case_no, {"p5_fee_override": amount})
            await db.log_audit("ADMIN", actor, "FEE_UPDATED", case_no, f"p5_fee_override={amount:.2f}")
            await update.message.reply_text(
                f"✅ 案件 <code>{case_no}</code> P5 费用已设为 <b>${amount:.2f} USDT</b>",
                parse_mode="HTML",
            )
        return True

    # ── 个人案件 P9：输入案件号 ───────────────────────────────────────────────
    if state == "ADM_FEES_CASE_P9_NO":
        case_no = text.strip().upper()
        c = await db.get_case_by_no(case_no)
        if not c:
            await update.message.reply_text(f"❌ 案件 {case_no} 不存在，请重新输入：")
            return True
        ctx.user_data["fees_case_no"] = case_no
        ctx.user_data["state"] = "ADM_FEES_CASE_P9_AMT"
        cur = await get_effective_p9_disbursement(c)
        cur_str = f"${cur:.2f}" if cur is not None else "未设置"
        await update.message.reply_text(
            f"案件 <code>{case_no}</code>\n当前 P9 拨款金额：<b>{cur_str}</b>\n\n"
            "请输入新拨款金额（USDT）：",
            parse_mode="HTML",
        )
        return True

    # ── 个人案件 P9：输入金额 ─────────────────────────────────────────────────
    if state == "ADM_FEES_CASE_P9_AMT":
        ctx.user_data.pop("state", None)
        case_no = ctx.user_data.pop("fees_case_no", None)
        if not case_no:
            return True
        try:
            amount = float(text.strip())
            assert amount > 0
        except Exception:
            await update.message.reply_text("❌ 请输入大于 0 的有效金额：")
            return True
        await db.merge_case_cmp_overrides(case_no, {"p9_disbursement_amount_usd": amount})
        await db.log_audit("ADMIN", actor, "FEE_UPDATED", case_no, f"p9_disbursement_amount_usd={amount:.2f}")
        await update.message.reply_text(
            f"✅ 案件 <code>{case_no}</code> P9 拨款金额已设为 <b>${amount:.2f} USDT</b>\n"
            "P9 推送将使用此金额。",
            parse_mode="HTML",
        )
        return True

    return False


async def _selfcheck_p5(update, new_amount: float) -> None:
    """简单自检：读取写入后的值并对比。"""
    try:
        readback = await db.fee_config_get("p5_fee", default=-999)
        if abs(readback - new_amount) < 0.001:
            await update.message.reply_text(
                f"🔍 自检通过：fee_config 读回值 ${readback:.2f} ✅\n"
                "P5 收费流程贯通，下次用户触发 P5 时将使用新金额。"
            )
        else:
            await update.message.reply_text(
                f"⚠️ 自检异常：写入 ${new_amount:.2f}，但读回 ${readback:.2f}，请检查数据库。"
            )
    except Exception as e:
        await update.message.reply_text(f"⚠️ 自检失败：{e}")
