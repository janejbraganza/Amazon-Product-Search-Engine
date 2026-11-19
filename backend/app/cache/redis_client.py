"""Redis connection management.

One client per process, created lazily from REDIS_URL. The client keeps a small pool of
connections and opens them on first use, so creating it never touches the network.

Timeouts are short and automatic retries are disabled: on this machine an unreachable
Redis took about 6.4 s to fail with redis-py's default retries versus about 0.25 s without.
A cache must never make a search slower than not having a cache.
"""

from functools import lru_cache

import redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from app.core.config import Settings, get_settings


def create_redis_client(settings: Settings) -> redis.Redis:
    return redis.Redis.from_url(
        settings.redis_url,  # credentials (if any) come from the URL in .env, never from code
        socket_connect_timeout=settings.redis_timeout_seconds,
        socket_timeout=settings.redis_timeout_seconds,
        retry=Retry(NoBackoff(), retries=0),
        decode_responses=True,  # get/set str instead of bytes
    )


@lru_cache
def get_redis_client() -> redis.Redis:
    """The shared Redis client for this process."""
    return create_redis_client(get_settings())
