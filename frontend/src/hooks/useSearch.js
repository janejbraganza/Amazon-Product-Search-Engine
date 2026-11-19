import { useCallback, useEffect, useState } from 'react'
import { isAbortError } from '../api/client.js'
import { searchProducts } from '../api/search.js'

/**
 * Fetch search results for the given /api/v1/search parameters (see utils/searchState.js
 * toApiParams: query, mode, prefix, pagination, sort and filters).
 *
 * Each stored result remembers the request it belongs to (``key``). The page is "loading"
 * whenever the stored result is for a different request than the current one, so:
 * - a new search never shows the previous search's error,
 * - previous results stay available (dimmed) while the next page loads,
 * - a slow, outdated response can never overwrite a newer one (it is also aborted),
 * - re-rendering with the same parameters never sends a duplicate request.
 *
 * @param {object} params  /api/v1/search parameters
 */
export function useSearch(params) {
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState({ key: null, data: null, error: null, meta: null })
  const paramsKey = JSON.stringify(params)
  const key = `${paramsKey}#${attempt}`

  useEffect(() => {
    const requestParams = JSON.parse(paramsKey)
    if (!requestParams.q) return undefined
    const requestKey = `${paramsKey}#${attempt}`
    const controller = new AbortController()
    searchProducts(requestParams, { signal: controller.signal }).then(
      ({ data, cacheStatus, durationMs }) =>
        setResult({ key: requestKey, data, error: null, meta: { cacheStatus, durationMs } }),
      (error) => {
        if (isAbortError(error)) return // superseded by a newer request
        setResult((previous) => ({ ...previous, key: requestKey, error }))
      },
    )
    return () => controller.abort()
  }, [paramsKey, attempt])

  const retry = useCallback(() => setAttempt((n) => n + 1), [])
  const isCurrent = result.key === key

  return {
    data: result.data, // latest successful response (may belong to a previous request)
    meta: result.meta,
    error: isCurrent ? result.error : null,
    isLoading: Boolean(params.q) && !isCurrent,
    isCurrent,
    retry,
  }
}
