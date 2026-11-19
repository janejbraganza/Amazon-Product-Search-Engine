"""Optional integration tests against a REAL Redis server.

- Uses Redis database 15 (not the app's database 0) and a unique key prefix per run.
- Skipped automatically when Redis is not reachable, so the suite never depends on it.
- Cleans up only the keys it created (SCAN + DELETE on its own prefix). Never FLUSHDB/ALL.
"""

import uuid
from collections.abc import Iterator
from urllib.parse import urlsplit, urlunsplit

import pytest
import redis

from app.cache.redis_client import create_redis_client
from app.cache.search_cache import CacheStatus, SearchCache, get_search_cache
from app.core.config import get_settings
from app.main import app
from app.search.index_manager import SearchIndexManager, get_index_manager
from app.services.product_loader import load_products

TEST_DB = 15


def redis_url_for_db(url: str, db: int) -> str:
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=f"/{db}"))


@pytest.fixture(scope="module")
def real_redis() -> Iterator[redis.Redis]:
    settings = get_settings()
    test_settings = settings.model_copy(
        update={"redis_url": redis_url_for_db(settings.redis_url, TEST_DB)}
    )
    client = create_redis_client(test_settings)
    try:
        client.ping()
    except redis.RedisError:
        pytest.skip("Redis is not reachable; start it with `docker compose up -d`")
    yield client
    client.close()


@pytest.fixture
def key_prefix(real_redis: redis.Redis) -> Iterator[str]:
    prefix = f"pse-test:{uuid.uuid4().hex}:"
    yield prefix
    # Delete exactly the keys this test created.
    for key in real_redis.scan_iter(match=f"{prefix}*"):
        real_redis.delete(key)


def test_uses_database_15(real_redis):
    assert real_redis.connection_pool.connection_kwargs["db"] == TEST_DB


def test_set_get_round_trip_with_ttl(real_redis, key_prefix):
    cache = SearchCache(real_redis, ttl_seconds=60, key_prefix=key_prefix)
    key = cache.build_key("build", {"terms": ["laptop"]})
    assert cache.get(key).status is CacheStatus.MISS
    assert cache.set(key, '{"hello": "world"}') is True
    lookup = cache.get(key)
    assert lookup.status is CacheStatus.HIT
    assert lookup.value == '{"hello": "world"}'
    assert 0 < real_redis.ttl(key) <= 60


def test_cleanup_only_touches_own_prefix(real_redis, key_prefix):
    other = f"pse-test-other:{uuid.uuid4().hex}"
    real_redis.set(other, "keep", ex=60)
    try:
        cache = SearchCache(real_redis, ttl_seconds=60, key_prefix=key_prefix)
        cache.set(cache.build_key("b", {"q": 1}), "{}")
        own = list(real_redis.scan_iter(match=f"{key_prefix}*"))
        assert len(own) == 1
    finally:
        assert real_redis.get(other) == "keep"
        real_redis.delete(other)


def test_api_miss_then_hit_with_real_redis(
    client, db_session, sample_products, real_redis, key_prefix
):
    load_products(db_session, sample_products)
    manager = SearchIndexManager()
    app.dependency_overrides[get_index_manager] = lambda: manager
    app.dependency_overrides[get_search_cache] = lambda: SearchCache(
        real_redis, ttl_seconds=60, key_prefix=key_prefix
    )
    try:
        miss = client.get("/api/v1/search", params={"q": "ideal", "limit": 5})
        hit = client.get("/api/v1/search", params={"q": "ideal", "limit": 5})
        assert (miss.headers["X-Cache"], hit.headers["X-Cache"]) == ("MISS", "HIT")
        assert hit.json() == miss.json()
        assert len(list(real_redis.scan_iter(match=f"{key_prefix}*"))) == 1
    finally:
        app.dependency_overrides.pop(get_index_manager, None)
