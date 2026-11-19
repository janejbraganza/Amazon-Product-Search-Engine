import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from '../test/server.js'
import { getProduct, listProducts } from './products.js'
import { getSuggestions, searchProducts } from './search.js'

/** Capture the URL of the next request to ``path``. */
function captureRequest(path, body = {}) {
  const seen = {}
  server.use(
    http.get(path, ({ request }) => {
      seen.url = new URL(request.url)
      return HttpResponse.json(body)
    }),
  )
  return seen
}

describe('API endpoint helpers', () => {
  it('searchProducts sends the existing /search parameters', async () => {
    const seen = captureRequest('/api/v1/search')
    await searchProducts({ q: 'wireless ear', mode: 'any', limit: 20, offset: 40, prefix: true })
    expect(seen.url.pathname).toBe('/api/v1/search')
    expect(Object.fromEntries(seen.url.searchParams)).toEqual({
      q: 'wireless ear',
      mode: 'any',
      limit: '20',
      offset: '40',
      prefix: 'true',
    })
  })

  it('searchProducts omits parameters that are not set', async () => {
    const seen = captureRequest('/api/v1/search')
    await searchProducts({ q: 'laptop' })
    expect(seen.url.search).toBe('?q=laptop')
  })

  it('searchProducts sends prefix=false explicitly', async () => {
    const seen = captureRequest('/api/v1/search')
    await searchProducts({ q: 'lap', prefix: false })
    expect(seen.url.searchParams.get('prefix')).toBe('false')
  })

  it('getSuggestions calls /search/suggestions', async () => {
    const seen = captureRequest('/api/v1/search/suggestions')
    await getSuggestions('ear', { limit: 8 })
    expect(seen.url.search).toBe('?q=ear&limit=8')
  })

  it('getProduct calls /products/{id}', async () => {
    const { data } = await getProduct(7)
    expect(data.id).toBe(7)
  })

  it('getProduct encodes the id', async () => {
    const seen = captureRequest('/api/v1/products/:id')
    await getProduct('a/b')
    expect(seen.url.pathname).toBe('/api/v1/products/a%2Fb')
  })

  it('listProducts sends limit and offset', async () => {
    const seen = captureRequest('/api/v1/products', { items: [], total: 0 })
    await listProducts({ limit: 5, offset: 10 })
    expect(seen.url.search).toBe('?limit=5&offset=10')
  })
})
