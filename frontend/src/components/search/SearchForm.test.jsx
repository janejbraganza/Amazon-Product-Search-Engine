import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { routes } from '../../routes.jsx'
import { mockSearch, mockSuggestions } from '../../test/fixtures.js'
import { renderRoute } from '../../test/renderRoute.jsx'

// Vocabulary shaped like real index terms and product counts.
const WORDS = {
  laptop: 220,
  lamp: 168,
  label: 12,
  wireless: 380,
  earbud: 231,
  early: 145,
  ear: 96,
}

const box = () => screen.getByRole('combobox', { name: 'Search products' })
const options = () => screen.findAllByRole('option')
const listbox = () => screen.getByRole('listbox', { name: 'Search suggestions', hidden: true })

afterEach(() => {
  vi.useRealTimers()
})

describe('autocomplete: suggestions', () => {
  it('shows suggestions for the last word with product counts', async () => {
    const user = userEvent.setup()
    const requests = mockSuggestions({ words: WORDS })
    renderRoute('/')
    await user.type(box(), 'la')
    const items = await options()
    expect(items.map((o) => o.textContent)).toEqual([
      'laptop220 products',
      'lamp168 products',
      'label12 products',
    ])
    expect(requests.at(-1)).toMatchObject({ q: 'la', limit: '10' })
  })

  it('completes only the last word of a multi-word query', async () => {
    const user = userEvent.setup()
    mockSuggestions({ words: WORDS })
    renderRoute('/')
    await user.type(box(), 'wireless ea')
    await screen.findByRole('option', { name: /earbud/ })
    // "wireless" is not suggested: only the last word ("ea") is completed.
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual([
      'earbud231 products',
      'early145 products',
      'ear96 products',
    ])
  })

  it('shows a message when there are no suggestions', async () => {
    const user = userEvent.setup()
    mockSuggestions({ words: WORDS })
    renderRoute('/')
    await user.type(box(), 'xyzq')
    expect(
      await screen.findByText('No matching words. Press Enter to search anyway.'),
    ).toBeVisible()
    expect(screen.queryByRole('option')).not.toBeInTheDocument()
    expect(box()).toHaveAttribute('aria-expanded', 'true')
  })

  it('shows a non-blocking message when the suggestions API fails, and search still works', async () => {
    const user = userEvent.setup()
    mockSuggestions({ status: 500 })
    const { router } = renderRoute('/')
    await user.type(box(), 'lap')
    expect(
      await screen.findByText('Suggestions are unavailable. You can still search.'),
    ).toBeVisible()
    await user.keyboard('{Enter}')
    expect(router.state.location.search).toBe('?q=lap')
  })

  it('shows a loading message while suggestions are on their way', async () => {
    const user = userEvent.setup()
    mockSuggestions({ words: WORDS, delays: { lap: 'infinite' } })
    renderRoute('/')
    await user.type(box(), 'lap')
    expect(await screen.findByText('Loading suggestions…')).toBeVisible()
  })

  it('does not request suggestions for empty, whitespace-only or punctuation-only input', async () => {
    const user = userEvent.setup()
    const requests = mockSuggestions({ words: WORDS })
    renderRoute('/')
    await user.type(box(), '   ')
    await user.clear(box())
    await user.type(box(), '!!! -')
    await new Promise((resolve) => setTimeout(resolve, 300))
    expect(requests).toEqual([])
    expect(box()).toHaveAttribute('aria-expanded', 'false')
  })

  it('does not request suggestions for the query already in the box when a page loads', async () => {
    const requests = mockSuggestions({ words: WORDS })
    mockSearch()
    renderRoute('/search?q=laptop')
    await screen.findAllByRole('article')
    await new Promise((resolve) => setTimeout(resolve, 300))
    expect(requests).toEqual([])
    expect(box()).toHaveAttribute('aria-expanded', 'false')
  })

  it('answers repeated text from memory instead of asking the API again', async () => {
    const user = userEvent.setup()
    const requests = mockSuggestions({ words: WORDS })
    renderRoute('/')
    await user.type(box(), 'la')
    await options()
    await user.type(box(), 'p')
    await waitFor(() => expect(requests.map((r) => r.q)).toEqual(['la', 'lap']))
    await user.keyboard('{Backspace}')
    await waitFor(() =>
      expect(screen.getAllByRole('option').map((o) => o.textContent)).toHaveLength(3),
    )
    expect(requests.map((r) => r.q)).toEqual(['la', 'lap'])
  })
})

