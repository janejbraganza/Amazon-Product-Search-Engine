"""BM25 formula tests (pure functions)."""

import math

import pytest

from app.search.bm25 import DEFAULT_FIELD_WEIGHTS, BM25Config, idf, length_norm, term_score


def test_idf_matches_hand_calculation():
    # ln(1 + (4 - 1 + 0.5) / (1 + 0.5)) = ln(3.3333...) = 1.2039728
    assert idf(1, 4) == pytest.approx(1.2039728, rel=1e-6)


def test_idf_is_never_negative_even_for_terms_in_every_document():
    assert idf(10_000, 10_000) > 0
    assert idf(10_000, 10_000) < 0.0001  # e.g. "ideal", present in every product


def test_rarer_terms_have_higher_idf():
    assert idf(1, 1000) > idf(10, 1000) > idf(500, 1000)


def test_length_norm_matches_hand_calculation():
    # 1.2 * (1 - 0.75 + 0.75 * 10 / 8) = 1.2 * 1.1875 = 1.425
    assert length_norm(10, 8, k1=1.2, b=0.75) == pytest.approx(1.425)


def test_term_score_matches_hand_calculation():
    # idf * tf * (k1 + 1) / (tf + norm) = 1.2039728 * 2 * 2.2 / (2 + 1.425) = 1.5467096
    score = term_score(tf=2, idf_value=idf(1, 4), norm=length_norm(10, 8, 1.2, 0.75), k1=1.2)
    assert score == pytest.approx(1.5467096, rel=1e-6)


def test_full_formula_written_out():
    n, df, tf, dl, avgdl, k1, b = 1000, 25, 3.0, 70.0, 66.0, 1.2, 0.75
    expected = math.log(1 + (n - df + 0.5) / (df + 0.5)) * (
        tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl / avgdl))
    )
    assert term_score(tf, idf(df, n), length_norm(dl, avgdl, k1, b), k1) == pytest.approx(expected)


def test_zero_term_frequency_scores_zero():
    assert term_score(0, idf(1, 10), 1.0, 1.2) == 0.0


def test_term_frequency_saturates():
    """More occurrences score higher, but each extra occurrence adds less."""
    norm, idf_value = 1.2, 1.0
    s1, s2, s3, s20 = (term_score(tf, idf_value, norm, 1.2) for tf in (1, 2, 3, 20))
    assert s1 < s2 < s3 < s20
    assert (s2 - s1) > (s3 - s2)
    assert s20 < idf_value * (1.2 + 1)  # upper bound: idf * (k1 + 1)


def test_longer_documents_score_lower_when_b_is_positive():
    short = term_score(2, 1.0, length_norm(30, 60, 1.2, 0.75), 1.2)
    long = term_score(2, 1.0, length_norm(120, 60, 1.2, 0.75), 1.2)
    assert short > long


def test_b_zero_ignores_document_length():
    assert length_norm(30, 60, 1.2, 0.0) == length_norm(120, 60, 1.2, 0.0)


def test_empty_index_average_length_is_safe():
    assert length_norm(0, 0, 1.2, 0.75) == 1.2


def test_default_config():
    config = BM25Config()
    assert (config.k1, config.b) == (1.2, 0.75)
    assert config.field_weights == DEFAULT_FIELD_WEIGHTS
    assert config.field_weights["product_name"] > config.field_weights["description"]


@pytest.mark.parametrize(
    "kwargs",
    [{"k1": -1}, {"b": 1.5}, {"b": -0.1}, {"field_weights": {"product_name": 0}}],
)
def test_invalid_config_is_rejected(kwargs):
    with pytest.raises(ValueError):
        BM25Config(**kwargs)
