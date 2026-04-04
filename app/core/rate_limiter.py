import time
import json
import logging
import asyncio
from typing import Optional
from collections import defaultdict

from app.core.config import config

logger = logging.getLogger(__name__)


class RedisRateLimiter:
    """Redis-backed rate limiter"""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(self.redis_url, decode_responses=True)
            except ImportError:
                logger.warning("redis package not installed, falling back to memory")
                return None
        return self._redis

    async def is_allowed(self, key: str, action: str) -> bool:
        r = await self._get_redis()
        if not r:
            return True  # allow if redis unavailable

        limits = {
            "register": config.RATE_LIMIT_REGISTER,
            "login": config.RATE_LIMIT_LOGIN,
            "create_link": config.RATE_LIMIT_CREATE_LINK,
            "redirect": config.RATE_LIMIT_REDIRECT,
        }
        limit = limits.get(action, 50)
        window = config.RATE_LIMIT_WINDOW_HOURS * 3600
        redis_key = f"rl:{action}:{key}"

        try:
            count = await r.incr(redis_key)
            if count == 1:
                await r.expire(redis_key, window)
            return count <= limit
        except Exception:
            return True

    async def get_remaining(self, key: str, action: str) -> int:
        r = await self._get_redis()
        if not r:
            return 999
        limits = {"register": config.RATE_LIMIT_REGISTER, "login": config.RATE_LIMIT_LOGIN, "create_link": config.RATE_LIMIT_CREATE_LINK, "redirect": config.RATE_LIMIT_REDIRECT}
        limit = limits.get(action, 50)
        try:
            count = await r.get(f"rl:{action}:{key}")
            return max(0, limit - int(count or 0))
        except Exception:
            return limit

    async def close(self):
        if self._redis:
            await self._redis.close()


class MemoryRateLimiter:
    """In-memory rate limiter (fallback)"""

    def __init__(self):
        self._counts: dict = defaultdict(lambda: {"count": 0, "reset_at": 0})

    async def is_allowed(self, key: str, action: str) -> bool:
        limits = {"register": config.RATE_LIMIT_REGISTER, "login": config.RATE_LIMIT_LOGIN, "create_link": config.RATE_LIMIT_CREATE_LINK, "redirect": config.RATE_LIMIT_REDIRECT}
        limit = limits.get(action, 50)
        window = config.RATE_LIMIT_WINDOW_HOURS * 3600
        rk = f"{action}:{key}"
        now = time.time()
        entry = self._counts[rk]

        if now > entry["reset_at"]:
            entry["count"] = 0
            entry["reset_at"] = now + window

        entry["count"] += 1
        return entry["count"] <= limit

    async def get_remaining(self, key: str, action: str) -> int:
        limits = {"register": config.RATE_LIMIT_REGISTER, "login": config.RATE_LIMIT_LOGIN, "create_link": config.RATE_LIMIT_CREATE_LINK, "redirect": config.RATE_LIMIT_REDIRECT}
        limit = limits.get(action, 50)
        rk = f"{action}:{key}"
        entry = self._counts.get(rk, {"count": 0, "reset_at": 0})
        if time.time() > entry["reset_at"]:
            return limit
        return max(0, limit - entry["count"])

    async def close(self):
        pass


def create_rate_limiter():
    """Factory: create rate limiter based on config"""
    if config.redis_enabled:
        logger.info("Using Redis rate limiter")
        return RedisRateLimiter(config.REDIS_URL)
    else:
        logger.info("Using in-memory rate limiter")
        return MemoryRateLimiter()


rate_limiter = None  # initialized at app startup
