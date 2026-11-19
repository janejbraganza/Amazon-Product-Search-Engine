import { useEffect, useState } from 'react'
import { isAbortError } from '../api/client.js'
import { searchProducts } from '../api/search.js'
import { parseSearchState, toApiParams } from '../utils/searchState.js'

/**
 * The real number of results for each query, as the search page would find them (same
 * default options: all words, partial last word), fetched with one-result searches.
 * A query whose request fails simply has no count (null) - nothing is estimated.
 * @param {string[]} queries
 * @returns {Record<string, number|null>}
 */
export function useResultCounts(queries) {
  const [counts, setCounts] = useState({})
  const queriesKey = JSON.stringify(queries)

  useEffect(() => {
    const controller = new AbortController()
    for (const q of JSON.parse(queriesKey)) {
      const params = { ...toApiParams(parseSearchState(new URLSearchParams({ q }))), limit: 1 }
      searchProducts(params, { signal: controller.signal }).then(
        ({ data }) => setCounts((previous) => ({ ...previous, [q]: data.total })),
        (error) => {
          if (!isAbortError(error)) setCounts((previous) => ({ ...previous, [q]: null }))
        },
      )
    }
    return () => controller.abort()
  }, [queriesKey])

  return counts
}
