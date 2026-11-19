"""In-memory inverted index with BM25 ranking statistics.

Each term maps to the products containing it, together with how often it occurs there:

    1 "Voltrix Pro Laptop"      laptop  -> {1: 3.0, 3: 3.0}
    2 "Hearthwell Air Fryer"    voltrix -> {1: 3.0, 3: 3.0}
    3 "Voltrix Air Laptop"      air     -> {2: 3.0, 3: 3.0}

(3.0 because a word in the product name has field weight 3; see bm25.BM25Config.)

From this structure we get every BM25 input:
    tf(t, d)  = postings[t][d]            df(t) = len(postings[t])
    |d|       = doc_lengths[d]            N     = len(doc_lengths)
    avgdl     = total_length / N

Matching (which products?) and ranking (in what order?) are separate steps:
``match_all`` / ``match_any`` return the matching IDs; ``rank`` scores and sorts them.

The index also owns a Trie of its vocabulary (``vocabulary_trie``) for prefix search and
autocomplete. It is built from the same postings, as part of the same object.

It also keeps, per product, the metadata needed to filter and sort results (category,
brand, price, rating, stock, created_at; see ``metadata``), and for each term the way it
is most often written in the products ("earbuds" for "earbud"; see ``display_form``).

The index is built once and then treated as read-only. To pick up data changes, build a
new index and swap it in (see ``index_manager.py``); readers never see a partial index,
and postings, statistics, the Trie, metadata and display forms always come from the same
build. A request that holds one index object therefore sees one consistent snapshot.
"""

import time
import uuid
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.search import bm25
from app.search.text_processing import analyze_with_surface, prefix_variants
from app.search.trie import Trie

# Most completions a partial word expands to (most common first). Same default as
# Elasticsearch's "max_expansions" for prefix queries.
DEFAULT_MAX_EXPANSIONS = 50

# Scores equal to this many decimal places are treated as ties (broken by product id),
# so floating-point noise in the last digits never decides the order.
SCORE_DECIMALS = 6


@dataclass(frozen=True)
class SearchDocument:
    """The searchable fields of one product, plus the values used to filter and sort.

    The filter/sort values are optional so small hand-built indexes (e.g. in tests) still
    work; a product without a price simply never matches a price filter.
    """

    id: int
    product_name: str
    description: str
    brand: str
    category: str
    price: Decimal | None = None
    rating: Decimal | None = None
    stock_quantity: int | None = None
    created_at: datetime | None = None

    def fields(self) -> dict[str, str]:
        return {
            "product_name": self.product_name,
            "description": self.description,
            "brand": self.brand,
            "category": self.category,
        }


@dataclass(frozen=True, slots=True)
class ProductMeta:
    """Filter/sort values of one product, captured when the index was built.

    ``category_key`` / ``brand_key`` are case-folded for case-insensitive filtering; the
    original spellings are kept for display (e.g. facet labels).
    """

    category: str
    brand: str
    category_key: str
    brand_key: str
    price: Decimal | None
    rating: Decimal | None
    stock_quantity: int | None
    created_at: datetime | None


@dataclass(frozen=True)
class ScoredDocument:
    id: int
    score: float


@dataclass(frozen=True)
class IndexStats:
    build_id: str
    documents: int
    terms: int
    postings: int  # total (term, product) pairs stored
    average_document_length: float
    trie_nodes: int
    build_seconds: float


