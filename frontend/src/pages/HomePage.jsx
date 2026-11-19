import { useEffect, useRef } from 'react'
import { Link, useLocation } from 'react-router'
import SearchForm from '../components/search/SearchForm.jsx'
import Icon from '../components/ui/Icon.jsx'
import { useCategories } from '../hooks/useCategories.js'
import { useResultCounts } from '../hooks/useResultCounts.js'
import { categoryIcon, categoryUrl } from '../utils/catalogue.js'
import { formatCount } from '../utils/format.js'
import { searchUrl } from '../utils/searchState.js'
import styles from './HomePage.module.css'

// Example searches across several categories. Their result counts are fetched from the
// search API, so the numbers shown are always the catalogue's real ones.
const EXAMPLE_SEARCHES = [
  'wireless earbuds',
  'laptop',
  'stainless steel',
  'yoga mat',
  'mystery novel',
]

const CAPABILITIES = [
  {
    icon: 'ranking',
    title: 'BM25 relevance ranking',
    text: 'An inverted index scores every match with BM25, weighting product names above brands, categories and descriptions, so the best matches come first.',
  },
  {
    icon: 'autocomplete',
    title: 'Trie-based autocomplete',
    text: 'Suggestions appear as you type. A Trie completes the last word you are typing and shows how many products contain each completion.',
  },
  {
    icon: 'bolt',
    title: 'Redis caching',
    text: 'Search results are cached in Redis, so a repeated search is answered from the cache instead of being ranked again.',
  },
  {
    icon: 'sliders',
    title: 'Filtering and sorting',
    text: 'Narrow results by category, brand, price, rating and stock, with live counts for each option, and sort by relevance, price, rating or newest.',
  },
]

/** "laptop, 220 results" (the visible text first, then the count when it is known). */
function exampleLabel(q, count) {
  if (typeof count !== 'number') return undefined
  return `${q}, ${formatCount(count)} ${count === 1 ? 'result' : 'results'}`
}

export default function HomePage() {
  const catalogue = useCategories()
  const counts = useResultCounts(EXAMPLE_SEARCHES)
  const location = useLocation()
  const categoriesHeading = useRef(null)
  const loaded = catalogue.status === 'success' && catalogue.categories.length > 0
  const largest = loaded ? catalogue.categories[0] : null // most products first

  // "Categories" in the header links to /#categories: scroll there and move focus to it.
  useEffect(() => {
    if (location.hash !== '#categories') return
    const heading = categoriesHeading.current
    heading?.scrollIntoView?.({ block: 'start' })
    heading?.focus({ preventScroll: true })
  }, [location.hash, location.key])

  return (
    <div className={styles.page}>
      <section className={styles.hero} aria-labelledby="home-title">
        <p className={styles.eyebrow}>Product search engine</p>
        <h1 id="home-title" className={styles.title}>
          Find the right product, fast.
        </h1>
        <p className={styles.subtitle}>
          {loaded && catalogue.totalProducts
            ? `Search ${formatCount(catalogue.totalProducts)} products across ${catalogue.categories.length} categories, ranked by relevance as you type.`
            : 'Search the product catalogue, ranked by relevance as you type.'}
        </p>
        <div className={styles.search}>
          <SearchForm size="large" autoFocus />
        </div>
        <div className={styles.examples}>
          <h2 className={styles.examplesLabel}>Try a search</h2>
          <ul className={styles.exampleList}>
            {EXAMPLE_SEARCHES.map((q) => (
              <li key={q}>
                <Link
                  className={styles.example}
                  to={searchUrl({ q })}
                  aria-label={exampleLabel(q, counts[q])}
                >
                  {q}
                  {typeof counts[q] === 'number' && (
                    <span className={styles.exampleCount}>{formatCount(counts[q])}</span>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className={styles.section} aria-labelledby="categories-title" id="categories">
        <div className={styles.sectionHeader}>
          <h2
            id="categories-title"
            className={styles.sectionTitle}
            ref={categoriesHeading}
            tabIndex={-1}
          >
            Browse by category
          </h2>
          {loaded && (
            <p className={styles.sectionNote}>
              {catalogue.categories.length} categories · {formatCount(catalogue.totalProducts)}{' '}
              products
            </p>
          )}
        </div>

        {catalogue.status === 'loading' && (
          <div role="status">
            <span className="visually-hidden">Loading categories…</span>
            <ul className={styles.categoryGrid} aria-hidden="true">
              {Array.from({ length: 10 }, (_, i) => (
                <li key={i} className={`${styles.categoryCard} ${styles.placeholder}`} />
              ))}
            </ul>
          </div>
        )}

        {catalogue.status === 'error' && (
          <div className={styles.notice} role="alert">
            <p>Categories couldn’t be loaded. You can still search for any product above.</p>
            <button type="button" className={styles.secondaryButton} onClick={catalogue.retry}>
              Try again
            </button>
          </div>
        )}

        {catalogue.status === 'success' && (
          <ul className={styles.categoryGrid}>
            {catalogue.categories.map((category) => (
              <li key={category.name}>
                <Link
                  to={categoryUrl(category.name)}
                  className={styles.categoryCard}
                  aria-label={`${category.name}, ${formatCount(category.product_count)} ${category.product_count === 1 ? 'product' : 'products'}`}
                >
                  <span className={styles.categoryIcon} aria-hidden="true">
                    <Icon name={categoryIcon(category.name)} size={24} />
                  </span>
                  <span className={styles.categoryName}>{category.name}</span>
                  <span className={styles.categoryCount}>
                    {formatCount(category.product_count)}{' '}
                    {category.product_count === 1 ? 'product' : 'products'}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className={styles.section} aria-labelledby="capabilities-title">
        <div className={styles.sectionHeader}>
          <h2 id="capabilities-title" className={styles.sectionTitle}>
            How the search works
          </h2>
        </div>
        <ul className={styles.capabilityGrid}>
          {CAPABILITIES.map((capability) => (
            <li key={capability.title} className={styles.capability}>
              <span className={styles.capabilityIcon} aria-hidden="true">
                <Icon name={capability.icon} size={22} />
              </span>
              <h3 className={styles.capabilityTitle}>{capability.title}</h3>
              <p className={styles.capabilityText}>{capability.text}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className={styles.cta} aria-labelledby="cta-title">
        <h2 id="cta-title" className={styles.ctaTitle}>
          Ready to explore?
        </h2>
        <p className={styles.ctaText}>
          Search for anything, or start with the largest category and narrow it down with filters.
        </p>
        <div className={styles.ctaActions}>
          {largest && (
            <Link to={categoryUrl(largest.name)} className={styles.primaryButton}>
              Explore {largest.name}
              <Icon name="arrowRight" size={18} />
            </Link>
          )}
          <button
            type="button"
            className={largest ? styles.secondaryButton : styles.primaryButton}
            onClick={() => document.getElementById('search-input-large')?.focus()}
          >
            Start searching
          </button>
        </div>
      </section>
    </div>
  )
}
