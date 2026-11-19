/**
 * Live: filters and sorting on the real search page against the real backend, through the
 * Vite proxy (no mocks). Expected values come from the real API in each test.
 * Run with `npm run test:live` while the backend and `npm run dev` are running.
 */
import { cleanup, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { buildSearchParams } from '../utils/searchState.js'
import { renderRoute } from '../test/renderRoute.jsx'

const TIMEOUT = { timeout: 15_000 }
const sidebar = () => within(screen.getByRole('complementary', { name: 'Filters' }))

/** The real API response for a search state (same parameters the page sends). */
async function api(state) {
  const params = buildSearchParams({ perPage: 20, page: 1, ...state })
  const api = new URLSearchParams()
  api.set('q', params.get('q'))
  api.set('prefix', 'true')
  api.set('limit', '20')
  api.set('offset', String(((state.page ?? 1) - 1) * 20))
  for (const key of ['sort', 'min_price', 'max_price', 'min_rating']) {
    if (params.get(key)) api.set(key, params.get(key))
  }
  params.getAll('category').forEach((c) => api.append('category', c))
  params.getAll('brand').forEach((b) => api.append('brand', b))
  if (params.get('in_stock')) api.set('in_stock', 'true')
  const response = await fetch(`${window.location.origin}/api/v1/search?${api}`)
  expect(response.status).toBe(200)
  return response.json()
}

const shownIds = () =>
  screen
    .getAllByRole('article')
    .map((card) => Number(within(card).getByRole('link').getAttribute('href').split('/').pop()))

async function expectResults(expected) {
  await waitFor(() => {
    expect(screen.getByText(/^Showing/).textContent).toContain(
      `of ${expected.total.toLocaleString('en-US')}`,
    )
    expect(shownIds()).toEqual(expected.items.map((item) => item.id))
  }, TIMEOUT)
}

describe('live: filters and sorting via the Vite proxy', () => {
  it('category and brand counts come from the real facets', async () => {
    const user = userEvent.setup()
    const expected = await api({ q: 'laptop' })
    renderRoute('/search?q=laptop')
    await expectResults(expected)
    // The panel shows the first 8 brands; expand to check every one.
    if (expected.facets.brands.length > 8) {
      await user.click(
        sidebar().getByRole('button', { name: `Show all ${expected.facets.brands.length}` }),
      )
    }
    for (const facet of expected.facets.brands) {
      const label = sidebar()
        .getByRole('checkbox', { name: new RegExp(`^${facet.value}`) })
        .closest('label')
      expect(label).toHaveTextContent(`${facet.value}${facet.count}`)
    }
    const electronics = expected.facets.categories.find((c) => c.value === 'Electronics')
    expect(
      sidebar()
        .getByRole('checkbox', { name: /^Electronics/ })
        .closest('label'),
    ).toHaveTextContent(`Electronics${electronics.count}`)
    // A catalogue category with no laptops: listed with 0 and disabled
    expect(sidebar().getByRole('checkbox', { name: /^Books/ })).toBeDisabled()
  })

  it('every sort option returns the real backend order', async () => {
    const user = userEvent.setup()
    renderRoute('/search?q=laptop')
    await screen.findAllByRole('article', {}, TIMEOUT)
    for (const [label, value] of [
      ['Price: Low to High', 'price_asc'],
      ['Price: High to Low', 'price_desc'],
      ['Customer Rating', 'rating'],
      ['Newest First', 'newest'],
      ['Relevance', 'relevance'],
    ]) {
      const expected = await api({ q: 'laptop', sort: value })
      await user.selectOptions(screen.getByRole('combobox', { name: 'Sort by' }), label)
      await expectResults(expected)
    }
  })

  it('combined filters, sort, page 2, refresh and clear all (the manual scenario)', async () => {
    const user = userEvent.setup()
    const base = await api({ q: 'laptop' })
    const brand = base.facets.brands[0].value // the most common laptop brand, from the API
    const { router } = renderRoute('/search?q=laptop')
    await expectResults(base)

    // 1-4. category, brand, price range
    await user.click(sidebar().getByRole('checkbox', { name: /^Electronics/ }))
    await user.click(sidebar().getByRole('checkbox', { name: new RegExp(`^${brand}`) }))
    await user.type(sidebar().getByRole('textbox', { name: 'Minimum price' }), '500')
    await user.type(sidebar().getByRole('textbox', { name: 'Maximum price' }), '2000{Enter}')
    // 5. sort by price, low to high
    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Sort by' }),
      'Price: Low to High',
    )
    const filters = {
      q: 'laptop',
      sort: 'price_asc',
      categories: ['Electronics'],
      brands: [brand],
      minPrice: '500',
      maxPrice: '2000',
    }
    const page1 = await api(filters)
    await expectResults(page1)
    expect(page1.total).toBeLessThan(base.total)
    const prices = page1.items.map((item) => item.price)
    expect(prices).toEqual([...prices].sort((a, b) => a - b))
    expect(page1.items.every((i) => i.brand === brand && i.price >= 500 && i.price <= 2000)).toBe(
      true,
    )

    // 6. page 2 (only if the filtered results have one)
    let state = filters
    if (page1.total > 20) {
      await user.click(screen.getByRole('link', { name: 'Next page' }))
      state = { ...filters, page: 2 }
      await expectResults(await api(state))
    }
    const url = router.state.location.pathname + router.state.location.search

    // 7-8. "refresh": a brand-new render of the same URL shows the same settings and results
    cleanup()
    renderRoute(url)
    await expectResults(await api(state))
    expect(sidebar().getByRole('checkbox', { name: /^Electronics/ })).toBeChecked()
    expect(sidebar().getByRole('checkbox', { name: new RegExp(`^${brand}`) })).toBeChecked()
    expect(sidebar().getByRole('textbox', { name: 'Minimum price' })).toHaveValue('500')
    expect(sidebar().getByRole('textbox', { name: 'Maximum price' })).toHaveValue('2000')
    expect(screen.getByRole('combobox', { name: 'Sort by' })).toHaveValue('price_asc')

    // 9. clear all filters: the search (and the sort) stay
    await user.click(screen.getByRole('button', { name: 'Clear all filters' }))
    await expectResults(await api({ q: 'laptop', sort: 'price_asc' }))
  })

  it('rating and stock filters match the real API', async () => {
    const user = userEvent.setup()
    renderRoute('/search?q=wireless+earbuds')
    await screen.findAllByRole('article', {}, TIMEOUT)
    await user.selectOptions(sidebar().getByRole('combobox', { name: 'Minimum rating' }), '4.5')
    await user.click(sidebar().getByRole('checkbox', { name: 'In stock only' }))
    const expected = await api({ q: 'wireless earbuds', minRating: '4.5', inStock: true })
    await expectResults(expected)
    expect(expected.items.every((i) => i.rating >= 4.5 && i.stock_quantity > 0)).toBe(true)
  })

  it('an invalid price range is caught before any request', async () => {
    const user = userEvent.setup()
    const { router } = renderRoute('/search?q=laptop')
    await screen.findAllByRole('article', {}, TIMEOUT)
    await user.type(sidebar().getByRole('textbox', { name: 'Minimum price' }), '900')
    await user.type(sidebar().getByRole('textbox', { name: 'Maximum price' }), '100{Enter}')
    expect(sidebar().getByRole('alert')).toHaveTextContent('must not be more than the maximum')
    expect(router.state.location.search).toBe('?q=laptop')
  })
})
