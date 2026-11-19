import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockCategories, mockSearch } from '../test/fixtures.js'
import { renderRoute } from '../test/renderRoute.jsx'

const sidebar = () => screen.getByRole('complementary', { name: 'Filters' })
const inSidebar = () => within(sidebar())
const results = () => screen.findAllByRole('article')
const last = (requests) => requests[requests.length - 1]
const box = (role, name) => inSidebar().getByRole(role, { name })

async function load(url, options) {
  const requests = mockSearch(options)
  const user = userEvent.setup()
  const utils = renderRoute(url)
  await results()
  return { requests, user, ...utils }
}

describe('filter sidebar: categories and brands', () => {
  it('lists catalogue categories with counts from the search facets', async () => {
    await load('/search?q=laptop')
    const electronics = box('checkbox', /^Electronics/)
    expect(electronics.closest('label')).toHaveTextContent('Electronics40')
    expect(box('checkbox', /^Home & Kitchen/).closest('label')).toHaveTextContent('5')
    // "Books" is in the catalogue but not in this search's facets: count 0, disabled
    expect(box('checkbox', /^Books/)).toBeDisabled()
    expect(box('checkbox', /^Books/).closest('label')).toHaveTextContent('Books0')
  })

  it('lists brands from the facets with their counts', async () => {
    await load('/search?q=laptop')
    const fieldset = inSidebar().getByRole('group', { name: 'Brand' })
    expect(
      within(fieldset)
        .getAllByRole('checkbox')
        .map((b) => b.closest('label').textContent),
    ).toEqual(['Voltrix30', 'Nexora10', 'Kestrel Labs5'])
  })

  it('shows only the first brands until "Show all" is pressed', async () => {
    const brands = Array.from({ length: 12 }, (_, i) => ({ value: `Brand ${i}`, count: 12 - i }))
    const { user } = await load('/search?q=laptop', {
      facets: { categories: [], brands },
    })
    const fieldset = inSidebar().getByRole('group', { name: 'Brand' })
    expect(within(fieldset).getAllByRole('checkbox')).toHaveLength(8)
    await user.click(within(fieldset).getByRole('button', { name: 'Show all 12' }))
    expect(within(fieldset).getAllByRole('checkbox')).toHaveLength(12)
  })

  it('selecting categories adds repeated parameters and resets to page 1', async () => {
    const { requests, user, router } = await load('/search?q=laptop&page=3')
    await user.click(box('checkbox', /^Electronics/))
    expect(router.state.location.search).toBe('?q=laptop&category=Electronics')
    await user.click(box('checkbox', /^Home & Kitchen/))
    expect(router.state.location.search).toBe(
      '?q=laptop&category=Electronics&category=Home+%26+Kitchen',
    )
    await waitFor(() =>
      expect(last(requests).all.category).toEqual(['Electronics', 'Home & Kitchen']),
    )
    expect(last(requests).search).toContain('category=Electronics&category=Home+%26+Kitchen')
    expect(last(requests).offset).toBe('0')
  })

  it('selecting several brands sends them all; unchecking removes one', async () => {
    const { requests, user, router } = await load('/search?q=laptop')
    await user.click(box('checkbox', /^Voltrix/))
    await user.click(box('checkbox', /^Nexora/))
    await waitFor(() => expect(last(requests).all.brand).toEqual(['Voltrix', 'Nexora']))
    await user.click(box('checkbox', /^Voltrix/))
    expect(router.state.location.search).toBe('?q=laptop&brand=Nexora')
  })

  it('a selected brand missing from the facets stays visible so it can be removed', async () => {
    await load('/search?q=laptop&brand=Orbix')
    const orbix = box('checkbox', /^Orbix/)
    expect(orbix).toBeChecked()
    expect(orbix).toBeEnabled()
  })

  it('falls back to facet categories when the categories request fails', async () => {
    mockCategories({ status: 500 })
    await load('/search?q=laptop')
    expect(await screen.findByText('The full category list could not be loaded.')).toBeVisible()
    expect(box('checkbox', /^Electronics/)).toBeEnabled()
    expect(inSidebar().queryByRole('checkbox', { name: /^Books/ })).not.toBeInTheDocument()
  })

  it('works with an empty category list', async () => {
    mockCategories({ categories: [] })
    await load('/search?q=laptop', { facets: { categories: [], brands: [] } })
    expect(inSidebar().getByText('No category options')).toBeVisible()
    expect(inSidebar().getByText('No brand options')).toBeVisible()
  })
})

