"""InvertedIndex tests with small hand-made documents (no database)."""

import pytest

from app.search.bm25 import BM25Config, idf, length_norm, term_score
from app.search.inverted_index import InvertedIndex, SearchDocument
from app.search.text_processing import query_terms

DOCS = [
    SearchDocument(
        1, "Voltrix Pro Laptop", "A fast laptop. Laptop for work.", "Voltrix", "Electronics"
    ),
    SearchDocument(
        2, "Hearthwell Air Fryer", "Crispy food with less oil.", "Hearthwell", "Home & Kitchen"
    ),
    SearchDocument(
        3, "Voltrix Air Wireless Earbuds", "Wireless audio for the gym.", "Voltrix", "Electronics"
    ),
    SearchDocument(
        4, "Trailforge Running Shoes", "Lightweight shoes for running.", "Trailforge", "Clothing"
    ),
]


@pytest.fixture
def index() -> InvertedIndex:
    return InvertedIndex.build(DOCS)


def search(index: InvertedIndex, query: str, mode: str = "all") -> list[int]:
    terms = query_terms(query)
    return index.match_all(terms) if mode == "all" else index.match_any(terms)


def test_index_maps_terms_to_product_ids(index):
    assert index.lookup("laptop") == {1}
    assert index.lookup("air") == {2, 3}
    assert index.lookup("voltrix") == {1, 3}


def test_all_fields_are_indexed(index):
    assert index.lookup("fast") == {1}  # description
    assert index.lookup("hearthwell") == {2}  # brand / name
    assert index.lookup("kitchen") == {2}  # category
    assert index.lookup("electronic") == {1, 3}  # category, plural-folded


def test_repeated_words_store_product_once(index):
    # "laptop" appears three times in product 1 but the posting holds the id once.
    assert index.lookup("laptop") == frozenset({1})
    stats = index.stats()
    assert stats.postings == sum(len(index.lookup(t)) for t, _ in index.most_common_terms(10_000))


def test_stop_words_are_not_indexed(index):
    assert "the" not in index
    assert "for" not in index


def test_stats(index):
    stats = index.stats()
    assert stats.documents == 4
    assert stats.terms == index.vocabulary_size > 0
    assert stats.build_seconds >= 0


def test_single_word_search(index):
    assert search(index, "earbuds") == [3]


def test_multi_word_search_requires_all_terms(index):
    assert search(index, "voltrix air") == [3]
    assert search(index, "voltrix laptop") == [1]


def test_multi_word_search_any_mode(index):
    assert search(index, "laptop fryer", mode="any") == [1, 2]


def test_search_is_case_insensitive(index):
    assert search(index, "VOLTRIX") == search(index, "voltrix") == search(index, "VoLtRiX")


def test_plural_and_singular_queries_match(index):
    assert search(index, "shoe") == search(index, "shoes") == [4]


def test_missing_term(index):
    assert search(index, "zzzz") == []
    assert index.lookup("zzzz") == frozenset()
    # One unknown word makes an AND search empty, but OR still returns the known matches.
    assert search(index, "voltrix zzzz") == []
    assert search(index, "voltrix zzzz", mode="any") == [1, 3]


def test_no_terms_returns_nothing(index):
    assert index.match_all([]) == []
    assert index.match_any([]) == []


def test_results_are_sorted_ids(index):
    assert search(index, "electronics") == [1, 3]


def test_duplicate_document_id_is_rejected(index):
    with pytest.raises(ValueError, match="already indexed"):
        index.add_document(DOCS[0])


def test_rebuild_reflects_changed_data(index):
    changed = [
        SearchDocument(1, "Voltrix Pro Tablet", "A tablet.", "Voltrix", "Electronics"),
        *DOCS[1:],
    ]
    rebuilt = InvertedIndex.build(changed)
    assert search(rebuilt, "tablet") == [1]
    assert search(rebuilt, "laptop") == []
    assert search(index, "laptop") == [1]  # the old index object is unchanged


def test_empty_index():
    empty = InvertedIndex.build([])
    assert empty.document_count == 0
    assert empty.match_all(["laptop"]) == []
    assert empty.rank(["laptop"]) == []


# ---- BM25 statistics ------------------------------------------------------------
# Default field weights: product_name 3, brand 2, category 2, description 1.


def doc(id_, name, description="Plain text.", brand="Acme", category="Gadgets"):
    return SearchDocument(id_, name, description, brand, category)


def ranked_ids(index: InvertedIndex, query: str, require_all: bool = True) -> list[int]:
    return [d.id for d in index.rank(query_terms(query), require_all=require_all)]


def test_term_frequency_is_field_weighted_and_counts_repeats():
    index = InvertedIndex.build(
        [SearchDocument(1, "Voltrix Laptop", "laptop laptop", "Voltrix", "Electronics")]
    )
    assert index.term_frequency("laptop", 1) == 3 * 1 + 1 * 2  # name once, description twice
    assert index.term_frequency("voltrix", 1) == 3 * 1 + 2 * 1  # name + brand
    assert index.term_frequency("electronic", 1) == 2 * 1  # category
    assert index.term_frequency("missing", 1) == 0


