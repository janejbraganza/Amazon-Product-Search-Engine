"""Layers B and C: HTTP latency and concurrency against a real uvicorn server.

Starts bench_server.py as a separate process (127.0.0.1:8765, 1 worker), then:

B. Sequential latency (one client, keep-alive connection), per query:
     no cache  - cache off, every request computed
     miss      - a fresh, empty cache prefix before EVERY request (each is a true MISS)
     hit       - one warm-up request, then repeated identical requests (each a HIT)
     down      - Redis unreachable: first request (pays the timeout) reported apart,
                 then requests during the cooldown
   plus autocomplete (/search/suggestions, not cached) and response-size info.
   Each request records client time AND server time (Server-Timing header), so
   transport/client overhead = client - server is reported separately.

C. Concurrency: 1, 5, 10, 20 client threads (one connection each) sending a fixed
   round-robin mix of all queries; uncached and cache-hit. Every response is checked
   against the expected result (product IDs and total) computed beforehand.

Redis: database 15, prefix "pse-bench:<run id>:"; only those keys are deleted at the end.

Usage (from backend/):  python ../benchmarks/bench_http.py [--repeat 200]
"""

import argparse
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import common  # noqa: F401  (adds backend/ to sys.path)
import httpx
from common import (
    AUTOCOMPLETE_QUERY,
    BENCH_DIR,
    BENCH_KEY_ROOT,
    SEARCH_QUERIES,
    bench_redis,
    cleanup_prefix,
    save_json,
    summarize,
)

PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"
SEARCH = "/api/v1/search"
CONCURRENCY_LEVELS = [1, 5, 10, 20]


# ---- Server process -------------------------------------------------------------------


def start_server(run_prefix: str, log_path: Path) -> subprocess.Popen:
    log = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(BENCH_DIR / "bench_server.py"), "--port", str(PORT),
         "--run-prefix", run_prefix],
        stdout=log, stderr=subprocess.STDOUT,
    )  # fmt: skip
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            if httpx.get(f"{BASE}/health", timeout=1).status_code == 200:
                return proc
        except httpx.HTTPError:
            time.sleep(0.25)
        if proc.poll() is not None:
            raise RuntimeError(f"benchmark server exited; see {log_path}")
    proc.terminate()
    raise RuntimeError("benchmark server did not start within 60 s")


# ---- Request helpers ------------------------------------------------------------------


def server_ms(response: httpx.Response) -> float:
    return float(response.headers["server-timing"].split("dur=")[1])


def fingerprint(body: dict) -> tuple:
    """What must be identical between correct responses (excludes the echoed query)."""
    return (body["total"], tuple(item["id"] for item in body["items"]))


def control(client: httpx.Client, mode: str) -> dict:
    response = client.post(f"/__bench/cache?mode={mode}")
    response.raise_for_status()
    return response.json()


def timed_get(client: httpx.Client, path: str, params: dict) -> tuple[float, httpx.Response]:
    started = time.perf_counter()
    response = client.get(path, params=params)
    return (time.perf_counter() - started) * 1000, response


class Recorder:
    def __init__(self) -> None:
        self.client_ms: list[float] = []
        self.server_ms: list[float] = []

    def add(self, elapsed: float, response: httpx.Response) -> None:
        self.client_ms.append(elapsed)
        self.server_ms.append(server_ms(response))

    def result(self) -> dict:
        overhead = [c - s for c, s in zip(self.client_ms, self.server_ms, strict=True)]
        return {
            "client_ms": summarize(self.client_ms),
            "server_ms": summarize(self.server_ms),
            "overhead_ms": summarize(overhead),
        }


def expect(response: httpx.Response, cache_status: str | None, expected: tuple | None):
    assert response.status_code == 200, response.text[:200]
    if cache_status is not None:
        got = response.headers.get("x-cache")
        assert got == cache_status, f"expected X-Cache {cache_status}, got {got}"
    if expected is not None:
        assert fingerprint(response.json()) == expected, "incorrect search result"


# ---- B. Sequential latency ------------------------------------------------------------


