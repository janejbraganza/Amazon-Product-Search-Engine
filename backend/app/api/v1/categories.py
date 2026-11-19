"""Category endpoint: ``GET /api/v1/categories``."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.product import CategoryCount, CategoryListResponse
from app.services import product_service

router = APIRouter(prefix="/categories", tags=["categories"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=CategoryListResponse)
def list_categories(db: DbSession) -> CategoryListResponse:
    """All categories with their product counts, read from the database.

    Ordered by product count (highest first), then by name. An empty catalogue returns an
    empty list.
    """
    rows = product_service.list_categories(db)
    return CategoryListResponse(
        categories=[CategoryCount(name=name, product_count=count) for name, count in rows],
        total_products=sum(count for _, count in rows),
    )
