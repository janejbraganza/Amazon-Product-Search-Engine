export const ELLIPSIS = '…'

export function pageCount(total, perPage) {
  return Math.max(1, Math.ceil(total / perPage))
}

/**
 * Page numbers to show, with gaps:  getPageItems(5, 12) -> [1, '…', 4, 5, 6, '…', 12]
 * Always shows the first and last page, the current page and ``siblings`` pages on each side.
 * A gap that would hide only one page shows that page instead, and when there are only a
 * few pages (as many as the widest gapped list would show) every page is listed.
 */
export function getPageItems(current, totalPages, siblings = 1) {
  if (totalPages <= 1) return [1]
  if (totalPages <= 2 * siblings + 5) {
    return Array.from({ length: totalPages }, (_, i) => i + 1)
  }
  const pages = new Set([1, totalPages])
  for (let p = current - siblings; p <= current + siblings; p++) {
    if (p >= 1 && p <= totalPages) pages.add(p)
  }
  const sorted = [...pages].sort((a, b) => a - b)
  const items = []
  sorted.forEach((page, i) => {
    const previous = sorted[i - 1]
    if (previous !== undefined && page - previous === 2) items.push(previous + 1)
    else if (previous !== undefined && page - previous > 2) items.push(ELLIPSIS)
    items.push(page)
  })
  return items
}
