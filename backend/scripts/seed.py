"""Seed the database with the synthetic product catalogue (safe to run on every start).

Usage (from backend/):  python -m scripts.seed

Used by the one-shot ``seed`` service in docker-compose.yml, before the API starts:
1. creates the tables if they are missing;
2. if the catalogue is already complete, does nothing else;
3. otherwise generates the catalogue (seed 42 - byte-for-byte the same as
   data/products.csv) into a temporary file and loads it. Existing ids are skipped
   (INSERT ... ON CONFLICT DO NOTHING), so nothing is ever duplicated or overwritten.

Existing data is never deleted or changed.
"""

import tempfile
import time
from pathlib import Path

from sqlalchemy import func, select

from app.database.init_db import init_db
from app.database.session import SessionLocal, engine
from app.models.product import Product
from app.services.product_loader import load_products, read_products_csv
from scripts.generate_products import DEFAULT_COUNT, DEFAULT_SEED, generate_products, write_csv


def product_count() -> int:
    with SessionLocal() as session:
        return session.scalar(select(func.count()).select_from(Product)) or 0


def main() -> None:
    init_db(engine)
    before = product_count()
    if before >= DEFAULT_COUNT:
        print(f"Catalogue already loaded ({before:,} products); nothing to do.")
        return

    started = time.perf_counter()
    print(f"Database has {before:,} products; loading the {DEFAULT_COUNT:,}-product catalogue...")
    with tempfile.TemporaryDirectory() as folder:
        csv_path = Path(folder) / "products.csv"
        write_csv(generate_products(DEFAULT_COUNT, DEFAULT_SEED), csv_path)
        products = read_products_csv(csv_path)  # same validation as scripts.load_products
    with SessionLocal() as session:
        result = load_products(session, products)
    print(
        f"Inserted {result.inserted:,}, skipped {result.skipped:,} already present; "
        f"{product_count():,} products in the database ({time.perf_counter() - started:.1f}s)."
    )


if __name__ == "__main__":
    main()
