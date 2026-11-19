"""Search use-cases, kept separate from the FastAPI routes so they can be tested directly.

search_products:  query text -> ranked product IDs (index) -> product rows (database).
                  match + BM25 rank -> filter -> sort -> paginate; facets are counted over
                  all matches. With prefix=True the last, partial word is expanded through
                  the Trie.
suggest_terms:    partial word -> indexed words that start with it (autocomplete).
"""

from dataclasses import dataclass, field
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.search.filters import (
    Facets,
    SearchFilters,
    SortOption,
    apply_filters,
    compute_facets,
    sort_results,
)
from app.search.inverted_index import DEFAULT_MAX_EXPANSIONS, InvertedIndex
from app.search.text_processing import query_terms, split_prefix_query, tokenize


class SearchMode(StrEnum):
    ALL = "all"  # every term must appear (AND)
    ANY = "any"  # at least one term must appear (OR)


class EmptyQueryError(ValueError):
    """The query contained no searchable words (only stop words or punctuation)."""


@dataclass(frozen=True)
class SearchHit:
    product: Product
    score: float


@dataclass(frozen=True)
class SearchResult:
    query: str
    terms: list[str]
    unmatched_terms: list[str]
    mode: SearchMode
    total: int
    items: list[SearchHit]
    prefix: str | None = None  # the partial word that was expanded (prefix search only)
    expanded_terms: list[str] = field(default_factory=list)
    # Products ranked onto this page but no longer in the database (deleted since the
    # last rebuild). Such a page is shorter than it should be, so it must not be cached.
    skipped_products: int = 0
    sort: SortOption = SortOption.RELEVANCE
    facets: Facets = field(default_factory=lambda: Facets(categories=[], brands=[]))


@dataclass(frozen=True)
class Suggestion:
    term: str
    product_count: int
    display: str = ""  # how the word is most often written ("earbuds" for "earbud")


def parse_query(query: str, prefix: bool = False) -> tuple[list[str], str | None]:
    """(complete terms, partial last word or None). Raises EmptyQueryError if nothing usable.

    Used by the search itself and by the cache key, so both see the same normalised query.
    """
    if prefix:
        terms, partial = split_prefix_query(query)
    else:
        terms, partial = query_terms(query), None
    if not terms and partial is None:
        raise EmptyQueryError("Query contains no searchable words")
    return terms, partial


def search_products(
    db: Session,
    index: InvertedIndex,
    query: str,
    mode: SearchMode = SearchMode.ALL,
    limit: int = 20,
    offset: int = 0,
    prefix: bool = False,
    max_expansions: int = DEFAULT_MAX_EXPANSIONS,
    filters: SearchFilters | None = None,
    sort: SortOption = SortOption.RELEVANCE,
) -> SearchResult:
    terms, partial = parse_query(query, prefix)
    filters = filters or SearchFilters()

    # Each group is one query word; a partial word becomes a group of its completions.
    groups = [[term] for term in terms]
    expanded: list[str] = []
    if partial is not None:
        expanded = index.complete_prefix(partial, limit=max_expansions)
        groups.append(expanded)  # an empty group matches nothing (so mode=all -> no results)

    # 1. Rank every match (unchanged BM25 ranking; pagination must come later).
    ranked = index.rank_groups(groups, require_all=mode is SearchMode.ALL)
    # 2. Facet counts over ALL matches (each facet ignores its own filter).
    facets = compute_facets(ranked, index, filters)
    # 3. Filter, then sort. With no filters and relevance sort this is the ranked list as is.
    filtered = apply_filters(ranked, index, filters)
    # Only the first offset + limit sorted results are needed to cut out the page.
    results = sort_results(filtered, index, sort, first=offset + limit)
    # 4. Cut out the requested page.
    page = results[offset : offset + limit]

    # 3. Fetch only this page's rows in one query, then restore the ranked order.
    page_ids = [doc.id for doc in page]
    rows = db.scalars(select(Product).where(Product.id.in_(page_ids))).all() if page_ids else []
    by_id = {product.id: product for product in rows}
    # A product deleted since the last rebuild is simply skipped.
    items = [SearchHit(by_id[doc.id], doc.score) for doc in page if doc.id in by_id]

    unmatched = [term for term in terms if term not in index]
    if partial is not None and not expanded:
        unmatched.append(f"{partial}*")  # "*" marks a prefix with no completions

    return SearchResult(
        query=query,
        terms=terms,
        unmatched_terms=unmatched,
        mode=mode,
        total=len(filtered),  # after filtering
        items=items,
        prefix=partial,
        expanded_terms=expanded,
        skipped_products=len(page) - len(items),
        sort=sort,
        facets=facets,
    )


def suggest_terms(
    index: InvertedIndex, query: str, limit: int = 10
) -> tuple[str, list[Suggestion]]:
    """Complete the last word of ``query``. Returns (prefix used, suggestions)."""
    tokens = tokenize(query)
    if not tokens:
        raise EmptyQueryError("Query contains no searchable characters")
    partial = tokens[-1]
    trie = index.vocabulary_trie
    suggestions = [
        Suggestion(term, trie.frequency(term), index.display_form(term))
        for term in index.complete_prefix(partial, limit)
    ]
    return partial, suggestions
