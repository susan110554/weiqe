#!/usr/bin/env python3
"""
分步执行多渠道架构数据库迁移
避免一次性执行大量SQL导致的问题
"""
import asyncio
import asyncpg
import os
import sys
from dotenv import load_dotenv

load_dotenv()

async def execute_sql_step(conn, step_name, sql):
    """执行单个SQL步骤"""
    try:
        print(f"⏳ 执行步骤: {step_name}")
        await conn.execute(sql)
        print(f"✅ 完成: {step_name}")
        return True
    except Exception as e:
        print(f"❌ 失败: {step_name} - {e}")
        return False

async def main():
    """分步执行迁移"""
    print("🚀 开始分步执行多渠道架构数据库迁移...")
    
    # 数据库连接
    db_config = {
        'host': os.getenv("DB_HOST", "localhost"),
        'port': int(os.getenv("DB_PORT", 5432)),
        'database': os.getenv("DB_NAME", "weiquan_bot"),
        'user': os.getenv("DB_USER", "postgres"),
        'password': os.getenv("DB_PASSWORD", ""),
    }
    
    conn = await asyncpg.connect(**db_config)
    print("✅ 数据库连接成功")
    
    # 步骤1: 扩展cases表
    step1_sql = """
    ALTER TABLE cases ADD COLUMN IF NOT EXISTS channel VARCHAR(20) DEFAULT 'telegram';
    ALTER TABLE cases ADD COLUMN IF NOT EXISTS channel_user_id VARCHAR(100);
    """
    await execute_sql_step(conn, "扩展cases表", step1_sql)
    
    # 步骤2: 更新现有数据
    step2_sql = """
    UPDATE cases SET 
        channel = 'telegram',
        channel_user_id = CAST(tg_user_id AS VARCHAR)
    WHERE channel IS NULL OR channel_user_id IS NULL;
    """
    await execute_sql_step(conn, "更新现有案件数据", step2_sql)
    
    # 步骤3: 创建内容模板表
    step3_sql = """
    CREATE TABLE IF NOT EXISTS content_templates (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        template_key VARCHAR(100) NOT NULL,
        channel_type VARCHAR(20) NOT NULL,
        content_type VARCHAR(20) NOT NULL DEFAULT 'text',
        title VARCHAR(200),
        content TEXT NOT NULL,
        variables JSONB,
        is_active BOOLEAN DEFAULT true,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(template_key, channel_type)
    );
    """
    await execute_sql_step(conn, "创建内容模板表", step3_sql)
    
    # 步骤4: 创建PDF模板表
    step4_sql = """
    CREATE TABLE IF NOT EXISTS pdf_templates (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        template_name VARCHAR(100) UNIQUE NOT NULL,
        template_type VARCHAR(50) NOT NULL,
        description TEXT,
        template_data JSONB NOT NULL,
        preview_image BYTEA,
        is_active BOOLEAN DEFAULT true,
        created_by VARCHAR(100),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """
    await execute_sql_step(conn, "创建PDF模板表", step4_sql)
    
    # 步骤5: 创建渠道配置表
    step5_sql = """
    CREATE TABLE IF NOT EXISTS channel_configs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        channel_type VARCHAR(20) NOT NULL,
        config_key VARCHAR(100) NOT NULL,
        config_value TEXT NOT NULL,
        config_type VARCHAR(20) DEFAULT 'string',
        description TEXT,
        is_sensitive BOOLEAN DEFAULT false,
        updated_by VARCHAR(100),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(channel_type, config_key)
    );
    """
    await execute_sql_step(conn, "创建渠道配置表", step5_sql)
    
    # 步骤6: 创建通知规则表
    step6_sql = """
    CREATE TABLE IF NOT EXISTS notification_rules (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        rule_name VARCHAR(100) UNIQUE NOT NULL,
        trigger_event VARCHAR(50) NOT NULL,
        target_channels TEXT[] NOT NULL,
        conditions JSONB,
        template_key VARCHAR(100),
        is_active BOOLEAN DEFAULT true,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """
    await execute_sql_step(conn, "创建通知规则表", step6_sql)
    
    # 步骤7: 创建消息日志表
    step7_sql = """
    CREATE TABLE IF NOT EXISTS message_logs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        channel_type VARCHAR(20) NOT NULL,
        channel_user_id VARCHAR(100) NOT NULL,
        message_type VARCHAR(20) NOT NULL,
        template_key VARCHAR(100),
        content_preview TEXT,
        status VARCHAR(20) DEFAULT 'pending',
        error_message TEXT,
        sent_at TIMESTAMPTZ DEFAULT NOW(),
        delivered_at TIMESTAMPTZ,
        case_id UUID REFERENCES cases(id) ON DELETE SET NULL
    );
    """
    await execute_sql_step(conn, "创建消息日志表", step7_sql)
    
    # 步骤8: 创建用户会话表
    step8_sql = """
    CREATE TABLE IF NOT EXISTS user_sessions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        channel_type VARCHAR(20) NOT NULL,
        channel_user_id VARCHAR(100) NOT NULL,
        session_data JSONB NOT NULL,
        current_state VARCHAR(50),
        expires_at TIMESTAMPTZ NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(channel_type, channel_user_id)
    );
    """
    await execute_sql_step(conn, "创建用户会话表", step8_sql)
    
    # 步骤9: 创建系统配置表
    step9_sql = """
    CREATE TABLE IF NOT EXISTS system_configs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        config_key VARCHAR(100) UNIQUE NOT NULL,
        config_value TEXT NOT NULL,
        config_type VARCHAR(20) DEFAULT 'string',
        description TEXT,
        is_public BOOLEAN DEFAULT false,
        updated_by VARCHAR(100),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """
    await execute_sql_step(conn, "创建系统配置表", step9_sql)
    
    # 步骤10: 创建索引
    index_sql = """
    CREATE INDEX IF NOT EXISTS idx_cases_channel ON cases(channel);
    CREATE INDEX IF NOT EXISTS idx_cases_channel_user_id ON cases(channel_user_id);
    CREATE INDEX IF NOT EXISTS idx_content_templates_key ON content_templates(template_key);
    CREATE INDEX IF NOT EXISTS idx_content_templates_channel ON content_templates(channel_type);
    CREATE INDEX IF NOT EXISTS idx_channel_configs_type ON channel_configs(channel_type);
    CREATE INDEX IF NOT EXISTS idx_notification_rules_event ON notification_rules(trigger_event);
    CREATE INDEX IF NOT EXISTS idx_message_logs_channel ON message_logs(channel_type, channel_user_id);
    CREATE INDEX IF NOT EXISTS idx_user_sessions_channel_user ON user_sessions(channel_type, channel_user_id);
    CREATE INDEX IF NOT EXISTS idx_system_configs_key ON system_configs(config_key);
    """
    await execute_sql_step(conn, "创建索引", index_sql)
    
    # 步骤11: 插入默认配置
    config_sql = """
    INSERT INTO channel_configs (channel_type, config_key, config_value, description) VALUES
    ('telegram', 'bot_token', '', 'Telegram Bot API Token'),
    ('telegram', 'webhook_url', '', 'Telegram Webhook URL'),
    ('telegram', 'max_file_size', '50000000', 'Maximum file size in bytes'),
    ('whatsapp', 'api_key', '', 'WhatsApp Business API Key'),
    ('whatsapp', 'phone_number_id', '', 'WhatsApp Phone Number ID'),
    ('web', 'admin_token', '', 'Web Admin Authentication Token'),
    ('web', 'session_timeout', '3600', 'Web Session Timeout in seconds')
    ON CONFLICT (channel_type, config_key) DO NOTHING;
    """
    await execute_sql_step(conn, "插入渠道配置", config_sql)
    
    system_config_sql = """
    INSERT INTO system_configs (config_key, config_value, description, is_public) VALUES
    ('system_name', 'FBI IC3 Multi-Channel System', 'System Display Name', true),
    ('system_version', '2.0.0', 'System Version', true),
    ('maintenance_mode', 'false', 'System Maintenance Mode', false),
    ('case_id_prefix', 'IC3', 'Case ID Prefix', false)
    ON CONFLICT (config_key) DO NOTHING;
    """
    await execute_sql_step(conn, "插入系统配置", system_config_sql)
    
    notification_sql = """
    INSERT INTO notification_rules (rule_name, trigger_event, target_channels, template_key) VALUES
    ('case_created_notification', 'case_created', ARRAY['telegram', 'whatsapp'], 'case_created_success'),
    ('status_changed_notification', 'status_changed', ARRAY['telegram', 'whatsapp'], 'case_status_updated')
    ON CONFLICT (rule_name) DO NOTHING;
    """
    await execute_sql_step(conn, "插入通知规则", notification_sql)
    
    # 验证结果
    print("\n🔍 验证迁移结果...")
    
    # 检查新表
    new_tables = await conn.fetch("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name IN (
            'content_templates', 'pdf_templates', 'channel_configs', 
            'notification_rules', 'message_logs', 'user_sessions', 'system_configs'
        )
        ORDER BY table_name
    """)
    
    print(f"✅ 成功创建 {len(new_tables)} 个新表:")
    for table in new_tables:
        print(f"   - {table['table_name']}")
    
    # 检查cases表扩展
    cases_columns = await conn.fetch("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'cases'
        AND column_name IN ('channel', 'channel_user_id')
        ORDER BY column_name
    """)
    
    print(f"✅ cases表新增列: {len(cases_columns)} 个")
    for col in cases_columns:
        print(f"   - {col['column_name']}")
    
    # 检查配置数据
    config_count = await conn.fetchval("SELECT COUNT(*) FROM channel_configs")
    system_config_count = await conn.fetchval("SELECT COUNT(*) FROM system_configs")
    
    print(f"✅ 配置数据:")
    print(f"   - 渠道配置: {config_count} 条")
    print(f"   - 系统配置: {system_config_count} 条")
    
    await conn.close()
    
    print("\n🎉 多渠道架构迁移完成!")
    print("📋 迁移总结:")
    print(f"   - 新增表: {len(new_tables)} 个")
    print(f"   - 扩展表: cases (添加渠道支持)")
    print(f"   - 配置数据: {config_count + system_config_count} 条")
    print("\n🚀 下一步:")
    print("1. 测试内容管理器")
    print("2. 开始业务逻辑抽离")
    print("3. 创建渠道适配器")

if __name__ == "__main__":
    try:
        asyncio.run(main())
        print("\n✅ 迁移成功完成!")
    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        sys.exit(1)
