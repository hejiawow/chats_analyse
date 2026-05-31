# -*- coding: utf-8 -*-
"""系统日志模型 — 统一存储 API 访问日志、审计日志、错误日志"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from app.models.database import Base


class SystemLog(Base):
    """系统日志表"""
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # === 日志分类 ===
    log_type = Column(String(32), nullable=False, comment="日志类型: api_access / audit / error")
    log_level = Column(String(16), nullable=False, default="info", comment="日志级别: debug / info / warning / error / critical")

    # === 时间戳 ===
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(), index=True, comment="创建时间")

    # === 用户信息 ===
    user_id = Column(Integer, nullable=True, comment="操作用户ID")
    username = Column(String(64), nullable=True, comment="用户名")

    # === API 访问日志专属字段 ===
    request_method = Column(String(16), nullable=True, comment="HTTP方法: GET / POST / PUT / DELETE")
    request_path = Column(String(512), nullable=True, comment="请求路径")
    request_query = Column(Text, nullable=True, comment="Query参数 (JSON)")
    request_body = Column(Text, nullable=True, comment="请求体 (脱敏后JSON)")
    response_status = Column(Integer, nullable=True, comment="HTTP响应状态码")
    response_time_ms = Column(Integer, nullable=True, comment="响应耗时(毫秒)")
    ip_address = Column(String(64), nullable=True, comment="客户端IP")
    user_agent = Column(String(512), nullable=True, comment="User-Agent")

    # === 审计日志专属字段 ===
    action = Column(String(64), nullable=True, comment="操作类型: login / logout / trigger_analysis / create_user 等")
    resource_type = Column(String(64), nullable=True, comment="资源类型: user / role / analysis_task / keyword 等")
    resource_id = Column(String(128), nullable=True, comment="资源ID")
    action_detail = Column(JSONB, nullable=True, comment="操作详情 (变更前后对比等)")

    # === 错误日志专属字段 ===
    error_type = Column(String(128), nullable=True, comment="异常类型")
    error_message = Column(Text, nullable=True, comment="错误消息")
    error_stacktrace = Column(Text, nullable=True, comment="堆栈跟踪")
    related_task_id = Column(String(64), nullable=True, comment="关联任务ID (Celery task_id)")

    # === 通用字段 ===
    extra_data = Column(JSONB, nullable=True, comment="扩展数据 (灵活存储额外信息)")

    __table_args__ = (
        Index("ix_system_logs_log_type", "log_type"),
        Index("ix_system_logs_user_id", "user_id"),
        Index("ix_system_logs_action", "action"),
        Index("ix_system_logs_log_type_level", "log_type", "log_level"),
        Index("ix_system_logs_user_created", "user_id", "created_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "log_type": self.log_type,
            "log_level": self.log_level,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "user_id": self.user_id,
            "username": self.username,
            "request_method": self.request_method,
            "request_path": self.request_path,
            "request_query": self.request_query,
            "request_body": self.request_body,
            "response_status": self.response_status,
            "response_time_ms": self.response_time_ms,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action_detail": self.action_detail,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "error_stacktrace": self.error_stacktrace,
            "related_task_id": self.related_task_id,
            "extra_data": self.extra_data,
        }