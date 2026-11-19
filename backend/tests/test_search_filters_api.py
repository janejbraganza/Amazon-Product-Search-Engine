"""Filters, sorting, facets, display forms and /categories through the API (test database).

Expected results are computed independently from the loaded sample products. The query
"ideal" matches every product (every description contains "Ideal for"), so a filtered
search must return exactly the products that pass the filter.
"""

from collections import Counter
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.main import app
from app.models.product import Product
from app.search.index_manager import SearchIndexManager, get_index_manager
from app.services.product_loader import load_products

URL = "/api/v1/search"


@pytest.fixture
def manager() -> SearchIndexManager:
    fresh = SearchIndexManager()
    app.dependency_overrides[get_index_manager] = lambda: fresh
    yield fresh
    app.dependency_overrides.pop(get_index_manager, None)


@pytest.fixture
def loaded(db_session: Session, sample_products):
    load_products(db_session, sample_products)
    return sample_products


def get(client: TestClient, **params):
    return client.get(URL, params={"q": "ideal", "limit": 100, **params})


def ids(response) -> list[int]:
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


def relevance_order(client) -> list[int]:
    return ids(get(client))


# ---- Each filter ----------------------------------------------------------------------


def test_category_filter_is_case_insensitive(client, manager, loaded):
    expected = sorted(p.id for p in loaded if p.category == "Electronics")
    for value in ("Electronics", "electronics", "  ELECTRONICS "):
        response = get(client, category=value)
        assert sorted(ids(response)) == expected
        assert response.json()["total"] == len(expected)


def test_several_categories_are_or_ed(client, manager, loaded):
    wanted = {"Electronics", "Books"}
    response = get(client, category=["electronics", "BOOKS"])
    assert sorted(ids(response)) == sorted(p.id for p in loaded if p.category in wanted)


def test_brand_filter_is_case_insensitive(client, manager, loaded):
    brand = Counter(p.brand for p in loaded).most_common(1)[0][0]
    expected = sorted(p.id for p in loaded if p.brand == brand)
    assert sorted(ids(get(client, brand=brand.upper()))) == expected
    assert sorted(ids(get(client, brand=brand.lower()))) == expected


def test_price_range_is_inclusive(client, manager, loaded):
    low, high = Decimal("20"), Decimal("120")
    expected = sorted(p.id for p in loaded if low <= p.price <= high)
    assert sorted(ids(get(client, min_price="20", max_price="120.00"))) == expected


def test_min_rating(client, manager, loaded):
    expected = sorted(p.id for p in loaded if p.rating >= Decimal("4.5"))
    assert sorted(ids(get(client, min_rating="4.5"))) == expected


def test_in_stock(client, manager, loaded):
    expected = sorted(p.id for p in loaded if p.stock_quantity > 0)
    assert sorted(ids(get(client, in_stock="true"))) == expected
    assert len(expected) < len(loaded)  # the sample has out-of-stock products
    assert sorted(ids(get(client, in_stock="false"))) == sorted(p.id for p in loaded)


def test_combined_filters(client, manager, loaded):
    def keep(p):
        return (
            p.category in {"Home & Kitchen", "Electronics"}
            and p.price <= Decimal(300)
            and p.rating >= Decimal("3.5")
            and p.stock_quantity > 0
        )

    response = get(
        client,
        category=["home & kitchen", "Electronics"],
        max_price="300",
        min_rating="3.5",
        in_stock="true",
    )
    assert sorted(ids(response)) == sorted(p.id for p in loaded if keep(p))


def test_filters_keep_relevance_order(client, manager, loaded):
    filtered = ids(get(client, in_stock="true"))
    assert filtered == [i for i in relevance_order(client) if i in set(filtered)]


def test_filter_matching_nothing(client, manager, loaded):
    body = get(client, category="No Such Category").json()
    assert (body["total"], body["items"]) == (0, [])


def test_filters_work_with_any_mode_and_prefix_search(client, manager, loaded):
    electronics = {p.id for p in loaded if p.category == "Electronics"}
    any_mode = ids(get(client, q="ideal zzzz", mode="any", category="electronics"))
    prefix = ids(get(client, q="ide", prefix="true", category="electronics"))
    assert set(any_mode) == set(prefix) == electronics


