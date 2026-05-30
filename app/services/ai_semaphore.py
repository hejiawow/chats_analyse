# -*- coding: utf-8 -*-
"""AI并发控制 - Redis分布式信号量"""
import logging
import time
import uuid
from typing import Optional

import redis

from config import settings


class AISemaphore:
    """Redis-based distributed semaphore for AI API rate limiting

    Uses Redis sorted sets for fair queuing with timestamps.
    Automatically cleans up expired entries to prevent slot leakage.
    """

    _logger = logging.getLogger(__name__)

    SEMAPHORE_KEY = "ai:semaphore"
    SEMAPHORE_TTL = 300  # 5 minutes TTL for safety cleanup

    def __init__(self, max_concurrent: int = 2, timeout: int = 300):
        """
        Initialize semaphore

        Args:
            max_concurrent: Maximum concurrent AI calls (default: 2)
            timeout: Maximum wait time in seconds (default: 300)
        """
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=5,
        )
        # Unique identifier for this semaphore instance
        self.identifier = str(uuid.uuid4())

    def acquire(self) -> bool:
        """
        Acquire a semaphore slot. Blocks until slot available or timeout.

        Returns:
            bool: True if acquired, False if timeout
        """
        start_time = time.time()
        semaphore_key = self.SEMAPHORE_KEY

        # 首次加入队列（之后保持在队列中等待）
        self.redis_client.zadd(
            semaphore_key,
            {self.identifier: time.time()}
        )

        while True:
            try:
                # Clean up expired entries (older than TTL)
                cutoff = time.time() - self.SEMAPHORE_TTL
                self.redis_client.zremrangebyscore(semaphore_key, '-inf', cutoff)

                # Check our position in queue (rank 0 = first)
                rank = self.redis_client.zrank(semaphore_key, self.identifier)

                if rank is not None and rank < self.max_concurrent:
                    # We're in the top N slots - acquired!
                    return True

                # Check timeout before waiting
                if time.time() - start_time > self.timeout:
                    # Timeout - remove ourselves and return False
                    self.redis_client.zrem(semaphore_key, self.identifier)
                    return False

                # Wait before checking again (stay in queue)
                time.sleep(0.5)

            except Exception as e:
                try:
                    self.redis_client.zrem(semaphore_key, self.identifier)
                except:
                    pass
                self._logger.error(f"AI Semaphore Redis error: {e}, rejecting call")
                return False

    def release(self):
        """Release the semaphore slot"""
        try:
            self.redis_client.zrem(self.SEMAPHORE_KEY, self.identifier)
        except Exception as e:
            self._logger.error(f"AI Semaphore release error: {e}")

    def __enter__(self):
        """Context manager entry"""
        acquired = self.acquire()
        if not acquired:
            raise TimeoutError("AI Semaphore acquisition timeout - waited too long for slot")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.release()
        return False


# Global semaphore instance (lazy initialization)
_ai_semaphore: Optional[AISemaphore] = None


def get_ai_semaphore() -> AISemaphore:
    """Get or create the global AI semaphore instance

    Uses settings.AI_MAX_CONCURRENT for max concurrent calls.
    """
    global _ai_semaphore
    if _ai_semaphore is None:
        max_concurrent = getattr(settings, 'AI_MAX_CONCURRENT', 2)
        timeout = getattr(settings, 'AI_SEMAPHORE_TIMEOUT', 300)
        _ai_semaphore = AISemaphore(max_concurrent=max_concurrent, timeout=timeout)
    return _ai_semaphore