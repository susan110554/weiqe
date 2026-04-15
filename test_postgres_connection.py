#!/usr/bin/env python3
"""测试 PostgreSQL 基础连接"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def test_connection():
    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", 5432))
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")
    
    print("=== 测试 PostgreSQL 连接 ===")
    
    # 先测试连接到默认数据库 postgres
    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database="postgres"  # 默认数据库
        )
        print("✅ 成功连接到 PostgreSQL 服务器")
        
        # 检查 weiquan_bot 数据库是否存在
        result = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = 'weiquan_bot'"
        )
        
        if result:
            print("✅ 数据库 'weiquan_bot' 存在")
        else:
            print("❌ 数据库 'weiquan_bot' 不存在")
            print("💡 请在 pgAdmin 中创建数据库 'weiquan_bot'")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        print("💡 可能的问题:")
        print("  - PostgreSQL 密码错误")
        print("  - PostgreSQL 服务未启动")
        print("  - 网络连接问题")

if __name__ == "__main__":
    asyncio.run(test_connection())
