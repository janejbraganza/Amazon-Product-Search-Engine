import { delay, http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from '../test/server.js'
import { ApiError, apiGet, buildUrl, isAbortError } from './client.js'

describe('buildUrl', () => {
  it('adds parameters and skips empty ones', () => {
    expect(buildUrl('/api/v1/search', { q: 'lap top', mode: undefined, offset: 0, x: '' })).toBe(
      '/api/v1/search?q=lap+top&offset=0',
    )
  })

  it('repeats array parameters', () => {
    expect(buildUrl('/p', { brand: ['A', 'B'] })).toBe('/p?brand=A&brand=B')
  })

  it('returns the bare path without parameters', () => {
    expect(buildUrl('/health')).toBe('/health')
  })
})

describe('apiGet', () => {
  it('returns data, cache status and duration', async () => {
    const result = await apiGet('/api/v1/search', { params: { q: 'air fryer' } })
    expect(result.data.total).toBe(1)
    expect(result.cacheStatus).toBe('MISS')
    expect(result.durationMs).toBeGreaterThanOrEqual(0)
  })

  it('uses the API message for a 422 with a text detail', async () => {
    server.use(
      http.get('/api/v1/search', () =>
        HttpResponse.json({ detail: 'Query contains no searchable words' }, { status: 422 }),
      ),
    )
    await expect(apiGet('/api/v1/search')).rejects.toMatchObject({
      name: 'ApiError',
      status: 422,
      kind: 'http',
      message: 'Query contains no searchable words',
    })
  })

  it('uses a friendly message for a 422 validation list', async () => {
    server.use(
      http.get('/api/v1/search', () =>
        HttpResponse.json(
          { detail: [{ loc: ['query', 'q'], msg: 'Field required' }] },
          { status: 422 },
        ),
      ),
    )
    await expect(apiGet('/api/v1/search')).rejects.toThrow('Please check your search')
  })

  it('reports 404s', async () => {
    server.use(
      http.get('/api/v1/products/:id', () =>
        HttpResponse.json({ detail: 'Product 99999 not found' }, { status: 404 }),
      ),
    )
    await expect(apiGet('/api/v1/products/99999')).rejects.toMatchObject({
      status: 404,
      message: 'Product 99999 not found',
    })
  })

  it('never shows server error details for 5xx', async () => {
    server.use(
      http.get('/api/v1/search', () =>
        HttpResponse.json({ detail: 'Traceback: secret internals' }, { status: 500 }),
      ),
    )
    const error = await apiGet('/api/v1/search').catch((e) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(500)
    expect(error.message).toMatch(/temporarily unavailable/)
    expect(error.message).not.toMatch(/Traceback/)
  })

  it('handles a non-JSON error body', async () => {
    server.use(http.get('/api/v1/search', () => new HttpResponse('Bad gateway', { status: 502 })))
    await expect(apiGet('/api/v1/search')).rejects.toMatchObject({ status: 502 })
  })

  it('reports network failures', async () => {
    server.use(http.get('/api/v1/search', () => HttpResponse.error()))
    await expect(apiGet('/api/v1/search')).rejects.toMatchObject({
      kind: 'network',
      message: expect.stringMatching(/Can't reach the search service/),
    })
  })

  it('times out slow responses', async () => {
    server.use(
      http.get('/api/v1/search', async () => {
        await delay('infinite')
      }),
    )
    await expect(apiGet('/api/v1/search', { timeoutMs: 50 })).rejects.toMatchObject({
      kind: 'timeout',
    })
  })

  it('rethrows caller cancellation as an AbortError (not a user-facing error)', async () => {
    server.use(
      http.get('/api/v1/search', async () => {
        await delay('infinite')
      }),
    )
    const controller = new AbortController()
    const request = apiGet('/api/v1/search', { signal: controller.signal })
    controller.abort()
    const error = await request.catch((e) => e)
    expect(isAbortError(error)).toBe(true)
    expect(error).not.toBeInstanceOf(ApiError)
  })

  it('does not even start a request with an already-cancelled signal', async () => {
    const controller = new AbortController()
    controller.abort()
    const error = await apiGet('/api/v1/search', { signal: controller.signal }).catch((e) => e)
    expect(isAbortError(error)).toBe(true)
  })
})
