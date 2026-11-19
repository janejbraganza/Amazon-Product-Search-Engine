# API reference

FastAPI backend, JSON over HTTP. All paths are relative to the app's origin:

- local development: `http://127.0.0.1:8000` (interactive docs at `/docs`), or through the
  Vite dev server at `http://localhost:5173`;
- Docker: `http://localhost:8080` (nginx forwards `/api/` and `/health`; `/docs` is
  deliberately not exposed).

Examples below are real responses from the 10,000-product catalogue, shortened with `"..."`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness check → `{"status": "ok"}` |
| GET | `/api/v1/products` | Catalogue listing, ordered by ID (`limit` 1–100, default 20; `offset` ≥ 0) |
| GET | `/api/v1/products/{product_id}` | One product; 404 if it doesn't exist |
| GET | `/api/v1/categories` | Every category with its product count |
| GET | `/api/v1/search` | BM25-ranked search with filters, sorting, facets and pagination; Redis-cached |
| GET | `/api/v1/search/suggestions` | Autocomplete: completions of the last word (Trie) |
| POST | `/api/v1/search/rebuild-index` | Rebuild the in-memory search index. **Returns 404 when `APP_ENV=production`** (as in Docker) |

## `GET /api/v1/search`

| Parameter | Default | Rules |
|-----------|---------|-------|
| `q` | required | 1–200 characters; must contain at least one searchable word |
| `mode` | `all` | `all` (every word) or `any` (at least one word) |
| `prefix` | `false` | `true`: the last word is a prefix (`lap` → `laptop`). The web app sends `true` unless "Exact words only" is ticked |
| `sort` | `relevance` | `relevance`, `price_asc`, `price_desc`, `rating`, `newest` |
| `category` | – | Repeatable (`?category=A&category=B`), case-insensitive, max 20 values |
| `brand` | – | Repeatable, case-insensitive, max 20 values |
| `min_price`, `max_price` | – | 0 – 99,999,999.99, up to 2 decimals, inclusive; `min_price > max_price` → 422 |
| `min_rating` | – | 0–5, 1 decimal, inclusive |
| `in_stock` | `false` | `true`: only products in stock |
| `limit` | 20 | 1–100 |
| `offset` | 0 | ≥ 0 |

