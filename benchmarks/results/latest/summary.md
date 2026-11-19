# Benchmark results (latest run)

## Environment

| Item | Value |
|---|---|
| timestamp_utc | 2026-11-13T22:03:18+00:00 |
| os | Windows-11-10.0.26200-SP0 |
| cpu | AMD Ryzen 5 5600H with Radeon Graphics |
| logical_cpus | 12 |
| physical_cpus | 6 |
| ram_gb | 7.3 |
| python | 3.13.15 |
| postgres | postgres (PostgreSQL) 18.7 |
| redis | Redis server v=8.10.3 |
| database | 127.0.0.1:5432/product_search |
| packages | fastapi 0.162.5, uvicorn 0.54.0, starlette 1.10.0, sqlalchemy 2.1.8, psycopg 3.3.9, redis 8.1.0, httpx 0.28.1, pydantic 2.14.3 |
| cache settings | {'search_cache_ttl_seconds': 300, 'redis_timeout_seconds': 0.25, 'redis_retry_cooldown_seconds': 30.0} |
| run settings | 200 measured requests per scenario after 20 warm-up; Redis-down 50; 400 requests per concurrency level |

Columns: mean | p50 | p95 | p99 | min | max (ms) | requests/s (1 client = 1000/mean)

## HTTP client latency - No cache (1 client)

| Scenario | mean | p50 | p95 | p99 | min | max | req/s |
|---|---|---|---|---|---|---|---|
| simple: laptop | 16.03 | 15.41 | 18.40 | 32.28 | 12.81 | 63.26 | 62.4 |
| multi-term (all): wireless bluetooth headphones | 5.36 | 5.34 | 6.41 | 7.28 | 4.35 | 7.89 | 186.6 |
| multi-term (any): wireless bluetooth headphones | 17.35 | 17.42 | 19.50 | 20.07 | 14.68 | 21.35 | 57.6 |
| multi-term (all): wireless earbuds | 18.86 | 17.23 | 28.62 | 36.54 | 13.30 | 37.45 | 53.0 |
| common term: ideal | 62.26 | 57.44 | 124.58 | 161.09 | 41.85 | 216.69 | 16.1 |
| prefix: lap | 15.79 | 15.46 | 18.71 | 20.52 | 13.06 | 24.65 | 63.3 |
| prefix: wireless ear | 16.23 | 16.18 | 18.25 | 19.66 | 13.88 | 21.17 | 61.6 |
| prefix: s | 77.36 | 71.84 | 121.06 | 146.30 | 58.14 | 198.85 | 12.9 |

## HTTP client latency - Cache miss (1 client)

| Scenario | mean | p50 | p95 | p99 | min | max | req/s |
|---|---|---|---|---|---|---|---|
| simple: laptop | 18.83 | 18.63 | 21.48 | 24.06 | 15.89 | 25.00 | 53.1 |
| multi-term (all): wireless bluetooth headphones | 9.38 | 9.37 | 10.96 | 11.34 | 7.88 | 12.21 | 106.6 |
| multi-term (any): wireless bluetooth headphones | 21.59 | 21.16 | 25.02 | 29.57 | 18.13 | 34.18 | 46.3 |
| multi-term (all): wireless earbuds | 21.19 | 20.75 | 25.66 | 30.21 | 17.32 | 31.59 | 47.2 |
| common term: ideal | 67.15 | 61.85 | 126.36 | 154.41 | 46.80 | 177.80 | 14.9 |
| prefix: lap | 21.04 | 20.49 | 27.42 | 30.57 | 16.23 | 38.16 | 47.5 |
| prefix: wireless ear | 21.03 | 20.59 | 24.83 | 28.45 | 17.32 | 38.51 | 47.5 |
| prefix: s | 82.22 | 77.57 | 129.73 | 156.17 | 62.06 | 173.81 | 12.2 |

## HTTP client latency - Cache hit (1 client)

| Scenario | mean | p50 | p95 | p99 | min | max | req/s |
|---|---|---|---|---|---|---|---|
| simple: laptop | 7.96 | 7.92 | 8.97 | 9.55 | 6.68 | 10.08 | 125.6 |
| multi-term (all): wireless bluetooth headphones | 7.46 | 7.34 | 8.59 | 9.96 | 6.18 | 10.07 | 134.1 |
| multi-term (any): wireless bluetooth headphones | 7.49 | 7.12 | 9.71 | 10.59 | 6.31 | 11.42 | 133.6 |
| multi-term (all): wireless earbuds | 8.09 | 8.03 | 9.48 | 10.13 | 6.60 | 10.22 | 123.6 |
| common term: ideal | 8.56 | 8.42 | 10.34 | 10.97 | 6.83 | 14.56 | 116.8 |
| prefix: lap | 8.21 | 8.13 | 9.58 | 10.31 | 6.67 | 11.73 | 121.8 |
| prefix: wireless ear | 8.25 | 8.09 | 9.99 | 11.41 | 6.71 | 13.21 | 121.2 |
| prefix: s | 6.95 | 6.90 | 7.65 | 7.99 | 6.24 | 8.43 | 143.9 |

