"""Search result caching tests, using in-memory Redis doubles (no Redis server needed).

FakeRedis     a dict that records every call and the TTL it was given.
FailingRedis  raises redis.ConnectionError, as a stopped/unreachable Redis would.
"""

import json
import logging
from decimal import Decimal

import pytest
import redis
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.cache import search_cache as search_cache_module
from app.cache.search_cache import KEY_PREFIX, CacheStatus, SearchCache, get_search_cache
from app.core.config import Settings
from app.main import app
from app.models.product import Product
from app.search.index_manager import SearchIndexManager, get_index_manager
from app.services import cached_search as cached_search_module
from app.services.cached_search import run_cached_search
from app.services.product_loader import load_products
from app.services.search_service import SearchMode

URL = "/api/v1/search"
REDIS_URL_WITH_SECRET = "redis://:s3cret-password@127.0.0.1:6379/0"


# ---- Test doubles -----------------------------------------------------------------


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int | None] = {}
        self.calls: list[tuple[str, str]] = []

    def get(self, name: str) -> str | None:
        self.calls.append(("get", name))
        return self.store.get(name)

    def set(self, name: str, value: str, ex: int | None = None) -> bool:
        self.calls.append(("set", name))
        self.store[name] = value
        self.ttls[name] = ex
        return True


class FailingRedis(FakeRedis):
    """Fails on lookup and/or store; can be 'repaired' by flipping the flags."""

    def __init__(self, fail_get: bool = True, fail_set: bool = True) -> None:
        super().__init__()
        self.fail_get = fail_get
        self.fail_set = fail_set

    def get(self, name: str) -> str | None:
        if self.fail_get:
            self.calls.append(("get-failed", name))
            raise redis.ConnectionError(f"Error connecting to {REDIS_URL_WITH_SECRET}")
        return super().get(name)

    def set(self, name: str, value: str, ex: int | None = None) -> bool:
        if self.fail_set:
            self.calls.append(("set-failed", name))
            raise redis.TimeoutError("Timeout writing to socket")
        return super().set(name, value, ex)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


# ---- Fixtures -----------------------------------------------------------------------


@pytest.fixture
def manager() -> SearchIndexManager:
    fresh = SearchIndexManager()
    app.dependency_overrides[get_index_manager] = lambda: fresh
    yield fresh
    app.dependency_overrides.pop(get_index_manager, None)


@pytest.fixture
def loaded(db_session: Session, sample_products):
    load_products(db_session, sample_products)
    return sample_products


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def use_cache(cache: SearchCache) -> SearchCache:
    """Route the API to ``cache`` (the client fixture removes the override afterwards)."""
    app.dependency_overrides[get_search_cache] = lambda: cache
    return cache


@pytest.fixture
def fake(client, clock) -> FakeRedis:
    redis_double = FakeRedis()
    use_cache(SearchCache(redis_double, ttl_seconds=300, cooldown_seconds=30, clock=clock))
    return redis_double


def get(client, q: str, **params):
    return client.get(URL, params={"q": q, **params})


def keys_written(redis_double: FakeRedis) -> list[str]:
    return [name for op, name in redis_double.calls if op == "set"]


# ---- Miss, hit and correctness ------------------------------------------------------


def test_first_request_is_a_miss_and_is_stored(client, manager, loaded, fake):
    response = get(client, "ideal")
    assert response.status_code == 200
    assert response.headers["X-Cache"] == "MISS"
    assert len(fake.store) == 1
    (key,) = fake.store
    assert key.startswith(f"{KEY_PREFIX}v2:{manager.get_index(None).build_id}:")


def test_repeated_request_is_a_hit_with_identical_body(client, manager, loaded, fake):
    miss = get(client, "wireless black", mode="any", limit=7, offset=3)
    hit = get(client, "wireless black", mode="any", limit=7, offset=3)
    assert (miss.headers["X-Cache"], hit.headers["X-Cache"]) == ("MISS", "HIT")
    assert hit.json() == miss.json()  # products, scores, unmatched terms: everything


def test_hit_does_not_run_the_search_engine(client, manager, loaded, fake, monkeypatch):
    get(client, "ideal")

    def must_not_run(*args, **kwargs):
        raise AssertionError("search engine called on a cache hit")

    monkeypatch.setattr(cached_search_module, "search_products", must_not_run)
    response = get(client, "ideal")
    assert response.headers["X-Cache"] == "HIT"
    assert response.json()["total"] == 50


