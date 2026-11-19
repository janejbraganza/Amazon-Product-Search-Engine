"""Draw the benchmark graphs (PNG) from results/latest/components.json and http.json.

Usage (from backend/):  python ../benchmarks/plot_results.py

Colours: validated categorical palette (fixed slot order blue, orange, aqua, yellow,
magenta; colour-blind-safe adjacent pairs) on a light surface. Every number plotted
is also in results/latest/summary.md, as the table view.
"""

import common  # noqa: F401  (adds backend/ to sys.path)
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from common import RESULTS_DIR, load_json  # noqa: E402

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]  # slots 1-5, fixed order
BLUE_LIGHT = "#86b6ef"  # blue step 250: second step of the same hue (ordinal)

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.size": 10,
        "text.color": TEXT,
        "axes.labelcolor": TEXT_2,
        "axes.edgecolor": GRID,
        "xtick.color": TEXT_2,
        "ytick.color": TEXT_2,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "axes.axisbelow": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "axes.titleweight": "bold",
        "axes.titlesize": 12,
        "axes.titlelocation": "left",
    }
)


def save(fig, name: str) -> None:
    fig.tight_layout()
    path = RESULTS_DIR / name
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"wrote {path}")


def top_legend(ax) -> None:
    """One legend row between the title and the plot, so it never covers data."""
    handles, _ = ax.get_legend_handles_labels()
    ncol = min(len(handles), 4)
    rows = -(-len(handles) // ncol)  # ceiling division
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=ncol,
              borderaxespad=0.3, handlelength=1.2, columnspacing=1.2)  # fmt: skip
    # Titles are left-aligned; lift the title above the legend row(s).
    ax.set_title(ax.get_title(loc="left"), loc="left", pad=10 + 20 * rows)


def hbar_groups(ax, labels, series: list[tuple[str, list[float], str]], fmt="{:.1f}"):
    """Grouped horizontal bars; a surface-coloured edge leaves a 2px gap between bars."""
    n = len(series)
    height = 0.8 / n
    for s, (name, values, color) in enumerate(series):
        ys = [i + (s - (n - 1) / 2) * height for i in range(len(labels))]
        bars = ax.barh(ys, values, height=height, color=color, label=name,
                       edgecolor=SURFACE, linewidth=2)  # fmt: skip
        for bar, value in zip(bars, values, strict=True):
            ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2, " " + fmt.format(value),
                    va="center", fontsize=7.5, color=TEXT_2)  # fmt: skip
    ax.set_yticks(range(len(labels)), labels)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)


def short(name: str) -> str:
    return name.replace("multi-term ", "").replace(": ", "\n", 1)


def latency_by_query(http: dict) -> None:
    seq = http["sequential"]
    names = list(seq["queries"])
    labels = [short(n) for n in names] + ["autocomplete\near", "baseline\n/health"]
    rows = [seq["queries"][n]["no_cache"]["client_ms"] for n in names]
    rows += [seq["autocomplete: ear"]["client_ms"], seq["health"]["client_ms"]]
    fig, ax = plt.subplots(figsize=(9, 7))
    hbar_groups(ax, labels, [
        ("p50 (median)", [r["p50"] for r in rows], SERIES[0]),
        ("p95", [r["p95"] for r in rows], BLUE_LIGHT),
    ])  # fmt: skip
    ax.set_xlabel("client latency, ms (no cache, 1 client)")
    ax.set_title("Search latency by query type (10,000 products)")
    top_legend(ax)
    save(fig, "latency_by_query.png")


def cache_comparison(http: dict) -> None:
    q = http["sequential"]["queries"]
    names = list(q)
    fig, ax = plt.subplots(figsize=(9, 8.5))
    hbar_groups(ax, [short(n) for n in names], [
        ("no cache", [q[n]["no_cache"]["client_ms"]["p50"] for n in names], SERIES[0]),
        ("cache miss", [q[n]["cache_miss"]["client_ms"]["p50"] for n in names], SERIES[1]),
        ("cache hit", [q[n]["cache_hit"]["client_ms"]["p50"] for n in names], SERIES[2]),
        ("Redis down (cooldown)",
         [q[n]["redis_down_cooldown"]["client_ms"]["p50"] for n in names], SERIES[3]),
    ])  # fmt: skip
    ax.set_xlabel("median client latency, ms (1 client)")
    ax.set_title("Cached vs uncached search (p50)")
    top_legend(ax)
    save(fig, "cache_comparison.png")