def test_document_frequency(index):
    assert index.document_frequency("voltrix") == 2
    assert index.document_frequency("air") == 2
    assert index.document_frequency("laptop") == 1
    assert index.document_frequency("zzzz") == 0


def test_document_length_and_average():
    index = InvertedIndex.build(
        [
            SearchDocument(1, "Voltrix Laptop", "laptop laptop", "Voltrix", "Electronics"),
            SearchDocument(2, "Fryer", "crispy", "Pureva", "Kitchen"),
        ]
    )
    # 3 x 2 name terms + 1 x 2 description terms + 2 x 1 brand + 2 x 1 category = 12
    assert index.document_length(1) == 12
    # 3 x 1 + 1 x 1 + 2 x 1 + 2 x 1 = 8
    assert index.document_length(2) == 8
    assert index.average_document_length == 10
    assert index.stats().average_document_length == 10


def test_custom_field_weights():
    config = BM25Config(
        field_weights={"product_name": 1, "description": 1, "brand": 1, "category": 1}
    )
    index = InvertedIndex.build(
        [SearchDocument(1, "Voltrix Laptop", "laptop laptop", "Voltrix", "Electronics")], config
    )
    assert index.term_frequency("laptop", 1) == 3
    assert index.document_length(1) == 6


def test_rank_score_equals_bm25_formula():
    index = InvertedIndex.build(
        [doc(1, "Hiking Backpack", "A backpack for long trails."), doc(2, "Rain Jacket")]
    )
    (scored,) = index.rank(["backpack"])
    config = index.config
    expected = term_score(
        tf=index.term_frequency("backpack", 1),
        idf_value=idf(index.document_frequency("backpack"), index.document_count),
        norm=length_norm(
            index.document_length(1), index.average_document_length, config.k1, config.b
        ),
        k1=config.k1,
    )
    assert scored.id == 1
    assert scored.score == pytest.approx(expected)


def test_name_match_ranks_above_description_match():
    index = InvertedIndex.build(
        [
            doc(1, "Trail Bag", "Fits inside a hiking backpack."),
            doc(2, "Hiking Backpack", "A bag for long trails."),
        ]
    )
    assert ranked_ids(index, "backpack") == [2, 1]


def test_more_occurrences_rank_higher():
    index = InvertedIndex.build(
        [doc(1, "Water Bottle", "Keeps water cold."), doc(2, "Water Bottle", "Keeps tea cold.")]
    )
    assert ranked_ids(index, "water") == [1, 2]


def test_shorter_document_ranks_higher_for_same_term_frequency():
    index = InvertedIndex.build(
        [
            doc(1, "Desk Lamp", "A lamp with many extra words describing finishes and colours."),
            doc(2, "Desk Lamp", "A lamp."),
        ]
    )
    assert ranked_ids(index, "lamp") == [2, 1]


def test_rare_term_outweighs_common_term():
    index = InvertedIndex.build(
        [doc(1, "Black Mug"), doc(2, "Black Plate"), doc(3, "Black Bowl"), doc(4, "Ceramic Mug")]
    )
    # "ceramic" (df 1) is rarer than "black" (df 3), so product 4 beats products 2 and 3.
    assert ranked_ids(index, "black ceramic", require_all=False)[:1] == [4]


def test_multiple_terms_add_up():
    index = InvertedIndex.build(
        [doc(1, "Wireless Mouse"), doc(2, "Wireless Earbuds"), doc(3, "Wired Earbuds")]
    )
    any_mode = index.rank(query_terms("wireless earbuds"), require_all=False)
    assert any_mode[0].id == 2  # matches both terms
    assert {d.id for d in any_mode[1:]} == {1, 3}
    assert any_mode[0].score > any_mode[1].score


def test_all_mode_ranks_only_products_with_every_term():
    index = InvertedIndex.build(
        [doc(1, "Wireless Mouse"), doc(2, "Wireless Earbuds"), doc(3, "Wired Earbuds")]
    )
    assert ranked_ids(index, "wireless earbuds") == [2]
    assert set(ranked_ids(index, "wireless earbuds")) <= set(
        ranked_ids(index, "wireless earbuds", require_all=False)
    )


def test_equal_scores_are_ordered_by_product_id():
    index = InvertedIndex.build(
        [doc(9, "Steel Spoon"), doc(4, "Steel Spoon"), doc(7, "Steel Spoon"), doc(1, "Wooden")]
    )
    ranked = index.rank(["spoon"])
    assert [d.id for d in ranked] == [4, 7, 9]
    assert ranked[0].score == ranked[1].score == ranked[2].score


def test_repeated_query_word_counts_once():
    index = InvertedIndex.build([doc(1, "Steel Spoon"), doc(2, "Steel Fork")])
    assert index.rank(["spoon", "spoon"]) == index.rank(["spoon"])


def test_unknown_terms_add_nothing_in_any_mode():
    index = InvertedIndex.build([doc(1, "Steel Spoon"), doc(2, "Steel Fork")])
    assert index.rank(["spoon", "zzzz"], require_all=False) == index.rank(["spoon"])
    assert index.rank(["spoon", "zzzz"], require_all=True) == []