def test_cached_entry_holds_the_complete_response(client, manager, loaded, fake):
    body = get(client, "ideal zzzz", mode="any", prefix="true").json()
    stored = json.loads(next(iter(fake.store.values())))
    assert stored == body
    assert stored["unmatched_terms"] == ["zzzz*"]  # prefix with no completions
    assert stored["items"][0]["score"] > 0
    assert {"product_name", "price", "stock_quantity"} <= set(stored["items"][0])


def test_hit_equals_uncached_response(client, manager, loaded, fake):
    cached = get(client, "wireless bl", prefix="true", mode="any")
    hit = get(client, "wireless bl", prefix="true", mode="any")
    use_cache(SearchCache(client=None))  # cache off
    uncached = get(client, "wireless bl", prefix="true", mode="any")
    assert uncached.headers["X-Cache"] == "BYPASS"
    assert hit.json() == cached.json() == uncached.json()


def test_equivalent_queries_share_an_entry_but_echo_their_own_query(client, manager, loaded, fake):
    first = get(client, "Ideal")
    second = get(client, "IDEALS!")  # same normalised terms: ["ideal"]
    assert second.headers["X-Cache"] == "HIT"
    assert len(fake.store) == 1
    assert first.json()["query"] == "Ideal"
    assert second.json()["query"] == "IDEALS!"
    assert {**second.json(), "query": "Ideal"} == first.json()


# ---- Cache keys -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ({"q": "ideal"}, {"q": "wireless"}),
        ({"q": "ideal black"}, {"q": "black ideal"}),  # term order changes score sums
        ({"q": "ideal black", "mode": "all"}, {"q": "ideal black", "mode": "any"}),
        ({"q": "ideal", "limit": 10}, {"q": "ideal", "limit": 11}),
        ({"q": "ideal", "offset": 0}, {"q": "ideal", "offset": 20}),
        ({"q": "ide", "prefix": "false"}, {"q": "ide", "prefix": "true"}),
        ({"q": "ide", "prefix": "true"}, {"q": "ide ", "prefix": "true"}),  # trailing space
    ],
    ids=["query", "term-order", "mode", "limit", "offset", "prefix-flag", "trailing-space"],
)
def test_different_parameters_use_different_keys(client, manager, loaded, fake, first, second):
    assert client.get(URL, params=first).headers["X-Cache"] == "MISS"
    assert client.get(URL, params=second).headers["X-Cache"] == "MISS"
    assert len(set(keys_written(fake))) == 2


def test_prefix_and_normal_search_do_not_collide(client, manager, loaded, fake):
    normal = get(client, "ide").json()
    prefixed = get(client, "ide", prefix="true").json()
    assert normal["total"] == 0  # "ide" is not a whole word
    assert prefixed["total"] == 50  # expands to "ideal"
    assert get(client, "ide").json() == normal  # each served from its own entry


def test_build_key_is_canonical():
    cache = SearchCache(FakeRedis())
    a = cache.build_key("build1", {"terms": ["x"], "mode": "all", "limit": 20})
    b = cache.build_key("build1", {"limit": 20, "mode": "all", "terms": ["x"]})
    assert a == b  # parameter order does not matter
    assert a != cache.build_key("build2", {"terms": ["x"], "mode": "all", "limit": 20})
    assert a.startswith("pse:search:v2:build1:")
    assert len(a.rsplit(":", 1)[1]) == 64  # sha256 hex digest


# ---- TTL ------------------------------------------------------------------------------


def test_default_ttl_is_300_seconds(client, manager, loaded, fake):
    get(client, "ideal")
    assert list(fake.ttls.values()) == [300]


def test_ttl_comes_from_settings(monkeypatch):
    settings = Settings(
        database_url="postgresql+psycopg://u@127.0.0.1/db", search_cache_ttl_seconds=42
    )
    redis_double = FakeRedis()
    monkeypatch.setattr(search_cache_module, "get_settings", lambda: settings)
    monkeypatch.setattr(search_cache_module, "get_redis_client", lambda: redis_double)
    get_search_cache.cache_clear()
    try:
        cache = get_search_cache()
        assert cache.ttl_seconds == 42
        cache.set("pse:search:v1:b:k", "{}")
        assert redis_double.ttls == {"pse:search:v1:b:k": 42}
    finally:
        get_search_cache.cache_clear()


