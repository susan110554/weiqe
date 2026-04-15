"""
WhatsApp Webhook Handler for Web Controller
处理WhatsApp Business API的webhook请求
"""
from fastapi import APIRouter, Request, Query, HTTPException
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# 全局WhatsApp适配器实例 (由主程序设置)
_whatsapp_adapter: Optional['WhatsAppAdapter'] = None


def set_whatsapp_adapter(adapter):
    """设置WhatsApp适配器实例"""
    global _whatsapp_adapter
    _whatsapp_adapter = adapter
    logger.info("WhatsApp adapter registered for webhook")


# 创建路由器
router = APIRouter(prefix="/webhook/whatsapp", tags=["WhatsApp Webhook"])


@router.get("")
async def verify_webhook(
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge")
):
    """
    WhatsApp Webhook验证端点
    
    WhatsApp会发送GET请求来验证webhook URL
    """
    if not _whatsapp_adapter:
        raise HTTPException(status_code=503, detail="WhatsApp adapter not initialized")
    
    if not mode or not token or not challenge:
        raise HTTPException(status_code=400, detail="Missing verification parameters")
    
    # 验证token
    result = _whatsapp_adapter.verify_webhook(mode, token, challenge)
    
    if result:
        logger.info("WhatsApp webhook verification successful")
        # 返回challenge字符串 (纯文本)
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(content=result)
    else:
        logger.warning("WhatsApp webhook verification failed")
        raise HTTPException(status_code=403, detail="Verification failed")


@router.post("")
async def receive_webhook(request: Request):
    """
    WhatsApp Webhook接收端点
    
    接收WhatsApp发送的消息和状态更新
    """
    if not _whatsapp_adapter:
        raise HTTPException(status_code=503, detail="WhatsApp adapter not initialized")
    
    try:
        # 获取webhook数据
        webhook_data = await request.json()
        
        logger.info(f"WhatsApp webhook received: {webhook_data.get('entry', [{}])[0].get('id', 'unknown')}")
        
        # 处理webhook
        success = await _whatsapp_adapter.process_webhook(webhook_data)
        
        if success:
            # WhatsApp期望200 OK响应
            return {"status": "ok"}
        else:
            raise HTTPException(status_code=500, detail="Webhook processing failed")
            
    except Exception as e:
        logger.error(f"WhatsApp webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def webhook_status():
    """检查webhook状态"""
    if not _whatsapp_adapter:
        return {
            "status": "not_initialized",
            "message": "WhatsApp adapter not set"
        }
    
    return {
        "status": "active" if _whatsapp_adapter.is_running else "inactive",
        "phone_number_id": _whatsapp_adapter.phone_number_id,
        "api_version": _whatsapp_adapter.api_version,
        "message": "WhatsApp webhook is ready"
    }
