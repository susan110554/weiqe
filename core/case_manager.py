"""
案件管理核心服务
从现有bot.py中抽离的案件管理逻辑，支持多渠道
"""
import json
import uuid
import hashlib
import hmac as _hmac
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import asyncpg
import logging

from .content_manager import ContentManager
from .signature_service import SignatureService

logger = logging.getLogger(__name__)


class CaseManager:
    """案件管理核心服务 - 渠道无关的业务逻辑"""
    
    def __init__(self, db_pool: asyncpg.Pool, content_manager: ContentManager, signature_service: SignatureService):
        self.db = db_pool
        self.content = content_manager
        self.signature = signature_service
        self._user_sessions = {}  # 用户会话状态缓存
    
    async def create_case(self, user_data: dict, channel: str, channel_user_id: str) -> str:
        """
        创建新案件 - 渠道无关
        
        Args:
            user_data: 用户提交的案件数据
            channel: 渠道类型 ('telegram', 'whatsapp', 'web')
            channel_user_id: 渠道内的用户ID
            
        Returns:
            case_id: 生成的案件ID
        """
        case_id = await self._generate_case_id()
        
        # 数据验证
        validation_result = self._validate_case_data(user_data)
        if not validation_result['valid']:
            raise ValueError(f"Invalid case data: {validation_result['errors']}")
        
        # 构造案件记录
        case_record = {
            "case_no": case_id,
            "channel": channel,
            "channel_user_id": channel_user_id,
            "tg_user_id": int(channel_user_id) if channel == 'telegram' else None,
            "tg_username": user_data.get("username", "Anonymous"),
            "platform": user_data.get("platform", "Not specified"),
            "amount": user_data.get("amount", "0"),
            "coin": user_data.get("coin", ""),
            "incident_time": user_data.get("incident_time", "Not specified"),
            "wallet_addr": user_data.get("wallet_addr", "Unknown"),
            "chain_type": user_data.get("chain_type", "Unknown"),
            "tx_hash": user_data.get("tx_hash", "None"),
            "contact": user_data.get("contact", "Anonymous"),
            "status": "待初步审核",
            "created_at": datetime.utcnow(),
        }
        
        # 保存PDF快照数据
        pdf_snapshot = self._build_pdf_snapshot(user_data, case_id)
        case_record["case_pdf_snapshot"] = pdf_snapshot
        
        async with self.db.acquire() as conn:
            # 插入案件记录
            await conn.execute("""
                INSERT INTO cases (
                    case_no, channel, channel_user_id, tg_user_id, tg_username,
                    platform, amount, coin, incident_time, wallet_addr, 
                    chain_type, tx_hash, contact, status, case_pdf_snapshot
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15
                )
            """, 
                case_record["case_no"], case_record["channel"], case_record["channel_user_id"],
                case_record["tg_user_id"], case_record["tg_username"], case_record["platform"],
                case_record["amount"], case_record["coin"], case_record["incident_time"],
                case_record["wallet_addr"], case_record["chain_type"], case_record["tx_hash"],
                case_record["contact"], case_record["status"], json.dumps(pdf_snapshot)
            )
            
            # 记录审计日志
            await conn.execute("""
                INSERT INTO audit_logs (action, actor_type, actor_id, target_id, detail)
                VALUES ($1, $2, $3, $4, $5)
            """, "CREATE_CASE", "USER", channel_user_id, case_id, f"Case created via {channel}")
        
        logger.info(f"Case created: {case_id} via {channel} by user {channel_user_id}")
        return case_id
    
    async def get_case_by_id(self, case_id: str) -> Optional[dict]:
        """根据案件ID获取案件详情"""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM cases WHERE case_no = $1 OR case_number = $1
            """, case_id)
            
            if not row:
                return None
                
            case_data = dict(row)
            
            # 获取证据文件
            evidences = await conn.fetch("""
                SELECT * FROM evidences WHERE case_id = $1 ORDER BY uploaded_at DESC
            """, case_data.get('id'))
            
            case_data['evidences'] = [dict(ev) for ev in evidences]
            
            # 获取状态历史
            status_history = await conn.fetch("""
                SELECT * FROM status_history WHERE case_id = $1 ORDER BY changed_at DESC
            """, case_data.get('id'))
            
            case_data['status_history'] = [dict(sh) for sh in status_history]
            
            return case_data
    
    async def update_case_status(self, case_id: str, new_status: str, admin_notes: str = None, changed_by: str = "system") -> bool:
        """更新案件状态"""
        async with self.db.acquire() as conn:
            # 获取当前状态
            current = await conn.fetchrow("SELECT status, id FROM cases WHERE case_no = $1", case_id)
            if not current:
                return False
            
            old_status = current['status']
            case_uuid = current['id']
            
            # 更新案件状态
            await conn.execute("""
                UPDATE cases SET status = $1, admin_notes = $2, updated_at = NOW()
                WHERE case_no = $3
            """, new_status, admin_notes, case_id)
            
            # 记录状态变更历史
            await conn.execute("""
                INSERT INTO status_history (case_id, old_status, new_status, changed_by, note)
                VALUES ($1, $2, $3, $4, $5)
            """, case_uuid, old_status, new_status, changed_by, admin_notes)
            
            # 记录审计日志
            await conn.execute("""
                INSERT INTO audit_logs (action, actor_type, actor_id, target_id, detail)
                VALUES ($1, $2, $3, $4, $5)
            """, "UPDATE_STATUS", "ADMIN", changed_by, case_id, 
                f"Status changed from {old_status} to {new_status}")
        
        logger.info(f"Case {case_id} status updated: {old_status} -> {new_status} by {changed_by}")
        return True
    
    async def get_cases_paginated(self, page: int = 1, limit: int = 20, status: str = None, channel: str = None) -> dict:
        """分页获取案件列表"""
        offset = (page - 1) * limit
        
        where_conditions = []
        params = []
        param_count = 0
        
        if status:
            param_count += 1
            where_conditions.append(f"status = ${param_count}")
            params.append(status)
        
        if channel:
            param_count += 1
            where_conditions.append(f"channel = ${param_count}")
            params.append(channel)
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        async with self.db.acquire() as conn:
            # 获取总数
            count_query = f"SELECT COUNT(*) FROM cases {where_clause}"
            total = await conn.fetchval(count_query, *params)
            
            # 获取分页数据
            param_count += 1
            limit_param = f"${param_count}"
            param_count += 1
            offset_param = f"${param_count}"
            
            data_query = f"""
                SELECT case_no, channel, platform, amount, coin, status, created_at, updated_at
                FROM cases {where_clause}
                ORDER BY created_at DESC
                LIMIT {limit_param} OFFSET {offset_param}
            """
            
            rows = await conn.fetch(data_query, *params, limit, offset)
            cases = [dict(row) for row in rows]
        
        return {
            'cases': cases,
            'total': total,
            'page': page,
            'limit': limit,
            'total_pages': (total + limit - 1) // limit
        }
    
    async def process_user_input(self, user_id: str, channel: str, message_type: str, content: str) -> Optional[dict]:
        """
        处理用户输入 - 统一的消息处理逻辑
        
        Args:
            user_id: 用户ID
            channel: 渠道类型
            message_type: 消息类型 ('text', 'photo', 'document')
            content: 消息内容
            
        Returns:
            response: 响应内容字典，None表示无需响应
        """
        # 获取用户会话状态
        session_key = f"{channel}:{user_id}"
        session = self._user_sessions.get(session_key, {})
        current_state = session.get('state')
        
        # 根据当前状态处理输入
        if current_state is None:
            # 无状态，处理命令或显示主菜单
            return await self._handle_main_menu(user_id, channel, content)
        
        elif current_state.startswith('CRS01_'):
            # CRS-01 身份验证步骤
            return await self._handle_crs01_input(user_id, channel, current_state, content, session)
        
        elif current_state.startswith('CRS02_'):
            # CRS-02 交易数据步骤
            return await self._handle_crs02_input(user_id, channel, current_state, content, session)
        
        elif current_state.startswith('CRS03_'):
            # CRS-03 平台信息步骤
            return await self._handle_crs03_input(user_id, channel, current_state, content, session)
        
        elif current_state == 'VERIFY_SIGNATURE':
            # 签名验证
            return await self._handle_signature_verification(user_id, channel, content, session)
        
        else:
            # 未知状态，重置到主菜单
            self._clear_user_session(session_key)
            return await self._handle_main_menu(user_id, channel, content)
    
    async def _handle_main_menu(self, user_id: str, channel: str, content: str) -> dict:
        """处理主菜单交互"""
        if content.lower() in ['/start', 'start', '开始', 'begin']:
            return await self.content.render_template('welcome_message', channel, {
                'user_id': user_id
            })
        
        elif content.lower() in ['case reporting', '案件报告', '报案']:
            # 开始案件报告流程
            session_key = f"{channel}:{user_id}"
            self._user_sessions[session_key] = {'state': 'CRS01_FULLNAME', 'data': {}}
            
            return await self.content.render_template('crs01_name_prompt', channel, {})
        
        elif content.lower() in ['case tracking', '案件查询', '查询']:
            return await self.content.render_template('case_tracking_prompt', channel, {})
        
        else:
            return await self.content.render_template('unknown_command', channel, {
                'command': content
            })
    
    async def _handle_crs01_input(self, user_id: str, channel: str, state: str, content: str, session: dict) -> dict:
        """处理CRS-01身份验证输入"""
        session_key = f"{channel}:{user_id}"
        
        if state == 'CRS01_FULLNAME':
            # 验证姓名
            if len(content.strip()) < 2:
                return await self.content.render_template('crs01_name_invalid', channel, {})
            
            session['data']['fullname'] = content.strip()
            session['state'] = 'CRS01_ADDRESS'
            self._user_sessions[session_key] = session
            
            return await self.content.render_template('crs01_address_prompt', channel, {
                'fullname': content.strip()
            })
        
        elif state == 'CRS01_ADDRESS':
            # 验证地址
            session['data']['address'] = content.strip()
            session['state'] = 'CRS01_PHONE'
            self._user_sessions[session_key] = session
            
            return await self.content.render_template('crs01_phone_prompt', channel, {})
        
        elif state == 'CRS01_PHONE':
            # 验证电话
            session['data']['phone'] = content.strip()
            session['state'] = 'CRS01_EMAIL'
            self._user_sessions[session_key] = session
            
            return await self.content.render_template('crs01_email_prompt', channel, {})
        
        elif state == 'CRS01_EMAIL':
            # 验证邮箱
            if '@' not in content or '.' not in content:
                return await self.content.render_template('crs01_email_invalid', channel, {})
            
            session['data']['email'] = content.strip()
            session['state'] = 'CRS02_TXID'
            self._user_sessions[session_key] = session
            
            return await self.content.render_template('crs02_txid_prompt', channel, {})
        
        return None
    
    async def _handle_signature_verification(self, user_id: str, channel: str, signature: str, session: dict) -> dict:
        """处理签名验证"""
        session_key = f"{channel}:{user_id}"
        case_data = session.get('data', {})
        
        # 验证签名
        is_valid = await self.signature.verify_signature(signature, case_data, user_id)
        
        if is_valid:
            # 签名有效，创建案件
            try:
                case_id = await self.create_case(case_data, channel, user_id)
                
                # 清除会话
                self._clear_user_session(session_key)
                
                return await self.content.render_template('case_created_success', channel, {
                    'case_id': case_id
                })
            
            except Exception as e:
                logger.error(f"Failed to create case: {e}")
                return await self.content.render_template('case_creation_failed', channel, {})
        
        else:
            return await self.content.render_template('signature_invalid', channel, {})
    
    def _clear_user_session(self, session_key: str):
        """清除用户会话"""
        self._user_sessions.pop(session_key, None)
    
    async def _generate_case_id(self) -> str:
        """生成唯一的案件ID"""
        while True:
            # 生成格式: IC3-YYYY-XXXXXX
            year = datetime.now().year
            random_part = str(uuid.uuid4()).replace('-', '')[:6].upper()
            case_id = f"IC3-{year}-{random_part}"
            
            # 检查是否已存在
            async with self.db.acquire() as conn:
                exists = await conn.fetchval(
                    "SELECT 1 FROM cases WHERE case_no = $1 OR case_number = $1", 
                    case_id
                )
                if not exists:
                    return case_id
    
    def _validate_case_data(self, data: dict) -> dict:
        """验证案件数据"""
        errors = []
        required_fields = ['fullname', 'platform', 'amount']
        
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Missing required field: {field}")
        
        # 验证金额格式
        amount = data.get('amount')
        if amount:
            try:
                float(str(amount).replace(',', ''))
            except (ValueError, TypeError):
                errors.append("Invalid amount format")
        
        # 验证邮箱格式
        email = data.get('email')
        if email and ('@' not in email or '.' not in email):
            errors.append("Invalid email format")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def _build_pdf_snapshot(self, user_data: dict, case_id: str) -> dict:
        """构建PDF快照数据"""
        return {
            "case_no": case_id,
            "registered": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "uid": user_data.get('user_id', ''),
            "fullname": user_data.get('fullname', '—'),
            "address": user_data.get('address', '—'),
            "phone": user_data.get('phone', '—'),
            "email": user_data.get('email', '—'),
            "amount": user_data.get('amount', '0'),
            "coin": user_data.get('coin', ''),
            "incident_time": user_data.get('incident_time', 'Not specified'),
            "tx_hash": user_data.get('tx_hash', '—'),
            "victim_wallet": user_data.get('victim_wallet', '—'),
            "wallet_addr": user_data.get('wallet_addr', '—'),
            "chain_type": user_data.get('chain_type', '—'),
            "platform": user_data.get('platform', '—'),
            "scammer_id": user_data.get('scammer_id', '—'),
            "incident_story": user_data.get('incident_story', '—'),
        }
