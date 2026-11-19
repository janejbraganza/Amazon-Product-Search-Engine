import { http, HttpResponse } from 'msw'

/**
 * Default mock API used by the tests (shapes copied from the real FastAPI responses).
 * Tests override individual handlers with server.use(...) when they need something else.
 */
export const productFixture = {
  id: 42,
  product_name: 'Brightnest Artisan Air Fryer, 8-Quart, Stainless Steel',
  description: 'The Brightnest Artisan Air Fryer features a digital touchscreen.',
  category: 'Home & Kitchen',
  brand: 'Brightnest',
  price: 123.49,
  rating: 3.7,
  review_count: 192,
  stock_quantity: 14,
  created_at: '2025-05-28T05:13:52Z',
}

export const searchFixture = {
  query: 'air fryer',
  terms: ['air', 'fryer'],
  unmatched_terms: [],
  mode: 'all',
  total: 1,
  limit: 20,
  offset: 0,
  items: [{ ...productFixture, score: 12.195446 }],
  prefix: null,
  expanded_terms: [],
  sort: 'relevance',
  facets: {
    categories: [{ value: 'Home & Kitchen', count: 1 }],
    brands: [{ value: 'Brightnest', count: 1 }],
  },
}

// Shape of GET /api/v1/categories (most products first, then by name).
export const categoriesFixture = {
  categories: [
    { name: 'Electronics', product_count: 1567 },
    { name: 'Home & Kitchen', product_count: 1427 },
    { name: 'Books', product_count: 801 },
  ],
  total_products: 3795,
}

export const handlers = [
  http.get('/api/v1/categories', () => HttpResponse.json(categoriesFixture)),
  http.get('/api/v1/search', () =>
    HttpResponse.json(searchFixture, { headers: { 'X-Cache': 'MISS' } }),
  ),
  http.get('/api/v1/search/suggestions', ({ request }) => {
    const q = new URL(request.url).searchParams.get('q')
    return HttpResponse.json({
      query: q,
      prefix: q,
      suggestions: [{ term: 'earbud', product_count: 231 }],
    })
  }),
  http.get('/api/v1/products/:id', ({ params }) =>
    HttpResponse.json({ ...productFixture, id: Number(params.id) }),
  ),
]
