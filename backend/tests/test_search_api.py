"""Search API and service tests against the test database."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.main import app
from app.models.product import Product
from app.search.index_manager import SearchIndexManager, get_index_manager
from app.search.text_processing import query_terms, unique_terms
from app.services.product_loader import load_products
from app.services.search_service import EmptyQueryError, SearchMode, search_products

URL = "/api/v1/search"


@pytest.fixture
def manager() -> SearchIndexManager:
    """A fresh, empty index manager for each test (never the app's shared one)."""
    fresh = SearchIndexManager()
    app.dependency_overrides[get_index_manager] = lambda: fresh
    yield fresh
    app.dependency_overrides.pop(get_index_manager, None)


@pytest.fixture
def loaded(db_session: Session, sample_products):
    load_products(db_session, sample_products)
    return sample_products


def brute_force(products, query: str, mode: str = "all") -> list[int]:
    """Reference answer: scan every product's text, no index involved."""
    wanted = set(query_terms(query))
    matches = []
    for p in products:
        terms = unique_terms([p.product_name, p.description, p.brand, p.category])
        if (wanted <= terms) if mode == "all" else (wanted & terms):
            matches.append(p.id)
    return sorted(matches)


def search_ids(client: TestClient, q: str, **params) -> list[int]:
    body = client.get(URL, params={"q": q, "limit": 100, **params}).json()
    return [item["id"] for item in body["items"]]


# ---- Correct retrieval ----------------------------------------------------------


def test_single_word_search_returns_matching_products(client, manager, loaded):
    category = loaded[0].category  # e.g. "Books"
    expected = sorted(p.id for p in loaded if p.category == category)

    response = client.get(URL, params={"q": category, "limit": 100})
    assert response.status_code == 200
    body = response.json()
    # Results are ranked by relevance now, so compare the set of products returned.
    assert sorted(item["id"] for item in body["items"]) == expected
    assert all(item["category"] == category for item in body["items"])
    assert body["total"] == len(expected)


def test_brand_search_finds_all_products_of_that_brand(client, manager, loaded):
    brand = loaded[0].brand
    ids = search_ids(client, brand)
    assert set(ids) >= {p.id for p in loaded if p.brand == brand}


@pytest.mark.parametrize(
    "query", ["wireless", "stainless steel", "black size", "ideal", "water resistant"]
)
@pytest.mark.parametrize("mode", ["all", "any"])
def test_results_match_brute_force_scan(client, manager, loaded, query, mode):
    # Same products as a full scan (ranking changes the order, not the membership).
    assert sorted(search_ids(client, query, mode=mode)) == brute_force(loaded, query, mode)


def test_multi_word_search_narrows_results(client, manager, loaded):
    product = loaded[0]
    words = product.product_name.split()[:2]
    one = search_ids(client, words[0])
    both = search_ids(client, " ".join(words))
    assert product.id in both
    assert set(both) <= set(one)


def test_search_is_case_insensitive(client, manager, loaded):
    brand = loaded[0].brand
    assert search_ids(client, brand.upper()) == search_ids(client, brand.lower())


def test_response_contains_full_product_details(client, manager, loaded):
    product = loaded[0]
    body = client.get(URL, params={"q": product.product_name}).json()
    item = next(i for i in body["items"] if i["id"] == product.id)
    assert item["product_name"] == product.product_name
    assert item["description"] == product.description
    assert item["brand"] == product.brand
    assert item["price"] == float(product.price)
    assert body["query"] == product.product_name
    assert body["mode"] == "all"


def test_pagination(client, manager, loaded):
    full = search_ids(client, "ideal")  # every product description contains "Ideal for"
    assert len(full) == 50
    page = client.get(URL, params={"q": "ideal", "limit": 20, "offset": 40}).json()
    assert page["total"] == 50
    assert [i["id"] for i in page["items"]] == full[40:]


# ---- Missing terms and invalid queries ------------------------------------------


def test_missing_term_returns_empty_result(client, manager, loaded):
    body = client.get(URL, params={"q": "zzzz"}).json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["unmatched_terms"] == ["zzzz"]


def test_partially_missing_terms(client, manager, loaded):
    brand = loaded[0].brand.split()[0]
    assert search_ids(client, f"{brand} zzzz") == []
    any_body = client.get(URL, params={"q": f"{brand} zzzz", "mode": "any"}).json()
    assert any_body["total"] > 0
    assert any_body["unmatched_terms"] == ["zzzz"]


@pytest.mark.parametrize(
    ("params", "detail"),
    [
        ({"q": "   "}, "Query must not be blank"),
        ({"q": "the and of"}, "Query contains no searchable words"),
        ({"q": "!!! ???"}, "Query contains no searchable words"),
    ],
)
def test_queries_without_searchable_words_return_422(client, manager, params, detail):
    response = client.get(URL, params=params)
    assert response.status_code == 422
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize(
    "params",
    [{}, {"q": ""}, {"q": "x" * 201}, {"q": "laptop", "mode": "maybe"}, {"q": "a", "limit": 0}],
    ids=["missing-q", "empty-q", "too-long", "bad-mode", "bad-limit"],
)
def test_invalid_parameters_return_422(client, manager, params):
    assert client.get(URL, params=params).status_code == 422


def test_service_rejects_empty_query(db_session, loaded):
    index = SearchIndexManager().get_index(db_session)
    with pytest.raises(EmptyQueryError):
        search_products(db_session, index, "the", SearchMode.ALL)


# ---- Index building and rebuilding ----------------------------------------------


def test_index_is_built_lazily_on_first_search(client, manager, loaded):
    assert not manager.is_built
    client.get(URL, params={"q": "ideal"})
    assert manager.is_built


def test_rebuild_picks_up_new_products(client, manager, loaded, db_session):
    assert search_ids(client, "zephyrboard") == []  # index built now, without the product

    db_session.add(
        Product(
            product_name="Voltrix Zephyrboard Mechanical Keyboard",
            description="A mechanical keyboard with hot-swappable switches.",
            category="Electronics",
            brand="Voltrix",
            price=Decimal("89.99"),
            rating=Decimal("4.6"),
        )
    )
    db_session.commit()
    assert search_ids(client, "zephyrboard") == []  # stale until rebuilt

    response = client.post(f"{URL}/rebuild-index")
    assert response.status_code == 200
    assert response.json()["documents"] == 51
    assert search_ids(client, "zephyrboard") == [51]


def test_rebuild_reports_stats(client, manager, loaded):
    body = client.post(f"{URL}/rebuild-index").json()
    assert body["documents"] == 50
    assert body["terms"] > 0
    assert body["postings"] >= body["terms"]
    assert body["build_seconds"] >= 0


def test_rebuild_is_disabled_in_production(client, manager):
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="production", database_url="postgresql+psycopg://unused@localhost/unused"
    )
    try:
        assert client.post(f"{URL}/rebuild-index").status_code == 404
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_existing_products_api_still_works(client, manager, loaded):
    assert client.get("/api/v1/products").json()["total"] == 50


