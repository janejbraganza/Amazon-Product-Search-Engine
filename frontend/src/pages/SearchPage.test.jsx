import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { makeProduct, mockSearch } from '../test/fixtures.js'
import { renderRoute } from '../test/renderRoute.jsx'
import { server } from '../test/server.js'

const results = () => screen.findAllByRole('article')
const lastRequest = (requests) => requests[requests.length - 1]
// The summary line contains <strong> (the total), so check the paragraph's full text.
const summary = () => screen.getByText(/^Showing/)

describe('SearchPage results', () => {
  it('shows a loading skeleton, then results with a summary', async () => {
    mockSearch({ total: 45 })
    renderRoute('/search?q=laptop')
    expect(screen.getByRole('status')).toHaveTextContent('Loading results')
    expect(await results()).toHaveLength(20)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.getByText(/Showing 1–20 of/)).toHaveTextContent(
      'Showing 1–20 of 45 results for “laptop”',
    )
  })

  it('requests prefix matching by default (Option A) with page-1 parameters', async () => {
    const requests = mockSearch()
    renderRoute('/search?q=lap')
    await results()
    expect(lastRequest(requests)).toEqual({
      q: 'lap',
      mode: 'all',
      prefix: 'true',
      limit: '20',
      offset: '0',
    })
  })

  it('shows what a partial word expanded to', async () => {
    mockSearch({ terms: ['wireless', 'ear'], expanded: ['earbud', 'early', 'ear'] })
    renderRoute('/search?q=wireless+ear')
    await results()
    expect(screen.getByText('“ear” matched: earbud, early, ear')).toBeVisible()
  })

  it('shows response time and "served from cache" on a cache hit', async () => {
    mockSearch({ cache: 'HIT' })
    renderRoute('/search?q=laptop')
    await results()
    expect(screen.getByText(/ms · served from cache/)).toBeVisible()
  })

  it('does not claim a cache hit on a miss', async () => {
    mockSearch({ cache: 'MISS' })
    renderRoute('/search?q=laptop')
    await results()
    expect(screen.queryByText(/served from cache/)).not.toBeInTheDocument()
  })

  it('reports words that matched nothing while other words did', async () => {
    mockSearch({ total: 3, terms: ['voltrix', 'zzzz'], unmatched: ['zzzz'] })
    renderRoute('/search?q=voltrix+zzzz&mode=any')
    await results()
    expect(screen.getByText('No products contain “zzzz”')).toBeVisible()
  })

  it('sets the document title', async () => {
    mockSearch()
    renderRoute('/search?q=laptop')
    await results()
    await waitFor(() => expect(document.title).toBe('laptop – Product Search'))
  })
})

describe('SearchPage options', () => {
  it('switching to "Any word" updates the URL, resets to page 1 and requests mode=any', async () => {
    const user = userEvent.setup()
    const requests = mockSearch()
    const { router } = renderRoute('/search?q=wireless+earbuds&page=2')
    await results()
    await user.click(screen.getByRole('radio', { name: 'Any word' }))
    expect(router.state.location.search).toBe('?q=wireless+earbuds&mode=any')
    await waitFor(() => expect(lastRequest(requests)).toMatchObject({ mode: 'any', offset: '0' }))
    expect(screen.getByRole('radio', { name: 'Any word' })).toBeChecked()
  })

  it('"Exact words only" sends prefix=false and is kept in the URL', async () => {
    const user = userEvent.setup()
    const requests = mockSearch()
    const { router } = renderRoute('/search?q=ear')
    await results()
    await user.click(screen.getByRole('checkbox', { name: 'Exact words only' }))
    expect(router.state.location.search).toBe('?q=ear&exact=1')
    await waitFor(() => expect(lastRequest(requests)).toMatchObject({ prefix: 'false' }))
  })

  it('changing the page size requests the new limit', async () => {
    const user = userEvent.setup()
    const requests = mockSearch({ total: 100 })
    const { router } = renderRoute('/search?q=laptop')
    await results()
    await user.selectOptions(screen.getByRole('combobox', { name: 'Per page' }), '40')
    expect(router.state.location.search).toBe('?q=laptop&per_page=40')
    await waitFor(() => expect(lastRequest(requests)).toMatchObject({ limit: '40' }))
    await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(40))
  })

  it('a new search from the header keeps the options but starts on page 1', async () => {
    const user = userEvent.setup()
    mockSearch()
    const { router } = renderRoute('/search?q=laptop&mode=any&exact=1&page=2&per_page=40')
    await results()
    const box = screen.getByRole('combobox', { name: 'Search products' })
    await user.clear(box)
    await user.type(box, 'yoga mat{Enter}')
    expect(router.state.location.search).toBe('?q=yoga+mat&mode=any&exact=1&per_page=40')
  })
})

