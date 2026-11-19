/**
 * Live: autocomplete against the real backend through the Vite proxy (no mocks).
 * Expected suggestions are fetched from the real API in each test, never hard-coded guesses.
 * Run with `npm run test:live` while the backend and `npm run dev` are running.
 */
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { renderRoute } from '../../test/renderRoute.jsx'

const TIMEOUT = { timeout: 15_000 }
const box = () => screen.getByRole('combobox', { name: 'Search products' })

/** The real API's suggestions for ``q``, formatted the way the dropdown shows them. */
async function apiSuggestions(q) {
  const response = await fetch(
    `${window.location.origin}/api/v1/search/suggestions?${new URLSearchParams({ q, limit: '10' })}`,
  )
  expect(response.status).toBe(200)
  const { suggestions } = await response.json()
  return suggestions.map(
    (s) =>
      `${s.term}${s.product_count.toLocaleString('en-US')} ${s.product_count === 1 ? 'product' : 'products'}`,
  )
}

const shownOptions = () => screen.getAllByRole('option').map((o) => o.textContent)

async function typeAndWaitFor(user, text) {
  const expected = await apiSuggestions(text)
  await user.type(box(), text)
  await waitFor(() => expect(shownOptions()).toEqual(expected), TIMEOUT)
  return expected
}

async function resultsSummary() {
  return (await screen.findByText(/^Showing/, {}, TIMEOUT)).textContent
}

describe('live: autocomplete via the Vite proxy', () => {
  it('"lap" shows the real suggestions', async () => {
    const user = userEvent.setup()
    renderRoute('/')
    const expected = await typeAndWaitFor(user, 'lap')
    expect(expected[0]).toBe('laptop220 products')
  })

  it('"wireless" shows the real suggestions', async () => {
    const user = userEvent.setup()
    renderRoute('/')
    const expected = await typeAndWaitFor(user, 'wireless')
    expect(expected[0]).toBe('wireless380 products')
  })

  it('"ear" shows the real suggestions', async () => {
    const user = userEvent.setup()
    renderRoute('/')
    const expected = await typeAndWaitFor(user, 'ear')
    expect(expected).toEqual(['earbud231 products', 'early145 products', 'ear96 products'])
  })

  it('mouse: clicking a suggestion searches for the completed query', async () => {
    const user = userEvent.setup()
    const { router } = renderRoute('/')
    await typeAndWaitFor(user, 'wireless ea')
    await user.click(screen.getByRole('option', { name: /^earbud/ }))
    expect(router.state.location.search).toBe('?q=wireless+earbud')
    expect(await resultsSummary()).toBe('Showing 1–20 of 231 results for “wireless earbud”')
  })

  it('keyboard: ArrowDown/ArrowUp move the highlight and Enter picks it', async () => {
    const user = userEvent.setup()
    const { router } = renderRoute('/')
    await typeAndWaitFor(user, 'ear')
    const [earbud, early, ear] = screen.getAllByRole('option')
    await user.keyboard('{ArrowDown}{ArrowDown}')
    expect(early).toHaveAttribute('aria-selected', 'true')
    await user.keyboard('{ArrowDown}')
    expect(ear).toHaveAttribute('aria-selected', 'true')
    await user.keyboard('{ArrowUp}{ArrowUp}')
    expect(earbud).toHaveAttribute('aria-selected', 'true')
    await user.keyboard('{Enter}')
    expect(router.state.location.search).toBe('?q=earbud')
    expect(await resultsSummary()).toBe('Showing 1–20 of 231 results for “earbud”')
  })

  it('Escape closes the dropdown', async () => {
    const user = userEvent.setup()
    renderRoute('/')
    await typeAndWaitFor(user, 'lap')
    await user.keyboard('{Escape}')
    expect(box()).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('option')).not.toBeInTheDocument()
  })

  it('fast typing: the list always matches the final text, never an earlier one', async () => {
    const user = userEvent.setup()
    renderRoute('/')
    const forE = await typeAndWaitFor(user, 'e') // a list for "e" is on screen
    const forEar = await apiSuggestions('ear')
    expect(forE).not.toEqual(forEar)
    await user.type(box(), 'ar') // quickly continue to "ear"
    await waitFor(() => expect(shownOptions()).toEqual(forEar), TIMEOUT)
    await new Promise((resolve) => setTimeout(resolve, 500))
    expect(shownOptions()).toEqual(forEar)
  })

  it('normal search still works after picking a suggestion', async () => {
    const user = userEvent.setup()
    const { router } = renderRoute('/')
    await typeAndWaitFor(user, 'lap')
    await user.keyboard('{ArrowDown}{Enter}')
    expect(await resultsSummary()).toBe('Showing 1–20 of 220 results for “laptop”')

    await user.clear(box())
    await user.type(box(), 'yoga mat{Enter}')
    expect(router.state.location.search).toBe('?q=yoga+mat')
    await waitFor(
      async () => expect(await resultsSummary()).toBe('Showing 1–20 of 174 results for “yoga mat”'),
      TIMEOUT,
    )
  })
})
