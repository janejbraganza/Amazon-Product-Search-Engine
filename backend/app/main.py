"""FastAPI entry point.

Routes: ``/health`` (liveness check) and the product API under ``/api/v1``.

With ``SEARCH_INDEX_WARMUP=true`` (set in Docker) the search index is built while the
server starts, so the first search is as fast as the rest. Otherwise it is built on the
first search, as before. A failed warm-up is logged and the lazy build is used instead.
"""

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import api_router
from app.core.config import get_settings

logger = logging.getLogger("uvicorn.error")


def warm_up_search_index() -> None:
    # Imported here so that importing the app never opens a database connection.
    from app.database.session import SessionLocal
    from app.search.index_manager import get_index_manager

    started = time.perf_counter()
    try:
        with SessionLocal() as session:
            index = get_index_manager().get_index(session)
    except Exception:  # the server still starts; the first search builds the index
        logger.exception("Search index warm-up failed; it will be built on the first search")
        return
    stats = index.stats()
    logger.info(
        "Search index ready: %s products, %s terms (%.2fs)",
        f"{stats.documents:,}",
        f"{stats.terms:,}",
        time.perf_counter() - started,
    )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if get_settings().search_index_warmup:
        warm_up_search_index()
    yield


app = FastAPI(title="Scalable Product Search Engine", lifespan=lifespan)
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
