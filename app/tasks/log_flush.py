# -*- coding: utf-8 -*-
"""日志刷新任务 — 定时将 Redis 缓冲队列写入数据库"""
from app.celery_app import celery_app
from app.services.system_log_service import log_service


@celery_app.task(name="app.tasks.log_flush.flush_logs")
def flush_logs():
    """定时刷新日志缓冲队列到数据库"""
    count = log_service.flush_sync()
    return {"flushed": count}