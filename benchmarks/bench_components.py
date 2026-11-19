"""Layer A: in-process component benchmarks (no HTTP, no cache).

Measures the algorithms themselves by calling the application's public functions:
  - index build time (postings + BM25 statistics + Trie) for 1,000 / 5,000 / 10,000 products
  - Trie construction time on its own
  - index memory (tracemalloc: Python allocations made by the build)
  - per-query matching time vs total ranking time -> BM25 scoring time = difference
  - prefix completion (Trie) time
  - PostgreSQL: time to stream the 10,000 products, and to fetch one 20-product page

Datasets: generated with the project's seeded generator (seed 42). The 1,000 and 5,000
sets are exactly the first products of the 10,000 set. They are built in memory only;
PostgreSQL is only read (10,000-product catalogue), never written.

Usage (from backend/):  python ../benchmarks/bench_components.py [--repeat 200]
"""

import argparse
import gc
import statistics
import time
import tracemalloc

import common  # noqa: F401  (adds backend/ to sys.path)
from common import SEARCH_QUERIES, save_json, summarize

from app.database.session import SessionLocal
from app.models.product import Product
from app.search.index_manager import load_documents
from app.search.inverted_index import DEFAULT_MAX_EXPANSIONS, InvertedIndex, SearchDocument
from app.search.trie import Trie
from app.services.search_service import parse_query
from scripts.generate_products import generate_products

SIZES = [1_000, 5_000, 10_000]
SEED = 42


def to_documents(products: list[dict]) -> list[SearchDocument]:
    return [
        SearchDocument(p["id"], p["product_name"], p["description"], p["brand"], p["category"])
        for p in products
    ]


def time_ms(fn, repeat: int, warmup: int = 10) -> list[float]:
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(repeat):
        started = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - started) * 1000)
    return samples


def groups_for(index: InvertedIndex, params: dict) -> tuple[list[list[str]], bool]:
    """Build the same term groups the search service builds (production functions)."""
    prefix = params.get("prefix") == "true"
    terms, partial = parse_query(params["q"], prefix)
    groups = [[t] for t in terms]
    if partial is not None:
        groups.append(index.complete_prefix(partial, limit=DEFAULT_MAX_EXPANSIONS))
    return groups, params.get("mode", "all") == "all"


def match_only(index: InvertedIndex, groups: list[list[str]], require_all: bool) -> list[int]:
    """Matching without scoring, via public methods (same result set as rank_groups)."""
    sets = [set(index.match_any(group)) for group in groups]
    if not sets:
        return []
    if require_all:
        return sorted(set.intersection(*sets))
    return sorted(set.union(*sets))


def build_metrics(docs: list[SearchDocument], repeat: int) -> dict:
    build_s = []
    for _ in range(repeat):
        gc.collect()
        build_s.append(InvertedIndex.build(docs).stats().build_seconds)
    index = InvertedIndex.build(docs)

    vocabulary = index.most_common_terms(10**9)  # [(term, document_frequency)]

    def build_trie() -> None:
        trie = Trie()
        for term, df in vocabulary:
            trie.insert(term, df)

    trie_ms = time_ms(build_trie, repeat=repeat, warmup=2)

    gc.collect()
    tracemalloc.start()
    measured = InvertedIndex.build(docs)
    index_bytes, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    stats = measured.stats()
    return {
        "products": len(docs),
        "terms": stats.terms,
        "postings": stats.postings,
        "trie_nodes": stats.trie_nodes,
        "avg_doc_length": stats.average_document_length,
        "index_build_ms": summarize([s * 1000 for s in build_s]),
        "trie_build_ms": summarize(trie_ms),
        "index_memory_mb": round(index_bytes / 1024**2, 2),
    }, index


def query_metrics(index: InvertedIndex, repeat: int) -> dict:
    results = {}
    for name, params in SEARCH_QUERIES.items():
        groups, require_all = groups_for(index, params)
        ranked = index.rank_groups(groups, require_all)
        match_ms = time_ms(lambda g=groups, r=require_all: match_only(index, g, r), repeat)
        rank_ms = time_ms(lambda g=groups, r=require_all: index.rank_groups(g, r), repeat)
        bm25_median = statistics.median(rank_ms) - statistics.median(match_ms)
        results[name] = {
            "matches": len(ranked),
            "groups": [len(g) for g in groups],
            "match_ms": summarize(match_ms),
            "rank_total_ms": summarize(rank_ms),
            "bm25_scoring_median_ms": round(max(bm25_median, 0.0), 3),
        }
    for prefix in ["ear", "lap", "s"]:
        samples = time_ms(lambda p=prefix: index.complete_prefix(p, limit=10), repeat)
        results[f"autocomplete: {prefix}"] = {
            "suggestions": len(index.complete_prefix(prefix, limit=10)),
            "complete_prefix_ms": summarize(samples),
        }
    return results