class InvertedIndex:
    def __init__(self, config: bm25.BM25Config | None = None) -> None:
        self.config = config or bm25.BM25Config()
        # Unique per index object. The search cache puts it in every key, so results from
        # an old index can never be served after a rebuild (see cache/search_cache.py).
        self.build_id = uuid.uuid4().hex
        # term -> {product_id: field-weighted term frequency}. One entry per product,
        # however many times the word is repeated (the count goes into the value).
        self._postings: dict[str, dict[int, float]] = {}
        self._doc_lengths: dict[int, float] = {}
        self._total_length = 0.0
        self._length_norms: dict[int, float] | None = None  # cached BM25 length part
        self._trie: Trie | None = None  # vocabulary Trie, built from _postings
        self._meta: dict[int, ProductMeta] = {}  # product_id -> filter/sort values
        # (term, written form) -> occurrences, e.g. ("earbud", "earbuds") -> 462.
        # One flat dict keeps this to a single dict update per word while indexing.
        self._surface_counts: dict[tuple[str, str], int] = {}
        self._display_forms: dict[str, str] | None = None  # term -> most common form
        self._build_seconds = 0.0

    @classmethod
    def build(
        cls, documents: Iterable[SearchDocument], config: bm25.BM25Config | None = None
    ) -> "InvertedIndex":
        """Build a complete index (postings, statistics and Trie) in a single pass."""
        started = time.perf_counter()
        index = cls(config)
        for document in documents:
            index.add_document(document)
        # Finish everything before the index is returned (and later swapped in), so no
        # search can ever see a half-built Trie or out-of-date statistics.
        index._compute_length_norms()
        index._build_trie()
        index._build_display_forms()
        index._build_seconds = time.perf_counter() - started
        return index

    def add_document(self, document: SearchDocument) -> None:
        if document.id in self._doc_lengths:
            raise ValueError(f"Product {document.id} is already indexed")

        weights = self.config.field_weights
        term_frequencies: dict[str, float] = {}
        surface_counts = self._surface_counts
        length = 0.0
        for field_name, text in document.fields().items():
            weight = weights.get(field_name, 1.0)
            # Same terms as analyze(text), each paired with the word as written.
            pairs = analyze_with_surface(text)
            length += weight * len(pairs)
            for pair in pairs:
                token = pair[0]
                term_frequencies[token] = term_frequencies.get(token, 0.0) + weight
                surface_counts[pair] = surface_counts.get(pair, 0) + 1

        for term, frequency in term_frequencies.items():
            self._postings.setdefault(term, {})[document.id] = frequency
        self._doc_lengths[document.id] = length
        self._total_length += length
        self._meta[document.id] = ProductMeta(
            category=document.category,
            brand=document.brand,
            category_key=document.category.casefold(),
            brand_key=document.brand.casefold(),
            price=document.price,
            rating=document.rating,
            stock_quantity=document.stock_quantity,
            created_at=document.created_at,
        )
        self._length_norms = None  # avgdl changed; recompute on next use
        self._trie = None  # vocabulary may have changed; rebuild on next use
        self._display_forms = None

    # ---- Matching (terms must already be processed with text_processing.analyze) ----

    def __contains__(self, term: str) -> bool:
        return term in self._postings

    def lookup(self, term: str) -> frozenset[int]:
        return frozenset(self._postings.get(term, ()))

    def match_all(self, terms: Iterable[str]) -> list[int]:
        """Sorted IDs of products containing every term (AND)."""
        postings = [self._postings.get(term, {}) for term in set(terms)]
        if not postings:
            return []
        postings.sort(key=len)  # intersect from the smallest list: less work, early exit
        result = set(postings[0])
        for other in postings[1:]:
            result.intersection_update(other)
            if not result:
                break
        return sorted(result)

    def match_any(self, terms: Iterable[str]) -> list[int]:
        """Sorted IDs of products containing at least one term (OR)."""
        result: set[int] = set()
        for term in set(terms):
            result.update(self._postings.get(term, ()))
        return sorted(result)

    def _match_groups(self, groups: Sequence[Sequence[str]], require_all: bool) -> list[int]:
        """A product matches a group if it contains any term of that group.

        require_all=True: products matching every group; False: matching at least one.
        """
        group_matches = [set(self.match_any(group)) for group in groups]
        if not group_matches:
            return []
        if not require_all:
            return sorted(set().union(*group_matches))
        group_matches.sort(key=len)  # intersect from the smallest set
        result = group_matches[0]
        for other in group_matches[1:]:
            result &= other
            if not result:
                break
        return sorted(result)

    # ---- Ranking ----

    def rank(self, terms: Iterable[str], require_all: bool = True) -> list[ScoredDocument]:
        """Matching products sorted by BM25 score (highest first, ties by lower id)."""
        terms = list(dict.fromkeys(terms))  # a repeated query word counts once
        return self.rank_groups([[term] for term in terms], require_all)

    def rank_groups(
        self, groups: Sequence[Sequence[str]], require_all: bool = True
    ) -> list[ScoredDocument]:
        """Rank products for a query made of term groups.

        Each group stands for one query word. A complete word is a group of one term; a
        partial word expanded by the Trie is a group of its completions:

            "wireless ear"  ->  [["wireless"], ["earbud", "early", "ear"]]

        A group contributes the BEST BM25 score among its terms that the product
        contains (one query word counts once). The product's score is the sum over
        groups, so for single-term groups this is exactly standard BM25.
        """
        candidates = self._match_groups(groups, require_all)
        if not candidates:
            return []

        norms = self._compute_length_norms()
        k1 = self.config.k1
        n = self.document_count

        # Step 1: for each group, walk each term's posting list once and keep, per
        # product, the best term score within the group. (Walking the postings is much
        # cheaper than checking every term for every candidate when a prefix expands to
        # many words.)
        group_best: list[dict[int, float]] = []
        for group in groups:
            best: dict[int, float] = {}
            for term in group:
                postings = self._postings.get(term)
                if not postings:
                    continue
                idf_value = bm25.idf(len(postings), n)  # once per term, not per product
                for doc_id, tf in postings.items():
                    score = bm25.term_score(tf, idf_value, norms[doc_id], k1)
                    if score > best.get(doc_id, 0.0):
                        best[doc_id] = score
            group_best.append(best)

        # Step 2: a product's score is the sum of its best score in each group, added in
        # the fixed query order so the result is deterministic.
        scored = []
        for doc_id in candidates:
            score = 0.0
            for best in group_best:
                score += best.get(doc_id, 0.0)
            scored.append(ScoredDocument(doc_id, score))

        scored.sort(key=lambda d: (-round(d.score, SCORE_DECIMALS), d.id))
        return scored

    # ---- Prefix search (Trie) ----

    @property
    def vocabulary_trie(self) -> Trie:
        """Trie of every indexed term, with each term's document frequency."""
        return self._build_trie()

    def _build_trie(self) -> Trie:
        if self._trie is None:
            trie = Trie()  # fully built before it is stored: never visible half-built
            for term, postings in self._postings.items():
                trie.insert(term, frequency=len(postings))
            self._trie = trie
        return self._trie

    # ---- Display forms (autocomplete presentation only) ----

    def _build_display_forms(self) -> dict[str, str]:
        if self._display_forms is None:
            # Most common written form; ties -> alphabetical, so the choice is deterministic.
            best: dict[str, tuple[int, str]] = {}
            for (term, surface), count in self._surface_counts.items():
                current = best.get(term)
                if current is None or (-count, surface) < (-current[0], current[1]):
                    best[term] = (count, surface)
            self._display_forms = {term: surface for term, (_, surface) in best.items()}
        return self._display_forms

    def display_form(self, term: str) -> str:
        """How ``term`` is most often written in the products ("earbud" -> "earbuds").

        Only for showing suggestions; searching the display form finds the same products,
        because it goes through the same text processing back to ``term``.
        """
        return self._build_display_forms().get(term, term)

    # ---- Product metadata (filtering and sorting) ----

    def metadata(self, doc_id: int) -> ProductMeta | None:
        return self._meta.get(doc_id)

    def complete_prefix(self, prefix: str, limit: int = DEFAULT_MAX_EXPANSIONS) -> list[str]:
        """Indexed terms starting with ``prefix``: most products first, then A-Z.

        Also tries the prefix's singular form ("laptops" -> "laptop"), because index
        terms are stored in singular form.
        """
        trie = self.vocabulary_trie
        candidates: set[str] = set()
        for variant in prefix_variants(prefix):
            candidates.update(trie.words_with_prefix(variant, limit=limit))
        ordered = sorted(candidates, key=lambda term: (-trie.frequency(term), term))
        return ordered[:limit]

    def _compute_length_norms(self) -> dict[int, float]:
        """Precompute k1 * (1 - b + b * |d| / avgdl) for every product."""
        if self._length_norms is None:
            avgdl = self.average_document_length
            k1, b = self.config.k1, self.config.b
            self._length_norms = {
                doc_id: bm25.length_norm(length, avgdl, k1, b)
                for doc_id, length in self._doc_lengths.items()
            }
        return self._length_norms

    # ---- Statistics ----

    def term_frequency(self, term: str, doc_id: int) -> float:
        """Field-weighted number of occurrences of ``term`` in product ``doc_id``."""
        return self._postings.get(term, {}).get(doc_id, 0.0)

    def document_frequency(self, term: str) -> int:
        """Number of products containing ``term``."""
        return len(self._postings.get(term, ()))

    def document_length(self, doc_id: int) -> float:
        """Field-weighted number of terms in product ``doc_id``."""
        return self._doc_lengths[doc_id]

    @property
    def document_count(self) -> int:
        return len(self._doc_lengths)

    @property
    def average_document_length(self) -> float:
        return self._total_length / self.document_count if self.document_count else 0.0

    @property
    def vocabulary_size(self) -> int:
        return len(self._postings)

    def stats(self) -> IndexStats:
        return IndexStats(
            build_id=self.build_id,
            documents=self.document_count,
            terms=self.vocabulary_size,
            postings=sum(len(ids) for ids in self._postings.values()),
            average_document_length=round(self.average_document_length, 4),
            trie_nodes=self.vocabulary_trie.node_count,
            build_seconds=round(self._build_seconds, 4),
        )

    def most_common_terms(self, n: int = 10) -> list[tuple[str, int]]:
        """Terms appearing in the most products (document frequency)."""
        counts = Counter({term: len(ids) for term, ids in self._postings.items()})
        return counts.most_common(n)
