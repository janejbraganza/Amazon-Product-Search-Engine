import { PAGE_SIZES, SORT_OPTIONS } from '../../utils/searchState.js'
import styles from './SearchControls.module.css'

/**
 * Matching options, sort order and page size for the current search. Every change is
 * reported through ``onChange`` (the page turns it into a new URL and goes back to page 1).
 * Sorting is done by the backend; this only chooses the ``sort`` value it receives.
 */
export default function SearchControls({ mode, exact, sort, perPage, onChange }) {
  return (
    <div className={styles.controls}>
      <fieldset className={styles.segmented}>
        <legend className="visually-hidden">Match</legend>
        {[
          ['all', 'All words'],
          ['any', 'Any word'],
        ].map(([value, label]) => (
          <label key={value} className={styles.option}>
            <input
              type="radio"
              name="mode"
              value={value}
              checked={mode === value}
              onChange={() => onChange({ mode: value })}
            />
            <span>{label}</span>
          </label>
        ))}
      </fieldset>

      <label className={styles.checkbox}>
        <input
          type="checkbox"
          checked={exact}
          onChange={(event) => onChange({ exact: event.target.checked })}
        />
        Exact words only
      </label>

      <div className={styles.selects}>
        <label className={styles.select}>
          <span>Sort by</span>
          <select value={sort} onChange={(event) => onChange({ sort: event.target.value })}>
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.select}>
          <span>Per page</span>
          <select
            value={perPage}
            onChange={(event) => onChange({ perPage: Number(event.target.value) })}
          >
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  )
}
