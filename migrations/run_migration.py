#!/usr/bin/env python3
"""
数据库迁移脚本 - 创建 push_tasks 表
运行: python migrations/run_migration.py
"""
import asyncio
import os
import sys

import asyncpg

MIGRATION_SQL = """
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
"""

async def run_migration():
    print("🔧 开始执行数据库迁移...")
    
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
        await conn.execute(MIGRATION_SQL)
        print("✅ push_tasks 表创建成功!")
        print("✅ 索引创建成功!")
        return True
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        return False
    finally:
        if conn:
            await conn.close()

if __name__ == "__main__":
    success = asyncio.run(run_migration())
    sys.exit(0 if success else 1)
