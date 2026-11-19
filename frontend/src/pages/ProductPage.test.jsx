import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { expectHeadingOutline } from '../test/a11y.js'
import { makeProduct, mockSearch } from '../test/fixtures.js'
import { productFixture } from '../test/handlers.js'
import { renderRoute } from '../test/renderRoute.jsx'
import { server } from '../test/server.js'

/** Mock GET /api/v1/products/:id; ``respond(id)`` returns a response. Records requested ids. */
function mockProduct(respond = (id) => HttpResponse.json({ ...productFixture, id: Number(id) })) {
  const requests = []
  server.use(
    http.get('/api/v1/products/:id', async ({ params }) => {
      requests.push(params.id)
      return respond(params.id)
    }),
  )
  return requests
}

/** Mock the similar-products search; records its parameters. */
function mockSimilar(items, { status = 200 } = {}) {
  const requests = []
  server.use(
    http.get('/api/v1/search', ({ request }) => {
      const params = new URL(request.url).searchParams
      requests.push({ ...Object.fromEntries(params), category: params.getAll('category') })
      if (status !== 200) return HttpResponse.json({ detail: 'error' }, { status })
      return HttpResponse.json({
        query: params.get('q'),
        terms: [],
        unmatched_terms: [],
        mode: 'any',
        total: items.length,
        limit: 5,
        offset: 0,
        items,
        prefix: null,
        expanded_terms: [],
        sort: 'relevance',
        facets: { categories: [], brands: [] },
      })
    }),
  )
  return requests
}

const heading = () => screen.findByRole('heading', { level: 1, name: productFixture.product_name })
const breadcrumb = () => within(screen.getByRole('navigation', { name: 'Breadcrumb' }))

describe('product page: details', () => {
  it('shows every field the API returns', async () => {
    mockSimilar([])
    renderRoute('/products/42')
    await heading()
    const details = within(screen.getByRole('article'))
    expect(details.getByRole('link', { name: 'Brightnest' })).toHaveAttribute(
      'href',
      '/search?q=Brightnest&brand=Brightnest',
    )
    expect(details.getByRole('link', { name: 'Home & Kitchen' })).toHaveAttribute(
      'href',
      '/search?q=Home+%26+Kitchen&category=Home+%26+Kitchen',
    )
    expect(details.getByText('$123.49')).toBeInTheDocument()
    expect(details.getByRole('img', { name: 'Rated 3.7 out of 5' })).toBeInTheDocument()
    expect(details.getByText('(192 reviews)')).toBeInTheDocument()
    expect(details.getByText('In stock')).toBeInTheDocument()
    expect(details.getByText(productFixture.description)).toBeInTheDocument()

    const facts = Object.fromEntries(
      details.getAllByRole('term').map((term) => [term.textContent, term.nextSibling.textContent]),
    )
    expect(facts).toEqual({
      Brand: 'Brightnest',
      Category: 'Home & Kitchen',
      'Customer rating': '3.7 out of 5 (192 reviews)',
      'Units in stock': '14',
      'Added to catalogue': 'May 28, 2025',
      'Product ID': '42',
    })
    expect(document.title).toBe(`${productFixture.product_name} – Product Search`)
  })

  it('shows low and empty stock clearly', async () => {
    mockSimilar([])
    mockProduct(() => HttpResponse.json({ ...productFixture, stock_quantity: 0, review_count: 1 }))
    renderRoute('/products/42')
    await heading()
    expect(screen.getByText('Out of stock')).toBeInTheDocument()
    expect(screen.getByText('(1 review)')).toBeInTheDocument()
  })

  it('shows a loading state until the product arrives', async () => {
    mockProduct(async () => {
      await delay('infinite')
    })
    renderRoute('/products/42')
    expect(screen.getByRole('status')).toHaveTextContent('Loading product…')
    expect(screen.queryByRole('article')).not.toBeInTheDocument()
    expect(document.title).toBe('Loading product – Product Search')
  })

  it('has a correct heading outline and breadcrumb', async () => {
    mockSimilar([makeProduct(7, { category: 'Home & Kitchen' })])
    renderRoute('/products/42')
    await screen.findByRole('heading', { name: 'Similar products' })
    expectHeadingOutline()
    const items = breadcrumb().getAllByRole('listitem')
    expect(items.map((item) => item.textContent)).toEqual([
      'Home',
      'Home & Kitchen',
      productFixture.product_name,
    ])
    expect(breadcrumb().getByText(productFixture.product_name)).toHaveAttribute(
      'aria-current',
      'page',
    )
  })
})

