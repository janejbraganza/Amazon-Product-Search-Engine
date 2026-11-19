import { useState } from 'react'
import { formatCount } from '../../utils/format.js'
import styles from './FilterPanel.module.css'

/**
 * Multi-select checkbox list (categories or brands) with counts from the API's facets.
 *
 * ``options``: [{value, count}] where count is a number from the facets, or undefined when
 * no counts are known yet. Options with a count of 0 that are not selected are disabled
 * (choosing them would give no results). Selected options always stay visible.
 */
export default function FacetCheckboxList({ legend, options, selected, onToggle, visible = 8 }) {
  const [expanded, setExpanded] = useState(false)
  const isSelected = (value) => selected.some((s) => s.toLowerCase() === value.toLowerCase())
  const shown = expanded
    ? options
    : options.filter((option, index) => index < visible || isSelected(option.value))
  const hidden = options.length - shown.length

  return (
    <fieldset className={styles.section}>
      <legend className={styles.legend}>{legend}</legend>
      {options.length === 0 ? (
        <p className={styles.note}>No {legend.toLowerCase()} options</p>
      ) : (
        <ul className={styles.options}>
          {shown.map(({ value, count }) => {
            const checked = isSelected(value)
            return (
              <li key={value}>
                <label className={styles.checkbox} data-disabled={!checked && count === 0}>
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={!checked && count === 0}
                    onChange={() => onToggle(value)}
                  />
                  <span className={styles.optionLabel}>{value}</span>
                  {count !== undefined && (
                    <span className={styles.count} aria-label={`${count} results`}>
                      {formatCount(count)}
                    </span>
                  )}
                </label>
              </li>
            )
          })}
        </ul>
      )}
      {(hidden > 0 || expanded) && options.length > visible && (
        <button type="button" className={styles.link} onClick={() => setExpanded(!expanded)}>
          {expanded ? 'Show fewer' : `Show all ${options.length}`}
        </button>
      )}
    </fieldset>
  )
}