def test_settings_defaults_and_validation():
    settings = Settings(database_url="postgresql+psycopg://u@127.0.0.1/db")
    assert settings.search_cache_ttl_seconds == 300
    assert settings.search_cache_enabled is True
    assert settings.redis_retry_cooldown_seconds == 30
    with pytest.raises(ValidationError):
        Settings(database_url="postgresql+psycopg://u@127.0.0.1/db", search_cache_ttl_seconds=0)
    with pytest.raises(ValueError):
        SearchCache(FakeRedis(), ttl_seconds=0)


# ---- Invalidation -------------------------------------------------------------------


def add_ideal_product(db_session: Session) -> None:
    db_session.add(
        Product(
            product_name="Ideal Kettle",
            description="An ideal kettle.",
            category="Home & Kitchen",
            brand="Voltrix",
            price=Decimal("29.99"),
            rating=Decimal("4.1"),
        )
    )
    db_session.commit()


def test_rebuild_invalidates_cached_results(client, manager, loaded, fake, db_session):
    assert get(client, "ideal").json()["total"] == 50
    assert get(client, "ideal").headers["X-Cache"] == "HIT"

    add_ideal_product(db_session)
    assert get(client, "ideal").json()["total"] == 50  # still cached, index not rebuilt

    client.post(f"{URL}/rebuild-index")
    after = get(client, "ideal")
    assert after.headers["X-Cache"] == "MISS"  # new build_id -> new key
    assert after.json()["total"] == 51
    assert get(client, "ideal").headers["X-Cache"] == "HIT"


def test_old_entries_are_left_to_expire_not_deleted(client, manager, loaded, fake):
    get(client, "ideal")
    old_build = manager.get_index(None).build_id
    client.post(f"{URL}/rebuild-index")
    get(client, "ideal")
    builds = {key.split(":")[3] for key in fake.store}
    assert builds == {old_build, manager.get_index(None).build_id}
    assert all(ttl == 300 for ttl in fake.ttls.values())  # old entries still expire


def test_search_racing_a_rebuild_never_stores_old_results_under_the_new_index(
    client, manager, loaded, fake, db_session
):
    # A request grabbed the old index, then a rebuild swapped in a new one.
    old_index = manager.get_index(db_session)
    add_ideal_product(db_session)
    new_index = manager.rebuild(db_session)
    assert old_index.build_id != new_index.build_id

    # The in-flight request finishes with the OLD index: its result is keyed by the old ID.
    cache = SearchCache(fake, clock=FakeClock())
    stale, status = run_cached_search(
        db_session, old_index, cache, "ideal", SearchMode.ALL, 20, 0, False
    )
    assert status is CacheStatus.MISS
    assert stale.total == 50
    assert all(f":{old_index.build_id}:" in key for key in fake.store)

    # New requests use the new index and can never read that entry.
    fresh = get(client, "ideal")
    assert fresh.headers["X-Cache"] == "MISS"
    assert fresh.json()["total"] == 51


def test_cache_never_touches_unrelated_keys(client, manager, loaded, fake):
    fake.store["other-app:session:1"] = "keep me"
    get(client, "ideal")
    get(client, "wireless", prefix="true")
    client.post(f"{URL}/rebuild-index")
    get(client, "ideal")
    assert fake.store["other-app:session:1"] == "keep me"
    assert all(name.startswith(KEY_PREFIX) for _, name in fake.calls)


def test_suggestions_endpoint_is_not_cached(client, manager, loaded, fake):
    response = client.get(f"{URL}/suggestions", params={"q": "ide"})
    assert response.status_code == 200
    assert "X-Cache" not in response.headers
    assert fake.calls == []


# ---- What must never be cached ------------------------------------------------------


@pytest.mark.parametrize("q", ["the", "!!!", "   "])
def test_invalid_queries_are_not_cached(client, manager, loaded, fake, q):
    assert get(client, q).status_code == 422
    assert fake.calls == []


def test_incomplete_page_is_not_cached(client, manager, loaded, fake, db_session):
    manager.get_index(db_session)  # index built with all 50 products
    db_session.delete(db_session.get(Product, 1))  # deleted without a rebuild
    db_session.commit()

    response = get(client, "ideal", limit=100)
    assert response.headers["X-Cache"] == "BYPASS"
    assert len(response.json()["items"]) == 49
    assert fake.store == {}


def test_unreadable_entry_is_ignored_and_replaced(client, manager, loaded, fake, caplog):
    get(client, "ideal")
    (key,) = fake.store
    fake.store[key] = '{"not": "a search response"}'

    with caplog.at_level(logging.WARNING):
        response = get(client, "ideal")
    assert response.status_code == 200
    assert response.headers["X-Cache"] == "MISS"
    assert response.json()["total"] == 50
    assert "unreadable search cache entry" in caplog.text
    assert json.loads(fake.store[key])["total"] == 50  # overwritten with a good entry


