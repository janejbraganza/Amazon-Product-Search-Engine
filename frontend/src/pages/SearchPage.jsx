import { useCallback, useEffect, useState } from 'react'
import { Navigate, useLocation, useNavigate, useSearchParams } from 'react-router'
import ActiveFilters from '../components/filters/ActiveFilters.jsx'
import FilterDrawer from '../components/filters/FilterDrawer.jsx'
import FilterPanel from '../components/filters/FilterPanel.jsx'
import Pagination from '../components/search/Pagination.jsx'
import ProductCard from '../components/search/ProductCard.jsx'
import SearchControls from '../components/search/SearchControls.jsx'
import SearchSummary from '../components/search/SearchSummary.jsx'
import EmptyState from '../components/states/EmptyState.jsx'
import ErrorState from '../components/states/ErrorState.jsx'
import ResultsSkeleton from '../components/states/ResultsSkeleton.jsx'
import Icon from '../components/ui/Icon.jsx'
import { useCategories } from '../hooks/useCategories.js'
import { useSearch } from '../hooks/useSearch.js'
import { formatCount } from '../utils/format.js'
import { pageCount } from '../utils/pagination.js'
import {
  activeFilterCount,
  NO_FILTERS,
  parseSearchState,
  searchUrl,
  toApiParams,
} from '../utils/searchState.js'
import styles from './SearchPage.module.css'

function filtersOf(state) {
  const { categories, brands, minPrice, maxPrice, minRating, inStock } = state
  return { categories, brands, minPrice, maxPrice, minRating, inStock }
}

/**
 * Search results. Everything (query, match mode, exact words, sort, filters, page, page
 * size) comes from the URL; controls, filters and pagination only change the URL. So
 * refresh, Back/Forward and shared links always show the same search. Filtering, sorting,
 * facet counts and pagination are all done by the backend.
 */
