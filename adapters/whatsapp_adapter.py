"""
WhatsApp Channel Adapter for FBI IC3 Multi-Channel Platform
基于WhatsApp Business API (Meta Graph API)
"""
import asyncio
import aiohttp
import hmac
import hashlib
import logging
import os
from typing import Optional, Dict, Any
from datetime import datetime

from adapters.base_adapter import BaseChannelAdapter

logger = logging.getLogger(__name__)


class WhatsAppAdapter(BaseChannelAdapter):
    """WhatsApp渠道适配器 - 使用WhatsApp Business API"""
    
    def __init__(
        self,
        api_key: str,
        phone_number_id: str,
        webhook_verify_token: str,
        case_manager,
        content_manager,
        signature_service=None,
        business_account_id: str = None
    ):
        """
        初始化WhatsApp适配器
        
        Args:
            api_key: WhatsApp Business API密钥
            phone_number_id: WhatsApp电话号码ID
            webhook_verify_token: Webhook验证令牌
            case_manager: 案件管理核心服务
            content_manager: 内容管理核心服务
            signature_service: 数字签名服务 (可选)
            business_account_id: WhatsApp Business账号ID (可选)
        """
        super().__init__('whatsapp', case_manager, content_manager)
        
        self.api_key = api_key
        self.phone_number_id = phone_number_id
        self.webhook_verify_token = webhook_verify_token
        self.business_account_id = business_account_id
        self.signature_service = signature_service
        
        # WhatsApp Business API配置
        self.api_version = "v18.0"
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
        
        # 用户会话管理
        self.user_sessions = {}
        
        logger.info("WhatsAppAdapter initialized")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # BaseChannelAdapter 必需方法实现
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def send_message(self, user_id: str, content: dict) -> bool:
        """
        发送消息给WhatsApp用户
        
        Args:
            user_id: WhatsApp用户电话号码 (格式: 国家码+号码, 如 8613800138000)
            content: 消息内容字典
                - content: 消息文本
                - content_type: 类型 (text/image/document)
                - image_url: 图片URL (可选)
                - document_url: 文档URL (可选)
                
        Returns:
            bool: 是否发送成功
        """
        try:
            url = f"{self.base_url}/{self.phone_number_id}/messages"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            message_text = content.get('content', '')
            content_type = content.get('content_type', 'text')
            
            # 构建消息payload
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": user_id
            }
            
            if content_type == 'image' and content.get('image_url'):
                # 图片消息
                payload["type"] = "image"
                payload["image"] = {
                    "link": content['image_url'],
                    "caption": message_text[:1024] if message_text else ""
                }
            elif content_type == 'document' and content.get('document_url'):
                # 文档消息
                payload["type"] = "document"
                payload["document"] = {
                    "link": content['document_url'],
                    "filename": content.get('filename', 'document.pdf'),
                    "caption": message_text[:1024] if message_text else ""
                }
            else:
                # 文本消息
                payload["type"] = "text"
                payload["text"] = {"body": message_text[:4096]}  # WhatsApp限制4096字符
            
            # 发送消息
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        response_data = await resp.json()
                        message_id = response_data.get('messages', [{}])[0].get('id')
                        logger.info(f"WhatsApp message sent to {user_id}, ID: {message_id}")
                        return True
                    else:
                        error_text = await resp.text()
                        logger.error(f"Failed to send WhatsApp message: {resp.status} - {error_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"WhatsApp send_message error: {e}")
            return False
    
    async def send_document(
        self,
        user_id: str,
        file_data: bytes,
        file_name: str,
        caption: str = None
    ) -> bool:
        """
        发送文档给WhatsApp用户
        
        注意: WhatsApp Business API需要先上传文件到服务器，然后通过URL发送
        这里提供简化实现，实际使用需要文件托管服务
        
        Args:
            user_id: WhatsApp用户电话号码
            file_data: 文件数据 (bytes)
            file_name: 文件名
            caption: 说明文字 (可选)
            
        Returns:
            bool: 是否发送成功
        """
        try:
            # 实际应用中需要：
            # 1. 上传文件到临时服务器或使用WhatsApp Media API
            # 2. 获取文件URL
            # 3. 使用URL发送文档
            
            logger.warning("WhatsApp send_document requires file hosting - implement media upload")
            
            # 这里返回一个提示消息
            await self.send_message(
                user_id,
                {
                    'content': f"📎 Document ready: {file_name}\n{caption or ''}",
                    'content_type': 'text'
                }
            )
            return True
            
        except Exception as e:
            logger.error(f"WhatsApp send_document error: {e}")
            return False
    
    async def get_user_info(self, user_id: str) -> dict:
        """
        获取WhatsApp用户信息
        
        注意: WhatsApp Business API对用户信息访问有限制
        
        Args:
            user_id: WhatsApp用户电话号码
            
        Returns:
            dict: 用户信息
        """
        return {
            'user_id': user_id,
            'phone_number': user_id,
            'channel': 'whatsapp',
            # WhatsApp API不提供用户名等详细信息
        }
    
    async def handle_message(self, message_data: dict) -> None:
        """
        处理接收到的WhatsApp消息
        
        Args:
            message_data: 从webhook接收的消息数据
        """
        try:
            # 解析消息
            from_number = message_data.get('from')
            message_type = message_data.get('type', 'text')
            message_id = message_data.get('id')
            
            if message_type == 'text':
                text_content = message_data.get('text', {}).get('body', '')
                await self._handle_text_message(from_number, text_content, message_id)
            
            elif message_type == 'image':
                await self._handle_image_message(from_number, message_data.get('image', {}))
            
            elif message_type == 'document':
                await self._handle_document_message(from_number, message_data.get('document', {}))
            
            else:
                logger.warning(f"Unsupported WhatsApp message type: {message_type}")
                
        except Exception as e:
            logger.error(f"WhatsApp handle_message error: {e}")
    
    async def handle_callback(self, callback_data: dict) -> None:
        """
        处理回调（WhatsApp主要使用按钮和列表，这里预留接口）
        """
        logger.info(f"WhatsApp callback received: {callback_data}")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # WhatsApp特定功能
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def _handle_text_message(self, from_number: str, text: str, message_id: str):
        """处理文本消息"""
        user_id = from_number
        
        # 获取用户会话状态
        session = self.user_sessions.get(user_id, {})
        state = session.get('state')
        
        # 处理命令
        text_lower = text.lower().strip()
        
        if text_lower in ['start', 'hello', 'hi', '开始']:
            await self._cmd_start(user_id)
        
        elif text_lower in ['help', '帮助']:
            await self._cmd_help(user_id)
        
        elif text_lower in ['mycases', 'cases', '我的案件']:
            await self._cmd_mycases(user_id)
        
        elif text_lower in ['newcase', 'new', '新案件']:
            await self._cmd_newcase(user_id)
        
        elif state == 'CREATING_CASE':
            # 处理案件创建流程
            await self._handle_case_creation(user_id, text, session)
        
        else:
            # 默认帮助消息
            await self.send_message(
                user_id,
                {
                    'content': "Send 'help' to see available commands.\n"
                              "发送 'help' 查看可用命令。",
                    'content_type': 'text'
                }
            )
    
    async def _handle_image_message(self, from_number: str, image_data: dict):
        """处理图片消息"""
        await self.send_message(
            from_number,
            {
                'content': "📷 Image received. Evidence upload coming soon.\n"
                          "图片已收到，证据上传功能即将推出。",
                'content_type': 'text'
            }
        )
    
    async def _handle_document_message(self, from_number: str, document_data: dict):
        """处理文档消息"""
        await self.send_message(
            from_number,
            {
                'content': "📎 Document received. Evidence upload coming soon.\n"
                          "文档已收到，证据上传功能即将推出。",
                'content_type': 'text'
            }
        )
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 命令处理
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def _cmd_start(self, user_id: str):
        """处理start命令"""
        try:
            # 使用ContentManager渲染欢迎消息
            welcome_content = await self.content_manager.render_template(
                'welcome_message',
                'whatsapp',
                {'user_name': user_id}
            )
            
            message = welcome_content.get('content', 
                "🇺🇸 *FBI IC3 Fraud Reporting*\n\n"
                "Welcome to the FBI Internet Crime Complaint Center.\n\n"
                "*Available Commands:*\n"
                "• help - Show help\n"
                "• mycases - View your cases\n"
                "• newcase - Create new case\n\n"
                "Type a command to get started."
            )
            
            await self.send_message(user_id, {'content': message, 'content_type': 'text'})
            
        except Exception as e:
            logger.error(f"WhatsApp _cmd_start error: {e}")
            await self.send_message(
                user_id,
                {'content': "Welcome to FBI IC3!", 'content_type': 'text'}
            )
    
    async def _cmd_help(self, user_id: str):
        """处理help命令"""
        help_text = """
📋 *FBI IC3 - Command Help*

*User Commands:*
• start - Start the bot
• help - Show this help
• mycases - View your cases
• newcase - Create new case

*Case Management:*
Send 'newcase' to report fraud
Send 'mycases' to check status

For assistance, reply with your question.
        """
        await self.send_message(user_id, {'content': help_text.strip(), 'content_type': 'text'})
    
    async def _cmd_mycases(self, user_id: str):
        """处理mycases命令"""
        try:
            # 调用CaseManager获取用户案件
            result = await self.case_manager.get_cases_paginated(
                page=1,
                limit=10,
                channel='whatsapp',
                channel_user_id=user_id
            )
            
            cases = result.get('cases', [])
            
            if not cases:
                await self.send_message(
                    user_id,
                    {
                        'content': "You have no cases yet.\n\nSend 'newcase' to create one.",
                        'content_type': 'text'
                    }
                )
                return
            
            # 构建案件列表
            lines = ["*Your Cases:*\n"]
            for case in cases[:5]:  # 只显示前5个
                case_no = case.get('case_no', 'N/A')
                status = case.get('status', 'Unknown')
                lines.append(f"• {case_no}")
                lines.append(f"  Status: {status}\n")
            
            if len(cases) > 5:
                lines.append(f"\n_... and {len(cases) - 5} more cases_")
            
            await self.send_message(
                user_id,
                {'content': '\n'.join(lines), 'content_type': 'text'}
            )
            
        except Exception as e:
            logger.error(f"WhatsApp _cmd_mycases error: {e}")
            await self.send_message(
                user_id,
                {'content': "Failed to retrieve cases.", 'content_type': 'text'}
            )
    
    async def _cmd_newcase(self, user_id: str):
        """处理newcase命令"""
        # 初始化会话
        self.user_sessions[user_id] = {
            'state': 'CREATING_CASE',
            'case_data': {},
            'step': 'name'
        }
        
        await self.send_message(
            user_id,
            {
                'content': "*Create New Case*\n\n"
                          "Let's collect your information.\n\n"
                          "Please provide your *full name*:",
                'content_type': 'text'
            }
        )
    
    async def _handle_case_creation(self, user_id: str, text: str, session: dict):
        """处理案件创建流程"""
        case_data = session.get('case_data', {})
        step = session.get('step')
        
        if step == 'name':
            case_data['full_name'] = text
            session['step'] = 'email'
            session['case_data'] = case_data
            self.user_sessions[user_id] = session
            
            await self.send_message(
                user_id,
                {
                    'content': f"Thank you, {text}.\n\nNow please provide your *email address*:",
                    'content_type': 'text'
                }
            )
        
        elif step == 'email':
            case_data['email'] = text
            session['step'] = 'description'
            session['case_data'] = case_data
            self.user_sessions[user_id] = session
            
            await self.send_message(
                user_id,
                {
                    'content': "Great. Now describe the *fraud incident*:",
                    'content_type': 'text'
                }
            )
        
        elif step == 'description':
            case_data['description'] = text
            
            # 创建案件
            await self._create_case_from_data(user_id, case_data)
            
            # 清除会话
            self.user_sessions.pop(user_id, None)
    
    async def _create_case_from_data(self, user_id: str, case_data: dict):
        """从收集的数据创建案件"""
        try:
            # 调用CaseManager创建案件
            case_info = {
                'channel': 'whatsapp',
                'channel_user_id': user_id,
                'full_name': case_data.get('full_name', ''),
                'email': case_data.get('email', ''),
                'description': case_data.get('description', ''),
                'platform': 'Other',
                'amount': '0',
                'status': '待初步审核',
            }
            
            case_id = await self.case_manager.create_case(case_info)
            
            if case_id:
                await self.send_message(
                    user_id,
                    {
                        'content': f"✅ *Case Created Successfully!*\n\n"
                                  f"Case ID: `{case_id}`\n"
                                  f"Status: Pending Review\n\n"
                                  f"You will receive updates as your case progresses.\n\n"
                                  f"Send 'mycases' to view your cases anytime.",
                        'content_type': 'text'
                    }
                )
            else:
                await self.send_message(
                    user_id,
                    {'content': "Failed to create case. Please try again later.", 'content_type': 'text'}
                )
                
        except Exception as e:
            logger.error(f"WhatsApp _create_case_from_data error: {e}")
            await self.send_message(
                user_id,
                {'content': "An error occurred. Please try again.", 'content_type': 'text'}
            )
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Webhook处理
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    def verify_webhook(self, mode: str, token: str, challenge: str) -> Optional[str]:
        """
        验证WhatsApp webhook
        
        Args:
            mode: 验证模式 (应为 'subscribe')
            token: 验证令牌
            challenge: 挑战字符串
            
        Returns:
            str: 如果验证成功返回challenge，否则返回None
        """
        if mode == "subscribe" and token == self.webhook_verify_token:
            logger.info("WhatsApp webhook verified successfully")
            return challenge
        else:
            logger.warning("WhatsApp webhook verification failed")
            return None
    
    async def process_webhook(self, webhook_data: dict) -> bool:
        """
        处理WhatsApp webhook数据
        
        Args:
            webhook_data: webhook POST数据
            
        Returns:
            bool: 处理是否成功
        """
        try:
            # 解析webhook数据
            entry = webhook_data.get('entry', [])
            
            for item in entry:
                changes = item.get('changes', [])
                
                for change in changes:
                    value = change.get('value', {})
                    
                    # 处理消息
                    messages = value.get('messages', [])
                    for message in messages:
                        await self.handle_message(message)
                    
                    # 处理状态更新 (已读、已送达等)
                    statuses = value.get('statuses', [])
                    for status in statuses:
                        self._handle_message_status(status)
            
            return True
            
        except Exception as e:
            logger.error(f"WhatsApp process_webhook error: {e}")
            return False
    
    def _handle_message_status(self, status: dict):
        """处理消息状态更新"""
        message_id = status.get('id')
        status_type = status.get('status')  # sent, delivered, read, failed
        logger.info(f"WhatsApp message {message_id} status: {status_type}")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 生命周期管理
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def start(self) -> bool:
        """
        启动WhatsApp适配器
        
        注意: WhatsApp使用webhook模式，需要配合FastAPI等Web框架
        这里只是标记为已启动
        """
        try:
            self.is_running = True
            logger.info("✅ WhatsAppAdapter started (webhook mode)")
            logger.info(f"   - Phone Number ID: {self.phone_number_id}")
            logger.info(f"   - API Version: {self.api_version}")
            logger.info(f"   - Webhook URL should be: /webhook/whatsapp")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start WhatsAppAdapter: {e}")
            return False
    
    async def stop(self) -> bool:
        """停止WhatsApp适配器"""
        try:
            self.is_running = False
            self.user_sessions.clear()
            logger.info("WhatsAppAdapter stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop WhatsAppAdapter: {e}")
            return False