describe('SearchPage pagination', () => {
  it('shows pages and moves to the next page with the right offset', async () => {
    const user = userEvent.setup()
    const requests = mockSearch({ total: 45 })
    const { router } = renderRoute('/search?q=laptop')
    await results()
    const nav = screen.getByRole('navigation', { name: 'Pagination' })
    expect(within(nav).getByRole('link', { name: 'Page 1' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(within(nav).getByRole('link', { name: 'Page 3' })).toBeVisible()
    expect(within(nav).getByLabelText('Previous page')).toHaveAttribute('aria-disabled', 'true')

    await user.click(within(nav).getByRole('link', { name: 'Next page' }))
    expect(router.state.location.search).toBe('?q=laptop&page=2')
    await waitFor(() => expect(lastRequest(requests)).toMatchObject({ offset: '20' }))
    await waitFor(() =>
      expect(summary()).toHaveTextContent('Showing 21–40 of 45 results for “laptop”'),
    )
  })

  it('shows the last, partial page', async () => {
    mockSearch({ total: 45 })
    renderRoute('/search?q=laptop&page=3')
    expect(await results()).toHaveLength(5)
    expect(summary()).toHaveTextContent('Showing 41–45 of 45 results for “laptop”')
    expect(screen.getByLabelText('Next page')).toHaveAttribute('aria-disabled', 'true')
  })

  it('hides pagination when everything fits on one page', async () => {
    mockSearch({ total: 7 })
    renderRoute('/search?q=laptop')
    await results()
    expect(screen.queryByRole('navigation', { name: 'Pagination' })).not.toBeInTheDocument()
  })

  it('redirects a page past the end to the last page', async () => {
    const requests = mockSearch({ total: 45 })
    const { router } = renderRoute('/search?q=laptop&page=9')
    await waitFor(() => expect(router.state.location.search).toBe('?q=laptop&page=3'))
    expect(await results()).toHaveLength(5)
    expect(requests.map((r) => r.offset)).toEqual(['160', '40'])
  })

  it('never shows an impossible range while correcting a page past the end', async () => {
    // Real API behaviour: offset past the end -> total > 0 but no items.
    mockSearch({ total: 45 })
    server.use(
      http.get('/api/v1/search', async ({ request }) => {
        const offset = new URL(request.url).searchParams.get('offset')
        if (offset === '40') await delay(200) // the corrected page arrives later
        return HttpResponse.json({
          query: 'laptop',
          terms: ['laptop'],
          unmatched_terms: [],
          mode: 'all',
          total: 45,
          limit: 20,
          offset: Number(offset),
          items: offset === '40' ? [makeProduct(41)] : [],
          prefix: null,
          expanded_terms: [],
        })
      }),
    )
    const { router } = renderRoute('/search?q=laptop&page=9')
    await waitFor(() => expect(router.state.location.search).toBe('?q=laptop&page=3'))
    // While the corrected page loads: skeleton, and no "Showing 161–160" style text.
    expect(screen.getByRole('status')).toHaveTextContent('Loading results')
    expect(screen.queryByText(/^Showing/)).not.toBeInTheDocument()
    expect(await results()).toHaveLength(1)
    expect(summary()).toHaveTextContent('Showing 41–41 of 45')
  })

  it('Back and Forward restore the previous pages (URL is the state)', async () => {
    const user = userEvent.setup()
    mockSearch({ total: 45 })
    const { router } = renderRoute('/search?q=laptop')
    await results()
    // Each history step re-fetches its page; on a busy machine (coverage, parallel workers,
    // CI) that can take longer than waitFor's 1 s default, so allow more time.
    const slow = { timeout: 5000 }
    await user.click(screen.getByRole('link', { name: 'Page 2' }))
    await waitFor(() => expect(screen.getByText(/Showing 21–40/)).toBeVisible(), slow)

    await router.navigate(-1)
    await waitFor(() => expect(screen.getByText(/Showing 1–20/)).toBeVisible(), slow)
    await router.navigate(1)
    await waitFor(() => expect(screen.getByText(/Showing 21–40/)).toBeVisible(), slow)
  })
})

describe('SearchPage empty and error states', () => {
  it('shows an empty state with the unmatched words and an "any word" link', async () => {
    mockSearch({ total: 0, terms: ['voltrix', 'zzzz'], unmatched: ['zzzz'] })
    renderRoute('/search?q=voltrix+zzzz')
    expect(
      await screen.findByRole('heading', { name: 'No products match “voltrix zzzz”' }),
    ).toBeVisible()
    expect(screen.getByText('No product contains “zzzz”.')).toBeVisible()
    expect(
      screen.getByRole('link', { name: 'Show products matching any of these words' }),
    ).toHaveAttribute('href', '/search?q=voltrix+zzzz&mode=any')
    expect(screen.queryByRole('navigation', { name: 'Pagination' })).not.toBeInTheDocument()
  })

  it('offers partial-word matching when "Exact words only" found nothing', async () => {
    mockSearch({ total: 0, terms: ['lap'], unmatched: ['lap'] })
    renderRoute('/search?q=lap&exact=1')
    expect(
      await screen.findByRole('link', { name: 'Include partial word matches' }),
    ).toHaveAttribute('href', '/search?q=lap')
    expect(screen.queryByText(/any of these words/)).not.toBeInTheDocument()
  })

  it('describes a prefix with no completions in plain words', async () => {
    mockSearch({ total: 0, terms: ['xyzq'], unmatched: ['xyzq*'] })
    renderRoute('/search?q=xyzq')
    expect(await screen.findByText('No product contains words starting with “xyzq”.')).toBeVisible()
  })

  it('shows the API message for a rejected query (422) without a retry button', async () => {
    mockSearch({ status: 422, errorBody: { detail: 'Query contains no searchable words' } })
    renderRoute('/search?q=the')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Try a different search')
    expect(alert).toHaveTextContent('Query contains no searchable words')
    expect(within(alert).queryByRole('button')).not.toBeInTheDocument()
  })

  it('shows a safe error message and recovers with "Try again"', async () => {
    const user = userEvent.setup()
    mockSearch({ status: 500, errorBody: { detail: 'Traceback: internal' } })
    renderRoute('/search?q=laptop')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Search is unavailable right now')
    expect(alert).not.toHaveTextContent('Traceback')

    mockSearch({ total: 3 })
    await user.click(within(alert).getByRole('button', { name: 'Try again' }))
    expect(await results()).toHaveLength(3)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('handles the backend being unreachable', async () => {
    server.use(http.get('/api/v1/search', () => HttpResponse.error()))
    renderRoute('/search?q=laptop')
    expect(await screen.findByRole('alert')).toHaveTextContent("Can't reach the search service")
  })
})

describe('SearchPage request ordering', () => {
  it('never lets a slow, outdated response replace newer results', async () => {
    server.use(
      http.get('/api/v1/search', async ({ request }) => {
        const q = new URL(request.url).searchParams.get('q')
        if (q === 'slow') await delay(300)
        return HttpResponse.json({
          query: q,
          terms: [q],
          unmatched_terms: [],
          mode: 'all',
          total: 1,
          limit: 20,
          offset: 0,
          items: [
            {
              id: q === 'slow' ? 1 : 2,
              product_name: `${q} product`,
              description: 'd',
              category: 'Books',
              brand: 'B',
              price: 1,
              rating: 4,
              review_count: 1,
              stock_quantity: 5,
              created_at: '2026-01-01T00:00:00Z',
              score: 1,
            },
          ],
          prefix: null,
          expanded_terms: [],
        })
      }),
    )
    const { router } = renderRoute('/search?q=slow')
    await router.navigate('/search?q=fast')
    expect(await screen.findByRole('heading', { name: 'fast product' })).toBeVisible()
    await new Promise((resolve) => setTimeout(resolve, 400)) // let the slow one "arrive"
    expect(screen.queryByRole('heading', { name: 'slow product' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'fast product' })).toBeVisible()
  })

  it('does not show results of a different query while the new one loads', async () => {
    server.use(
      http.get('/api/v1/search', async ({ request }) => {
        const q = new URL(request.url).searchParams.get('q')
        if (q === 'second') await delay('infinite')
        return HttpResponse.json({
          query: q,
          terms: [q],
          unmatched_terms: [],
          mode: 'all',
          total: 0,
          limit: 20,
          offset: 0,
          items: [],
          prefix: null,
          expanded_terms: [],
        })
      }),
    )
    const { router } = renderRoute('/search?q=first')
    expect(await screen.findByRole('heading', { name: 'No products match “first”' })).toBeVisible()
    await router.navigate('/search?q=second')
    expect(await screen.findByRole('status')).toHaveTextContent('Loading results')
    expect(screen.queryByText(/first/)).not.toBeInTheDocument()
  })
})
