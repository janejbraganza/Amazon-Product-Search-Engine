"""Autocomplete endpoint tests: GET /api/v1/search/suggestions (test database)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.search.index_manager import SearchIndexManager, get_index_manager
from app.search.text_processing import unique_terms
from app.services.product_loader import load_products

URL = "/api/v1/search/suggestions"


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


def vocabulary(products) -> dict[str, int]:
    """Reference: every indexed term -> number of products containing it."""
    counts: dict[str, int] = {}
    for p in products:
        for term in unique_terms([p.product_name, p.description, p.brand, p.category]):
            counts[term] = counts.get(term, 0) + 1
    return counts


def suggest(client: TestClient, q: str, **params) -> dict:
    response = client.get(URL, params={"q": q, **params})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("prefix", ["s", "wa", "bl", "ide", "1", "pr"])
def test_suggestions_match_reference_vocabulary(client, manager, loaded, prefix):
    counts = vocabulary(loaded)
    expected = sorted((t for t in counts if t.startswith(prefix)), key=lambda t: (-counts[t], t))
    body = suggest(client, prefix, limit=50)
    assert [s["term"] for s in body["suggestions"]] == expected[:50]
    assert all(s["product_count"] == counts[s["term"]] for s in body["suggestions"])


def test_response_shape(client, manager, loaded):
    body = suggest(client, "ide")
    assert body["query"] == "ide"
    assert body["prefix"] == "ide"
    assert body["suggestions"][0] == {"term": "ideal", "product_count": 50, "display": "ideal"}


def test_order_is_deterministic_and_has_no_duplicates(client, manager, loaded):
    first = suggest(client, "s", limit=50)["suggestions"]
    assert first == suggest(client, "s", limit=50)["suggestions"]
    terms = [s["term"] for s in first]
    assert len(terms) == len(set(terms))
    keys = [(-s["product_count"], s["term"]) for s in first]
    assert keys == sorted(keys)


def test_default_and_custom_limit(client, manager, loaded):
    assert len(suggest(client, "s")["suggestions"]) == 10
    assert len(suggest(client, "s", limit=3)["suggestions"]) == 3


def test_case_insensitive(client, manager, loaded):
    assert suggest(client, "IDE")["suggestions"] == suggest(client, "ide")["suggestions"]


def test_no_matches_returns_empty_list(client, manager, loaded):
    body = suggest(client, "xyzq")
    assert body["suggestions"] == []
    assert body["prefix"] == "xyzq"


def test_completes_the_last_word(client, manager, loaded):
    body = suggest(client, "stainless ide")
    assert body["prefix"] == "ide"
    assert body["suggestions"][0]["term"] == "ideal"


def test_plural_prefix_falls_back_to_singular(client, manager, loaded):
    counts = vocabulary(loaded)
    assert "ideal" in counts and "ideals" not in counts
    terms = [s["term"] for s in suggest(client, "ideals")["suggestions"]]
    assert terms == ["ideal"]


def test_stop_word_prefix_is_still_completed(client, manager, loaded):
    # "for" is a stop word for full-word search, but as a prefix it may start a real word.
    counts = vocabulary(loaded)
    expected = {t for t in counts if t.startswith("for")}
    assert {s["term"] for s in suggest(client, "for", limit=50)["suggestions"]} == expected


@pytest.mark.parametrize(
    ("params", "detail"),
    [
        ({"q": "   "}, "Query must not be blank"),
        ({"q": "!!!"}, "Query contains no searchable characters"),
    ],
)
def test_blank_or_punctuation_only_returns_422(client, manager, params, detail):
    response = client.get(URL, params=params)
    assert response.status_code == 422
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize(
    "params",
    [{}, {"q": ""}, {"q": "x" * 201}, {"q": "la", "limit": 0}, {"q": "la", "limit": 51}],
    ids=["missing", "empty", "too-long", "limit-0", "limit-51"],
)
def test_invalid_parameters_return_422(client, manager, params):
    assert client.get(URL, params=params).status_code == 422


def test_suggestions_after_rebuild_include_new_words(client, manager, loaded, db_session):
    from decimal import Decimal

    from app.models.product import Product

    assert suggest(client, "zephyr")["suggestions"] == []
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
    assert suggest(client, "zephyr")["suggestions"] == []  # stale until rebuilt
    client.post("/api/v1/search/rebuild-index")
    assert suggest(client, "zephyr")["suggestions"] == [
        {"term": "zephyrboard", "product_count": 1, "display": "zephyrboard"}
    ]
