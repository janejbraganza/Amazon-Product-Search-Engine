import { useId, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router'
import { useSuggestions } from '../../hooks/useSuggestions.js'
import { completeQuery } from '../../utils/autocomplete.js'
import { returnToSearch } from '../../utils/catalogue.js'
import { formatCount } from '../../utils/format.js'
import { NO_FILTERS, parseSearchState, searchUrl } from '../../utils/searchState.js'
import Icon from '../ui/Icon.jsx'
import styles from './SearchForm.module.css'

/**
 * Search box with autocomplete (WAI-ARIA combobox pattern).
 *
 * - Submitting navigates to /search?q=..., keeping the current matching options
 *   (mode, exact words, page size) and starting on page 1.
 * - Starts with the current query from the URL, so it always shows what was searched.
 *   On a product page opened from search results, the search it came from is used
 *   instead (its query is shown, and a new search keeps that search's options).
 * - While typing, suggestions for the LAST word come from /api/v1/search/suggestions.
 *   ArrowDown/ArrowUp move through them, Enter or a click picks one (it replaces the last
 *   word and searches), Escape closes the list, Tab moves on as usual.
 *
 * @param {{size?: 'compact'|'large', autoFocus?: boolean}} props
 */
export default function SearchForm({ size = 'compact', autoFocus = false }) {
  const [urlParams] = useSearchParams()
  const location = useLocation()
  const returnTo = location.pathname === '/search' ? null : returnToSearch(location.state)
  const searchParams = returnTo
    ? new URLSearchParams(returnTo.path.slice('/search?'.length))
    : urlParams
  const currentQuery = searchParams.get('q') ?? ''
  const [value, setValue] = useState(currentQuery)
  const [syncedQuery, setSyncedQuery] = useState(currentQuery)
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const navigate = useNavigate()
  const baseId = useId()
  const inputId = `search-input-${size}`
  const listboxId = `${baseId}-suggestions`

  // Keep the box in sync when the URL changes (Back/Forward, links) - React's
  // "adjust state when a prop changes" pattern, without an effect.
  if (currentQuery !== syncedQuery) {
    setSyncedQuery(currentQuery)
    setValue(currentQuery)
    setOpen(false)
  }

  // Suggestions are only requested while the list is open (i.e. after the user types),
  // never for the query that is already in the box when a page loads.
  const { status, suggestions, prefix } = useSuggestions(open ? value : '')
  const showPopup = open && value.trim() !== '' && status !== 'idle'
  const hasOptions = showPopup && suggestions.length > 0
  const active = hasOptions && activeIndex < suggestions.length ? activeIndex : -1

  function search(query) {
    setOpen(false)
    setActiveIndex(-1)
    // A new search keeps the user's matching options and sort order (mode, exact words,
    // sort, page size), clears the filters (they belonged to the previous search) and
    // always starts on page 1. On the home page there are none, so defaults apply.
    navigate(searchUrl({ ...parseSearchState(searchParams), ...NO_FILTERS, q: query, page: 1 }))
  }

  function selectSuggestion(suggestion) {
    const query = completeQuery(value, suggestion.term)
    setValue(query)
    search(query)
  }

  function handleSubmit(event) {
    event.preventDefault()
    const query = value.trim()
    if (!query) return
    search(query)
  }

  function handleChange(event) {
    setValue(event.target.value)
    setOpen(true)
    setActiveIndex(-1)
  }

  function handleKeyDown(event) {
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault()
        if (!open) setOpen(true)
        else if (hasOptions) setActiveIndex((active + 1) % suggestions.length)
        break
      case 'ArrowUp':
        if (!hasOptions) return
        event.preventDefault()
        setActiveIndex(active <= 0 ? suggestions.length - 1 : active - 1)
        break
      case 'Enter':
        if (active >= 0) {
          event.preventDefault() // pick the highlighted suggestion instead of submitting
          selectSuggestion(suggestions[active])
        }
        break
      case 'Escape':
        if (showPopup) {
          event.preventDefault()
          setOpen(false)
          setActiveIndex(-1)
        }
        break
      case 'Tab':
        setOpen(false) // focus moves on normally
        break
      default:
    }
  }

  return (
    <form
      role="search"
      className={`${styles.form} ${styles[size]}`}
      onSubmit={handleSubmit}
      aria-label="Product search"
    >
      <label htmlFor={inputId} className="visually-hidden">
        Search products
      </label>
      <Icon name="search" className={styles.icon} />
      <input
        id={inputId}
        className={styles.input}
        type="search"
        name="q"
        role="combobox"
        aria-expanded={showPopup}
        aria-controls={listboxId}
        aria-autocomplete="list"
        aria-activedescendant={active >= 0 ? `${listboxId}-${active}` : undefined}
        placeholder="Search products, brands and categories"
        autoComplete="off"
        spellCheck="false"
        enterKeyHint="search"
        maxLength={200}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        onBlur={() => setOpen(false)}
        autoFocus={autoFocus} // only the home-page hero box, where searching is the only task
      />
      <button type="submit" className={styles.button}>
        Search
      </button>

      <div className={styles.popup} hidden={!showPopup}>
        <ul
          id={listboxId}
          role="listbox"
          aria-label="Search suggestions"
          className={styles.listbox}
        >
          {hasOptions &&
            suggestions.map((suggestion, index) => (
              <li
                key={suggestion.term}
                id={`${listboxId}-${index}`}
                role="option"
                aria-selected={index === active}
                className={styles.option}
                // Keep focus in the input so the click is not lost to its blur handler.
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => selectSuggestion(suggestion)}
                onMouseMove={() => index !== active && setActiveIndex(index)}
              >
                <Icon name="search" size={16} className={styles.optionIcon} />
                <SuggestionTerm term={suggestion.term} prefix={prefix} />
                <span className={styles.count}>
                  {formatCount(suggestion.product_count)}{' '}
                  {suggestion.product_count === 1 ? 'product' : 'products'}
                </span>
              </li>
            ))}
        </ul>
        {showPopup && !hasOptions && (
          <p className={styles.message}>
            {status === 'loading' && 'Loading suggestions…'}
            {status === 'success' && 'No matching words. Press Enter to search anyway.'}
            {status === 'error' && 'Suggestions are unavailable. You can still search.'}
          </p>
        )}
      </div>

      {/* Announced by screen readers when the list changes. */}
      <div className="visually-hidden" aria-live="polite" aria-atomic="true">
        {showPopup && status === 'success'
          ? hasOptions
            ? `${suggestions.length} ${suggestions.length === 1 ? 'suggestion' : 'suggestions'} available. Use the up and down arrow keys to choose one.`
            : 'No suggestions.'
          : ''}
        {showPopup && status === 'error' ? 'Suggestions are unavailable.' : ''}
      </div>
    </form>
  )
}

/** The typed part of the suggestion in normal weight, the completion in bold. */
function SuggestionTerm({ term, prefix }) {
  const typed = prefix && term.startsWith(prefix) ? prefix : ''
  return (
    <span className={styles.term}>
      {typed}
      <strong>{term.slice(typed.length)}</strong>
    </span>
  )
}