describe('filter sidebar: price, rating, stock', () => {
  it('applies a price once typing pauses (not on every keystroke)', async () => {
    const { requests, user, router } = await load('/search?q=laptop&page=2')
    const before = requests.length
    await user.type(box('textbox', 'Minimum price'), '49.99')
    expect(router.state.location.search).toBe('?q=laptop&page=2') // not yet
    await waitFor(() => expect(router.state.location.search).toBe('?q=laptop&min_price=49.99'), {
      timeout: 2000,
    })
    await waitFor(() => expect(last(requests).min_price).toBe('49.99'))
    expect(requests.length - before).toBe(1) // one request for five keystrokes
  })

  it('Enter applies a price immediately', async () => {
    const { user, router } = await load('/search?q=laptop')
    await user.type(box('textbox', 'Maximum price'), '200{Enter}')
    expect(router.state.location.search).toBe('?q=laptop&max_price=200')
  })

  it('applies a min-max range together', async () => {
    const { requests, user } = await load('/search?q=laptop')
    await user.type(box('textbox', 'Minimum price'), '50')
    await user.type(box('textbox', 'Maximum price'), '199.5{Enter}')
    await waitFor(() =>
      expect(last(requests)).toMatchObject({ min_price: '50', max_price: '199.5' }),
    )
  })

  it.each([
    ['1.234', '', 'Enter a minimum price like 50 or 49.99.'],
    ['-5', '', 'Enter a minimum price like 50 or 49.99.'],
    ['', 'abc', 'Enter a maximum price like 200 or 199.99.'],
    ['300', '100', 'The minimum price must not be more than the maximum price.'],
  ])('rejects min %j / max %j without searching', async (min, max, message) => {
    const { requests, user, router } = await load('/search?q=laptop')
    const count = requests.length
    if (min) await user.type(box('textbox', 'Minimum price'), min)
    if (max) await user.type(box('textbox', 'Maximum price'), `${max}{Enter}`)
    expect(await inSidebar().findByRole('alert')).toHaveTextContent(message)
    await new Promise((resolve) => setTimeout(resolve, 900))
    expect(router.state.location.search).toBe('?q=laptop')
    expect(requests).toHaveLength(count)
  })

  it('minimum rating sends min_rating', async () => {
    const { requests, user, router } = await load('/search?q=laptop')
    await user.selectOptions(box('combobox', 'Minimum rating'), '4')
    expect(router.state.location.search).toBe('?q=laptop&min_rating=4')
    await waitFor(() => expect(last(requests).min_rating).toBe('4'))
    await user.selectOptions(box('combobox', 'Minimum rating'), '')
    expect(router.state.location.search).toBe('?q=laptop')
  })

  it('"In stock only" sends in_stock=true, and unchecking sends no stock filter', async () => {
    const { requests, user, router } = await load('/search?q=laptop')
    await user.click(box('checkbox', 'In stock only'))
    expect(router.state.location.search).toBe('?q=laptop&in_stock=true')
    await waitFor(() => expect(last(requests).in_stock).toBe('true'))
    await user.click(box('checkbox', 'In stock only'))
    await waitFor(() => expect(last(requests)).not.toHaveProperty('in_stock'))
  })
})

describe('sorting', () => {
  it.each([
    ['Price: Low to High', 'price_asc'],
    ['Price: High to Low', 'price_desc'],
    ['Customer Rating', 'rating'],
    ['Newest First', 'newest'],
  ])('"%s" sends sort=%s and resets to page 1', async (label, value) => {
    const { requests, user, router } = await load('/search?q=laptop&page=2')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Sort by' }), label)
    expect(router.state.location.search).toBe(`?q=laptop&sort=${value}`)
    await waitFor(() => expect(last(requests)).toMatchObject({ sort: value, offset: '0' }))
  })

  it('relevance is the default and is not sent', async () => {
    const { requests, user, router } = await load('/search?q=laptop&sort=rating')
    expect(screen.getByRole('combobox', { name: 'Sort by' })).toHaveValue('rating')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Sort by' }), 'Relevance')
    expect(router.state.location.search).toBe('?q=laptop')
    await waitFor(() => expect(last(requests)).not.toHaveProperty('sort'))
  })
})

