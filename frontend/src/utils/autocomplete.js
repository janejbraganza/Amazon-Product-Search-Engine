/**
 * Helpers for autocomplete, matching how the backend's /search/suggestions works:
 * it completes the LAST word of the text (its response field `prefix` is that word,
 * normalised), and it rejects text without any letter or digit (422).
 */

/** Same rule as the backend tokenizer: at least one letter or digit. */
export function isSearchable(text) {
  return /[\p{L}\p{N}]/u.test(text)
}

/** Text to send to /search/suggestions, or '' when no request should be made. */
export function suggestionQuery(text) {
  const trimmed = text.trim()
  return isSearchable(trimmed) ? trimmed : ''
}

/** Replace the last word of ``text`` with the chosen suggestion: "wireless ea" + "earbud". */
export function completeQuery(text, term) {
  const trimmed = text.trimEnd()
  const lastWordStart = trimmed.search(/\S+$/)
  return lastWordStart === -1 ? term : trimmed.slice(0, lastWordStart) + term
}
