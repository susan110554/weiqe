-- P1-P12 阶段推送任务表迁移
-- 执行: psql -d your_db -f create_push_tasks_table.sql

CREATE TABLE IF NOT EXISTS push_tasks (
    id                   BIGSERIAL PRIMARY KEY,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    case_no              TEXT NOT NULL,
    tg_user_id           BIGINT NOT NULL,
    phase                TEXT NOT NULL,
    push_type            TEXT NOT NULL DEFAULT 'auto',
    status               TEXT NOT NULL DEFAULT 'pending',
    scheduled_at         TIMESTAMPTZ NOT NULL,
    sent_at              TIMESTAMPTZ,
    read_at              TIMESTAMPTZ,
    tg_message_id        BIGINT,
    error_message        TEXT,
    template_data        JSONB DEFAULT '{}'::jsonb,
    cancelled_at         TIMESTAMPTZ,
    cancelled_by         TEXT
);

CREATE INDEX IF NOT EXISTS idx_push_tasks_case ON push_tasks (case_no, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_push_tasks_status ON push_tasks (status, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_push_tasks_pending ON push_tasks (status, scheduled_at) WHERE status = 'pending';

COMMENT ON TABLE push_tasks IS 'P1-P12阶段推送任务管理表';
