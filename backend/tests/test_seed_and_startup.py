"""Docker start-up helpers: the idempotent seed script and the optional index warm-up."""

import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import app.main as main_module
import scripts.seed as seed
from app.core.config import Settings, get_settings
from app.models.product import Product
from app.search.index_manager import SearchIndexManager
from app.services.product_loader import load_products
from scripts.generate_products import generate_products

SEED_COUNT = 30  # a small catalogue keeps the tests fast; the logic is the same


@pytest.fixture
def seed_db(db_session: Session, test_engine: Engine, monkeypatch) -> Session:
    """Point the seed script at the (emptied) test database with a 30-product catalogue."""
    monkeypatch.setattr(seed, "engine", test_engine)
    monkeypatch.setattr(seed, "SessionLocal", sessionmaker(bind=test_engine))
    monkeypatch.setattr(seed, "DEFAULT_COUNT", SEED_COUNT)
    return db_session


def count(session: Session) -> int:
    session.expire_all()
    return session.scalar(select(func.count()).select_from(Product))


def test_seed_loads_an_empty_database(seed_db: Session, capsys):
    seed.main()
    assert count(seed_db) == SEED_COUNT
    assert f"Inserted {SEED_COUNT}, skipped 0" in capsys.readouterr().out


def test_seed_is_idempotent(seed_db: Session, capsys):
    seed.main()
    seed.main()
    assert count(seed_db) == SEED_COUNT
    assert "already loaded (30 products); nothing to do" in capsys.readouterr().out


def test_seed_fills_gaps_without_touching_existing_rows(seed_db: Session):
    seed.main()
    seed_db.execute(update(Product).where(Product.id == 1).values(price=1.23))
    seed_db.execute(Product.__table__.delete().where(Product.id > 20))
    seed_db.commit()
    assert count(seed_db) == 20

    seed.main()
    assert count(seed_db) == SEED_COUNT
    assert float(seed_db.get(Product, 1).price) == 1.23  # existing data never overwritten


def test_seed_matches_the_published_generator(seed_db: Session):
    """The seeded rows are exactly the generator's seed-42 output (same as products.csv)."""
    seed.main()
    first = seed_db.get(Product, 1)
    expected = generate_products(SEED_COUNT, 42)[0]
    assert first.product_name == expected["product_name"]
    assert first.price == expected["price"]


def test_warm_up_builds_the_index(db_session: Session, sample_products, monkeypatch, caplog):
    load_products(db_session, sample_products)
    manager = SearchIndexManager()
    monkeypatch.setattr("app.search.index_manager.get_index_manager", lambda: manager)
    monkeypatch.setattr(
        "app.database.session.SessionLocal", sessionmaker(bind=db_session.get_bind())
    )
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        main_module.warm_up_search_index()
    assert manager.is_built
    assert "Search index ready: 50 products" in caplog.text


def test_failed_warm_up_is_logged_and_not_fatal(monkeypatch, caplog):
    def broken_session():
        raise RuntimeError("database down")

    manager = SearchIndexManager()
    monkeypatch.setattr("app.search.index_manager.get_index_manager", lambda: manager)
    monkeypatch.setattr("app.database.session.SessionLocal", broken_session)
    main_module.warm_up_search_index()  # must not raise
    assert not manager.is_built
    assert "warm-up failed" in caplog.text


@pytest.mark.parametrize("enabled", [True, False])
def test_lifespan_runs_the_warm_up_only_when_enabled(monkeypatch, enabled):
    calls = []
    settings = get_settings().model_copy(update={"search_index_warmup": enabled})
    monkeypatch.setattr(main_module, "get_settings", lambda: settings)
    monkeypatch.setattr(main_module, "warm_up_search_index", lambda: calls.append(1))
    with TestClient(main_module.app) as client:
        assert client.get("/health").json() == {"status": "ok"}
    assert calls == ([1] if enabled else [])


def test_warm_up_is_off_by_default():
    assert Settings.model_fields["search_index_warmup"].default is False