# ---- BM25 ranking through the API -----------------------------------------------


def search_body(client: TestClient, q: str, **params) -> dict:
    return client.get(URL, params={"q": q, "limit": 100, **params}).json()


@pytest.mark.parametrize("mode", ["all", "any"])
@pytest.mark.parametrize("query", ["ideal", "wireless", "black size", "stainless steel"])
def test_results_are_sorted_by_score_then_id(client, manager, loaded, query, mode):
    items = search_body(client, query, mode=mode)["items"]
    keys = [(-item["score"], item["id"]) for item in items]
    assert keys == sorted(keys)  # score descending; equal scores by ascending id
    assert all(item["score"] > 0 for item in items)


def test_api_scores_match_index_ranking(client, manager, loaded, db_session):
    body = search_body(client, "wireless black", mode="any")
    ranked = manager.get_index(db_session).rank(["wireless", "black"], require_all=False)
    assert [i["id"] for i in body["items"]] == [d.id for d in ranked]
    assert [i["score"] for i in body["items"]] == [round(d.score, 6) for d in ranked]


def test_exact_product_name_ranks_that_product_first(client, manager, loaded):
    for product in loaded[:5]:
        items = search_body(client, product.product_name)["items"]
        assert items[0]["id"] == product.id


def test_pagination_happens_after_ranking(client, manager, loaded):
    full = search_ids(client, "ideal")  # all 50 products, ranked
    assert full != sorted(full)  # ranking really changed the order
    paged: list[int] = []
    for offset in range(0, 50, 7):
        body = client.get(URL, params={"q": "ideal", "limit": 7, "offset": offset}).json()
        assert body["total"] == 50
        paged.extend(item["id"] for item in body["items"])
    assert paged == full  # pages stitched together == the full ranked list


def test_unknown_terms_still_reported_with_ranking(client, manager, loaded):
    body = search_body(client, "wireless zzzz", mode="any")
    assert body["unmatched_terms"] == ["zzzz"]
    assert [i["id"] for i in body["items"]] == search_ids(client, "wireless")
    assert [i["score"] for i in body["items"]] == [
        i["score"] for i in search_body(client, "wireless")["items"]
    ]


def test_rebuild_updates_scores(client, manager, loaded, db_session):
    before = {i["id"]: i["score"] for i in search_body(client, "ideal")["items"]}

    db_session.add(
        Product(
            product_name="Voltrix Ideal Kettle",
            description="An ideal kettle, ideal for tea.",
            category="Home & Kitchen",
            brand="Voltrix",
            price=Decimal("29.99"),
            rating=Decimal("4.1"),
        )
    )
    db_session.commit()
    stale = {i["id"]: i["score"] for i in search_body(client, "ideal")["items"]}
    assert stale == before  # unchanged until the index is rebuilt

    stats = client.post(f"{URL}/rebuild-index").json()
    assert stats["documents"] == 51
    after = search_body(client, "ideal")["items"]
    assert after[0]["id"] == 51  # "ideal" in name and twice in description
    assert {i["id"]: i["score"] for i in after if i["id"] != 51} != before


