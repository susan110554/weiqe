# 🏗️ 多渠道统一架构改造计划

## 📋 **改造概览**

### **目标架构**
```
统一Web控制器
├── Telegram Bot (现有)
├── WhatsApp Bot (新增)
├── Web管理界面 (新增)
└── 共享业务核心
```

## 🔧 **核心改造项目**

### **1. 业务逻辑抽象化**

#### **当前问题**
- 业务逻辑与Telegram Bot紧耦合
- 消息处理、状态管理、PDF生成都在bot.py中
- 无法复用给其他渠道

#### **改造方案**
```python
# 新建 core/ 目录结构
core/
├── __init__.py
├── business_logic.py      # 核心业务逻辑
├── case_manager.py        # 案件管理
├── signature_service.py   # 数字签名服务
├── pdf_service.py         # PDF生成服务
├── content_manager.py     # 内容管理
├── workflow_engine.py     # 工作流引擎
└── notification_service.py # 通知服务
```

### **2. 渠道适配器模式**

#### **设计模式**
```python
# adapters/base_adapter.py
class BaseChannelAdapter:
    async def send_message(self, user_id: str, content: dict) -> bool
    async def send_document(self, user_id: str, file_data: bytes) -> bool
    async def get_user_info(self, user_id: str) -> dict
    async def handle_callback(self, callback_data: str) -> None

# adapters/telegram_adapter.py
class TelegramAdapter(BaseChannelAdapter):
    # 现有bot.py逻辑迁移到这里

# adapters/whatsapp_adapter.py  
class WhatsAppAdapter(BaseChannelAdapter):
    # WhatsApp API集成

# adapters/web_adapter.py
class WebAdapter(BaseChannelAdapter):
    # Web界面交互逻辑
```

### **3. 内容管理系统**

#### **数据库扩展**
```sql
-- 内容模板表
CREATE TABLE content_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_key VARCHAR(100) UNIQUE NOT NULL,
    channel_type VARCHAR(20) NOT NULL, -- 'telegram', 'whatsapp', 'web'
    content_type VARCHAR(20) NOT NULL, -- 'text', 'image', 'document'
    title VARCHAR(200),
    content TEXT NOT NULL,
    variables JSONB, -- 模板变量定义
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- PDF模板表
CREATE TABLE pdf_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_name VARCHAR(100) UNIQUE NOT NULL,
    template_type VARCHAR(50) NOT NULL, -- 'case_report', 'certificate', 'receipt'
    template_data JSONB NOT NULL, -- PDF模板配置
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 渠道配置表
CREATE TABLE channel_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_type VARCHAR(20) NOT NULL,
    config_key VARCHAR(100) NOT NULL,
    config_value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(channel_type, config_key)
);
```

## 🔄 **具体改造步骤**

### **阶段1: 业务逻辑抽离 (1-2周)**

#### **1.1 创建核心业务服务**
```python
# core/case_manager.py
class CaseManager:
    def __init__(self, db_pool, content_manager):
        self.db = db_pool
        self.content = content_manager
    
    async def create_case(self, user_data: dict, channel: str) -> str:
        """创建案件 - 渠道无关"""
        case_id = await self._generate_case_id()
        
        # 验证数据
        if not self._validate_case_data(user_data):
            raise ValueError("Invalid case data")
        
        # 保存到数据库
        await self.db.create_case({
            **user_data,
            "case_no": case_id,
            "channel": channel,
            "created_at": datetime.utcnow()
        })
        
        return case_id
    
    async def get_case_status_message(self, case_id: str, channel: str) -> dict:
        """获取案件状态消息 - 支持多渠道"""
        case = await self.db.get_case_by_no(case_id)
        template_key = f"case_status_{case['status'].lower()}"
        
        return await self.content.render_template(
            template_key, 
            channel, 
            case
        )
```

#### **1.2 内容管理服务**
```python
# core/content_manager.py
class ContentManager:
    def __init__(self, db_pool):
        self.db = db_pool
        self._cache = {}
    
    async def render_template(self, template_key: str, channel: str, variables: dict) -> dict:
        """渲染模板内容"""
        template = await self._get_template(template_key, channel)
        
        if not template:
            # 降级到默认模板
            template = await self._get_template(template_key, 'default')
        
        content = self._render_variables(template['content'], variables)
        
        return {
            'content_type': template['content_type'],
            'title': template.get('title'),
            'content': content,
            'variables': variables
        }
    
    async def update_template(self, template_key: str, channel: str, content: str) -> bool:
        """更新模板内容"""
        return await self.db.execute("""
            INSERT INTO content_templates (template_key, channel_type, content_type, content)
            VALUES ($1, $2, 'text', $3)
            ON CONFLICT (template_key, channel_type) 
            DO UPDATE SET content = $3, updated_at = NOW()
        """, template_key, channel, content)
```

### **阶段2: 渠道适配器实现 (2-3周)**

