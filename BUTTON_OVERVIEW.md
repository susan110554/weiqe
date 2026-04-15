# 按钮结构总览（前端 + 后端）

> 工程：`维权机器人` · 主逻辑 `bot.py` · 键盘 `bot_modules/keyboards.py` · CRS 步骤 `bot_modules/crs.py` · 管理后台 `bot_modules/admin_console.py` + `adm_*.py`  
> 说明：**M04 / RAD** 子菜单已清空，仅保留 `HOME`；**M08** 已从主菜单移除。

---

## 一、前端：键盘从哪里来

### 1. 底部固定键盘（Reply）

| 函数 | 行布局（`KeyboardButton` 文案） | 后端识别方式 |
|------|----------------------------------|--------------|
| `kb_main_bottom(user_id)` | ① Case Reporting · Evidence Upload ② Case Tracking · Risk Analysis ③ Knowledge Base · Legal Referral ④ User Center ⑤（管理员）管理后台 | `msg_handler` 里 `menu_map` **精确匹配按钮文字** → 映射到 `M01`…`M09` 等 |

### 2. 首页内联键盘（Inline）

| 函数 | callback_data | 备注 |
|------|----------------|------|
| `kb_home(user_id)` | `M01` `M02` `M03` `M04` `M05` `M06` `M09` · `HOME`（各按钮成对分行） | 管理员多一行 `adm|main` |
| `/start` 等 | 常与 `kb_home` / 合成图 caption 同屏 | 见 `cmd_start` |

### 3. 模块菜单（`keyboards.py` 静态表）

| 函数 | 主要 callback_data（节选） |
|------|----------------------------|
| `kb_m01()` | `CRS-01` `CRS-02` `CRS-03` `CRS-04-OTHER` `CRS-04` `HOME` |
| `kb_m01_for_user(...)` | 同上，但 CRS 区块动态隐藏；CRS-02 入口为 `CRS-02-TYPE` |
| `kb_m02()` | `EVM-01`…`EVM-05` `HOME` |
| `kb_m02_back_only()` | `EVM-MENU` |
| `kb_evm_seal()` | `evm_seal` `EVM-MENU` |
| `kb_m03(user_data, case)` | `CTS-01` `CTS-02` `CTS-03` 或 `CTS-03_LOCKED` `CTS-04` `HOME` |
| `kb_cts03_fees()` | `CTS03_FEE_*` `M03` |
| `kb_m04()` | **仅** `HOME`（RAD 重做中） |
| `kb_m05()` | `KBS-01`…`KBS-05` `HOME` |
| `kb_m06()` | `LRS-01`…`LRS-04` `HOME` |
| `kb_lrs04_expedited()` | `LRS04_EXPEDITE_PAY` `LRS04_EXPEDITE_CONSULT` `M06` |
| `kb_m09()` | `ORG-01`…`ORG-05` `HOME` |
| `kb_rad02()` | **仅** `HOME`（链选择已清空） |
| `kb_rad02_result_followup(...)` | **仅** `HOME`（参数已忽略） |

### 4. CRS / 表单类（`keyboards.py`）

| 函数 | 用途概要 |
|------|-----------|
| `kb_crs01_menu` | `CRS01_*` `CRS01_DONE` `CRS01_BACK`（字段行由 `_field_btn` 生成） |
| `kb_phone` | `PHONE_EMAIL` `PHONE_DIRECT` `PHONE_DONE` `PHONE_BACK` |
| `kb_crs03_menu` / `kb_crs03_crime` | `CRS03_*` `CRS03_DONE` `go_back` |
| `kb_fraud_type` | `FRAUD-TYPE|…` `go_back` `go_cancel` |
| `kb_crs04_other` | `CRS04_*` `CRS04_OTHER_SAVE` `CRS04_OTHER_BACK` |
| `kb_crs01_nav` / `kb_crs_nav` / `kb_nav` | `go_back` `go_cancel` |
| `kb_crs_attest` / `kb_signature_request` / `kb_confirm` | `confirm_submit` `CRS-01` `go_cancel` `sign_and_submit` `cancel_submit` `restart` |
| `kb_after_submit(case_id)` | `pdf|{id}` `quickcheck|{id}` `close_session` |
| `kb_certificate_actions` / `kb_cert_email_*` | `pdf|` `cert|verify` `cert|email|…` `cert|done` 等 |
| `kb_pin_pad` | `pin|0-9` `pin|del` `pin|confirm` 可选 `pin|forgot` |
| `kb_recovery_*` | `recovery|email` `recovery|caseid` `recovery|back` 等 |
| `kb_contact` | `ct_tg` `ct_email` `ct_wa` `ct_skip` |
| `kb_admin_case(case_no)` | `st|{case_no}|STATUS` `assign|` `liaison_*` `agentmsg|` `notify|` `evlist|` `adm|case|refresh_pdf|` |
| `kb_upload_case` | `upload_set|{case_no}` `HOME` |

