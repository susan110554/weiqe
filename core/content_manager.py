"""
内容管理服务
支持多渠道的模板内容管理，可通过Web界面实时编辑
"""
import json
import re
from typing import Dict, List, Optional
import asyncpg
import logging

logger = logging.getLogger(__name__)


class ContentManager:
    """内容管理服务 - 支持多渠道模板管理"""
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db = db_pool
        self._template_cache = {}
        self._cache_ttl = 300  # 5分钟缓存
    
    async def render_template(self, template_key: str, channel: str, variables: dict = None) -> dict:
        """
        渲染模板内容
        
        Args:
            template_key: 模板键名
            channel: 渠道类型 ('telegram', 'whatsapp', 'web')
            variables: 模板变量
            
        Returns:
            渲染后的内容字典
        """
        if variables is None:
            variables = {}
        
        # 获取模板
        template = await self._get_template(template_key, channel)
        
        if not template:
            # 尝试获取默认模板
            template = await self._get_template(template_key, 'default')
            
        if not template:
            # 返回错误模板
            return {
                'content_type': 'text',
                'content': f"❌ Template not found: {template_key}",
                'title': 'Error'
            }
        
        # 渲染变量
        content = self._render_variables(template['content'], variables)
        title = self._render_variables(template.get('title', ''), variables) if template.get('title') else None
        
        return {
            'content_type': template['content_type'],
            'content': content,
            'title': title,
            'template_key': template_key,
            'channel': channel,
            'variables': variables
        }
    
    async def get_template(self, template_key: str, channel: str) -> Optional[dict]:
        """获取原始模板数据"""
        return await self._get_template(template_key, channel)
    
    async def update_template(self, template_key: str, channel: str, content: str, 
                            content_type: str = 'text', title: str = None, 
                            variables: dict = None) -> bool:
        """
        更新模板内容
        
        Args:
            template_key: 模板键名
            channel: 渠道类型
            content: 模板内容
            content_type: 内容类型 ('text', 'html', 'markdown')
            title: 模板标题
            variables: 变量定义
        """
        try:
            async with self.db.acquire() as conn:
                await conn.execute("""
                    INSERT INTO content_templates 
                    (template_key, channel_type, content_type, title, content, variables)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (template_key, channel_type) 
                    DO UPDATE SET 
                        content_type = $3,
                        title = $4,
                        content = $5,
                        variables = $6,
                        updated_at = NOW()
                """, template_key, channel, content_type, title, content, 
                    json.dumps(variables) if variables else None)
            
            # 清除缓存
            cache_key = f"{template_key}:{channel}"
            self._template_cache.pop(cache_key, None)
            
            logger.info(f"Template updated: {template_key} for {channel}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update template {template_key}: {e}")
            return False
    
    async def delete_template(self, template_key: str, channel: str) -> bool:
        """删除模板"""
        try:
            async with self.db.acquire() as conn:
                result = await conn.execute("""
                    DELETE FROM content_templates 
                    WHERE template_key = $1 AND channel_type = $2
                """, template_key, channel)
            
            # 清除缓存
            cache_key = f"{template_key}:{channel}"
            self._template_cache.pop(cache_key, None)
            
            return result != "DELETE 0"
            
        except Exception as e:
            logger.error(f"Failed to delete template {template_key}: {e}")
            return False
    
    async def get_all_templates(self, channel: str = None) -> List[dict]:
        """获取所有模板列表"""
        try:
            async with self.db.acquire() as conn:
                if channel:
                    rows = await conn.fetch("""
                        SELECT template_key, channel_type, content_type, title, 
                               LENGTH(content) as content_length, variables, updated_at
                        FROM content_templates 
                        WHERE channel_type = $1
                        ORDER BY template_key, channel_type
                    """, channel)
                else:
                    rows = await conn.fetch("""
                        SELECT template_key, channel_type, content_type, title,
                               LENGTH(content) as content_length, variables, updated_at
                        FROM content_templates 
                        ORDER BY template_key, channel_type
                    """)
                
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to get templates: {e}")
            return []
    
    async def get_template_variables(self, template_key: str, channel: str) -> dict:
        """获取模板变量定义"""
        template = await self._get_template(template_key, channel)
        if template and template.get('variables'):
            try:
                return json.loads(template['variables'])
            except json.JSONDecodeError:
                pass
        return {}
    
    async def create_default_templates(self):
        """创建默认模板"""
        default_templates = [
            # 欢迎消息
            {
                'key': 'welcome_message',
                'channel': 'telegram',
                'type': 'text',
                'title': 'Welcome Message',
                'content': """🏛️ <b>FBI INTERNET CRIME COMPLAINT CENTER</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Welcome to the <b>Authorized Digital Reporting Interface (ADRI)</b>

This secure system allows you to file official complaints for:
• Cryptocurrency fraud & theft
• Online investment scams  
• Romance scams involving crypto
• Business email compromise
• Ransomware incidents

<b>Your report will be:</b>
✅ Digitally signed and legally binding
✅ Forwarded to appropriate law enforcement
✅ Protected with federal-grade encryption

Select an option below to begin:""",
                'variables': {'user_id': 'User identifier'}
            },
            {
                'key': 'welcome_message', 
                'channel': 'whatsapp',
                'type': 'text',
                'title': 'Welcome Message',
                'content': """🏛️ *FBI INTERNET CRIME COMPLAINT CENTER*

Welcome to the Authorized Digital Reporting Interface (ADRI)

This secure system allows you to file official complaints for cryptocurrency fraud, online scams, and cyber crimes.

Your report will be digitally signed and legally binding.

Reply with *START* to begin filing a complaint.""",
                'variables': {'user_id': 'User identifier'}
            },
            
            # CRS-01 身份验证提示
            {
                'key': 'crs01_name_prompt',
                'channel': 'telegram', 
                'type': 'text',
                'title': 'Name Prompt',
                'content': """👤 <b>STEP 1 of 3 — IDENTITY VERIFICATION</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Please enter your <b>full legal name</b> as it appears on your government-issued identification:

<i>Example: John Michael Smith</i>""",
                'variables': {}
            },
            {
                'key': 'crs01_address_prompt',
                'channel': 'telegram',
                'type': 'text', 
                'title': 'Address Prompt',
                'content': """🏠 <b>STEP 2 of 3 — PHYSICAL ADDRESS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Hello {{fullname}},

Please enter your complete physical address:

<i>Example: 123 Main Street, Apt 4B, New York, NY 10001</i>""",
                'variables': {'fullname': 'User full name'}
            },
            
            # 错误消息
            {
                'key': 'crs01_name_invalid',
                'channel': 'telegram',
                'type': 'text',
                'title': 'Invalid Name',
                'content': """❌ <b>Invalid Name</b>

Please enter your complete legal name (minimum 2 characters).

<i>Example: John Smith</i>""",
                'variables': {}
            },
            {
                'key': 'unknown_command',
                'channel': 'telegram',
                'type': 'text',
                'title': 'Unknown Command',
                'content': """❓ <b>Unknown Command</b>

I didn't understand: <code>{{command}}</code>

Please use the menu buttons or type /start to begin.""",
                'variables': {'command': 'User input command'}
            },
            
            # 案件创建成功
            {
                'key': 'case_created_success',
                'channel': 'telegram',
                'type': 'text',
                'title': 'Case Created',
                'content': """✅ <b>CASE SUCCESSFULLY CREATED</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>Case ID:</b> <code>{{case_id}}</code>
<b>Status:</b> ⚪ SUBMITTED
<b>Filed:</b> {{current_time}}

Your complaint has been officially filed with the IC3. 
You will receive email updates as your case progresses through our review system.

<b>Important:</b> Save your Case ID for future reference.""",
                'variables': {
                    'case_id': 'Generated case identifier',
                    'current_time': 'Current timestamp'
                }
            }
        ]
        
        for template in default_templates:
            await self.update_template(
                template['key'],
                template['channel'], 
                template['content'],
                template['type'],
                template['title'],
                template['variables']
            )
        
        logger.info("Default templates created")
    
    async def _get_template(self, template_key: str, channel: str) -> Optional[dict]:
        """从数据库获取模板（带缓存）"""
        cache_key = f"{template_key}:{channel}"
        
        # 检查缓存
        if cache_key in self._template_cache:
            cached = self._template_cache[cache_key]
            if cached['expires'] > self._get_current_timestamp():
                return cached['data']
        
        # 从数据库获取
        try:
            async with self.db.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT template_key, channel_type, content_type, title, content, variables
                    FROM content_templates 
                    WHERE template_key = $1 AND channel_type = $2
                """, template_key, channel)
                
                if row:
                    template_data = dict(row)
                    
                    # 缓存结果
                    self._template_cache[cache_key] = {
                        'data': template_data,
                        'expires': self._get_current_timestamp() + self._cache_ttl
                    }
                    
                    return template_data
                    
        except Exception as e:
            logger.error(f"Failed to get template {template_key}:{channel}: {e}")
        
        return None
    
    def _render_variables(self, content: str, variables: dict) -> str:
        """渲染模板变量"""
        if not content or not variables:
            return content
        
        # 简单的变量替换 {{variable_name}}
        def replace_var(match):
            var_name = match.group(1).strip()
            return str(variables.get(var_name, f"{{{{ {var_name} }}}}"))
        
        # 替换 {{variable}} 格式的变量
        content = re.sub(r'\{\{\s*([^}]+)\s*\}\}', replace_var, content)
        
        # 添加当前时间变量
        if '{{current_time}}' in content:
            from datetime import datetime
            current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
            content = content.replace('{{current_time}}', current_time)
        
        return content
    
    def _get_current_timestamp(self) -> int:
        """获取当前时间戳"""
        from time import time
        return int(time())
    
    async def refresh_cache(self):
        """刷新模板缓存"""
        self._template_cache.clear()
        logger.info("Template cache refreshed")
    
    async def get_template_usage_stats(self) -> dict:
        """获取模板使用统计"""
        try:
            async with self.db.acquire() as conn:
                # 按渠道统计模板数量
                channel_stats = await conn.fetch("""
                    SELECT channel_type, COUNT(*) as template_count
                    FROM content_templates
                    GROUP BY channel_type
                    ORDER BY template_count DESC
                """)
                
                # 最近更新的模板
                recent_updates = await conn.fetch("""
                    SELECT template_key, channel_type, updated_at
                    FROM content_templates
                    ORDER BY updated_at DESC
                    LIMIT 10
                """)
                
                return {
                    'channel_stats': [dict(row) for row in channel_stats],
                    'recent_updates': [dict(row) for row in recent_updates],
                    'cache_size': len(self._template_cache)
                }
                
        except Exception as e:
            logger.error(f"Failed to get template stats: {e}")
            return {}
