"""
通知服务
跨渠道通知管理和消息发送
"""
import json
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """通知服务 - 跨渠道通知管理"""
    
    def __init__(self, db_pool=None):
        self.db = db_pool
        self._adapters = {}  # 渠道适配器注册表
    
    def register_adapter(self, channel: str, adapter):
        """注册渠道适配器"""
        self._adapters[channel] = adapter
        logger.info(f"Registered adapter for channel: {channel}")
    
    async def send_notification(self, user_id: str, channel: str, notification_type: str, data: dict) -> bool:
        """
        发送通知
        
        Args:
            user_id: 用户ID
            channel: 渠道类型
            notification_type: 通知类型
            data: 通知数据
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 获取通知规则
            rules = await self._get_notification_rules(notification_type)
            
            for rule in rules:
                if channel in rule.get('target_channels', []):
                    await self._send_to_channel(user_id, channel, rule, data)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return False
    
    async def _get_notification_rules(self, event_type: str) -> List[dict]:
        """获取通知规则"""
        if not self.db:
            return []
        
        try:
            async with self.db.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM notification_rules 
                    WHERE trigger_event = $1 AND is_active = true
                """, event_type)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get notification rules: {e}")
            return []
    
    async def _send_to_channel(self, user_id: str, channel: str, rule: dict, data: dict) -> bool:
        """发送到指定渠道"""
        try:
            adapter = self._adapters.get(channel)
            if not adapter:
                logger.warning(f"No adapter registered for channel: {channel}")
                return False
            
            # 构造消息内容
            template_key = rule.get('template_key')
            if template_key:
                # 使用模板渲染消息
                content = await self._render_notification_template(template_key, channel, data)
            else:
                # 使用默认消息格式
                content = {
                    'content_type': 'text',
                    'content': f"Notification: {rule.get('rule_name', 'Unknown')}"
                }
            
            # 发送消息
            success = await adapter.send_message(user_id, content)
            
            # 记录发送日志
            await self._log_message(user_id, channel, template_key, content, success)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send to channel {channel}: {e}")
            return False
    
    async def _render_notification_template(self, template_key: str, channel: str, data: dict) -> dict:
        """渲染通知模板"""
        # 这里应该调用 ContentManager 来渲染模板
        # 暂时返回简单格式
        return {
            'content_type': 'text',
            'content': f"Notification from template: {template_key}",
            'data': data
        }
    
    async def _log_message(self, user_id: str, channel: str, template_key: str, 
                          content: dict, success: bool) -> None:
        """记录消息发送日志"""
        if not self.db:
            return
        
        try:
            async with self.db.acquire() as conn:
                await conn.execute("""
                    INSERT INTO message_logs 
                    (channel_type, channel_user_id, message_type, template_key, 
                     content_preview, status, sent_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                    channel, user_id, content.get('content_type', 'text'),
                    template_key, content.get('content', '')[:200],
                    'sent' if success else 'failed', datetime.utcnow()
                )
        except Exception as e:
            logger.error(f"Failed to log message: {e}")
