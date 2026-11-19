"""Shared pytest fixtures.

Database tests run against a separate database (default: "<DATABASE_URL db>_test"), so
they never touch the real catalogue. It is created automatically if missing, and the
products table is emptied before every test.
"""

import re
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import make_url, text
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.cache.search_cache import SearchCache, get_search_cache
from app.core.config import get_settings
from app.database.base import Base
from app.database.init_db import init_db
from app.database.session import build_engine, get_db
from app.main import app
from app.schemas.product import ProductCreate
from scripts.generate_products import generate_products


def _test_database_url() -> URL:
    settings = get_settings()
    main_url = make_url(settings.database_url)
    if settings.test_database_url:
        url = make_url(settings.test_database_url)
    else:
        url = main_url.set(database=f"{main_url.database}_test")
    if url.database == main_url.database:
        raise RuntimeError("The test database must differ from the main database.")
    if not re.fullmatch(r"[A-Za-z0-9_]+", url.database or ""):
        raise RuntimeError(f"Unsupported test database name: {url.database!r}")
    return url


def _ensure_database_exists(url: URL) -> None:
    admin = build_engine(url.set(database="postgres")).execution_options(
        isolation_level="AUTOCOMMIT"
    )
    try:
        with admin.connect() as conn:
            exists = conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
            )
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        admin.dispose()


@pytest.fixture(scope="session")
def test_engine() -> Iterator[Engine]:
    url = _test_database_url()
    try:
        _ensure_database_exists(url)
    except OperationalError as exc:
        pytest.fail(
            "Cannot connect to PostgreSQL. Start it with `docker compose up -d` "
            f"from the project root. ({exc.orig.__class__.__name__})",
            pytrace=False,
        )
    engine = build_engine(url)
    Base.metadata.drop_all(engine)  # start each test run from the current schema
    init_db(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine: Engine) -> Iterator[Session]:
    with test_engine.begin() as conn:
        conn.execute(text("TRUNCATE products RESTART IDENTITY"))
    session = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db_session
    # Search caching is off unless a test opts in (tests/test_search_cache.py), so the
    # suite never depends on, or writes to, a real Redis server.
    app.dependency_overrides.setdefault(get_search_cache, lambda: SearchCache(client=None))
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_search_cache, None)


@pytest.fixture
def sample_products() -> list[ProductCreate]:
    """50 small, valid, reproducible products."""
    return [ProductCreate.model_validate(p) for p in generate_products(count=50, seed=1)]
