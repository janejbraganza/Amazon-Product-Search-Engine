"""Version 1 of the HTTP API. All routers here are mounted under ``/api/v1``."""

from fastapi import APIRouter

from app.api.v1.categories import router as categories_router
from app.api.v1.products import router as products_router
from app.api.v1.search import router as search_router

api_router = APIRouter()
api_router.include_router(products_router)
api_router.include_router(search_router)
api_router.include_router(categories_router)
