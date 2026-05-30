# -*- coding: utf-8 -*-
"""全局配置"""
import os
import sys

# 强制使用 UTF-8 编码（解决 Windows 中文系统 psycopg2 编码问题）
os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.platform == 'win32':
    os.environ['PGCLIENTENCODING'] = 'UTF8'

from pydantic_settings import BaseSettings


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
    AI_API_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # AI Concurrency Control (分布式信号量限制并发调用)
    AI_MAX_CONCURRENT: int = 2  # 最大并发 AI 调用数（免费版 DashScope 只允许 1）
    AI_SEMAPHORE_TIMEOUT: int = 300  # 获取信号量超时时间（秒）

    # Embedding (DashScope)
    EMBEDDING_MODEL: str = "text-embedding-v3"
    EMBEDDING_DIMENSIONS: int = 1024

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # PostgreSQL
    DATABASE_URL: str = ""
    DATABASE_URL_SYNC: str = ""

    # JWT
    JWT_SECRET_KEY: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
