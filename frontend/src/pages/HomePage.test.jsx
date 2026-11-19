import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { searchFixture } from '../test/handlers.js'
import { mockCategories } from '../test/fixtures.js'
import { renderRoute } from '../test/renderRoute.jsx'
import { server } from '../test/server.js'
import { expectHeadingOutline } from '../test/a11y.js'

const CATEGORIES = [
  { name: 'Electronics', product_count: 1567 },
  { name: 'Home & Kitchen', product_count: 1427 },
  { name: 'Books', product_count: 801 },
]

/** Mock /api/v1/search returning a different total per query; records every request. */
function mockCounts(totals) {
  const requests = []
  server.use(
    http.get('/api/v1/search', ({ request }) => {
      const params = new URL(request.url).searchParams
      requests.push(Object.fromEntries(params))
      const total = totals[params.get('q')]
      if (total === undefined) return HttpResponse.json({ detail: 'boom' }, { status: 500 })
      return HttpResponse.json({ ...searchFixture, query: params.get('q'), total })
    }),
  )
  return requests
}

const categoriesSection = () => within(screen.getByRole('region', { name: 'Browse by category' }))

describe('home page', () => {
  it('renders the hero, search box and the real catalogue size from the API', async () => {
    mockCategories({ categories: CATEGORIES })
    renderRoute('/')
    expect(screen.getByRole('heading', { level: 1, name: 'Find the right product, fast.' }))
    expect(screen.getByRole('combobox', { name: 'Search products' })).toHaveFocus()
    // Before the categories arrive no number is shown (nothing is hard-coded)...
    expect(screen.getByText('Search the product catalogue, ranked by relevance as you type.'))
    // ...then the numbers come from GET /api/v1/categories.
    expect(
      await screen.findByText(
        'Search 3,795 products across 3 categories, ranked by relevance as you type.',
      ),
    ).toBeInTheDocument()
  })

  it('lists every category from the API with its product count and a browse link', async () => {
    mockCategories({ categories: CATEGORIES })
    renderRoute('/')
    const links = await categoriesSection().findAllByRole('link')
    expect(links.map((link) => link.textContent)).toEqual([
      'Electronics1,567 products',
      'Home & Kitchen1,427 products',
      'Books801 products',
    ])
    expect(links[1]).toHaveAttribute('href', '/search?q=Home+%26+Kitchen&category=Home+%26+Kitchen')
    expect(categoriesSection().getByText('3 categories · 3,795 products')).toBeInTheDocument()
  })

  it('shows a loading state while categories load', async () => {
    server.use(
      http.get('/api/v1/categories', async () => {
        await delay('infinite')
      }),
    )
    renderRoute('/')
    expect(categoriesSection().getByRole('status')).toHaveTextContent('Loading categories…')
  })

  it('explains a categories failure, keeps search usable and can retry', async () => {
    const user = userEvent.setup()
    mockCategories({ status: 500 })
    renderRoute('/')
    expect(await categoriesSection().findByRole('alert')).toHaveTextContent(
      'Categories couldn’t be loaded',
    )
    expect(screen.getByRole('combobox', { name: 'Search products' })).toBeEnabled()
    // No numbers without data, and no "Explore" button for an unknown category
    expect(screen.queryByText(/Search \d/)).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /^Explore/ })).not.toBeInTheDocument()

    mockCategories({ categories: CATEGORIES })
    await user.click(categoriesSection().getByRole('button', { name: 'Try again' }))
    expect(await categoriesSection().findByRole('link', { name: /Electronics/ })).toBeVisible()
  })

  it('example searches show their real result counts from the search API', async () => {
    const requests = mockCounts({
      'wireless earbuds': 231,
      laptop: 220,
      'stainless steel': 1,
      'yoga mat': 2000,
      // 'mystery novel' fails: shown without a count
    })
    renderRoute('/')
    const examples = within(screen.getByRole('heading', { name: 'Try a search' }).parentElement)
    expect(await examples.findByRole('link', { name: 'laptop, 220 results' })).toHaveAttribute(
      'href',
      '/search?q=laptop',
    )
    expect(examples.getByRole('link', { name: 'stainless steel, 1 result' })).toBeVisible()
    expect(examples.getByRole('link', { name: 'yoga mat, 2,000 results' })).toBeVisible()
    await waitFor(() => expect(requests).toHaveLength(5))
    expect(examples.getByRole('link', { name: 'mystery novel' })).toBeVisible()
    // Counted exactly as the results page searches (partial last word on), one result only
    expect(requests.find((r) => r.q === 'laptop')).toEqual({
      q: 'laptop',
      mode: 'all',
      prefix: 'true',
      limit: '1',
      offset: '0',
    })
  })

  it('an example search opens its results', async () => {
    const user = userEvent.setup()
    const { router } = renderRoute('/')
    await user.click(screen.getByRole('link', { name: /^yoga mat/ }))
    expect(router.state.location.pathname).toBe('/search')
    expect(router.state.location.search).toBe('?q=yoga+mat')
  })

  it('a category card opens that category’s results', async () => {
    const user = userEvent.setup()
    mockCategories({ categories: CATEGORIES })
    const { router } = renderRoute('/')
    await user.click(await categoriesSection().findByRole('link', { name: /^Books/ }))
    expect(router.state.location.search).toBe('?q=Books&category=Books')
    expect(await screen.findByRole('heading', { level: 1, name: 'Results for “Books”' }))
  })

  it('explains the four search capabilities', () => {
    renderRoute('/')
    const section = within(screen.getByRole('region', { name: 'How the search works' }))
    expect(section.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual([
      'BM25 relevance ranking',
      'Trie-based autocomplete',
      'Redis caching',
      'Filtering and sorting',
    ])
    // No invented performance figures
    expect(section.queryByText(/\d+\s?(ms|x|%)/)).not.toBeInTheDocument()
  })

  it('the call to action explores the largest category or focuses the search box', async () => {
    const user = userEvent.setup()
    mockCategories({ categories: CATEGORIES })
    renderRoute('/')
    const cta = within(screen.getByRole('region', { name: 'Ready to explore?' }))
    expect(await cta.findByRole('link', { name: 'Explore Electronics' })).toHaveAttribute(
      'href',
      '/search?q=Electronics&category=Electronics',
    )
    const box = screen.getByRole('combobox', { name: 'Search products' })
    box.blur()
    await user.click(cta.getByRole('button', { name: 'Start searching' }))
    expect(box).toHaveFocus()
  })

  it('has one h1 and no skipped heading levels', async () => {
    mockCategories({ categories: CATEGORIES })
    renderRoute('/')
    await categoriesSection().findAllByRole('link')
    expectHeadingOutline()
  })
})
