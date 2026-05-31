# -*- coding: utf-8 -*-
"""审计日志服务 — 记录关键业务操作"""
from typing import Optional

from app.services.system_log_service import log_service


class AuditService:
    """审计日志服务"""

    async def log_login(
        self,
        user_id: Optional[int],
        username: str,
        ip_address: str,
        success: bool = True,
        failure_reason: Optional[str] = None,
    ):
        """记录登录操作 - 登录失败时立即写入"""
        await log_service.write_log(
            log_type="audit",
            log_level="info" if success else "warning",
            user_id=user_id if success else None,
            username=username,
            action="login" if success else "login_failed",
            resource_type="session",
            action_detail={
                "success": success,
                "ip_address": ip_address,
                "failure_reason": failure_reason,
            },
            ip_address=ip_address,
            immediate=not success,  # 登录失败时立即写入
        )

    async def log_logout(self, user_id: int, username: str, ip_address: str):
        """记录登出操作"""
        await log_service.write_log(
            log_type="audit",
            log_level="info",
            user_id=user_id,
            username=username,
            action="logout",
            resource_type="session",
            ip_address=ip_address,
        )

    async def log_trigger_analysis(
        self,
        user_id: int,
        username: str,
        task_id: str,
        agent: str,
        datasource: str,
        target_user_id: str,
        target_friend_id: int,
        ip_address: str,
    ):
        """记录触发分析操作"""
        await log_service.write_log(
            log_type="audit",
            log_level="info",
            user_id=user_id,
            username=username,
            action="trigger_analysis",
            resource_type="analysis_task",
            resource_id=task_id,
            action_detail={
                "agent": agent,
                "datasource": datasource,
                "target_user_id": target_user_id,
                "target_friend_id": target_friend_id,
            },
            related_task_id=task_id,
            ip_address=ip_address,
        )

    async def log_batch_quality_check(
        self,
        user_id: int,
        username: str,
        task_id: str,
        time_range: dict,
        limit: int,
        ip_address: str,
    ):
        """记录批量质检触发"""
        await log_service.write_log(
            log_type="audit",
            log_level="info",
            user_id=user_id,
            username=username,
            action="trigger_batch_quality_check",
            resource_type="batch_task",
            resource_id=task_id,
            action_detail={
                "time_range": time_range,
                "limit": limit,
            },
            related_task_id=task_id,
            ip_address=ip_address,
        )

    async def log_cancel_task(
        self,
        user_id: int,
        username: str,
        task_id: str,
        task_type: str,
        ip_address: str,
    ):
        """记录任务取消操作"""
        await log_service.write_log(
            log_type="audit",
            log_level="warning",
            user_id=user_id,
            username=username,
            action="cancel_task",
            resource_type="task",
            resource_id=task_id,
            action_detail={
                "task_type": task_type,
            },
            related_task_id=task_id,
            ip_address=ip_address,
        )

    async def log_create_user(
        self,
        operator_id: int,
        operator_name: str,
        created_user_id: int,
        created_username: str,
        ip_address: str,
    ):
        """记录创建用户操作"""
        await log_service.write_log(
            log_type="audit",
            log_level="info",
            user_id=operator_id,
            username=operator_name,
            action="create_user",
            resource_type="user",
            resource_id=str(created_user_id),
            action_detail={
                "created_username": created_username,
            },
            ip_address=ip_address,
        )

    async def log_update_user(
        self,
        operator_id: int,
        operator_name: str,
        target_user_id: int,
        changes: dict,
        ip_address: str,
    ):
        """记录更新用户操作"""
        await log_service.write_log(
            log_type="audit",
            log_level="info",
            user_id=operator_id,
            username=operator_name,
            action="update_user",
            resource_type="user",
            resource_id=str(target_user_id),
            action_detail={
                "changes": changes,
            },
            ip_address=ip_address,
        )

    async def log_delete_user(
        self,
        operator_id: int,
        operator_name: str,
        deleted_user_id: int,
        deleted_username: str,
        ip_address: str,
    ):
        """记录删除用户操作"""
        await log_service.write_log(
            log_type="audit",
            log_level="warning",
            user_id=operator_id,
            username=operator_name,
            action="delete_user",
            resource_type="user",
            resource_id=str(deleted_user_id),
            action_detail={
                "deleted_username": deleted_username,
            },
            ip_address=ip_address,
        )

    async def log_assign_roles(
        self,
        operator_id: int,
        operator_name: str,
        target_user_id: int,
        role_ids: list,
        ip_address: str,
    ):
        """记录角色分配操作"""
        await log_service.write_log(
            log_type="audit",
            log_level="info",
            user_id=operator_id,
            username=operator_name,
            action="assign_roles",
            resource_type="user",
            resource_id=str(target_user_id),
            action_detail={
                "role_ids": role_ids,
            },
            ip_address=ip_address,
        )

    async def log_create_role(
        self,
        operator_id: int,
        operator_name: str,
        role_id: int,
        role_name: str,
        permissions: list,
        ip_address: str,
    ):
        """记录创建角色操作"""
        await log_service.write_log(
            log_type="audit",
            log_level="info",
            user_id=operator_id,
            username=operator_name,
            action="create_role",
            resource_type="role",
            resource_id=str(role_id),
            action_detail={
                "role_name": role_name,
                "permissions": permissions,
            },
            ip_address=ip_address,
        )

    async def log_update_role(
        self,
        operator_id: int,
        operator_name: str,
        role_id: int,
        role_name: str,
        changes: dict,
        ip_address: str,
    ):
        """记录更新角色操作"""
        await log_service.write_log(
            log_type="audit",
            log_level="info",
            user_id=operator_id,
            username=operator_name,
            action="update_role",
            resource_type="role",
            resource_id=str(role_id),
            action_detail={
                "role_name": role_name,
                "changes": changes,
            },
            ip_address=ip_address,
        )

    async def log_delete_role(
        self,
        operator_id: int,
        operator_name: str,
        role_id: int,
        role_name: str,
        ip_address: str,
    ):
        """记录删除角色操作"""
        await log_service.write_log(
            log_type="audit",
            log_level="warning",
            user_id=operator_id,
            username=operator_name,
            action="delete_role",
            resource_type="role",
            resource_id=str(role_id),
            action_detail={
                "role_name": role_name,
            },
            ip_address=ip_address,
        )

    async def log_keyword_change(
        self,
        operator_id: int,
        operator_name: str,
        action: str,
        keyword_id: int,
        keyword: str,
        changes: Optional[dict] = None,
        ip_address: str = None,
    ):
        """记录关键词配置变更"""
        await log_service.write_log(
            log_type="audit",
            log_level="info",
            user_id=operator_id,
            username=operator_name,
            action=f"{action}_keyword",
            resource_type="keyword",
            resource_id=str(keyword_id),
            action_detail={
                "keyword": keyword,
                "changes": changes,
            },
            ip_address=ip_address,
        )


# 全局实例
audit_service = AuditService()