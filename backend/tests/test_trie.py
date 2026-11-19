"""Trie tests (pure data structure, no database)."""

import random
import string

import pytest

from app.search.trie import Trie


@pytest.fixture
def trie() -> Trie:
    t = Trie()
    for word, freq in [("laptop", 220), ("lap", 3), ("lamp", 40), ("ladder", 40), ("tablet", 90)]:
        t.insert(word, freq)
    return t


# ---- Insertion and lookup ---------------------------------------------------------


def test_insert_and_contains(trie):
    assert trie.contains("laptop")
    assert "lamp" in trie
    assert len(trie) == 5


def test_prefix_of_a_word_is_not_a_word(trie):
    assert not trie.contains("lapt")  # only a path, not an inserted word
    assert trie.has_prefix("lapt")


def test_shared_prefixes_share_nodes():
    t = Trie()
    t.insert("lap")
    t.insert("laptop")  # reuses l-a-p, adds t-o-p
    assert t.node_count == 1 + len("laptop")  # root + one node per character


def test_frequency(trie):
    assert trie.frequency("laptop") == 220
    assert trie.frequency("lapt") == 0  # not a complete word
    assert trie.frequency("zebra") == 0


# ---- Duplicates -------------------------------------------------------------------


def test_duplicate_insert_is_stored_once_and_adds_frequency():
    t = Trie()
    t.insert("laptop", 2)
    nodes_after_first = t.node_count
    t.insert("laptop", 3)
    t.insert("laptop")
    assert len(t) == 1
    assert t.node_count == nodes_after_first  # no new nodes
    assert t.frequency("laptop") == 6
    assert t.words_with_prefix("lap") == ["laptop"]  # never returned twice


# ---- Prefix search ----------------------------------------------------------------


def test_words_with_prefix_most_frequent_first_then_alphabetical(trie):
    # laptop 220, ladder 40, lamp 40 (tie -> A-Z), lap 3
    assert trie.words_with_prefix("la") == ["laptop", "ladder", "lamp", "lap"]


def test_prefix_that_is_also_a_word_includes_it(trie):
    assert trie.words_with_prefix("lap") == ["laptop", "lap"]


def test_full_word_as_prefix(trie):
    assert trie.words_with_prefix("laptop") == ["laptop"]


def test_limit(trie):
    assert trie.words_with_prefix("la", limit=2) == ["laptop", "ladder"]
    assert trie.words_with_prefix("la", limit=0) == []
    assert trie.words_with_prefix("la", limit=100) == ["laptop", "ladder", "lamp", "lap"]
    with pytest.raises(ValueError):
        trie.words_with_prefix("la", limit=-1)


def test_no_matching_prefix(trie):
    assert trie.words_with_prefix("zzz") == []
    assert trie.words_with_prefix("laptops") == []  # longer than any stored word
    assert not trie.has_prefix("zzz")


def test_prefix_search_is_case_sensitive_by_design(trie):
    # The Trie stores exactly what it is given; lowercasing is the caller's job
    # (text_processing), so "LAP" does not match.
    assert trie.words_with_prefix("LAP") == []


# ---- Empty and invalid input ------------------------------------------------------


def test_empty_prefix_returns_nothing(trie):
    assert trie.words_with_prefix("") == []
    assert not trie.has_prefix("")


def test_empty_trie():
    t = Trie()
    assert len(t) == 0
    assert t.words_with_prefix("a") == []
    assert not t.contains("a")


@pytest.mark.parametrize("prefix", ["!", "la!", "lä", "la p", "\n", "🙂"])
def test_unknown_characters_simply_do_not_match(trie, prefix):
    assert trie.words_with_prefix(prefix) == []


def test_any_characters_can_be_stored():
    t = Trie()
    for word in ["15.6", "usb-c", "café", "🙂ok"]:
        t.insert(word)
    assert t.words_with_prefix("15") == ["15.6"]
    assert t.words_with_prefix("caf") == ["café"]
    assert t.words_with_prefix("🙂") == ["🙂ok"]


@pytest.mark.parametrize("bad", [None, 42, b"lap", ["lap"]])
def test_non_string_input_raises_type_error(trie, bad):
    with pytest.raises(TypeError):
        trie.words_with_prefix(bad)
    with pytest.raises(TypeError):
        trie.insert(bad)


def test_invalid_insert_values():
    t = Trie()
    with pytest.raises(ValueError):
        t.insert("")
    with pytest.raises(ValueError):
        t.insert("laptop", frequency=-1)


# ---- Scale ------------------------------------------------------------------------


def test_large_number_of_words_matches_brute_force():
    rng = random.Random(7)
    words = [
        "".join(rng.choices(string.ascii_lowercase, k=rng.randint(1, 10))) for _ in range(50_000)
    ]
    t = Trie()
    for word in words:
        t.insert(word)

    counts: dict[str, int] = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1
    assert len(t) == len(counts)  # duplicates in the random list stored once

    for prefix in ["a", "ab", "xyz", "q", "mm", "zzzz", "hello"]:
        expected = sorted(
            (w for w in counts if w.startswith(prefix)), key=lambda w: (-counts[w], w)
        )
        assert t.words_with_prefix(prefix) == expected
        assert t.words_with_prefix(prefix, limit=5) == expected[:5]


def test_very_long_word_does_not_hit_recursion_limit():
    t = Trie()
    long_word = "a" * 5_000
    t.insert(long_word)
    assert t.words_with_prefix("aaa") == [long_word]
