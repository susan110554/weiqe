"""
数字签名服务
从现有bot.py中抽离的HMAC-SHA256签名逻辑，支持多渠道
"""
import hashlib
import hmac as _hmac
import json
import os
from datetime import datetime
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class SignatureService:
    """数字签名服务 - 渠道无关的签名验证"""
    
    def __init__(self, secret_key: str = None):
        self.secret_key = secret_key or os.getenv("SIGNATURE_SECRET_KEY", "change-me-in-production")
        
        if self.secret_key == "change-me-in-production":
            logger.warning("⚠️ 使用默认签名密钥，生产环境请更换!")
    
    def generate_signature(self, case_data: dict, user_id: str, timestamp: str = None) -> str:
        """
        生成案件数字签名
        
        Args:
            case_data: 案件数据字典
            user_id: 用户ID
            timestamp: 时间戳 (可选，默认使用当前时间)
            
        Returns:
            signature_hex: 十六进制签名字符串
        """
        if timestamp is None:
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # 构造签名载荷
        case_id = case_data.get('case_no', '')
        payload = json.dumps({k: str(v) for k, v in sorted(case_data.items())}, sort_keys=True)
        sig_payload = f"{case_id}{user_id}{timestamp}{payload}{self.secret_key}"
        
        # 生成HMAC-SHA256签名
        signature_hex = _hmac.new(
            self.secret_key.encode() if isinstance(self.secret_key, str) else self.secret_key,
            sig_payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        
        logger.info(f"Generated signature for case {case_id}, user {user_id}")
        return signature_hex
    
    def verify_signature(self, signature: str, case_data: dict, user_id: str, timestamp: str = None) -> bool:
        """
        验证数字签名
        
        Args:
            signature: 待验证的签名
            case_data: 案件数据
            user_id: 用户ID
            timestamp: 时间戳
            
        Returns:
            bool: 签名是否有效
        """
        try:
            expected_signature = self.generate_signature(case_data, user_id, timestamp)
            is_valid = signature.lower() == expected_signature.lower()
            
            if is_valid:
                logger.info(f"Signature verified for case {case_data.get('case_no')}")
            else:
                logger.warning(f"Invalid signature for case {case_data.get('case_no')}")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False
    
    def create_signature_record(self, case_id: str, user_id: str, signature_hex: str, 
                              ip_address: str = None, auth_ref: str = None) -> dict:
        """
        创建签名记录数据
        
        Args:
            case_id: 案件ID
            user_id: 用户ID  
            signature_hex: 签名十六进制字符串
            ip_address: IP地址 (可选)
            auth_ref: 授权引用 (可选)
            
        Returns:
            dict: 签名记录数据
        """
        return {
            'case_no': case_id,
            'tg_user_id': int(user_id) if user_id.isdigit() else None,
            'channel_user_id': user_id,
            'signature_hex': signature_hex,
            'signed_at': datetime.utcnow(),
            'ip_address': ip_address,
            'auth_ref': auth_ref or os.getenv("AUTH_REF", "FBI-2026-HQ-9928-X82")
        }
    
    def build_certificate_text(self, case_id: str, signature_hex: str, 
                             user_id: str = None, timestamp: str = None) -> str:
        """
        构建数字证书文本
        
        Args:
            case_id: 案件ID
            signature_hex: 签名十六进制
            user_id: 用户ID (可选)
            timestamp: 时间戳 (可选)
            
        Returns:
            str: 格式化的证书文本
        """
        if timestamp is None:
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        signed_by = f"USR-{str(user_id)[-6:].zfill(6)}" if user_id else "SYSTEM"
        auth_ref = os.getenv("AUTH_REF", "FBI-2026-HQ-9928-X82")
        
        certificate_text = f"""🏛️ <b>FEDERAL BUREAU OF INVESTIGATION</b>
<b>INTERNET CRIME COMPLAINT CENTER</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🔐 DIGITAL SIGNATURE CERTIFICATE</b>

<b>Case ID:</b> <code>{case_id}</code>
<b>Signed By:</b> <code>{signed_by}</code>
<b>Timestamp:</b> <code>{timestamp}</code>
<b>Auth Ref:</b> <code>{auth_ref}</code>

<b>Digital Signature:</b>
<code>{signature_hex[:32]}
{signature_hex[32:]}</code>

<b>Verification Status:</b> ✅ <b>VERIFIED</b>

This document has been cryptographically signed and 
represents your formal electronic signature on file 
with the IC3.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
<i>This is an official federal document.</i>"""

        return certificate_text
    
    def validate_signature_format(self, signature: str) -> bool:
        """
        验证签名格式
        
        Args:
            signature: 签名字符串
            
        Returns:
            bool: 格式是否有效
        """
        if not signature:
            return False
        
        # 移除空格和换行
        clean_signature = signature.replace(' ', '').replace('\n', '')
        
        # 检查是否为64位十六进制字符串
        if len(clean_signature) != 64:
            return False
        
        try:
            int(clean_signature, 16)
            return True
        except ValueError:
            return False
    
    def get_signature_info(self, signature: str) -> dict:
        """
        获取签名信息
        
        Args:
            signature: 签名字符串
            
        Returns:
            dict: 签名信息
        """
        return {
            'signature': signature,
            'algorithm': 'HMAC-SHA256',
            'length': len(signature.replace(' ', '').replace('\n', '')),
            'format_valid': self.validate_signature_format(signature),
            'created_at': datetime.utcnow().isoformat()
        }
