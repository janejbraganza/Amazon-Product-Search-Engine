"""Generate a reproducible synthetic product catalogue as CSV.

Usage (from backend/):
    python -m scripts.generate_products                      # 10,000 products, seed 42
    python -m scripts.generate_products --count 500 --seed 7 --output ../data/sample.csv

Products are assembled from the curated vocabulary in ``catalog_data.py`` rather than
random text, so names and descriptions contain real, searchable words. All randomness
comes from a single ``random.Random(seed)`` instance, so the same seed always produces
the same file. ``created_at`` is relative to a fixed reference date (not "now") for the
same reason.
"""

import argparse
import csv
import math
import random
from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.core.config import DATA_DIR
from scripts.catalog_data import CATALOG

DEFAULT_COUNT = 10_000
DEFAULT_SEED = 42
DEFAULT_OUTPUT = DATA_DIR / "products.csv"
REFERENCE_DATE = datetime(2026, 10, 31, tzinfo=UTC)
CREATED_WITHIN_DAYS = 730  # products were "listed" over the two years before REFERENCE_DATE
MAX_ATTEMPTS_PER_TYPE = 25

FIELDNAMES = [
    "id",
    "product_name",
    "description",
    "category",
    "brand",
    "price",
    "rating",
    "review_count",
    "stock_quantity",
    "created_at",
]


def name_capacity(category: dict, spec: dict) -> int:
    """Number of distinct product names a product type can produce."""
    total = len(category["brands"]) if "{brand}" in spec.get("template", "{brand}") else 1
    if "{line}" in spec.get("template", "{line}") and category["lines"]:
        total *= len(category["lines"])
    for words in spec.get("parts", {}).values():
        total *= len(words)
    for group in spec["specs"]:
        total *= len(group)
    return total


def _price(rng: random.Random, low: float, high: float) -> Decimal:
    # Triangular distribution skewed towards the cheaper end, like real catalogues.
    value = rng.triangular(low, high, low + (high - low) * 0.25)
    cents = rng.choice(["99", "99", "49", "95"])
    return Decimal(f"{math.floor(value)}.{cents}")


def _rating(rng: random.Random) -> Decimal:
    # Beta(7, 2) scaled to 1-5: mean about 4.1 with a tail of poorly rated products.
    return Decimal(f"{1 + 4 * rng.betavariate(7, 2):.1f}")


def _review_count(rng: random.Random) -> int:
    # Log-normal: most products have tens of reviews, a few best-sellers have thousands.
    return max(1, min(60_000, int(rng.lognormvariate(3.5, 1.6))))


def _stock(rng: random.Random) -> int:
    if rng.random() < 0.05:  # about 5% out of stock
        return 0
    return max(1, min(1_000, int(rng.lognormvariate(3.8, 1.0))))


def _created_at(rng: random.Random) -> datetime:
    return REFERENCE_DATE - timedelta(seconds=rng.randrange(CREATED_WITHIN_DAYS * 86_400))


def _build_text(rng: random.Random, category: dict, spec: dict) -> tuple[str, str, str]:
    """Return (product_name, description, brand) for one product of the given type."""
    brand = rng.choice(category["brands"])
    words = {
        "brand": brand,
        "line": rng.choice(category["lines"]) if category["lines"] else "",
        "name": spec["name"],
        **{key: rng.choice(options) for key, options in spec.get("parts", {}).items()},
    }
    chosen_specs = [rng.choice(group) for group in spec["specs"]]

    name = spec.get("template", "{brand} {line} {name}").format(**words)
    if chosen_specs:
        name += ", " + ", ".join(chosen_specs)

    subject = spec.get("subject", "The {brand} {line} {name}").format(**words)
    first, second, third = rng.sample(spec["features"], 3)
    sentences = [
        f"{subject} {first}.",
        f"It {second} and {third}.",
        f"Ideal for {rng.choice(spec['uses'])}.",
    ]
    if chosen_specs:
        sentences.append(f"{spec.get('spec_label', 'Specifications')}: {', '.join(chosen_specs)}.")
    sentences.append(rng.choice(category["closers"]))
    return name, " ".join(sentences), brand


def generate_products(count: int = DEFAULT_COUNT, seed: int = DEFAULT_SEED) -> list[dict]:
    """Generate ``count`` products with unique IDs (1..count) and unique names."""
    if count < 1:
        raise ValueError("count must be at least 1")

    rng = random.Random(seed)
    categories = list(CATALOG)
    weights = [CATALOG[c]["weight"] for c in categories]
    seen_names: set[str] = set()
    products: list[dict] = []
    total_attempts = 0

    while len(products) < count:
        category_name = rng.choices(categories, weights=weights)[0]
        category = CATALOG[category_name]
        spec = rng.choice(category["types"])

        for _ in range(MAX_ATTEMPTS_PER_TYPE):
            total_attempts += 1
            name, description, brand = _build_text(rng, category, spec)
            if name not in seen_names:
                break
        else:
            # This product type is (nearly) exhausted; pick another category/type.
            if total_attempts > count * MAX_ATTEMPTS_PER_TYPE:
                raise RuntimeError("Catalogue vocabulary too small for the requested count")
            continue

        seen_names.add(name)
        products.append(
            {
                "id": len(products) + 1,
                "product_name": name,
                "description": description,
                "category": category_name,
                "brand": brand,
                "price": _price(rng, *spec["price"]),
                "rating": _rating(rng),
                "review_count": _review_count(rng),
                "stock_quantity": _stock(rng),
                "created_at": _created_at(rng),
            }
        )
    return products


def write_csv(products: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for product in products:
            writer.writerow({**product, "created_at": product["created_at"].isoformat()})


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic product catalogue CSV.")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    products = generate_products(args.count, args.seed)
    write_csv(products, args.output)

    print(f"Wrote {len(products):,} products to {args.output.resolve()} (seed={args.seed})")
    for category, n in sorted(Counter(p["category"] for p in products).items()):
        print(f"  {category:<25} {n:>6,}")


if __name__ == "__main__":
    main()
