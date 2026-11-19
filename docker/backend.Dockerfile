# syntax=docker/dockerfile:1
# FastAPI backend (also used by the one-shot "seed" service).
# Build context: the repository root (see docker-compose.yml); only the files allowed by
# docker/backend.Dockerfile.dockerignore are sent to the build.

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_ENV=production

WORKDIR /app

# Runtime dependencies only (pytest, ruff etc. are in requirements-dev.txt).
# psycopg[binary] ships its own libpq, so no system packages are needed.
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

# Unprivileged user that owns nothing it does not need to write.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

COPY backend/app ./app
COPY backend/scripts ./scripts

USER app
EXPOSE 8000

# /health answers without touching the database. Python is used because the slim image
# has no curl or wget.
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"]

# One worker: the search index lives in process memory, and each worker would build and
# hold its own copy. The API is fast enough that one worker serves this demo comfortably.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-server-header"]
