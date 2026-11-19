# ruff: noqa: E501  (this file mostly builds Markdown table rows; long lines read better)
"""Run the complete Phase 7 benchmark and write results/latest/.

Usage (from backend/, with `docker compose up -d` and the 10,000 products loaded):
    python ../benchmarks/run_all.py              # full run (about 10-15 minutes)
    python ../benchmarks/run_all.py --quick      # smoke test with few repetitions

Steps (each benchmark runs in its own process, so they cannot affect each other):
  1. bench_components.py   in-process: build times, BM25 vs matching, Trie, memory, scaling
  2. bench_http.py         real uvicorn server: latency (no cache / miss / hit / Redis
                           down), autocomplete, concurrency 1-20 with correctness checks
  3. plot_results.py       PNG graphs
  4. summary.md            every number in table form, plus the environment
  5. safety check          no benchmark keys left in Redis DB 0 or DB 15
"""

import argparse
import subprocess
import sys

import common
from common import BENCH_DIR, RESULTS_DIR, count_bench_keys, environment, load_json, save_json


def run(script: str, *args: str) -> None:
    print(f"\n=== {script} {' '.join(args)}")
    subprocess.run([sys.executable, str(BENCH_DIR / script), *args], check=True)


def fmt_stats(s: dict) -> str:
    return f"{s['mean']:.2f} | {s['p50']:.2f} | {s['p95']:.2f} | {s['p99']:.2f} | {s['min']:.2f} | {s['max']:.2f} | {s['rps']:.1f}"