def request_breakdown(repeat: int) -> dict:
    """Where an uncached search request's server time goes, step by step, using the same
    production functions the route calls (real 10,000-product database, read-only)."""
    from app.schemas.search import SearchResponse
    from app.search.index_manager import SearchIndexManager
    from app.services.cached_search import build_search_response
    from app.services.search_service import SearchMode, search_products

    out = {}
    with SessionLocal() as session:
        index = SearchIndexManager().get_index(session)
        for name, params in SEARCH_QUERIES.items():
            mode = SearchMode(params.get("mode", "all"))
            prefix = params.get("prefix") == "true"
            groups, require_all = groups_for(index, params)

            def service(p=params, m=mode, x=prefix):
                return search_products(session, index, p["q"], mode=m, limit=20, offset=0, prefix=x)

            result = service()
            response = build_search_response(result, 20, 0)
            cached_json = response.model_dump_json()
            out[name] = {
                "rank_ms": summarize(
                    time_ms(lambda g=groups, r=require_all: index.rank_groups(g, r), repeat)
                ),
                "search_products_ms": summarize(time_ms(service, repeat)),
                "build_response_ms": summarize(
                    time_ms(lambda r=result: build_search_response(r, 20, 0), repeat)
                ),
                "serialize_json_ms": summarize(time_ms(response.model_dump_json, repeat)),
                "validate_cached_json_ms": summarize(
                    time_ms(
                        lambda j=cached_json: SearchResponse.model_validate_json(j),
                        repeat,
                    )
                ),
                "items": len(response.items),
            }
    return out


def database_metrics(repeat: int) -> dict:
    from sqlalchemy import select

    with SessionLocal() as session:
        fetch_all = []
        for _ in range(5):
            started = time.perf_counter()
            docs = list(load_documents(session))
            fetch_all.append((time.perf_counter() - started) * 1000)
        ids = list(range(1, 10_000, 500))[:20]
        page = time_ms(
            lambda: session.scalars(select(Product).where(Product.id.in_(ids))).all(), repeat
        )

    def new_session_page() -> None:
        # What each API request does: new session -> pooled connection checkout
        # (pool_pre_ping) -> query -> close (rollback, connection returned to the pool).
        with SessionLocal() as request_session:
            request_session.scalars(select(Product).where(Product.id.in_(ids))).all()

    def new_session_only() -> None:
        with SessionLocal() as request_session:
            request_session.connection()

    return {
        "products_in_db": len(docs),
        "load_all_documents_ms": summarize(fetch_all),
        "fetch_20_product_page_ms": summarize(page),
        "fetch_20_product_page_new_session_ms": summarize(time_ms(new_session_page, repeat)),
        "session_checkout_and_close_ms": summarize(time_ms(new_session_only, repeat)),
    }


def main() -> dict:
    parser = argparse.ArgumentParser(description="In-process component benchmarks")
    parser.add_argument("--repeat", type=int, default=200)
    parser.add_argument("--build-repeat", type=int, default=5)
    args = parser.parse_args()

    all_products = generate_products(max(SIZES), SEED)
    scaling = {}
    for size in SIZES:
        docs = to_documents(all_products[:size])
        metrics, index = build_metrics(docs, args.build_repeat)
        metrics["queries"] = query_metrics(index, args.repeat)
        scaling[str(size)] = metrics
        print(
            f"{size:>6} products: build p50 {metrics['index_build_ms']['p50']:.0f} ms, "
            f"trie p50 {metrics['trie_build_ms']['p50']:.1f} ms, "
            f"memory {metrics['index_memory_mb']} MB, terms {metrics['terms']}"
        )

    db = database_metrics(args.repeat)
    print(
        f"PostgreSQL: stream 10k rows p50 {db['load_all_documents_ms']['p50']:.0f} ms, "
        f"20-row page p50 {db['fetch_20_product_page_ms']['p50']:.2f} ms"
    )
    breakdown = request_breakdown(args.repeat)
    lap = breakdown["simple: laptop"]
    print(
        "laptop breakdown p50: rank {:.2f} | search_products {:.2f} | build response {:.2f} "
        "| JSON {:.2f} ms".format(
            lap["rank_ms"]["p50"],
            lap["search_products_ms"]["p50"],
            lap["build_response_ms"]["p50"],
            lap["serialize_json_ms"]["p50"],
        )
    )
    result = {
        "seed": SEED,
        "repeat": args.repeat,
        "build_repeat": args.build_repeat,
        "scaling": scaling,
        "database": db,
        "request_breakdown_10k": breakdown,
    }
    path = save_json("components.json", result)
    print(f"saved {path}")
    return result


if __name__ == "__main__":
    main()
