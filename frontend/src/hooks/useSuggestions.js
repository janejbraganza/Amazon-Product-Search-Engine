import { useEffect, useState } from 'react'
import { isAbortError } from '../api/client.js'
import { getSuggestions } from '../api/search.js'
import { suggestionQuery } from '../utils/autocomplete.js'
import { useDebouncedValue } from './useDebouncedValue.js'

export const SUGGESTION_DEBOUNCE_MS = 175
export const SUGGESTION_LIMIT = 10
const MAX_CACHED = 100

/**
 * Autocomplete suggestions for ``text`` from GET /api/v1/search/suggestions.
 *
 * - Waits until typing pauses (debounce), so fast typing sends one request, not one per key.
 * - Sends nothing for empty, whitespace-only or punctuation-only text.
 * - Results are stored per text. Only the entry for the CURRENT text is ever shown, so an
 *   older response can never replace newer suggestions; the previous request is also
 *   aborted when the text changes or the component unmounts.
 * - Text already looked up (e.g. after Backspace) is answered from memory.
 *
 * @returns {{status: 'idle'|'loading'|'success'|'error', suggestions: object[], prefix: string|null}}
 */
export function useSuggestions(text, { delay = SUGGESTION_DEBOUNCE_MS } = {}) {
  const query = useDebouncedValue(suggestionQuery(text), delay)
  const [results, setResults] = useState(() => new Map()) // query -> API response
  const [failure, setFailure] = useState(null) // { query, error } for the latest failure
  const known = query ? results.get(query) : undefined

  useEffect(() => {
    if (!query || known) return undefined
    const controller = new AbortController()
    getSuggestions(query, { limit: SUGGESTION_LIMIT, signal: controller.signal }).then(
      ({ data }) =>
        setResults((previous) => {
          const next = new Map(previous)
          next.set(query, data)
          if (next.size > MAX_CACHED) next.delete(next.keys().next().value) // drop oldest
          return next
        }),
      (error) => {
        if (!isAbortError(error)) setFailure({ query, error }) // cancelled requests are not errors
      },
    )
    return () => controller.abort()
  }, [query, known])

  if (!query) return { status: 'idle', suggestions: [], prefix: null }
  if (known) return { status: 'success', suggestions: known.suggestions, prefix: known.prefix }
  if (failure?.query === query) return { status: 'error', suggestions: [], prefix: null }
  return { status: 'loading', suggestions: [], prefix: null }
}