describe('combined filters, chips and clearing', () => {
  const FULL =
    '/search?q=laptop&mode=any&exact=1&sort=price_asc&category=Electronics&brand=Voltrix&brand=Nexora&min_price=50&max_price=2000&min_rating=4&in_stock=true&page=2&per_page=40'

  it('a shared or refreshed URL restores every control and sends every parameter', async () => {
    const { requests } = await load(FULL)
    expect(box('checkbox', /^Electronics/)).toBeChecked()
    expect(box('checkbox', /^Voltrix/)).toBeChecked()
    expect(box('checkbox', /^Nexora/)).toBeChecked()
    expect(box('textbox', 'Minimum price')).toHaveValue('50')
    expect(box('textbox', 'Maximum price')).toHaveValue('2000')
    expect(box('combobox', 'Minimum rating')).toHaveValue('4')
    expect(box('checkbox', 'In stock only')).toBeChecked()
    expect(screen.getByRole('combobox', { name: 'Sort by' })).toHaveValue('price_asc')
    expect(last(requests)).toEqual({
      q: 'laptop',
      mode: 'any',
      prefix: 'false',
      limit: '40',
      offset: '40',
      sort: 'price_asc',
      category: 'Electronics',
      brand: 'Nexora', // Object.fromEntries keeps the last repeated value...
      min_price: '50',
      max_price: '2000',
      min_rating: '4',
      in_stock: 'true',
    })
    expect(last(requests).all.brand).toEqual(['Voltrix', 'Nexora']) // ...both were sent
  })

  it('shows a chip for every active filter; removing a chip removes only that filter', async () => {
    const { user, router } = await load(FULL)
    const chips = screen.getByRole('region', { name: 'Active filters' })
    expect(
      within(chips)
        .getAllByRole('button')
        .map((b) => b.textContent),
    ).toEqual([
      'Electronics',
      'Voltrix',
      'Nexora',
      '$50 – $2000',
      '4★ & up',
      'In stock only',
      'Clear all filters',
    ])
    await user.click(within(chips).getByRole('button', { name: 'Remove filter: Voltrix' }))
    expect(router.state.location.search).toBe(
      '?q=laptop&mode=any&exact=1&sort=price_asc&category=Electronics&brand=Nexora&min_price=50&max_price=2000&min_rating=4&in_stock=true&per_page=40',
    )
  })

  it('"Clear all filters" keeps the query, matching options, sort and page size', async () => {
    const { user, router, requests } = await load(FULL)
    await user.click(screen.getByRole('button', { name: 'Clear all filters' }))
    expect(router.state.location.search).toBe(
      '?q=laptop&mode=any&exact=1&sort=price_asc&per_page=40',
    )
    await waitFor(() => expect(last(requests).all.category).toEqual([]))
    expect(box('textbox', 'Minimum price')).toHaveValue('')
    expect(screen.queryByRole('region', { name: 'Active filters' })).not.toBeInTheDocument()
  })

  it('Back and Forward restore filter state and results', async () => {
    const { user, router, requests } = await load('/search?q=laptop')
    await user.click(box('checkbox', /^Electronics/))
    await waitFor(() => expect(last(requests).all.category).toEqual(['Electronics']))
    await router.navigate(-1)
    await waitFor(() => expect(box('checkbox', /^Electronics/)).not.toBeChecked())
    await waitFor(() => expect(last(requests).all.category).toEqual([]))
    await router.navigate(1)
    await waitFor(() => expect(box('checkbox', /^Electronics/)).toBeChecked())
  })

  it('does not send duplicate requests for the same state', async () => {
    const { requests } = await load('/search?q=laptop&category=Electronics')
    await new Promise((resolve) => setTimeout(resolve, 300))
    expect(requests).toHaveLength(1)
  })

  it('a new search from the search box clears filters but keeps sort and options', async () => {
    const { user, router } = await load(FULL)
    const input = screen.getByRole('combobox', { name: 'Search products' })
    await user.clear(input)
    await user.type(input, 'tablet{Enter}')
    expect(router.state.location.search).toBe(
      '?q=tablet&mode=any&exact=1&sort=price_asc&per_page=40',
    )
  })

  it('offers "Clear all filters" when filters leave no results', async () => {
    mockSearch({ total: 0 })
    const { router } = renderRoute('/search?q=laptop&brand=Orbix')
    expect(await screen.findByRole('heading', { name: 'No products match “laptop”' })).toBeVisible()
    const link = screen.getByRole('link', { name: 'Clear all filters' })
    expect(link).toHaveAttribute('href', '/search?q=laptop')
    expect(router.state.location.search).toBe('?q=laptop&brand=Orbix')
  })

  it('keeps a decimal typed after the whole-number part was already applied', async () => {
    const { user, router } = await load('/search?q=laptop')
    const input = box('textbox', 'Maximum price')
    await user.type(input, '150')
    await waitFor(() => expect(router.state.location.search).toBe('?q=laptop&max_price=150'), {
      timeout: 2000,
    })
    await user.type(input, '.25')
    expect(input).toHaveValue('150.25')
    await waitFor(() => expect(router.state.location.search).toBe('?q=laptop&max_price=150.25'), {
      timeout: 2000,
    })
  })

  it('Clear all cancels a price that was still waiting to be applied', async () => {
    const { user, router } = await load('/search?q=laptop&brand=Voltrix')
    await user.type(box('textbox', 'Minimum price'), '75')
    await user.click(screen.getByRole('button', { name: 'Clear all filters' }))
    await new Promise((resolve) => setTimeout(resolve, 900))
    expect(router.state.location.search).toBe('?q=laptop')
  })
})

