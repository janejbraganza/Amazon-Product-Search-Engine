import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { expectHeadingOutline } from '../test/a11y.js'
import { mockSearch } from '../test/fixtures.js'
import { renderRoute } from '../test/renderRoute.jsx'

/** The page's always-present polite live region (screen-reader announcements). */
const announcer = () =>
  [...document.querySelectorAll('[aria-live="polite"]')].find((el) =>
    el.closest('section[aria-labelledby="search-title"]'),
  )

describe('search page accessibility', () => {
  it('announces the results once they arrive, and again for the next page', async () => {
    const user = userEvent.setup()
    mockSearch({ total: 45 })
    renderRoute('/search?q=laptop')
    expect(announcer()).toBeInTheDocument()
    expect(announcer()).toHaveTextContent('') // the skeleton announces loading
    await waitFor(() =>
      expect(announcer()).toHaveTextContent('Results 1 to 20 of 45 for “laptop”.'),
    )
    await user.click(screen.getByRole('link', { name: 'Next page' }))
    await waitFor(() =>
      expect(announcer()).toHaveTextContent('Results 21 to 40 of 45 for “laptop”.'),
    )
  })

  it('announces when nothing matches', async () => {
    mockSearch({ total: 0 })
    renderRoute('/search?q=zzzz')
    await waitFor(() => expect(announcer()).toHaveTextContent('No products match “zzzz”.'))
  })

  it('has one h1 and no skipped heading levels', async () => {
    mockSearch({ total: 3 })
    renderRoute('/search?q=laptop')
    await screen.findAllByRole('article')
    expectHeadingOutline()
  })

  it('every form control has an accessible name', async () => {
    mockSearch({ total: 3 })
    renderRoute('/search?q=laptop')
    await screen.findAllByRole('article')
    const controls = [
      ...screen.getAllByRole('textbox'),
      ...screen.getAllByRole('combobox'),
      ...screen.getAllByRole('checkbox'),
      ...screen.getAllByRole('button'),
    ]
    for (const control of controls) {
      expect(control, control.outerHTML.slice(0, 80)).toHaveAccessibleName()
    }
  })

  it('the mobile filter drawer can be opened, used and closed with the keyboard only', async () => {
    const user = userEvent.setup()
    mockSearch({ total: 3 })
    renderRoute('/search?q=laptop')
    await screen.findAllByRole('article')
    const opener = screen.getByRole('button', { name: /^Filters/ })
    opener.focus()
    await user.keyboard('{Enter}')
    const dialog = screen.getByRole('dialog', { name: 'Filters' })
    expect(within(dialog).getByRole('button', { name: 'Close filters' })).toHaveFocus()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(opener).toHaveFocus()
  })
})
