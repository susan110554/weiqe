"""
Telegram Channel Adapter for FBI IC3 Multi-Channel Platform
重构自原bot.py，使用适配器模式，集成核心业务服务
"""
import asyncio
import html
import logging
import os
from typing import Optional, Dict, Any
from datetime import datetime

from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)

from adapters.base_adapter import BaseChannelAdapter

logger = logging.getLogger(__name__)


class TelegramAdapter(BaseChannelAdapter):
    """Telegram渠道适配器 - 处理所有Telegram Bot交互"""
    
    def __init__(
        self,
        token: str,
        case_manager,
        content_manager,
        signature_service=None,
        pdf_service=None,
        notification_service=None
    ):
        """
        初始化Telegram适配器
        
        Args:
            token: Telegram Bot Token
            case_manager: 案件管理核心服务
            content_manager: 内容管理核心服务
            signature_service: 数字签名服务 (可选)
            pdf_service: PDF生成服务 (可选)
            notification_service: 通知服务 (可选)
        """
        super().__init__('telegram', case_manager, content_manager)
        
        self.token = token
        self.bot = Bot(token)
        self.app: Optional[Application] = None
        self.signature_service = signature_service
        self.pdf_service = pdf_service
        self.notification_service = notification_service
        
        # Admin用户ID列表
        self.admin_ids = self._load_admin_ids()
        
        logger.info("TelegramAdapter initialized")
    
    def _load_admin_ids(self) -> list:
        """从环境变量加载管理员ID"""
        admin_str = os.getenv("ADMIN_IDS", "")
        if not admin_str:
            return []
        return [int(id.strip()) for id in admin_str.split(",") if id.strip()]
    
    def is_admin(self, user_id: int) -> bool:
        """检查用户是否为管理员"""
        return user_id in self.admin_ids
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # BaseChannelAdapter 必需方法实现
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def send_message(self, user_id: str, content: dict) -> bool:
        """
        发送消息给用户
        
        Args:
            user_id: Telegram用户ID (字符串格式)
            content: 消息内容字典
                - content: 消息文本
                - content_type: 类型 (text/html/markdown)
                - reply_markup: 键盘 (可选)
                - photo: 图片路径 (可选)
                
        Returns:
            bool: 是否发送成功
        """
        try:
            telegram_id = int(user_id)
            message_text = content.get('content', '')
            content_type = content.get('content_type', 'text')
            
            # 解析模式
            parse_mode = None
            if content_type == 'html':
                parse_mode = 'HTML'
            elif content_type == 'markdown':
                parse_mode = 'Markdown'
            
            # 处理键盘
            reply_markup = content.get('reply_markup')
            
            # 处理图片消息
            photo_path = content.get('photo')
            if photo_path and os.path.isfile(photo_path):
                with open(photo_path, 'rb') as f:
                    await self.bot.send_photo(
                        chat_id=telegram_id,
                        photo=f,
                        caption=message_text,
                        parse_mode=parse_mode,
                        reply_markup=reply_markup
                    )
                return True
            
            # 发送文本消息
            await self.bot.send_message(
                chat_id=telegram_id,
                text=message_text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to send message to {user_id}: {e}")
            return False
    
    async def send_document(
        self,
        user_id: str,
        file_data: bytes,
        file_name: str,
        caption: str = None
    ) -> bool:
        """
        发送文档给用户
        
        Args:
            user_id: Telegram用户ID
            file_data: 文件数据 (bytes)
            file_name: 文件名
            caption: 说明文字 (可选)
            
        Returns:
            bool: 是否发送成功
        """
        try:
            telegram_id = int(user_id)
            
            import io
            file_obj = io.BytesIO(file_data)
            file_obj.name = file_name
            
            await self.bot.send_document(
                chat_id=telegram_id,
                document=file_obj,
                filename=file_name,
                caption=caption
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to send document to {user_id}: {e}")
            return False
    
    async def get_user_info(self, user_id: str) -> dict:
        """
        获取用户信息
        
        Args:
            user_id: Telegram用户ID
            
        Returns:
            dict: 用户信息
        """
        try:
            telegram_id = int(user_id)
            chat = await self.bot.get_chat(telegram_id)
            
            return {
                'user_id': str(chat.id),
                'username': chat.username or '',
                'first_name': chat.first_name or '',
                'last_name': chat.last_name or '',
                'full_name': f"{chat.first_name or ''} {chat.last_name or ''}".strip(),
                'is_bot': getattr(chat, 'is_bot', False),
            }
            
        except Exception as e:
            logger.error(f"Failed to get user info for {user_id}: {e}")
            return {'user_id': user_id, 'error': str(e)}
    
    async def handle_message(self, message_data: dict) -> None:
        """
        处理用户消息 (由telegram.ext框架调用，这里保留接口兼容性)
        实际消息处理在各个handler中完成
        """
        pass
    
    async def handle_callback(self, callback_data: dict) -> None:
        """
        处理回调查询 (由telegram.ext框架调用，这里保留接口兼容性)
        实际回调处理在callback_handler中完成
        """
        pass
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Telegram特定功能
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    def _setup_handlers(self):
        """设置所有Telegram命令和消息处理器"""
        if not self.app:
            logger.error("Application not initialized")
            return
        
        # 命令处理器
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(CommandHandler("mycases", self._cmd_mycases))
        self.app.add_handler(CommandHandler("newcase", self._cmd_newcase))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        
        # 管理员命令
        self.app.add_handler(CommandHandler("console", self._cmd_console))
        self.app.add_handler(CommandHandler("admin", self._cmd_admin))
        
        # 回调查询处理器
        self.app.add_handler(CallbackQueryHandler(self._callback_handler))
        
        # 消息处理器
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._msg_handler)
        )
        self.app.add_handler(MessageHandler(filters.PHOTO, self._photo_handler))
        self.app.add_handler(MessageHandler(filters.Document.ALL, self._document_handler))
        
        # 错误处理器
        self.app.add_error_handler(self._error_handler)
        
        logger.info("Telegram handlers registered")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 命令处理器
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /start 命令"""
        user_id = str(update.effective_user.id)
        user_name = update.effective_user.first_name or "User"
        
        # 使用ContentManager渲染欢迎消息
        try:
            welcome_content = await self.content_manager.render_template(
                'welcome_message',
                'telegram',
                {'user_name': user_name}
            )
            
            await update.message.reply_text(
                welcome_content.get('content', 'Welcome to FBI IC3!'),
                parse_mode='HTML'
            )
            
        except Exception as e:
            logger.error(f"Failed to render welcome template: {e}")
            # 降级到默认消息
            await update.message.reply_text(
                f"Welcome {user_name}! FBI IC3 Multi-Channel Platform"
            )
        
        logger.info(f"[Telegram] /start by user {user_id}")
    
    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /help 命令"""
        help_text = """
<b>FBI IC3 - Command Help</b>

<b>User Commands:</b>
/start - Start the bot
/help - Show this help message
/mycases - View your cases
/newcase - Create a new case
/status - Check case status

<b>Admin Commands:</b>
/console - Admin console
/admin - Admin panel

For assistance, contact support.
        """
        await update.message.reply_text(help_text.strip(), parse_mode='HTML')
    
    async def _cmd_mycases(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /mycases 命令 - 查看我的案件"""
        user_id = str(update.effective_user.id)
        
        try:
            # 调用CaseManager获取用户案件
            result = await self.case_manager.get_cases_paginated(
                page=1,
                limit=10,
                channel='telegram',
                channel_user_id=user_id
            )
            
            cases = result.get('cases', [])
            
            if not cases:
                await update.message.reply_text(
                    "You have no cases yet. Use /newcase to create one."
                )
                return
            
            # 构建案件列表
            lines = ["<b>Your Cases:</b>\n"]
            for case in cases:
                case_no = case.get('case_no', 'N/A')
                status = case.get('status', 'Unknown')
                created = case.get('created_at', '')
                lines.append(f"• {case_no} - {status} ({created})")
            
            await update.message.reply_text(
                "\n".join(lines),
                parse_mode='HTML'
            )
            
        except Exception as e:
            logger.error(f"Failed to get cases for user {user_id}: {e}")
            await update.message.reply_text(
                "Failed to retrieve cases. Please try again later."
            )
    
    async def _cmd_newcase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /newcase 命令 - 创建新案件"""
        await update.message.reply_text(
            "<b>Create New Case</b>\n\n"
            "Starting case creation process...\n"
            "Please provide the required information.",
            parse_mode='HTML'
        )
        
        # 设置用户状态为创建案件
        context.user_data['state'] = 'CREATING_CASE'
        context.user_data['case_data'] = {}
        
        # 开始收集信息
        await update.message.reply_text(
            "Please provide your <b>full name</b>:",
            parse_mode='HTML'
        )
    
    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /status 命令 - 查询案件状态"""
        args = context.args
        
        if not args:
            await update.message.reply_text(
                "Usage: /status CASE_ID\n"
                "Example: /status IC3-2026-REF-1234-ABC"
            )
            return
        
        case_id = args[0].upper()
        
        try:
            # 调用CaseManager获取案件详情
            case = await self.case_manager.get_case_by_id(case_id)
            
            if not case:
                await update.message.reply_text(f"Case {case_id} not found.")
                return
            
            # 构建状态消息
            status_msg = f"""
<b>Case Status</b>

Case ID: {case.get('case_no', 'N/A')}
Status: {case.get('status', 'Unknown')}
Platform: {case.get('platform', 'N/A')}
Amount: ${case.get('amount', '0')}
Created: {case.get('created_at', 'N/A')}
Updated: {case.get('updated_at', 'N/A')}
            """
            
            await update.message.reply_text(status_msg.strip(), parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"Failed to get case status for {case_id}: {e}")
            await update.message.reply_text("Failed to retrieve case status.")
    
    async def _cmd_console(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /console 命令 - 管理员控制台"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied.")
            return
        
        await update.message.reply_text(
            "<b>Admin Console</b>\n\n"
            "Administrative functions available.",
            parse_mode='HTML'
        )
    
    async def _cmd_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /admin 命令 - 管理员面板"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("Access denied.")
            return
        
        await update.message.reply_text(
            "<b>Admin Panel</b>\n\n"
            "Admin features coming soon.",
            parse_mode='HTML'
        )
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 回调处理器
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def _callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理所有回调查询"""
        query = update.callback_query
        data = query.data
        
        try:
            await query.answer()
            
            # 根据回调数据分发到不同处理器
            if data.startswith('case_'):
                await self._handle_case_callback(update, context, data)
            elif data.startswith('status_'):
                await self._handle_status_callback(update, context, data)
            elif data.startswith('admin_'):
                await self._handle_admin_callback(update, context, data)
            else:
                logger.warning(f"Unhandled callback data: {data}")
                
        except Exception as e:
            logger.error(f"Callback handler error: {e}")
    
    async def _handle_case_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        data: str
    ):
        """处理案件相关回调"""
        # 解析回调数据
        parts = data.split('_')
        if len(parts) < 2:
            return
        
        action = parts[1]
        
        if action == 'view':
            # 查看案件详情
            case_id = parts[2] if len(parts) > 2 else None
            if case_id:
                await self._show_case_detail(update, case_id)
        
        elif action == 'update':
            # 更新案件
            pass
    
    async def _handle_status_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        data: str
    ):
        """处理状态更新回调"""
        pass
    
    async def _handle_admin_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        data: str
    ):
        """处理管理员回调"""
        if not self.is_admin(update.effective_user.id):
            await update.callback_query.answer("Access denied.", show_alert=True)
            return
        
        # 管理员功能
        pass
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 消息处理器
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def _msg_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理文本消息"""
        user_id = str(update.effective_user.id)
        message_text = update.message.text
        
        # 检查用户状态
        state = context.user_data.get('state')
        
        if state == 'CREATING_CASE':
            # 处理案件创建流程
            await self._handle_case_creation(update, context, message_text)
        else:
            # 默认消息处理
            await update.message.reply_text(
                "I received your message. Use /help to see available commands."
            )
    
    async def _handle_case_creation(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        message_text: str
    ):
        """处理案件创建流程中的消息"""
        case_data = context.user_data.get('case_data', {})
        
        # 根据收集进度处理不同字段
        if 'full_name' not in case_data:
            case_data['full_name'] = message_text
            context.user_data['case_data'] = case_data
            await update.message.reply_text(
                "Thank you. Now please provide your <b>email address</b>:",
                parse_mode='HTML'
            )
        elif 'email' not in case_data:
            case_data['email'] = message_text
            context.user_data['case_data'] = case_data
            await update.message.reply_text(
                "Great. Please describe the <b>fraud incident</b>:",
                parse_mode='HTML'
            )
        elif 'description' not in case_data:
            case_data['description'] = message_text
            context.user_data['case_data'] = case_data
            
            # 完成收集，创建案件
            await self._create_case_from_data(update, context, case_data)
    
    async def _create_case_from_data(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        case_data: dict
    ):
        """从收集的数据创建案件"""
        user_id = str(update.effective_user.id)
        
        try:
            # 调用CaseManager创建案件
            case_info = {
                'tg_user_id': int(user_id),
                'channel': 'telegram',
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
                await update.message.reply_text(
                    f"✅ <b>Case created successfully!</b>\n\n"
                    f"Case ID: {case_id}\n"
                    f"Status: Pending Review\n\n"
                    f"You will receive updates as your case progresses.",
                    parse_mode='HTML'
                )
                
                # 清除状态
                context.user_data.pop('state', None)
                context.user_data.pop('case_data', None)
            else:
                await update.message.reply_text(
                    "Failed to create case. Please try again later."
                )
                
        except Exception as e:
            logger.error(f"Failed to create case: {e}")
            await update.message.reply_text(
                "An error occurred while creating your case. Please try again."
            )
    
    async def _photo_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理图片消息"""
        await update.message.reply_text(
            "Photo received. Evidence upload feature coming soon."
        )
    
    async def _document_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理文档消息"""
        await update.message.reply_text(
            "Document received. Evidence upload feature coming soon."
        )
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 辅助方法
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def _show_case_detail(self, update: Update, case_id: str):
        """显示案件详情"""
        try:
            case = await self.case_manager.get_case_by_id(case_id)
            
            if not case:
                await update.callback_query.message.reply_text(
                    f"Case {case_id} not found."
                )
                return
            
            detail_msg = f"""