# ---- Validation -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("params", "detail"),
    [
        (
            {"min_price": "50", "max_price": "10"},
            "min_price must be less than or equal to max_price",
        ),
        ({"category": "   "}, "category must not be blank"),
        ({"brand": ""}, "brand must not be blank"),
    ],
)
def test_invalid_filter_combinations_return_422_with_message(
    client, manager, loaded, params, detail
):
    response = get(client, **params)
    assert response.status_code == 422
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize(
    "params",
    [
        {"min_price": "-1"},
        {"max_price": "-0.01"},
        {"min_price": "abc"},
        {"min_price": "1.234"},  # more than 2 decimal places
        {"max_price": "100000000"},  # above the NUMERIC(10,2) column limit
        {"min_rating": "5.5"},
        {"min_rating": "-1"},
        {"min_rating": "4.25"},  # ratings have one decimal place
        {"sort": "cheapest"},
        {"in_stock": "maybe"},
        {"category": [f"c{i}" for i in range(21)]},  # more than 20 values
    ],
    ids=lambda p: next(iter(p.items()))[0] + "=" + str(next(iter(p.values())))[:12],
)
def test_invalid_parameters_return_422(client, manager, loaded, params):
    assert get(client, **params).status_code == 422


# ---- Sorting ------------------------------------------------------------------------------


def expected_order(products, key):
    return [p.id for p in sorted(products, key=key)]


@pytest.mark.parametrize(
    ("sort", "key"),
    [
        ("price_asc", lambda p: (p.price, p.id)),
        ("price_desc", lambda p: (-p.price, p.id)),
        ("rating", lambda p: (-p.rating, p.id)),
        ("newest", lambda p: (-p.created_at.timestamp(), p.id)),
    ],
)
def test_sort_modes(client, manager, loaded, sort, key):
    response = get(client, sort=sort)
    assert ids(response) == expected_order(loaded, key)
    assert response.json()["sort"] == sort


def test_relevance_is_the_default_and_unchanged(client, manager, loaded):
    default = get(client).json()
    explicit = get(client, sort="relevance").json()
    assert default["sort"] == "relevance"
    assert default["items"] == explicit["items"]
    scores = [(-round(i["score"], 6), i["id"]) for i in default["items"]]
    assert scores == sorted(scores)


def test_sort_ties_break_by_ascending_id(client, manager, loaded, db_session):
    # Give five products the same price and rating to force ties.
    tied = sorted(p.id for p in loaded)[10:15]
    db_session.execute(
        update(Product)
        .where(Product.id.in_(tied))
        .values(price=Decimal("1.00"), rating=Decimal("5.0"))
    )
    db_session.commit()
    client.post(f"{URL}/rebuild-index")
    # $1.00 is below every sample price, so exactly the five tied products come first.
    assert ids(get(client, sort="price_asc"))[:5] == tied
    # Some sample products are already rated 5.0: every 5.0 product ties, ascending id.
    top_rated = sorted({*tied, *(p.id for p in loaded if p.rating == Decimal("5.0"))})
    assert ids(get(client, sort="rating"))[: len(top_rated)] == top_rated


def test_sorting_combined_with_filters(client, manager, loaded):
    kept = [p for p in loaded if p.category == "Electronics"]
    assert ids(get(client, category="electronics", sort="price_desc")) == expected_order(
        kept, lambda p: (-p.price, p.id)
    )


# ---- Pagination after filtering and sorting ----------------------------------------------


def test_pagination_happens_after_filtering_and_sorting(client, manager, loaded):
    full = ids(get(client, in_stock="true", sort="price_asc"))
    pages = []
    for offset in range(0, len(full), 7):
        response = get(client, in_stock="true", sort="price_asc", limit=7, offset=offset)
        assert response.json()["total"] == len(full)
        pages.extend(ids(response))
    assert pages == full


# ---- Facets --------------------------------------------------------------------------------


