"""
基础渠道适配器
定义所有渠道适配器的统一接口
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class BaseChannelAdapter(ABC):
    """基础渠道适配器抽象类"""
    
    def __init__(self, channel_name: str, case_manager, content_manager):
        self.channel_name = channel_name
        self.case_manager = case_manager
        self.content_manager = content_manager
        self.is_running = False
    
    @abstractmethod
    async def send_message(self, user_id: str, content: dict) -> bool:
        """
        发送消息到用户
        
        Args:
            user_id: 用户ID
            content: 消息内容字典
                {
                    'content_type': 'text' | 'image' | 'document',
                    'content': '消息内容',
                    'title': '标题（可选）',
                    'file_data': bytes（文件类型时）,
                    'file_name': '文件名（可选）'
                }
        
        Returns:
            bool: 发送是否成功
        """
        pass
    
    @abstractmethod
    async def send_document(self, user_id: str, file_data: bytes, file_name: str, caption: str = None) -> bool:
        """
        发送文档到用户
        
        Args:
            user_id: 用户ID
            file_data: 文件数据
            file_name: 文件名
            caption: 文件说明
        
        Returns:
            bool: 发送是否成功
        """
        pass
    
    @abstractmethod
    async def get_user_info(self, user_id: str) -> Optional[dict]:
        """
        获取用户信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            dict: 用户信息字典或None
                {
                    'user_id': str,
                    'username': str,
                    'first_name': str,
                    'last_name': str,
                    'language_code': str
                }
        """
        pass
    
    @abstractmethod
    async def handle_message(self, message_data: dict) -> None:
        """
        处理接收到的消息
        
        Args:
            message_data: 消息数据字典
        """
        pass
    
    @abstractmethod
    async def handle_callback(self, callback_data: dict) -> None:
        """
        处理回调数据（按钮点击等）
        
        Args:
            callback_data: 回调数据字典
        """
        pass
    
    @abstractmethod
    async def start(self) -> bool:
        """
        启动适配器
        
        Returns:
            bool: 启动是否成功
        """
        pass
    
    @abstractmethod
    async def stop(self) -> bool:
        """
        停止适配器
        
        Returns:
            bool: 停止是否成功
        """
        pass
    
    async def process_user_input(self, user_id: str, message_type: str, content: str) -> Optional[dict]:
        """
        处理用户输入的通用方法
        
        Args:
            user_id: 用户ID
            message_type: 消息类型
            content: 消息内容
            
        Returns:
            dict: 响应内容或None
        """
        try:
            response = await self.case_manager.process_user_input(
                user_id=user_id,
                channel=self.channel_name,
                message_type=message_type,
                content=content
            )
            return response
        except Exception as e:
            logger.error(f"Error processing user input in {self.channel_name}: {e}")
            return await self.content_manager.render_template(
                'system_error', 
                self.channel_name, 
                {'error': 'System temporarily unavailable'}
            )
    
    async def send_case_notification(self, user_id: str, case_id: str, notification_type: str) -> bool:
        """
        发送案件通知
        
        Args:
            user_id: 用户ID
            case_id: 案件ID
            notification_type: 通知类型
            
        Returns:
            bool: 发送是否成功
        """
        try:
            case_data = await self.case_manager.get_case_by_id(case_id)
            if not case_data:
                return False
            
            template_key = f"case_notification_{notification_type}"
            content = await self.content_manager.render_template(
                template_key, 
                self.channel_name, 
                {
                    'case_id': case_id,
                    'status': case_data.get('status', 'Unknown'),
                    'platform': case_data.get('platform', 'Unknown')
                }
            )
            
            return await self.send_message(user_id, content)
            
        except Exception as e:
            logger.error(f"Error sending case notification: {e}")
            return False
    
    def validate_user_id(self, user_id: str) -> bool:
        """
        验证用户ID格式
        
        Args:
            user_id: 用户ID
            
        Returns:
            bool: 是否有效
        """
        return bool(user_id and str(user_id).strip())
    
    def format_error_message(self, error: str) -> dict:
        """
        格式化错误消息
        
        Args:
            error: 错误信息
            
        Returns:
            dict: 格式化的错误消息
        """
        return {
            'content_type': 'text',
            'content': f"❌ Error: {error}",
            'title': 'System Error'
        }
    
    def get_channel_stats(self) -> dict:
        """
        获取渠道统计信息
        
        Returns:
            dict: 统计信息
        """
        return {
            'channel_name': self.channel_name,
            'is_running': self.is_running,
            'adapter_type': self.__class__.__name__
        }