## HTTP client latency - Redis unavailable (during cooldown) (1 client)

| Scenario | mean | p50 | p95 | p99 | min | max | req/s |
|---|---|---|---|---|---|---|---|
| simple: laptop | 15.08 | 14.73 | 17.77 | 19.00 | 13.27 | 19.12 | 66.3 |
| multi-term (all): wireless bluetooth headphones | 5.14 | 5.14 | 5.77 | 6.24 | 4.16 | 6.53 | 194.4 |
| multi-term (any): wireless bluetooth headphones | 16.64 | 16.50 | 18.63 | 18.95 | 14.75 | 19.07 | 60.1 |
| multi-term (all): wireless earbuds | 15.78 | 15.70 | 17.15 | 18.11 | 13.96 | 18.85 | 63.4 |
| common term: ideal | 60.91 | 56.61 | 98.87 | 136.97 | 43.10 | 141.70 | 16.4 |
| prefix: lap | 15.22 | 14.98 | 17.47 | 17.78 | 12.81 | 17.80 | 65.7 |
| prefix: wireless ear | 16.20 | 16.18 | 18.26 | 19.28 | 13.93 | 19.97 | 61.7 |
| prefix: s | 76.17 | 72.40 | 122.17 | 153.64 | 58.79 | 154.79 | 13.1 |

## HTTP server-side time (Server-Timing) - no cache

| Scenario | mean | p50 | p95 | p99 | min | max | req/s |
|---|---|---|---|---|---|---|---|
| simple: laptop | 13.83 | 13.26 | 15.72 | 29.89 | 10.77 | 60.35 | 72.3 |
| multi-term (all): wireless bluetooth headphones | 3.51 | 3.48 | 4.22 | 4.80 | 2.81 | 4.95 | 284.8 |
| multi-term (any): wireless bluetooth headphones | 15.34 | 15.45 | 17.28 | 17.88 | 12.76 | 18.18 | 65.2 |
| multi-term (all): wireless earbuds | 16.44 | 15.05 | 25.46 | 32.88 | 11.29 | 34.32 | 60.8 |
| common term: ideal | 60.15 | 55.42 | 122.72 | 158.75 | 39.82 | 214.16 | 16.6 |
| prefix: lap | 13.64 | 13.36 | 16.13 | 18.04 | 11.18 | 21.96 | 73.3 |
| prefix: wireless ear | 14.13 | 14.05 | 15.83 | 17.46 | 11.75 | 18.99 | 70.8 |
| prefix: s | 75.35 | 69.73 | 119.15 | 144.14 | 56.13 | 196.74 | 13.3 |

## HTTP server-side time (Server-Timing) - cache hit

| Scenario | mean | p50 | p95 | p99 | min | max | req/s |
|---|---|---|---|---|---|---|---|
| simple: laptop | 5.99 | 5.96 | 6.75 | 7.40 | 4.95 | 7.64 | 167.0 |
| multi-term (all): wireless bluetooth headphones | 5.46 | 5.37 | 6.42 | 7.35 | 4.38 | 7.46 | 183.1 |
| multi-term (any): wireless bluetooth headphones | 5.60 | 5.34 | 7.26 | 7.74 | 4.69 | 7.95 | 178.6 |
| multi-term (all): wireless earbuds | 6.09 | 6.04 | 7.13 | 7.78 | 4.88 | 8.17 | 164.2 |
| common term: ideal | 6.48 | 6.36 | 7.94 | 8.53 | 5.15 | 9.79 | 154.4 |
| prefix: lap | 6.18 | 6.13 | 7.32 | 8.41 | 5.02 | 9.65 | 161.8 |
| prefix: wireless ear | 6.21 | 6.09 | 7.49 | 8.67 | 4.95 | 10.53 | 160.9 |
| prefix: s | 5.22 | 5.19 | 5.70 | 6.04 | 4.68 | 6.14 | 191.7 |

## Other endpoints (client latency, 1 client)

| Scenario | mean | p50 | p95 | p99 | min | max | req/s |
|---|---|---|---|---|---|---|---|
| autocomplete: ear | 3.69 | 3.67 | 4.21 | 4.87 | 3.23 | 5.04 | 271.1 |
| /health (HTTP + framework floor) | 2.30 | 2.28 | 2.62 | 2.86 | 1.93 | 3.21 | 435.5 |

## Redis unavailable - first request (pays the connection timeout)

| Query | client ms | server ms |
|---|---|---|
| simple: laptop | 283.0 | 280.3 |
| multi-term (all): wireless bluetooth headphones | 259.1 | 257.4 |
| multi-term (any): wireless bluetooth headphones | 270.7 | 269.1 |
| multi-term (all): wireless earbuds | 273.0 | 271.2 |
| common term: ideal | 425.0 | 422.6 |
| prefix: lap | 276.9 | 275.0 |
| prefix: wireless ear | 277.7 | 275.9 |
| prefix: s | 319.9 | 318.2 |

