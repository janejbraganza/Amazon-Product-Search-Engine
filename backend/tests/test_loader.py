"""Product loading tests: insertion, idempotency and validation of the CSV."""

import csv
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.schemas.product import ProductCreate
from app.services.product_loader import load_products, read_products_csv
from scripts.generate_products import generate_products, write_csv


def count_products(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Product))


def test_load_inserts_all_products(db_session: Session, sample_products):
    result = load_products(db_session, sample_products)

    assert (result.inserted, result.skipped) == (50, 0)
    assert count_products(db_session) == 50
    stored = db_session.get(Product, 1)
    assert stored.product_name == sample_products[0].product_name
    assert stored.price == sample_products[0].price


def test_reloading_does_not_create_duplicates(db_session: Session, sample_products):
    load_products(db_session, sample_products)
    result = load_products(db_session, sample_products)

    assert (result.inserted, result.skipped) == (0, 50)
    assert count_products(db_session) == 50


def test_partial_overlap_inserts_only_new_rows(db_session: Session, sample_products):
    load_products(db_session, sample_products[:30])
    result = load_products(db_session, sample_products)

    assert (result.inserted, result.skipped) == (20, 30)
    assert count_products(db_session) == 50


def test_small_batches_load_everything(db_session: Session, sample_products):
    result = load_products(db_session, sample_products, batch_size=7)
    assert result.inserted == 50


def test_id_sequence_continues_after_load(db_session: Session, sample_products):
    load_products(db_session, sample_products)
    product = Product(
        product_name="New Product",
        description="Added after the bulk load.",
        category="Electronics",
        brand="Voltrix",
        price=Decimal("10.00"),
        rating=Decimal("4.0"),
    )
    db_session.add(product)
    db_session.commit()
    assert product.id == 51


def test_invalid_batch_size_raises(db_session: Session, sample_products):
    with pytest.raises(ValueError):
        load_products(db_session, sample_products, batch_size=0)


def _write_rows(path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_csv_with_duplicate_ids_is_rejected(tmp_path):
    rows = generate_products(count=3, seed=1)
    rows[2]["id"] = 1
    path = tmp_path / "dupes.csv"
    write_csv(rows, path)
    with pytest.raises(ValueError, match="duplicate id 1"):
        read_products_csv(path)


def test_csv_with_invalid_row_reports_line_number(tmp_path):
    rows = [ProductCreate.model_validate(p).model_dump() for p in generate_products(3, seed=1)]
    rows[1]["rating"] = "7.5"
    path = tmp_path / "bad.csv"
    _write_rows(path, rows)
    with pytest.raises(ValueError, match="line 3"):
        read_products_csv(path)
