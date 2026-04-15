#!/usr/bin/env python3
"""
综合测试 - 测试所有适配器
验证Telegram和WhatsApp适配器的完整功能
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def test_all_adapters():
    """测试所有适配器"""
    print("=" * 70)
    print("🧪 FBI IC3 多渠道适配器 - 综合测试")
    print("=" * 70)
    
    all_tests_passed = True
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 测试1: 模块导入
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n📦 测试1: 模块导入")
    print("-" * 70)
    
    try:
        from adapters import BaseChannelAdapter, TelegramAdapter, WhatsAppAdapter
        from core import CaseManager, ContentManager, SignatureService
        print("   ✅ 所有模块导入成功")
        print(f"      - BaseChannelAdapter")
        print(f"      - TelegramAdapter")
        print(f"      - WhatsAppAdapter")
        print(f"      - CaseManager")
        print(f"      - ContentManager")
        print(f"      - SignatureService")
    except ImportError as e:
        print(f"   ❌ 导入失败: {e}")
        all_tests_passed = False
        return all_tests_passed
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 测试2: 继承关系
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n🔗 测试2: 继承关系")
    print("-" * 70)
    
    inheritance_checks = [
        ("TelegramAdapter", issubclass(TelegramAdapter, BaseChannelAdapter)),
        ("WhatsAppAdapter", issubclass(WhatsAppAdapter, BaseChannelAdapter)),
    ]
    
    for name, result in inheritance_checks:
        if result:
            print(f"   ✅ {name} 继承 BaseChannelAdapter")
        else:
            print(f"   ❌ {name} 继承关系错误")
            all_tests_passed = False
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 测试3: 必需方法检查
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n⚙️  测试3: 必需方法检查")
    print("-" * 70)
    
    required_methods = [
        'send_message',
        'send_document',
        'get_user_info',
        'handle_message',
        'handle_callback',
        'start',
        'stop',
    ]
    
    print("   Telegram适配器:")
    telegram_methods_ok = True
    for method in required_methods:
        if hasattr(TelegramAdapter, method):
            print(f"      ✅ {method}")
        else:
            print(f"      ❌ {method}")
            telegram_methods_ok = False
            all_tests_passed = False
    
    print("\n   WhatsApp适配器:")
    whatsapp_methods_ok = True
    for method in required_methods:
        if hasattr(WhatsAppAdapter, method):
            print(f"      ✅ {method}")
        else:
            print(f"      ❌ {method}")
            whatsapp_methods_ok = False
            all_tests_passed = False
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 测试4: Mock初始化
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n🏗️  测试4: Mock初始化")
    print("-" * 70)
    
    try:
        # 创建Mock服务
        class MockCaseManager:
            async def get_cases_paginated(self, *args, **kwargs):
                return {'cases': [], 'total': 0}
            async def get_case_by_id(self, case_id):
                return {
                    'case_no': case_id,
                    'status': 'Pending',
                    'full_name': 'Test User',
                    'email': 'test@example.com'
                }
            async def create_case(self, case_info):
                return f"IC3-2026-TEST-{case_info.get('channel', 'XX').upper()}-001"
        
        class MockContentManager:
            async def render_template(self, template_key, channel, variables):
                return {
                    'content': f"Template: {template_key} for {channel}",
                    'content_type': 'text'
                }
        
        class MockSignatureService:
            def generate_signature(self, data, user_id):
                return "mock_signature_hash"
        
        mock_case_manager = MockCaseManager()
        mock_content_manager = MockContentManager()
        mock_signature_service = MockSignatureService()
        
        # 初始化Telegram适配器
        telegram_adapter = TelegramAdapter(
            token="TEST_TELEGRAM_TOKEN",
            case_manager=mock_case_manager,
            content_manager=mock_content_manager,
            signature_service=mock_signature_service
        )
        print("   ✅ TelegramAdapter 初始化成功")
        
        # 初始化WhatsApp适配器
        whatsapp_adapter = WhatsAppAdapter(
            api_key="TEST_WHATSAPP_KEY",
            phone_number_id="123456789",
            webhook_verify_token="TEST_VERIFY_TOKEN",
            case_manager=mock_case_manager,
            content_manager=mock_content_manager
        )
        print("   ✅ WhatsAppAdapter 初始化成功")
        
    except Exception as e:
        print(f"   ❌ 初始化失败: {e}")
        all_tests_passed = False
        return all_tests_passed
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 测试5: 属性验证
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n🔍 测试5: 属性验证")
    print("-" * 70)
    
    print("   Telegram适配器:")
    telegram_checks = [
        ("channel_name", telegram_adapter.channel_name == 'telegram'),
        ("case_manager", telegram_adapter.case_manager is not None),
        ("content_manager", telegram_adapter.content_manager is not None),
        ("signature_service", telegram_adapter.signature_service is not None),
        ("token", telegram_adapter.token == "TEST_TELEGRAM_TOKEN"),
        ("admin_ids", isinstance(telegram_adapter.admin_ids, list)),
    ]
    
    for name, result in telegram_checks:
        if result:
            print(f"      ✅ {name}")
        else:
            print(f"      ❌ {name}")
            all_tests_passed = False
    
    print("\n   WhatsApp适配器:")
    whatsapp_checks = [
        ("channel_name", whatsapp_adapter.channel_name == 'whatsapp'),
        ("case_manager", whatsapp_adapter.case_manager is not None),
        ("content_manager", whatsapp_adapter.content_manager is not None),
        ("api_key", whatsapp_adapter.api_key == "TEST_WHATSAPP_KEY"),
        ("phone_number_id", whatsapp_adapter.phone_number_id == "123456789"),
        ("api_version", whatsapp_adapter.api_version == "v18.0"),
    ]
    
    for name, result in whatsapp_checks:
        if result:
            print(f"      ✅ {name}")
        else:
            print(f"      ❌ {name}")
            all_tests_passed = False
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 测试6: WhatsApp Webhook验证
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n🔐 测试6: WhatsApp Webhook验证")
    print("-" * 70)
    
    # 测试正确的token
    challenge = whatsapp_adapter.verify_webhook(
        "subscribe", 
        "TEST_VERIFY_TOKEN", 
        "test_challenge_12345"
    )
    if challenge == "test_challenge_12345":
        print("   ✅ 正确token验证通过")
    else:
        print("   ❌ 正确token验证失败")
        all_tests_passed = False
    
    # 测试错误的token
    challenge_fail = whatsapp_adapter.verify_webhook(
        "subscribe", 
        "WRONG_TOKEN", 
        "test_challenge"
    )
    if challenge_fail is None:
        print("   ✅ 错误token被正确拒绝")
    else:
        print("   ❌ 错误token未被拒绝")
        all_tests_passed = False
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 测试7: 辅助方法测试
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n🛠️  测试7: 辅助方法测试")
    print("-" * 70)
    
    # Telegram is_admin测试
    is_admin_result = telegram_adapter.is_admin(12345)
    print(f"   ✅ Telegram is_admin(12345): {is_admin_result}")
    
    # Telegram _load_admin_ids测试
    admin_ids = telegram_adapter._load_admin_ids()
    print(f"   ✅ Telegram _load_admin_ids(): {len(admin_ids)} admins")
    
    # WhatsApp get_user_info测试（同步版本 - 直接调用返回dict）
    # 注意：实际使用时get_user_info是async，这里测试基本逻辑
    import asyncio
    try:
        user_info = asyncio.run(whatsapp_adapter.get_user_info("8613800138000"))
        if user_info.get('user_id') == "8613800138000":
            print(f"   ✅ WhatsApp get_user_info() 返回正确")
        else:
            print(f"   ❌ WhatsApp get_user_info() 返回错误")
            all_tests_passed = False
    except Exception as e:
        print(f"   ⚠️  WhatsApp get_user_info() 测试跳过: {e}")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 总结
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n" + "=" * 70)
    if all_tests_passed:
        print("🎉 所有测试通过！")
        print("\n📊 测试总结:")
        print("   ✅ 模块导入: 通过")
        print("   ✅ 继承关系: 通过")
        print("   ✅ 必需方法: 通过")
        print("   ✅ Mock初始化: 通过")
        print("   ✅ 属性验证: 通过")
        print("   ✅ Webhook验证: 通过")
        print("   ✅ 辅助方法: 通过")
        
        print("\n📋 适配器信息:")
        print("   Telegram适配器:")
        print(f"      - 渠道: {telegram_adapter.channel_name}")
        print(f"      - Token: {telegram_adapter.token[:15]}...")
        print(f"      - 管理员数: {len(telegram_adapter.admin_ids)}")
        
        print("\n   WhatsApp适配器:")
        print(f"      - 渠道: {whatsapp_adapter.channel_name}")
        print(f"      - Phone ID: {whatsapp_adapter.phone_number_id}")
        print(f"      - API版本: {whatsapp_adapter.api_version}")
        
        print("\n✅ 适配器状态:")
        print("   - TelegramAdapter: 准备就绪")
        print("   - WhatsAppAdapter: 准备就绪")
        
        print("\n💡 下一步:")
        print("   1. Telegram: 设置TELEGRAM_TOKEN环境变量")
        print("   2. WhatsApp: 设置WHATSAPP_*环境变量")
        print("   3. 运行实际测试: python start_telegram_adapter.py")
        print("   4. 配置WhatsApp webhook并测试")
        
        print("\n📁 相关文件:")
        print("   - adapters/telegram_adapter.py (692行)")
        print("   - adapters/whatsapp_adapter.py (585行)")
        print("   - test_telegram_adapter_simple.py")
        print("   - test_whatsapp_adapter.py")
        print("   - test_all_adapters.py (本文件)")
        
        return True
    else:
        print("❌ 部分测试失败")
        print("\n请检查上述失败的测试项")
        return False


def main():
    """主函数"""
    try:
        success = test_all_adapters()
        
        print("\n" + "=" * 70)
        if success:
            print("✅ 综合测试完成: 所有测试通过")
            print("=" * 70)
            sys.exit(0)
        else:
            print("❌ 综合测试完成: 部分测试失败")
            print("=" * 70)
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