describe('mobile filter drawer', () => {
  async function openDrawer(url = '/search?q=laptop') {
    const loaded = await load(url)
    await loaded.user.click(screen.getByRole('button', { name: /^Filters/ }))
    return { ...loaded, dialog: screen.getByRole('dialog', { name: 'Filters' }) }
  }

  it('opens an accessible dialog and moves focus into it', async () => {
    const { dialog } = await openDrawer()
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(within(dialog).getByRole('button', { name: 'Close filters' })).toHaveFocus()
    expect(document.body.style.overflow).toBe('hidden')
  })

  it('changes are a draft until "Show results", which applies them once', async () => {
    const { dialog, user, router, requests } = await openDrawer('/search?q=laptop&page=2')
    const count = requests.length
    await user.click(within(dialog).getByRole('checkbox', { name: /^Electronics/ }))
    await user.click(within(dialog).getByRole('checkbox', { name: 'In stock only' }))
    expect(router.state.location.search).toBe('?q=laptop&page=2') // nothing applied yet
    await user.click(within(dialog).getByRole('button', { name: 'Show results' }))
    expect(router.state.location.search).toBe('?q=laptop&category=Electronics&in_stock=true')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await waitFor(() => expect(requests).toHaveLength(count + 1))
    expect(screen.getByRole('button', { name: /^Filters/ })).toHaveTextContent('Filters2')
  })

  it('"Clear" empties the draft; "Show results" then removes all filters', async () => {
    const { dialog, user, router } = await openDrawer('/search?q=laptop&brand=Voltrix&min_rating=4')
    expect(within(dialog).getByRole('checkbox', { name: /^Voltrix/ })).toBeChecked()
    await user.click(within(dialog).getByRole('button', { name: 'Clear' }))
    expect(within(dialog).getByRole('checkbox', { name: /^Voltrix/ })).not.toBeChecked()
    await user.click(within(dialog).getByRole('button', { name: 'Show results' }))
    expect(router.state.location.search).toBe('?q=laptop')
  })

  it.each([
    [
      'the close button',
      async (user, dialog) =>
        user.click(within(dialog).getByRole('button', { name: 'Close filters' })),
    ],
    ['Escape', async (user) => user.keyboard('{Escape}')],
  ])('closing with %s discards the draft and returns focus', async (_, close) => {
    const { dialog, user, router } = await openDrawer()
    await user.click(within(dialog).getByRole('checkbox', { name: /^Electronics/ }))
    await close(user, dialog)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(router.state.location.search).toBe('?q=laptop')
    expect(screen.getByRole('button', { name: /^Filters/ })).toHaveFocus()
    expect(document.body.style.overflow).toBe('')
  })

  it('keeps Tab focus inside the dialog', async () => {
    const { dialog, user } = await openDrawer()
    const close = within(dialog).getByRole('button', { name: 'Close filters' })
    const apply = within(dialog).getByRole('button', { name: 'Show results' })
    await user.tab({ shift: true })
    expect(apply).toHaveFocus()
    await user.tab()
    expect(close).toHaveFocus()
  })

  it('disables "Show results" while a price is invalid', async () => {
    const { dialog, user } = await openDrawer()
    await user.type(within(dialog).getByRole('textbox', { name: 'Minimum price' }), '9.999')
    expect(await within(dialog).findByRole('alert')).toBeVisible()
    expect(within(dialog).getByRole('button', { name: 'Show results' })).toBeDisabled()
    await user.clear(within(dialog).getByRole('textbox', { name: 'Minimum price' }))
    await user.type(within(dialog).getByRole('textbox', { name: 'Minimum price' }), '10')
    await waitFor(() =>
      expect(within(dialog).getByRole('button', { name: 'Show results' })).toBeEnabled(),
    )
  })

  it('applies a draft price range from the drawer', async () => {
    const { dialog, user, router } = await openDrawer()
    await user.type(within(dialog).getByRole('textbox', { name: 'Minimum price' }), '50')
    await user.type(within(dialog).getByRole('textbox', { name: 'Maximum price' }), '150.25')
    await waitFor(() =>
      expect(within(dialog).getByRole('button', { name: 'Show results' })).toBeEnabled(),
    )
    await new Promise((resolve) => setTimeout(resolve, 50)) // draft update (0 ms debounce)
    await user.click(within(dialog).getByRole('button', { name: 'Show results' }))
    expect(router.state.location.search).toBe('?q=laptop&min_price=50&max_price=150.25')
  })
})
