"""Server-side filtering, sorting and facet counts for search results.

All three work on the ranked list from ``InvertedIndex.rank_groups`` and on the product
metadata stored in the SAME index object, so one request always uses one consistent
snapshot (postings, BM25 statistics and metadata from the same build).

Order of operations for a search:
    match + BM25 rank (unchanged)  ->  filter  ->  sort  ->  paginate
    facets: counted over the full matching list (never just the current page)
"""

import heapq
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from app.search.inverted_index import InvertedIndex, ProductMeta, ScoredDocument


class SortOption(StrEnum):
    RELEVANCE = "relevance"  # BM25 score, ties by product id (the existing order)
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    RATING = "rating"  # highest rating first
    NEWEST = "newest"  # most recently created first


@dataclass(frozen=True)
class SearchFilters:
    """Optional filters. Several values of one dimension are OR-ed (e.g. two brands);
    different dimensions are AND-ed. Category and brand match case-insensitively."""

    categories: frozenset[str] = field(default_factory=frozenset)  # case-folded
    brands: frozenset[str] = field(default_factory=frozenset)  # case-folded
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    min_rating: Decimal | None = None
    in_stock: bool = False  # True: only products with stock_quantity > 0

    @classmethod
    def create(
        cls,
        categories: Iterable[str] = (),
        brands: Iterable[str] = (),
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        min_rating: Decimal | None = None,
        in_stock: bool = False,
    ) -> "SearchFilters":
        """Normalise raw request values. Raises ValueError for invalid combinations."""

        def keys(values: Iterable[str], name: str) -> frozenset[str]:
            cleaned = [value.strip() for value in values]
            if any(not value for value in cleaned):
                raise ValueError(f"{name} must not be blank")
            return frozenset(value.casefold() for value in cleaned)

        if min_price is not None and max_price is not None and min_price > max_price:
            raise ValueError("min_price must be less than or equal to max_price")
        return cls(
            categories=keys(categories, "category"),
            brands=keys(brands, "brand"),
            min_price=min_price,
            max_price=max_price,
            min_rating=min_rating,
            in_stock=in_stock,
        )

    @property
    def is_empty(self) -> bool:
        return self == SearchFilters()

    def matches(self, meta: ProductMeta | None, ignore: str | None = None) -> bool:
        """Does a product pass every filter? ``ignore`` skips one dimension ("category"
        or "brand"), which is how facet counts leave out their own filter."""
        if meta is None:
            return self.is_empty
        if self.categories and ignore != "category" and meta.category_key not in self.categories:
            return False
        if self.brands and ignore != "brand" and meta.brand_key not in self.brands:
            return False
        return self.matches_values(meta)

    def matches_values(self, meta: ProductMeta) -> bool:
        """The price, rating and stock filters only (the dimensions facets never ignore)."""
        if self.min_price is not None and (meta.price is None or meta.price < self.min_price):
            return False
        if self.max_price is not None and (meta.price is None or meta.price > self.max_price):
            return False
        if self.min_rating is not None and (meta.rating is None or meta.rating < self.min_rating):
            return False
        if self.in_stock and not (meta.stock_quantity or 0) > 0:
            return False
        return True

    def cache_params(self) -> dict[str, object]:
        """Canonical form for the cache key (order-independent, case-folded, exact decimals)."""
        return {
            "categories": sorted(self.categories),
            "brands": sorted(self.brands),
            "min_price": None if self.min_price is None else str(self.min_price.normalize()),
            "max_price": None if self.max_price is None else str(self.max_price.normalize()),
            "min_rating": None if self.min_rating is None else str(self.min_rating.normalize()),
            "in_stock": self.in_stock,
        }


def apply_filters(
    ranked: Sequence[ScoredDocument], index: InvertedIndex, filters: SearchFilters
) -> list[ScoredDocument]:
    """Keep only matching products, preserving the ranked order."""
    if filters.is_empty:
        return list(ranked)
    return [doc for doc in ranked if filters.matches(index.metadata(doc.id))]


def sort_results(
    docs: Sequence[ScoredDocument],
    index: InvertedIndex,
    sort: SortOption,
    first: int | None = None,
) -> list[ScoredDocument]:
    """Re-order filtered results. Ties always fall back to ascending product id.

    ``relevance`` keeps the existing BM25 order unchanged. Products without the sort
    value (only possible in hand-built indexes) go last. With ``first``, only the first
    ``first`` results are returned - exactly the start of the full sort, found with a heap
    instead of sorting everything (a page needs only offset + limit results).
    """
    if sort is SortOption.RELEVANCE:
        return list(docs) if first is None else list(docs[:first])

    # Build plain (value, id, doc) tuples once and let Python's built-in tuple comparison
    # do the sorting. Values are arranged so that ascending order is the wanted order:
    # negated for "highest first", and +infinity (= last) for a missing value. Product ids
    # are unique, so the doc itself is never compared.
    missing = float("inf")
    keyed = []
    for doc in docs:
        m = index.metadata(doc.id)
        if sort is SortOption.PRICE_ASC:
            value = missing if m is None or m.price is None else m.price
        elif sort is SortOption.PRICE_DESC:
            value = missing if m is None or m.price is None else -m.price
        elif sort is SortOption.RATING:
            value = missing if m is None or m.rating is None else -m.rating
        else:  # NEWEST
            value = missing if m is None or m.created_at is None else -m.created_at.timestamp()
        keyed.append((value, doc.id, doc))
    if first is not None and first < len(keyed):
        keyed = heapq.nsmallest(first, keyed)  # same as sorted(keyed)[:first]
    else:
        keyed.sort()
    return [doc for _, _, doc in keyed]


@dataclass(frozen=True)
class FacetValue:
    value: str
    count: int


@dataclass(frozen=True)
class Facets:
    categories: list[FacetValue]
    brands: list[FacetValue]


def compute_facets(
    ranked: Sequence[ScoredDocument], index: InvertedIndex, filters: SearchFilters
) -> Facets:
    """Category and brand counts over ALL matching products (not just one page).

    Category counts apply every active filter EXCEPT the category filter, and brand counts
    every filter except the brand filter, so choosing a category still shows the other
    categories (with how many results each would give). Sorted by count, then name.
    """
    categories, brands = filters.categories, filters.brands
    metadata = index.metadata
    metas = [m for m in map(metadata, (doc.id for doc in ranked)) if m is not None]
    # Price/rating/stock apply to both facets, so they are checked once per product.
    if (
        filters.min_price is not None
        or filters.max_price is not None
        or filters.min_rating is not None
        or filters.in_stock
    ):
        metas = [m for m in metas if filters.matches_values(m)]

    # Counter counts in C. The category facet ignores only the category filter (so it
    # applies the brand filter) and the brand facet ignores only the brand filter.
    category_counts = Counter(m.category_key for m in metas if not brands or m.brand_key in brands)
    brand_counts = Counter(
        m.brand_key for m in metas if not categories or m.category_key in categories
    )
    category_names = {m.category_key: m.category for m in metas}
    brand_names = {m.brand_key: m.brand for m in metas}

    def ordered(counts: Counter, display: dict[str, str]) -> list[FacetValue]:
        values = [FacetValue(display[key], count) for key, count in counts.items()]
        return sorted(values, key=lambda v: (-v.count, v.value.casefold(), v.value))

    return Facets(
        categories=ordered(category_counts, category_names),
        brands=ordered(brand_counts, brand_names),
    )
