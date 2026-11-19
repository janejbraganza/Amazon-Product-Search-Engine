import { useCallback, useEffect, useState } from 'react'
import { isAbortError } from '../api/client.js'
import { getCategories } from '../api/products.js'

/**
 * All catalogue categories from GET /api/v1/categories, loaded once per page visit
 * (``retry`` loads them again after a failure).
 * @returns {{status: 'loading'|'success'|'error', categories: {name: string, product_count: number}[],
 *   totalProducts: number|null, retry: () => void}}
 */
export function useCategories() {
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState({ attempt: -1, status: 'loading', data: null })

  useEffect(() => {
    const controller = new AbortController()
    getCategories({ signal: controller.signal }).then(
      ({ data }) => setState({ attempt, status: 'success', data }),
      (error) => {
        if (!isAbortError(error)) setState({ attempt, status: 'error', data: null })
      },
    )
    return () => controller.abort()
  }, [attempt])

  const retry = useCallback(() => setAttempt((n) => n + 1), [])
  const current = state.attempt === attempt
  const status = current ? state.status : 'loading'
  const data = current ? state.data : null
  return {
    status,
    categories: data?.categories ?? [],
    totalProducts: data?.total_products ?? null,
    retry,
  }
}
