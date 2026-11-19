"""Dataset generator tests (no database needed)."""

import pytest

from app.schemas.product import ProductCreate
from app.services.product_loader import read_products_csv
from scripts.catalog_data import CATALOG
from scripts.generate_products import FIELDNAMES, generate_products, write_csv


@pytest.fixture(scope="module")
def products() -> list[dict]:
    return generate_products(count=2_000, seed=42)


def test_same_seed_gives_identical_output(products):
    assert generate_products(count=2_000, seed=42) == products


def test_different_seed_gives_different_output(products):
    assert generate_products(count=2_000, seed=7) != products


def test_ids_are_unique_and_sequential(products):
    assert [p["id"] for p in products] == list(range(1, 2_001))


def test_product_names_are_unique(products):
    assert len({p["product_name"] for p in products}) == len(products)


def test_every_product_is_valid(products):
    for p in products:
        assert set(p) == set(FIELDNAMES)
        ProductCreate.model_validate(p)  # raises if any field is out of range


def test_covers_all_categories_and_many_brands(products):
    assert {p["category"] for p in products} == set(CATALOG)
    assert len({p["brand"] for p in products}) >= 50


def test_values_are_realistic(products):
    out_of_stock = sum(p["stock_quantity"] == 0 for p in products)
    assert 0 < out_of_stock < len(products) * 0.1
    assert all(p["review_count"] >= 1 for p in products)
    assert len({p["rating"] for p in products}) > 10


def test_descriptions_are_meaningful_text(products):
    for p in products:
        words = p["description"].split()
        assert len(words) >= 20
        assert "Ideal for" in p["description"]
        assert p["description"].endswith(".")
        # Description must mention the brand, so the text is tied to the product.
        assert p["brand"] in p["description"]


def test_csv_round_trip(tmp_path, products):
    path = tmp_path / "products.csv"
    write_csv(products, path)
    loaded = read_products_csv(path)
    assert [p.model_dump() for p in loaded] == [
        ProductCreate.model_validate(p).model_dump() for p in products
    ]


def test_invalid_count_raises():
    with pytest.raises(ValueError):
        generate_products(count=0)