def write_summary(env: dict) -> None:
    comp = load_json("components.json")
    http = load_json("http.json")
    seq = http["sequential"]
    lines = ["# Benchmark results (latest run)", ""]

    lines += ["## Environment", "", "| Item | Value |", "|---|---|"]
    for key in ["timestamp_utc", "os", "cpu", "logical_cpus", "physical_cpus", "ram_gb",
                "python", "postgres", "redis", "database"]:  # fmt: skip
        lines.append(f"| {key} | {env[key]} |")
    lines.append(f"| packages | {', '.join(f'{k} {v}' for k, v in env['packages'].items())} |")
    lines.append(f"| cache settings | {env['settings']} |")
    lines.append(
        f"| run settings | {http['repeat']} measured requests per scenario after "
        f"{http['warmup']} warm-up; Redis-down {http['down_repeat']}; "
        f"{http['concurrent_requests_per_level']} requests per concurrency level |"
    )
    lines += [
        "",
        "Columns: mean | p50 | p95 | p99 | min | max (ms) | requests/s (1 client = 1000/mean)",
        "",
    ]

    def table(title: str, rows: list[tuple[str, dict]]) -> None:
        nonlocal lines
        lines += [f"## {title}", "", "| Scenario | mean | p50 | p95 | p99 | min | max | req/s |",
                  "|---|---|---|---|---|---|---|---|"]  # fmt: skip
        lines += [f"| {name} | {fmt_stats(stats)} |" for name, stats in rows]
        lines.append("")

    for scenario, label in [("no_cache", "No cache"), ("cache_miss", "Cache miss"),
                            ("cache_hit", "Cache hit"),
                            ("redis_down_cooldown", "Redis unavailable (during cooldown)")]:  # fmt: skip
        table(
            f"HTTP client latency - {label} (1 client)",
            [(n, q[scenario]["client_ms"]) for n, q in seq["queries"].items()],
        )
    table(
        "HTTP server-side time (Server-Timing) - no cache",
        [(n, q["no_cache"]["server_ms"]) for n, q in seq["queries"].items()],
    )
    table(
        "HTTP server-side time (Server-Timing) - cache hit",
        [(n, q["cache_hit"]["server_ms"]) for n, q in seq["queries"].items()],
    )
    table(
        "Other endpoints (client latency, 1 client)",
        [("autocomplete: ear", seq["autocomplete: ear"]["client_ms"]),
         ("/health (HTTP + framework floor)", seq["health"]["client_ms"])],
    )  # fmt: skip
    lines += ["## Redis unavailable - first request (pays the connection timeout)", "",
              "| Query | client ms | server ms |", "|---|---|---|"]  # fmt: skip
    for n, q in seq["queries"].items():
        first = q["redis_down_first_request_ms"]
        lines.append(f"| {n} | {first['client']:.1f} | {first['server']:.1f} |")
    lines.append("")

    lines += ["## Concurrency (round-robin mix of all queries)", "",
              "| Cache | Clients | Requests | Errors | Incorrect | req/s | mean | p50 | p95 | p99 | max |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for key, label in [("uncached", "no cache"), ("cache_hit", "cache hit")]:
        for level, r in sorted(http["concurrency"][key].items(), key=lambda kv: int(kv[0])):
            s = r["latency_ms"]
            lines.append(
                f"| {label} | {level} | {r['requests']} | {r['errors']} | {r['incorrect']} | "
                f"{s['rps']:.1f} | {s['mean']:.1f} | {s['p50']:.1f} | {s['p95']:.1f} | "
                f"{s['p99']:.1f} | {s['max']:.1f} |"
            )
    lines.append("")

    lines += ["## In-process components (10,000 products)", "",
              "| Query | matches | matching p50 | ranking total p50 | BM25 scoring (p50 diff) | "
              "search_products p50 | build response p50 | JSON p50 |",
              "|---|---|---|---|---|---|---|---|"]  # fmt: skip
    q10 = comp["scaling"]["10000"]["queries"]
    for n, bd in comp["request_breakdown_10k"].items():
        q = q10[n]
        lines.append(
            f"| {n} | {q['matches']} | {q['match_ms']['p50']:.3f} | {q['rank_total_ms']['p50']:.3f} | "
            f"{q['bm25_scoring_median_ms']:.3f} | {bd['search_products_ms']['p50']:.3f} | "
            f"{bd['build_response_ms']['p50']:.3f} | {bd['serialize_json_ms']['p50']:.3f} |"
        )
    lines += ["", "| Autocomplete (Trie) | suggestions | complete_prefix p50 ms |", "|---|---|---|"]
    for n, q in q10.items():
        if n.startswith("autocomplete"):
            lines.append(f"| {n} | {q['suggestions']} | {q['complete_prefix_ms']['p50']:.4f} |")
    db = comp["database"]
    lines += ["", "| PostgreSQL (10,000 products) | p50 ms |", "|---|---|",
              f"| stream all products for an index build | {db['load_all_documents_ms']['p50']:.1f} |",
              f"| fetch a 20-product page (reused session) | {db['fetch_20_product_page_ms']['p50']:.2f} |",
              f"| fetch a 20-product page (new session, as per request) | {db['fetch_20_product_page_new_session_ms']['p50']:.2f} |",
              f"| open + close a session (connection checkout) | {db['session_checkout_and_close_ms']['p50']:.2f} |",
              ""]  # fmt: skip

    lines += ["## Catalogue scaling (in-process, seed 42)", "",
              "| Products | Terms | Postings | Trie nodes | Index build p50 ms | Trie build p50 ms | Index memory MB |",
              "|---|---|---|---|---|---|---|"]  # fmt: skip
    for size, s in sorted(comp["scaling"].items(), key=lambda kv: int(kv[0])):
        lines.append(
            f"| {int(size):,} | {s['terms']:,} | {s['postings']:,} | {s['trie_nodes']:,} | "
            f"{s['index_build_ms']['p50']:.0f} | {s['trie_build_ms']['p50']:.2f} | {s['index_memory_mb']} |"
        )
    lines += ["", "| Query (ranking total p50 ms) | " + " | ".join(f"{int(s):,}" for s in sorted(comp["scaling"], key=int)) + " |",
              "|---|" + "---|" * len(comp["scaling"])]  # fmt: skip
    for n in q10:
        if "rank_total_ms" in q10[n]:
            vals = [
                comp["scaling"][s]["queries"][n]["rank_total_ms"]["p50"]
                for s in sorted(comp["scaling"], key=int)
            ]
            lines.append(f"| {n} | " + " | ".join(f"{v:.3f}" for v in vals) + " |")

    mem = http["memory_rss_mb"]
    lines += ["", "## Server process memory (RSS, psutil)", "", "| Point | MB |", "|---|---|",
              f"| server started (before index) | {mem['server_start']} |",
              f"| after first search (index built) | {mem['after_index_build']} |",
              f"| end of run | {mem['end_of_run']} |",
              f"| first search including index build | {http['first_search_including_index_build_s']} s |",
              ""]  # fmt: skip
    (RESULTS_DIR / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {RESULTS_DIR / 'summary.md'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run all Phase 7 benchmarks")
    parser.add_argument("--quick", action="store_true", help="few repetitions (smoke test)")
    args = parser.parse_args()

    if args.quick:
        run("bench_components.py", "--repeat", "20", "--build-repeat", "1")
        run("bench_http.py", "--repeat", "20", "--warmup", "3", "--down-repeat", "5",
            "--concurrent-requests", "40")  # fmt: skip
    else:
        run("bench_components.py")
        run("bench_http.py")
    run("plot_results.py")

    env = environment(
        {"products_in_database": load_json("components.json")["database"]["products_in_db"]}
    )
    save_json("environment.json", env)
    write_summary(env)

    leftovers = count_bench_keys()
    print(f"\nbenchmark keys left in Redis: {leftovers}")
    if any(leftovers.values()):
        raise SystemExit("benchmark keys were left behind in Redis")
    print("done:", common.RESULTS_DIR)


if __name__ == "__main__":
    main()
