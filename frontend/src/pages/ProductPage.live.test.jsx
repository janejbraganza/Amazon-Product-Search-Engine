/**
 * Live: the product page and the home page against the real backend through the Vite
 * proxy (no mocks). Expected values are read from the real API in each test.
 * Run with `npm run test:live` while the backend and `npm run dev` are running.
 */
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { renderRoute } from '../test/renderRoute.jsx'
import { categoryUrl, similarQuery } from '../utils/catalogue.js'
import { formatPrice } from '../utils/format.js'

const TIMEOUT = { timeout: 15_000 }

async function get(path) {
  const response = await fetch(`${window.location.origin}${path}`)
  return { status: response.status, body: await response.json() }
}

describe('live: GET /api/v1/products/{id} through the Vite proxy', () => {
  it('returns a product with every field the page shows', async () => {
    const { status, body } = await get('/api/v1/products/1')
    expect(status).toBe(200)
    expect(Object.keys(body).sort()).toEqual(
      [
        'brand',
        'category',
        'created_at',
        'description',
        'id',
        'price',
        'product_name',
        'rating',
        'review_count',
        'stock_quantity',
      ].sort(),
    )
    expect(body.id).toBe(1)
  })

  it('answers 404 for a missing product and 422 for an invalid ID', async () => {
    expect((await get('/api/v1/products/99999999')).status).toBe(404)
    expect((await get('/api/v1/products/abc')).status).toBe(422)
    expect((await get('/api/v1/products/0')).status).toBe(422)
  })
})

describe('live: product page', () => {
  it('shows the real product', async () => {
    const { body: product } = await get('/api/v1/products/1')
    renderRoute('/products/1')
    expect(
      await screen.findByRole('heading', { level: 1, name: product.product_name }, TIMEOUT),
    ).toBeVisible()
    const details = within(screen.getByRole('article'))
    expect(details.getByText(formatPrice(product.price))).toBeInTheDocument()
    expect(details.getByText(product.description)).toBeInTheDocument()
    expect(details.getByRole('img', { name: `Rated ${product.rating.toFixed(1)} out of 5` }))
    const facts = Object.fromEntries(
      details.getAllByRole('term').map((term) => [term.textContent, term.nextSibling.textContent]),
    )
    expect(facts['Product ID']).toBe('1')
    expect(facts.Brand).toBe(product.brand)
    expect(facts.Category).toBe(product.category)
    expect(facts['Units in stock']).toBe(product.stock_quantity.toLocaleString('en-US'))
  })

  it('shows similar products: the real search, same category, without the product itself', async () => {
    const { body: product } = await get('/api/v1/products/1')
    const params = new URLSearchParams({
      q: similarQuery(product.product_name),
      mode: 'any',
      prefix: 'false',
      limit: '5',
      category: product.category,
    })
    const { body: search } = await get(`/api/v1/search?${params}`)
    const expected = search.items.filter((item) => item.id !== 1).slice(0, 4)
    expect(expected.length).toBeGreaterThan(0)
    expect(expected.every((item) => item.category === product.category)).toBe(true)

    renderRoute('/products/1')
    const section = within(await screen.findByRole('region', { name: 'Similar products' }, TIMEOUT))
    expect(
      section.getAllByRole('heading', { level: 3 }).map((heading) => heading.textContent),
    ).toEqual(expected.map((item) => item.product_name))
  })

  it('shows "Product not found" for a real 404', async () => {
    renderRoute('/products/99999999')
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Product not found' }, TIMEOUT),
    ).toBeVisible()
  })

  it('results -> product -> Back to results keeps the search', async () => {
    const user = userEvent.setup()
    const url = '/search?q=laptop&sort=price_asc&category=Electronics&page=2'
    const { router } = renderRoute(url)
    const cards = await screen.findAllByRole('article', {}, TIMEOUT)
    const name = within(cards[0]).getByRole('link').textContent
    await user.click(within(cards[0]).getByRole('link'))
    expect(await screen.findByRole('heading', { level: 1, name }, TIMEOUT)).toBeVisible()
    await user.click(screen.getByRole('link', { name: 'Back to results' }))
    expect(router.state.location.pathname + router.state.location.search).toBe(url)
    await waitFor(() => expect(screen.getAllByRole('article')[0]).toHaveTextContent(name), TIMEOUT)
  })
})

describe('live: home page', () => {
  it('shows the real categories, counts and catalogue size', async () => {
    const { body } = await get('/api/v1/categories')
    renderRoute('/')
    const section = within(screen.getByRole('region', { name: 'Browse by category' }))
    const links = await section.findAllByRole('link', {}, TIMEOUT)
    expect(links.map((link) => link.getAttribute('aria-label'))).toEqual(
      body.categories.map((c) => `${c.name}, ${c.product_count.toLocaleString('en-US')} products`),
    )
    expect(
      screen.getByText(
        `Search ${body.total_products.toLocaleString('en-US')} products across ${body.categories.length} categories, ranked by relevance as you type.`,
      ),
    ).toBeInTheDocument()
  })

  it('every category link lists exactly that category’s products', async () => {
    const { body } = await get('/api/v1/categories')
    for (const category of body.categories) {
      const params = new URLSearchParams(categoryUrl(category.name).split('?')[1])
      const api = new URLSearchParams({
        q: params.get('q'),
        prefix: 'true',
        limit: '1',
        category: category.name,
      })
      const { status, body: search } = await get(`/api/v1/search?${api}`)
      expect(status).toBe(200)
      expect(search.total, category.name).toBe(category.product_count)
    }
  })

  it('example searches show the real result counts', async () => {
    renderRoute('/')
    const examples = within(screen.getByRole('heading', { name: 'Try a search' }).parentElement)
    await waitFor(
      () =>
        expect(examples.getAllByRole('link').every((link) => link.hasAttribute('aria-label'))).toBe(
          true,
        ),
      TIMEOUT,
    )
    for (const link of examples.getAllByRole('link')) {
      const q = new URLSearchParams(link.getAttribute('href').split('?')[1]).get('q')
      const { body } = await get(
        `/api/v1/search?${new URLSearchParams({ q, prefix: 'true', limit: '1' })}`,
      )
      expect(link).toHaveAttribute(
        'aria-label',
        `${q}, ${body.total.toLocaleString('en-US')} ${body.total === 1 ? 'result' : 'results'}`,
      )
    }
  })
})
