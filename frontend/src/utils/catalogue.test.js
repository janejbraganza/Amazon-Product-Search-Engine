import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  brandUrl,
  categoryIcon,
  categoryUrl,
  isValidProductId,
  returnToSearch,
  similarQuery,
} from './catalogue.js'
import { formatDate } from './format.js'
import {
  applyTheme,
  readStoredTheme,
  storeTheme,
  subscribeToSystemTheme,
  systemTheme,
  THEME_STORAGE_KEY,
} from './theme.js'

describe('category and brand links', () => {
  it('browses a category by searching its name within that category', () => {
    expect(categoryUrl('Electronics')).toBe('/search?q=Electronics&category=Electronics')
    expect(categoryUrl('Home & Kitchen')).toBe(
      '/search?q=Home+%26+Kitchen&category=Home+%26+Kitchen',
    )
  })

  it('browses a brand by searching its name within that brand', () => {
    expect(brandUrl('Kestrel Labs')).toBe('/search?q=Kestrel+Labs&brand=Kestrel+Labs')
  })

  it('has an icon for every catalogue category and a fallback for unknown ones', () => {
    const categories = [
      'Automotive',
      'Beauty & Personal Care',
      'Books',
      'Clothing',
      'Electronics',
      'Grocery & Gourmet Food',
      'Home & Kitchen',
      'Office Supplies',
      'Sports & Outdoors',
      'Toys & Games',
    ]
    const icons = categories.map(categoryIcon)
    expect(icons).not.toContain('package')
    expect(new Set(icons).size).toBe(categories.length) // every category looks different
    expect(categoryIcon('Garden')).toBe('package')
  })
})

describe('isValidProductId', () => {
  it.each(['1', '42', '10000', '9223372036854775807'])('accepts %s', (id) => {
    expect(isValidProductId(id)).toBe(true)
  })

  it.each([
    'abc',
    '0',
    '-1',
    '1.5',
    '01',
    ' 42',
    '42 ',
    '1e3',
    '',
    '9223372036854775808', // BIGINT max + 1
    '99999999999999999999',
  ])('rejects %j', (id) => {
    expect(isValidProductId(id)).toBe(false)
  })

  it('rejects non-strings', () => {
    expect(isValidProductId(undefined)).toBe(false)
    expect(isValidProductId(42)).toBe(false)
  })
})

describe('returnToSearch', () => {
  it('returns the search a product was opened from, with its query', () => {
    expect(returnToSearch({ fromSearch: '/search?q=laptop&sort=price_asc&page=2' })).toEqual({
      path: '/search?q=laptop&sort=price_asc&page=2',
      query: 'laptop',
    })
  })

  it.each([
    null,
    undefined,
    {},
    { fromSearch: 42 },
    { fromSearch: 'https://example.com/search?q=x' }, // never leaves the app
    { fromSearch: '//example.com/search?q=x' },
    { fromSearch: '/products/1' },
    { fromSearch: '/search?sort=rating' }, // no query
    { fromSearch: '/search?q=%20%20' },
  ])('ignores %j', (state) => {
    expect(returnToSearch(state)).toBeNull()
  })
})

describe('similarQuery', () => {
  it('uses the product name, with spaces tidied', () => {
    expect(similarQuery('  Voltrix   Pro Laptop, 14-inch ')).toBe('Voltrix Pro Laptop, 14-inch')
  })

  it('cuts long names at a word boundary to fit the 200-character API limit', () => {
    const name = `${'word '.repeat(60)}end`
    const query = similarQuery(name)
    expect(query.length).toBeLessThanOrEqual(200)
    expect(query.endsWith('word')).toBe(true)
    expect(name.startsWith(query)).toBe(true)
  })

  it('cuts a single very long word at 200 characters', () => {
    expect(similarQuery('x'.repeat(300))).toHaveLength(200)
  })
})

describe('formatDate', () => {
  it('formats an API timestamp as a UTC date', () => {
    expect(formatDate('2025-05-28T05:13:52Z')).toBe('May 28, 2025')
    expect(formatDate('2025-12-31T23:59:59Z')).toBe('December 31, 2025') // not shifted
  })

  it('returns null for an unreadable date', () => {
    expect(formatDate('not a date')).toBeNull()
  })
})

describe('theme helpers', () => {
  afterEach(() => {
    localStorage.clear()
    delete document.documentElement.dataset.theme
    delete window.matchMedia
  })

  it('reads and stores the choice, ignoring unknown values', () => {
    expect(readStoredTheme()).toBeNull()
    expect(storeTheme('dark')).toBe(true)
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
    expect(readStoredTheme()).toBe('dark')
    localStorage.setItem(THEME_STORAGE_KEY, 'purple')
    expect(readStoredTheme()).toBeNull()
  })

  it('survives blocked storage', () => {
    // Spy on the prototype: jsdom's Storage (Node < 25) treats properties set on the
    // instance as stored items, so only the prototype methods can be replaced.
    vi.spyOn(Object.getPrototypeOf(localStorage), 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Object.getPrototypeOf(localStorage), 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(readStoredTheme()).toBeNull()
    expect(storeTheme('dark')).toBe(false)
  })

  it('sets and removes <html data-theme>', () => {
    applyTheme('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
    applyTheme(null)
    expect(document.documentElement).not.toHaveAttribute('data-theme')
  })

  it('reads the operating-system preference (light when it cannot be read)', () => {
    expect(systemTheme()).toBe('light') // jsdom has no matchMedia
    expect(subscribeToSystemTheme(() => {})).toBeTypeOf('function')
    window.matchMedia = () => ({ matches: true })
    expect(systemTheme()).toBe('dark')
  })
})