<b>Case Details</b>

Case ID: {case.get('case_no', 'N/A')}
Status: {case.get('status', 'Unknown')}
Name: {case.get('full_name', 'N/A')}
Email: {case.get('email', 'N/A')}
Platform: {case.get('platform', 'N/A')}
Amount: ${case.get('amount', '0')}
Created: {case.get('created_at', 'N/A')}
            """
            
            await update.callback_query.message.reply_text(
                detail_msg.strip(),
                parse_mode='HTML'
            )
            
        except Exception as e:
            logger.error(f"Failed to show case detail: {e}")
    
    async def _error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """全局错误处理器"""
        logger.error(f"Update {update} caused error {context.error}")
        
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "An error occurred. Please try again later."
            )
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 适配器生命周期管理
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def start(self) -> bool:
        """启动Telegram适配器"""
        try:
            # 创建Application
            self.app = Application.builder().token(self.token).build()
            
            # 设置handlers
            self._setup_handlers()
            
            # 设置Bot命令菜单
            commands = [
                BotCommand("start", "Start the bot"),
                BotCommand("help", "Show help"),
                BotCommand("mycases", "View your cases"),
                BotCommand("newcase", "Create new case"),
                BotCommand("status", "Check case status"),
            ]
            await self.bot.set_my_commands(commands)
            
            # 启动轮询
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
            
            logger.info("✅ TelegramAdapter started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start TelegramAdapter: {e}")
            return False
    
    async def stop(self) -> bool:
        """停止Telegram适配器"""
        try:
            if self.app:
                await self.app.updater.stop()
                await self.app.stop()
                await self.app.shutdown()
            
            logger.info("TelegramAdapter stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop TelegramAdapter: {e}")
            return False