Response header `X-Cache`: `HIT`, `MISS` or `BYPASS` (see
[search-engine.md](search-engine.md#search-result-cache-redis)).

```http
GET /api/v1/search?q=laptop&prefix=true&category=Electronics&brand=Kestrel+Labs&min_price=500&max_price=2000&sort=price_asc&limit=2
```

```json
{
  "query": "laptop", "terms": [], "unmatched_terms": [], "mode": "all",
  "total": 26, "limit": 2, "offset": 0,
  "items": [
    { "id": 6085, "product_name": "Kestrel Labs Nova Laptop, 15.6-inch, 8GB RAM, 256GB SSD",
      "price": 620.99, "rating": 4.4, "score": 6.060103, "...": "..." },
    { "id": 5340, "product_name": "Kestrel Labs Max Laptop, 13-inch, 32GB RAM, 512GB SSD",
      "price": 628.99, "rating": 4.2, "score": 6.197218, "...": "..." }
  ],
  "prefix": "laptop", "expanded_terms": ["laptop"],
  "sort": "price_asc",
  "facets": {
    "categories": [ { "value": "Electronics", "count": 26 } ],
    "brands": [ { "value": "Kestrel Labs", "count": 26 }, { "value": "Pulsewave", "count": 24 }, "..." ]
  }
}
```

| Field | Meaning |
|-------|---------|
| `terms` | The complete query words after normalisation (here empty: the only word is the partial one) |
| `prefix`, `expanded_terms` | The partial word and its Trie completions (prefix search only) |
| `unmatched_terms` | Words that match no product (`"xyz*"` for a prefix with no completions) |
| `total` | Matches **after** filters |
| `items[].score` | BM25 score (kept even when sorting by price) |
| `facets` | Category/brand counts over all matches; each facet ignores its own filter |

Examples of edge cases:

```http
GET /api/v1/search?q=LAPTOPS                        -> terms ["laptop"], total 220 (case and plural ignored)
GET /api/v1/search?q=wi-fi                          -> terms ["wi", "fi", "wifi"], total 181
GET /api/v1/search?q=voltrix%20zzzz                 -> total 0 (mode=all: every word must match)
GET /api/v1/search?q=voltrix%20zzzz&mode=any        -> total 160, "unmatched_terms": ["zzzz"]
GET /api/v1/search?q=lap                            -> total 0 (whole words only without prefix=true)
GET /api/v1/search?q=the                            -> 422 {"detail": "Query contains no searchable words"}
GET /api/v1/search?q=laptop&min_price=900&max_price=100 -> 422 (min_price greater than max_price)
```

## `GET /api/v1/search/suggestions`

| Parameter | Default | Rules |
|-----------|---------|-------|
| `q` | required | 1–200 characters; the **last word** is completed |
| `limit` | 10 | 1–50 |

```json
{ "query": "wireless ear", "prefix": "ear",
  "suggestions": [ { "term": "earbud", "product_count": 231, "display": "earbuds" },
                   { "term": "early",  "product_count": 145, "display": "early" },
                   { "term": "ear",    "product_count": 96,  "display": "ear" } ] }
```

Ordered by product count, then A–Z. `term` is the index term; `display` is how it is most
often written in product text. `q=!!!` → 422 (no searchable characters).

## `GET /api/v1/categories`

```json
{ "categories": [ { "name": "Electronics", "product_count": 1567 },
                  { "name": "Home & Kitchen", "product_count": 1427 }, "..." ],
  "total_products": 10000 }
```

Read from PostgreSQL; ordered by product count (highest first), then by name.

## `GET /api/v1/products` and `GET /api/v1/products/{product_id}`

```http
GET /api/v1/products/42
```

```json
{
  "id": 42,
  "product_name": "Brightnest Artisan Air Fryer, 8-Quart, Stainless Steel",
  "description": "The Brightnest Artisan Air Fryer features a digital touchscreen and adjustable temperature control. ...",
  "category": "Home & Kitchen",
  "brand": "Brightnest",
  "price": 123.49,
  "rating": 3.7,
  "review_count": 192,
  "stock_quantity": 14,
  "created_at": "2025-05-28T05:13:52Z"
}
```

The listing returns `{"items": [...], "total": 10000, "limit": 20, "offset": 0}`; an `offset`
past the end returns `"items": []`. `price` and `rating` are stored as exact `NUMERIC` values
and returned as JSON numbers.

## `POST /api/v1/search/rebuild-index`

Rebuilds postings, BM25 statistics, filter metadata and the Trie from PostgreSQL and swaps the
new index in atomically. Disabled (404) when `APP_ENV=production`, because the API has no
authentication.

```json
{ "build_id": "3f9c2b…", "documents": 10000, "terms": 1733, "postings": 366584,
  "average_document_length": 66.0923, "trie_nodes": 5971, "build_seconds": 1.6542 }
```

## Errors

| Situation | Status | Body |
|-----------|--------|------|
| Product doesn't exist (`/api/v1/products/99999999`) | 404 | `{"detail": "Product 99999999 not found"}` |
| ID isn't a whole number ≥ 1 (`abc`, `0`, `1.5`) | 422 | FastAPI validation error listing the field |
| Parameter out of range (`limit=0`, `min_rating=6`, `q` too long) | 422 | FastAPI validation error listing the field |
| Blank query / no searchable words | 422 | `{"detail": "Query must not be blank"}` / `{"detail": "Query contains no searchable words"}` |

The frontend never shows raw server errors: its API client turns every failure into a short,
user-safe message.
