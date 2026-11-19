"""Filters, sorting, facets and display forms on small hand-built indexes (no database)."""

import threading
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.search.filters import (
    SearchFilters,
    SortOption,
    apply_filters,
    compute_facets,
    sort_results,
)
from app.search.inverted_index import InvertedIndex, SearchDocument
from app.search.text_processing import analyze, analyze_with_surface, query_terms


def doc(id_, name, category, brand, price, rating, stock, day, description="A gadget."):
    return SearchDocument(
        id=id_,
        product_name=name,
        description=description,
        brand=brand,
        category=category,
        price=Decimal(price),
        rating=Decimal(rating),
        stock_quantity=stock,
        created_at=datetime(2026, 1, day, tzinfo=UTC),
    )


# Every product name contains "gadget", so the query "gadget" matches all of them.
DOCS = [
    doc(1, "Voltrix Gadget", "Electronics", "Voltrix", "99.99", "4.5", 10, 5),
    doc(2, "Voltrix Mini Gadget", "Electronics", "Voltrix", "49.50", "3.9", 0, 9),
    doc(3, "Nexora Gadget Pro", "Electronics", "Nexora", "149.00", "4.8", 3, 1),
    doc(4, "Hearthwell Kitchen Gadget", "Home & Kitchen", "Hearthwell", "19.99", "4.5", 50, 7),
    doc(5, "Hearthwell Gadget Set", "Home & Kitchen", "Hearthwell", "49.50", "2.0", 8, 3),
    doc(6, "Trailforge Outdoor Gadget", "Sports & Outdoors", "Trailforge", "75.00", "4.1", 0, 9),
]


@pytest.fixture(scope="module")
def index() -> InvertedIndex:
    return InvertedIndex.build(DOCS)


@pytest.fixture(scope="module")
def ranked(index):
    return index.rank(query_terms("gadget"))


def ids(docs):
    return [d.id for d in docs]


def filters(**kwargs) -> SearchFilters:
    return SearchFilters.create(**kwargs)


# ---- SearchFilters: validation and normalisation -----------------------------------


def test_filters_normalise_case_and_whitespace():
    f = filters(categories=["  ELECTRONICS "], brands=["voltrix", "NEXORA"])
    assert f.categories == {"electronics"}
    assert f.brands == {"voltrix", "nexora"}


@pytest.mark.parametrize(
    "kwargs",
    [{"categories": ["  "]}, {"brands": [""]}, {"min_price": Decimal(10), "max_price": Decimal(5)}],
)
def test_invalid_filters_raise(kwargs):
    with pytest.raises(ValueError):
        filters(**kwargs)


def test_equal_min_and_max_price_is_allowed():
    assert filters(min_price=Decimal("49.50"), max_price=Decimal("49.50")).min_price == Decimal(
        "49.50"
    )


def test_empty_filters():
    assert SearchFilters().is_empty
    assert filters().is_empty
    assert not filters(in_stock=True).is_empty


def test_cache_params_are_canonical():
    a = filters(categories=["Electronics", "Books"], min_price=Decimal("10.00"))
    b = filters(categories=["books", "ELECTRONICS"], min_price=Decimal("10"))
    assert a.cache_params() == b.cache_params()
    assert a.cache_params()["categories"] == ["books", "electronics"]
    assert (
        filters(min_price=Decimal(10)).cache_params()
        != filters(max_price=Decimal(10)).cache_params()
    )


# ---- Filtering -----------------------------------------------------------------------


def test_no_filters_keep_the_ranked_list_unchanged(index, ranked):
    assert apply_filters(ranked, index, SearchFilters()) == ranked


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"categories": ["electronics"]}, {1, 2, 3}),
        ({"categories": ["Home & Kitchen", "sports & OUTDOORS"]}, {4, 5, 6}),  # OR within
        ({"brands": ["HEARTHWELL"]}, {4, 5}),
        ({"min_price": Decimal("49.50")}, {1, 2, 3, 5, 6}),  # inclusive
        ({"max_price": Decimal("49.50")}, {2, 4, 5}),  # inclusive
        ({"min_price": Decimal(50), "max_price": Decimal(100)}, {1, 6}),
        ({"min_rating": Decimal("4.5")}, {1, 3, 4}),  # inclusive
        ({"in_stock": True}, {1, 3, 4, 5}),
        ({"categories": ["Electronics"], "in_stock": True}, {1, 3}),  # AND across
        (
            {"categories": ["electronics"], "brands": ["voltrix"], "max_price": Decimal(60)},
            {2},
        ),
        ({"categories": ["Books"]}, set()),
    ],
)
def test_each_filter_and_combinations(index, ranked, kwargs, expected):
    assert set(ids(apply_filters(ranked, index, filters(**kwargs)))) == expected


