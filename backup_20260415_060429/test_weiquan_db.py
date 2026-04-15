#!/usr/bin/env python3
"""直接测试连接到 weiquan_bot 数据库"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def test_weiquan_db():
    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", 5432))
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")
    database = os.getenv("DB_NAME", "weiquan_bot")
    
    print("=== 测试直接连接到 weiquan_bot 数据库 ===")
    print(f"连接参数: {user}@{host}:{port}/{database}")
    
    try:
        # 测试单个连接
        print("1️⃣ 测试单个连接...")
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        print("✅ 单个连接成功")
        
        # 测试简单查询
        result = await conn.fetchval("SELECT version()")
        print(f"✅ 查询成功: PostgreSQL {result.split()[1]}")
        
        await conn.close()
        
        # 测试连接池
        print("\n2️⃣ 测试连接池...")
        pool = await asyncpg.create_pool(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            min_size=1,
            max_size=2
        )
        print("✅ 连接池创建成功")
        
        # 测试从连接池获取连接
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT current_database()")
            print(f"✅ 连接池查询成功: 当前数据库 = {result}")
        
        await pool.close()
        print("✅ 连接池关闭成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        print(f"错误类型: {type(e).__name__}")
        
        # 检查是否是权限问题
        if "permission denied" in str(e).lower():
            print("💡 这是权限问题，用户可能没有访问数据库的权限")
        elif "does not exist" in str(e).lower():
            print("💡 数据库可能不存在或名称错误")
        elif "authentication failed" in str(e).lower():
            print("💡 认证失败，检查用户名和密码")
        
        return False

if __name__ == "__main__":
    success = asyncio.run(test_weiquan_db())
    if success:
        print("\n🎉 所有测试通过！可以尝试运行 init_local_db.py")
    else:
        print("\n❌ 需要先解决连接问题")
