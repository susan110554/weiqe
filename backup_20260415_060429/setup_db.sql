-- ══════════════════════════════════════════════════════
-- 维权机器人 PostgreSQL 数据库初始化脚本
-- 在 pgAdmin 4 中执行此文件
-- ══════════════════════════════════════════════════════

-- 1. 创建数据库（在 pgAdmin 中手动创建名为 weiquan_bot 的数据库后执行以下内容）

-- 2. 启用 UUID 扩展
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 3. 案件主表
CREATE TABLE IF NOT EXISTS cases (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_no       TEXT UNIQUE NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW(),

    tg_user_id    BIGINT NOT NULL,
    tg_username   TEXT,

    platform      TEXT NOT NULL,
    amount        NUMERIC(20,6),
    coin          TEXT,
    incident_time TEXT,
    wallet_addr   TEXT,
    chain_type    TEXT,
    tx_hash       TEXT,
    contact       TEXT,

    status        TEXT DEFAULT '待初步审核',
    admin_notes   TEXT,
    risk_score    INTEGER DEFAULT 0,
    risk_label    TEXT DEFAULT '未评估'
);

-- 提交时完整 PDF 载荷（多笔交易、CRS 等），供长期下载还原
ALTER TABLE cases ADD COLUMN IF NOT EXISTS case_pdf_snapshot JSONB;

-- 4. 证据文件表
CREATE TABLE IF NOT EXISTS evidences (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id     UUID REFERENCES cases(id) ON DELETE CASCADE,
    uploaded_at TIMESTAMPTZ DEFAULT NOW(),
    file_type   TEXT,
    file_id     TEXT,
    file_name   TEXT,
    description TEXT
);

-- 5. 审计日志表
CREATE TABLE IF NOT EXISTS audit_logs (
    id          BIGSERIAL PRIMARY KEY,
    logged_at   TIMESTAMPTZ DEFAULT NOW(),
    actor_type  TEXT,
    actor_id    TEXT,
    action      TEXT NOT NULL,
    target_id   TEXT,
    detail      TEXT
);

-- 6. 案件数字签名表 (CERTIFY-TRANSMIT 签名存储)
CREATE TABLE IF NOT EXISTS case_signatures (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_no      TEXT NOT NULL UNIQUE,
    tg_user_id   BIGINT NOT NULL,
    signed_at    TIMESTAMPTZ DEFAULT NOW(),
    signature_hex TEXT NOT NULL,
    ip_address   TEXT,
    auth_ref     TEXT
);

-- 7. 用户 PIN 表 (重置 PIN 用)
CREATE TABLE IF NOT EXISTS user_pins (
    tg_user_id  BIGINT PRIMARY KEY,
    pin_hash    TEXT NOT NULL,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 8. 状态变更历史
CREATE TABLE IF NOT EXISTS status_history (
    id          BIGSERIAL PRIMARY KEY,
    case_id     UUID REFERENCES cases(id) ON DELETE CASCADE,
    changed_at  TIMESTAMPTZ DEFAULT NOW(),
    old_status  TEXT,
    new_status  TEXT,
    changed_by  TEXT,
    note        TEXT
);

-- 9. 自动更新 updated_at 触发器
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_cases_updated ON cases;
CREATE TRIGGER trg_cases_updated
BEFORE UPDATE ON cases
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- 10. 索引优化
CREATE INDEX IF NOT EXISTS idx_cases_tg_user    ON cases(tg_user_id);
CREATE INDEX IF NOT EXISTS idx_cases_status      ON cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_created     ON cases(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logged      ON audit_logs(logged_at DESC);
CREATE INDEX IF NOT EXISTS idx_evidence_case     ON evidences(case_id);

-- 完成
SELECT '✅ 数据库初始化完成！' AS result;