def sequential(client: httpx.Client, repeat: int, warmup: int, down_repeat: int) -> dict:
    results: dict = {"queries": {}}
    expected: dict[str, tuple] = {}

    for name, params in SEARCH_QUERIES.items():
        print(f"  {name}")
        entry: dict = {}

        # No cache
        control(client, "off")
        for _ in range(warmup):
            client.get(SEARCH, params=params)
        reference = client.get(SEARCH, params=params)
        expected[name] = fingerprint(reference.json())
        entry["matches"] = reference.json()["total"]
        entry["response_kb"] = round(len(reference.content) / 1024, 1)
        rec = Recorder()
        for _ in range(repeat):
            elapsed, response = timed_get(client, SEARCH, params)
            expect(response, "BYPASS", expected[name])
            rec.add(elapsed, response)
        entry["no_cache"] = rec.result()

        # Cache miss: a fresh empty cache before each measured request.
        rec = Recorder()
        for i in range(warmup + repeat):
            control(client, "on")
            elapsed, response = timed_get(client, SEARCH, params)
            expect(response, "MISS", expected[name])
            if i >= warmup:
                rec.add(elapsed, response)
        entry["cache_miss"] = rec.result()

        # Cache hit: one miss to fill the cache, then only hits are measured.
        control(client, "on")
        expect(client.get(SEARCH, params=params), "MISS", expected[name])
        for _ in range(warmup):
            client.get(SEARCH, params=params)
        rec = Recorder()
        for _ in range(repeat):
            elapsed, response = timed_get(client, SEARCH, params)
            expect(response, "HIT", expected[name])
            rec.add(elapsed, response)
        entry["cache_hit"] = rec.result()

        # Redis unavailable: the first request pays the timeout, the rest skip Redis.
        control(client, "down")
        elapsed, response = timed_get(client, SEARCH, params)
        expect(response, "BYPASS", expected[name])
        entry["redis_down_first_request_ms"] = {
            "client": round(elapsed, 3),
            "server": round(server_ms(response), 3),
        }
        rec = Recorder()
        for _ in range(down_repeat):
            elapsed, response = timed_get(client, SEARCH, params)
            expect(response, "BYPASS", expected[name])
            rec.add(elapsed, response)
        entry["redis_down_cooldown"] = rec.result()
        results["queries"][name] = entry

    # Autocomplete (not cached)
    path = f"{SEARCH}/suggestions"
    for _ in range(warmup):
        client.get(path, params=AUTOCOMPLETE_QUERY)
    rec = Recorder()
    for _ in range(repeat):
        elapsed, response = timed_get(client, path, AUTOCOMPLETE_QUERY)
        assert response.status_code == 200
        assert [s["term"] for s in response.json()["suggestions"]][:1] == ["earbud"]
        rec.add(elapsed, response)
    results["autocomplete: ear"] = rec.result()

    # A trivial endpoint: the floor set by HTTP + framework overhead.
    rec = Recorder()
    for _ in range(repeat):
        elapsed, response = timed_get(client, "/health", {})
        rec.add(elapsed, response)
    results["health"] = rec.result()

    control(client, "off")
    return results, expected


# ---- C. Concurrency -----------------------------------------------------------------