def concurrency_charts(http: dict) -> None:
    conc = http["concurrency"]
    styles = [("uncached", "no cache", SERIES[0]), ("cache_hit", "cache hit", SERIES[1])]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=False)
    for ax, pct in zip(axes, ["p50", "p95"], strict=True):
        for key, label, color in styles:
            levels = sorted(conc[key], key=int)
            xs = [int(lv) for lv in levels]
            ys = [conc[key][lv]["latency_ms"][pct] for lv in levels]
            ax.plot(xs, ys, color=color, linewidth=2, marker="o", markersize=7, label=label,
                    markeredgecolor=SURFACE, markeredgewidth=2)  # fmt: skip
            ax.annotate(f"{ys[-1]:.0f} ms", (xs[-1], ys[-1]), textcoords="offset points",
                        xytext=(6, 0), va="center", fontsize=8, color=TEXT_2)  # fmt: skip
        ax.set_xticks([1, 5, 10, 20])
        ax.set_xlabel("concurrent clients")
        ax.set_ylabel(f"{pct} latency, ms")
        ax.set_title(f"Latency vs concurrency ({pct})")
        ax.set_ylim(bottom=0)
    axes[0].legend(loc="upper left")
    save(fig, "concurrency_latency.png")

    fig, ax = plt.subplots(figsize=(7, 4.2))
    for key, label, color in styles:
        levels = sorted(conc[key], key=int)
        xs = [int(lv) for lv in levels]
        ys = [conc[key][lv]["latency_ms"]["rps"] for lv in levels]
        ax.plot(xs, ys, color=color, linewidth=2, marker="o", markersize=7, label=label,
                markeredgecolor=SURFACE, markeredgewidth=2)  # fmt: skip
        for x, y in zip(xs, ys, strict=True):
            ax.annotate(f"{y:.0f}", (x, y), textcoords="offset points", xytext=(0, 8),
                        ha="center", fontsize=8, color=TEXT_2)  # fmt: skip
    ax.set_xticks([1, 5, 10, 20])
    ax.set_xlabel("concurrent clients")
    ax.set_ylabel("requests per second")
    ax.set_ylim(bottom=0)
    ax.set_title("Throughput vs concurrency (mixed query set)")
    ax.legend(loc="upper left")
    save(fig, "concurrency_throughput.png")


def scaling(components: dict) -> None:
    sc = components["scaling"]
    sizes = sorted(sc, key=int)
    xs = [int(s) for s in sizes]
    panels = [
        ("Index build time", "ms (p50)", [sc[s]["index_build_ms"]["p50"] for s in sizes], "{:.0f}"),
        ("Index memory", "MB (tracemalloc)", [sc[s]["index_memory_mb"] for s in sizes], "{:.1f}"),
        ("Trie build time", "ms (p50)", [sc[s]["trie_build_ms"]["p50"] for s in sizes], "{:.1f}"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    for ax, (title, unit, ys, fmt) in zip(axes, panels, strict=True):
        ax.plot(xs, ys, color=SERIES[0], linewidth=2, marker="o", markersize=7,
                markeredgecolor=SURFACE, markeredgewidth=2)  # fmt: skip
        for x, y in zip(xs, ys, strict=True):
            ax.annotate(fmt.format(y), (x, y), textcoords="offset points", xytext=(0, 8),
                        ha="center", fontsize=8, color=TEXT_2)  # fmt: skip
        ax.set_title(title)
        ax.set_ylabel(unit)
        ax.set_xlabel("products")
        ax.set_xticks(xs, [f"{x:,}" for x in xs])
        ax.set_ylim(bottom=0, top=max(ys) * 1.2)
    save(fig, "scaling.png")


def request_breakdown(components: dict) -> None:
    bd = components["request_breakdown_10k"]
    sc = components["scaling"]["10000"]["queries"]
    names = list(bd)
    parts = {
        "matching": [sc[n]["match_ms"]["p50"] for n in names],
        "BM25 scoring": [sc[n]["bm25_scoring_median_ms"] for n in names],
        "DB page fetch + other": [
            max(bd[n]["search_products_ms"]["p50"] - bd[n]["rank_ms"]["p50"], 0) for n in names
        ],
        "build response": [bd[n]["build_response_ms"]["p50"] for n in names],
        "JSON serialise": [bd[n]["serialize_json_ms"]["p50"] for n in names],
    }
    fig, ax = plt.subplots(figsize=(9, 6))
    left = [0.0] * len(names)
    for (label, values), color in zip(parts.items(), SERIES, strict=True):
        ax.barh(range(len(names)), values, left=left, color=color, label=label, height=0.6,
                edgecolor=SURFACE, linewidth=2)  # fmt: skip
        left = [a + b for a, b in zip(left, values, strict=True)]
    for i, total in enumerate(left):
        ax.text(total, i, f" {total:.1f} ms", va="center", fontsize=8, color=TEXT_2)
    ax.set_yticks(range(len(names)), [short(n) for n in names])
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("ms (p50, in-process, one reused DB session)")
    ax.set_title("Where uncached search time goes (server work only)")
    top_legend(ax)
    save(fig, "request_breakdown.png")


def main() -> None:
    components = load_json("components.json")
    http = load_json("http.json")
    latency_by_query(http)
    cache_comparison(http)
    concurrency_charts(http)
    scaling(components)
    request_breakdown(components)


if __name__ == "__main__":
    main()
