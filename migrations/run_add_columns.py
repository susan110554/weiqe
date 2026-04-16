#!/usr/bin/env python3
"""
数据库迁移脚本 - 添加缺失字段
运行: python migrations/run_add_columns.py
"""
import asyncio
import os
import sys

import asyncpg

MIGRATION_SQL = """
-- 1. 为 cases 表添加 auto_push_settings 字段
ALTER TABLE cases 
ADD COLUMN IF NOT EXISTS auto_push_settings JSONB DEFAULT '{}'::jsonb;

COMMENT ON COLUMN cases.auto_push_settings IS '自动推送设置 (JSON格式: {enabled, schedule, updated_at, updated_by})';

-- 2. 为 liaison_messages 表添加 sent_at 字段
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'liaison_messages' AND column_name = 'sent_at'
    ) THEN
        ALTER TABLE liaison_messages ADD COLUMN sent_at TIMESTAMPTZ;
        UPDATE liaison_messages SET sent_at = created_at WHERE sent_at IS NULL;
    END IF;
END $$;

COMMENT ON COLUMN liaison_messages.sent_at IS '消息发送时间';

-- 3. 为 cases 表添加 user_id 字段
ALTER TABLE cases 
ADD COLUMN IF NOT EXISTS user_id INTEGER;

COMMENT ON COLUMN cases.user_id IS '关联 users 表的 ID';

-- 4. 确保 cases 表有 tg_user_id 字段
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
"""

VERIFICATION_SQL = """
SELECT 
    table_name,
    column_name,
    data_type
FROM information_schema.columns 
WHERE (table_name = 'cases' AND column_name IN ('auto_push_settings', 'user_id', 'tg_user_id'))
   OR (table_name = 'liaison_messages' AND column_name = 'sent_at')
ORDER BY table_name, column_name;
"""

async def run_migration():
    print("🔧 开始执行数据库字段迁移...")
    
    # 加载环境变量
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_path):
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip())
    
    host = os.getenv('DB_HOST', 'localhost')
    port = int(os.getenv('DB_PORT', 5432))
    database = os.getenv('DB_NAME', 'weiquan_bot')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '')
    
    print(f"   连接配置: {host}:{port}/{database} (用户: {user})")
    
    conn = None
    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        
        # 执行迁移
        await conn.execute(MIGRATION_SQL)
        print("✅ 字段添加成功!")
        
        # 验证
        rows = await conn.fetch(VERIFICATION_SQL)
        print("\n📋 验证结果:")
        for row in rows:
            print(f"   ✅ {row['table_name']}.{row['column_name']} ({row['data_type']})")
        
        return True
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if conn:
            await conn.close()

if __name__ == "__main__":
    success = asyncio.run(run_migration())
    sys.exit(0 if success else 1)
