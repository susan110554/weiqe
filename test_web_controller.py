#!/usr/bin/env python3
"""
测试Web控制器集成
验证所有核心功能是否正常工作
"""
import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

async def test_web_controller_setup():
    """测试Web控制器设置"""
    print("🧪 测试Web控制器集成...")
    
    # 测试1: 检查文件结构
    print("\n1️⃣ 检查文件结构...")
    required_files = [
        "web_controller/__init__.py",
        "web_controller/main.py",
        "web_controller/auth.py",
        "web_controller/models.py",
        "web_controller/utils.py",
        "web_controller/requirements.txt",
        "web_controller/README.md"
    ]
    
    missing_files = []
    for file_path in required_files:
        full_path = Path(file_path)
        if full_path.exists():
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path} (缺失)")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n⚠️  缺少 {len(missing_files)} 个文件!")
        return False
    
    # 测试2: 导入核心模块
    print("\n2️⃣ 测试模块导入...")
    try:
        from web_controller import auth, models, utils
        print("   ✅ web_controller.auth")
        print("   ✅ web_controller.models")
        print("   ✅ web_controller.utils")
    except ImportError as e:
        print(f"   ❌ 导入失败: {e}")
        return False
    
    # 测试3: 检查环境变量
    print("\n3️⃣ 检查环境变量...")
    env_vars = {
        "DB_HOST": os.getenv("DB_HOST", "localhost"),
        "DB_NAME": os.getenv("DB_NAME", "weiquan_bot"),
        "WEB_SECRET_KEY": os.getenv("WEB_SECRET_KEY", "未设置"),
        "WEB_ADMIN_TOKEN": os.getenv("WEB_ADMIN_TOKEN", "未设置"),
    }
    
    for key, value in env_vars.items():
        if value == "未设置":
            print(f"   ⚠️  {key}: {value} (建议设置)")
        else:
            masked_value = value[:10] + "..." if len(value) > 10 else value
            print(f"   ✅ {key}: {masked_value}")
    
    # 测试4: 测试认证功能
    print("\n4️⃣ 测试认证功能...")
    try:
        from web_controller.auth import create_access_token, decode_access_token
        
        # 创建测试token
        test_token = create_access_token({"sub": "test_user", "role": "admin"})
        print(f"   ✅ Token生成成功: {test_token[:30]}...")
        
        # 解码token
        payload = decode_access_token(test_token)
        print(f"   ✅ Token解码成功: sub={payload['sub']}, role={payload['role']}")
        
    except Exception as e:
        print(f"   ❌ 认证测试失败: {e}")
        return False
    
    # 测试5: 测试工具函数
    print("\n5️⃣ 测试工具函数...")
    try:
        from web_controller.utils import paginate, serialize_row
        
        # 测试分页
        page_info = paginate(total=100, page=2, limit=20)
        print(f"   ✅ 分页功能: {page_info['total_pages']} 页")
        
        # 测试序列化 (模拟数据库行)
        from datetime import datetime
        mock_row = {
            'id': 'test-id',
            'created_at': datetime.utcnow(),
            'data': b'binary data'
        }
        serialized = serialize_row(mock_row)
        print(f"   ✅ 序列化功能: {len(serialized)} 个字段")
        
    except Exception as e:
        print(f"   ❌ 工具测试失败: {e}")
        return False
    
    # 测试6: 测试Pydantic模型
    print("\n6️⃣ 测试Pydantic模型...")
    try:
        from web_controller.models import (
            LoginRequest, TemplateCreateRequest, CaseStatusUpdateRequest
        )
        
        # 测试登录请求模型
        login_req = LoginRequest(token="test-token")
        print(f"   ✅ LoginRequest: {login_req.token[:10]}...")
        
        # 测试模板创建模型
        template_req = TemplateCreateRequest(
            template_key="test_template",
            channel="telegram",
            content="Hello {{user_name}}!",
            content_type="text"
        )
        print(f"   ✅ TemplateCreateRequest: {template_req.template_key}")
        
        # 测试案件状态更新模型
        status_req = CaseStatusUpdateRequest(
            new_status="审核中",
            admin_notes="Test note"
        )
        print(f"   ✅ CaseStatusUpdateRequest: {status_req.new_status}")
        
    except Exception as e:
        print(f"   ❌ 模型测试失败: {e}")
        return False
    
    # 测试7: 检查FastAPI依赖
    print("\n7️⃣ 检查FastAPI依赖...")
    try:
        import fastapi
        import uvicorn
        import jwt as pyjwt
        
        print(f"   ✅ FastAPI: {fastapi.__version__}")
        print(f"   ✅ Uvicorn: {uvicorn.__version__}")
        print(f"   ✅ PyJWT: {pyjwt.__version__}")
        
    except ImportError as e:
        print(f"   ⚠️  缺少依赖: {e}")
        print(f"   💡 请运行: pip install -r web_controller/requirements.txt")
        return False
    
    return True

async def test_core_services():
    """测试核心服务集成"""
    print("\n8️⃣ 测试核心服务集成...")
    try:
        from core import CaseManager, ContentManager, SignatureService
        import database as db
        
        # 获取数据库连接
        conn = await db.get_pool()
        print("   ✅ 数据库连接成功")
        
        # 测试核心服务
        content_manager = ContentManager(conn)
        signature_service = SignatureService()
        
        print("   ✅ ContentManager初始化成功")
        print("   ✅ SignatureService初始化成功")
        
        await db.close_pool()
        return True
        
    except Exception as e:
        print(f"   ⚠️  核心服务测试失败: {e}")
        print(f"   💡 确保数据库已启动并完成迁移")
        return False

async def main():
    """主测试函数"""
    print("=" * 60)
    print("🌐 IC3 Web控制器集成测试")
    print("=" * 60)
    
    # 基础设置测试
    setup_ok = await test_web_controller_setup()
    
    # 核心服务测试
    services_ok = await test_core_services()
    
    print("\n" + "=" * 60)
    if setup_ok:
        print("🎉 Web控制器设置测试通过!")
        print("\n📋 下一步:")
        print("1. 安装依赖: pip install -r web_controller/requirements.txt")
        print("2. 配置环境变量 (见web_controller/README.md)")
        print("3. 启动服务: uvicorn web_controller.main:app --reload --port 8000")
        print("4. 访问文档: http://localhost:8000/docs")
        
        if services_ok:
            print("\n✅ 核心服务集成正常!")
        else:
            print("\n⚠️  核心服务测试失败，但不影响Web控制器启动")
            print("   (启动后会在运行时连接核心服务)")
        
        return True
    else:
        print("❌ Web控制器设置测试失败")
        print("请检查上述错误并修复")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ 测试被中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
