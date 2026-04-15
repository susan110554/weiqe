#!/usr/bin/env python3
"""
启动Telegram适配器
使用新的适配器模式运行Telegram Bot
"""
import asyncio
import sys
import os
import logging
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def main():
    """主函数"""
    print("=" * 60)
    print("🤖 启动FBI IC3 Telegram Bot (适配器模式)")
    print("=" * 60)
    
    # 1. 检查环境变量
    print("\n1️⃣ 检查环境变量...")
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    if not telegram_token:
        print("   ❌ TELEGRAM_TOKEN未设置")
        print("   💡 请在.env文件中设置: TELEGRAM_TOKEN=your_bot_token")
        return
    print(f"   ✅ TELEGRAM_TOKEN: {telegram_token[:10]}...")
    
    db_name = os.getenv("DB_NAME", "weiquan_bot")
    db_host = os.getenv("DB_HOST", "localhost")
    print(f"   ✅ 数据库: {db_host}/{db_name}")
    
    # 2. 导入模块
    print("\n2️⃣ 导入模块...")
    try:
        import asyncpg
        from adapters import TelegramAdapter
        from core import CaseManager, ContentManager, SignatureService
        print("   ✅ 模块导入成功")
    except ImportError as e:
        print(f"   ❌ 导入失败: {e}")
        return
    
    # 3. 初始化数据库连接
    print("\n3️⃣ 连接数据库...")
    try:
        conn = await asyncpg.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 5432)),
            database=os.getenv("DB_NAME", "weiquan_bot"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
        )
        print("   ✅ 数据库连接成功")
        
        # 创建Mock Pool (Windows兼容)
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
        
        mock_pool = MockPool(conn)
        
    except Exception as e:
        print(f"   ❌ 数据库连接失败: {e}")
        print("   💡 请确保PostgreSQL正在运行")
        return
    
    # 4. 初始化核心服务
    print("\n4️⃣ 初始化核心服务...")
    try:
        content_manager = ContentManager(mock_pool)
        signature_service = SignatureService()
        case_manager = CaseManager(mock_pool, content_manager, signature_service)
        print("   ✅ 核心服务初始化完成")
    except Exception as e:
        print(f"   ❌ 核心服务初始化失败: {e}")
        await conn.close()
        return
    
    # 5. 初始化Telegram适配器
    print("\n5️⃣ 初始化Telegram适配器...")
    try:
        adapter = TelegramAdapter(
            token=telegram_token,
            case_manager=case_manager,
            content_manager=content_manager,
            signature_service=signature_service
        )
        print("   ✅ Telegram适配器初始化完成")
    except Exception as e:
        print(f"   ❌ 适配器初始化失败: {e}")
        await conn.close()
        return
    
    # 6. 启动适配器
    print("\n6️⃣ 启动Telegram Bot...")
    try:
        success = await adapter.start()
        
        if success:
            print("\n" + "=" * 60)
            print("✅ Telegram Bot已成功启动！")
            print("=" * 60)
            print("\n📱 Bot信息:")
            print(f"   - 渠道类型: {adapter.channel_type}")
            print(f"   - 管理员数量: {len(adapter.admin_ids)}")
            print("\n💡 可用命令:")
            print("   /start - 开始使用")
            print("   /help - 帮助信息")
            print("   /mycases - 查看我的案件")
            print("   /newcase - 创建新案件")
            print("   /status - 查询案件状态")
            print("\n⚠️  按Ctrl+C停止Bot")
            print("=" * 60)
            
            # 保持运行
            try:
                await asyncio.Event().wait()
            except KeyboardInterrupt:
                print("\n\n⚠️ 收到停止信号...")
                
        else:
            print("   ❌ 启动失败")
            
    except Exception as e:
        logger.error(f"启动过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    
    # 7. 清理
    print("\n7️⃣ 清理资源...")
    try:
        await adapter.stop()
        print("   ✅ Telegram适配器已停止")
    except Exception as e:
        logger.error(f"停止适配器失败: {e}")
    
    try:
        await conn.close()
        print("   ✅ 数据库连接已关闭")
    except Exception as e:
        logger.error(f"关闭数据库连接失败: {e}")
    
    print("\n" + "=" * 60)
    print("👋 Telegram Bot已停止")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ 程序被中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"程序异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
