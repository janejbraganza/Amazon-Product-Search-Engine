"""Search with a Redis cache in front (the "cache-aside" pattern).

    1. Normalise the query and build the cache key (needs the index's build_id).
    2. Look the key up in Redis.  Found      -> return it            (X-Cache: HIT)
    3. Not found: run the normal search engine (BM25, Trie unchanged).
    4. Store the response in Redis with a TTL                        (X-Cache: MISS)
       ...unless the cache is off, Redis is down, or the result is
       not safe to cache                                             (X-Cache: BYPASS)

The SAME InvertedIndex object supplies the key's build_id and ranks the results, so a
result is always stored under the ID of the index that actually produced it, even if a
rebuild swaps in a new index while this request is running.
"""

import logging

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.cache.search_cache import CacheStatus, SearchCache
from app.schemas.product import ProductRead
from app.schemas.search import FacetValue, SearchFacets, SearchResponse, SearchResultItem
from app.search.filters import SearchFilters, SortOption
from app.search.inverted_index import DEFAULT_MAX_EXPANSIONS, SCORE_DECIMALS, InvertedIndex
from app.services.search_service import (
    SearchHit,
    SearchMode,
    SearchResult,
    parse_query,
    search_products,
)

logger = logging.getLogger(__name__)


def cache_params(
    query: str,
    mode: SearchMode,
    prefix: bool,
    limit: int,
    offset: int,
    filters: SearchFilters | None = None,
    sort: SortOption = SortOption.RELEVANCE,
) -> dict[str, object]:
    """Everything that changes the response, in normalised form (raises EmptyQueryError)."""
    terms, partial = parse_query(query, prefix)
    return {
        "terms": terms,  # normalised, in typed order ("LAPTOPS" and "laptop" share a key)
        "partial": partial,  # unfinished last word (prefix search), else None
        "mode": mode.value,
        "prefix": prefix,
        "limit": limit,
        "offset": offset,
        "max_expansions": DEFAULT_MAX_EXPANSIONS,
        # Filters in canonical form: case-folded, sorted, exact decimals, so equivalent
        # requests ("Electronics" vs "electronics") share an entry and different ones never do.
        "filters": (filters or SearchFilters()).cache_params(),
        "sort": sort.value,
    }


def run_cached_search(
    db: Session,
    index: InvertedIndex,
    cache: SearchCache,
    query: str,
    mode: SearchMode,
    limit: int,
    offset: int,
    prefix: bool,
    filters: SearchFilters | None = None,
    sort: SortOption = SortOption.RELEVANCE,
) -> tuple[SearchResponse, CacheStatus]:
    key = cache.build_key(
        index.build_id, cache_params(query, mode, prefix, limit, offset, filters, sort)
    )

    lookup = cache.get(key)
    if lookup.status is CacheStatus.HIT:
        try:
            cached = SearchResponse.model_validate_json(lookup.value)
        except ValidationError:
            logger.warning("Ignoring unreadable search cache entry %s", key)
        else:
            # "query" is the only field that echoes the raw input; the rest depends only
            # on the normalised parameters in the key.
            return cached.model_copy(update={"query": query}), CacheStatus.HIT

    result = search_products(
        db,
        index,
        query,
        mode=mode,
        limit=limit,
        offset=offset,
        prefix=prefix,
        filters=filters,
        sort=sort,
    )
    response = build_search_response(result, limit, offset)

    # Only cache complete pages: if products vanished since the last rebuild, the page is
    # short and would stay wrong for the whole TTL.
    stored = False
    if lookup.status is not CacheStatus.BYPASS and result.skipped_products == 0:
        stored = cache.set(key, response.model_dump_json())
    return response, CacheStatus.MISS if stored else CacheStatus.BYPASS


def build_search_response(result: SearchResult, limit: int, offset: int) -> SearchResponse:
    return SearchResponse(
        query=result.query,
        terms=result.terms,
        unmatched_terms=result.unmatched_terms,
        mode=result.mode,
        total=result.total,
        limit=limit,
        offset=offset,
        items=[_to_item(hit) for hit in result.items],
        prefix=result.prefix,
        expanded_terms=result.expanded_terms,
        sort=result.sort,
        facets=SearchFacets(
            categories=[FacetValue(value=f.value, count=f.count) for f in result.facets.categories],
            brands=[FacetValue(value=f.value, count=f.count) for f in result.facets.brands],
        ),
    )


def _to_item(hit: SearchHit) -> SearchResultItem:
    fields = {name: getattr(hit.product, name) for name in ProductRead.model_fields}
    # Same rounding as the ranking tie-break, so equal displayed scores are true ties.
    return SearchResultItem(**fields, score=round(hit.score, SCORE_DECIMALS))
