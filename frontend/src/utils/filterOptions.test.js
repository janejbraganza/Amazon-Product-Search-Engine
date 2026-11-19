import { describe, expect, it } from 'vitest'
import { brandOptions, categoryOptions, toggleValue, validatePriceRange } from './filterOptions.js'
import {
  activeFilterCount,
  buildSearchParams,
  NO_FILTERS,
  parsePrice,
  parseRating,
  parseSearchState,
  SORT_OPTIONS,
  toApiParams,
} from './searchState.js'

const parse = (query) => parseSearchState(new URLSearchParams(query))

describe('price and rating values (same rules as the backend)', () => {
  it.each(['0', '50', '49.9', '49.99', '99999999.99'])('accepts price %s', (value) => {
    expect(parsePrice(value)).toBe(value)
  })

  it.each(['', '-1', '1.234', 'abc', '1e3', '100000000', '12.', '.5'])(
    'rejects price %j',
    (value) => {
      expect(parsePrice(value)).toBeNull()
    },
  )

  it.each(['0', '4', '4.5', '5', '5.0'])('accepts rating %s', (value) => {
    expect(parseRating(value)).toBe(value)
  })

  it.each(['-1', '5.5', '6', '4.25', 'x', ''])('rejects rating %j', (value) => {
    expect(parseRating(value)).toBeNull()
  })
})

describe('filters in the URL', () => {
  it('reads repeated categories and brands, trims them and drops blanks and duplicates', () => {
    const state = parse(
      'q=x&category=Electronics&category=%20Books%20&category=electronics&category=&brand=Voltrix&brand=VOLTRIX',
    )
    expect(state.categories).toEqual(['Electronics', 'Books'])
    expect(state.brands).toEqual(['Voltrix'])
  })

  it('keeps at most 20 values per filter (backend limit)', () => {
    const query = Array.from({ length: 25 }, (_, i) => `category=c${i}`).join('&')
    expect(parse(`q=x&${query}`).categories).toHaveLength(20)
  })

  it('reads prices, rating, stock and sort', () => {
    expect(
      parse('q=x&min_price=50&max_price=199.99&min_rating=4.5&in_stock=true&sort=price_asc'),
    ).toMatchObject({
      minPrice: '50',
      maxPrice: '199.99',
      minRating: '4.5',
      inStock: true,
      sort: 'price_asc',
    })
  })

  it('ignores invalid filter values instead of breaking the page', () => {
    expect(
      parse('q=x&min_price=-5&max_price=abc&min_rating=9&in_stock=maybe&sort=cheapest'),
    ).toMatchObject({ ...NO_FILTERS, sort: 'relevance' })
  })

  it('writes filters with the backend parameter names, repeated values and no defaults', () => {
    const params = buildSearchParams({
      q: 'laptop',
      sort: 'rating',
      categories: ['Electronics', 'Home & Kitchen'],
      brands: ['Voltrix', 'Nexora'],
      minPrice: '50',
      maxPrice: '200',
      minRating: '4',
      inStock: true,
      page: 1,
    })
    expect(params.toString()).toBe(
      'q=laptop&sort=rating&category=Electronics&category=Home+%26+Kitchen&brand=Voltrix&brand=Nexora&min_price=50&max_price=200&min_rating=4&in_stock=true',
    )
    expect(buildSearchParams({ q: 'laptop', ...NO_FILTERS }).toString()).toBe('q=laptop')
  })

  it('every sort option has the exact backend value', () => {
    expect(SORT_OPTIONS.map((o) => [o.value, o.label])).toEqual([
      ['relevance', 'Relevance'],
      ['price_asc', 'Price: Low to High'],
      ['price_desc', 'Price: High to Low'],
      ['rating', 'Customer Rating'],
      ['newest', 'Newest First'],
    ])
  })

  it('API parameters leave out inactive filters and the default sort', () => {
    const base = { q: 'x', mode: 'all', exact: false, page: 1, perPage: 20 }
    const params = toApiParams({ ...base, ...NO_FILTERS, sort: 'relevance' })
    expect(Object.entries(params).filter(([, v]) => v !== undefined)).toEqual([
      ['q', 'x'],
      ['mode', 'all'],
      ['prefix', true],
      ['limit', 20],
      ['offset', 0],
    ])
  })

  it('API parameters include every active filter', () => {
    expect(
      toApiParams({
        q: 'x',
        mode: 'any',
        exact: true,
        sort: 'newest',
        categories: ['Books'],
        brands: ['A', 'B'],
        minPrice: '1.5',
        maxPrice: '9',
        minRating: '3',
        inStock: true,
        page: 2,
        perPage: 40,
      }),
    ).toEqual({
      q: 'x',
      mode: 'any',
      prefix: false,
      limit: 40,
      offset: 40,
      sort: 'newest',
      category: ['Books'],
      brand: ['A', 'B'],
      min_price: '1.5',
      max_price: '9',
      min_rating: '3',
      in_stock: true,
    })
  })

  it('counts active filters (a price range counts once)', () => {
    expect(activeFilterCount({ ...NO_FILTERS })).toBe(0)
    expect(
      activeFilterCount({
        categories: ['A', 'B'],
        brands: ['C'],
        minPrice: '1',
        maxPrice: '2',
        minRating: '4',
        inStock: true,
      }),
    ).toBe(6)
  })
})

