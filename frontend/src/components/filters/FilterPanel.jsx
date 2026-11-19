import {
  brandOptions,
  categoryOptions,
  RATING_OPTIONS,
  toggleValue,
} from '../../utils/filterOptions.js'
import FacetCheckboxList from './FacetCheckboxList.jsx'
import PriceRange from './PriceRange.jsx'
import styles from './FilterPanel.module.css'

/**
 * All filter controls. ``filters`` is the filter part of the search state; every change is
 * reported as ``onChange(changes)``. Used both in the desktop sidebar (changes apply at
 * once) and in the mobile drawer (changes go to a draft until "Show results").
 */
export default function FilterPanel({
  filters,
  facets,
  catalogue,
  categoriesFailed = false,
  onChange,
  priceDelay,
  onPriceValidityChange,
  resetKey = 0,
}) {
  return (
    <div className={styles.panel}>
      <FacetCheckboxList
        legend="Category"
        options={categoryOptions(catalogue, facets, filters.categories)}
        selected={filters.categories}
        onToggle={(value) => onChange({ categories: toggleValue(filters.categories, value) })}
        visible={10}
      />
      {categoriesFailed && (
        <p className={styles.note}>The full category list could not be loaded.</p>
      )}

      <FacetCheckboxList
        legend="Brand"
        options={brandOptions(facets, filters.brands)}
        selected={filters.brands}
        onToggle={(value) => onChange({ brands: toggleValue(filters.brands, value) })}
      />

      <PriceRange
        key={resetKey} // a new key (Clear all) empties the boxes and cancels a pending price
        minPrice={filters.minPrice}
        maxPrice={filters.maxPrice}
        onChange={onChange}
        delay={priceDelay}
        onValidityChange={onPriceValidityChange}
      />

      <fieldset className={styles.section}>
        <legend className={styles.legend}>Customer rating</legend>
        <label className={styles.selectField}>
          <span className="visually-hidden">Minimum rating</span>
          <select
            aria-label="Minimum rating"
            value={filters.minRating ?? ''}
            onChange={(event) => onChange({ minRating: event.target.value || null })}
          >
            {RATING_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
            {filters.minRating !== null &&
              !RATING_OPTIONS.some((o) => o.value === filters.minRating) && (
                <option value={filters.minRating}>{filters.minRating} & up</option>
              )}
          </select>
        </label>
      </fieldset>

      <fieldset className={styles.section}>
        <legend className={styles.legend}>Availability</legend>
        <label className={styles.checkbox}>
          <input
            type="checkbox"
            checked={filters.inStock}
            onChange={(event) => onChange({ inStock: event.target.checked })}
          />
          <span className={styles.optionLabel}>In stock only</span>
        </label>
      </fieldset>
    </div>
  )
}
