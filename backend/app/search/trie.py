"""A Trie (prefix tree) for finding all words that start with a given prefix.

Each node represents one character; the path from the root to a node spells a prefix.
Nodes that end a complete word are marked ``is_word``. Words sharing a prefix share
nodes, e.g. "lap", "laptop" and "lamp":

    (root)
      └─ l
          └─ a
              ├─ p *            * = end of a word ("lap")
              │   └─ t
              │       └─ o
              │           └─ p *        ("laptop")
              └─ m
                  └─ p *                ("lamp")

Finding words for a prefix = walk down one node per character (O(p)), then collect every
word below that node. Each word also stores a ``frequency`` (for search terms: how many
products contain it), used to show the most useful suggestions first.
"""

import heapq


class TrieNode:
    # __slots__ stops Python from giving every node its own attribute dict, which
    # keeps thousands of small nodes compact.
    __slots__ = ("children", "is_word", "frequency")

    def __init__(self) -> None:
        self.children: dict[str, TrieNode] = {}  # only the characters actually used
        self.is_word = False
        self.frequency = 0


class Trie:
    def __init__(self) -> None:
        self._root = TrieNode()
        self._word_count = 0
        self._node_count = 1  # the root

    def insert(self, word: str, frequency: int = 1) -> None:
        """Add ``word``. Inserting an existing word keeps one copy and adds the frequency."""
        _check_text(word)
        if not word:
            raise ValueError("Cannot insert an empty word")
        if frequency < 0:
            raise ValueError("frequency must be >= 0")

        node = self._root
        for char in word:
            child = node.children.get(char)
            if child is None:
                child = TrieNode()
                node.children[char] = child
                self._node_count += 1
            node = child
        if not node.is_word:
            node.is_word = True
            self._word_count += 1
        node.frequency += frequency

    def contains(self, word: str) -> bool:
        """True if ``word`` was inserted as a complete word."""
        node = self._find_node(word)
        return node is not None and node.is_word

    def frequency(self, word: str) -> int:
        node = self._find_node(word)
        return node.frequency if node is not None and node.is_word else 0

    def has_prefix(self, prefix: str) -> bool:
        """True if at least one word starts with ``prefix``."""
        _check_text(prefix)
        return bool(prefix) and self._find_node(prefix) is not None

    def words_with_prefix(self, prefix: str, limit: int | None = None) -> list[str]:
        """Words starting with ``prefix``: most frequent first, then alphabetical.

        An empty prefix returns [] (rather than the whole vocabulary).
        """
        _check_text(prefix)
        if limit is not None and limit < 0:
            raise ValueError("limit must be >= 0")
        if not prefix or limit == 0:
            return []
        node = self._find_node(prefix)
        if node is None:
            return []

        matches = self._collect(node, prefix)  # [(frequency, word), ...]
        if limit is None or limit >= len(matches):
            ranked = sorted(matches, key=_most_frequent_first)
        else:  # top-k without sorting everything
            ranked = heapq.nsmallest(limit, matches, key=_most_frequent_first)
        return [word for _, word in ranked]

    def __len__(self) -> int:
        return self._word_count

    def __contains__(self, word: str) -> bool:
        return self.contains(word)

    @property
    def node_count(self) -> int:
        return self._node_count

    # ---- Helpers ----

    def _find_node(self, prefix: str) -> TrieNode | None:
        """Walk down one node per character; None if the path does not exist."""
        _check_text(prefix)
        node = self._root
        for char in prefix:
            node = node.children.get(char)
            if node is None:
                return None
        return node

    @staticmethod
    def _collect(start: TrieNode, prefix: str) -> list[tuple[int, str]]:
        """Every (frequency, word) below ``start``, using an explicit stack (no recursion)."""
        found: list[tuple[int, str]] = []
        stack = [(start, prefix)]
        while stack:
            node, word = stack.pop()
            if node.is_word:
                found.append((node.frequency, word))
            for char, child in node.children.items():
                stack.append((child, word + char))
        return found


def _most_frequent_first(item: tuple[int, str]) -> tuple[int, str]:
    """Sort key: higher frequency first, then alphabetical (deterministic)."""
    frequency, word = item
    return (-frequency, word)


def _check_text(value: object) -> None:
    if not isinstance(value, str):
        raise TypeError(f"Expected a string, got {type(value).__name__}")