# ---- Prefix search (Trie expansion + inverted index + BM25) ---------------------


def prefix_body(client: TestClient, q: str, **params) -> dict:
    return client.get(URL, params={"q": q, "prefix": "true", "limit": 100, **params}).json()


def test_prefix_search_expands_partial_word(client, manager, loaded):
    body = prefix_body(client, "ide")
    assert body["prefix"] == "ide"
    assert "ideal" in body["expanded_terms"]
    assert body["total"] == 50  # every product contains "ideal"


def test_prefix_search_equals_manual_expansion(client, manager, loaded, db_session):
    """prefix=true returns the same products as searching the completions directly."""
    index = manager.get_index(db_session)
    for partial in ["st", "bl", "wa"]:
        expansions = index.complete_prefix(partial)
        expected = brute_force(loaded, " ".join(expansions), mode="any")
        assert sorted(i["id"] for i in prefix_body(client, partial)["items"]) == expected


def test_prefix_search_is_ranked_by_bm25(client, manager, loaded, db_session):
    body = prefix_body(client, "wireless bl", mode="any")
    index = manager.get_index(db_session)
    ranked = index.rank_groups([["wireless"], index.complete_prefix("bl")], require_all=False)
    assert [i["id"] for i in body["items"]] == [d.id for d in ranked]
    assert [i["score"] for i in body["items"]] == [round(d.score, 6) for d in ranked]
    keys = [(-i["score"], i["id"]) for i in body["items"]]
    assert keys == sorted(keys)


def test_complete_word_with_prefix_flag_ranks_like_normal_search(client, manager, loaded):
    # "ideal" is a whole word; as a prefix it expands to ["ideal"] only.
    normal = search_body(client, "ideal")["items"]
    assert prefix_body(client, "ideal")["items"] == normal


def test_prefix_search_all_mode_requires_complete_words_and_prefix(client, manager, loaded):
    brand = loaded[0].brand.split()[0].lower()
    all_ids = {i["id"] for i in prefix_body(client, f"{brand} ide")["items"]}
    assert all_ids == set(search_ids(client, brand))  # every product has "ideal"
    assert prefix_body(client, f"{brand} xyzq")["total"] == 0


def test_prefix_search_pagination_after_ranking(client, manager, loaded):
    full = [i["id"] for i in prefix_body(client, "ide")["items"]]
    paged: list[int] = []
    for offset in range(0, 50, 9):
        body = prefix_body(client, "ide", limit=9, offset=offset)
        paged.extend(i["id"] for i in body["items"])
    assert paged == full


def test_prefix_with_no_completions(client, manager, loaded):
    body = prefix_body(client, "xyzq")
    assert body["total"] == 0
    assert body["expanded_terms"] == []
    assert body["unmatched_terms"] == ["xyzq*"]
    any_body = prefix_body(client, "ideal xyzq", mode="any")
    assert any_body["total"] == 50
    assert any_body["unmatched_terms"] == ["xyzq*"]


def test_trailing_space_disables_prefix_expansion(client, manager, loaded):
    body = prefix_body(client, "ide ")
    assert body["prefix"] is None
    assert body["terms"] == ["ide"]
    assert body["total"] == 0


def test_prefix_flag_defaults_to_false(client, manager, loaded):
    body = search_body(client, "ide")
    assert body["total"] == 0  # whole-word search: "ide" is not a word
    assert body["prefix"] is None
    assert body["expanded_terms"] == []


def test_prefix_search_rejects_queries_without_characters(client, manager):
    response = client.get(URL, params={"q": "!!!", "prefix": "true"})
    assert response.status_code == 422


def test_rebuild_updates_prefix_search(client, manager, loaded, db_session):
    assert prefix_body(client, "zeph")["total"] == 0
    db_session.add(
        Product(
            product_name="Zephyrboard Keyboard",
            description="A quiet keyboard.",
            category="Electronics",
            brand="Voltrix",
            price=Decimal("49.99"),
            rating=Decimal("4.2"),
        )
    )
    db_session.commit()
    client.post(f"{URL}/rebuild-index")
    body = prefix_body(client, "zeph")
    assert body["expanded_terms"] == ["zephyrboard"]
    assert [i["id"] for i in body["items"]] == [51]


def test_rebuild_stats_include_trie(client, manager, loaded):
    body = client.post(f"{URL}/rebuild-index").json()
    assert body["trie_nodes"] > body["terms"] > 0
