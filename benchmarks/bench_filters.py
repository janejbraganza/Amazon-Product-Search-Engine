"""Phase 8 Stage 5: filtered and sorted search benchmark (same method as Phase 7).

Usage (from backend/, with Docker running and the 10,000 products loaded):
    python ../benchmarks/bench_filters.py [--repeat 100]

Reuses Phase 7's benchmark server (bench_server.py: real uvicorn, Server-Timing header,
cache control on Redis DB 15 with a run-specific key prefix that is deleted afterwards).

A. HTTP, 1 client: for two queries ("laptop": 220 matches, "ideal": all 10,000), each
   filter / sort scenario with no cache, cache miss (fresh empty prefix before every
   request) and cache hit (repeated request). Client and server time are both recorded.
B. In-process (no HTTP): time of the steps added in Stage 5 - facet counting, filtering
   and sorting - next to BM25 ranking itself, on the 10,000-product index.
"""

import argparse
import time
import uuid

import bench_http as phase7  # Phase 7 helpers: server start, control, timing, recorder
import common  # noqa: F401  (adds backend/ to sys.path)
import httpx
from common import BENCH_KEY_ROOT, bench_redis, cleanup_prefix, load_json, save_json, summarize

from app.database.session import SessionLocal
from app.search.filters import (
    SearchFilters,
    SortOption,
    apply_filters,
    compute_facets,
    sort_results,
)
from app.search.index_manager import build_index_from_db
from app.services.search_service import parse_query

QUERIES = ["laptop", "ideal"]
SCENARIOS: dict[str, dict] = {
    "unfiltered": {},
    "category": {"category": "Electronics"},
    "brand": {"brand": "Voltrix"},
    "price range": {"min_price": "50", "max_price": "200"},
    "combined": {
        "category": "Electronics",
        "max_price": "1000",
        "min_rating": "4",
        "in_stock": "true",
    },
    "sort price_asc": {"sort": "price_asc"},
    "sort price_desc": {"sort": "price_desc"},
    "sort rating": {"sort": "rating"},
    "sort newest": {"sort": "newest"},
}
SEARCH = "/api/v1/search"


def http_benchmarks(client: httpx.Client, repeat: int, warmup: int) -> dict:
    out: dict = {}
    for q in QUERIES:
        for name, extra in SCENARIOS.items():
            params = {"q": q, "limit": "20", **extra}
            entry: dict = {}
            # No cache
            phase7.control(client, "off")
            for _ in range(warmup):
                client.get(SEARCH, params=params)
            reference = client.get(SEARCH, params=params)
            expected = phase7.fingerprint(reference.json())
            entry["total"] = reference.json()["total"]
            rec = phase7.Recorder()
            for _ in range(repeat):
                elapsed, response = phase7.timed_get(client, SEARCH, params)
                phase7.expect(response, "BYPASS", expected)
                rec.add(elapsed, response)
            entry["no_cache"] = rec.result()
            # Cache miss: a fresh empty prefix before every measured request
            rec = phase7.Recorder()
            for i in range(warmup + repeat):
                phase7.control(client, "on")
                elapsed, response = phase7.timed_get(client, SEARCH, params)
                phase7.expect(response, "MISS", expected)
                if i >= warmup:
                    rec.add(elapsed, response)
            entry["cache_miss"] = rec.result()
            # Cache hit
            phase7.control(client, "on")
            phase7.expect(client.get(SEARCH, params=params), "MISS", expected)
            rec = phase7.Recorder()
            for _ in range(repeat):
                elapsed, response = phase7.timed_get(client, SEARCH, params)
                phase7.expect(response, "HIT", expected)
                rec.add(elapsed, response)
            entry["cache_hit"] = rec.result()
            out[f"{q} | {name}"] = entry
            print(
                f"  {q:<7} {name:<16} total={entry['total']:>5}  "
                f"no-cache p50 {entry['no_cache']['client_ms']['p50']:6.2f} ms  "
                f"miss p50 {entry['cache_miss']['client_ms']['p50']:6.2f}  "
                f"hit p50 {entry['cache_hit']['client_ms']['p50']:6.2f}"
            )
    phase7.control(client, "off")
    return out


