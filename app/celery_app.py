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
    task_time_limit=300,  # 单个任务最大执行时间（秒），超时会被强制终止
    task_soft_time_limit=280,  # 单个任务软超时时间（秒），超时时发送信号
    # 定时任务配置
    beat_schedule={
        "flush-logs-every-30-seconds": {
            "task": "app.tasks.log_flush.flush_logs",
            "schedule": 30.0,  # 每30秒刷新日志缓冲队列
        },
        "auto-quality-review-every-2-hours": {
            "task": "app.tasks.quality_review.auto_quality_review_task",
            # "schedule": crontab(minute=0, hour="*/2"),  # 每2小时执行一次
            "schedule": crontab(minute="*/1", hour=0),  # 每2小时执行一次
        },
    },
)

# 自动发现任务
celery_app.autodiscover_tasks(["app.tasks"])