def test_filtering_preserves_relevance_order(index, ranked):
    kept = ids(apply_filters(ranked, index, filters(in_stock=True)))
    assert kept == [i for i in ids(ranked) if i in set(kept)]


def test_products_without_metadata_never_match_value_filters():
    bare = InvertedIndex.build([SearchDocument(1, "Gadget", "x", "B", "C")])
    ranked = bare.rank(["gadget"])
    assert ids(apply_filters(ranked, bare, SearchFilters())) == [1]
    assert ids(apply_filters(ranked, bare, filters(min_price=Decimal(1)))) == []
    assert ids(apply_filters(ranked, bare, filters(categories=["c"]))) == [1]


# ---- Sorting -------------------------------------------------------------------------


def test_relevance_sort_keeps_bm25_order(index, ranked):
    assert sort_results(ranked, index, SortOption.RELEVANCE) == ranked


def test_price_ascending_with_id_tie_break(index, ranked):
    # 2 and 5 both cost 49.50 -> lower id first
    assert ids(sort_results(ranked, index, SortOption.PRICE_ASC)) == [4, 2, 5, 6, 1, 3]


def test_price_descending_with_id_tie_break(index, ranked):
    assert ids(sort_results(ranked, index, SortOption.PRICE_DESC)) == [3, 1, 6, 2, 5, 4]


def test_rating_with_id_tie_break(index, ranked):
    # 1 and 4 both rated 4.5 -> lower id first
    assert ids(sort_results(ranked, index, SortOption.RATING)) == [3, 1, 4, 6, 2, 5]


def test_newest_with_id_tie_break(index, ranked):
    # 2 and 6 both created on day 9 -> lower id first
    assert ids(sort_results(ranked, index, SortOption.NEWEST)) == [2, 6, 4, 1, 5, 3]


def test_sort_after_filter(index, ranked):
    filtered = apply_filters(ranked, index, filters(categories=["electronics"]))
    assert ids(sort_results(filtered, index, SortOption.PRICE_ASC)) == [2, 1, 3]


def test_products_without_sort_value_go_last():
    mixed = InvertedIndex.build(
        [
            SearchDocument(1, "Gadget", "x", "B", "C"),  # no metadata values
            doc(2, "Gadget", "C", "B", "5.00", "3.0", 1, 2),
        ]
    )
    ranked = mixed.rank(["gadget"])
    for option in (
        SortOption.PRICE_ASC,
        SortOption.PRICE_DESC,
        SortOption.RATING,
        SortOption.NEWEST,
    ):
        assert ids(sort_results(ranked, mixed, option)) == [2, 1]


# ---- Facets --------------------------------------------------------------------------


def facet_map(values):
    return {v.value: v.count for v in values}


def test_facets_without_filters_count_all_matches(index, ranked):
    facets = compute_facets(ranked, index, SearchFilters())
    assert facet_map(facets.categories) == {
        "Electronics": 3,
        "Home & Kitchen": 2,
        "Sports & Outdoors": 1,
    }
    assert facet_map(facets.brands) == {"Voltrix": 2, "Hearthwell": 2, "Nexora": 1, "Trailforge": 1}
    # sorted by count desc, then name
    assert [v.value for v in facets.brands] == ["Hearthwell", "Voltrix", "Nexora", "Trailforge"]


def test_category_facet_ignores_the_category_filter(index, ranked):
    facets = compute_facets(ranked, index, filters(categories=["electronics"]))
    # every category is still listed with its own count...
    assert facet_map(facets.categories) == {
        "Electronics": 3,
        "Home & Kitchen": 2,
        "Sports & Outdoors": 1,
    }
    # ...while brands respect the category filter
    assert facet_map(facets.brands) == {"Voltrix": 2, "Nexora": 1}


def test_brand_facet_ignores_the_brand_filter(index, ranked):
    facets = compute_facets(ranked, index, filters(brands=["voltrix"]))
    assert facet_map(facets.brands) == {"Voltrix": 2, "Hearthwell": 2, "Nexora": 1, "Trailforge": 1}
    assert facet_map(facets.categories) == {"Electronics": 2}


def test_facets_with_combined_filters(index, ranked):
    f = filters(categories=["electronics"], brands=["voltrix"], in_stock=True)
    facets = compute_facets(ranked, index, f)
    # categories: brand=voltrix AND in stock -> only product 1
    assert facet_map(facets.categories) == {"Electronics": 1}
    # brands: category=electronics AND in stock -> products 1 (Voltrix), 3 (Nexora)
    assert facet_map(facets.brands) == {"Voltrix": 1, "Nexora": 1}


def test_facets_count_the_full_match_list(index):
    two = index.rank(query_terms("voltrix"))
    facets = compute_facets(two, index, SearchFilters())
    assert facet_map(facets.categories) == {"Electronics": 2}