def time_ms(fn, repeat: int, warmup: int = 5) -> list[float]:
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(repeat):
        started = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - started) * 1000)
    return samples


def in_process_benchmarks(repeat: int) -> dict:
    with SessionLocal() as session:
        index = build_index_from_db(session)
    combined = SearchFilters.create(
        categories=["Electronics"], max_price=1000, min_rating=4, in_stock=True
    )
    out = {}
    for q in QUERIES:
        terms, _ = parse_query(q)
        ranked = index.rank_groups([[t] for t in terms])
        out[q] = {
            "matches": len(ranked),
            "bm25_rank_ms": summarize(
                time_ms(lambda t=terms: index.rank_groups([[x] for x in t]), repeat)
            ),
            "facets_unfiltered_ms": summarize(
                time_ms(lambda r=ranked: compute_facets(r, index, SearchFilters()), repeat)
            ),
            "facets_combined_filters_ms": summarize(
                time_ms(lambda r=ranked: compute_facets(r, index, combined), repeat)
            ),
            "filter_combined_ms": summarize(
                time_ms(lambda r=ranked: apply_filters(r, index, combined), repeat)
            ),
            "sort_price_asc_all_matches_ms": summarize(
                time_ms(lambda r=ranked: sort_results(r, index, SortOption.PRICE_ASC), repeat)
            ),
        }
        p50 = {name: stats["p50"] for name, stats in out[q].items() if isinstance(stats, dict)}
        labels = {
            "bm25_rank_ms": "BM25 rank",
            "facets_unfiltered_ms": "facets",
            "facets_combined_filters_ms": "facets+filters",
            "filter_combined_ms": "filter",
            "sort_price_asc_all_matches_ms": "sort",
        }
        parts = [f"{label} {p50[name]:.3f} ms" for name, label in labels.items()]
        print(f"  {q:<7} matches={out[q]['matches']:>5}  " + " | ".join(parts))
    return out


def phase7_reference() -> dict:
    """Phase 7's published numbers for the same unfiltered queries (for comparison)."""
    try:
        phase7_http = load_json("http.json")["sequential"]["queries"]
    except (FileNotFoundError, KeyError):
        return {}
    ref = {}
    for name, label in [("simple: laptop", "laptop"), ("common term: ideal", "ideal")]:
        if name in phase7_http:
            ref[label] = {
                state: phase7_http[name][state]["client_ms"]["p50"]
                for state in ("no_cache", "cache_miss", "cache_hit")
            }
    return ref


def main() -> None:
    parser = argparse.ArgumentParser(description="Filtered/sorted search benchmark")
    parser.add_argument("--repeat", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=10)
    args = parser.parse_args()

    run_prefix = f"{BENCH_KEY_ROOT}{uuid.uuid4().hex[:12]}:"
    log_path = common.BENCH_DIR / "results" / "server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    redis_client = bench_redis()
    proc = phase7.start_server(run_prefix, log_path)
    try:
        with httpx.Client(base_url=phase7.BASE, timeout=60) as client:
            client.get(SEARCH, params={"q": "laptop"})  # first search builds the index
            print("A. HTTP, 1 client (client time p50)")
            http = http_benchmarks(client, args.repeat, args.warmup)
    finally:
        proc.terminate()
        proc.wait(timeout=30)
        deleted = cleanup_prefix(redis_client, run_prefix)
        print(f"cleaned up {deleted} benchmark keys ({run_prefix}*) from Redis db 15")

    print("B. In-process steps (p50)")
    steps = in_process_benchmarks(args.repeat)
    result = {
        "repeat": args.repeat,
        "warmup": args.warmup,
        "http": http,
        "in_process": steps,
        "phase7_reference_p50_ms": phase7_reference(),
        "redis_keys_deleted": deleted,
    }
    print(f"saved {save_json('filters.json', result)}")
    print("Phase 7 reference (client p50 ms):", result["phase7_reference_p50_ms"])
    print("Leftover benchmark keys:", common.count_bench_keys())


if __name__ == "__main__":
    main()
