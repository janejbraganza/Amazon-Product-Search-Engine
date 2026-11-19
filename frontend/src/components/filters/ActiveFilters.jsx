import { NO_FILTERS } from '../../utils/searchState.js'
import Icon from '../ui/Icon.jsx'
import styles from './ActiveFilters.module.css'

function priceLabel(min, max) {
  if (min !== null && max !== null) return `$${min} – $${max}`
  if (min !== null) return `$${min} and up`
  return `Up to $${max}`
}

/** Removable chips for every active filter, plus "Clear all filters". */
export default function ActiveFilters({
  filters,
  onChange,
  onClearAll = () => onChange(NO_FILTERS),
}) {
  const chips = [
    ...filters.categories.map((category) => ({
      label: category,
      remove: { categories: filters.categories.filter((c) => c !== category) },
    })),
    ...filters.brands.map((brand) => ({
      label: brand,
      remove: { brands: filters.brands.filter((b) => b !== brand) },
    })),
  ]
  if (filters.minPrice !== null || filters.maxPrice !== null) {
    chips.push({
      label: priceLabel(filters.minPrice, filters.maxPrice),
      remove: { minPrice: null, maxPrice: null },
    })
  }
  if (filters.minRating !== null) {
    chips.push({ label: `${filters.minRating}★ & up`, remove: { minRating: null } })
  }
  if (filters.inStock) chips.push({ label: 'In stock only', remove: { inStock: false } })
  if (chips.length === 0) return null

  return (
    <div className={styles.bar} aria-label="Active filters" role="region">
      <ul className={styles.chips}>
        {chips.map((chip) => (
          <li key={chip.label}>
            <button
              type="button"
              className={styles.chip}
              onClick={() => onChange(chip.remove)}
              aria-label={`Remove filter: ${chip.label}`}
            >
              {chip.label}
              <Icon name="close" size={14} />
            </button>
          </li>
        ))}
      </ul>
      <button type="button" className={styles.clear} onClick={onClearAll}>
        Clear all filters
      </button>
    </div>
  )
}
