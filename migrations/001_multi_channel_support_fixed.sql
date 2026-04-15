-- ══════════════════════════════════════════════════════
-- 多渠道支持数据库迁移脚本 (修复版)
-- 版本: 001-fixed
-- 描述: 添加WhatsApp Bot、Web控制器支持，统一内容管理
-- ══════════════════════════════════════════════════════

-- 1. 扩展现有cases表，添加渠道支持
ALTER TABLE cases ADD COLUMN IF NOT EXISTS channel VARCHAR(20) DEFAULT 'telegram';
ALTER TABLE cases ADD COLUMN IF NOT EXISTS channel_user_id VARCHAR(100);

-- 更新现有数据
UPDATE cases SET 
    channel = 'telegram',
    channel_user_id = CAST(tg_user_id AS VARCHAR)
WHERE channel IS NULL OR channel_user_id IS NULL;

-- 添加索引
CREATE INDEX IF NOT EXISTS idx_cases_channel ON cases(channel);
CREATE INDEX IF NOT EXISTS idx_cases_channel_user_id ON cases(channel_user_id);

-- 2. 创建内容模板表
CREATE TABLE IF NOT EXISTS content_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_key VARCHAR(100) NOT NULL,
    channel_type VARCHAR(20) NOT NULL, -- 'telegram', 'whatsapp', 'web', 'default'
    content_type VARCHAR(20) NOT NULL DEFAULT 'text', -- 'text', 'html', 'markdown', 'image'
    title VARCHAR(200),
    content TEXT NOT NULL,
    variables JSONB, -- 模板变量定义 {"var_name": "description"}
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(template_key, channel_type)
);

-- 内容模板索引
CREATE INDEX IF NOT EXISTS idx_content_templates_key ON content_templates(template_key);
CREATE INDEX IF NOT EXISTS idx_content_templates_channel ON content_templates(channel_type);
CREATE INDEX IF NOT EXISTS idx_content_templates_active ON content_templates(is_active);

-- 3. 创建PDF模板表
CREATE TABLE IF NOT EXISTS pdf_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_name VARCHAR(100) UNIQUE NOT NULL,
    template_type VARCHAR(50) NOT NULL, -- 'case_report', 'certificate', 'receipt', 'custom'
    description TEXT,
    template_data JSONB NOT NULL, -- PDF模板配置
    preview_image BYTEA, -- 模板预览图
    is_active BOOLEAN DEFAULT true,
    created_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- PDF模板索引
CREATE INDEX IF NOT EXISTS idx_pdf_templates_type ON pdf_templates(template_type);
CREATE INDEX IF NOT EXISTS idx_pdf_templates_active ON pdf_templates(is_active);

-- 4. 创建渠道配置表
CREATE TABLE IF NOT EXISTS channel_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_type VARCHAR(20) NOT NULL, -- 'telegram', 'whatsapp', 'web'
    config_key VARCHAR(100) NOT NULL,
    config_value TEXT NOT NULL,
    config_type VARCHAR(20) DEFAULT 'string', -- 'string', 'number', 'boolean', 'json'
    description TEXT,
    is_sensitive BOOLEAN DEFAULT false, -- 是否为敏感配置（如API密钥）
    updated_by VARCHAR(100),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(channel_type, config_key)
);

-- 渠道配置索引
CREATE INDEX IF NOT EXISTS idx_channel_configs_type ON channel_configs(channel_type);
CREATE INDEX IF NOT EXISTS idx_channel_configs_key ON channel_configs(config_key);

-- 5. 创建通知规则表
CREATE TABLE IF NOT EXISTS notification_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name VARCHAR(100) UNIQUE NOT NULL,
    trigger_event VARCHAR(50) NOT NULL, -- 'case_created', 'status_changed', 'payment_received'
    target_channels TEXT[] NOT NULL, -- ['telegram', 'whatsapp', 'email']
    conditions JSONB, -- 触发条件
    template_key VARCHAR(100), -- 使用的模板
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 通知规则索引
CREATE INDEX IF NOT EXISTS idx_notification_rules_event ON notification_rules(trigger_event);
CREATE INDEX IF NOT EXISTS idx_notification_rules_active ON notification_rules(is_active);

-- 6. 创建消息发送日志表
CREATE TABLE IF NOT EXISTS message_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_type VARCHAR(20) NOT NULL,
    channel_user_id VARCHAR(100) NOT NULL,
    message_type VARCHAR(20) NOT NULL, -- 'text', 'document', 'image'
    template_key VARCHAR(100),
    content_preview TEXT, -- 消息内容预览（前200字符）
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'sent', 'failed', 'delivered'
    error_message TEXT,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    delivered_at TIMESTAMPTZ,
    
    -- 关联案件（可选）
    case_id UUID REFERENCES cases(id) ON DELETE SET NULL
);

-- 消息日志索引
CREATE INDEX IF NOT EXISTS idx_message_logs_channel ON message_logs(channel_type, channel_user_id);
CREATE INDEX IF NOT EXISTS idx_message_logs_status ON message_logs(status);
CREATE INDEX IF NOT EXISTS idx_message_logs_sent_at ON message_logs(sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_message_logs_case_id ON message_logs(case_id);

-- 7. 创建用户会话状态表（替代内存存储）
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_type VARCHAR(20) NOT NULL,
    channel_user_id VARCHAR(100) NOT NULL,
    session_data JSONB NOT NULL, -- 会话状态数据
    current_state VARCHAR(50),
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(channel_type, channel_user_id)
);

