# 🌐 IC3 Multi-Channel Admin Web Controller

FastAPI后端管理系统，为ccc多渠道欺诈报告平台提供Web管理界面。

## 📋 **功能特性**

### **1. 认证系统**
- JWT Token认证
- 基于环境变量的管理员令牌验证
- 8小时Token有效期

### **2. 内容模板管理** (17个API端点)
- ✅ 获取模板列表 (支持渠道过滤)
- ✅ 查看单个模板
- ✅ 创建新模板
- ✅ 更新模板 (自动失效缓存)
- ✅ 删除模板
- ✅ 实时预览 (变量渲染)
- ✅ 缓存刷新
- ✅ 使用统计

### **3. 案件管理**
- ✅ 分页案件列表
- ✅ 案件详情 (含证据和历史记录)
- ✅ 状态更新
- ✅ 渠道过滤

### **4. 渠道配置**
- ✅ 获取所有渠道配置
- ✅ 更新配置 (Upsert模式)

### **5. 仪表板统计**
- ✅ 案件总数统计
- ✅ 按渠道分组
- ✅ 按状态分组
- ✅ 最近5个案件

## 🚀 **快速开始**

### **1. 安装依赖**
```bash
cd web_controller
pip install -r requirements.txt
```

### **2. 配置环境变量**
在项目根目录的`.env`文件中添加：
```bash
# Web控制器配置
WEB_SECRET_KEY=your-secret-key-here
WEB_ADMIN_TOKEN=your-admin-token-here
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# 数据库配置 (已有)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=weiquan_bot
DB_USER=postgres
DB_PASSWORD=your_password
```

### **3. 启动服务**
```bash
# 方式1: 使用uvicorn直接启动
cd ..  # 回到项目根目录
uvicorn web_controller.main:app --reload --port 8000

# 方式2: 使用Python启动
python -m uvicorn web_controller.main:app --reload --port 8000

# 生产环境
uvicorn web_controller.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### **4. 访问API文档**
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## 📚 **API端点概览**

### **认证 (Auth)**
```
POST   /api/auth/login     # 登录获取JWT
GET    /api/auth/me        # 获取当前用户信息
```

### **模板管理 (Templates)**
```
GET    /api/templates                  # 获取模板列表
GET    /api/templates/{key}           # 获取单个模板
POST   /api/templates                  # 创建模板
PUT    /api/templates/{key}           # 更新模板
DELETE /api/templates/{key}           # 删除模板
POST   /api/templates/preview         # 预览模板
POST   /api/templates/cache/refresh   # 刷新缓存
GET    /api/templates/stats           # 使用统计
```

### **案件管理 (Cases)**
```
GET    /api/cases                # 分页案件列表
GET    /api/cases/{case_id}     # 案件详情
PUT    /api/cases/{case_id}/status  # 更新状态
```

### **渠道配置 (Channels)**
```
GET    /api/channels/config              # 获取所有配置
PUT    /api/channels/{type}/config       # 更新配置
```

### **仪表板 (Dashboard)**
```
GET    /api/dashboard/stats    # 统计数据
```

### **健康检查**
```
GET    /health                 # 服务状态
```

## 🔐 **认证流程**

### **1. 获取JWT Token**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"token": "your-admin-token"}'

# 响应
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "expires_in": 28800
}
```

### **2. 使用Token访问受保护端点**
```bash
curl -X GET http://localhost:8000/api/templates \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..."
```

## 💡 **使用示例**

### **创建内容模板**
```bash
curl -X POST http://localhost:8000/api/templates \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "template_key": "welcome_whatsapp",
    "channel": "whatsapp",
    "content": "Hello {{user_name}}! Welcome to IC3.",
    "content_type": "text",
    "title": "WhatsApp Welcome Message",
    "variables": {"user_name": "User full name"}
  }'
```

### **更新模板内容**
```bash
curl -X PUT http://localhost:8000/api/templates/welcome_whatsapp \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "whatsapp",
    "content": "Hi {{user_name}}! Thanks for reporting to IC3.",
    "content_type": "text"
  }'
```

### **预览模板**
```bash
curl -X POST "http://localhost:8000/api/templates/preview?template_key=welcome_whatsapp&channel=whatsapp" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_name": "Alice"}'
```

