"""
FBI IC3 Multi-Channel Platform - Channel Adapters

渠道适配器模块，实现各个渠道的统一接口
"""

from .base_adapter import BaseChannelAdapter
from .telegram_adapter import TelegramAdapter
from .whatsapp_adapter import WhatsAppAdapter

# 暂时注释掉未实现的适配器
# from .web_adapter import WebAdapter

__all__ = [
    'BaseChannelAdapter',
    'TelegramAdapter',
    'WhatsAppAdapter',
    # 'WebAdapter',
]
