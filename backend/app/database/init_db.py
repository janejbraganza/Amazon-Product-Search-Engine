"""Create database tables.

Uses ``Base.metadata.create_all``, which only creates missing tables, so it is safe to
run repeatedly. (Alembic migrations can replace this once the schema starts evolving.)
"""

from sqlalchemy.engine import Engine

import app.models  # noqa: F401  (registers models on Base.metadata)
from app.database.base import Base


def init_db(engine: Engine) -> list[str]:
    """Create all tables that do not exist yet. Returns the table names managed by the app."""
    Base.metadata.create_all(bind=engine)
    return sorted(Base.metadata.tables)
