"""Text normalisation and tokenisation tests (pure functions, no database)."""

import pytest

from app.search.text_processing import (
    STOP_WORDS,
    analyze,
    fold_plural,
    normalize,
    prefix_variants,
    query_terms,
    split_prefix_query,
    tokenize,
    unique_terms,
)


def test_normalize_lowercases_and_drops_possessives():
    assert normalize("Men's HOODIE") == "men hoodie"
    assert normalize("Kids' Toys") == "kids toys"


def test_normalize_unicode():
    assert normalize("CAFÉ") == "café"
    assert normalize("ｗｉｄｅ") == "wide"  # full-width letters (NFKC)


def test_tokenize_discards_punctuation():
    assert tokenize("Black/White, Size: M! (new) & improved.") == [
        "black", "white", "size", "m", "new", "improved",
    ]  # fmt: skip


def test_tokenize_keeps_decimal_numbers_and_units():
    assert tokenize("15.6-inch 16GB 1:16") == ["15.6", "inch", "16gb", "1", "16"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("wi-fi", ["wi", "fi", "wifi"]),
        ("usb-c", ["usb", "c", "usbc"]),
        ("2-4 players", ["2", "4", "players"]),  # numeric parts are not joined
        ("1-year", ["1", "year"]),
    ],
)
def test_tokenize_hyphenated_words(text, expected):
    assert tokenize(text) == expected


@pytest.mark.parametrize(
    ("word", "singular"),
    [
        ("laptops", "laptop"),
        ("shoes", "shoe"),
        ("batteries", "battery"),
        ("glasses", "glass"),
        ("watches", "watch"),
        ("boxes", "box"),
        ("brushes", "brush"),
        ("glass", "glass"),
        ("series", "series"),
        ("lens", "lens"),
        ("cactus", "cactus"),
        ("gas", "gas"),  # too short to fold
        ("16gb", "16gb"),  # not purely alphabetic
    ],
)
def test_fold_plural(word, singular):
    assert fold_plural(word) == singular


def test_stop_words_removed_but_meaningful_words_kept():
    assert analyze("The sugar free bar for the gym") == ["sugar", "free", "bar", "gym"]
    assert analyze("Vitamin C") == ["vitamin", "c"]
    assert {"free", "c", "up", "all", "no"}.isdisjoint(STOP_WORDS)


def test_analyze_keeps_repeated_words():
    assert analyze("Laptop laptop LAPTOPS") == ["laptop", "laptop", "laptop"]


def test_unique_terms_deduplicates_across_fields():
    terms = unique_terms(["Voltrix Laptop", "A fast laptop.", "Voltrix", None, "Electronics"])
    assert terms == {"voltrix", "laptop", "fast", "electronic"}


def test_unique_terms_does_not_merge_words_across_fields():
    assert unique_terms(["usb", "c"]) == {"usb", "c"}


def test_query_terms_are_distinct_and_ordered():
    assert query_terms("Wireless EARBUDS wireless") == ["wireless", "earbud"]


@pytest.mark.parametrize("text", ["", "   ", "!!!", "the and of", None])
def test_empty_or_meaningless_input_gives_no_terms(text):
    assert analyze(text) == []


def test_index_and_query_processing_agree():
    """A query written differently from the product text still produces the same terms."""
    product_terms = unique_terms(["Voltrix Pro Laptop with Wi-Fi 6 and USB-C ports"])
    for query in ["LAPTOPS", "wifi", "Wi Fi", "usb-c port"]:
        assert set(query_terms(query)) <= product_terms


# ---- Prefix (partial word) processing -------------------------------------------


@pytest.mark.parametrize(
    ("query", "terms", "partial"),
    [
        ("lap", [], "lap"),
        ("Wireless EAR", ["wireless"], "ear"),
        ("wireless ear ", ["wireless", "ear"], None),  # trailing space: word finished
        ("the lap", [], "lap"),  # stop words dropped from complete words
        ("shoes for", ["shoe"], "for"),  # ...but a partial stop word is kept
        ("laptops ba", ["laptop"], "ba"),  # complete words folded, partial not
        ("15.6-in", ["15.6"], "in"),
        ("!!!", [], None),
        ("", [], None),
    ],
)
def test_split_prefix_query(query, terms, partial):
    assert split_prefix_query(query) == (terms, partial)


@pytest.mark.parametrize(
    ("prefix", "variants"),
    [("lap", ["lap"]), ("laptops", ["laptops", "laptop"]), ("batteries", ["batteries", "battery"])],
)
def test_prefix_variants(prefix, variants):
    assert prefix_variants(prefix) == variants