describe('filter options', () => {
  const catalogue = [
    { name: 'Electronics', product_count: 1567 },
    { name: 'Books', product_count: 801 },
  ]
  const facets = {
    categories: [{ value: 'Electronics', count: 40 }],
    brands: [
      { value: 'Voltrix', count: 30 },
      { value: 'Nexora', count: 10 },
    ],
  }

  it('lists every catalogue category with counts from the facets (0 when absent)', () => {
    expect(categoryOptions(catalogue, facets, [])).toEqual([
      { value: 'Electronics', count: 40 },
      { value: 'Books', count: 0 },
    ])
  })

  it('has no counts while facets are unknown', () => {
    expect(categoryOptions(catalogue, null, []).map((o) => o.count)).toEqual([undefined, undefined])
  })

  it('adds categories from the facets or the URL that the catalogue list lacks', () => {
    expect(categoryOptions([], facets, ['Toys']).map((o) => o.value)).toEqual([
      'Electronics',
      'Toys',
    ])
    expect(categoryOptions(catalogue, facets, ['electronics'])).toHaveLength(2) // case-insensitive
  })

  it('lists brands from the facets, plus selected brands without results', () => {
    expect(brandOptions(facets, ['Orbix'])).toEqual([
      { value: 'Voltrix', count: 30 },
      { value: 'Nexora', count: 10 },
      { value: 'Orbix', count: 0 },
    ])
    expect(brandOptions(null, ['Orbix'])).toEqual([{ value: 'Orbix', count: undefined }])
  })

  it('toggles values case-insensitively', () => {
    expect(toggleValue(['Voltrix'], 'Nexora')).toEqual(['Voltrix', 'Nexora'])
    expect(toggleValue(['Voltrix', 'Nexora'], 'VOLTRIX')).toEqual(['Nexora'])
  })

  it.each([
    ['', '', { min: null, max: null, error: null }],
    ['50', '', { min: '50', max: null, error: null }],
    ['', '199.99', { min: null, max: '199.99', error: null }],
    ['50', '50', { min: '50', max: '50', error: null }],
  ])('accepts min %j max %j', (min, max, expected) => {
    expect(validatePriceRange(min, max)).toEqual(expected)
  })

  it.each([
    ['1.234', '', /minimum price like/],
    ['-1', '', /minimum price like/],
    ['', 'abc', /maximum price like/],
    ['200', '50', /must not be more than the maximum/],
  ])('rejects min %j max %j', (min, max, message) => {
    expect(validatePriceRange(min, max).error).toMatch(message)
  })
})
