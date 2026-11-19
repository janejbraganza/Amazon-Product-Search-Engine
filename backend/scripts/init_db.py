"""Create the database tables (safe to run repeatedly).

Usage (from backend/):  python -m scripts.init_db
Connection details come from DATABASE_URL in backend/.env.
"""

from sqlalchemy import inspect

from app.database.init_db import init_db
from app.database.session import engine


def main() -> None:
    tables = init_db(engine)
    existing = set(inspect(engine).get_table_names())
    for table in tables:
        print(f"  {table:<20} {'ready' if table in existing else 'MISSING'}")
    print(f"Database '{engine.url.database}' initialised.")


if __name__ == "__main__":
    main()
