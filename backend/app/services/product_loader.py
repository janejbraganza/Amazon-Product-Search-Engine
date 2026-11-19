"""Read products from CSV and bulk-insert them into PostgreSQL.

Duplicates are avoided with ``INSERT ... ON CONFLICT (id) DO NOTHING``: running the
loader again inserts nothing and reports every row as skipped.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.product import Product
from app.schemas.product import ProductCreate

DEFAULT_BATCH_SIZE = 1_000  # 1,000 rows x 10 columns stays well below PostgreSQL's 65,535 params


@dataclass(frozen=True)
class LoadResult:
    inserted: int
    skipped: int


def read_products_csv(path: Path) -> list[ProductCreate]:
    """Parse and validate every row. Raises ValueError naming the first bad row."""
    products: list[ProductCreate] = []
    seen_ids: set[int] = set()
    with path.open(newline="", encoding="utf-8") as handle:
        # Row 1 is the header, so data starts on line 2.
        for line_number, row in enumerate(csv.DictReader(handle), start=2):
            try:
                product = ProductCreate.model_validate(row)
            except ValidationError as exc:
                raise ValueError(f"{path.name} line {line_number}: invalid product: {exc}") from exc
            if product.id in seen_ids:
                raise ValueError(f"{path.name} line {line_number}: duplicate id {product.id}")
            seen_ids.add(product.id)
            products.append(product)
    return products


def load_products(
    session: Session, products: list[ProductCreate], batch_size: int = DEFAULT_BATCH_SIZE
) -> LoadResult:
    """Insert products in batches inside one transaction; existing IDs are skipped."""
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    inserted = 0
    for start in range(0, len(products), batch_size):
        batch = [p.model_dump() for p in products[start : start + batch_size]]
        stmt = (
            insert(Product)
            .values(batch)
            .on_conflict_do_nothing(index_elements=[Product.id])
            .returning(Product.id)
        )
        inserted += len(session.execute(stmt).all())

    sync_id_sequence(session)
    session.commit()
    return LoadResult(inserted=inserted, skipped=len(products) - inserted)


def sync_id_sequence(session: Session) -> None:
    """Move the identity sequence past the highest ID, so new rows don't collide."""
    session.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('products', 'id'), "
            "COALESCE((SELECT MAX(id) FROM products), 1), "
            "(SELECT MAX(id) FROM products) IS NOT NULL)"
        )
    )
