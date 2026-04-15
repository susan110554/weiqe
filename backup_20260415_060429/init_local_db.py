#!/usr/bin/env python3
"""
本地数据库初始化脚本
自动创建数据库并初始化表结构
"""
import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

import asyncpg
from dotenv import load_dotenv

load_dotenv()

async def create_connection():
    """创建单个数据库连接"""
    return await asyncpg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        database=os.getenv("DB_NAME", "weiquan_bot"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )

async def main():
    """初始化本地数据库"""
    print("🔄 开始初始化本地数据库...")
    
    conn = None
    try:
        # 创建单个连接而不是连接池
        conn = await create_connection()
        print("✅ 数据库连接成功")
        
        # 导入并运行 init_db，但使用我们的连接
        from database import init_db
        
        # 临时替换全局连接池以使用单个连接
        import database
        original_get_pool = database.get_pool
        
        class MockPool:
            def __init__(self, conn):
                self._conn = conn
            
            def acquire(self):
                return MockConnection(self._conn)
        
        class MockConnection:
            def __init__(self, conn):
                self._conn = conn
            
            async def __aenter__(self):
                return self._conn
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        
        # 替换 get_pool 函数
        async def mock_get_pool():
            return MockPool(conn)
        
        database.get_pool = mock_get_pool
        
        try:
            # 初始化表结构
            await init_db()
            print("✅ 数据库表结构初始化完成")
        finally:
            # 恢复原始函数
            database.get_pool = original_get_pool
        
        # 验证表是否创建成功
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        print(f"✅ 成功创建 {len(tables)} 个表:")
        for table in tables:
            print(f"   - {table['table_name']}")
                
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        print("\n🔧 可能的解决方案:")
        print("1. 检查 PostgreSQL 服务是否运行")
        print("2. 验证 .env 文件中的数据库配置")
        print("3. 确保数据库 'weiquan_bot' 已创建")
        print("4. 检查用户权限")
        return False
        
    finally:
        if conn:
            await conn.close()
    
    print("\n🎉 数据库初始化完成！现在可以运行 bot.py")
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
