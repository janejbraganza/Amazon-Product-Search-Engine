import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { renderRoute } from './test/renderRoute.jsx'

describe('routing', () => {
  it('renders the home page with a large search box and example links', () => {
    renderRoute('/')
    expect(screen.getByRole('heading', { level: 1, name: /find the right product/i })).toBeVisible()
    expect(screen.getAllByRole('search')).toHaveLength(1) // header search is hidden on home
    expect(screen.getByRole('link', { name: 'wireless earbuds' })).toHaveAttribute(
      'href',
      '/search?q=wireless+earbuds',
    )
  })

  it('renders the search page for a query', () => {
    renderRoute('/search?q=laptop')
    expect(screen.getByRole('heading', { level: 1, name: 'Results for “laptop”' })).toBeVisible()
    expect(screen.getByRole('search')).toBeVisible() // header search
  })

  it('redirects an empty search to the home page', async () => {
    const { router } = renderRoute('/search?q=%20%20')
    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
  })

  it('renders the product page', async () => {
    renderRoute('/products/42')
    expect(
      await screen.findByRole('heading', { level: 1, name: /Brightnest Artisan Air Fryer/ }),
    ).toBeVisible()
  })

  it('renders a 404 page for unknown routes', () => {
    renderRoute('/no/such/page')
    expect(screen.getByRole('heading', { level: 1, name: 'Page not found' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Go to search' })).toHaveAttribute('href', '/')
  })

  it('has a skip link and landmarks on every page', () => {
    renderRoute('/search?q=laptop')
    expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveAttribute(
      'href',
      '#main-content',
    )
    expect(screen.getByRole('banner')).toBeInTheDocument()
    expect(screen.getByRole('main')).toBeInTheDocument()
    expect(screen.getByRole('contentinfo')).toBeInTheDocument()
  })
})

describe('search form', () => {
  it('submits the trimmed query to /search', async () => {
    const user = userEvent.setup()
    const { router } = renderRoute('/')
    await user.type(
      screen.getByRole('combobox', { name: 'Search products' }),
      '  wireless earbuds  ',
    )
    await user.click(screen.getByRole('button', { name: 'Search' }))
    expect(router.state.location.pathname).toBe('/search')
    expect(router.state.location.search).toBe('?q=wireless+earbuds')
  })

  it('submits with the Enter key', async () => {
    const user = userEvent.setup()
    const { router } = renderRoute('/')
    await user.type(screen.getByRole('combobox', { name: 'Search products' }), 'laptop{Enter}')
    expect(router.state.location.search).toBe('?q=laptop')
  })

  it('does nothing for a blank query', async () => {
    const user = userEvent.setup()
    const { router } = renderRoute('/')
    await user.type(screen.getByRole('combobox', { name: 'Search products' }), '   {Enter}')
    expect(router.state.location.pathname).toBe('/')
  })

  it('shows the current query in the header search box', () => {
    renderRoute('/search?q=yoga+mat')
    expect(screen.getByRole('combobox', { name: 'Search products' })).toHaveValue('yoga mat')
  })

  it('updates the header search box when the URL changes', async () => {
    const { router } = renderRoute('/search?q=laptop')
    await router.navigate('/search?q=mystery+novel')
    await waitFor(() =>
      expect(screen.getByRole('combobox', { name: 'Search products' })).toHaveValue(
        'mystery novel',
      ),
    )
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('mystery novel')
  })
})
