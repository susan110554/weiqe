"""
管理后台中文文案 — 所有管理员可见的菜单、按钮、提示、表格列名
"""

# ── 主菜单 ─────────────────────────────────────────────
MAIN_MENU_TITLE = (
    "IC3 管理后台\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "请选择功能模块："
)

BTN_USERS = "👥 用户管理"
BTN_CASES = "📋 案件管理"
BTN_MSG = "📨 消息中心"
BTN_AGENTS = "👮 探员调度"
BTN_SECURITY = "🔐 安全与PIN"
BTN_PDF = "📄 文件与PDF"
BTN_NOTIFY = "🔔 通知管理"
BTN_DASHBOARD = "📊 系统仪表盘"

# ── 案件管理 ───────────────────────────────────────────
CASES_MENU_TITLE = (
    "📋 案件管理\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "请选择操作："
)

BTN_VIEW_CASES = "查看案件"
BTN_SEARCH_CASE = "搜索案件"
BTN_CHANGE_STATUS = "修改状态"
BTN_ASSIGN_AGENT = "派遣探员"
BTN_GEN_REPORT = "生成报告"
BTN_CLOSE_CASE = "关闭案件"
BTN_BACK = "⬅️ 返回"

# 查看案件筛选
BTN_ALL_CASES = "全部案件"
BTN_PENDING = "🟡 待审核"
BTN_IN_PROGRESS = "🟢 进行中"
BTN_CLOSED = "🔴 已关闭"

# 状态选项（P1–P12 + 自定义）
STATUS_P0 = "P1 · ⚪ SUBMITTED"
STATUS_P1 = "P2 · 🟡 PENDING REVIEW"
STATUS_P2 = "P3 · 🔵 CASE ACCEPTED"
STATUS_P3 = "P4 · 🟢 REFERRED TO LAW ENFORCEMENT"
STATUS_P4 = "P5 · ⚫ IDENTITY VERIFICATION"
STATUS_P5 = "P6 · 🟠 PRELIMINARY REVIEW"
STATUS_P6 = "P7 · 🔴 ASSET TRACING"
STATUS_P7 = "P8 · 🟣 LEGAL DOCUMENTATION"
STATUS_P8 = "P9 · 💰 FUND DISBURSEMENT"
STATUS_CLOSED = "✅ CASE CLOSED"
STATUS_CUSTOM = "🔧 自定义状态"

# 案件列表
CASES_LIST_HEADER = "📋 案件列表\n━━━━━━━━━━━━━━━━━━\n\n"
CASE_ITEM = "{icon} <code>{case_no}</code>\n  平台: {platform} | 金额: {amount} {coin}\n  状态: {status}\n"
NO_CASES = "暂无案件记录。"
PAGE_FMT = "\n━━━━━━━━━━━━━━━━━━\n第 {page} 页，共 {total_pages} 页"

# 案件详情（管理员可见）
CASE_DETAIL_HEADER = "📋 案件详情\n━━━━━━━━━━━━━━━━━━\n\n"
CASE_DETAIL_FIELDS = (
    "🔖 案件编号: {case_no}\n"
    "📌 状态: {status}\n"
    "🕒 提交时间: {created_at}\n"
    "🔄 更新时间: {updated_at}\n\n"
    "🏛 平台: {platform}\n"
    "💰 金额: {amount} {coin}\n"
    "📅 事发时间: {incident_time}\n"
    "🔗 钱包: {wallet_addr}\n"
    "⛓ 链类型: {chain_type}\n"
    "📞 联系: {contact}\n"
    "👤 报案人: {tg_user_id}\n"
)

# 派遣探员
ASSIGN_AGENT_PROMPT = (
    "👤 <b>派遣探员</b>\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "案件: <code>{case_no}</code>\n\n"
    "请输入探员显示名或内部编号（2–48 个字符）。\n\n"
    "示例: <code>勘查组-A7</code>、<code>Smith-318</code>"
)
ASSIGN_AGENT_STEP2 = (
    "✅ 探员标识: <code>{agent_code}</code>\n\n"
    "请输入探员的 Telegram User ID（数字）或 @用户名"
)
ASSIGN_SUCCESS = "✅ 探员 <b>{agent_code}</b> 已派遣至案件 <code>{case_no}</code>，已通知报案人。"

# 修改状态 - 自定义输入
STATUS_CUSTOM_PROMPT = (
    "📋 <b>自定义状态</b>\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "案件: <code>{case_no}</code>\n\n"
    "请输入 P7–P10 的自定义状态名称（英文）\n\n"
    "示例: P7 · CUSTOM REVIEW"
)

# ── 用户管理 ───────────────────────────────────────────
USERS_MENU_TITLE = (
    "👥 用户管理\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "请选择操作："
)
BTN_VIEW_USERS = "查看用户"
BTN_SEARCH_USER = "搜索用户"
BTN_SUSPEND_USER = "暂停用户"
BTN_RESUME_USER = "恢复用户"
BTN_ACTIVITY_LOG = "活动日志"

USERS_LIST_HEADER = "👥 用户列表\n━━━━━━━━━━━━━━━━━━\n\n"
USER_ITEM = "{icon} <code>{tg_user_id}</code> @{username}\n  状态: {status}\n"
NO_USERS = "暂无用户记录。"
BTN_ALL_USERS = "全部用户"
BTN_ACTIVE_USERS = "🟢 活跃"
BTN_SUSPENDED_USERS = "🔴 已暂停"

USER_SUSPEND_PROMPT = (
    "⏸ <b>暂停用户</b>\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "请输入要暂停的 Telegram User ID（数字）："
)
USER_SUSPEND_REASON = "请输入暂停原因（可选，直接发送文字）："
USER_SUSPEND_UNTIL = "请输入暂停截止时间（如 7 表示 7 天后，或 2026-04-01 表示具体日期）："
USER_RESUME_PROMPT = "请输入要恢复的 Telegram User ID："
USER_SEARCH_PROMPT = "请输入 User ID 或 Telegram ID 搜索："

# ── 探员调度 ───────────────────────────────────────────
AGENTS_MENU_TITLE = (
    "👮 探员调度\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "请选择操作："
)
BTN_VIEW_AGENTS = "查看探员"
BTN_AGENTS_ASSIGN = "派遣探员"
BTN_REASSIGN = "重新分配"
BTN_WORKLOAD = "工作负荷"
BTN_BY_OFFICE = "按办公室查看"

AGENTS_LIST_HEADER = "👮 探员列表\n━━━━━━━━━━━━━━━━━━\n\n"
AGENT_ITEM = "• <code>{agent_code}</code> — {office} {active}\n"
NO_AGENTS = "暂无探员记录。可从案件管理派遣探员后自动同步。"

# 通用
ACCESS_DENIED = "❌ 权限不足。"
OPERATION_FAILED = "❌ 操作失败。"
CONFIRM = "确认"
