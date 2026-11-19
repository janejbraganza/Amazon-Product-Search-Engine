"""Benchmark-only server launcher. NOT part of the application.

Starts uvicorn with the existing FastAPI app, wrapped from the outside (the app's code,
routes and behaviour are unchanged). Only inside this benchmark process it adds:

1. ``Server-Timing: app;dur=<ms>`` on every response: time from receiving the request
   to sending the response headers, measured in the server. Lets the client separate
   server processing from transport/client overhead.
2. ``POST /__bench/cache?mode=off|on|down`` (handled by the wrapper, never reaches the
   app): switches the search cache used via FastAPI's dependency override.
     off  -> no cache (every search computed)
     on   -> Redis database 15, key prefix "<run-prefix><new token>:" (fresh = empty cache)
     down -> a Redis client pointed at a closed port (simulates an outage)
3. ``GET /__bench/rss``: resident memory of this server process (psutil).

Usage (normally started by bench_http.py):
    python ../benchmarks/bench_server.py --port 8765 --run-prefix pse-bench:<id>:
"""

import argparse
import json
import os
import time
import uuid
from urllib.parse import parse_qs

import common  # noqa: F401  (adds backend/ to sys.path)
import psutil
import uvicorn
from common import BENCH_KEY_ROOT, bench_redis

from app.cache.redis_client import create_redis_client
from app.cache.search_cache import SearchCache, get_search_cache
from app.core.config import get_settings
from app.main import app

CLOSED_PORT_URL = "redis://127.0.0.1:6390/0"  # nothing listens here


class BenchState:
    def __init__(self, run_prefix: str) -> None:
        if not run_prefix.startswith(BENCH_KEY_ROOT):
            raise SystemExit(f"--run-prefix must start with {BENCH_KEY_ROOT!r}")
        self.run_prefix = run_prefix
        self.settings = get_settings()
        self.redis = bench_redis()
        self.cache = SearchCache(client=None)
        self.process = psutil.Process(os.getpid())

    def switch(self, mode: str) -> dict:
        if mode == "off":
            self.cache = SearchCache(client=None)
            return {"mode": mode}
        if mode == "on":
            prefix = f"{self.run_prefix}{uuid.uuid4().hex[:12]}:"
            self.cache = SearchCache(
                self.redis,
                ttl_seconds=self.settings.search_cache_ttl_seconds,
                cooldown_seconds=self.settings.redis_retry_cooldown_seconds,
                key_prefix=prefix,
            )
            return {"mode": mode, "prefix": prefix}
        if mode == "down":
            down = self.settings.model_copy(update={"redis_url": CLOSED_PORT_URL})
            self.cache = SearchCache(
                create_redis_client(down),
                cooldown_seconds=self.settings.redis_retry_cooldown_seconds,
                key_prefix=f"{self.run_prefix}down:",
            )
            return {"mode": mode}
        raise ValueError(mode)


class BenchWrapper:
    """Pure ASGI wrapper: timing header + benchmark control endpoints."""

    def __init__(self, inner, state: BenchState) -> None:
        self.inner = inner
        self.state = state

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.inner(scope, receive, send)
        path = scope["path"]
        if path.startswith("/__bench/"):
            return await self._control(scope, send)

        started = time.perf_counter()

        async def send_with_timing(message):
            if message["type"] == "http.response.start":
                duration = (time.perf_counter() - started) * 1000
                headers = list(message.get("headers", []))
                headers.append((b"server-timing", f"app;dur={duration:.3f}".encode()))
                message = {**message, "headers": headers}
            await send(message)

        return await self.inner(scope, receive, send_with_timing)

    async def _control(self, scope, send):
        query = parse_qs(scope.get("query_string", b"").decode())
        try:
            if scope["path"] == "/__bench/cache":
                body = self.state.switch(query.get("mode", ["off"])[0])
            elif scope["path"] == "/__bench/rss":
                body = {"rss_mb": round(self.state.process.memory_info().rss / 1024**2, 1)}
            else:
                raise ValueError("unknown benchmark endpoint")
            status = 200
        except ValueError as exc:
            body, status = {"error": str(exc)}, 400
        payload = json.dumps(body).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": payload})


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark-only API server")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--run-prefix", required=True)
    args = parser.parse_args()

    state = BenchState(args.run_prefix)
    # Runtime-only override in this process: the app's search cache = state.cache.
    app.dependency_overrides[get_search_cache] = lambda: state.cache
    uvicorn.run(
        BenchWrapper(app, state),
        host="127.0.0.1",
        port=args.port,
        workers=1,
        log_level="warning",
        access_log=False,
    )


if __name__ == "__main__":
    main()
