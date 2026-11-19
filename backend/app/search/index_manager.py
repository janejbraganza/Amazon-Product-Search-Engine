"""Owns the live search index for the running application.

- The index is built from PostgreSQL on the first search (lazy), then reused.
- ``rebuild`` builds a fresh index and swaps it in with a single assignment, so
  concurrent searches keep using the old index until the new one is complete.
- A lock prevents two simultaneous first requests from both building the index.
"""

import threading
from collections.abc import Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.search.inverted_index import InvertedIndex, SearchDocument

FETCH_CHUNK_SIZE = 1_000


def load_documents(session: Session) -> Iterator[SearchDocument]:
    """Stream the searchable text plus the filter/sort columns, in chunks, ordered by id.

    Everything comes from one query, so a build's text and metadata come from the same
    read of the table.
    """
    stmt = (
        select(
            Product.id,
            Product.product_name,
            Product.description,
            Product.brand,
            Product.category,
            Product.price,
            Product.rating,
            Product.stock_quantity,
            Product.created_at,
        )
        .order_by(Product.id)
        .execution_options(yield_per=FETCH_CHUNK_SIZE)
    )
    for row in session.execute(stmt):
        yield SearchDocument(*row)


def build_index_from_db(session: Session) -> InvertedIndex:
    return InvertedIndex.build(load_documents(session))


class SearchIndexManager:
    def __init__(self) -> None:
        self._index: InvertedIndex | None = None
        self._build_lock = threading.Lock()

    @property
    def is_built(self) -> bool:
        return self._index is not None

    def get_index(self, session: Session) -> InvertedIndex:
        """Return the live index, building it on first use."""
        index = self._index
        if index is not None:
            return index
        with self._build_lock:
            if self._index is None:  # another request may have built it while we waited
                self._index = build_index_from_db(session)
            return self._index

    def rebuild(self, session: Session) -> InvertedIndex:
        """Rebuild from the current database contents and swap it in."""
        with self._build_lock:
            new_index = build_index_from_db(session)
            self._index = new_index  # atomic reference swap
            return new_index


# The single index shared by all requests in this process.
index_manager = SearchIndexManager()


def get_index_manager() -> SearchIndexManager:
    """FastAPI dependency (overridable in tests)."""
    return index_manager