#### **2.1 Telegram适配器重构**
```python
# adapters/telegram_adapter.py
class TelegramAdapter(BaseChannelAdapter):
    def __init__(self, token: str, case_manager: CaseManager):
        self.bot = Bot(token)
        self.case_manager = case_manager
        self.app = Application.builder().token(token).build()
        self._setup_handlers()
    
    async def send_message(self, user_id: str, content: dict) -> bool:
        """发送消息 - 统一接口"""
        try:
            if content['content_type'] == 'text':
                await self.bot.send_message(
                    chat_id=int(user_id),
                    text=content['content'],
                    parse_mode='HTML'
                )
            elif content['content_type'] == 'document':
                await self.bot.send_document(
                    chat_id=int(user_id),
                    document=content['file_data'],
                    caption=content.get('caption', '')
                )
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False
    
    def _setup_handlers(self):
        """设置处理器 - 调用核心业务逻辑"""
        self.app.add_handler(CommandHandler("start", self._handle_start))
        self.app.add_handler(MessageHandler(filters.TEXT, self._handle_text))
        self.app.add_handler(CallbackQueryHandler(self._handle_callback))
    
    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """开始命令 - 调用业务逻辑"""
        user_id = str(update.effective_user.id)
        welcome_content = await self.case_manager.content.render_template(
            'welcome_message', 
            'telegram', 
            {'user_name': update.effective_user.first_name}
        )
        await self.send_message(user_id, welcome_content)
```

#### **2.2 WhatsApp适配器**
```python
# adapters/whatsapp_adapter.py
class WhatsAppAdapter(BaseChannelAdapter):
    def __init__(self, api_key: str, case_manager: CaseManager):
        self.api_key = api_key
        self.case_manager = case_manager
        self.webhook_url = "/webhook/whatsapp"
    
    async def send_message(self, user_id: str, content: dict) -> bool:
        """WhatsApp消息发送"""
        url = f"https://graph.facebook.com/v17.0/{self.phone_number_id}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "to": user_id,
            "type": "text",
            "text": {"body": content['content']}
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                return resp.status == 200
    
    async def handle_webhook(self, request_data: dict):
        """处理WhatsApp webhook"""
        for entry in request_data.get('entry', []):
            for change in entry.get('changes', []):
                if change.get('field') == 'messages':
                    await self._process_message(change['value'])
    
    async def _process_message(self, message_data: dict):
        """处理消息 - 调用业务逻辑"""
        for message in message_data.get('messages', []):
            user_id = message['from']
            text = message.get('text', {}).get('body', '')
            
            # 调用统一的消息处理逻辑
            response = await self.case_manager.process_user_input(
                user_id=user_id,
                channel='whatsapp',
                message_type='text',
                content=text
            )
            
            if response:
                await self.send_message(user_id, response)
```

### **阶段3: Web控制器开发 (3-4周)**

#### **3.1 FastAPI Web控制器**
```python
# web_controller/main.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="IC3 Multi-Channel Controller")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 内容管理API
@app.get("/api/templates")
async def get_templates(channel: str = None):
    """获取内容模板列表"""
    return await content_manager.get_templates(channel)

@app.put("/api/templates/{template_key}")
async def update_template(
    template_key: str, 
    channel: str,
    content: str,
    admin_token: str = Depends(verify_admin_token)
):
    """更新模板内容"""
    success = await content_manager.update_template(template_key, channel, content)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to update template")
    
    # 通知所有渠道刷新缓存
    await notify_channels_refresh(template_key)
    
    return {"status": "success"}

# PDF管理API
@app.get("/api/pdf-templates")
async def get_pdf_templates():
    """获取PDF模板列表"""
    return await pdf_service.get_templates()

@app.post("/api/pdf-templates")
async def create_pdf_template(template_data: dict):
    """创建PDF模板"""
    return await pdf_service.create_template(template_data)

@app.put("/api/pdf-templates/{template_id}")
async def update_pdf_template(template_id: str, template_data: dict):
    """更新PDF模板"""
    return await pdf_service.update_template(template_id, template_data)

# 案件管理API
@app.get("/api/cases")
async def get_cases(
    page: int = 1, 
    limit: int = 20,
    status: str = None,
    channel: str = None
):
    """获取案件列表"""
    return await case_manager.get_cases_paginated(page, limit, status, channel)

@app.get("/api/cases/{case_id}")
async def get_case_detail(case_id: str):
    """获取案件详情"""
    case = await case_manager.get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case

@app.put("/api/cases/{case_id}/status")
async def update_case_status(
    case_id: str, 
    new_status: str, 
    admin_notes: str = None
):
    """更新案件状态"""
    success = await case_manager.update_case_status(case_id, new_status, admin_notes)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to update case status")
    
    # 通知用户状态变更
    await notification_service.notify_case_status_change(case_id, new_status)
    
    return {"status": "success"}

# 渠道配置API
@app.get("/api/channels/config")
async def get_channel_configs():
    """获取渠道配置"""
    return await config_manager.get_all_configs()

@app.put("/api/channels/{channel_type}/config")
async def update_channel_config(
    channel_type: str, 
    configs: dict,
    admin_token: str = Depends(verify_admin_token)
):
    """更新渠道配置"""
    for key, value in configs.items():
        await config_manager.set_config(channel_type, key, value)
    
    # 重启对应渠道服务
    await restart_channel_service(channel_type)
    
    return {"status": "success"}
```

