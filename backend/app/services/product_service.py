"""Product queries used by the API (kept separate from HTTP concerns)."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.product import Product


def list_products(db: Session, limit: int, offset: int) -> tuple[list[Product], int]:
    """Return one page of products ordered by id, plus the total product count.

    Ordering by the primary key keeps pages stable: no product appears twice or is skipped.
    """
    total = db.scalar(select(func.count()).select_from(Product)) or 0
    items = db.scalars(select(Product).order_by(Product.id).limit(limit).offset(offset)).all()
    return list(items), total


def get_product(db: Session, product_id: int) -> Product | None:
    return db.get(Product, product_id)


def list_categories(db: Session) -> list[tuple[str, int]]:
    """(category, product count) from the database: most products first, then by name."""
    count = func.count(Product.id)
    stmt = (
        select(Product.category, count)
        .group_by(Product.category)
        .order_by(count.desc(), Product.category.asc())
    )
    return [(category, total) for category, total in db.execute(stmt).all()]