def facets(response):
    body = response.json()["facets"]
    return (
        {f["value"]: f["count"] for f in body["categories"]},
        {f["value"]: f["count"] for f in body["brands"]},
    )


def test_facets_count_all_matches_not_just_the_page(client, manager, loaded):
    categories, brands = facets(get(client, limit=1))
    assert categories == dict(Counter(p.category for p in loaded))
    assert brands == dict(Counter(p.brand for p in loaded))


def test_facets_are_sorted_by_count_then_name(client, manager, loaded):
    values = get(client).json()["facets"]["categories"]
    keys = [(-v["count"], v["value"].casefold()) for v in values]
    assert keys == sorted(keys)


def test_category_facet_ignores_category_filter_but_brand_facet_respects_it(
    client, manager, loaded
):
    categories, brands = facets(get(client, category="Electronics"))
    assert categories == dict(Counter(p.category for p in loaded))
    assert brands == dict(Counter(p.brand for p in loaded if p.category == "Electronics"))


def test_brand_facet_ignores_brand_filter_but_category_facet_respects_it(client, manager, loaded):
    brand = Counter(p.brand for p in loaded).most_common(1)[0][0]
    categories, brands = facets(get(client, brand=brand))
    assert brands == dict(Counter(p.brand for p in loaded))
    assert categories == dict(Counter(p.category for p in loaded if p.brand == brand))


def test_facets_with_several_filters(client, manager, loaded):
    def others(p):  # price + stock filters apply to both facets
        return p.price <= Decimal(200) and p.stock_quantity > 0

    response = get(
        client, category="Electronics", brand="Voltrix", max_price="200", in_stock="true"
    )
    categories, brands = facets(response)
    assert categories == dict(
        Counter(p.category for p in loaded if others(p) and p.brand == "Voltrix")
    )
    assert brands == dict(
        Counter(p.brand for p in loaded if others(p) and p.category == "Electronics")
    )


def test_facets_for_a_query_without_matches(client, manager, loaded):
    body = get(client, q="zzzz").json()
    assert body["facets"] == {"categories": [], "brands": []}


# ---- Suggestion display forms ----------------------------------------------------------------


def test_suggestions_include_display_forms(client, manager, loaded, db_session):
    db_session.add(
        Product(
            product_name="Voltrix USB-C Earbuds",
            description="USB-C earbuds with Wi-Fi pairing.",
            category="Electronics",
            brand="Voltrix",
            price=Decimal("29.99"),
            rating=Decimal("4.2"),
        )
    )
    db_session.commit()
    client.post(f"{URL}/rebuild-index")
    usb = client.get(f"{URL}/suggestions", params={"q": "usb"}).json()["suggestions"]
    by_term = {s["term"]: s for s in usb}
    assert by_term["usbc"]["display"] == "usb-c"
    # Several sample products also mention USB-C; the count must match a real search.
    assert by_term["usbc"]["product_count"] == get(client, q="usb-c").json()["total"] >= 1
    electr = client.get(f"{URL}/suggestions", params={"q": "electr"}).json()["suggestions"]
    assert {s["term"]: s["display"] for s in electr}["electronic"] == "electronics"


def test_searching_a_suggestion_display_form_finds_the_same_products(client, manager, loaded):
    for suggestion in client.get(f"{URL}/suggestions", params={"q": "e", "limit": 50}).json()[
        "suggestions"
    ]:
        by_display = get(client, q=suggestion["display"]).json()["total"]
        assert by_display == suggestion["product_count"], suggestion


# ---- Categories endpoint ---------------------------------------------------------------------


def test_categories_endpoint_counts_from_the_database(client, manager, loaded):
    body = client.get("/api/v1/categories").json()
    expected = Counter(p.category for p in loaded)
    assert {c["name"]: c["product_count"] for c in body["categories"]} == dict(expected)
    assert body["total_products"] == len(loaded)
    keys = [(-c["product_count"], c["name"]) for c in body["categories"]]
    assert keys == sorted(keys)


def test_categories_endpoint_with_an_empty_catalogue(client, db_session):
    body = client.get("/api/v1/categories").json()
    assert body == {"categories": [], "total_products": 0}
