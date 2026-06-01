# -*- coding: utf-8 -*-
"""共享日志服务 — 任务实时日志写入 Redis（供 analysis.py 和 batch_quality.py 共用）"""
import json
import logging
from datetime import datetime

import redis
from config import settings

logger = logging.getLogger(__name__)
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

LOGS_KEY_PREFIX = "task:logs:"
DONE_KEY_PREFIX = "task:done:"

LOG_TTL_SECONDS = 7200   # 日志 key 2小时过期（比进度 key 的1小时略长）
DONE_TTL_SECONDS = 3600  # 完成标记1小时过期


def log(task_id: str, message: str, level: str = "info"):
    """向指定任务的日志列表追加一条日志（写入 Redis，自动设置过期时间）"""
    try:
        key = f"{LOGS_KEY_PREFIX}{task_id}"
        log_entry = json.dumps({
            "time": datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "message": message,
        })
        redis_client.rpush(key, log_entry)
        redis_client.expire(key, LOG_TTL_SECONDS)
    except Exception:
        logger.exception(f"Failed to write log for task {task_id}: {message}")


def get_task_logs(task_id: str) -> list[dict]:
    """获取指定任务的日志（从 Redis 读取）"""
    key = f"{LOGS_KEY_PREFIX}{task_id}"
    logs = redis_client.lrange(key, 0, -1)
    result = []
    for log_str in logs:
        try:
            result.append(json.loads(log_str))
        except json.JSONDecodeError:
            pass
    return result


def mark_task_done(task_id: str):
    """标记任务已完成（写入 Redis）"""
    redis_client.set(f"{DONE_KEY_PREFIX}{task_id}", "1", ex=DONE_TTL_SECONDS)


def is_task_done(task_id: str) -> bool:
    """检查任务是否完成（从 Redis 读取）"""
    return redis_client.get(f"{DONE_KEY_PREFIX}{task_id}") == "1"


def clear_task_logs(task_id: str):
    """清理过期日志（从 Redis 删除）"""
    redis_client.delete(f"{LOGS_KEY_PREFIX}{task_id}")
    redis_client.delete(f"{DONE_KEY_PREFIX}{task_id}")
