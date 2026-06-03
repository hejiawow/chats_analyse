# -*- coding: utf-8 -*-
"""全局配置"""
import os
import sys
import dotenv
dotenv.load_dotenv()

# 强制使用 UTF-8 编码（解决 Windows 中文系统 psycopg2 编码问题）
os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.platform == 'win32':
    os.environ['PGCLIENTENCODING'] = 'UTF8'

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 虎鲸 API
    HUJING_APP_ID: str = os.getenv("HUJING_APP_ID")
    HUJING_APP_KEY: str = os.getenv("HUJING_APP_KEY")
    HUJING_API_BASE_URL: str = os.getenv("HUJING_API_BASE_URL")

    # 虎鲸文件服务URL（用于语音文件访问）
    # 默认从API基础URL推断，如 https://hj.ahujiaoyu.com:9029 -> https://hj.ahujiaoyu.com
    HUJING_FILE_BASE_URL: str = os.getenv("HUJING_FILE_BASE_URL", "")

    # 虎鲸 Chat Pairs API（批量质检专用）
    HUJING_CHAT_API_URL: str = os.getenv("HUJING_CHAT_API_URL")
    HUJING_CHAT_API_KEY: str = os.getenv("HUJING_CHAT_API_KEY")

    # AI (DashScope)
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY")
    AI_MODEL: str = os.getenv("AI_MODEL")
    AI_API_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # AI Concurrency Control (分布式信号量限制并发调用)
    AI_MAX_CONCURRENT: int = 2  # 最大并发 AI 调用数（免费版 DashScope 只允许 1）
    AI_SEMAPHORE_TIMEOUT: int = 300  # 获取信号量超时时间（秒）

    # Embedding (DashScope)
    EMBEDDING_MODEL: str = "text-embedding-v3"
    EMBEDDING_DIMENSIONS: int = 1024

    # ASR (Fun-ASR)
    # ASR服务基础URL
    ASR_BASE_URL: str = os.getenv("ASR_BASE_URL", "https://dashscope.aliyuncs.com/api/v1")
    # ASR提交任务接口路径
    ASR_SUBMIT_PATH: str = os.getenv("ASR_SUBMIT_PATH", "/services/audio/asr/transcription")
    # ASR查询任务接口路径
    ASR_QUERY_PATH: str = os.getenv("ASR_QUERY_PATH", "/tasks")
    # ASR模型名称: fun-asr, paraformer-v1, qwen3-asr-flash等
    ASR_MODEL: str = os.getenv("ASR_MODEL", "fun-asr")
    # ASR请求超时时间(秒)
    ASR_TIMEOUT: int = int(os.getenv("ASR_TIMEOUT", "30"))
    # ASR轮询最大重试次数
    ASR_MAX_RETRIES: int = int(os.getenv("ASR_MAX_RETRIES", "60"))
    # ASR轮询间隔(秒)
    ASR_POLL_INTERVAL: int = int(os.getenv("ASR_POLL_INTERVAL", "2"))
    # ASR默认语言: zh, en, ja等
    ASR_DEFAULT_LANGUAGE: str = os.getenv("ASR_DEFAULT_LANGUAGE", "zh")
    # ASR音频通道ID
    ASR_CHANNEL_ID: int = int(os.getenv("ASR_CHANNEL_ID", "0"))
    # ASR批量并发数（控制同时处理的语音数量）
    ASR_MAX_WORKERS: int = int(os.getenv("ASR_MAX_WORKERS", "5"))

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # PostgreSQL
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    DATABASE_URL_SYNC: str = os.getenv("DATABASE_URL_SYNC")

    # JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