describe('autocomplete: debounce', () => {
  it('waits about 175 ms after the last key before asking the API', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const requests = mockSuggestions({ words: WORDS })
    renderRoute('/')
    await user.type(box(), 'lap')
    await act(() => vi.advanceTimersByTimeAsync(150))
    expect(requests).toEqual([])
    await act(() => vi.advanceTimersByTimeAsync(50))
    await waitFor(() => expect(requests.map((r) => r.q)).toEqual(['lap']))
  })

  it('sends one request for fast typing, not one per key', async () => {
    const user = userEvent.setup()
    const requests = mockSuggestions({ words: WORDS })
    renderRoute('/')
    await user.type(box(), 'wireless') // keys arrive faster than the debounce delay
    await options()
    expect(requests.map((r) => r.q)).toEqual(['wireless'])
  })
})

describe('autocomplete: keyboard and mouse', () => {
  async function openWith(text) {
    const user = userEvent.setup()
    mockSuggestions({ words: WORDS })
    const utils = renderRoute('/')
    await user.type(box(), text)
    await options()
    return { user, ...utils }
  }

  it('ArrowDown and ArrowUp move the highlight (with wrap-around)', async () => {
    const { user } = await openWith('la')
    const [laptop, lamp, label] = screen.getAllByRole('option')
    expect(box()).not.toHaveAttribute('aria-activedescendant')

    await user.keyboard('{ArrowDown}')
    expect(laptop).toHaveAttribute('aria-selected', 'true')
    expect(box()).toHaveAttribute('aria-activedescendant', laptop.id)
    await user.keyboard('{ArrowDown}{ArrowDown}')
    expect(label).toHaveAttribute('aria-selected', 'true')
    await user.keyboard('{ArrowDown}')
    expect(laptop).toHaveAttribute('aria-selected', 'true') // wrapped to the top
    await user.keyboard('{ArrowUp}')
    expect(label).toHaveAttribute('aria-selected', 'true') // wrapped to the bottom
    await user.keyboard('{ArrowUp}')
    expect(lamp).toHaveAttribute('aria-selected', 'true')
    expect(laptop).toHaveAttribute('aria-selected', 'false')
  })

  it('Enter picks the highlighted suggestion and searches for it', async () => {
    const { user, router } = await openWith('la')
    await user.keyboard('{ArrowDown}{ArrowDown}{Enter}')
    expect(router.state.location.pathname).toBe('/search')
    expect(router.state.location.search).toBe('?q=lamp')
    expect(box()).toHaveValue('lamp')
    expect(box()).toHaveAttribute('aria-expanded', 'false')
  })

  it('Enter without a highlighted suggestion submits the typed text (existing behaviour)', async () => {
    const { user, router } = await openWith('la')
    await user.keyboard('{Enter}')
    expect(router.state.location.search).toBe('?q=la')
  })

  it('Enter on a suggestion replaces only the last word', async () => {
    const { user, router } = await openWith('wireless ea')
    await user.keyboard('{ArrowDown}{Enter}')
    expect(router.state.location.search).toBe('?q=wireless+earbud')
  })

  it('a mouse click picks a suggestion and searches for it', async () => {
    const { user, router } = await openWith('la')
    await user.click(screen.getByRole('option', { name: /lamp/ }))
    expect(router.state.location.search).toBe('?q=lamp')
    expect(box()).toHaveValue('lamp')
  })

  it('hovering moves the highlight', async () => {
    const { user } = await openWith('la')
    await user.hover(screen.getByRole('option', { name: /label/ }))
    expect(screen.getByRole('option', { name: /label/ })).toHaveAttribute('aria-selected', 'true')
  })

  it('Escape closes the list and keeps the text', async () => {
    const { user } = await openWith('la')
    await user.keyboard('{Escape}')
    expect(box()).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('option')).not.toBeInTheDocument()
    expect(box()).toHaveValue('la')
  })

  it('ArrowDown re-opens a closed list', async () => {
    const { user } = await openWith('la')
    await user.keyboard('{Escape}{ArrowDown}')
    expect(await options()).toHaveLength(3)
  })

  it('Tab closes the list and moves focus normally', async () => {
    const { user } = await openWith('la')
    await user.tab()
    expect(screen.getByRole('button', { name: 'Search' })).toHaveFocus()
    expect(box()).toHaveAttribute('aria-expanded', 'false')
  })

  it('clicking elsewhere closes the list', async () => {
    const { user } = await openWith('la')
    await user.click(screen.getByRole('heading', { level: 1 }))
    expect(box()).toHaveAttribute('aria-expanded', 'false')
  })

  it('keys do nothing special while the list is closed', async () => {
    const user = userEvent.setup()
    mockSuggestions({ words: WORDS })
    const { router } = renderRoute('/')
    box().focus()
    await user.keyboard('{ArrowUp}{Escape}')
    expect(box()).toHaveAttribute('aria-expanded', 'false')
    expect(router.state.location.pathname).toBe('/')
  })

  it('typing again resets the highlight', async () => {
    const { user } = await openWith('la')
    await user.keyboard('{ArrowDown}')
    await user.type(box(), 'p')
    await waitFor(() => expect(box()).not.toHaveAttribute('aria-activedescendant'))
  })
})

