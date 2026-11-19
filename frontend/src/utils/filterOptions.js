/**
 * Helpers for the filter panel. Counts always come from the search response's ``facets``
 * (computed by the backend over ALL matching products); nothing here counts results.
 */
import { parsePrice } from './searchState.js'

export const RATING_OPTIONS = [
  { value: '', label: 'Any rating' },
  { value: '4.5', label: '4.5 & up' },
  { value: '4', label: '4 & up' },
  { value: '3.5', label: '3.5 & up' },
  { value: '3', label: '3 & up' },
  { value: '2', label: '2 & up' },
]

const lower = (value) => value.toLowerCase()

function countMap(values) {
  return values ? new Map(values.map((v) => [lower(v.value), v.count])) : null
}

/**
 * Category options: every catalogue category (GET /categories), plus any category the
 * facets or the URL mention. ``count`` comes from the facets; it is undefined while no
 * facets are known and 0 for a category with no results for this search.
 */
export function categoryOptions(catalogue, facets, selected) {
  const counts = countMap(facets?.categories)
  const names = []
  const seen = new Set()
  const add = (name) => {
    if (!seen.has(lower(name))) {
      seen.add(lower(name))
      names.push(name)
    }
  }
  catalogue.forEach((c) => add(c.name))
  facets?.categories.forEach((c) => add(c.value))
  selected.forEach(add)
  return names.map((value) => ({
    value,
    count: counts ? (counts.get(lower(value)) ?? 0) : undefined,
  }))
}

/** Brand options: the facets (most results first), plus selected brands not in them. */
export function brandOptions(facets, selected) {
  const options = facets ? facets.brands.map((b) => ({ value: b.value, count: b.count })) : []
  const known = new Set(options.map((o) => lower(o.value)))
  selected
    .filter((brand) => !known.has(lower(brand)))
    .forEach((brand) => options.push({ value: brand, count: facets ? 0 : undefined }))
  return options
}

/** Add ``value`` to the list, or remove it if present (case-insensitive). */
export function toggleValue(list, value) {
  return list.some((v) => lower(v) === lower(value))
    ? list.filter((v) => lower(v) !== lower(value))
    : [...list, value]
}

/** Validate the two typed prices. Returns {min, max, error} with min/max as API strings. */
export function validatePriceRange(minText, maxText) {
  const min = minText.trim() === '' ? null : parsePrice(minText)
  const max = maxText.trim() === '' ? null : parsePrice(maxText)
  if (minText.trim() !== '' && min === null) {
    return { min, max, error: 'Enter a minimum price like 50 or 49.99.' }
  }
  if (maxText.trim() !== '' && max === null) {
    return { min, max, error: 'Enter a maximum price like 200 or 199.99.' }
  }
  if (min !== null && max !== null && Number(min) > Number(max)) {
    return { min, max, error: 'The minimum price must not be more than the maximum price.' }
  }
  return { min, max, error: null }
}
