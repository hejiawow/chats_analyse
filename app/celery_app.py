# -*- coding: utf-8 -*-
"""Celery 配置"""
from celery import Celery
from celery.schedules import crontab

from config import settings

celery_app = Celery(
    "hujing-agent",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # 任务超时设置
    task_time_limit=600,  # 单个任务最大执行时间（秒），超时会被强制终止
    task_soft_time_limit=550,  # 单个任务软超时时间（秒），超时时发送信号
    # 定时任务配置
    beat_schedule={
        "flush-logs-every-30-seconds": {
            "task": "app.tasks.log_flush.flush_logs",
            "schedule": 30.0,  # 每30秒刷新日志缓冲队列
        },
        "auto-quality-review": {
            "task": "auto_quality_review_consumer",
            "schedule": crontab(minute="*/5"),  # 每5分钟触发一次，单次执行（查→处理→退出）
        },
        # 云客数据源定时质检（待 API 就绪后启用）
        # "batch-quality-communication": {
        #     "task": "app.tasks.batch_quality_comm.run_batch_quality_comm",
        #     "schedule": crontab(minute=30, hour="*/2"),  # 每2小时
        # },
    },
)

# 自动发现任务
celery_app.autodiscover_tasks(["app.tasks"])