describe('autocomplete: keeps search settings', () => {
  it('a picked suggestion keeps mode, exact words and page size, and starts on page 1', async () => {
    const user = userEvent.setup()
    mockSuggestions({ words: WORDS })
    mockSearch()
    const { router } = renderRoute('/search?q=old&mode=any&exact=1&page=3&per_page=40')
    await screen.findAllByRole('article')
    await user.clear(box())
    await user.type(box(), 'wireless ea')
    // Wait for the list for the full text (a pause while typing can show an earlier list).
    await user.click(await screen.findByRole('option', { name: /earbud/ }))
    expect(router.state.location.search).toBe('?q=wireless+earbud&mode=any&exact=1&per_page=40')
  })

  it('searching from a suggestion loads results for the completed query', async () => {
    const user = userEvent.setup()
    mockSuggestions({ words: WORDS })
    const searches = mockSearch()
    renderRoute('/')
    await user.type(box(), 'lap')
    await options()
    await user.keyboard('{ArrowDown}{Enter}')
    await screen.findAllByRole('article')
    expect(searches.at(-1)).toMatchObject({ q: 'laptop', prefix: 'true' }) // default kept
  })
})

describe('autocomplete: cancellation and stale responses', () => {
  it('cancels the previous request when the text changes', async () => {
    const user = userEvent.setup()
    const requests = mockSuggestions({ words: WORDS, delays: { la: 'infinite' } })
    renderRoute('/')
    await user.type(box(), 'la')
    await waitFor(() => expect(requests.map((r) => r.q)).toEqual(['la']))
    await user.type(box(), 'p')
    await options()
    expect(requests.map((r) => [r.q, r.aborted])).toEqual([
      ['la', true],
      ['lap', false],
    ])
  })

  it('an older, slower response never replaces newer suggestions', async () => {
    const user = userEvent.setup()
    // "la" answers after "lap"; if it were shown it would add lamp and label.
    mockSuggestions({ words: WORDS, delays: { la: 300 } })
    renderRoute('/')
    await user.type(box(), 'la')
    await new Promise((resolve) => setTimeout(resolve, 200)) // "la" request is in flight
    await user.type(box(), 'p')
    expect((await options()).map((o) => o.textContent)).toEqual(['laptop220 products'])
    await new Promise((resolve) => setTimeout(resolve, 300)) // "la" would arrive now
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['laptop220 products'])
  })

  it('does not show an error for a cancelled request', async () => {
    const user = userEvent.setup()
    mockSuggestions({ words: WORDS, delays: { la: 'infinite' } })
    renderRoute('/')
    await user.type(box(), 'la')
    await user.type(box(), 'p')
    await options()
    expect(screen.queryByText(/unavailable/)).not.toBeInTheDocument()
  })

  it('cancels the request when the search box unmounts', async () => {
    const user = userEvent.setup()
    const requests = mockSuggestions({ words: WORDS, delays: { lap: 'infinite' } })
    const router = createMemoryRouter(routes, { initialEntries: ['/'] })
    const { unmount } = render(<RouterProvider router={router} />)
    await user.type(box(), 'lap')
    await waitFor(() => expect(requests).toHaveLength(1))
    unmount()
    await waitFor(() => expect(requests[0].aborted).toBe(true))
  })
})

describe('autocomplete: accessibility', () => {
  it('uses the combobox / listbox / option roles and states', async () => {
    const user = userEvent.setup()
    mockSuggestions({ words: WORDS })
    renderRoute('/')
    const input = box()
    expect(input).toHaveAttribute('aria-autocomplete', 'list')
    expect(input).toHaveAttribute('aria-expanded', 'false')
    expect(input).toHaveAttribute('aria-controls', listbox().id)

    await user.type(input, 'la')
    const items = await options()
    expect(input).toHaveAttribute('aria-expanded', 'true')
    expect(within(listbox()).getAllByRole('option')).toHaveLength(3)
    items.forEach((item) => {
      expect(item.id).toMatch(new RegExp(`^${listbox().id}-\\d+$`))
      expect(item).toHaveAttribute('aria-selected', 'false')
    })
  })

  it('announces how many suggestions are available', async () => {
    const user = userEvent.setup()
    mockSuggestions({ words: WORDS })
    renderRoute('/')
    await user.type(box(), 'la')
    await options()
    expect(
      screen.getByText('3 suggestions available. Use the up and down arrow keys to choose one.'),
    ).toBeInTheDocument()
  })

  it('the header and home search boxes have different listbox ids', async () => {
    mockSearch()
    renderRoute('/search?q=laptop')
    expect(box().getAttribute('aria-controls')).toBe(listbox().id)
  })
})
