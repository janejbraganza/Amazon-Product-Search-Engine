import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderRoute } from '../../test/renderRoute.jsx'
import { THEME_STORAGE_KEY } from '../../utils/theme.js'

const root = document.documentElement
const toggle = () => screen.getByRole('button', { name: 'Dark theme' })
const mainNav = () => within(screen.getByRole('navigation', { name: 'Main' }))

/** A fake operating-system colour preference (jsdom has no matchMedia). */
function mockSystemTheme(initial) {
  const listeners = new Set()
  const query = {
    matches: initial === 'dark',
    addEventListener: (_, listener) => listeners.add(listener),
    removeEventListener: (_, listener) => listeners.delete(listener),
  }
  window.matchMedia = vi.fn(() => query)
  return {
    change(theme) {
      query.matches = theme === 'dark'
      act(() => listeners.forEach((listener) => listener()))
    },
    listeners,
  }
}

afterEach(() => {
  localStorage.clear()
  delete root.dataset.theme
  delete window.matchMedia
})

describe('theme toggle', () => {
  it('follows the operating system when nothing was chosen', () => {
    mockSystemTheme('dark')
    renderRoute('/')
    expect(toggle()).toHaveAttribute('aria-pressed', 'true')
    expect(toggle()).toHaveAttribute('title', 'Switch to light theme')
    expect(root).not.toHaveAttribute('data-theme') // CSS follows the system by itself
  })

  it('defaults to light when the system preference cannot be read', () => {
    renderRoute('/')
    expect(toggle()).toHaveAttribute('aria-pressed', 'false')
    expect(toggle()).toHaveAttribute('title', 'Switch to dark theme')
  })

  it('switches theme, sets <html data-theme> and remembers the choice', async () => {
    const user = userEvent.setup()
    mockSystemTheme('light')
    renderRoute('/')
    await user.click(toggle())
    expect(toggle()).toHaveAttribute('aria-pressed', 'true')
    expect(root.dataset.theme).toBe('dark')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')

    await user.click(toggle())
    expect(toggle()).toHaveAttribute('aria-pressed', 'false')
    expect(root.dataset.theme).toBe('light')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('light')
  })

  it('restores a saved choice on the next visit, even against the system setting', () => {
    mockSystemTheme('light')
    localStorage.setItem(THEME_STORAGE_KEY, 'dark')
    renderRoute('/search?q=laptop')
    expect(toggle()).toHaveAttribute('aria-pressed', 'true')
    expect(root.dataset.theme).toBe('dark')
  })

  it('ignores an unknown saved value', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'neon')
    renderRoute('/')
    expect(toggle()).toHaveAttribute('aria-pressed', 'false')
    expect(root).not.toHaveAttribute('data-theme')
  })

  it('updates live when the system setting changes, until a choice is made', async () => {
    const user = userEvent.setup()
    const system = mockSystemTheme('light')
    renderRoute('/')
    system.change('dark')
    expect(toggle()).toHaveAttribute('aria-pressed', 'true')

    await user.click(toggle()) // choose light explicitly
    system.change('dark')
    expect(toggle()).toHaveAttribute('aria-pressed', 'false')
  })

  it('keeps the theme on every page (one shared header)', async () => {
    const user = userEvent.setup()
    const { router } = renderRoute('/')
    await user.click(toggle())
    await act(() => router.navigate('/search?q=laptop'))
    expect(toggle()).toHaveAttribute('aria-pressed', 'true')
    await act(() => router.navigate('/products/42'))
    expect(toggle()).toHaveAttribute('aria-pressed', 'true')
    expect(root.dataset.theme).toBe('dark')
  })

  it('still works when storage is blocked (the choice just is not saved)', async () => {
    const user = userEvent.setup()
    vi.spyOn(Object.getPrototypeOf(localStorage), 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    renderRoute('/')
    await user.click(toggle())
    expect(toggle()).toHaveAttribute('aria-pressed', 'true')
    expect(root.dataset.theme).toBe('dark')
  })

  it('is reachable and operable with the keyboard', async () => {
    const user = userEvent.setup()
    renderRoute('/search?q=laptop')
    toggle().focus()
    await user.keyboard('{Enter}')
    expect(toggle()).toHaveAttribute('aria-pressed', 'true')
    await user.keyboard(' ')
    expect(toggle()).toHaveAttribute('aria-pressed', 'false')
  })
})

describe('header navigation', () => {
  it('has a labelled main navigation with Home and Categories', () => {
    renderRoute('/search?q=laptop')
    expect(mainNav().getByRole('link', { name: 'Home' })).toHaveAttribute('href', '/')
    expect(mainNav().getByRole('link', { name: 'Categories' })).toHaveAttribute(
      'href',
      '/#categories',
    )
    expect(screen.getByRole('link', { name: 'Product Search home' })).toHaveAttribute('href', '/')
  })

  it('marks Home as the current page only on the home page', async () => {
    const { router } = renderRoute('/')
    expect(mainNav().getByRole('link', { name: 'Home' })).toHaveAttribute('aria-current', 'page')
    await act(() => router.navigate('/search?q=laptop'))
    expect(mainNav().getByRole('link', { name: 'Home' })).not.toHaveAttribute('aria-current')
  })

  it('Home goes back to the home page from a search', async () => {
    const user = userEvent.setup()
    const { router } = renderRoute('/search?q=laptop')
    await user.click(mainNav().getByRole('link', { name: 'Home' }))
    expect(router.state.location.pathname).toBe('/')
    expect(screen.getByRole('heading', { level: 1, name: /find the right product/i })).toBeVisible()
  })

  it('Categories opens the home page and moves focus to the category section', async () => {
    const user = userEvent.setup()
    const { router } = renderRoute('/search?q=laptop')
    await user.click(mainNav().getByRole('link', { name: 'Categories' }))
    expect(router.state.location.hash).toBe('#categories')
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Browse by category' })).toHaveFocus(),
    )
  })

  it('shows the header search box on every page except home', async () => {
    const { router } = renderRoute('/')
    expect(screen.getAllByRole('search')).toHaveLength(1) // the hero box only
    await act(() => router.navigate('/products/42'))
    expect(within(screen.getByRole('banner')).getByRole('search')).toBeInTheDocument()
    await act(() => router.navigate('/no/such/page'))
    expect(within(screen.getByRole('banner')).getByRole('search')).toBeInTheDocument()
  })

  it('has a footer navigation and states that the data is synthetic', () => {
    renderRoute('/')
    const footer = within(screen.getByRole('contentinfo'))
    expect(footer.getByText(/synthetic demo data/)).toBeInTheDocument()
    expect(footer.getByRole('link', { name: 'Browse categories' })).toHaveAttribute(
      'href',
      '/#categories',
    )
    expect(footer.queryByText(/10,000/)).not.toBeInTheDocument() // no hard-coded statistics
  })

  it('the skip link moves focus to the main content', async () => {
    const user = userEvent.setup()
    renderRoute('/search?q=laptop')
    await user.tab()
    expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveFocus()
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content')
    expect(screen.getByRole('main')).toHaveAttribute('tabindex', '-1') // focusable target
  })
})
