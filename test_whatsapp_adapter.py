#!/usr/bin/env python3
"""
测试WhatsApp适配器
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def test_whatsapp_adapter():
    """测试WhatsApp适配器结构"""
    print("=" * 60)
    print("🧪 WhatsApp适配器结构测试")
    print("=" * 60)
    
    # 测试1: 导入模块
    print("\n1️⃣ 测试模块导入...")
    try:
        from adapters import WhatsAppAdapter, BaseChannelAdapter
        print("   ✅ 模块导入成功")
    except ImportError as e:
        print(f"   ❌ 导入失败: {e}")
        return False
    
    # 测试2: 检查继承关系
    print("\n2️⃣ 检查继承关系...")
    if issubclass(WhatsAppAdapter, BaseChannelAdapter):
        print("   ✅ WhatsAppAdapter正确继承BaseChannelAdapter")
    else:
        print("   ❌ 继承关系错误")
        return False
    
    # 测试3: 检查类方法
    print("\n3️⃣ 检查类方法...")
    required_methods = [
        '__init__',
        'send_message',
        'send_document',
        'get_user_info',
        'handle_message',
        'handle_callback',
        'start',
        'stop',
        'verify_webhook',
        'process_webhook',
        '_cmd_start',
        '_cmd_help',
        '_cmd_mycases',
        '_cmd_newcase',
        '_handle_case_creation',
        '_handle_text_message',
    ]
    
    all_present = True
    for method_name in required_methods:
        if hasattr(WhatsAppAdapter, method_name):
            print(f"   ✅ {method_name}")
        else:
            print(f"   ❌ {method_name} 缺失")
            all_present = False
    
    # 测试4: Mock初始化测试
    print("\n4️⃣ Mock初始化测试...")
    try:
        # 创建Mock对象
        class MockCaseManager:
            async def get_cases_paginated(self, *args, **kwargs):
                return {'cases': [], 'total': 0}
            async def create_case(self, case_info):
                return "IC3-2026-WA-001"
        
        class MockContentManager:
            async def render_template(self, template_key, channel, variables):
                return {'content': f"Test template: {template_key}"}
        
        # 初始化适配器
        adapter = WhatsAppAdapter(
            api_key="TEST_API_KEY",
            phone_number_id="123456789",
            webhook_verify_token="TEST_VERIFY_TOKEN",
            case_manager=MockCaseManager(),
            content_manager=MockContentManager()
        )
        print("   ✅ Mock初始化成功")
        
        # 测试5: 验证适配器属性
        print("\n5️⃣ 验证适配器属性...")
        checks = [
            ("channel_name", adapter.channel_name == 'whatsapp'),
            ("case_manager", adapter.case_manager is not None),
            ("content_manager", adapter.content_manager is not None),
            ("api_key", adapter.api_key == "TEST_API_KEY"),
            ("phone_number_id", adapter.phone_number_id == "123456789"),
            ("webhook_verify_token", adapter.webhook_verify_token == "TEST_VERIFY_TOKEN"),
            ("api_version", adapter.api_version is not None),
            ("base_url", "graph.facebook.com" in adapter.base_url),
        ]
        
        for name, result in checks:
            if result:
                print(f"   ✅ {name}")
            else:
                print(f"   ❌ {name}")
                all_present = False
        
        # 测试6: 测试webhook验证
        print("\n6️⃣ 测试webhook验证...")
        challenge = adapter.verify_webhook("subscribe", "TEST_VERIFY_TOKEN", "test_challenge_123")
        if challenge == "test_challenge_123":
            print("   ✅ Webhook验证成功")
        else:
            print("   ❌ Webhook验证失败")
            all_present = False
        
        # 测试失败的验证
        challenge_fail = adapter.verify_webhook("subscribe", "WRONG_TOKEN", "test")
        if challenge_fail is None:
            print("   ✅ 错误token被正确拒绝")
        else:
            print("   ❌ 错误token未被拒绝")
            all_present = False
        
    except Exception as e:
        print(f"   ❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 总结
    print("\n" + "=" * 60)
    if all_present:
        print("🎉 所有测试通过！")
        print("\n📊 WhatsApp适配器信息:")
        print(f"   - 类名: WhatsAppAdapter")
        print(f"   - 基类: BaseChannelAdapter")
        print(f"   - 方法数量: {len(required_methods)}")
        print(f"   - 渠道类型: whatsapp")
        print(f"   - API版本: {adapter.api_version}")
        
        print("\n✅ 适配器功能:")
        print("   - 命令处理: start, help, mycases, newcase")
        print("   - 消息类型: 文本, 图片, 文档")
        print("   - Webhook: GET验证, POST接收")
        print("   - 核心集成: CaseManager, ContentManager")
        
        print("\n💡 下一步:")
        print("   1. 设置环境变量:")
        print("      WHATSAPP_API_KEY=your_api_key")
        print("      WHATSAPP_PHONE_NUMBER_ID=your_phone_id")
        print("      WHATSAPP_WEBHOOK_VERIFY_TOKEN=your_token")
        print("   2. 在Meta Developer配置webhook URL")
        print("   3. 集成到web_controller启动webhook服务")
        print("   4. 在WhatsApp测试消息")
        
        print("\n📋 文件清单:")
        print("   ✅ adapters/whatsapp_adapter.py (585行)")
        print("   ✅ web_controller/whatsapp_webhook.py")
        print("   ✅ test_whatsapp_adapter.py (本文件)")
        
        return True
    else:
        print("❌ 部分测试失败")
        return False


def main():
    """主函数"""
    try:
        success = test_whatsapp_adapter()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
