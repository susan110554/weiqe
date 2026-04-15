#!/usr/bin/env python3
"""
调试版本的数据库初始化脚本
逐步执行，找出具体在哪里失败
"""
import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from database import get_pool, close_pool
import asyncpg

async def debug_init():
    """逐步调试初始化过程"""
    print("🔄 开始调试数据库初始化...")
    
    try:
        print("1️⃣ 获取连接池...")
        pool = await get_pool()
        print("✅ 连接池获取成功")
        
        print("2️⃣ 测试连接池连接...")
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT current_database()")
            print(f"✅ 连接池测试成功，当前数据库: {result}")
        
        print("3️⃣ 检查现有表...")
        async with pool.acquire() as conn:
            tables = await conn.fetch("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            print(f"📋 当前有 {len(tables)} 个表:")
            for table in tables:
                print(f"   - {table['table_name']}")
        
        print("4️⃣ 尝试创建一个简单的测试表...")
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS test_table (
                    id SERIAL PRIMARY KEY,
                    name TEXT
                )
            """)
            print("✅ 测试表创建成功")
            
            # 删除测试表
            await conn.execute("DROP TABLE IF EXISTS test_table")
            print("✅ 测试表删除成功")
        
        print("5️⃣ 尝试执行 init_db() 的第一个 SQL 语句...")
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS cases (
                    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    case_no       TEXT UNIQUE NOT NULL,
                    created_at    TIMESTAMPTZ DEFAULT NOW(),
                    updated_at    TIMESTAMPTZ DEFAULT NOW(),

                    -- 用户信息
                    tg_user_id    BIGINT NOT NULL,
                    tg_username   TEXT,

                    -- 案件详情
                    platform      TEXT NOT NULL,
                    amount        NUMERIC(20,6),
                    coin          TEXT,
                    incident_time TEXT,
                    wallet_addr   TEXT,
                    chain_type    TEXT,
                    tx_hash       TEXT,
                    contact       TEXT,

                    -- 状态管理
                    status        TEXT DEFAULT '待初步审核',
                    admin_notes   TEXT,

                    -- 风险评分
                    risk_score    INTEGER DEFAULT 0,
                    risk_label    TEXT DEFAULT '未评估'
                );
            """)
            print("✅ cases 表创建成功")
        
        print("6️⃣ 现在尝试完整的 init_db()...")
        from database import init_db
        await init_db()
        print("✅ init_db() 执行成功！")
        
        return True
        
    except Exception as e:
        print(f"❌ 在步骤中失败: {e}")
        print(f"错误类型: {type(e).__name__}")
        import traceback
        print("详细错误信息:")
        traceback.print_exc()
        return False
        
    finally:
        await close_pool()

if __name__ == "__main__":
    success = asyncio.run(debug_init())
    if success:
        print("\n🎉 调试成功！数据库初始化完成")
    else:
        print("\n❌ 调试发现问题，需要进一步排查")