def test_disabled_cache_never_calls_redis(client, manager, loaded):
    redis_double = FakeRedis()
    use_cache(SearchCache(redis_double, enabled=False))
    assert get(client, "ideal").headers["X-Cache"] == "BYPASS"
    assert get(client, "ideal").headers["X-Cache"] == "BYPASS"
    assert redis_double.calls == []


# ---- Redis failures ---------------------------------------------------------------


def uncached_body(client, q: str, **params) -> dict:
    previous = app.dependency_overrides[get_search_cache]
    use_cache(SearchCache(client=None))
    try:
        return get(client, q, **params).json()
    finally:
        app.dependency_overrides[get_search_cache] = previous


def test_redis_down_during_lookup_still_returns_correct_results(
    client, manager, loaded, clock, caplog
):
    failing = FailingRedis(fail_get=True, fail_set=True)
    use_cache(SearchCache(failing, clock=clock))
    with caplog.at_level(logging.WARNING):
        response = get(client, "wireless bl", prefix="true", mode="any")
    assert response.status_code == 200
    assert response.headers["X-Cache"] == "BYPASS"
    assert response.json() == uncached_body(client, "wireless bl", prefix="true", mode="any")
    assert "Search cache lookup failed (ConnectionError" in caplog.text
    # The lookup failed, so storing is not even attempted (Redis is in cooldown).
    assert [op for op, _ in failing.calls] == ["get-failed"]


def test_redis_down_during_store_still_returns_correct_results(
    client, manager, loaded, clock, caplog
):
    failing = FailingRedis(fail_get=False, fail_set=True)
    use_cache(SearchCache(failing, clock=clock))
    with caplog.at_level(logging.WARNING):
        response = get(client, "ideal")
    assert response.status_code == 200
    assert response.headers["X-Cache"] == "BYPASS"
    assert response.json() == uncached_body(client, "ideal")
    assert [op for op, _ in failing.calls] == ["get", "set-failed"]
    assert "Search cache store failed (TimeoutError" in caplog.text


def test_failure_logs_and_responses_never_expose_internals(client, manager, loaded, clock, caplog):
    use_cache(SearchCache(FailingRedis(), clock=clock))
    with caplog.at_level(logging.WARNING):
        response = get(client, "ideal")
    assert "s3cret" not in response.text
    assert "Redis" not in response.text and "redis" not in response.text
    # The error message contained a URL with a password: the log keeps the error but
    # redacts the credentials.
    assert "ConnectionError" in caplog.text
    assert "s3cret" not in caplog.text
    assert "redis://***@127.0.0.1:6379/0" in caplog.text


def test_redact_credentials():
    from app.cache.search_cache import redact_credentials

    assert redact_credentials("redis://:pw@host:6379/0") == "redis://***@host:6379/0"
    assert redact_credentials("rediss://user:pw@h/1 x") == "rediss://***@h/1 x"
    assert redact_credentials("Error 10061 connecting to 127.0.0.1:6379.") == (
        "Error 10061 connecting to 127.0.0.1:6379."
    )


def test_cooldown_skips_redis_for_30_seconds_then_retries(client, manager, loaded, clock):
    failing = FailingRedis(fail_get=True, fail_set=True)
    cache = use_cache(SearchCache(failing, cooldown_seconds=30, clock=clock))

    get(client, "ideal")  # fails once -> cooldown starts
    assert len(failing.calls) == 1
    assert not cache.available

    clock.now += 29.9
    for _ in range(3):
        assert get(client, "ideal").headers["X-Cache"] == "BYPASS"
    assert len(failing.calls) == 1  # Redis not contacted during the cooldown

    clock.now += 0.2  # cooldown over, and Redis has recovered
    failing.fail_get = failing.fail_set = False
    assert get(client, "ideal").headers["X-Cache"] == "MISS"
    assert get(client, "ideal").headers["X-Cache"] == "HIT"


def test_cache_methods_never_raise():
    cache = SearchCache(FailingRedis(), clock=FakeClock())
    assert cache.get("k").status is CacheStatus.BYPASS
    assert cache.set("k", "v") is False


# ---- Existing behaviour with the cache switched on ------------------------------------