# ---- Display forms ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Voltrix Wireless Earbuds, USB-C and Wi-Fi 6",
        "The Men's Running-Shoes, 15.6-inch!",
        "Batteries, glasses & watches for kids'",
        "Height-adjustable desk with anti-glare 2-4 players",
        "the and of",
        "",
    ],
)
def test_analyze_with_surface_gives_exactly_the_analyze_terms(text):
    assert [term for term, _ in analyze_with_surface(text)] == analyze(text)


def test_analyze_with_surface_pairs():
    assert analyze_with_surface("Wireless Earbuds, USB-C") == [
        ("wireless", "wireless"),
        ("earbud", "earbuds"),
        ("usb", "usb"),
        ("c", "c"),
        ("usbc", "usb-c"),
    ]


def test_display_form_is_the_most_common_written_form():
    idx = InvertedIndex.build(
        [
            SearchDocument(1, "Earbuds", "Wireless earbuds", "B", "Electronics"),
            SearchDocument(2, "Earbud case", "Fits two earbuds", "B", "Electronics"),
            SearchDocument(3, "USB-C cable", "usb-c", "B", "Electronics"),
        ]
    )
    assert idx.display_form("earbud") == "earbuds"  # 3 x "earbuds" vs 1 x "earbud"
    assert idx.display_form("usbc") == "usb-c"
    assert idx.display_form("electronic") == "electronics"
    assert idx.display_form("unknown") == "unknown"


def test_display_form_ties_are_alphabetical():
    idx = InvertedIndex.build(
        [SearchDocument(1, "Shoe", "x", "B", "C"), SearchDocument(2, "Shoes", "x", "B", "C")]
    )
    assert idx.display_form("shoe") == "shoe"  # 1 vs 1 -> alphabetical


def test_searching_a_display_form_finds_the_same_products():
    idx = InvertedIndex.build(DOCS + [SearchDocument(9, "USB-C Earbuds", "x", "B", "Electronics")])
    for term in ("usbc", "earbud", "electronic"):
        display = idx.display_form(term)
        assert set(idx.match_all(query_terms(display))) == idx.lookup(term)


# ---- Metadata and rebuild consistency -------------------------------------------------


def test_metadata_is_stored_per_product(index):
    meta = index.metadata(2)
    assert (meta.category, meta.brand, meta.price, meta.rating, meta.stock_quantity) == (
        "Electronics",
        "Voltrix",
        Decimal("49.50"),
        Decimal("3.9"),
        0,
    )
    assert meta.category_key == "electronics"
    assert index.metadata(999) is None


def test_rebuild_creates_new_metadata_and_leaves_the_old_snapshot_intact():
    old = InvertedIndex.build(DOCS)
    changed = [doc(1, "Voltrix Gadget", "Electronics", "Voltrix", "5.00", "4.5", 10, 5), *DOCS[1:]]
    new = InvertedIndex.build(changed)
    assert old.metadata(1).price == Decimal("99.99")
    assert new.metadata(1).price == Decimal("5.00")
    cheap = filters(max_price=Decimal(10))
    assert ids(apply_filters(old.rank(["gadget"]), old, cheap)) == []
    assert ids(apply_filters(new.rank(["gadget"]), new, cheap)) == [1]


def test_concurrent_rebuilds_never_mix_snapshots():
    """Searches running while another thread keeps swapping in new indexes must always see
    postings, metadata and facets from ONE index object."""
    a = InvertedIndex.build(DOCS)  # product 1 costs 99.99
    b = InvertedIndex.build(
        [doc(1, "Voltrix Gadget", "Electronics", "Voltrix", "5.00", "4.5", 10, 5), *DOCS[1:]]
    )
    current = {"index": a}
    stop = threading.Event()
    errors: list[str] = []

    def swapper():
        while not stop.is_set():
            current["index"] = b if current["index"] is a else a

    def searcher():
        cheap = filters(max_price=Decimal(10))
        for _ in range(300):
            index = current["index"]  # one reference per "request"
            ranked = index.rank(["gadget"])
            result = ids(apply_filters(ranked, index, cheap))
            facets = compute_facets(ranked, index, cheap)
            expected = [] if index is a else [1]
            if result != expected or sum(v.count for v in facets.brands) != len(expected):
                errors.append(f"inconsistent result {result} for {'a' if index is a else 'b'}")

    swap = threading.Thread(target=swapper)
    workers = [threading.Thread(target=searcher) for _ in range(4)]
    swap.start()
    for w in workers:
        w.start()
    for w in workers:
        w.join()
    stop.set()
    swap.join()
    assert errors == []


@pytest.mark.parametrize("option", list(SortOption))
@pytest.mark.parametrize("first", [0, 1, 2, 4, 6, 50])
def test_partial_sort_equals_the_start_of_the_full_sort(index, ranked, option, first):
    full = sort_results(ranked, index, option)
    assert sort_results(ranked, index, option, first=first) == full[:first]