### 5. CRS-02 金融 / 多笔交易（大量动态按钮）

- **不在** `keyboards.py` 一次性列完；由 `bot.py` 的 `callback_handler` 与 **`bot_modules/crs.py`** 内 `InlineKeyboardMarkup` 动态拼装。  
- 前缀示例：`CRS02_*` `CRS02_FIN_*` `CRS02_FIN_TX1_TYPE|*` `CRYPTO_*` `CASH_*` `CHECK_*` `MO_*` `WIRE_*` `OTHER_*` `TX1_*` 及证人/CRS04 相关 `CRS04_WITNESS_*` 等（以代码检索为准）。

---

## 二、后端：谁处理点击与文字

### 1. 回调总入口

- **`bot.py` → `async def callback_handler(update, ctx)`**  
  几乎所有 **非管理** `callback_data` 在此分支处理。
- **`CallbackQueryHandler` 注册**（`main()`）  
  - 先匹配：`^(adm|st|notify|evlist|upload_set|pdf)\|`  
  - 再注册**通用** `callback_handler`（兜底其余 callback）。

### 2. 前缀 / 模式路由（`callback_handler` 内，节选）

| 模式 | 处理逻辑 |
|------|-----------|
| `noop` | 空操作 |
| `adm|` | `admin_console.handle_callback` → 各 `adm_*.py` |
| `confirm_submit` / `sign_and_submit` / `cancel_submit` | 提交与签名流 |
| `recovery|` | `handle_recovery_callback` |
| `pin|` | 按 `ctx.user_data["state"]` 分发：PDF / 邮件 / CTS03 支付 / LRS04 支付 / Recovery PIN / Case PIN |
| `cert|` | 证书与邮件 PDF |
| `pdf|` | 下载 PDF → PIN |
| `view_evidence_detail` / `rad02_no_case_pdf` / `rad02_no_explorer` | RAD-02 遗留回调（新 UI 已难触达） |
| `HOME` / `go_back` / `go_cancel` / `restart` | 导航与取消 |
| `M01`…`M09`、各 `CRS-*`、`CTS-*`、`KBS-*`、`LRS-*`、`ORG-*`、`EVM-*` 等 | 模块内联菜单与 CRS 大段逻辑 |
| `st|` / `notify|` / `evlist|` / `upload_set|` / `liaison_*` / `assign|` / `agentmsg|` 等 | 管理员办案与用户侧联络（与 `kb_admin_case` 等对应） |

### 3. 管理后台 `adm|*`

| 模块文件 | 职责（按钮前缀示例） |
|----------|----------------------|
| `adm_main_menu.py` | `adm|main` 主菜单 |
| `adm_users.py` | `adm|users|…` |
| `adm_cases.py` | `adm|cases|…` |
| `adm_msg.py` | `adm|msg|…` |
| `adm_agents.py` | `adm|agents|…` |
| `adm_pdf.py` | `adm|pdf|…` |
| `adm_security.py` / `adm_notifications.py` / `adm_dashboard.py` | 占位或扩展 |

### 4. 文本消息（底部键盘 → 模块）

- **`msg_handler`**：`menu_map` 将 **Reply 按钮文字** 映射到 `M01`…`M09`，再 `reply_markup=kb_m01_for_user` / `kb_m02` / `await _kb_m03_for_user` / `kb_m04` 等。  
- **状态机**：`QUERY_CASE`、`RISK_QUERY`、`EVID_AUTH`、`PDF_PIN_WAIT`、`CTS03_PAY_PIN_WAIT`、`LRS04_PAY_PIN_WAIT`、CRS 各 `S_*` / `CRS02*` 字符串 state 等，在 **`msg_handler`** 前半段大量 `if state == ...` 分支处理（**不等同于** Inline callback）。

### 5. 命令（非按钮，但属入口）

| 命令 | 作用 |
|------|------|
| `/start` | 清会话、发抬头、主菜单 |
| `/console` | 管理员控制台（非管理员拒绝） |
| `/upload` / `/ingest_evidence` / `/done` | 证据上传流程（见 `evidence.py` 等） |

---

## 三、维护时怎么查

1. **改菜单文案或增删一行按钮**：先改 `keyboards.py`，再在 `bot.py` 的 `callback_handler` / `msg_handler` 里搜 **相同 `callback_data` 或按钮文字**。  
2. **CRS-02 / CRS-04 证人**：优先搜 `crs.py` + `bot.py` 里 `CRS02` / `CRS04` / `WITNESS`。  
3. **收费 PIN**：`CTS03_*`、`LRS04_*`、`pin|` 分支。  
4. **与本文不一致时**：以仓库当前代码为准；可把本文件当作「地图」，定期同步。

---

*生成方式：根据当前仓库静态扫描整理，动态 CRS 按钮仅作类别说明。*
