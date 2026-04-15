#!/usr/bin/env python3
"""
测试Telegram适配器
验证适配器功能是否正常
"""
import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))


async def test_telegram_adapter():
    """测试Telegram适配器初始化和基本功能"""
    print("=" * 60)
    print("🧪 测试Telegram适配器")
    print("=" * 60)
    
    # 测试1: 导入模块
    print("\n1️⃣ 测试模块导入...")
    try:
        from adapters import TelegramAdapter, BaseChannelAdapter
        from core import CaseManager, ContentManager, SignatureService
        print("   ✅ 模块导入成功")
    except ImportError as e:
        print(f"   ❌ 导入失败: {e}")
        return False
    
    # 测试2: 检查继承关系
    print("\n2️⃣ 检查继承关系...")
    if issubclass(TelegramAdapter, BaseChannelAdapter):
        print("   ✅ TelegramAdapter正确继承BaseChannelAdapter")
    else:
        print("   ❌ 继承关系错误")
        return False
    
    # 测试3: 检查环境变量
    print("\n3️⃣ 检查环境变量...")
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    if telegram_token:
        print(f"   ✅ TELEGRAM_TOKEN已配置: {telegram_token[:10]}...")
    else:
        print("   ⚠️  TELEGRAM_TOKEN未配置")
    
    # 测试4: 初始化核心服务（使用单连接模式）
    print("\n4️⃣ 初始化核心服务...")
    try:
        import asyncpg
        import database as db
        
        # 创建单个数据库连接
        conn = await asyncpg.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 5432)),
            database=os.getenv("DB_NAME", "weiquan_bot"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
        )
        print("   ✅ 数据库连接成功")
        
        # 创建Mock Pool
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
        
        # 初始化核心服务
        content_manager = ContentManager(mock_pool)
        signature_service = SignatureService()
        case_manager = CaseManager(mock_pool, content_manager, signature_service)
        
        print("   ✅ 核心服务初始化成功")
        
        # 测试5: 初始化Telegram适配器
        print("\n5️⃣ 初始化Telegram适配器...")
        
        # 使用测试token或真实token
        test_token = telegram_token or "TEST_TOKEN_FOR_VALIDATION"
        
        try:
            adapter = TelegramAdapter(
                token=test_token,
                case_manager=case_manager,
                content_manager=content_manager,
                signature_service=signature_service
            )
            print("   ✅ TelegramAdapter初始化成功")
        except Exception as e:
            print(f"   ❌ 初始化失败: {e}")
            await conn.close()
            return False
        
        # 测试6: 验证适配器属性
        print("\n6️⃣ 验证适配器属性...")
        checks = [
            ("channel_type", adapter.channel_type == 'telegram'),
            ("case_manager", adapter.case_manager is not None),
            ("content_manager", adapter.content_manager is not None),
            ("signature_service", adapter.signature_service is not None),
            ("token", adapter.token == test_token),
        ]
        
        all_passed = True
        for name, result in checks:
            if result:
                print(f"   ✅ {name}")
            else:
                print(f"   ❌ {name}")
                all_passed = False
        
        # 测试7: 验证必需方法存在
        print("\n7️⃣ 验证必需方法...")
        required_methods = [
            'send_message',
            'send_document',
            'get_user_info',
            'handle_message',
            'handle_callback',
            'start',
            'stop',
        ]
        
        for method_name in required_methods:
            if hasattr(adapter, method_name):
                print(f"   ✅ {method_name}()")
            else:
                print(f"   ❌ {method_name}() 缺失")
                all_passed = False
        
        # 测试8: 测试辅助方法
        print("\n8️⃣ 测试辅助方法...")
        
        # 测试is_admin
        admin_ids = adapter._load_admin_ids()
        print(f"   ✅ _load_admin_ids(): {len(admin_ids)} admins")
        
        # 测试is_admin方法
        is_admin_result = adapter.is_admin(12345)
        print(f"   ✅ is_admin(12345): {is_admin_result}")
        
        # 清理
        await conn.close()
        print("\n   ✅ 数据库连接已关闭")
        
        print("\n" + "=" * 60)
        if all_passed:
            print("🎉 所有测试通过！")
            print("\n📋 Telegram适配器状态:")
            print(f"   - 渠道类型: {adapter.channel_type}")
            print(f"   - 管理员数量: {len(adapter.admin_ids)}")
            print(f"   - 核心服务: 已集成")
            print("   - 准备状态: ✅ 可以启动")
            print("\n💡 下一步:")
            print("   1. 确保TELEGRAM_TOKEN环境变量已设置")
            print("   2. 运行 start_telegram_adapter.py 启动适配器")
            print("   3. 测试/start命令")
            return True
        else:
            print("❌ 部分测试失败")
            return False
        
    except Exception as e:
        print(f"   ❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    try:
        success = await test_telegram_adapter()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ 测试被中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
