/**
 * Small fetch wrapper used by every API call.
 *
 * - Relative URLs only: the browser talks to its own origin (Vite proxy in development,
 *   nginx in Docker), so no backend host or credentials ever appear in frontend code.
 * - A timeout plus optional caller cancellation through an AbortSignal.
 * - Every failure becomes an ApiError with a short, user-safe message. Raw server errors,
 *   stack traces and internal details are never shown to users.
 */

export const DEFAULT_TIMEOUT_MS = 10_000

export class ApiError extends Error {
  /**
   * @param {string} message  user-safe message
   * @param {{status?: number, detail?: unknown, kind?: 'http'|'network'|'timeout'}} [info]
   */
  constructor(message, { status = 0, detail = null, kind = 'http' } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.kind = kind
  }
}

/** True when a request was cancelled by its caller (not a failure to show to users). */
export function isAbortError(error) {
  return error?.name === 'AbortError'
}

/** '/api/v1/search' + {q: 'lap', mode: undefined} -> '/api/v1/search?q=lap' */
export function buildUrl(path, params = {}) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    for (const item of Array.isArray(value) ? value : [value]) {
      search.append(key, String(item))
    }
  }
  const query = search.toString()
  return query ? `${path}?${query}` : path
}

function messageFor(status, body) {
  const detail = body?.detail
  if (status === 422) {
    // FastAPI returns either our own string message or a list of validation problems.
    return typeof detail === 'string' ? detail : 'Please check your search and try again.'
  }
  if (status === 404) {
    return typeof detail === 'string' ? detail : 'Not found.'
  }
  if (status >= 500) {
    return 'The search service is temporarily unavailable. Please try again.'
  }
  return `Something went wrong (error ${status}).`
}

async function readJson(response) {
  try {
    return await response.json()
  } catch {
    return null
  }
}

/**
 * GET a JSON endpoint.
 * @returns {Promise<{data: any, cacheStatus: string|null, durationMs: number}>}
 */
export async function apiGet(path, { params, signal, timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
  const controller = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)
  const onCallerAbort = () => controller.abort()
  if (signal) {
    if (signal.aborted) controller.abort()
    else signal.addEventListener('abort', onCallerAbort, { once: true })
  }

  const started = performance.now()
  let response
  try {
    // Resolve against the page's own origin (same result as a relative URL in browsers,
    // and also works in environments whose fetch() needs absolute URLs, such as tests).
    response = await fetch(new URL(buildUrl(path, params), window.location.origin), {
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    })
  } catch (error) {
    if (signal?.aborted) throw new DOMException('Request cancelled', 'AbortError')
    if (timedOut) {
      throw new ApiError('The search service took too long to respond. Please try again.', {
        kind: 'timeout',
      })
    }
    throw new ApiError("Can't reach the search service. Check your connection and try again.", {
      kind: 'network',
      detail: error?.message ?? null,
    })
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', onCallerAbort)
  }

  const body = await readJson(response)
  if (!response.ok) {
    throw new ApiError(messageFor(response.status, body), {
      status: response.status,
      detail: body?.detail ?? null,
    })
  }
  return {
    data: body,
    cacheStatus: response.headers.get('x-cache'),
    durationMs: Math.round(performance.now() - started),
  }
}
