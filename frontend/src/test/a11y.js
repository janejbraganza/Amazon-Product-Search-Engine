import { screen } from '@testing-library/react'
import { expect } from 'vitest'

/**
 * Check the page's heading outline: exactly one h1, and no level skipped on the way down
 * (h1 -> h3 without an h2 is an error; going back up, e.g. h3 -> h2, is fine).
 */
export function expectHeadingOutline() {
  const headings = screen
    .getAllByRole('heading', { hidden: true })
    .map((h) => ({ level: Number(h.tagName.slice(1)), text: h.textContent }))
  expect(headings.filter((h) => h.level === 1)).toHaveLength(1)
  expect(headings[0].level).toBe(1)
  headings.forEach((heading, i) => {
    if (i === 0) return
    const jump = heading.level - headings[i - 1].level
    expect(
      jump,
      `"${heading.text}" (h${heading.level}) after h${headings[i - 1].level}`,
    ).toBeLessThanOrEqual(1)
  })
  return headings
}
