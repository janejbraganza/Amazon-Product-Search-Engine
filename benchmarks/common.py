"""Shared helpers for the Phase 7 benchmarks (no application code lives here).

- ``summarize``         latency statistics (mean, p50, p95, p99, min, max, requests/s)
- ``environment``       hardware / software / dataset description, credentials removed
- ``bench_redis``       Redis client for database 15 (never the app's database 0)
- ``cleanup_prefix``    deletes ONLY keys under a benchmark-owned prefix (SCAN + DEL);
                        FLUSHDB / FLUSHALL are never used anywhere in the benchmarks.
"""

import json
import math
import os
import platform
import statistics
import subprocess
import sys
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

BENCH_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BENCH_DIR.parent / "backend"
RESULTS_DIR = BENCH_DIR / "results" / "latest"
sys.path.insert(0, str(BACKEND_DIR))

BENCH_REDIS_DB = 15
BENCH_KEY_ROOT = "pse-bench:"  # every benchmark key starts with this

# Fixed query set shared by every benchmark (name -> /api/v1/search parameters).
SEARCH_QUERIES: dict[str, dict] = {
    "simple: laptop": {"q": "laptop"},
    "multi-term (all): wireless bluetooth headphones": {"q": "wireless bluetooth headphones"},
    "multi-term (any): wireless bluetooth headphones": {
        "q": "wireless bluetooth headphones",
        "mode": "any",
    },
    "multi-term (all): wireless earbuds": {"q": "wireless earbuds"},
    "common term: ideal": {"q": "ideal"},
    "prefix: lap": {"q": "lap", "prefix": "true"},
    "prefix: wireless ear": {"q": "wireless ear", "prefix": "true"},
    "prefix: s": {"q": "s", "prefix": "true"},
}
AUTOCOMPLETE_QUERY = {"q": "ear"}  # GET /api/v1/search/suggestions


# ---- Statistics -----------------------------------------------------------------------


def percentile(sorted_values: list[float], pct: float) -> float:
    """Linear-interpolated percentile (same method as numpy's default)."""
    if not sorted_values:
        return math.nan
    rank = (len(sorted_values) - 1) * pct / 100
    low, high = math.floor(rank), math.ceil(rank)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (rank - low)


def summarize(samples_ms: list[float], wall_seconds: float | None = None) -> dict:
    """Latency stats in ms. Throughput = requests / wall time if given, else 1000 / mean."""
    values = sorted(samples_ms)
    mean = statistics.fmean(values)
    rps = len(values) / wall_seconds if wall_seconds else 1000 / mean
    return {
        "n": len(values),
        "mean": round(mean, 3),
        "p50": round(percentile(values, 50), 3),
        "p95": round(percentile(values, 95), 3),
        "p99": round(percentile(values, 99), 3),
        "min": round(values[0], 3),
        "max": round(values[-1], 3),
        "stdev": round(statistics.stdev(values), 3) if len(values) > 1 else 0.0,
        "rps": round(rps, 1),
    }


# ---- Environment ------------------------------------------------------------------------


def _cpu_name() -> str:
    if sys.platform == "win32":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            )
            return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
        except OSError:
            pass
    return platform.processor() or "unknown"


def _docker(cmd: list[str]) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


def environment(extra: dict | None = None) -> dict:
    import psutil

    from app.core.config import get_settings

    settings = get_settings()
    db_url = urlsplit(settings.database_url)
    pkgs = ["fastapi", "uvicorn", "starlette", "sqlalchemy", "psycopg", "redis", "httpx",
            "pydantic"]  # fmt: skip
    info = {
        "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "os": platform.platform(),
        "cpu": _cpu_name(),
        "logical_cpus": os.cpu_count(),
        "physical_cpus": psutil.cpu_count(logical=False),
        "ram_gb": round(psutil.virtual_memory().total / 1024**3, 1),
        "python": sys.version.split()[0],
        "packages": {p: _version(p) for p in pkgs},
        "postgres": _docker(["docker", "exec", "pse-postgres", "postgres", "--version"]),
        "redis": _docker(["docker", "exec", "pse-redis", "redis-server", "--version"]).split(
            " sha="
        )[0],
        # Host/port/database only: credentials are never recorded.
        "database": f"{db_url.hostname}:{db_url.port}{db_url.path}",
        "redis_bench_db": BENCH_REDIS_DB,
        "settings": {
            "search_cache_ttl_seconds": settings.search_cache_ttl_seconds,
            "redis_timeout_seconds": settings.redis_timeout_seconds,
            "redis_retry_cooldown_seconds": settings.redis_retry_cooldown_seconds,
        },
    }
    info.update(extra or {})
    return info


def _version(package: str) -> str:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return "not installed"


# ---- Redis safety ---------------------------------------------------------------------


def bench_redis_url() -> str:
    from app.core.config import get_settings

    parts = urlsplit(get_settings().redis_url)
    return urlunsplit(parts._replace(path=f"/{BENCH_REDIS_DB}"))


def bench_redis():
    from app.cache.redis_client import create_redis_client
    from app.core.config import get_settings

    settings = get_settings().model_copy(update={"redis_url": bench_redis_url()})
    return create_redis_client(settings)


def cleanup_prefix(client, prefix: str) -> int:
    """Delete keys under ``prefix`` only. Refuses prefixes outside the benchmark root."""
    if not prefix.startswith(BENCH_KEY_ROOT) or len(prefix) <= len(BENCH_KEY_ROOT):
        raise ValueError(f"Refusing to clean non-benchmark prefix {prefix!r}")
    deleted = 0
    for key in client.scan_iter(match=f"{prefix}*", count=500):
        deleted += client.delete(key)
    return deleted


def count_bench_keys() -> dict[str, int]:
    """Benchmark keys left in DB 0 and DB 15 (should both be 0 after a run)."""
    from app.cache.redis_client import create_redis_client
    from app.core.config import get_settings

    counts = {}
    for db in (0, BENCH_REDIS_DB):
        url = urlunsplit(urlsplit(get_settings().redis_url)._replace(path=f"/{db}"))
        client = create_redis_client(get_settings().model_copy(update={"redis_url": url}))
        counts[f"db{db}"] = sum(1 for _ in client.scan_iter(match=f"{BENCH_KEY_ROOT}*"))
        client.close()
    return counts


# ---- Results files ----------------------------------------------------------------------


def save_json(name: str, data: dict) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / name
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def load_json(name: str) -> dict:
    return json.loads((RESULTS_DIR / name).read_text(encoding="utf-8"))