#### **3.2 Web管理界面**
```typescript
// frontend/src/components/ContentManager.tsx
import React, { useState, useEffect } from 'react';
import { Card, Button, Input, Select, message } from 'antd';

const ContentManager: React.FC = () => {
    const [templates, setTemplates] = useState([]);
    const [selectedTemplate, setSelectedTemplate] = useState(null);
    const [content, setContent] = useState('');
    const [channel, setChannel] = useState('telegram');

    const updateTemplate = async () => {
        try {
            await fetch(`/api/templates/${selectedTemplate.key}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ channel, content })
            });
            message.success('模板更新成功');
        } catch (error) {
            message.error('更新失败');
        }
    };

    return (
        <Card title="内容管理">
            <Select 
                value={channel} 
                onChange={setChannel}
                style={{ width: 200, marginBottom: 16 }}
            >
                <Select.Option value="telegram">Telegram</Select.Option>
                <Select.Option value="whatsapp">WhatsApp</Select.Option>
                <Select.Option value="web">Web</Select.Option>
            </Select>
            
            <Input.TextArea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                rows={10}
                placeholder="输入模板内容..."
            />
            
            <Button 
                type="primary" 
                onClick={updateTemplate}
                style={{ marginTop: 16 }}
            >
                更新模板
            </Button>
        </Card>
    );
};
```

## 🔄 **现有Bot改造清单**

### **必须修改的文件**

#### **1. bot.py 重构**
```python
# 原有的 bot.py (9861行) 需要拆分为:
bot.py                    # 保留启动逻辑 (约500行)
adapters/telegram_adapter.py  # Telegram特定逻辑 (约3000行)
core/business_logic.py    # 核心业务逻辑 (约2000行)
core/case_manager.py      # 案件管理 (约1500行)
core/signature_service.py # 签名服务 (约800行)
core/pdf_service.py       # PDF服务 (约1000行)
```

#### **2. 数据库迁移脚本**
```sql
-- migration_001_multi_channel.sql
-- 添加渠道支持
ALTER TABLE cases ADD COLUMN channel VARCHAR(20) DEFAULT 'telegram';
ALTER TABLE cases ADD COLUMN channel_user_id VARCHAR(100);

-- 更新现有数据
UPDATE cases SET 
    channel = 'telegram',
    channel_user_id = CAST(tg_user_id AS VARCHAR);

-- 创建新表
CREATE TABLE content_templates (...);
CREATE TABLE pdf_templates (...);
CREATE TABLE channel_configs (...);
```

#### **3. 配置文件调整**
```python
# config/multi_channel_config.py
class MultiChannelConfig:
    # Telegram配置
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    
    # WhatsApp配置  
    WHATSAPP_API_KEY = os.getenv("WHATSAPP_API_KEY")
    WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    
    # Web配置
    WEB_SECRET_KEY = os.getenv("WEB_SECRET_KEY")
    WEB_ADMIN_TOKEN = os.getenv("WEB_ADMIN_TOKEN")
    
    # 共享配置
    DATABASE_URL = os.getenv("DATABASE_URL")
    REDIS_URL = os.getenv("REDIS_URL")
    SIGNATURE_SECRET_KEY = os.getenv("SIGNATURE_SECRET_KEY")
```

## 📊 **改造优先级**

### **高优先级 (必须)**
1. ✅ **业务逻辑抽离** - 创建core模块
2. ✅ **数据库扩展** - 添加多渠道支持表
3. ✅ **内容管理系统** - 可编辑模板
4. ✅ **Web控制器API** - 管理接口

### **中优先级 (重要)**
1. 🔄 **Telegram适配器重构** - 现有功能迁移
2. 🔄 **WhatsApp适配器开发** - 新渠道支持
3. 🔄 **PDF模板系统** - 可视化编辑
4. 🔄 **Web管理界面** - 用户友好界面

### **低优先级 (可选)**
1. ⏳ **实时通知系统** - WebSocket支持
2. ⏳ **多语言支持** - i18n国际化
3. ⏳ **高级分析** - 数据统计面板
4. ⏳ **API限流** - 安全防护

## 🎯 **预期收益**

### **技术收益**
- 🔧 **代码复用率**: 提升80%以上
- 🚀 **开发效率**: 新渠道开发时间减少70%
- 🛡️ **维护成本**: 统一业务逻辑，降低50%维护成本
- 📈 **扩展性**: 支持无限渠道扩展

### **业务收益**
- 📱 **多渠道覆盖**: Telegram + WhatsApp + Web
- ⚡ **实时管理**: Web界面随时修改内容
- 📊 **统一数据**: 所有渠道数据集中管理
- 🎨 **灵活定制**: PDF和内容模板可视化编辑

这个改造方案将现有的单一Telegram Bot升级为支持多渠道的统一平台，同时保持现有功能的完整性。
