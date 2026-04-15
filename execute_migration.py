#!/usr/bin/env python3
"""
多渠道架构数据库迁移执行脚本
通过Python执行SQL迁移，避免PostgreSQL路径问题
"""
import asyncio
import asyncpg
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

async def execute_migration():
    """执行数据库迁移"""
    print("🚀 开始执行多渠道架构数据库迁移...")
    
    # 读取迁移文件
    migration_file = Path("migrations/001_multi_channel_support_fixed.sql")
    if not migration_file.exists():
        print(f"❌ 错误: 迁移文件不存在: {migration_file}")
        return False
    
    print(f"📄 读取迁移文件: {migration_file}")
    migration_sql = migration_file.read_text(encoding='utf-8')
    
    # 数据库连接参数
    db_config = {
        'host': os.getenv("DB_HOST", "localhost"),
        'port': int(os.getenv("DB_PORT", 5432)),
        'database': os.getenv("DB_NAME", "weiquan_bot"),
        'user': os.getenv("DB_USER", "postgres"),
        'password': os.getenv("DB_PASSWORD", ""),
    }
    
    print(f"🗄️ 连接数据库: {db_config['database']}@{db_config['host']}:{db_config['port']}")
    
    try:
        # 创建数据库连接
        conn = await asyncpg.connect(**db_config)
        print("✅ 数据库连接成功")
        
        # 获取迁移前的表数量
        tables_before = await conn.fetchval("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        print(f"📊 迁移前表数量: {tables_before}")
        
        # 执行迁移SQL
        print("⏳ 执行迁移脚本...")
        await conn.execute(migration_sql)
        print("✅ 迁移脚本执行完成")
        
        # 获取迁移后的表数量
        tables_after = await conn.fetchval("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        print(f"📊 迁移后表数量: {tables_after}")
        print(f"📈 新增表数量: {tables_after - tables_before}")
        
        # 验证新增的表
        print("\n🔍 验证新增的表...")
        new_tables = await conn.fetch("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN (
                'content_templates', 'pdf_templates', 'channel_configs', 
                'notification_rules', 'message_logs', 'user_sessions', 'system_configs'
            )
            ORDER BY table_name
        """)
        
        if new_tables:
            print("✅ 成功创建以下新表:")
            for table in new_tables:
                print(f"   - {table['table_name']}")
        else:
            print("⚠️ 未检测到新表，可能迁移未完全成功")
        
        # 验证现有表的扩展
        print("\n🔍 验证现有表的扩展...")
        cases_columns = await conn.fetch("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = 'cases'
            AND column_name IN ('channel', 'channel_user_id')
            ORDER BY column_name
        """)
        
        if cases_columns:
            print("✅ cases表成功添加新列:")
            for col in cases_columns:
                print(f"   - {col['column_name']}")
        else:
            print("⚠️ cases表可能未正确扩展")
        
        # 检查默认数据
        print("\n🔍 检查默认配置数据...")
        config_count = await conn.fetchval("SELECT COUNT(*) FROM channel_configs")
        system_config_count = await conn.fetchval("SELECT COUNT(*) FROM system_configs")
        notification_rules_count = await conn.fetchval("SELECT COUNT(*) FROM notification_rules")
        
        print(f"✅ 渠道配置数量: {config_count}")
        print(f"✅ 系统配置数量: {system_config_count}")
        print(f"✅ 通知规则数量: {notification_rules_count}")
        
        # 关闭连接
        await conn.close()
        print("\n🎉 多渠道架构迁移完成!")
        print("📋 迁移总结:")
        print(f"   - 新增表: {len(new_tables) if new_tables else 0} 个")
        print(f"   - 扩展表: cases (添加渠道支持)")
        print(f"   - 默认配置: {config_count + system_config_count + notification_rules_count} 条")
        
        return True
        
    except asyncpg.exceptions.PostgresError as e:
        print(f"❌ 数据库错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 执行错误: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_migration():
    """测试迁移结果"""
    print("\n🧪 测试迁移结果...")
    
    db_config = {
        'host': os.getenv("DB_HOST", "localhost"),
        'port': int(os.getenv("DB_PORT", 5432)),
        'database': os.getenv("DB_NAME", "weiquan_bot"),
        'user': os.getenv("DB_USER", "postgres"),
        'password': os.getenv("DB_PASSWORD", ""),
    }
    
    try:
        conn = await asyncpg.connect(**db_config)
        
        # 测试插入内容模板
        await conn.execute("""
            INSERT INTO content_templates (template_key, channel_type, content_type, content)
            VALUES ('test_template', 'telegram', 'text', 'Hello {{user_name}}!')
            ON CONFLICT (template_key, channel_type) DO NOTHING
        """)
        
        # 测试查询
        template = await conn.fetchrow("""
            SELECT * FROM content_templates 
            WHERE template_key = 'test_template' AND channel_type = 'telegram'
        """)
        
        if template:
            print("✅ 内容模板表测试通过")
        else:
            print("⚠️ 内容模板表测试失败")
        
        # 测试cases表扩展
        await conn.execute("""
            UPDATE cases SET channel = 'telegram', channel_user_id = CAST(tg_user_id AS VARCHAR)
            WHERE channel IS NULL AND tg_user_id IS NOT NULL
        """)
        
        updated_count = await conn.fetchval("""
            SELECT COUNT(*) FROM cases WHERE channel = 'telegram'
        """)
        print(f"✅ cases表渠道标记: {updated_count} 条记录")
        
        await conn.close()
        print("🎯 迁移测试完成!")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")

async def main():
    """主函数"""
    print("=" * 60)
    print("🏗️ FBI IC3 多渠道架构数据库迁移")
    print("=" * 60)
    
    success = await execute_migration()
    
    if success:
        await test_migration()
        print("\n🚀 下一步:")
        print("1. 开始核心业务逻辑抽离")
        print("2. 创建渠道适配器")
        print("3. 开发Web控制器")
        print("\n📖 详细步骤请参考: REFACTOR_IMPLEMENTATION_GUIDE.md")
    else:
        print("\n❌ 迁移失败，请检查错误信息并重试")
    
    return success

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 未知错误: {e}")
        sys.exit(1)
