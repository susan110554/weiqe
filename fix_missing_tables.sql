-- ══════════════════════════════════════════════════════
-- 修复缺失表：若仅执行过 setup_db.sql 旧版，缺少 case_signatures / user_pins
-- 在 pgAdmin 中连接 weiquan_bot 后执行此文件
-- ══════════════════════════════════════════════════════

-- 1. case_signatures（案件数字签名）
CREATE TABLE IF NOT EXISTS case_signatures (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_no      TEXT NOT NULL UNIQUE,
    tg_user_id   BIGINT NOT NULL,
    signed_at    TIMESTAMPTZ DEFAULT NOW(),
    signature_hex TEXT NOT NULL,
    ip_address   TEXT,
    auth_ref     TEXT
);

-- 2. user_pins（用户 PIN）
CREATE TABLE IF NOT EXISTS user_pins (
    tg_user_id  BIGINT PRIMARY KEY,
    pin_hash    TEXT NOT NULL,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

SELECT '✅ 缺失表已创建！' AS result;
