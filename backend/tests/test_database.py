"""Database connection, table creation and constraint tests."""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.product import Product


def make_product(**overrides) -> Product:
    values = {
        "product_name": "Voltrix Pro Laptop, 14-inch",
        "description": "A lightweight laptop for students and remote work.",
        "category": "Electronics",
        "brand": "Voltrix",
        "price": Decimal("899.99"),
        "rating": Decimal("4.5"),
        "review_count": 120,
        "stock_quantity": 15,
    }
    values.update(overrides)
    return Product(**values)


def test_database_connection_select_1(test_engine: Engine):
    with test_engine.connect() as conn:
        assert conn.scalar(text("SELECT 1")) == 1


def test_products_table_has_expected_columns(test_engine: Engine):
    inspector = inspect(test_engine)
    assert "products" in inspector.get_table_names()

    columns = {c["name"]: c for c in inspector.get_columns("products")}
    assert set(columns) == {
        "id",
        "product_name",
        "description",
        "category",
        "brand",
        "price",
        "rating",
        "review_count",
        "stock_quantity",
        "created_at",
    }
    assert all(not c["nullable"] for c in columns.values())
    assert (columns["price"]["type"].precision, columns["price"]["type"].scale) == (10, 2)
    assert (columns["rating"]["type"].precision, columns["rating"]["type"].scale) == (2, 1)
    assert columns["created_at"]["type"].timezone is True
    assert inspector.get_pk_constraint("products")["constrained_columns"] == ["id"]


def test_products_table_has_indexes_and_checks(test_engine: Engine):
    inspector = inspect(test_engine)
    indexed = {tuple(ix["column_names"]) for ix in inspector.get_indexes("products")}
    for column in ("category", "brand", "price", "rating", "created_at"):
        assert (column,) in indexed

    checks = {c["name"] for c in inspector.get_check_constraints("products")}
    assert {
        "ck_products_name_not_blank",
        "ck_products_description_not_blank",
        "ck_products_price_positive",
        "ck_products_rating_range",
        "ck_products_review_count_non_negative",
        "ck_products_stock_non_negative",
    } <= checks


def test_insert_product_assigns_id_and_created_at(db_session: Session):
    product = make_product()
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)

    assert product.id == 1
    assert isinstance(product.created_at, datetime)
    assert product.created_at.tzinfo is not None
    assert db_session.get(Product, 1).product_name == "Voltrix Pro Laptop, 14-inch"


@pytest.mark.parametrize(
    "overrides",
    [
        {"price": Decimal("0")},
        {"price": Decimal("-5.00")},
        {"rating": Decimal("0.5")},
        {"rating": Decimal("5.5")},
        {"review_count": -1},
        {"stock_quantity": -1},
        {"product_name": "   "},
        {"description": ""},
    ],
    ids=lambda o: next(iter(o)),
)
def test_constraints_reject_invalid_values(db_session: Session, overrides: dict):
    db_session.add(make_product(**overrides))
    with pytest.raises(IntegrityError):
        db_session.commit()
