import { delay as wait, http, HttpResponse } from 'msw'
import { server } from './server.js'

/**
 * Mock GET /api/v1/search/suggestions. ``words`` is the fake vocabulary as
 * {term: product_count}; like the real API it completes the LAST word of q and returns
 * {query, prefix, suggestions}. ``delays`` maps a q to a response delay (ms or 'infinite').
 * Every request is recorded with its q and whether it was later aborted.
 */
export function mockSuggestions({ words = {}, delays = {}, status = 200 } = {}) {
  const requests = []
  server.use(
    http.get('/api/v1/search/suggestions', async ({ request }) => {
      const url = new URL(request.url)
      const q = url.searchParams.get('q')
      const record = { q, limit: url.searchParams.get('limit'), aborted: false }
      request.signal.addEventListener('abort', () => {
        record.aborted = true
      })
      requests.push(record)
      if (delays[q] !== undefined) await wait(delays[q])
      if (status !== 200) return HttpResponse.json({ detail: 'Server error' }, { status })
      const prefix = q.trim().toLowerCase().split(/\s+/).pop()
      const suggestions = Object.entries(words)
        .filter(([term]) => term.startsWith(prefix))
        .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
        .slice(0, Number(url.searchParams.get('limit') ?? 10))
        .map(([term, product_count]) => ({ term, product_count }))
      return HttpResponse.json({ query: q, prefix, suggestions })
    }),
  )
  return requests
}

/** A product in the exact shape of the API's SearchResultItem. */
export function makeProduct(id, overrides = {}) {
  return {
    id,
    product_name: `Voltrix Pro Laptop ${id}, 14-inch`,
    description: `Laptop number ${id} with a bright display.`,
    category: 'Electronics',
    brand: 'Voltrix',
    price: 899.99,
    rating: 4.5,
    review_count: 120,
    stock_quantity: 25,
    created_at: '2026-01-01T00:00:00Z',
    score: 10 - id / 1000,
    ...overrides,
  }
}

/**
 * Mock GET /api/v1/search backed by a fake catalogue of ``total`` products.
 * It paginates with the request's limit/offset like the real API and records every request.
 * Options let a test shape the response (terms, unmatched terms, prefix expansion, X-Cache).
 */
export const DEFAULT_FACETS = {
  categories: [
    { value: 'Electronics', count: 40 },
    { value: 'Home & Kitchen', count: 5 },
  ],
  brands: [
    { value: 'Voltrix', count: 30 },
    { value: 'Nexora', count: 10 },
    { value: 'Kestrel Labs', count: 5 },
  ],
}

/**
 * Mock GET /api/v1/search shaped like the real (Stage 5) response, including ``sort`` and
 * ``facets``. Filtering itself is the backend's job, so the mock does not filter: tests
 * check the parameters the page SENDS (recorded in ``requests``; repeated parameters such
 * as category are also recorded as arrays in ``requests[i].all``).
 */
export function mockSearch({
  total = 45,
  terms = ['laptop'],
  unmatched = [],
  expanded = [],
  cache = 'MISS',
  status = 200,
  errorBody = null,
  facets = DEFAULT_FACETS,
} = {}) {
  const requests = []
  server.use(
    http.get('/api/v1/search', ({ request }) => {
      const params = new URL(request.url).searchParams
      const record = Object.fromEntries(params)
      Object.defineProperty(record, 'all', {
        value: { category: params.getAll('category'), brand: params.getAll('brand') },
        enumerable: false, // keep toEqual on the plain parameters unchanged
      })
      record.search = params.toString()
      Object.defineProperty(record, 'search', { enumerable: false })
      requests.push(record)
      if (status !== 200) return HttpResponse.json(errorBody, { status })
      const limit = Number(params.get('limit') ?? 20)
      const offset = Number(params.get('offset') ?? 0)
      const prefixOn = params.get('prefix') === 'true'
      const items = []
      for (let id = offset + 1; id <= Math.min(offset + limit, total); id++) {
        items.push(makeProduct(id))
      }
      return HttpResponse.json(
        {
          query: params.get('q'),
          terms: prefixOn && expanded.length ? terms.slice(0, -1) : terms,
          unmatched_terms: unmatched,
          mode: params.get('mode') ?? 'all',
          total,
          limit,
          offset,
          items,
          prefix: prefixOn && expanded.length ? terms[terms.length - 1] : null,
          expanded_terms: prefixOn ? expanded : [],
          sort: params.get('sort') ?? 'relevance',
          facets,
        },
        { headers: { 'X-Cache': cache } },
      )
    }),
  )
  return requests
}

/** Mock GET /api/v1/categories. ``status`` other than 200 simulates a failure. */
export function mockCategories({ categories = [], status = 200 } = {}) {
  server.use(
    http.get('/api/v1/categories', () =>
      status === 200
        ? HttpResponse.json({
            categories,
            total_products: categories.reduce((sum, c) => sum + c.product_count, 0),
          })
        : HttpResponse.json({ detail: 'error' }, { status }),
    ),
  )
}
