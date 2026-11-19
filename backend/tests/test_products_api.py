"""API tests for GET /api/v1/products and GET /api/v1/products/{product_id}."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.product_loader import load_products

URL = "/api/v1/products"


@pytest.fixture
def loaded(db_session: Session, sample_products):
    load_products(db_session, sample_products)
    return sample_products


def test_list_products_default_page(client: TestClient, loaded):
    response = client.get(URL)
    assert response.status_code == 200
    body = response.json()

    assert (body["total"], body["limit"], body["offset"]) == (50, 20, 0)
    assert [p["id"] for p in body["items"]] == list(range(1, 21))
    first = body["items"][0]
    assert first["product_name"] == loaded[0].product_name
    assert isinstance(first["price"], float)
    assert isinstance(first["rating"], float)
    assert set(first) == {
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


def test_pagination_pages_do_not_overlap(client: TestClient, loaded):
    seen: list[int] = []
    for offset in (0, 20, 40):
        body = client.get(URL, params={"limit": 20, "offset": offset}).json()
        seen.extend(p["id"] for p in body["items"])

    assert seen == list(range(1, 51))  # every product exactly once, in order


def test_last_page_is_partial(client: TestClient, loaded):
    body = client.get(URL, params={"limit": 20, "offset": 40}).json()
    assert len(body["items"]) == 10


def test_offset_past_end_returns_empty_page(client: TestClient, loaded):
    body = client.get(URL, params={"offset": 1_000}).json()
    assert body["items"] == []
    assert body["total"] == 50


def test_empty_catalogue(client: TestClient, db_session):
    body = client.get(URL).json()
    assert body == {"items": [], "total": 0, "limit": 20, "offset": 0}


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 101}, {"limit": "abc"}, {"offset": -1}],
    ids=["limit-0", "limit-101", "limit-text", "offset-negative"],
)
def test_invalid_pagination_params_return_422(client: TestClient, params):
    assert client.get(URL, params=params).status_code == 422


def test_get_product_by_id(client: TestClient, loaded):
    response = client.get(f"{URL}/7")
    assert response.status_code == 200
    body = response.json()
    expected = loaded[6]
    assert body["id"] == 7
    assert body["product_name"] == expected.product_name
    assert body["brand"] == expected.brand
    assert body["price"] == float(expected.price)


def test_missing_product_returns_404(client: TestClient, loaded):
    response = client.get(f"{URL}/99999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Product 99999 not found"}


@pytest.mark.parametrize("product_id", ["abc", "0", "-5", "1.5", str(2**63)])
def test_invalid_product_id_returns_422(client: TestClient, product_id):
    assert client.get(f"{URL}/{product_id}").status_code == 422