export default function SearchPage() {
  const [searchParams] = useSearchParams()
  const location = useLocation()
  const navigate = useNavigate()
  const state = parseSearchState(searchParams)
  const { data, meta, error, isLoading, isCurrent, retry } = useSearch(toApiParams(state))
  const catalogue = useCategories()
  const [draft, setDraft] = useState(null) // mobile drawer: filters being edited, or null
  const [draftPriceValid, setDraftPriceValid] = useState(true)
  const [clearCount, setClearCount] = useState(0) // resets the sidebar price boxes

  const totalPages = data ? pageCount(data.total, state.perPage) : 1
  const pageOutOfRange = isCurrent && data && data.total > 0 && state.page > totalPages

  // A page number past the end (old link, hand-edited URL) -> go to the last page.
  useEffect(() => {
    if (pageOutOfRange) {
      navigate(searchUrl({ ...state, page: totalPages }), { replace: true })
    }
  }, [pageOutOfRange, navigate, state, totalPages])

  // New page of results -> start at the top.
  useEffect(() => {
    window.scrollTo({ top: 0 })
  }, [state.page])

  // Any change of options, sort or filters starts again at page 1.
  const search = searchParams.toString()
  const changeOptions = useCallback(
    (changes) => {
      const current = parseSearchState(new URLSearchParams(search))
      navigate(searchUrl({ ...current, ...changes, page: 1 }))
    },
    [navigate, search],
  )

  if (!state.q) return <Navigate to="/" replace />

  // A response for a page past the end has a total but no items: never display it (the
  // redirect above replaces it). Results from an earlier, different query are also never
  // shown while the new one loads (and neither are its facet counts).
  const emptyPage = data && data.total > 0 && data.items.length === 0
  const showPrevious = data && data.query.trim() === state.q && !emptyPage
  const facets = showPrevious ? data.facets : null
  const filters = filtersOf(state)
  const filterCount = activeFilterCount(state)

  // Read out by screen readers when results arrive (the skeleton announces loading and
  // the error message is an alert). The region always exists, so every change is heard.
  let announcement = ''
  if (!error && showPrevious && !isLoading) {
    const { total, offset, items } = data
    announcement =
      total === 0
        ? `No products match “${state.q}”.`
        : `Results ${formatCount(offset + 1)} to ${formatCount(offset + items.length)} of ${formatCount(total)} for “${state.q}”.`
  }

  const panelProps = {
    facets,
    catalogue: catalogue.categories,
    categoriesFailed: catalogue.status === 'error',
  }

  return (
    <section aria-labelledby="search-title" className={styles.page}>
      <title>{`${state.q} – Product Search`}</title>
      <h1 id="search-title" className="visually-hidden">
        Results for “{state.q}”
      </h1>
      <p className="visually-hidden" aria-live="polite" aria-atomic="true">
        {announcement}
      </p>

      <div className={styles.layout}>
        <aside className={styles.sidebar} aria-label="Filters">
          <h2 className={styles.sidebarTitle}>Filters</h2>
          <FilterPanel
            {...panelProps}
            filters={filters}
            onChange={changeOptions}
            resetKey={clearCount}
          />
        </aside>

        <div className={styles.main}>
          <div className={styles.toolbar}>
            <SearchControls
              mode={state.mode}
              exact={state.exact}
              sort={state.sort}
              perPage={state.perPage}
              onChange={changeOptions}
            />
            <button
              type="button"
              className={styles.filtersButton}
              onClick={() => {
                setDraftPriceValid(true)
                setDraft(filters)
              }}
              aria-haspopup="dialog"
            >
              <Icon name="filter" size={18} />
              Filters
              {filterCount > 0 && <span className={styles.badge}>{filterCount}</span>}
            </button>
          </div>

          <ActiveFilters
            filters={filters}
            onChange={changeOptions}
            onClearAll={() => {
              setClearCount((n) => n + 1)
              changeOptions(NO_FILTERS)
            }}
          />

          {error ? (
            <ErrorState error={error} onRetry={retry} />
          ) : !showPrevious ? (
            <ResultsSkeleton />
          ) : data.total === 0 ? (
            <EmptyState
              query={state.q}
              unmatchedTerms={data.unmatched_terms}
              links={{
                anyWord:
                  state.mode === 'all' && data.terms.length + (data.prefix ? 1 : 0) > 1
                    ? searchUrl({ ...state, mode: 'any', page: 1 })
                    : null,
                partialWords: state.exact ? searchUrl({ ...state, exact: false, page: 1 }) : null,
                clearFilters:
                  filterCount > 0 ? searchUrl({ ...state, ...NO_FILTERS, page: 1 }) : null,
              }}
            />
          ) : (
            <div className={isLoading ? styles.refreshing : undefined} aria-busy={isLoading}>
              <SearchSummary data={data} meta={meta} />
              <ul className={styles.grid}>
                {data.items.map((product) => (
                  <li key={product.id}>
                    <ProductCard
                      product={product}
                      terms={[...data.terms, ...data.expanded_terms]}
                      fromSearch={location.pathname + location.search}
                    />
                  </li>
                ))}
              </ul>
              <Pagination
                page={state.page}
                totalPages={totalPages}
                hrefFor={(page) => searchUrl({ ...state, page })}
              />
            </div>
          )}
        </div>
      </div>

      {draft && (
        <FilterDrawer
          onClose={() => setDraft(null)}
          onClear={() => setDraft(NO_FILTERS)}
          onApply={() => {
            navigate(searchUrl({ ...state, ...draft, page: 1 }))
            setDraft(null)
          }}
          applyDisabled={!draftPriceValid}
        >
          <FilterPanel
            {...panelProps}
            filters={draft}
            onChange={(changes) => setDraft((current) => ({ ...current, ...changes }))}
            priceDelay={0}
            onPriceValidityChange={setDraftPriceValid}
          />
        </FilterDrawer>
      )}
    </section>
  )
}
