import { apiGet } from './client.js'

/**
 * GET /api/v1/search - BM25-ranked keyword search with optional filters and sort.
 * Parameter names are the backend's. Undefined values are not sent; arrays (category,
 * brand) are sent as repeated parameters: ?category=A&category=B.
 *
 * @param {{q: string, mode?: string, limit?: number, offset?: number, prefix?: boolean,
 *   sort?: string, category?: string[], brand?: string[], min_price?: string,
 *   max_price?: string, min_rating?: string, in_stock?: boolean}} params
 */
export function searchProducts(params, { signal } = {}) {
  const { prefix, in_stock: inStock, ...rest } = params
  return apiGet('/api/v1/search', {
    params: {
      ...rest,
      prefix: prefix === undefined ? undefined : String(prefix),
      in_stock: inStock ? 'true' : undefined,
    },
    signal,
  })
}

/** GET /api/v1/search/suggestions - Trie autocomplete for the last word of `q`. */
export function getSuggestions(q, { limit, signal } = {}) {
  return apiGet('/api/v1/search/suggestions', { params: { q, limit }, signal })
}
