/**
 * Search state <-> URL. The URL is the single source of truth for the results page, so
 * refresh, Back/Forward and shared links all reproduce the same search.
 *
 *   /search?q=laptop&mode=any&exact=1&sort=price_asc&category=Electronics&category=Books
 *          &brand=Voltrix&min_price=50&max_price=200&min_rating=4&in_stock=true&page=2&per_page=40
 *
 * Filter and sort parameters use the same names and values as the backend API.
 * Defaults are left out of the URL (mode=all, partial-word matching on, relevance, no
 * filters, page 1, 20 per page). Invalid values in a hand-edited URL are ignored, using the
 * same rules as the backend's validation.
 */

export const PAGE_SIZES = [20, 40, 60]
export const DEFAULT_PAGE_SIZE = 20
export const MODES = ['all', 'any']
export const SORT_OPTIONS = [
  { value: 'relevance', label: 'Relevance' },
  { value: 'price_asc', label: 'Price: Low to High' },
  { value: 'price_desc', label: 'Price: High to Low' },
  { value: 'rating', label: 'Customer Rating' },
  { value: 'newest', label: 'Newest First' },
]
const SORT_VALUES = SORT_OPTIONS.map((option) => option.value)
export const MAX_FILTER_VALUES = 20 // backend limit per repeatable filter
export const MAX_PRICE = 99999999.99 // backend limit (NUMERIC(10, 2))

/** The filter part of the state, all inactive. */
export const NO_FILTERS = {
  categories: [],
  brands: [],
  minPrice: null,
  maxPrice: null,
  minRating: null,
  inStock: false,
}

const PRICE_PATTERN = /^\d{1,8}(\.\d{1,2})?$/ // up to 99999999.99, max two decimals
const RATING_PATTERN = /^(?:[0-4](?:\.\d)?|5(?:\.0)?)$/ // 0 to 5, max one decimal

/** "49.9" -> "49.9"; "", "-1", "1.234", "abc" -> null. */
export function parsePrice(value) {
  const text = String(value ?? '').trim()
  return PRICE_PATTERN.test(text) && Number(text) <= MAX_PRICE ? text : null
}

export function parseRating(value) {
  const text = String(value ?? '').trim()
  return RATING_PATTERN.test(text) ? text : null
}

/** Trimmed, non-empty, case-insensitively unique values (first spelling wins), max 20. */
function cleanValues(values) {
  const seen = new Set()
  const result = []
  for (const raw of values) {
    const value = raw.trim()
    const key = value.toLowerCase()
    if (!value || seen.has(key)) continue
    seen.add(key)
    result.push(value)
  }
  return result.slice(0, MAX_FILTER_VALUES)
}

function positiveInt(value, fallback) {
  const number = Number(value)
  return Number.isInteger(number) && number >= 1 ? number : fallback
}

/** @param {URLSearchParams} params */
export function parseSearchState(params) {
  const mode = params.get('mode')
  const sort = params.get('sort')
  const perPage = Number(params.get('per_page'))
  return {
    q: (params.get('q') ?? '').trim(),
    mode: MODES.includes(mode) ? mode : 'all',
    exact: params.get('exact') === '1',
    sort: SORT_VALUES.includes(sort) ? sort : 'relevance',
    categories: cleanValues(params.getAll('category')),
    brands: cleanValues(params.getAll('brand')),
    minPrice: parsePrice(params.get('min_price')),
    maxPrice: parsePrice(params.get('max_price')),
    minRating: parseRating(params.get('min_rating')),
    inStock: ['true', '1'].includes(params.get('in_stock')),
    page: positiveInt(params.get('page'), 1),
    perPage: PAGE_SIZES.includes(perPage) ? perPage : DEFAULT_PAGE_SIZE,
  }
}

/** Build the query string for a search state, leaving out defaults and inactive filters. */
export function buildSearchParams({
  q,
  mode = 'all',
  exact = false,
  sort = 'relevance',
  categories = [],
  brands = [],
  minPrice = null,
  maxPrice = null,
  minRating = null,
  inStock = false,
  page = 1,
  perPage,
}) {
  const params = new URLSearchParams({ q })
  if (mode !== 'all') params.set('mode', mode)
  if (exact) params.set('exact', '1')
  if (sort !== 'relevance') params.set('sort', sort)
  categories.forEach((category) => params.append('category', category))
  brands.forEach((brand) => params.append('brand', brand))
  if (minPrice !== null) params.set('min_price', minPrice)
  if (maxPrice !== null) params.set('max_price', maxPrice)
  if (minRating !== null) params.set('min_rating', minRating)
  if (inStock) params.set('in_stock', 'true')
  if (page > 1) params.set('page', String(page))
  if (perPage && perPage !== DEFAULT_PAGE_SIZE) params.set('per_page', String(perPage))
  return params
}

export function searchUrl(state) {
  return `/search?${buildSearchParams(state)}`
}

export function activeFilterCount(state) {
  return (
    state.categories.length +
    state.brands.length +
    (state.minPrice !== null || state.maxPrice !== null ? 1 : 0) +
    (state.minRating !== null ? 1 : 0) +
    (state.inStock ? 1 : 0)
  )
}

/**
 * The /api/v1/search request for a state. Partial-word (prefix) matching is on by default.
 * Inactive filters and the default sort are left out (undefined/empty values are not sent).
 */
export function toApiParams({
  q,
  mode,
  exact,
  sort = 'relevance',
  categories = [],
  brands = [],
  minPrice = null,
  maxPrice = null,
  minRating = null,
  inStock = false,
  page,
  perPage,
}) {
  return {
    q,
    mode,
    prefix: !exact,
    limit: perPage,
    offset: (page - 1) * perPage,
    sort: sort === 'relevance' ? undefined : sort,
    category: categories.length ? categories : undefined,
    brand: brands.length ? brands : undefined,
    min_price: minPrice ?? undefined,
    max_price: maxPrice ?? undefined,
    min_rating: minRating ?? undefined,
    in_stock: inStock ? true : undefined,
  }
}
