# -*- coding: utf-8 -*-
"""全局配置"""
import os
import sys
from datetime import datetime, timezone, timedelta

# 强制使用 UTF-8 编码（解决 Windows 中文系统 psycopg2 编码问题）
os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.platform == 'win32':
    os.environ['PGCLIENTENCODING'] = 'UTF8'

from pydantic_settings import BaseSettings


# 东八区时区常量（UTC+8）
TZ_SHANGHAI = timezone(timedelta(hours=8))


def now_shanghai() -> datetime:
    """获取东八区当前时间（带时区信息）"""
    return datetime.now(TZ_SHANGHAI)


def to_naive_shanghai(dt: datetime) -> datetime:
    """将带时区的 datetime 转换为东八区 naive datetime（用于数据库存储）"""
    if dt.tzinfo is None:
        return dt  # 已经是 naive，假设是东八区
    return dt.astimezone(TZ_SHANGHAI).replace(tzinfo=None)


class Settings(BaseSettings):
    # 虎鲸 API
    HUJING_APP_ID: str = ""
    HUJING_APP_KEY: str = ""
    HUJING_API_BASE_URL: str = ""

    # 虎鲸 Chat Pairs API（批量质检专用）
    HUJING_CHAT_API_URL: str = ""
    HUJING_CHAT_API_KEY: str = ""

    # AI (DashScope)
    DASHSCOPE_API_KEY: str = ""
    AI_MODEL: str = "qwen-plus"
    AI_API_URL: str = ""

    # AI Concurrency Control (分布式信号量限制并发调用)
    AI_MAX_CONCURRENT: int = 2  # 最大并发 AI 调用数（免费版 DashScope 只允许 1）
    AI_SEMAPHORE_TIMEOUT: int = 360  # 获取信号量超时时间（秒）

    # 质检检测聊天记录配置
    QUALITY_CHECK_CHAT_DAYS: int = 7  # 质检检测默认往前查询天数
    QUALITY_CHECK_MAX_CHAT_RECORDS: int = 1000  # 质检检测最大聊天记录条数

    # Embedding (DashScope)
    EMBEDDING_MODEL: str = "text-embedding-v3"
    EMBEDDING_DIMENSIONS: int = 1024

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # PostgreSQL
    DATABASE_URL: str = ""
    DATABASE_URL_SYNC: str = ""

    # Quality Check
    QUALITY_CHECK_CHAT_DAYS: int = 1
    QUALITY_CHECK_MAX_CHAT_RECORDS: int = 500

    # JWT
    JWT_SECRET_KEY: str = ""

    # Open API
    OPEN_API_KEY: str = ""

    # Open API
    OPEN_API_KEY: str = ""

    # 沟通记录 API（新数据源）
    COMMUNICATION_APP_ID: str = ""
    COMMUNICATION_API_BASE_URL: str = ""   # 接口 base URL
    COMMUNICATION_API_KEY: str = ""        # 认证 key（如有）

    # Open API (外部开放接口)
    OPEN_API_KEY: str = ""

    # 钉钉在线表格 API
    DINGTALK_APP_KEY: str = ""
    DINGTALK_APP_SECRET: str = ""
    DINGTALK_WORKBOOK_ID: str = ""
    DINGTALK_SHEET_ID: str = ""
    DINGTALK_OPERATOR_UNION_ID: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()