### **获取案件列表**
```bash
curl -X GET "http://localhost:8000/api/cases?page=1&limit=20&status=待初步审核" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### **更新案件状态**
```bash
curl -X PUT http://localhost:8000/api/cases/IC3-2026-123456/status \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "new_status": "审核中",
    "admin_notes": "Initial review completed, escalating to senior agent"
  }'
```

## 🏗️ **架构设计**

### **核心服务集成**
Web控制器直接调用项目核心服务：
- `CaseManager` - 案件管理
- `ContentManager` - 内容管理
- `SignatureService` - 数字签名

### **文件结构**
```
web_controller/
├── __init__.py           # 模块初始化
├── main.py               # FastAPI应用主文件 (362行)
├── auth.py               # JWT认证逻辑 (43行)
├── models.py             # Pydantic模型定义 (180行)
├── utils.py              # 工具函数 (92行)
├── requirements.txt      # Python依赖
└── README.md             # 本文档
```

### **依赖关系**
```
FastAPI App (main.py)
    ↓
Core Services (调用现有模块)
    ├── CaseManager
    ├── ContentManager
    └── SignatureService
    ↓
Database (PostgreSQL)
    └── 35个表 (28个原有 + 7个新增)
```

## 🧪 **测试**

### **健康检查**
```bash
curl http://localhost:8000/health
```

### **API文档测试**
1. 访问 http://localhost:8000/docs
2. 点击 "Authorize" 按钮
3. 输入管理员令牌
4. 测试各个端点

## 🔒 **安全注意事项**

1. **生产环境必须修改**:
   - `WEB_SECRET_KEY` - 用于JWT签名
   - `WEB_ADMIN_TOKEN` - 管理员登录令牌

2. **CORS配置**:
   - 生产环境限制`CORS_ORIGINS`为具体域名
   - 不要使用通配符`*`

3. **Token过期**:
   - 默认8小时，可通过`JWT_EXPIRE_MINUTES`环境变量调整

## 📊 **性能**

- **缓存**: ContentManager内置5分钟模板缓存
- **连接池**: 复用现有PostgreSQL连接池
- **异步**: 完全异步I/O，支持高并发

## 🐛 **故障排查**

### **常见问题**

#### **1. "Core services unavailable"**
```bash
# 检查核心模块是否正确安装
python -c "from core.case_manager import CaseManager; print('OK')"

# 检查数据库连接
python -c "import asyncio; import database as db; asyncio.run(db.get_pool())"
```

#### **2. "Invalid token"**
- 确认`WEB_ADMIN_TOKEN`环境变量已设置
- 检查JWT是否过期 (默认8小时)
- 验证Authorization header格式: `Bearer YOUR_TOKEN`

#### **3. 数据库连接错误**
- 检查`.env`中的数据库配置
- 确认PostgreSQL服务运行中
- 验证数据库迁移已执行

## 📝 **开发规范**

### **添加新端点**
```python
@app.get("/api/your-endpoint", tags=["YourCategory"])
async def your_function(_user=Depends(require_auth)):
    """端点文档说明"""
    if not SERVICES_AVAILABLE:
        raise HTTPException(503, "Core services unavailable")
    
    # 调用核心服务
    result = await _some_manager.do_something()
    return result
```

### **错误处理**
```python
try:
    result = await operation()
except Exception as e:
    logger.error(f"Operation failed: {e}")
    raise HTTPException(500, "Internal server error")
```

## 🚀 **部署**

### **Docker部署**
```dockerfile
# Dockerfile (示例)
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r web_controller/requirements.txt
CMD ["uvicorn", "web_controller.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### **Systemd服务**
```ini
# /etc/systemd/system/ic3-web.service
[Unit]
Description=IC3 Web Controller
After=network.target postgresql.service

[Service]
Type=simple
User=ic3
WorkingDirectory=/opt/ic3
Environment="PATH=/opt/ic3/venv/bin"
ExecStart=/opt/ic3/venv/bin/uvicorn web_controller.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

## 📞 **技术支持**

如有问题，请检查：
1. Swagger文档: http://localhost:8000/docs
2. 日志输出: 查看uvicorn控制台
3. 健康检查: http://localhost:8000/health

---

**版本**: 1.0.0  
**开发团队**: IC3 Development Team  
**最后更新**: 2026-04-15
