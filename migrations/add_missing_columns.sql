-- 添加缺失的数据库字段
-- 执行: psql -d weiquan_bot -f add_missing_columns.sql

-- 1. 为 cases 表添加 auto_push_settings 字段
ALTER TABLE cases 
ADD COLUMN IF NOT EXISTS auto_push_settings JSONB DEFAULT '{}'::jsonb;

COMMENT ON COLUMN cases.auto_push_settings IS '自动推送设置 (JSON格式: {enabled, schedule, updated_at, updated_by})';

-- 2. 为 liaison_messages 表添加 sent_at 字段（如果不存在）
-- 注意：表已有 created_at，我们添加 sent_at 作为发送时间
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'liaison_messages' AND column_name = 'sent_at'
    ) THEN
        ALTER TABLE liaison_messages ADD COLUMN sent_at TIMESTAMPTZ;
        -- 将现有数据的 created_at 复制到 sent_at
        UPDATE liaison_messages SET sent_at = created_at WHERE sent_at IS NULL;
    END IF;
END $$;

COMMENT ON COLUMN liaison_messages.sent_at IS '消息发送时间';

-- 3. 为 cases 表添加 user_id 字段（关联 users 表）
ALTER TABLE cases 
ADD COLUMN IF NOT EXISTS user_id INTEGER;

COMMENT ON COLUMN cases.user_id IS '关联 users 表的 ID';

-- 4. 为 cases 表添加 tg_user_id 字段（如果尚未存在）
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'cases' AND column_name = 'tg_user_id'
    ) THEN
        ALTER TABLE cases ADD COLUMN tg_user_id BIGINT;
    END IF;
END $$;

-- 5. 创建索引
CREATE INDEX IF NOT EXISTS idx_cases_auto_push ON cases ((auto_push_settings->>'enabled')) 
WHERE auto_push_settings->>'enabled' = 'true';

-- 验证
SELECT 
    'cases.auto_push_settings' as column_name,
    CASE WHEN EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'cases' AND column_name = 'auto_push_settings'
    ) THEN '✅ 存在' ELSE '❌ 缺失' END as status
UNION ALL
SELECT 
    'liaison_messages.sent_at',
    CASE WHEN EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'liaison_messages' AND column_name = 'sent_at'
    ) THEN '✅ 存在' ELSE '❌ 缺失' END
UNION ALL
SELECT 
    'cases.user_id',
    CASE WHEN EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'cases' AND column_name = 'user_id'
    ) THEN '✅ 存在' ELSE '❌ 缺失' END;
