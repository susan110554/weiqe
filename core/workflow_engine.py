"""
工作流引擎
案件状态自动化管理和业务流程控制
"""
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """工作流引擎 - 案件状态自动化管理"""
    
    def __init__(self, db_pool=None, notification_service=None):
        self.db = db_pool
        self.notification_service = notification_service
        self._workflows = {}  # 工作流定义
        self._register_default_workflows()
    
    def _register_default_workflows(self):
        """注册默认工作流"""
        self._workflows = {
            'case_created': self._handle_case_created,
            'status_changed': self._handle_status_changed,
            'payment_received': self._handle_payment_received,
            'evidence_uploaded': self._handle_evidence_uploaded,
        }
    
    async def trigger_workflow(self, event_type: str, case_id: str, data: dict) -> bool:
        """
        触发工作流
        
        Args:
            event_type: 事件类型
            case_id: 案件ID
            data: 事件数据
            
        Returns:
            bool: 执行是否成功
        """
        try:
            logger.info(f"Triggering workflow for event {event_type}, case {case_id}")
            
            workflow_handler = self._workflows.get(event_type)
            if workflow_handler:
                return await workflow_handler(case_id, data)
            else:
                logger.warning(f"No workflow handler for event type: {event_type}")
                return False
                
        except Exception as e:
            logger.error(f"Workflow trigger failed: {e}")
            return False
    
    async def _handle_case_created(self, case_id: str, data: dict) -> bool:
        """处理案件创建事件"""
        try:
            # 1. 发送确认通知
            if self.notification_service:
                await self.notification_service.send_notification(
                    user_id=data.get('user_id'),
                    channel=data.get('channel', 'telegram'),
                    notification_type='case_created',
                    data={'case_id': case_id}
                )
            
            # 2. 安排自动状态推进
            await self._schedule_auto_progress(case_id, 'P1_TO_P2', hours=24)
            
            # 3. 记录工作流执行
            await self._log_workflow_execution('case_created', case_id, 'completed')
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to handle case_created for {case_id}: {e}")
            return False
    
    async def _handle_status_changed(self, case_id: str, data: dict) -> bool:
        """处理状态变更事件"""
        try:
            old_status = data.get('old_status')
            new_status = data.get('new_status')
            
            # 发送状态变更通知
            if self.notification_service:
                await self.notification_service.send_notification(
                    user_id=data.get('user_id'),
                    channel=data.get('channel', 'telegram'),
                    notification_type='status_changed',
                    data={
                        'case_id': case_id,
                        'old_status': old_status,
                        'new_status': new_status
                    }
                )
            
            # 根据新状态安排后续操作
            if new_status == '审核中':
                await self._schedule_auto_progress(case_id, 'REVIEW_REMINDER', hours=72)
            elif new_status == '已结案':
                await self._handle_case_closed(case_id, data)
            
            await self._log_workflow_execution('status_changed', case_id, 'completed')
            return True
            
        except Exception as e:
            logger.error(f"Failed to handle status_changed for {case_id}: {e}")
            return False
    
    async def _handle_payment_received(self, case_id: str, data: dict) -> bool:
        """处理支付接收事件"""
        try:
            # 更新案件状态
            if self.db:
                async with self.db.acquire() as conn:
                    await conn.execute("""
                        UPDATE cases SET status = '支付已确认', updated_at = NOW()
                        WHERE case_no = $1
                    """, case_id)
            
            # 发送支付确认通知
            if self.notification_service:
                await self.notification_service.send_notification(
                    user_id=data.get('user_id'),
                    channel=data.get('channel', 'telegram'),
                    notification_type='payment_received',
                    data={'case_id': case_id, 'amount': data.get('amount')}
                )
            
            await self._log_workflow_execution('payment_received', case_id, 'completed')
            return True
            
        except Exception as e:
            logger.error(f"Failed to handle payment_received for {case_id}: {e}")
            return False
    
    async def _handle_evidence_uploaded(self, case_id: str, data: dict) -> bool:
        """处理证据上传事件"""
        try:
            # 更新案件状态为证据已补充
            if self.db:
                async with self.db.acquire() as conn:
                    await conn.execute("""
                        UPDATE cases SET 
                            status = '证据已补充', 
                            admin_notes = COALESCE(admin_notes, '') || ' | 证据已上传',
                            updated_at = NOW()
                        WHERE case_no = $1
                    """, case_id)
            
            # 通知用户证据已收到
            if self.notification_service:
                await self.notification_service.send_notification(
                    user_id=data.get('user_id'),
                    channel=data.get('channel', 'telegram'),
                    notification_type='evidence_received',
                    data={'case_id': case_id, 'file_count': data.get('file_count', 1)}
                )
            
            await self._log_workflow_execution('evidence_uploaded', case_id, 'completed')
            return True
            
        except Exception as e:
            logger.error(f"Failed to handle evidence_uploaded for {case_id}: {e}")
            return False
    
    async def _handle_case_closed(self, case_id: str, data: dict) -> bool:
        """处理案件关闭"""
        try:
            # 清理相关的自动化任务
            await self._cancel_scheduled_tasks(case_id)
            
            # 发送案件关闭通知
            if self.notification_service:
                await self.notification_service.send_notification(
                    user_id=data.get('user_id'),
                    channel=data.get('channel', 'telegram'),
                    notification_type='case_closed',
                    data={'case_id': case_id, 'resolution': data.get('resolution')}
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to handle case_closed for {case_id}: {e}")
            return False
    
    async def _schedule_auto_progress(self, case_id: str, task_type: str, hours: int) -> bool:
        """安排自动进度任务"""
        if not self.db:
            return False
        
        try:
            run_at = datetime.utcnow() + timedelta(hours=hours)
            
            async with self.db.acquire() as conn:
                await conn.execute("""
                    INSERT INTO case_progress_jobs (case_no, kind, run_at, created_at)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (case_no, kind) DO UPDATE SET
                        run_at = $3, created_at = $4
                """, case_id, task_type, run_at, datetime.utcnow())
            
            logger.info(f"Scheduled {task_type} for case {case_id} at {run_at}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to schedule auto progress: {e}")
            return False
    
    async def _cancel_scheduled_tasks(self, case_id: str) -> bool:
        """取消预定任务"""
        if not self.db:
            return False
        
        try:
            async with self.db.acquire() as conn:
                await conn.execute("""
                    DELETE FROM case_progress_jobs WHERE case_no = $1
                """, case_id)
            
            logger.info(f"Cancelled scheduled tasks for case {case_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel scheduled tasks: {e}")
            return False
    
    async def _log_workflow_execution(self, workflow_type: str, case_id: str, status: str) -> None:
        """记录工作流执行日志"""
        if not self.db:
            return
        
        try:
            async with self.db.acquire() as conn:
                await conn.execute("""
                    INSERT INTO audit_logs (action, actor_type, actor_id, target_id, detail)
                    VALUES ($1, $2, $3, $4, $5)
                """, f"WORKFLOW_{workflow_type.upper()}", "SYSTEM", "workflow_engine", 
                    case_id, f"Workflow {workflow_type} {status}")
                    
        except Exception as e:
            logger.error(f"Failed to log workflow execution: {e}")
    
    async def get_workflow_stats(self) -> dict:
        """获取工作流统计信息"""
        if not self.db:
            return {}
        
        try:
            async with self.db.acquire() as conn:
                # 获取待执行任务数量
                pending_tasks = await conn.fetchval("""
                    SELECT COUNT(*) FROM case_progress_jobs 
                    WHERE run_at > NOW()
                """)
                
                # 获取今日执行的工作流数量
                today_workflows = await conn.fetchval("""
                    SELECT COUNT(*) FROM audit_logs 
                    WHERE action LIKE 'WORKFLOW_%' 
                    AND logged_at >= CURRENT_DATE
                """)
                
                return {
                    'pending_tasks': pending_tasks,
                    'today_workflows': today_workflows,
                    'registered_workflows': len(self._workflows)
                }
                
        except Exception as e:
            logger.error(f"Failed to get workflow stats: {e}")
            return {}
