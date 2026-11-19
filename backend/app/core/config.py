"""Application settings.

Values are read from environment variables, falling back to ``backend/.env``.
Secrets (like the database password) live only in ``.env`` and are never hardcoded here.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ directory, so ".env" is found no matter where the process is started from.
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    database_url: str
    # 127.0.0.1 rather than localhost: on Windows, "localhost" tries IPv6 first and each
    # new connection waits seconds before falling back to IPv4 (where Docker listens).
    redis_url: str = "redis://127.0.0.1:6379/0"
    # Optional: database used by pytest. If unset, "<database>_test" is derived from database_url.
    test_database_url: str | None = None

    # ---- Search index ----
    # Build the search index when the server starts instead of on the first search.
    # Off by default (tests and local development keep the lazy build); Docker turns it on.
    search_index_warmup: bool = False

    # ---- Search result cache (Redis) ----
    search_cache_enabled: bool = True
    search_cache_ttl_seconds: int = Field(default=300, gt=0)
    # Short timeouts: a slow or missing Redis must never make searches slow.
    redis_timeout_seconds: float = Field(default=0.25, gt=0)
    # After a Redis failure, skip Redis for this long instead of timing out on every request.
    redis_retry_cooldown_seconds: float = Field(default=30, ge=0)


@lru_cache
def get_settings() -> Settings:
    """Return the settings object (created once, then cached)."""
    return Settings()
