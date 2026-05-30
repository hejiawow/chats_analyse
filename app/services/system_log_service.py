# -*- coding: utf-8 -*-
"""系统日志服务 — 支持异步写入、批量刷新、查询、统计"""
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import redis
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.models.database import async_session, sync_engine
from app.models.system_log import SystemLog
from config import settings

logger = logging.getLogger(__name__)

# Redis 缓冲队列
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
LOG_BUFFER_KEY = "system:log:buffer"
LOG_BUFFER_SIZE = 100  # 达到此数量触发批量写入


class SystemLogService:
    """系统日志服务"""

    async def write_log(
        self,
        log_type: str,
        log_level: str = "info",
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        request_method: Optional[str] = None,
        request_path: Optional[str] = None,
        request_query: Optional[str] = None,
        request_body: Optional[str] = None,
        response_status: Optional[int] = None,
        response_time_ms: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        action_detail: Optional[dict] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        error_stacktrace: Optional[str] = None,
        related_task_id: Optional[str] = None,
        extra_data: Optional[dict] = None,
        immediate: bool = False,
    ):
        """写入日志 - 默认写入 Redis 缓冲队列，immediate=True 时立即写入数据库"""
        log_entry = {
            "log_type": log_type,
            "log_level": log_level,
            "created_at": datetime.now(),
            "user_id": user_id,
            "username": username,
            "request_method": request_method,
            "request_path": request_path,
            "request_query": request_query,
            "request_body": request_body,
            "response_status": response_status,
            "response_time_ms": response_time_ms,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action_detail": action_detail,
            "error_type": error_type,
            "error_message": error_message,
            "error_stacktrace": error_stacktrace,
            "related_task_id": related_task_id,
            "extra_data": extra_data,
        }

        if immediate:
            # 立即写入数据库（用于关键日志如登录失败）
            await self._write_immediate(log_entry)
        else:
            # 写入 Redis 缓冲队列
            log_entry["created_at"] = log_entry["created_at"].isoformat()
            redis_client.rpush(LOG_BUFFER_KEY, json.dumps(log_entry, ensure_ascii=False))

            # 检查是否达到批量写入阈值
            buffer_size = redis_client.llen(LOG_BUFFER_KEY)
            if buffer_size >= LOG_BUFFER_SIZE:
                asyncio.create_task(self._flush_to_db())

    async def _write_immediate(self, log_data: dict):
        """立即写入单条日志到数据库"""
        async with async_session() as session:
            try:
                log = SystemLog(**log_data)
                session.add(log)
                await session.commit()
            except Exception as e:
                logger.error(f"Failed to write log immediately: {e}")

    def flush_sync(self):
        """同步刷新 Redis 缓冲队列到数据库 (供 Celery 调用)"""
        # 使用 Lua 脚本原子性地获取并清空队列
        lua_script = """
        local logs = redis.call('LRANGE', KEYS[1], 0, -1)
        redis.call('DEL', KEYS[1])
        return logs
        """
        logs_json = redis_client.eval(lua_script, 1, LOG_BUFFER_KEY)

        if not logs_json:
            return 0

        # 批量写入数据库
        with Session(sync_engine) as session:
            try:
                count = 0
                for log_json in logs_json:
                    log_data = json.loads(log_json)
                    log_data["created_at"] = datetime.fromisoformat(log_data["created_at"])
                    log = SystemLog(**log_data)
                    session.add(log)
                    count += 1
                session.commit()
                return count
            except Exception as e:
                logger.error(f"Failed to flush logs to DB: {e}")
                session.rollback()
                return 0

    async def _flush_to_db(self):
        """异步刷新 Redis 缓冲队列到数据库"""
        return self.flush_sync()

    async def query_logs(
        self,
        log_type: Optional[str] = None,
        log_level: Optional[str] = None,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[SystemLog], int]:
        """查询日志"""
        async with async_session() as session:
            # 构建查询条件
            conditions = []
            if log_type:
                conditions.append(SystemLog.log_type == log_type)
            if log_level:
                conditions.append(SystemLog.log_level == log_level)
            if user_id:
                conditions.append(SystemLog.user_id == user_id)
            if username:
                conditions.append(SystemLog.username.ilike(f"%{username}%"))
            if action:
                conditions.append(SystemLog.action == action)
            if resource_type:
                conditions.append(SystemLog.resource_type == resource_type)
            if start_time:
                conditions.append(SystemLog.created_at >= start_time)
            if end_time:
                conditions.append(SystemLog.created_at <= end_time)

            # 查询总数
            count_stmt = select(func.count(SystemLog.id))
            if conditions:
                count_stmt = count_stmt.where(and_(*conditions))
            total = (await session.execute(count_stmt)).scalar()

            # 分页查询
            stmt = select(SystemLog)
            if conditions:
                stmt = stmt.where(and_(*conditions))
            stmt = stmt.order_by(SystemLog.created_at.desc())
            stmt = stmt.offset((page - 1) * page_size).limit(page_size)

            result = await session.execute(stmt)
            logs = result.scalars().all()

            return list(logs), total or 0

    async def get_log_statistics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        group_by: str = "log_type",
    ) -> List[Dict[str, Any]]:
        """获取日志统计"""
        async with async_session() as session:
            # 构建时间条件
            conditions = []
            if start_time:
                conditions.append(SystemLog.created_at >= start_time)
            if end_time:
                conditions.append(SystemLog.created_at <= end_time)

            # 分组统计
            if group_by == "log_type":
                stmt = select(
                    SystemLog.log_type,
                    func.count(SystemLog.id).label("count")
                )
                if conditions:
                    stmt = stmt.where(and_(*conditions))
                stmt = stmt.group_by(SystemLog.log_type)
            elif group_by == "log_level":
                stmt = select(
                    SystemLog.log_level,
                    func.count(SystemLog.id).label("count")
                )
                if conditions:
                    stmt = stmt.where(and_(*conditions))
                stmt = stmt.group_by(SystemLog.log_level)
            elif group_by == "user_id":
                stmt = select(
                    SystemLog.user_id,
                    SystemLog.username,
                    func.count(SystemLog.id).label("count")
                )
                if conditions:
                    stmt = stmt.where(and_(*conditions))
                stmt = stmt.group_by(SystemLog.user_id, SystemLog.username)
            elif group_by == "action":
                stmt = select(
                    SystemLog.action,
                    func.count(SystemLog.id).label("count")
                )
                if conditions:
                    stmt = stmt.where(and_(*conditions))
                stmt = stmt.group_by(SystemLog.action)
            else:
                raise ValueError(f"Invalid group_by: {group_by}")

            result = await session.execute(stmt)
            # 使用 ._mapping 获取字典
            return [dict(row._mapping) for row in result.all()]

    async def delete_old_logs(self, days: int = 90) -> int:
        """删除指定天数前的日志"""
        async with async_session() as session:
            cutoff = datetime.now() - timedelta(days=days)
            stmt = select(SystemLog).where(SystemLog.created_at < cutoff)
            result = await session.execute(stmt)
            logs = result.scalars().all()
            count = len(logs)
            for log in logs:
                await session.delete(log)
            await session.commit()
            return count


# 全局实例
log_service = SystemLogService()