def test_rebuild_updates_ranking_statistics():
    docs = [doc(1, "Steel Spoon"), doc(2, "Wooden Fork")]
    before = InvertedIndex.build(docs)
    after = InvertedIndex.build([*docs, doc(3, "Steel Spoon Set"), doc(4, "Silver Spoon")])

    assert (before.document_count, after.document_count) == (2, 4)
    assert (before.document_frequency("spoon"), after.document_frequency("spoon")) == (1, 3)
    assert before.average_document_length != after.average_document_length
    # "spoon" became more common, so product 1's score for it changes.
    assert before.rank(["spoon"])[0].score != after.rank(["spoon"])[0].score
    # The old index is untouched (searches in progress keep consistent statistics).
    assert before.document_frequency("spoon") == 1
    assert ranked_ids(before, "spoon") == [1]


# ---- Trie integration and prefix ranking ----------------------------------------


def test_trie_contains_exactly_the_index_vocabulary(index):
    trie = index.vocabulary_trie
    vocabulary = {term for term, _ in index.most_common_terms(10_000)}
    assert len(trie) == index.vocabulary_size == len(vocabulary)
    for term in vocabulary:
        assert trie.contains(term)
        assert trie.frequency(term) == index.document_frequency(term)


def test_trie_is_built_with_the_index(index):
    assert index._trie is not None  # ready before the index is handed out
    assert index.stats().trie_nodes == index.vocabulary_trie.node_count > 1


def test_complete_prefix_orders_by_document_frequency(index):
    # voltrix (2 products), then A-Z among equal counts
    assert index.complete_prefix("v") == ["voltrix"]
    assert index.complete_prefix("w") == ["wireless", "work"]
    assert index.complete_prefix("zzz") == []
    assert index.complete_prefix("") == []


def test_complete_prefix_singular_fallback(index):
    assert index.complete_prefix("laptops") == ["laptop"]


def test_complete_prefix_limit(index):
    assert len(index.complete_prefix("l", limit=2)) == 2
    assert index.complete_prefix("l", limit=2) == index.complete_prefix("l")[:2]


def test_rank_groups_with_single_terms_equals_rank(index):
    terms = query_terms("voltrix air")
    for require_all in (True, False):
        assert index.rank_groups([[t] for t in terms], require_all) == index.rank(
            terms, require_all
        )


def test_prefix_group_uses_best_term_not_sum():
    index = InvertedIndex.build(
        [doc(1, "Ear Earbud Case"), doc(2, "Earbud Case"), doc(3, "Plain Case")]
    )
    ranked = index.rank_groups([["earbud", "ear"]])
    assert {d.id for d in ranked} == {1, 2}
    score = {d.id: d.score for d in ranked}

    def contribution(term: str, doc_id: int) -> float:
        cfg = index.config
        return term_score(
            index.term_frequency(term, doc_id),
            idf(index.document_frequency(term), index.document_count),
            length_norm(
                index.document_length(doc_id), index.average_document_length, cfg.k1, cfg.b
            ),
            cfg.k1,
        )

    # Product 1 contains both completions but is scored by its best one only, not the sum.
    best = max(contribution("earbud", 1), contribution("ear", 1))
    assert score[1] == pytest.approx(best)
    assert score[1] < contribution("earbud", 1) + contribution("ear", 1)


def test_prefix_group_matching_in_both_modes():
    index = InvertedIndex.build(
        [doc(1, "Wireless Earbud"), doc(2, "Wireless Mouse"), doc(3, "Wired Earbud")]
    )
    groups = [["wireless"], index.complete_prefix("ear")]
    assert {d.id for d in index.rank_groups(groups, require_all=True)} == {1}
    assert {d.id for d in index.rank_groups(groups, require_all=False)} == {1, 2, 3}
    assert index.rank_groups(groups, require_all=False)[0].id == 1  # matches both groups


def test_empty_prefix_group_means_no_match_in_all_mode():
    index = InvertedIndex.build([doc(1, "Steel Spoon"), doc(2, "Steel Fork")])
    assert index.rank_groups([["steel"], []], require_all=True) == []
    assert [d.id for d in index.rank_groups([["steel"], []], require_all=False)] == [1, 2]


def test_prefix_ranking_ties_ordered_by_id():
    index = InvertedIndex.build([doc(8, "Steel Spoon"), doc(3, "Steel Spoon"), doc(5, "Wood")])
    ranked = index.rank_groups([index.complete_prefix("spo")])
    assert [d.id for d in ranked] == [3, 8]
    assert ranked[0].score == ranked[1].score


def test_rebuild_replaces_trie_and_keeps_old_one_intact():
    before = InvertedIndex.build([doc(1, "Steel Spoon")])
    after = InvertedIndex.build([doc(1, "Steel Spoon"), doc(2, "Zephyr Kettle")])
    assert before.complete_prefix("zep") == []
    assert after.complete_prefix("zep") == ["zephyr"]
    assert before.vocabulary_trie is not after.vocabulary_trie
    assert before.complete_prefix("zep") == []  # old index (and its Trie) unchanged
