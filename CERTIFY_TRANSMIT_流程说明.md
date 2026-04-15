# CERTIFY-TRANSMIT REPORT 交互逻辑说明

本文档描述点击「I CERTIFY — TRANSMIT REPORT」后的完整交互流程及后端实现。

---

## 后端流程概览

| 步骤 | 触发 | 后端动作 |
|-----|------|----------|
| **STEP 1** | 用户点击 Sign & Submit | 收集：Telegram User ID、Case ID、所有填写字段、当前 UTC 时间戳、用户 IP（服务器端） |
| **STEP 2** | 用户输入 PIN | 校验：PIN 与数据库匹配；失败 3 次 → 锁定会话 |
| **STEP 3** | PIN 验证通过 | 生成签名：HMAC-SHA256(CaseID + UserID + Timestamp + AllFields + SecretKey) → 存入 case_signatures |
| **STEP 4** | 签名完成 | Bot 推送格式化证书消息 |

---

## 1. 用户点击 [ I CERTIFY — TRANSMIT REPORT ]（STEP 1 — SIGNATURE REQUEST）

**Bot 推送：** STEP 1 — SIGNATURE REQUEST

```
STEP 1 — SIGNATURE REQUEST
━━━━━━━━━━━━━━━━━━

You are about to sign and
submit your case to IC3.
All information will be locked
and cannot be edited after signing.

  Case ID   : IC3-2026-XXXXXX
  Submitted : [timestamp]
  Status    : Pending Signature

━━━━━━━━━━━━━━━━━━
[ ✅ Sign & Submit ]  [ ❌ Cancel ]
```

- **Cancel** → 返回案件复核界面（`crs04_review`）。
- **Sign & Submit** → 进入 STEP 2（PIN 验证）。

**实现位置：** `bot.py` → `show_signature_request()`，`crs.py` → `build_signature_request_text()`

**后端：** 预生成 Case ID、Submitted 时间戳。

---

## 2. 用户点击 [ ✅ Sign & Submit ]（STEP 2 — PIN VERIFICATION）

**Bot 推送：** STEP 2 — PIN VERIFICATION

```
STEP 2 — PIN VERIFICATION
━━━━━━━━━━━━━━━━━━

Enter your 6-digit security PIN
to confirm your identity.

  ● ● ● _ _ _

[ 1 ] [ 2 ] [ 3 ]
[ 4 ] [ 5 ] [ 6 ]
[ 7 ] [ 8 ] [ 9 ]
      [ 0 ]
[ ⌫ Delete ] [ ✅ Confirm ]
[ 🔑 Forgot PIN ]  （已有 PIN 时显示）
```

**逻辑：**
- **首次提交**：先设置 PIN（SET_PIN）→ 确认 PIN（CONFIRM_PIN）→ 签名
- **再次提交**：直接输入已有 PIN（ENTER_PIN）→ 验证 → 签名
- **忘记 PIN**：点击 🔑 Forgot PIN → 身份验证后设置新 PIN

**错误 PIN：** 提示「❌ Incorrect. X attempts remaining.»（剩余 1 次时为「1 attempt remaining.»）

**3 次错误** → 会话锁定，Bot 发送：「🔒 Session locked for security. Please contact ic3.gov/support」

**30 分钟无操作** → 「⏱ Session expired. Please restart with /start」

**实现位置：** `bot.py` → `handle_sign_and_submit()`, `handle_pin_callback()`；`crs.py` → `build_pin_verification_text`, `build_pin_incorrect_text`, `build_pin_locked_text`

---

## 3. PIN 验证通过后（STEP 3 — 无加载动画）

**后端直接执行：**
- HMAC-SHA256(CaseID + UserID + Timestamp + AllFields + SecretKey)
- 存入 `case_signatures` 表：signature_hex/signature、signed_at、tg_user_id、case_no、ip_address、auth_ref

**实现位置：** `bot.py` → `do_actual_submit_and_sign()`

---

## 4. Bot 推送证书（STEP 3 — CERTIFICATE ISSUED）

证书文案与三按钮：[ 📋 Save Certificate ] [ 🔍 Verify Signature ] [ ✅ Done ]

**实现位置：** `crs.py` → `build_certificate_text()`，`keyboards.py` → `kb_certificate_actions()`

---

## 4.1 STEP 4 — 按钮行为

**[ 📋 Save Certificate ]**  
Bot 将证书以新消息重发并 **置顶**（pin_chat_message），然后发送「✅ Certificate saved to your case record.»

**[ 🔍 Verify Signature ]**  
Bot 提示：「Send your signature string to verify.»  
用户粘贴签名 → 有效则返回 VALID（Case ID、Signed、Status: Authentic & Unmodified）；无效则「❌ INVALID — Signature not found. Contact: ic3.gov/support」

**[ ✅ Done ]**  
Bot 发送成功文案（Case ID、You will be notified when a Special Agent is assigned），并返回主菜单。

---

## 5. 边界情况（Edge cases）

- **会话空闲 30 分钟** → 「⏱ Session expired. Please restart with /start」（在 STEP 2 任一 PIN 操作时检查 `pending_signature_at`）
- **案件已签名 / 重复提交** → 「🔒 Case is locked. Contact ic3.gov/support to request amendments.」（在点击 Sign & Submit 时检查 `get_signature_by_case_no`）
- **用户尝试在签名后编辑** → 同上 Case is locked 提示（当前流程中仅在 Sign & Submit 处校验）

---

## 6. 后端步骤摘要

| 步骤 | 触发 | 动作 |
|------|------|------|
| STEP 1 | 用户点击 I CERTIFY → Bot 展示 Signature Request | 预生成 Case ID、Submitted；Cancel 回复核页 |
| STEP 2 | 用户点击 Sign & Submit → 输入 PIN | 校验 `user_pins`；错误显示 X attempts remaining；3 次错误锁定；30 分钟过期 |
| STEP 3 | PIN 正确 | HMAC-SHA256 签名存入 `case_signatures`；Bot 推送证书 + 三按钮 |
| STEP 4 | Save / Verify / Done | Save 重发并置顶证书；Verify 校验签名返回 VALID/INVALID；Done 成功文案 + 主菜单 |

---

## 7. 相关文件

- `bot.py`：`show_signature_request`, `handle_sign_and_submit`, `handle_pin_callback`, `handle_cert_callback`, `do_actual_submit_and_sign`
- `bot_modules/crs.py`：`build_signature_request_text`, `build_pin_verification_text`, `build_set_pin_text`, `build_confirm_pin_text`, `build_certificate_text`
- `bot_modules/keyboards.py`：`kb_signature_request`, `kb_pin_pad`, `kb_certificate_actions`
- `database.py`：`user_pins`, `case_signatures`, `get_user_pin_hash`, `set_user_pin_hash`, `save_case_signature`, `get_signature_by_hex`
