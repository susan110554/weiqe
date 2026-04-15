# ⚡ 快速上手指南

## 🎯 **30分钟快速开始**

### **第1步: 验证环境 (5分钟)**
```bash
# 切换到项目目录
cd c:\Users\Administrator\Desktop\weiqe

# 运行测试
python test_simple.py

# 预期结果
✅ 文件结构完整 (7个文件)
✅ 模块导入成功
✅ JWT认证功能正常
✅ 所有基本功能测试通过
```

### **第2步: 启动Web控制器 (5分钟)**
```bash
# 启动服务
uvicorn web_controller.main_fixed:app --reload --port 8000

# 或使用启动脚本
start_web_controller.bat

# 预期输出
INFO: Application startup complete.
INFO: Uvicorn running on http://127.0.0.1:8000
```

### **第3步: 访问API文档 (10分钟)**
```
1. 打开浏览器
2. 访问: http://localhost:8000/docs
3. 查看17个API端点
4. 点击 "Authorize" 按钮
5. 输入管理员令牌 (默认: admin-token)
6. 测试API端点
```

### **第4步: 熟悉核心服务 (10分钟)**
```python
# 查看核心服务代码
core/case_manager.py       # 案件管理
core/content_manager.py    # 内容管理
core/signature_service.py  # 数字签名

# 理解调用方式
from core import CaseManager, ContentManager

# 案件管理示例
cases = await case_manager.get_cases_paginated(page=1, limit=20)

# 模板管理示例
content = await content_manager.render_template(
    "welcome_message", "telegram", {"user_name": "Alice"}
)
```

---

## 📋 **关键文件速查**

### **必读文档 (按优先级)**
1. ⭐⭐⭐ `FINAL_HANDOVER_PACKAGE.md` - **完整交接包**
2. ⭐⭐⭐ `PROJECT_STATUS.md` - **项目状态**
3. ⭐⭐ `web_controller/README.md` - **Web API使用**
4. ⭐⭐ `REFACTOR_IMPLEMENTATION_GUIDE.md` - **实施指南**
5. ⭐ `ARCHITECTURE_REFACTOR_PLAN.md` - **架构设计**

### **核心代码位置**
```
核心业务:  core/
Web控制器: web_controller/
适配器:    adapters/
测试:      test_*.py
文档:      *.md
```

---

## 🎯 **待开发任务卡片**

### **任务1: Telegram适配器** ⏰ 5-7天 🔴 高优先级
```
📍 位置: adapters/telegram_adapter.py
📚 参考: bot.py, adapters/base_adapter.py
🎯 目标: 重构现有bot.py为适配器模式
✅ 标准: 保持所有功能,调用核心服务
```

### **任务2: WhatsApp适配器** ⏰ 7-10天 🔴 高优先级
```
📍 位置: adapters/whatsapp_adapter.py
📚 参考: adapters/base_adapter.py
🎯 目标: 基于WhatsApp Business API开发
✅ 标准: 支持基本案件创建流程
```

### **任务3: Web前端** ⏰ 10-12天 🟡 中优先级
```
📍 位置: frontend/
📚 参考: web_controller/README.md
🎯 目标: React + Ant Design管理界面
✅ 标准: 模板编辑+案件管理
```

---

## 💡 **常见问题速答**

### **Q1: Web控制器启动失败怎么办?**
```bash
# 使用Windows优化版
uvicorn web_controller.main_fixed:app --reload --port 8000

# 如果还有问题,检查数据库连接
python test_simple.py
```

### **Q2: 如何调用核心服务?**
```python
# 所有核心服务在 core/ 目录
from core import CaseManager, ContentManager, SignatureService

# 使用示例见各个py文件的docstring
```

### **Q3: 如何测试API?**
```
1. 启动Web控制器
2. 访问 http://localhost:8000/docs
3. 使用Swagger UI测试
```

### **Q4: 数据库表结构在哪?**
```sql
# 迁移脚本
migrations/001_multi_channel_support_fixed.sql

# 包含35个表的完整结构
```

