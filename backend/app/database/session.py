"""Database engine and session management.

``engine`` holds the connection pool; ``SessionLocal`` creates short-lived sessions.
``get_db`` is a FastAPI dependency that gives each request its own session and
always closes it afterwards.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def build_engine(database_url: str) -> Engine:
    return create_engine(
        database_url,
        pool_pre_ping=True,  # transparently replace connections dropped by the server
        connect_args={"connect_timeout": 5},  # fail fast if PostgreSQL is not running
    )


engine = build_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