@pytest.mark.parametrize(
    "params",
    [
        {"q": "ideal", "limit": 5, "offset": 10},
        {"q": "wireless black", "mode": "any"},
        {"q": "st", "prefix": "true"},
        {"q": "ideal zzzz"},
    ],
)
def test_cached_search_matches_uncached_search(client, manager, loaded, fake, params):
    expected = uncached_body(client, **params)
    assert client.get(URL, params=params).json() == expected  # MISS path
    assert client.get(URL, params=params).json() == expected  # HIT path


# ---- Cache key v2: filters and sort -------------------------------------------------------


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ({"category": "Electronics"}, {"category": "Books"}),
        ({"category": "Electronics"}, {}),
        ({"brand": "Voltrix"}, {"brand": "Nexora"}),
        ({"min_price": "10"}, {"min_price": "11"}),
        ({"min_price": "10"}, {"max_price": "10"}),
        ({"max_price": "100"}, {"max_price": "100.01"}),
        ({"min_rating": "4.0"}, {"min_rating": "4.5"}),
        ({"in_stock": "true"}, {"in_stock": "false"}),
        ({"sort": "relevance"}, {"sort": "price_asc"}),
        ({"sort": "price_asc"}, {"sort": "price_desc"}),
        ({"sort": "rating"}, {"sort": "newest"}),
        ({"category": "Electronics", "offset": 0}, {"category": "Electronics", "offset": 5}),
        ({"category": "Electronics", "limit": 5}, {"category": "Electronics", "limit": 6}),
    ],
)
def test_different_filters_or_sort_use_different_keys(client, manager, loaded, fake, first, second):
    a = get(client, "ideal", **first)
    b = get(client, "ideal", **second)
    assert (a.headers["X-Cache"], b.headers["X-Cache"]) == ("MISS", "MISS")
    assert len(set(keys_written(fake))) == 2


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ({"category": "Electronics"}, {"category": "  electronics "}),
        ({"category": ["Books", "Electronics"]}, {"category": ["ELECTRONICS", "books"]}),
        ({"brand": "Voltrix"}, {"brand": "VOLTRIX"}),
        ({"min_price": "10"}, {"min_price": "10.00"}),
        ({"min_rating": "4"}, {"min_rating": "4.0"}),
        ({}, {"sort": "relevance", "in_stock": "false"}),  # explicit defaults
    ],
)
def test_equivalent_filters_share_one_entry(client, manager, loaded, fake, first, second):
    miss = get(client, "ideal", **first)
    hit = get(client, "ideal", **second)
    assert (miss.headers["X-Cache"], hit.headers["X-Cache"]) == ("MISS", "HIT")
    assert hit.json() == miss.json()


def test_cached_filtered_response_includes_facets_and_sort(client, manager, loaded, fake):
    params = {"category": "Electronics", "in_stock": "true", "sort": "price_desc"}
    miss = get(client, "ideal", **params)
    hit = get(client, "ideal", **params)
    assert hit.headers["X-Cache"] == "HIT"
    assert hit.json() == miss.json()
    stored = json.loads(next(iter(fake.store.values())))
    assert stored["sort"] == "price_desc"
    assert stored["facets"]["categories"]
    assert all(item["category"] == "Electronics" for item in stored["items"])


def test_filtered_cache_key_has_v2_and_the_build_id(client, manager, loaded, fake):
    get(client, "ideal", category="Electronics")
    (key,) = fake.store
    assert key.startswith(f"{KEY_PREFIX}v2:{manager.get_index(None).build_id}:")


def test_filtered_results_after_rebuild_are_not_served_from_the_old_index(
    client, manager, loaded, fake, db_session
):
    first = get(client, "ideal", category="Home & Kitchen").json()
    add_ideal_product(db_session)  # a new Home & Kitchen product mentioning "ideal"
    client.post(f"{URL}/rebuild-index")
    after = get(client, "ideal", category="Home & Kitchen")
    assert after.headers["X-Cache"] == "MISS"
    assert after.json()["total"] == first["total"] + 1


def test_redis_down_with_filters_still_returns_correct_results(client, manager, loaded, clock):
    params = {"category": "Electronics", "sort": "price_asc", "max_price": "500"}
    expected = uncached_body(client, "ideal", **params)
    use_cache(SearchCache(FailingRedis(), clock=clock))
    response = get(client, "ideal", **params)
    assert response.headers["X-Cache"] == "BYPASS"
    assert response.json() == expected


def test_invalid_filters_are_rejected_before_the_cache(client, manager, loaded, fake):
    assert get(client, "ideal", min_price="50", max_price="10").status_code == 422
    assert fake.calls == []