### **Q5: 如何实现新的适配器?**
```python
# 1. 继承基类
from adapters.base_adapter import BaseChannelAdapter

# 2. 实现必需方法
class MyAdapter(BaseChannelAdapter):
    async def send_message(self, user_id, content): ...
    async def handle_message(self, message_data): ...
    # ... 其他必需方法

# 3. 参考 adapters/base_adapter.py
```

---

## 🔑 **关键代码片段**

### **案件管理**
```python
from core.case_manager import CaseManager

# 获取案件列表
cases = await case_manager.get_cases_paginated(
    page=1, 
    limit=20, 
    status='待初步审核',
    channel='telegram'
)

# 获取案件详情
case = await case_manager.get_case_by_id('IC3-2026-123456')

# 更新状态
success = await case_manager.update_case_status(
    'IC3-2026-123456', 
    '审核中', 
    'Admin review completed'
)
```

### **内容管理**
```python
from core.content_manager import ContentManager

# 创建/更新模板
await content_manager.update_template(
    template_key='welcome_telegram',
    channel='telegram',
    content='Welcome {{user_name}}!',
    content_type='text',
    title='Telegram Welcome'
)

# 渲染模板
content = await content_manager.render_template(
    'welcome_telegram',
    'telegram',
    {'user_name': 'Alice'}
)

# 结果: 'Welcome Alice!'
```

### **数字签名**
```python
from core.signature_service import SignatureService

sig_service = SignatureService()

# 生成签名
signature = sig_service.generate_signature(
    case_data={'case_no': 'IC3-001', 'amount': '1000'},
    user_id='12345'
)

# 验证签名
is_valid = sig_service.verify_signature(
    signature, case_data, user_id
)
```

---

## 🚦 **开发流程**

### **Day 1: 熟悉**
```
□ 阅读 FINAL_HANDOVER_PACKAGE.md
□ 运行所有测试脚本
□ 启动Web控制器并测试
□ 浏览核心代码
```

### **Day 2-3: Telegram分析**
```
□ 分析 bot.py 结构
□ 识别所有handlers
□ 规划迁移策略
□ 创建适配器文件
```

### **Day 4-7: Telegram开发**
```
□ 迁移handlers
□ 集成核心服务
□ 替换模板系统
□ 测试所有功能
```

### **Week 2: WhatsApp**
```
□ 注册WhatsApp Business API
□ 实现webhook
□ 开发适配器
□ 集成测试
```

### **Week 3-4: Web前端**
```
□ 搭建React项目
□ 实现登录认证
□ 开发管理界面
□ 集成API
```

---

## 📞 **获取帮助**

### **文档查询**
```
架构设计:    ARCHITECTURE_REFACTOR_PLAN.md
实施步骤:    REFACTOR_IMPLEMENTATION_GUIDE.md
API使用:     web_controller/README.md
项目状态:    PROJECT_STATUS.md
完整交接:    FINAL_HANDOVER_PACKAGE.md
```

### **代码示例**
```
核心服务:    core/*.py
适配器:      adapters/base_adapter.py
Web API:     web_controller/*.py
测试:        test_*.py
```

### **在线资源**
```
FastAPI文档: https://fastapi.tiangolo.com/
WhatsApp API: https://developers.facebook.com/docs/whatsapp
React文档:    https://react.dev/
```

---

## ✅ **检查清单**

### **开发前**
- [ ] 所有测试通过
- [ ] Web控制器可以启动
- [ ] 理解核心服务用法
- [ ] 熟悉适配器基类
- [ ] 环境变量已配置

### **开发中**
- [ ] 遵循适配器模式
- [ ] 复用核心业务逻辑
- [ ] 使用模板系统
- [ ] 编写单元测试
- [ ] 保持代码风格一致

### **开发后**
- [ ] 所有功能测试通过
- [ ] 集成测试通过
- [ ] 代码已审查
- [ ] 文档已更新
- [ ] 部署就绪

---

**快速上手指南 v1.0**  
**最后更新**: 2026-04-15  
**适用于**: FBI IC3 多渠道架构开发

🚀 **开始你的开发之旅吧！** 🚀
