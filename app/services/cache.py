# -*- coding: utf-8 -*-
"""Redis 缓存工具"""
import json
import redis
from typing import Any, Optional

from config import settings

_redis_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    """获取 Redis 客户端（单例）"""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=5,
            )
            _redis_client.ping()
        except Exception:
            _redis_client = None  # Redis 不可用时降级为无缓存
    return _redis_client


def cache_get(key: str) -> Any | None:
    """从缓存读取，失败返回 None"""
    client = get_redis()
    if client is None:
        return None
    try:
        val = client.get(key)
        if val is not None:
            return json.loads(val)
    except Exception:
        pass
    return None


def cache_set(key: str, value: Any, ttl: int = 3600) -> None:
    """写入缓存，默认 5 分钟过期"""
    client = get_redis()
    if client is None:
        return
    try:
        client.setex(key, ttl, json.dumps(value, ensure_ascii=False))
    except Exception:
        pass


def cache_delete(key: str) -> None:
    """删除缓存"""
    client = get_redis()
    if client is None:
        return
    try:
        client.delete(key)
    except Exception:
        pass


def cache_clear_pattern(pattern: str) -> int:
    """清理匹配 pattern 的所有 key，返回删除数量"""
    client = get_redis()
    if client is None:
        return 0
    try:
        keys = client.keys(pattern)
        if keys:
            return client.delete(*keys)
    except Exception:
        pass
    return 0
