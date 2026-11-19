"""Search endpoints.

GET  /api/v1/search                  keyword search (BM25-ranked), optional prefix expansion,
                                     cached in Redis (see services/cached_search.py)
GET  /api/v1/search/suggestions      autocomplete: words starting with a prefix (Trie)
POST /api/v1/search/rebuild-index    rebuild index + statistics + Trie from the database

The routes are plain ``def`` (not ``async def``), so FastAPI runs them in its thread pool:
blocking calls to PostgreSQL and Redis never block the event loop.
"""

from dataclasses import asdict
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.cache.search_cache import SearchCache, get_search_cache
from app.core.config import Settings, get_settings
from app.database.session import get_db
from app.schemas.search import (
    IndexStatsResponse,
    SearchResponse,
    Suggestion,
    SuggestionResponse,
)
from app.search.filters import SearchFilters, SortOption
from app.search.index_manager import SearchIndexManager, get_index_manager
from app.services.cached_search import run_cached_search
from app.services.search_service import EmptyQueryError, SearchMode, suggest_terms

router = APIRouter(prefix="/search", tags=["search"])

DbSession = Annotated[Session, Depends(get_db)]
IndexManager = Annotated[SearchIndexManager, Depends(get_index_manager)]
Cache = Annotated[SearchCache, Depends(get_search_cache)]
MAX_QUERY_LENGTH = 200
MAX_PAGE_SIZE = 100
MAX_SUGGESTIONS = 50
CACHE_HEADER = "X-Cache"
MAX_FILTER_VALUES = 20  # per repeatable filter (category, brand)
MAX_PRICE = Decimal("99999999.99")  # products.price is NUMERIC(10, 2)


@router.get("", response_model=SearchResponse)
def search(
    db: DbSession,
    manager: IndexManager,
    cache: Cache,
    response: Response,
    q: Annotated[str, Query(min_length=1, max_length=MAX_QUERY_LENGTH, description="Search words")],
    mode: Annotated[SearchMode, Query(description="all = AND, any = OR")] = SearchMode.ALL,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    prefix: Annotated[
        bool, Query(description="Treat the last word as a prefix (e.g. 'lap' -> 'laptop')")
    ] = False,
    sort: Annotated[
        SortOption, Query(description="relevance (BM25), price_asc, price_desc, rating, newest")
    ] = SortOption.RELEVANCE,
    category: Annotated[
        list[str] | None,
        Query(
            max_length=MAX_FILTER_VALUES,
            description="Only these categories (repeatable, case-insensitive)",
        ),
    ] = None,
    brand: Annotated[
        list[str] | None,
        Query(
            max_length=MAX_FILTER_VALUES,
            description="Only these brands (repeatable, case-insensitive)",
        ),
    ] = None,
    min_price: Annotated[
        Decimal | None, Query(ge=0, le=MAX_PRICE, decimal_places=2, description="Lowest price")
    ] = None,
    max_price: Annotated[
        Decimal | None, Query(ge=0, le=MAX_PRICE, decimal_places=2, description="Highest price")
    ] = None,
    min_rating: Annotated[
        Decimal | None,
        Query(ge=0, le=5, decimal_places=1, description="Lowest rating (0-5, one decimal)"),
    ] = None,
    in_stock: Annotated[
        bool, Query(description="true: only products with stock; false: no stock filter")
    ] = False,
) -> SearchResponse:
    """Find products whose name, description, brand or category contain the query words.

    Matches are ranked by BM25 relevance (ties by product id), then filtered, then sorted
    (``sort``), then paginated. ``facets`` counts categories and brands over all matches.
    The ``X-Cache`` response header says whether Redis served it: HIT, MISS or BYPASS.
    """
    if not q.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Query must not be blank")
    try:
        filters = SearchFilters.create(
            categories=category or (),
            brands=brand or (),
            min_price=min_price,
            max_price=max_price,
            min_rating=min_rating,
            in_stock=in_stock,
        )
    except ValueError as exc:  # e.g. min_price > max_price, blank category
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    # Take ONE index reference and use it for the cache key, ranking, filtering, sorting and
    # facets, so a rebuild during this request cannot mix two different index snapshots.
    index = manager.get_index(db)
    try:
        body, cache_status = run_cached_search(
            db,
            index,
            cache,
            q,
            mode=mode,
            limit=limit,
            offset=offset,
            prefix=prefix,
            filters=filters,
            sort=sort,
        )
    except EmptyQueryError as exc:  # invalid queries are rejected before the cache is used
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    response.headers[CACHE_HEADER] = cache_status.value
    return body


@router.get("/suggestions", response_model=SuggestionResponse)
def suggestions(
    db: DbSession,
    manager: IndexManager,
    q: Annotated[
        str, Query(min_length=1, max_length=MAX_QUERY_LENGTH, description="Text typed so far")
    ],
    limit: Annotated[int, Query(ge=1, le=MAX_SUGGESTIONS, description="Max suggestions")] = 10,
) -> SuggestionResponse:
    """Autocomplete: indexed words that start with the last word of ``q``.

    Ordered by how many products contain the word, then alphabetically.
    """
    if not q.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Query must not be blank")
    try:
        partial, found = suggest_terms(manager.get_index(db), q, limit=limit)
    except EmptyQueryError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return SuggestionResponse(
        query=q,
        prefix=partial,
        suggestions=[
            Suggestion(term=s.term, product_count=s.product_count, display=s.display) for s in found
        ],
    )


@router.post("/rebuild-index", response_model=IndexStatsResponse)
def rebuild_index(
    db: DbSession,
    manager: IndexManager,
    settings: Annotated[Settings, Depends(get_settings)],
) -> IndexStatsResponse:
    """Rebuild the search index from the database (call after product data changes).

    Disabled when APP_ENV=production until authentication is added.
    """
    if settings.app_env == "production":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    index = manager.rebuild(db)
    return IndexStatsResponse(**asdict(index.stats()))