## Concurrency (round-robin mix of all queries)

| Cache | Clients | Requests | Errors | Incorrect | req/s | mean | p50 | p95 | p99 | max |
|---|---|---|---|---|---|---|---|---|---|---|
| no cache | 1 | 400 | 0 | 0 | 38.4 | 25.9 | 15.1 | 71.1 | 116.8 | 137.5 |
| no cache | 5 | 400 | 0 | 0 | 49.9 | 100.0 | 92.8 | 193.7 | 224.2 | 235.6 |
| no cache | 10 | 400 | 0 | 0 | 47.5 | 208.2 | 197.0 | 357.2 | 399.2 | 461.4 |
| no cache | 20 | 400 | 0 | 0 | 47.8 | 410.5 | 409.2 | 620.8 | 667.9 | 689.7 |
| cache hit | 1 | 400 | 0 | 0 | 133.6 | 7.3 | 7.2 | 8.3 | 8.8 | 45.6 |
| cache hit | 5 | 400 | 0 | 0 | 233.8 | 21.0 | 20.3 | 29.7 | 38.3 | 45.3 |
| cache hit | 10 | 400 | 0 | 0 | 245.7 | 40.0 | 39.3 | 53.1 | 60.7 | 66.4 |
| cache hit | 20 | 400 | 0 | 0 | 262.9 | 74.4 | 73.7 | 88.6 | 121.3 | 128.9 |

## In-process components (10,000 products)

| Query | matches | matching p50 | ranking total p50 | BM25 scoring (p50 diff) | search_products p50 | build response p50 | JSON p50 |
|---|---|---|---|---|---|---|---|
| simple: laptop | 220 | 0.037 | 0.640 | 0.603 | 4.103 | 0.471 | 0.144 |
| multi-term (all): wireless bluetooth headphones | 0 | 0.178 | 0.095 | 0.000 | 0.185 | 0.008 | 0.006 |
| multi-term (any): wireless bluetooth headphones | 686 | 0.212 | 2.289 | 2.077 | 7.224 | 0.306 | 0.082 |
| multi-term (all): wireless earbuds | 231 | 0.152 | 1.471 | 1.319 | 4.902 | 0.308 | 0.081 |
| common term: ideal | 10000 | 0.758 | 35.045 | 34.287 | 43.617 | 0.358 | 0.139 |
| prefix: lap | 220 | 0.038 | 0.562 | 0.524 | 4.304 | 0.304 | 0.144 |
| prefix: wireless ear | 231 | 0.206 | 1.174 | 0.969 | 5.390 | 0.369 | 0.081 |
| prefix: s | 9769 | 1.788 | 55.661 | 53.873 | 64.386 | 0.298 | 0.109 |

| Autocomplete (Trie) | suggestions | complete_prefix p50 ms |
|---|---|---|
| autocomplete: ear | 3 | 0.0160 |
| autocomplete: lap | 1 | 0.0110 |
| autocomplete: s | 10 | 0.4300 |

| PostgreSQL (10,000 products) | p50 ms |
|---|---|
| stream all products for an index build | 164.1 |
| fetch a 20-product page (reused session) | 3.10 |
| fetch a 20-product page (new session, as per request) | 8.17 |
| open + close a session (connection checkout) | 1.54 |

## Catalogue scaling (in-process, seed 42)

| Products | Terms | Postings | Trie nodes | Index build p50 ms | Trie build p50 ms | Index memory MB |
|---|---|---|---|---|---|---|
| 1,000 | 1,721 | 36,725 | 5,939 | 180 | 6.29 | 3.66 |
| 5,000 | 1,733 | 183,332 | 5,971 | 801 | 8.46 | 12.79 |
| 10,000 | 1,733 | 366,584 | 5,971 | 1645 | 8.56 | 24.42 |

| Query (ranking total p50 ms) | 1,000 | 5,000 | 10,000 |
|---|---|---|---|
| simple: laptop | 0.078 | 0.283 | 0.640 |
| multi-term (all): wireless bluetooth headphones | 0.021 | 0.044 | 0.095 |
| multi-term (any): wireless bluetooth headphones | 0.194 | 1.092 | 2.289 |
| multi-term (all): wireless earbuds | 0.075 | 0.441 | 1.471 |
| common term: ideal | 3.126 | 15.785 | 35.045 |
| prefix: lap | 0.077 | 0.283 | 0.562 |
| prefix: wireless ear | 0.087 | 0.510 | 1.174 |
| prefix: s | 4.094 | 25.476 | 55.661 |

## Server process memory (RSS, psutil)

| Point | MB |
|---|---|
| server started (before index) | 88.6 |
| after first search (index built) | 123.5 |
| end of run | 136.4 |
| first search including index build | 2.341 s |
