"""Text processing shared by indexing and querying.

The same pipeline runs on product text and on search queries, so a query word always
matches the form stored in the index:

    "Men's Running-Shoes, 15.6-inch!"
      1. normalize      -> "men running-shoes, 15.6-inch!"        (Unicode NFKC, casefold, 's)
      2. tokenize       -> men, running, shoes, runningshoes, 15.6, inch
      3. stop words     -> (removed: "the", "and", "with", ...)
      4. fold plurals   -> men, running, shoe, runningshoe, 15.6, inch

``analyze`` keeps repeated words (useful for future term-frequency ranking);
``unique_terms`` returns each word once (what the inverted index stores).
"""

import re
import unicodedata
from collections.abc import Iterable
from functools import lru_cache

# Deliberately small: only words that carry no product meaning. Words such as "free"
# (sugar free), "up", "all", "no" and single letters ("vitamin c", "usb-c") are kept.
STOP_WORDS: frozenset[str] = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "if", "of", "to", "in", "on", "at", "by",
        "for", "with", "from", "into", "as", "is", "are", "was", "be", "been", "it", "its",
        "this", "that", "these", "those", "than", "then", "so", "such", "has", "have",
        "also", "their", "your", "you", "our", "they", "them", "can", "will", "each",
    }
)  # fmt: skip

# Words ending in "s" that are not plurals (or whose plural rule would mangle them).
_PLURAL_EXCEPTIONS: frozenset[str] = frozenset(
    {"series", "species", "lens", "news", "plus", "always", "towards", "various", "chaos"}
)

# A piece is a decimal number ("15.6") or a run of letters/digits ("16gb", "café").
_PIECE = r"(?:\d+(?:\.\d+)+|[^\W_]+)"
# A chunk is one or more pieces joined by hyphens ("usb-c", "15.6-inch", "wi-fi").
_CHUNK_RE = re.compile(rf"{_PIECE}(?:-{_PIECE})*")
_POSSESSIVE_RE = re.compile(r"(?<=[^\W_])['’]s\b")
_APOSTROPHE_RE = re.compile(r"['’]")


def normalize(text: str) -> str:
    """Unicode-normalise, lowercase and drop possessives/apostrophes."""
    if not text.isascii():  # NFKC is a no-op for ASCII, so skip it in the common case
        text = unicodedata.normalize("NFKC", text)
    text = text.casefold()
    text = _POSSESSIVE_RE.sub("", text)  # "men's" -> "men"
    return _APOSTROPHE_RE.sub("", text)  # "kids'" -> "kids", "don't" -> "dont"


def tokenize(text: str) -> list[str]:
    """Split normalised text into word tokens; punctuation is discarded.

    Hyphenated words yield their parts plus a joined form when every part contains a
    letter, so "wi-fi", "wi fi" and "wifi" can all match: "wi-fi" -> wi, fi, wifi.
    """
    tokens: list[str] = []
    for chunk in _CHUNK_RE.findall(normalize(text)):
        parts = chunk.split("-")
        tokens.extend(parts)
        if len(parts) > 1 and all(any(ch.isalpha() for ch in part) for part in parts):
            tokens.append("".join(parts))
    return tokens


@lru_cache(maxsize=65_536)  # vocabulary is small, so most calls are cache hits
def fold_plural(token: str) -> str:
    """Reduce simple English plurals to their singular form ("laptops" -> "laptop").

    Intentionally simple (not a full stemmer): applied identically at index and query
    time, so even an imperfect singular still matches consistently.
    """
    if len(token) <= 3 or not token.isalpha() or token in _PLURAL_EXCEPTIONS:
        return token
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"  # batteries -> battery
    if token.endswith(("sses", "shes", "ches", "xes", "zzes")):
        return token[:-2]  # glasses -> glass, watches -> watch, boxes -> box
    if token.endswith(("ss", "us", "is")):
        return token  # glass, cactus, analysis
    if token.endswith("s"):
        return token[:-1]  # laptops -> laptop, shoes -> shoe
    return token


def analyze(text: str | None) -> list[str]:
    """Full pipeline. Keeps repeated words, in order of appearance."""
    if not text:
        return []
    return [fold_plural(t) for t in tokenize(text) if t not in STOP_WORDS]


def analyze_with_surface(text: str | None) -> list[tuple[str, str]]:
    """Like ``analyze``, but each term is paired with the text it came from.

    The terms are exactly ``analyze(text)`` (same rules, same order); the second value is
    the lowercase word as written ("earbuds" for term "earbud", "usb-c" for "usbc"). Used
    only to show natural display forms in autocomplete; search itself never uses it.
    """
    if not text:
        return []
    pairs: list[tuple[str, str]] = []
    for chunk in _CHUNK_RE.findall(normalize(text)):
        parts = chunk.split("-")
        for part in parts:
            if part not in STOP_WORDS:
                pairs.append((fold_plural(part), part))
        if len(parts) > 1 and all(any(ch.isalpha() for ch in part) for part in parts):
            joined = "".join(parts)
            if joined not in STOP_WORDS:
                pairs.append((fold_plural(joined), chunk))
    return pairs


def unique_terms(texts: Iterable[str | None]) -> set[str]:
    """Distinct terms across several text fields (e.g. name, description, brand)."""
    # One pass over the joined fields; the newline separator keeps words from merging.
    return set(analyze("\n".join(text for text in texts if text)))


def query_terms(query: str) -> list[str]:
    """Distinct query terms, in the order the user typed them."""
    return list(dict.fromkeys(analyze(query)))


def split_prefix_query(query: str) -> tuple[list[str], str | None]:
    """Split a query someone is still typing into (complete terms, partial last word).

    "wireless ear"  -> (["wireless"], "ear")
    "wireless ear " -> (["wireless", "ear"], None)   trailing space = last word finished

    The partial word is only normalised: stop words are kept ("for" may become "fork")
    and plurals are not folded ("ba" is not a word yet).
    """
    tokens = tokenize(query)
    if not tokens or query[-1:].isspace():
        return query_terms(query), None
    *complete, partial = tokens
    terms = [fold_plural(t) for t in complete if t not in STOP_WORDS]
    return list(dict.fromkeys(terms)), partial


def prefix_variants(prefix: str) -> list[str]:
    """The prefix itself, plus its singular form if it looks like a finished plural.

    Index terms are stored in singular form, so "laptops" would otherwise match nothing.
    """
    folded = fold_plural(prefix)
    return [prefix] if folded == prefix else [prefix, folded]
