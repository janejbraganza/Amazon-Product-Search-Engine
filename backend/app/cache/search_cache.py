"""Search result cache stored in Redis.

Key design
----------
    pse:search:v2:{index_build_id}:{sha256 of the normalised search parameters}

- ``pse:search:``     our own namespace; nothing outside it is ever read or written.
- ``v2``              bump when the response format or search behaviour changes
                      (v2 added filters and sort to the hashed parameters).
- ``index_build_id``  random ID of the InvertedIndex that produced the result. A rebuild
                      creates a new index with a new ID, so entries from the old index can
                      never be read again (they simply expire after the TTL). This is the
                      invalidation strategy: versioned keys, no deletes needed.
- the hash            covers everything that changes the response (terms, partial word,
                      mode, prefix flag, limit, offset, expansion cap, filters, sort).

Failure handling
----------------
``get`` and ``set`` never raise. A Redis error is logged, and Redis is then skipped for
``cooldown_seconds`` so an outage costs one short timeout, not one per request.
"""

import hashlib
import json
import logging
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from typing import Any, Protocol

import redis

from app.cache.redis_client import get_redis_client
from app.core.config import get_settings

logger = logging.getLogger(__name__)

KEY_PREFIX = "pse:search:"
CACHE_VERSION = "v2"  # v2: filters and sort are part of the key (Phase 8)


class RedisLike(Protocol):
    """The two Redis commands the cache needs (real client or a test fake)."""

    def get(self, name: str) -> Any: ...
    def set(self, name: str, value: str, ex: int | None = None) -> Any: ...


class CacheStatus(StrEnum):
    HIT = "HIT"  # served from Redis
    MISS = "MISS"  # computed, then stored in Redis
    BYPASS = "BYPASS"  # computed, not stored (cache off, Redis unavailable, not cacheable)


@dataclass(frozen=True)
class CacheLookup:
    status: CacheStatus  # HIT, MISS (not found) or BYPASS (cache not usable)
    value: str | None = None


class SearchCache:
    def __init__(
        self,
        client: RedisLike | None,
        ttl_seconds: int = 300,
        cooldown_seconds: float = 30.0,
        enabled: bool = True,
        key_prefix: str = KEY_PREFIX,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._client = client
        self.ttl_seconds = ttl_seconds
        self.cooldown_seconds = cooldown_seconds
        self.enabled = enabled and client is not None
        self.key_prefix = key_prefix
        self._clock = clock
        self._skip_until = 0.0  # monotonic time until which Redis is not contacted
        self._lock = threading.Lock()

    # ---- Keys ----

    def build_key(self, index_build_id: str, params: dict[str, Any]) -> str:
        # Canonical JSON (sorted keys, no spaces) so equal parameters give equal keys.
        canonical = json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"{self.key_prefix}{CACHE_VERSION}:{index_build_id}:{digest}"

    # ---- Availability (cooldown after failures) ----

    @property
    def available(self) -> bool:
        return self.enabled and self._clock() >= self._skip_until

    def _record_failure(self, operation: str, exc: Exception) -> None:
        with self._lock:
            self._skip_until = self._clock() + self.cooldown_seconds
        # Log the error type and message, with any credentials in URLs removed.
        logger.warning(
            "Search cache %s failed (%s: %s). Skipping Redis for %.0f s.",
            operation,
            type(exc).__name__,
            redact_credentials(str(exc)),
            self.cooldown_seconds,
        )

    # ---- Operations (never raise) ----

    def get(self, key: str) -> CacheLookup:
        if not self.available:
            return CacheLookup(CacheStatus.BYPASS)
        try:
            value = self._client.get(key)
        except redis.RedisError as exc:
            self._record_failure("lookup", exc)
            return CacheLookup(CacheStatus.BYPASS)
        if value is None:
            return CacheLookup(CacheStatus.MISS)
        return CacheLookup(CacheStatus.HIT, value)

    def set(self, key: str, value: str) -> bool:
        """Store ``value`` with the configured TTL. Returns True if it was stored."""
        if not self.available:
            return False
        try:
            self._client.set(key, value, ex=self.ttl_seconds)
        except redis.RedisError as exc:
            self._record_failure("store", exc)
            return False
        return True


_URL_CREDENTIALS = re.compile(r"(\w+://)[^@/\s]*@")


def redact_credentials(text: str) -> str:
    """'redis://user:secret@host' -> 'redis://***@host' (for log messages)."""
    return _URL_CREDENTIALS.sub(r"\1***@", text)


@lru_cache
def get_search_cache() -> SearchCache:
    """FastAPI dependency: the shared cache for this process (overridable in tests).

    Shared so the cooldown state is shared: one failure pauses Redis for every request.
    """
    settings = get_settings()
    return SearchCache(
        client=get_redis_client(),
        ttl_seconds=settings.search_cache_ttl_seconds,
        cooldown_seconds=settings.redis_retry_cooldown_seconds,
        enabled=settings.search_cache_enabled,
    )
