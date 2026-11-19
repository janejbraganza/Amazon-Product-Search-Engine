"""Pydantic schemas for the search API."""

from pydantic import BaseModel, Field

from app.schemas.product import ProductRead
from app.search.filters import SortOption
from app.services.search_service import SearchMode


class SearchResultItem(ProductRead):
    score: float = Field(description="BM25 relevance score (higher = more relevant)")


class FacetValue(BaseModel):
    value: str = Field(description="Category or brand name")
    count: int = Field(description="Matching products with this value")


class SearchFacets(BaseModel):
    categories: list[FacetValue] = Field(
        default_factory=list,
        description="Counts with every active filter applied except the category filter",
    )
    brands: list[FacetValue] = Field(
        default_factory=list,
        description="Counts with every active filter applied except the brand filter",
    )


class SearchResponse(BaseModel):
    query: str = Field(description="The query exactly as received")
    terms: list[str] = Field(description="Searchable terms after text processing")
    unmatched_terms: list[str] = Field(description="Terms that appear in no product")
    mode: SearchMode
    total: int = Field(description="Number of matching products (after filters)")
    limit: int
    offset: int
    items: list[SearchResultItem] = Field(description="In the requested sort order")
    prefix: str | None = Field(
        default=None, description="Partial last word that was expanded (prefix=true only)"
    )
    expanded_terms: list[str] = Field(
        default_factory=list, description="Indexed words the prefix was expanded to"
    )
    sort: SortOption = Field(default=SortOption.RELEVANCE, description="Order of the items")
    facets: SearchFacets = Field(
        default_factory=SearchFacets, description="Category and brand counts over all matches"
    )


class Suggestion(BaseModel):
    term: str = Field(description="Indexed word that starts with the prefix")
    product_count: int = Field(description="Number of products containing the word")
    display: str = Field(
        description="How the word is most often written in the products, for showing to "
        "users (e.g. 'earbuds' for term 'earbud'); searching it finds the same products"
    )


class SuggestionResponse(BaseModel):
    query: str
    prefix: str = Field(description="The partial word that was completed")
    suggestions: list[Suggestion] = Field(description="Most common first, then A-Z")


class IndexStatsResponse(BaseModel):
    build_id: str = Field(description="Unique ID of this index build (part of cache keys)")
    documents: int = Field(description="Products in the index")
    terms: int = Field(description="Distinct terms")
    postings: int = Field(description="Total (term, product) pairs")
    average_document_length: float = Field(description="Average field-weighted length")
    trie_nodes: int = Field(description="Nodes in the vocabulary Trie")
    build_seconds: float
