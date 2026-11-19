import { useCallback, useEffect, useState } from 'react'
import { isAbortError } from '../api/client.js'
import { getProduct } from '../api/products.js'
import { isValidProductId } from '../utils/catalogue.js'

/**
 * One product from GET /api/v1/products/{id}.
 *
 * status: 'invalid' (not a product ID - no request is sent), 'loading', 'success',
 * 'not-found' (404) or 'error' (anything else; ``retry`` tries again).
 * Like useSearch, the stored result remembers which request it belongs to, so moving to
 * another product never shows the previous product (or its error) and a slow, outdated
 * response can never overwrite a newer one.
 *
 * @param {string} productId  the raw route parameter
 */
export function useProduct(productId) {
  const valid = isValidProductId(productId)
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState({ key: null, product: null, error: null })
  const key = `${productId}#${attempt}`

  useEffect(() => {
    if (!valid) return undefined
    const requestKey = `${productId}#${attempt}`
    const controller = new AbortController()
    getProduct(productId, { signal: controller.signal }).then(
      ({ data }) => setResult({ key: requestKey, product: data, error: null }),
      (error) => {
        if (!isAbortError(error)) setResult({ key: requestKey, product: null, error })
      },
    )
    return () => controller.abort()
  }, [productId, attempt, valid])

  const retry = useCallback(() => setAttempt((n) => n + 1), [])

  if (!valid) return { status: 'invalid', product: null, error: null, retry }
  if (result.key !== key) return { status: 'loading', product: null, error: null, retry }
  if (result.error) {
    const status = result.error.status === 404 ? 'not-found' : 'error'
    return { status, product: null, error: result.error, retry }
  }
  return { status: 'success', product: result.product, error: null, retry }
}
