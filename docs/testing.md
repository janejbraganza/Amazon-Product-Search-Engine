# Testing

Four kinds of checks, from fastest to most realistic:

| Kind | What runs | Needs |
|------|-----------|-------|
| **Backend tests** (pytest) | Algorithms, API routes, cache, loader, seed — against a separate test database | PostgreSQL (`docker compose up -d`); Redis optional |
| **Frontend unit/component tests** (Vitest + Testing Library + MSW) | Components and pages in jsdom with a mocked API | Nothing else |
| **Frontend live tests** (Vitest, `*.live.test.jsx`) | Real pages in jsdom with **real** `fetch()` calls to the real backend through the Vite proxy or nginx | Running backend + Vite (or the Docker stack) |
| **Real-browser checks** | Headless Microsoft Edge driven through the Chrome DevTools Protocol | Running app (not part of CI) |

Latest results (Stage 9): **449 backend tests passed** (99% statement coverage of `app/`),
**320 frontend tests passed**, **31 live tests passed**, 12/12 real-browser checks passed.
Ruff, ESLint and Prettier report no problems.

## Backend

```powershell
docker compose up -d                       # PostgreSQL (and Redis) for the tests
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest                            # all tests
python -m pytest --cov=app                  # with coverage
python -m ruff check . ; python -m ruff format --check .
```

Database tests use a **separate database**, `product_search_test`, created automatically; the
real catalogue is never touched. Override it with `TEST_DATABASE_URL`. The `client` fixture
turns the search cache off by default, so tests don't depend on Redis.

| File | Covers |
|------|--------|
| `test_health.py` | `/health` |
| `test_database.py` | Connection, table columns/types/indexes, CHECK constraints |
| `test_generator.py` | Same seed → same output, unique IDs and names, valid fields, CSV round trip |
| `test_loader.py` | Insertion, re-load and partial-overlap duplicates, ID sequence, bad-CSV errors |
| `test_seed_and_startup.py` | Idempotent seed (empty, complete and partial databases; existing rows untouched), index warm-up on/off and failure handling |
| `test_products_api.py` | Listing, pagination, empty results, 404 and 422 |
| `test_text_processing.py` | Lowercasing, punctuation, hyphens, decimals, possessives, stop words, plurals, Unicode, prefix parsing |
| `test_inverted_index.py` | Postings, all/any matching, BM25 statistics, ranking against the formula, tie-breaking, prefix groups, rebuild |
| `test_bm25.py` | IDF and scores against hand-calculated values, IDF never negative, saturation, length normalisation |
| `test_trie.py` | Insert/lookup, shared nodes, ordering and limits, 50,000 random words checked against a full scan |
| `test_autocomplete_api.py` | `/search/suggestions`: order, no duplicates, limit, plural fallback, stop-word prefixes, 422s, rebuild adds words |
| `test_search_api.py` | Search results equal a full scan, scores descending with ties by ID, pagination after ranking, 422s, lazy build, rebuild, rebuild disabled in production |
| `test_filters.py` | Filters, sorting with ID tie-breaks, disjunctive facets, heap-based partial sort equals a full sort, per-product metadata and suggestion display forms, rebuilds never mixing snapshots |
| `test_search_filters_api.py` | Filters, sorting and facets through the API (case-insensitive and repeated values, inclusive bounds, pagination after filtering and sorting, 422s), suggestion display forms, `/categories` |
| `test_search_cache.py` | Cache-aside with in-memory fakes: miss→hit, key contents, TTL, versioned invalidation, rebuild race, never-cached cases, Redis failures and cooldown, credential redaction |
| `test_redis_integration.py` | **Optional**, real Redis on database 15 with a unique key prefix; skipped when Redis isn't reachable. Never `FLUSHDB`/`FLUSHALL` |

## Frontend

```powershell
cd frontend
npm run lint            # ESLint
npm run format:check    # Prettier
npm test                # unit + component tests (MSW mocks the API)
npm run test:coverage   # the same, with coverage (text + HTML in coverage/)
npm run build           # production build
```

The unit/component suite covers the API client (timeouts, cancellation, user-safe errors),
URL search state, autocomplete (keyboard, debouncing, stale responses), the search page
(loading/empty/error states, pagination, no duplicate or stale requests), filters (sidebar,
price validation, chips, URL state, Back/Forward, mobile drawer), the home and product pages
(loading, 404, invalid IDs, API failure, back navigation, similar products), the theme toggle
and its persistence, header navigation, and accessibility checks (heading outline, accessible
names, live-region announcements, keyboard-only drawer use).

### Live tests (real backend)

```powershell
# terminal 1: docker compose up -d, then the backend on 127.0.0.1:8000
# terminal 2: cd frontend; npm run dev
cd frontend
npm run test:live                                   # through the Vite proxy (localhost:5173)
$env:LIVE_BASE_URL = "http://localhost:8080"; npm run test:live   # against the Docker stack
```

These render the real pages and compare what they show with what the real API returns
(search totals and order, facet counts, every sort option, the combined-filter scenario,
product pages, 404s, category links, autocomplete).

## Real-browser verification and screenshots

The screenshots in [`docs/screenshots/`](screenshots/) were captured from the running Docker
build (http://localhost:8080) with **headless Microsoft Edge driven through the Chrome
DevTools Protocol** (a small Node script using only Node's built-in `fetch` and `WebSocket`;
Playwright is not a project dependency). Clicks, typing and key presses were sent as real
browser input events. The script checked:

| Check | Result |
|-------|--------|
| Home page shows real catalogue numbers and all 10 categories | pass |
| Autocomplete suggests `earbud` for "wireless ear"; Enter searches for it | pass |
| Category + brand + price range + sort by price: 26 results, ascending from $620.99 | pass |
| Pagination to page 2 (6 results) | pass |
| Product page, then "Back to results" returns to the same filtered page 2 | pass |
| "Clear all filters" keeps the query and sort | pass |
| Theme toggle switches to dark and the choice survives a reload | pass |
| Dark theme from the operating-system preference | pass |
| Mobile (390 px): home page; filter drawer opens with focus on "Close", applies on "Show results" | pass |
| No horizontal scrolling: 5 pages × 5 widths (320–1440 px) × 2 themes | pass (50/50) |
| No JavaScript errors (the only console messages were the intentional 404 test page) | pass |

This is automated checking in one browser engine (Chromium/Edge). It isn't a substitute for
testing on real phones, Safari or Firefox.

## Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request:

- **backend:** Python 3.13, `requirements-dev.txt`, Ruff (lint + format check), pytest with
  coverage, against PostgreSQL 18 and Redis 8 service containers (a throwaway CI database).
- **frontend:** Node 24, `npm ci`, ESLint, Prettier, Vitest with coverage, production build.
- **docker:** validates the Compose file and builds both images (nothing is pushed or
  deployed).

Benchmarks, live tests and browser checks are not run in CI.
