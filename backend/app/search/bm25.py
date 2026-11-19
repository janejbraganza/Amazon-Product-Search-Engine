"""Okapi BM25 scoring.

For a query q and a product d:

    score(d, q) = sum over terms t in q of
                  IDF(t) * tf(t,d) * (k1 + 1) / (tf(t,d) + k1 * (1 - b + b * |d| / avgdl))

    IDF(t) = ln(1 + (N - df(t) + 0.5) / (df(t) + 0.5))

    tf(t,d)  how often t occurs in d (here: field-weighted, see BM25Config.field_weights)
    df(t)    number of products containing t
    N        number of indexed products
    |d|      length of d in terms (field-weighted);  avgdl = average |d|
    k1       term-frequency saturation: higher = repeated words keep adding more score
    b        length normalisation: 0 = ignore length, 1 = fully normalise by length

The IDF is the Lucene/Elasticsearch "+1" variant: it is never negative, so a word that
appears in almost every product adds almost nothing instead of lowering the score.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass, field

# A term in the product name counts three times as much as one in the description, etc.
DEFAULT_FIELD_WEIGHTS: dict[str, float] = {
    "product_name": 3.0,
    "brand": 2.0,
    "category": 2.0,
    "description": 1.0,
}


@dataclass(frozen=True)
class BM25Config:
    k1: float = 1.2
    b: float = 0.75
    field_weights: Mapping[str, float] = field(default_factory=lambda: dict(DEFAULT_FIELD_WEIGHTS))

    def __post_init__(self) -> None:
        if self.k1 < 0:
            raise ValueError("k1 must be >= 0")
        if not 0 <= self.b <= 1:
            raise ValueError("b must be between 0 and 1")
        if any(weight <= 0 for weight in self.field_weights.values()):
            raise ValueError("field weights must be positive")


def idf(document_frequency: int, document_count: int) -> float:
    """Inverse document frequency: rare terms score high, common terms close to 0."""
    return math.log(1 + (document_count - document_frequency + 0.5) / (document_frequency + 0.5))


def length_norm(doc_length: float, avg_doc_length: float, k1: float, b: float) -> float:
    """The k1 * (1 - b + b * |d| / avgdl) part of the denominator (depends only on d)."""
    if avg_doc_length <= 0:
        return k1
    return k1 * (1 - b + b * doc_length / avg_doc_length)


def term_score(tf: float, idf_value: float, norm: float, k1: float) -> float:
    """BM25 contribution of one term to one product's score."""
    if tf <= 0:
        return 0.0
    return idf_value * tf * (k1 + 1) / (tf + norm)