describe('product page: errors', () => {
  it('shows "not found" for a 404', async () => {
    mockProduct((id) => HttpResponse.json({ detail: `Product ${id} not found` }, { status: 404 }))
    renderRoute('/products/999999')
    expect(await screen.findByRole('heading', { level: 1, name: 'Product not found' }))
    expect(screen.getByText(/There is no product with ID 999999/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Search for products' })).toHaveAttribute('href', '/')
    expect(document.title).toBe('Product not available – Product Search')
  })

  it.each(['abc', '0', '-5', '1.5', '99999999999999999999'])(
    'rejects the invalid ID %j without calling the API',
    async (id) => {
      const requests = mockProduct()
      renderRoute(`/products/${id}`)
      expect(await screen.findByRole('heading', { level: 1, name: 'Product not found' }))
      expect(screen.getByText(`“${id}” is not a valid product ID.`)).toBeInTheDocument()
      expect(requests).toEqual([])
    },
  )

  it('explains an API failure and retries', async () => {
    const user = userEvent.setup()
    mockSimilar([])
    let fail = true
    const requests = mockProduct((id) =>
      fail
        ? HttpResponse.json({ detail: 'Traceback: internals' }, { status: 503 })
        : HttpResponse.json({ ...productFixture, id: Number(id) }),
    )
    renderRoute('/products/42')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Couldn’t load this product')
    expect(alert).not.toHaveTextContent('Traceback') // raw server details never shown
    expectHeadingOutline()

    fail = false
    await user.click(within(alert).getByRole('button', { name: 'Try again' }))
    await heading()
    expect(requests).toEqual(['42', '42'])
  })

  it('explains a network failure', async () => {
    mockProduct(() => HttpResponse.error())
    renderRoute('/products/42')
    expect(await screen.findByRole('alert')).toHaveTextContent("Can't reach")
  })
})

describe('product page: back navigation from search results', () => {
  async function openFromResults(url) {
    const user = userEvent.setup()
    mockSearch({ total: 45 })
    const utils = renderRoute(url)
    const cards = await screen.findAllByRole('article')
    mockProduct((id) => HttpResponse.json(makeProduct(Number(id))))
    // (the similar-products search is answered by the same search mock)
    await user.click(within(cards[2]).getByRole('link'))
    await screen.findByRole('heading', { level: 1, name: /^Voltrix Pro Laptop \d+, 14-inch$/ })
    return { user, ...utils }
  }

  it('returns to exactly the same results (query, filters, sort, page)', async () => {
    const url = '/search?q=laptop&sort=price_asc&brand=Voltrix&min_price=100&page=2'
    const { user, router } = await openFromResults(url)
    expect(router.state.location.pathname).toBe('/products/23')

    const back = screen.getByRole('link', { name: 'Back to results' })
    expect(back).toHaveAttribute('href', url)
    expect(breadcrumb().getByRole('link', { name: 'Results for “laptop”' })).toHaveAttribute(
      'href',
      url,
    )

    await user.click(back)
    expect(router.state.location.pathname + router.state.location.search).toBe(url)
    expect(await screen.findAllByRole('article')).toHaveLength(20)
    expect(screen.getByRole('combobox', { name: 'Sort by' })).toHaveValue('price_asc')
  })

  it('the browser Back button also returns to the results', async () => {
    const { router } = await openFromResults('/search?q=laptop&page=2')
    await act(() => router.navigate(-1))
    expect(router.state.location.search).toBe('?q=laptop&page=2')
    expect(await screen.findAllByRole('article')).toHaveLength(20)
  })

  it('keeps the search in the header box, and a new search keeps its sort', async () => {
    const { user, router } = await openFromResults('/search?q=laptop&sort=rating')
    const box = within(screen.getByRole('banner')).getByRole('combobox', {
      name: 'Search products',
    })
    expect(box).toHaveValue('laptop')
    await user.clear(box)
    await user.type(box, 'tablet{Enter}')
    expect(router.state.location.search).toBe('?q=tablet&sort=rating')
  })

  it('a product opened directly offers "Back to home" instead', async () => {
    mockSimilar([])
    renderRoute('/products/42')
    await heading()
    expect(screen.getByRole('link', { name: 'Back to home' })).toHaveAttribute('href', '/')
    expect(breadcrumb().queryByText(/Results for/)).not.toBeInTheDocument()
  })

  it('a 404 opened from results links back to them', async () => {
    mockProduct(() => HttpResponse.json({ detail: 'Product 5 not found' }, { status: 404 }))
    const { router } = renderRoute('/')
    await act(() => router.navigate('/products/5', { state: { fromSearch: '/search?q=lamp' } }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Product not found' }))
    expect(
      screen.getAllByRole('link', { name: 'Back to results' }).map((l) => l.getAttribute('href')),
    ).toEqual(['/search?q=lamp', '/search?q=lamp'])
  })
})

describe('product page: similar products', () => {
  it('searches for the product name in its category and leaves the product itself out', async () => {
    const requests = mockSimilar([
      makeProduct(42, { product_name: 'Itself' }),
      makeProduct(7, { product_name: 'Brightnest Compact Air Fryer' }),
      makeProduct(8, { product_name: 'Ovenly Air Fryer Oven' }),
    ])
    renderRoute('/products/42')
    const section = within(await screen.findByRole('region', { name: 'Similar products' }))
    expect(requests).toEqual([
      {
        q: productFixture.product_name,
        mode: 'any',
        prefix: 'false',
        limit: '5',
        category: ['Home & Kitchen'],
      },
    ])
    expect(section.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual([
      'Brightnest Compact Air Fryer',
      'Ovenly Air Fryer Oven',
    ])
    expect(section.getByText(/ranked by BM25 relevance/)).toBeInTheDocument()
  })

  it('shows at most four', async () => {
    mockSimilar([1, 2, 3, 4, 5].map((id) => makeProduct(id)))
    renderRoute('/products/42')
    const section = within(await screen.findByRole('region', { name: 'Similar products' }))
    expect(section.getAllByRole('article')).toHaveLength(4)
  })

  it.each([
    ['the search fails', () => mockSimilar([], { status: 500 })],
    ['only the product itself is found', () => mockSimilar([makeProduct(42)])],
    ['nothing is found', () => mockSimilar([])],
  ])('is not shown when %s', async (_, setup) => {
    const requests = setup()
    renderRoute('/products/42')
    await heading()
    await waitFor(() => expect(requests).toHaveLength(1))
    // give the response time to render (it must not)
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(screen.queryByRole('region', { name: 'Similar products' })).not.toBeInTheDocument()
  })

  it('opening a similar product loads it and keeps the way back to the results', async () => {
    const user = userEvent.setup()
    mockSimilar([makeProduct(7, { product_name: 'Brightnest Compact Air Fryer' })])
    const requests = mockProduct((id) =>
      HttpResponse.json(
        id === '7'
          ? makeProduct(7, { product_name: 'Brightnest Compact Air Fryer' })
          : { ...productFixture, id: Number(id) },
      ),
    )
    const { router } = renderRoute('/')
    await act(() => router.navigate('/products/42', { state: { fromSearch: '/search?q=fryer' } }))
    const section = within(await screen.findByRole('region', { name: 'Similar products' }))
    await user.click(section.getByRole('link', { name: 'Brightnest Compact Air Fryer' }))
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Brightnest Compact Air Fryer' }),
    ).toBeVisible()
    expect(router.state.location.pathname).toBe('/products/7')
    expect(requests).toEqual(['42', '7'])
    expect(screen.getByRole('link', { name: 'Back to results' })).toHaveAttribute(
      'href',
      '/search?q=fryer',
    )
  })
})
