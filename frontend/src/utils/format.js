// The API returns prices and ratings as numbers (they may also arrive as numeric strings).
const priceFormat = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
const countFormat = new Intl.NumberFormat('en-US')

export function formatPrice(value) {
  return priceFormat.format(Number(value))
}

export function formatCount(value) {
  return countFormat.format(Number(value))
}

export function formatRating(value) {
  return Number(value).toFixed(1)
}

/** Stock label + tone for a product's stock_quantity. */
export function stockStatus(quantity) {
  if (quantity <= 0) return { label: 'Out of stock', tone: 'danger' }
  if (quantity <= 10) return { label: `Only ${quantity} left`, tone: 'warning' }
  return { label: 'In stock', tone: 'success' }
}

const dateFormat = new Intl.DateTimeFormat('en-US', { dateStyle: 'long', timeZone: 'UTC' })

/** '2025-05-28T05:13:52Z' -> 'May 28, 2025' (UTC, so every visitor sees the same date). */
export function formatDate(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : dateFormat.format(date)
}
