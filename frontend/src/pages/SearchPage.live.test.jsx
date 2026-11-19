/**
 * Live: the real SearchPage against the real backend through the Vite proxy (no mocks).
 * Expected numbers are the real 10,000-product catalogue (seed 42) verified in earlier phases.
 * Run with `npm run test:live` while the backend and `npm run dev` are running.
 */
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { renderRoute } from '../test/renderRoute.jsx'

const summary = async () =>
  (await screen.findByText(/^Showing/, {}, { timeout: 15_000 })).textContent
const cards = () => screen.findAllByRole('article', {}, { timeout: 15_000 })

describe('live: search results page via the Vite proxy', () => {
  it('shows real, BM25-ranked results for "laptop"', async () => {
    renderRoute('/search?q=laptop')
    expect(await cards()).toHaveLength(20)
    expect(await summary()).toBe('Showing 1–20 of 220 results for “laptop”')
    const first = screen.getAllByRole('article')[0]
    expect(within(first).getByRole('heading')).toHaveTextContent(
      'Pulsewave Core Laptop, 14-inch, 32GB RAM, 1TB SSD',
    )
  })

  it('prefix matching is on by default: "wireless ear" expands like the API', async () => {
    renderRoute('/search?q=wireless+ear')
    expect(await summary()).toBe('Showing 1–20 of 231 results for “wireless ear”')
    expect(screen.getByText('“ear” matched: earbud, early, ear')).toBeVisible()
  })

  it('Option A: "ear" gives the broader prefix results, "Exact words only" the narrow ones', async () => {
    const user = userEvent.setup()
    const { router } = renderRoute('/search?q=ear')
    expect(await summary()).toMatch(/of 376 results/)
    await user.click(screen.getByRole('checkbox', { name: 'Exact words only' }))
    expect(router.state.location.search).toBe('?q=ear&exact=1')
    await waitFor(async () => expect(await summary()).toMatch(/of 96 results/), { timeout: 15_000 })
  })

  it('pagination moves through real pages', async () => {
    const user = userEvent.setup()
    renderRoute('/search?q=laptop')
    await cards()
    await user.click(screen.getByRole('link', { name: 'Next page' }))
    await waitFor(
      async () => expect(await summary()).toBe('Showing 21–40 of 220 results for “laptop”'),
      {
        timeout: 15_000,
      },
    )
  })

  it('a page past the end is corrected to the last real page', async () => {
    const { router } = renderRoute('/search?q=laptop&page=50')
    await waitFor(() => expect(router.state.location.search).toBe('?q=laptop&page=11'), {
      timeout: 15_000,
    })
    expect(await summary()).toBe('Showing 201–220 of 220 results for “laptop”')
  })

  it('"Any word" mode with an unknown word reports it', async () => {
    renderRoute('/search?q=voltrix+zzzz&mode=any')
    expect(await summary()).toMatch(/of 160 results/)
    expect(screen.getByText(/No products contain words starting with “zzzz”/)).toBeVisible()
  })

  it('shows the empty state for a word nothing starts with', async () => {
    renderRoute('/search?q=xyzq')
    expect(
      await screen.findByRole('heading', { name: 'No products match “xyzq”' }, { timeout: 15_000 }),
    ).toBeVisible()
    expect(screen.getByText('No product contains words starting with “xyzq”.')).toBeVisible()
  })

  // Verified against the API: with prefix matching (the default) "the" is a partial word and
  // the API answers 200 with no matches; with prefix off it answers 422.
  it('"the" with prefix matching (default) is an empty result, not an error', async () => {
    renderRoute('/search?q=the')
    expect(
      await screen.findByRole('heading', { name: 'No products match “the”' }, { timeout: 15_000 }),
    ).toBeVisible()
    expect(screen.getByText('No product contains words starting with “the”.')).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('"the" with "Exact words only" shows the API 422 message', async () => {
    renderRoute('/search?q=the&exact=1')
    const alert = await screen.findByRole('alert', {}, { timeout: 15_000 })
    expect(alert).toHaveTextContent('Query contains no searchable words')
  })
})