-- 用户会话索引
CREATE INDEX IF NOT EXISTS idx_user_sessions_channel_user ON user_sessions(channel_type, channel_user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires ON user_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_user_sessions_state ON user_sessions(current_state);

-- 8. 扩展audit_logs表，添加渠道信息
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS channel_type VARCHAR(20);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS channel_user_id VARCHAR(100);

-- 更新现有审计日志
UPDATE audit_logs SET 
    channel_type = 'telegram',
    channel_user_id = actor_id
WHERE channel_type IS NULL AND actor_type = 'USER';

-- 9. 创建系统配置表
CREATE TABLE IF NOT EXISTS system_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value TEXT NOT NULL,
    config_type VARCHAR(20) DEFAULT 'string',
    description TEXT,
    is_public BOOLEAN DEFAULT false, -- 是否可通过API公开访问
    updated_by VARCHAR(100),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 系统配置索引
CREATE INDEX IF NOT EXISTS idx_system_configs_key ON system_configs(config_key);
CREATE INDEX IF NOT EXISTS idx_system_configs_public ON system_configs(is_public);

-- 10. 创建触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为新表添加更新时间触发器
DROP TRIGGER IF EXISTS update_content_templates_updated_at ON content_templates;
CREATE TRIGGER update_content_templates_updated_at
    BEFORE UPDATE ON content_templates
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

DROP TRIGGER IF EXISTS update_pdf_templates_updated_at ON pdf_templates;
CREATE TRIGGER update_pdf_templates_updated_at
    BEFORE UPDATE ON pdf_templates
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

DROP TRIGGER IF EXISTS update_channel_configs_updated_at ON channel_configs;
CREATE TRIGGER update_channel_configs_updated_at
    BEFORE UPDATE ON channel_configs
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

DROP TRIGGER IF EXISTS update_user_sessions_updated_at ON user_sessions;
CREATE TRIGGER update_user_sessions_updated_at
    BEFORE UPDATE ON user_sessions
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

-- 11. 创建清理过期会话的函数
CREATE OR REPLACE FUNCTION cleanup_expired_sessions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM user_sessions WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- 12. 插入默认配置数据

-- 默认渠道配置
INSERT INTO channel_configs (channel_type, config_key, config_value, description) VALUES
('telegram', 'bot_token', '', 'Telegram Bot API Token'),
('telegram', 'webhook_url', '', 'Telegram Webhook URL'),
('telegram', 'max_file_size', '50000000', 'Maximum file size in bytes (50MB)'),
('whatsapp', 'api_key', '', 'WhatsApp Business API Key'),
('whatsapp', 'phone_number_id', '', 'WhatsApp Phone Number ID'),
('whatsapp', 'webhook_verify_token', '', 'WhatsApp Webhook Verification Token'),
('web', 'admin_token', '', 'Web Admin Authentication Token'),
('web', 'session_timeout', '3600', 'Web Session Timeout in seconds'),
('web', 'cors_origins', '*', 'CORS Allowed Origins')
ON CONFLICT (channel_type, config_key) DO NOTHING;

-- 默认系统配置
INSERT INTO system_configs (config_key, config_value, description, is_public) VALUES
('system_name', 'FBI IC3 Multi-Channel System', 'System Display Name', true),
('system_version', '2.0.0', 'System Version', true),
('maintenance_mode', 'false', 'System Maintenance Mode', false),
('max_cases_per_user_per_day', '5', 'Maximum cases per user per day', false),
('case_id_prefix', 'IC3', 'Case ID Prefix', false)
ON CONFLICT (config_key) DO NOTHING;

-- 默认通知规则
INSERT INTO notification_rules (rule_name, trigger_event, target_channels, template_key) VALUES
('case_created_notification', 'case_created', ARRAY['telegram', 'whatsapp'], 'case_created_success'),
('status_changed_notification', 'status_changed', ARRAY['telegram', 'whatsapp'], 'case_status_updated'),
('payment_received_notification', 'payment_received', ARRAY['telegram', 'whatsapp'], 'payment_confirmed')
ON CONFLICT (rule_name) DO NOTHING;

-- 13. 创建视图：多渠道案件统计
CREATE OR REPLACE VIEW v_case_stats_by_channel AS
SELECT 
    channel,
    COUNT(*) as total_cases,
    COUNT(CASE WHEN status = '待初步审核' THEN 1 END) as pending_cases,
    COUNT(CASE WHEN status = '审核中' THEN 1 END) as under_review_cases,
    COUNT(CASE WHEN status = '已结案' THEN 1 END) as closed_cases,
    AVG(EXTRACT(EPOCH FROM (updated_at - created_at))/3600) as avg_processing_hours,
    DATE_TRUNC('day', created_at) as date_created
FROM cases 
GROUP BY channel, DATE_TRUNC('day', created_at)
ORDER BY date_created DESC, channel;

-- 14. 创建视图：模板使用统计
CREATE OR REPLACE VIEW v_template_usage_stats AS
SELECT 
    ct.template_key,
    ct.channel_type,
    ct.content_type,
    COUNT(ml.id) as usage_count,
    MAX(ml.sent_at) as last_used,
    ct.updated_at as last_updated
FROM content_templates ct
LEFT JOIN message_logs ml ON ct.template_key = ml.template_key
GROUP BY ct.id, ct.template_key, ct.channel_type, ct.content_type, ct.updated_at
ORDER BY usage_count DESC;

-- ══════════════════════════════════════════════════════
-- 迁移验证
-- ══════════════════════════════════════════════════════

DO $$
DECLARE
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name IN (
        'content_templates', 'pdf_templates', 'channel_configs', 
        'notification_rules', 'message_logs', 'user_sessions', 'system_configs'
    );
    
    IF table_count = 7 THEN
        RAISE NOTICE '✅ Multi-channel migration completed successfully. Created % new tables.', table_count;
    ELSE
        RAISE EXCEPTION '❌ Migration incomplete. Expected 7 tables, found %', table_count;
    END IF;
END $$;
