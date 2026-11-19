import { describe, expect, it } from 'vitest'
import { formatCount, formatPrice, formatRating, stockStatus } from './format.js'
import { highlightTerms } from './highlight.js'
import { ELLIPSIS, getPageItems, pageCount } from './pagination.js'
import {
  buildSearchParams,
  NO_FILTERS,
  parseSearchState,
  searchUrl,
  toApiParams,
} from './searchState.js'

const parse = (query) => parseSearchState(new URLSearchParams(query))

describe('parseSearchState', () => {
  it('reads every option from the URL', () => {
    expect(parse('q=wireless+ear&mode=any&exact=1&page=3&per_page=40')).toEqual({
      q: 'wireless ear',
      mode: 'any',
      exact: true,
      ...NO_FILTERS,
      sort: 'relevance',
      page: 3,
      perPage: 40,
    })
  })

  it('uses defaults when options are missing', () => {
    expect(parse('q=laptop')).toEqual({
      q: 'laptop',
      mode: 'all',
      exact: false,
      sort: 'relevance',
      ...NO_FILTERS,
      page: 1,
      perPage: 20,
    })
  })

  it.each([
    ['mode=maybe', { mode: 'all' }],
    ['page=0', { page: 1 }],
    ['page=-2', { page: 1 }],
    ['page=2.5', { page: 1 }],
    ['page=abc', { page: 1 }],
    ['per_page=33', { perPage: 20 }],
    ['per_page=1000', { perPage: 20 }],
    ['exact=yes', { exact: false }],
  ])('falls back to defaults for invalid %s', (query, expected) => {
    expect(parse(`q=x&${query}`)).toMatchObject(expected)
  })

  it('trims the query', () => {
    expect(parse('q=%20%20laptop%20').q).toBe('laptop')
  })
})

describe('buildSearchParams / searchUrl', () => {
  it('leaves defaults out of the URL', () => {
    expect(searchUrl({ q: 'laptop', mode: 'all', exact: false, page: 1, perPage: 20 })).toBe(
      '/search?q=laptop',
    )
  })

  it('writes non-default options', () => {
    expect(
      buildSearchParams({ q: 'a b', mode: 'any', exact: true, page: 2, perPage: 60 }).toString(),
    ).toBe('q=a+b&mode=any&exact=1&page=2&per_page=60')
  })

  it('round-trips through parseSearchState', () => {
    const state = {
      q: 'stainless steel',
      mode: 'any',
      exact: true,
      sort: 'price_desc',
      categories: ['Electronics', 'Home & Kitchen'],
      brands: ['Voltrix'],
      minPrice: '49.99',
      maxPrice: '200',
      minRating: '4.5',
      inStock: true,
      page: 4,
      perPage: 40,
    }
    expect(parseSearchState(buildSearchParams(state))).toEqual(state)
  })
})

describe('toApiParams', () => {
  it('turns on prefix matching by default and computes the offset', () => {
    expect(toApiParams({ q: 'lap', mode: 'all', exact: false, page: 3, perPage: 20 })).toEqual({
      q: 'lap',
      mode: 'all',
      prefix: true,
      limit: 20,
      offset: 40,
    })
  })

  it('turns prefix matching off for exact words', () => {
    expect(toApiParams({ q: 'ear', mode: 'any', exact: true, page: 1, perPage: 60 })).toMatchObject(
      {
        prefix: false,
        limit: 60,
        offset: 0,
      },
    )
  })
})

describe('pagination', () => {
  it('counts pages', () => {
    expect(pageCount(0, 20)).toBe(1)
    expect(pageCount(20, 20)).toBe(1)
    expect(pageCount(21, 20)).toBe(2)
    expect(pageCount(231, 20)).toBe(12)
  })

  it.each([
    [1, 1, [1]],
    [1, 5, [1, 2, 3, 4, 5]],
    [1, 12, [1, 2, ELLIPSIS, 12]],
    [5, 12, [1, ELLIPSIS, 4, 5, 6, ELLIPSIS, 12]],
    [3, 12, [1, 2, 3, 4, ELLIPSIS, 12]], // a gap of one page shows the page instead
    [12, 12, [1, ELLIPSIS, 11, 12]],
    [4, 7, [1, 2, 3, 4, 5, 6, 7]],
  ])('page %i of %i -> %j', (current, total, expected) => {
    expect(getPageItems(current, total)).toEqual(expected)
  })
})

describe('format', () => {
  it('formats prices, counts and ratings (numbers or numeric strings)', () => {
    expect(formatPrice(1226.99)).toBe('$1,226.99')
    expect(formatPrice('3.95')).toBe('$3.95')
    expect(formatCount(10000)).toBe('10,000')
    expect(formatRating(4)).toBe('4.0')
    expect(formatRating('4.25')).toBe('4.3')
  })

  it.each([
    [0, 'Out of stock', 'danger'],
    [1, 'Only 1 left', 'warning'],
    [10, 'Only 10 left', 'warning'],
    [11, 'In stock', 'success'],
  ])('stock %i -> %s', (quantity, label, tone) => {
    expect(stockStatus(quantity)).toEqual({ label, tone })
  })
})

describe('highlightTerms', () => {
  const marked = (text, terms) =>
    highlightTerms(text, terms)
      .filter((part) => part.match)
      .map((part) => part.text)

  it('marks words that start with a processed term', () => {
    expect(marked('Voltrix Flex Wireless Earbuds, Graphite', ['wireless', 'earbud'])).toEqual([
      'Wireless',
      'Earbuds',
    ])
  })

  it('is case-insensitive and reproduces the text exactly', () => {
    const parts = highlightTerms('USB-C Laptop Stand', ['laptop'])
    expect(parts.map((p) => p.text).join('')).toBe('USB-C Laptop Stand')
    expect(marked('USB-C Laptop Stand', ['LAPTOP'])).toEqual(['Laptop'])
  })

  it('requires short terms to match a whole word', () => {
    expect(marked('USB-C Charging Cable', ['c'])).toEqual(['C'])
  })

  it('returns the text unchanged without terms', () => {
    expect(highlightTerms('Laptop', [])).toEqual([{ text: 'Laptop', match: false }])
  })
})
