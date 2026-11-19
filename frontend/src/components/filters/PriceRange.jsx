import { useEffect, useId, useRef, useState } from 'react'
import { validatePriceRange } from '../../utils/filterOptions.js'
import styles from './FilterPanel.module.css'

const key = (min, max) => `${min ?? ''}|${max ?? ''}`

/**
 * Minimum / maximum price inputs. Valid values are reported through ``onChange`` once
 * typing pauses for ``delay`` ms (or at once with Enter), so the search is not repeated
 * on every keystroke. Invalid values show a message and are never sent.
 *
 * The boxes follow the applied values (URL or drawer draft) when those change elsewhere
 * (Clear all, a removed chip, Back/Forward), but NOT when the change is just the echo of a
 * value these boxes sent themselves - otherwise text typed meanwhile (e.g. the "." of
 * "150.25") would be overwritten.
 */
export default function PriceRange({
  minPrice,
  maxPrice,
  onChange,
  delay = 700,
  onValidityChange,
}) {
  const id = useId()
  const [minText, setMinText] = useState(minPrice ?? '')
  const [maxText, setMaxText] = useState(maxPrice ?? '')
  const applied = key(minPrice, maxPrice)
  const [synced, setSynced] = useState(applied) // applied value last seen
  const [emitted, setEmitted] = useState(applied) // value these boxes last sent
  const timer = useRef(null)
  // A delayed price must be applied with the LATEST onChange (built from the current URL),
  // not the one from when typing started - otherwise it could restore filters removed since.
  const latest = useRef({ onChange, minPrice, maxPrice })
  useEffect(() => {
    latest.current = { onChange, minPrice, maxPrice }
  })

  if (applied !== synced) {
    setSynced(applied)
    if (applied !== emitted) {
      // Changed elsewhere: show the new value.
      setMinText(minPrice ?? '')
      setMaxText(maxPrice ?? '')
      setEmitted(applied)
    }
  }

  // A change made elsewhere cancels a price that was still waiting to be applied.
  useEffect(() => {
    if (applied !== emitted) clearTimeout(timer.current)
  }, [applied, emitted])
  useEffect(() => () => clearTimeout(timer.current), [])

  const { error } = validatePriceRange(minText, maxText)
  useEffect(() => {
    onValidityChange?.(error === null)
  }, [error, onValidityChange])

  function send(nextMin, nextMax) {
    const result = validatePriceRange(nextMin, nextMax)
    if (result.error) return
    const current = latest.current
    if (result.min === current.minPrice && result.max === current.maxPrice) return
    setEmitted(key(result.min, result.max))
    current.onChange({ minPrice: result.min, maxPrice: result.max })
  }

  function handleInput(nextMin, nextMax) {
    setMinText(nextMin)
    setMaxText(nextMax)
    clearTimeout(timer.current)
    if (delay === 0) send(nextMin, nextMax)
    else timer.current = setTimeout(() => send(nextMin, nextMax), delay)
  }

  function applyNow(event) {
    if (event.key !== 'Enter') return
    event.preventDefault()
    clearTimeout(timer.current)
    send(minText, maxText)
  }

  const errorId = `${id}-error`
  return (
    <fieldset className={styles.section}>
      <legend className={styles.legend}>Price</legend>
      <div className={styles.priceRow}>
        <label className={styles.priceField}>
          <span>Min</span>
          <span className={styles.currency}>$</span>
          <input
            type="text"
            inputMode="decimal"
            placeholder="0"
            value={minText}
            onChange={(event) => handleInput(event.target.value, maxText)}
            onKeyDown={applyNow}
            aria-label="Minimum price"
            aria-invalid={error !== null && error.includes('minimum')}
            aria-describedby={error ? errorId : undefined}
          />
        </label>
        <span className={styles.dash} aria-hidden="true">
          –
        </span>
        <label className={styles.priceField}>
          <span>Max</span>
          <span className={styles.currency}>$</span>
          <input
            type="text"
            inputMode="decimal"
            placeholder="Any"
            value={maxText}
            onChange={(event) => handleInput(minText, event.target.value)}
            onKeyDown={applyNow}
            aria-label="Maximum price"
            aria-invalid={error !== null && !error.startsWith('Enter a minimum')}
            aria-describedby={error ? errorId : undefined}
          />
        </label>
      </div>
      {error && (
        <p id={errorId} className={styles.error} role="alert">
          {error}
        </p>
      )}
    </fieldset>
  )
}
