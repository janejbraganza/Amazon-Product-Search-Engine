import { searchUrl } from './searchState.js'

/**
 * Catalogue helpers shared by the home page and the product page: category icons, links
 * that browse a category or brand through the normal search page, product-ID checks, the
 * "back to results" link and the query used for similar products.
 */

// Icon per catalogue category (names as returned by GET /api/v1/categories). A category
// that is not listed here (e.g. one added to the data later) gets the generic package icon.
const CATEGORY_ICONS = {
  Automotive: 'car',
  'Beauty & Personal Care': 'sparkle',
  Books: 'book',
  Clothing: 'shirt',
  Electronics: 'electronics',
  'Grocery & Gourmet Food': 'basket',
  'Home & Kitchen': 'home',
  'Office Supplies': 'paperclip',
  'Sports & Outdoors': 'ball',
  'Toys & Games': 'puzzle',
}

export function categoryIcon(category) {
  return CATEGORY_ICONS[category] ?? 'package'
}

/**
 * Browse one category: search for the category's own name, restricted to that category.
 * Category names are indexed (field weight 2), so this lists the category's products;
 * the category filter keeps out other categories that merely mention the words.
 */
export function categoryUrl(category) {
  return searchUrl({ q: category, categories: [category] })
}

/** Browse one brand: search for the brand name, restricted to that brand. */
export function brandUrl(brand) {
  return searchUrl({ q: brand, brands: [brand] })
}

// Product IDs are positive integers that fit the backend's BIGINT column.
const BIGINT_MAX = 2n ** 63n - 1n

/** True for a product ID the API can accept ("42"); false for "abc", "0", "-1", "1.5". */
export function isValidProductId(value) {
  if (typeof value !== 'string' || !/^[1-9]\d{0,18}$/.test(value)) return false
  return BigInt(value) <= BIGINT_MAX
}

/**
 * The search results page a product was opened from (passed as router state by the
 * result cards), or null. Only an in-app /search URL with a query is accepted.
 */
export function returnToSearch(locationState) {
  const path = locationState?.fromSearch
  if (typeof path !== 'string' || !path.startsWith('/search?')) return null
  const q = new URLSearchParams(path.slice('/search?'.length)).get('q')
  return q && q.trim() ? { path, query: q.trim() } : null
}

const MAX_QUERY_LENGTH = 200 // the search API's limit for q

/**
 * The search used to find similar products: the product's own name (BM25 ranks products
 * sharing the most, and the rarest, words first), cut at a word boundary to fit the API.
 */
export function similarQuery(productName) {
  const name = productName.replace(/\s+/g, ' ').trim()
  if (name.length <= MAX_QUERY_LENGTH) return name
  const cut = name.slice(0, MAX_QUERY_LENGTH + 1)
  const lastSpace = cut.lastIndexOf(' ')
  return (lastSpace > 0 ? cut.slice(0, lastSpace) : cut.slice(0, MAX_QUERY_LENGTH)).trim()
}
