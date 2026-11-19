"""Load the generated product CSV into PostgreSQL.

Usage (from backend/):
    python -m scripts.load_products                         # loads ../data/products.csv
    python -m scripts.load_products --input path/to/file.csv --batch-size 500

Creates the table first if needed. Re-running is safe: rows whose id already exists
are skipped (INSERT ... ON CONFLICT DO NOTHING).
"""

import argparse
import time
from pathlib import Path

from sqlalchemy import func, select

from app.database.init_db import init_db
from app.database.session import SessionLocal, engine
from app.models.product import Product
from app.services.product_loader import DEFAULT_BATCH_SIZE, load_products, read_products_csv
from scripts.generate_products import DEFAULT_OUTPUT


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Load products from CSV into PostgreSQL.")
    parser.add_argument("--input", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    args = parser.parse_args(argv)

    if not args.input.exists():
        raise SystemExit(
            f"{args.input} not found. Generate it first: python -m scripts.generate_products"
        )

    init_db(engine)
    started = time.perf_counter()
    products = read_products_csv(args.input)
    with SessionLocal() as session:
        result = load_products(session, products, batch_size=args.batch_size)
        total = session.scalar(select(func.count()).select_from(Product))
    elapsed = time.perf_counter() - started

    print(f"Read {len(products):,} products from {args.input.resolve()}")
    print(f"  inserted: {result.inserted:,}")
    print(f"  skipped (already present): {result.skipped:,}")
    print(f"  products now in database: {total:,}  ({elapsed:.2f}s)")


if __name__ == "__main__":
    main()
