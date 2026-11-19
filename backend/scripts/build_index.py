"""Build the inverted index from PostgreSQL once and print statistics (for inspection).

Usage (from backend/):
    python -m scripts.build_index
    python -m scripts.build_index --top 20 --lookup laptop wireless

Note: this builds a separate copy for inspection. To refresh the index inside a running
API server, call POST /api/v1/search/rebuild-index instead.
"""

import argparse

from app.database.session import SessionLocal
from app.search.index_manager import build_index_from_db
from app.search.text_processing import query_terms


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build the search index and show stats.")
    parser.add_argument("--top", type=int, default=15, help="most common terms to list")
    parser.add_argument("--lookup", nargs="*", default=[], help="words to look up")
    args = parser.parse_args(argv)

    with SessionLocal() as session:
        index = build_index_from_db(session)

    stats = index.stats()
    print(f"Indexed products : {stats.documents:,}")
    print(f"Distinct terms   : {stats.terms:,}")
    print(f"Postings         : {stats.postings:,}  (term -> product pairs)")
    print(f"Build time       : {stats.build_seconds:.3f}s (excluding nothing; includes DB fetch)")
    print(f"\nTop {args.top} terms by number of products:")
    for term, count in index.most_common_terms(args.top):
        print(f"  {term:<15} {count:>6,}")
    for word in args.lookup:
        terms = query_terms(word)
        ids = index.match_all(terms) if terms else []
        print(f"\nlookup {word!r} -> terms {terms} -> {len(ids):,} products {ids[:10]}")


if __name__ == "__main__":
    main()
