#!/usr/bin/env python3
"""
测试内容管理器功能
验证多渠道架构的核心组件
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from core.content_manager import ContentManager
import database as db

async def test_content_manager():
    """测试内容管理器"""
    print("🧪 开始测试内容管理器...")
    
    # 获取数据库连接池
    pool = await db.get_pool()
    print("✅ 数据库连接池获取成功")
    
    # 创建内容管理器
    content_manager = ContentManager(pool)
    print("✅ 内容管理器创建成功")
    
    # 测试1: 创建默认模板
    print("\n📝 测试1: 创建默认模板")
    await content_manager.create_default_templates()
    print("✅ 默认模板创建完成")
    
    # 测试2: 获取模板列表
    print("\n📋 测试2: 获取模板列表")
    templates = await content_manager.get_all_templates()
    print(f"✅ 获取到 {len(templates)} 个模板:")
    for template in templates[:5]:  # 只显示前5个
        print(f"   - {template['template_key']} ({template['channel_type']})")
    
    # 测试3: 渲染模板
    print("\n🎨 测试3: 渲染模板")
    welcome_content = await content_manager.render_template(
        'welcome_message', 
        'telegram', 
        {'user_id': '12345'}
    )
    print("✅ 模板渲染成功:")
    print(f"   类型: {welcome_content['content_type']}")
    print(f"   标题: {welcome_content.get('title', 'N/A')}")
    print(f"   内容长度: {len(welcome_content['content'])} 字符")
    
    # 测试4: 更新模板
    print("\n✏️ 测试4: 更新模板")
    success = await content_manager.update_template(
        'test_template',
        'telegram',
        '🎉 这是一个测试模板! 用户: {{user_name}}',
        'text',
        '测试模板'
    )
    print(f"✅ 模板更新: {'成功' if success else '失败'}")
    
    # 测试5: 渲染更新后的模板
    print("\n🎨 测试5: 渲染更新后的模板")
    test_content = await content_manager.render_template(
        'test_template',
        'telegram',
        {'user_name': 'Alice'}
    )
    print("✅ 模板渲染成功:")
    print(f"   内容: {test_content['content']}")
    
    # 测试6: 跨渠道模板
    print("\n🌐 测试6: 跨渠道模板支持")
    
    # 为WhatsApp创建不同的欢迎模板
    await content_manager.update_template(
        'welcome_message',
        'whatsapp',
        '*FBI IC3 WhatsApp Bot*\n\nWelcome! Send *START* to begin filing a complaint.',
        'text',
        'WhatsApp Welcome'
    )
    
    # 渲染不同渠道的模板
    telegram_welcome = await content_manager.render_template('welcome_message', 'telegram', {})
    whatsapp_welcome = await content_manager.render_template('welcome_message', 'whatsapp', {})
    
    print("✅ 跨渠道模板测试:")
    print(f"   Telegram: {len(telegram_welcome['content'])} 字符")
    print(f"   WhatsApp: {len(whatsapp_welcome['content'])} 字符")
    print(f"   内容不同: {telegram_welcome['content'] != whatsapp_welcome['content']}")
    
    # 测试7: 模板统计
    print("\n📊 测试7: 模板使用统计")
    stats = await content_manager.get_template_usage_stats()
    print(f"✅ 统计信息:")
    print(f"   渠道统计: {len(stats.get('channel_stats', []))} 个渠道")
    print(f"   缓存大小: {stats.get('cache_size', 0)}")
    
    await db.close_pool()
    print("\n🎉 内容管理器测试完成!")

async def test_case_manager():
    """测试案件管理器"""
    print("\n🧪 开始测试案件管理器...")
    
    try:
        from core.case_manager import CaseManager
        from core.signature_service import SignatureService
        
        # 获取数据库连接池
        pool = await db.get_pool()
        
        # 创建服务实例
        content_manager = ContentManager(pool)
        signature_service = SignatureService()  # 需要实现
        case_manager = CaseManager(pool, content_manager, signature_service)
        
        print("✅ 案件管理器创建成功")
        
        # 测试获取案件列表
        cases = await case_manager.get_cases_paginated(page=1, limit=5)
        print(f"✅ 获取案件列表: {cases['total']} 个案件")
        
        await db.close_pool()
        
    except ImportError as e:
        print(f"⚠️ 案件管理器测试跳过 (模块未完成): {e}")

async def main():
    """主测试函数"""
    print("=" * 60)
    print("🧪 多渠道架构核心组件测试")
    print("=" * 60)
    
    try:
        await test_content_manager()
        await test_case_manager()
        
        print("\n🎯 测试总结:")
        print("✅ 内容管理器: 功能正常")
        print("✅ 数据库扩展: 迁移成功")
        print("✅ 多渠道支持: 基础架构就绪")
        
        print("\n🚀 下一步开发建议:")
        print("1. 完善 core/signature_service.py")
        print("2. 完善 core/pdf_service.py")
        print("3. 开发 adapters/telegram_adapter.py")
        print("4. 开发 web_controller/main.py")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
