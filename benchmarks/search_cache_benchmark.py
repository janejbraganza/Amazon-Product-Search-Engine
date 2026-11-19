"""Benchmark: search response time with and without the Redis cache.

Usage (from backend/, with Docker running and the 10,000 products loaded):
    python ../benchmarks/search_cache_benchmark.py
    python ../benchmarks/search_cache_benchmark.py --rounds 30 --requests 2000 --seed 42

What is measured (in-process FastAPI TestClient against the real PostgreSQL and Redis,
so times include routing, validation and JSON serialisation, but no network hop):

  1. No cache        - cache disabled; every request runs the full search.
  2. First search    - cache enabled, key not present (MISS: search + store in Redis).
  3. Repeated search - same request again (HIT: read from Redis).
  4. Mixed workload  - a seeded, skewed stream of requests; reports hit rate and average
                       time, compared with the same stream without a cache.
  5. Redis down      - unreachable Redis: the first request pays the timeout, the rest
                       skip Redis during the cooldown.

Safety: uses Redis database 15 and a unique key prefix per run, and deletes only its own
keys at the end (SCAN + DELETE). It never uses FLUSHDB or FLUSHALL.
"""

import argparse
import random
import statistics
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from app.cache.redis_client import create_redis_client  # noqa: E402
from app.cache.search_cache import SearchCache, get_search_cache  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.search.index_manager import index_manager  # noqa: E402

BENCH_DB = 15
URL = "/api/v1/search"

# Fixed query set: cheap, medium and expensive searches, normal and prefix.
QUERIES: list[dict] = [
    {"q": "laptop"},
    {"q": "wireless earbuds"},
    {"q": "voltrix laptop 32gb"},
    {"q": "stainless steel", "mode": "any"},
    {"q": "gluten free protein bars", "mode": "any"},
    {"q": "ideal"},  # matches all 10,000 products
    {"q": "wireless ear", "prefix": "true"},
    {"q": "s", "prefix": "true"},  # 50 expansions, ~9,800 products
]


def label(params: dict) -> str:
    extra = " ".join(f"{k}={v}" for k, v in params.items() if k != "q")
    return f"{params['q']!r} {extra}".strip()


def summarize(samples_ms: list[float]) -> str:
    ordered = sorted(samples_ms)
    p95 = ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]
    return f"{statistics.mean(ordered):8.2f} {statistics.median(ordered):8.2f} {p95:8.2f}"


def timed(client: TestClient, params: dict) -> tuple[float, str]:
    started = time.perf_counter()
    response = client.get(URL, params=params)
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert response.status_code == 200, response.text
    return elapsed_ms, response.headers.get("X-Cache", "?")


def use_cache(cache: SearchCache | None) -> None:
    app.dependency_overrides[get_search_cache] = lambda: cache or SearchCache(client=None)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--rounds", type=int, default=30, help="repetitions per query")
    parser.add_argument("--requests", type=int, default=2000, help="mixed-workload length")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    settings = get_settings()
    redis_url = urlunsplit(urlsplit(settings.redis_url)._replace(path=f"/{BENCH_DB}"))
    redis_client = create_redis_client(settings.model_copy(update={"redis_url": redis_url}))
    redis_client.ping()
    run_prefix = f"pse-bench:{uuid.uuid4().hex}:"

    def new_cache() -> SearchCache:
        # A fresh key prefix gives an empty cache without deleting anything.
        return SearchCache(
            redis_client, ttl_seconds=300, key_prefix=f"{run_prefix}{uuid.uuid4().hex}:"
        )

    client = TestClient(app)
    with SessionLocal() as session:
        index_manager.get_index(session)  # build the index before timing anything

    # Warm-up (imports, connection pools, first-request costs) - not measured.
    use_cache(None)
    for params in QUERIES:
        timed(client, params)

    try:
        print(f"Rounds per query: {args.rounds} | times in ms (mean / median / p95)\n")
        header = f"{'query':<38} {'no cache':>26}   {'first (MISS)':>26}   {'repeat (HIT)':>26}"
        print(header)
        print("-" * len(header))
        totals = {"none": [], "miss": [], "hit": []}
        for params in QUERIES:
            none, miss, hit = [], [], []
            for _ in range(args.rounds):
                use_cache(None)
                none.append(timed(client, params)[0])
                use_cache(new_cache())
                t, status = timed(client, params)
                assert status == "MISS", status
                miss.append(t)
                t, status = timed(client, params)
                assert status == "HIT", status
                hit.append(t)
            totals["none"] += none
            totals["miss"] += miss
            totals["hit"] += hit
            print(f"{label(params):<38} {summarize(none)}   {summarize(miss)}   {summarize(hit)}")
        print("-" * len(header))
        print(
            f"{'ALL QUERIES':<38} {summarize(totals['none'])}   "
            f"{summarize(totals['miss'])}   {summarize(totals['hit'])}"
        )

        # Mixed workload: popular queries are requested more often (seeded, repeatable).
        rng = random.Random(args.seed)
        weights = [1 / (rank + 1) for rank in range(len(QUERIES))]
        stream = rng.choices(QUERIES, weights=weights, k=args.requests)
        use_cache(None)
        uncached = [timed(client, p)[0] for p in stream]
        use_cache(new_cache())
        cached_runs = [timed(client, p) for p in stream]
        hits = sum(status == "HIT" for _, status in cached_runs)
        print(
            f"\nMixed workload: {args.requests} requests, "
            f"{len(QUERIES)} distinct queries, seed {args.seed}"
        )
        print(
            f"  without cache : mean {statistics.mean(uncached):.2f} ms, "
            f"total {sum(uncached) / 1000:.2f} s"
        )
        cached_times = [t for t, _ in cached_runs]
        print(
            f"  with cache    : mean {statistics.mean(cached_times):.2f} ms, "
            f"total {sum(cached_times) / 1000:.2f} s, hit rate {hits / len(stream):.1%} "
            f"({hits} hits / {len(stream) - hits} misses)"
        )

        # Redis unavailable: unreachable port, normal timeout and cooldown settings.
        down_settings = settings.model_copy(update={"redis_url": "redis://127.0.0.1:6390/0"})
        use_cache(
            SearchCache(
                create_redis_client(down_settings),
                cooldown_seconds=settings.redis_retry_cooldown_seconds,
            )
        )
        first_down, status = timed(client, QUERIES[0])
        during = [timed(client, QUERIES[0]) for _ in range(20)]
        use_cache(None)
        baseline = [timed(client, QUERIES[0])[0] for _ in range(20)]
        print(f"\nRedis unavailable (query {label(QUERIES[0])}):")
        print(
            f"  first request (pays the {settings.redis_timeout_seconds}s timeout): "
            f"{first_down:.1f} ms, X-Cache {status}"
        )
        print(
            f"  next 20 requests (cooldown, Redis skipped): mean "
            f"{statistics.mean(t for t, _ in during):.2f} ms, all {set(s for _, s in during)}"
        )
        print(
            f"  same request, cache disabled            : mean {statistics.mean(baseline):.2f} ms"
        )
    finally:
        app.dependency_overrides.pop(get_search_cache, None)
        deleted = 0
        for key in redis_client.scan_iter(match=f"{run_prefix}*"):
            deleted += redis_client.delete(key)
        print(
            f"\nCleaned up {deleted} benchmark keys "
            f"(prefix {run_prefix}*) from Redis db {BENCH_DB}."
        )


if __name__ == "__main__":
    main()