def run_level(level: int, total_requests: int, expected: dict, cached: bool) -> dict:
    """``level`` client threads, one keep-alive connection each, started together."""
    names = list(SEARCH_QUERIES)
    with httpx.Client(base_url=BASE, timeout=60) as admin:
        control(admin, "on" if cached else "off")
        if cached:  # fill the cache so the measured requests are all hits
            for name in names:
                admin.get(SEARCH, params=SEARCH_QUERIES[name])
    per_client = total_requests // level
    latencies: list[list[float]] = [[] for _ in range(level)]
    errors = [0] * level
    wrong = [0] * level
    barrier = threading.Barrier(level + 1)

    def worker(slot: int) -> None:
        with httpx.Client(base_url=BASE, timeout=60) as client:
            client.get("/health")  # open the connection before timing
            barrier.wait()
            for i in range(per_client):
                name = names[(slot + i) % len(names)]  # fixed round-robin query mix
                try:
                    elapsed, response = timed_get(client, SEARCH, SEARCH_QUERIES[name])
                except httpx.HTTPError:
                    errors[slot] += 1
                    continue
                if response.status_code != 200:
                    errors[slot] += 1
                elif fingerprint(response.json()) != expected[name] or (
                    cached and response.headers.get("x-cache") != "HIT"
                ):
                    wrong[slot] += 1
                latencies[slot].append(elapsed)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(level)]
    for t in threads:
        t.start()
    barrier.wait()  # all clients connected; start the clock together
    started = time.perf_counter()
    for t in threads:
        t.join()
    wall = time.perf_counter() - started

    samples = [ms for client_samples in latencies for ms in client_samples]
    return {
        "clients": level,
        "requests": per_client * level,
        "errors": sum(errors),
        "incorrect": sum(wrong),
        "wall_seconds": round(wall, 3),
        "latency_ms": summarize(samples, wall_seconds=wall),
    }


def concurrency(levels: list[int], total_requests: int, expected: dict, cached: bool) -> dict:
    out = {}
    for level in levels:
        out[str(level)] = run_level(level, total_requests, expected, cached)
        print(
            f"  {'cached' if cached else 'uncached':<8} {level:>2} clients: "
            f"{out[str(level)]['latency_ms']['rps']:7.1f} req/s, "
            f"p50 {out[str(level)]['latency_ms']['p50']:7.2f} ms, "
            f"p95 {out[str(level)]['latency_ms']['p95']:7.2f} ms, "
            f"errors {out[str(level)]['errors']}, incorrect {out[str(level)]['incorrect']}"
        )
    return out


def main() -> dict:
    parser = argparse.ArgumentParser(description="HTTP latency and concurrency benchmarks")
    parser.add_argument("--repeat", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--down-repeat", type=int, default=50)
    parser.add_argument("--concurrent-requests", type=int, default=400)
    args = parser.parse_args()

    run_prefix = f"{BENCH_KEY_ROOT}{uuid.uuid4().hex[:12]}:"
    log_path = Path(BENCH_DIR / "results" / "server.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    redis_client = bench_redis()
    proc = start_server(run_prefix, log_path)
    try:
        with httpx.Client(base_url=BASE, timeout=60) as client:
            rss_start = client.get("/__bench/rss").json()["rss_mb"]
            started = time.perf_counter()
            client.get(SEARCH, params={"q": "laptop"})  # first search builds the index
            first_search_s = time.perf_counter() - started
            rss_after_index = client.get("/__bench/rss").json()["rss_mb"]

            print("B. sequential latency")
            sequential_results, expected = sequential(
                client, args.repeat, args.warmup, args.down_repeat
            )

        print("C. concurrency")
        concurrent = {
            "uncached": concurrency(
                CONCURRENCY_LEVELS, args.concurrent_requests, expected, cached=False
            ),
            "cache_hit": concurrency(
                CONCURRENCY_LEVELS, args.concurrent_requests, expected, cached=True
            ),
        }
        with httpx.Client(base_url=BASE, timeout=60) as client:
            rss_end = client.get("/__bench/rss").json()["rss_mb"]
    finally:
        proc.terminate()
        proc.wait(timeout=30)
        deleted = cleanup_prefix(redis_client, run_prefix)
        print(f"cleaned up {deleted} benchmark keys ({run_prefix}*) from Redis db 15")

    result = {
        "repeat": args.repeat,
        "warmup": args.warmup,
        "down_repeat": args.down_repeat,
        "concurrent_requests_per_level": args.concurrent_requests,
        "server": {"workers": 1, "host": "127.0.0.1", "port": PORT},
        "memory_rss_mb": {
            "server_start": rss_start,
            "after_index_build": rss_after_index,
            "end_of_run": rss_end,
        },
        "first_search_including_index_build_s": round(first_search_s, 3),
        "sequential": sequential_results,
        "concurrency": concurrent,
        "redis_keys_deleted": deleted,
    }
    path = save_json("http.json", result)
    print(f"saved {path}")
    return result


if __name__ == "__main__":
    main()
