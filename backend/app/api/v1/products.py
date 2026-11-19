"""Product endpoints: ``GET /api/v1/products`` and ``GET /api/v1/products/{product_id}``."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.product import ProductListResponse, ProductRead
from app.services import product_service

router = APIRouter(prefix="/products", tags=["products"])

DbSession = Annotated[Session, Depends(get_db)]
MAX_PAGE_SIZE = 100
BIGINT_MAX = 2**63 - 1  # largest value the BIGINT id column can hold


@router.get("", response_model=ProductListResponse)
def list_products(
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE, description="Page size")] = 20,
    offset: Annotated[int, Query(ge=0, description="Number of products to skip")] = 0,
) -> ProductListResponse:
    """List products ordered by id, with limit/offset pagination."""
    items, total = product_service.list_products(db, limit=limit, offset=offset)
    return ProductListResponse(
        items=[ProductRead.model_validate(p) for p in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{product_id}",
    response_model=ProductRead,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Product not found"}},
)
def get_product(
    db: DbSession,
    product_id: Annotated[int, Path(ge=1, le=BIGINT_MAX, description="Product ID")],
) -> ProductRead:
    """Return a single product, or 404 if it does not exist."""
    product = product_service.get_product(db, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Product {product_id} not found"
        )
    return ProductRead.model_validate(product)
