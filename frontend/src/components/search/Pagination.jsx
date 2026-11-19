import { Link } from 'react-router'
import { ELLIPSIS, getPageItems } from '../../utils/pagination.js'
import Icon from '../ui/Icon.jsx'
import styles from './Pagination.module.css'

/**
 * Page links (real links, so each page has its own shareable URL).
 * ``hrefFor(page)`` builds the URL for a page.
 */
export default function Pagination({ page, totalPages, hrefFor }) {
  if (totalPages <= 1) return null
  const items = getPageItems(page, totalPages)

  return (
    <nav className={styles.pagination} aria-label="Pagination">
      <PageLink
        to={page > 1 ? hrefFor(page - 1) : null}
        label="Previous page"
        className={styles.step}
      >
        <Icon name="chevronLeft" size={18} />
        <span className={styles.stepText}>Previous</span>
      </PageLink>

      <ol className={styles.pages}>
        {items.map((item, index) =>
          item === ELLIPSIS ? (
            <li key={`gap-${index}`} className={styles.gap} aria-hidden="true">
              {ELLIPSIS}
            </li>
          ) : (
            <li key={item}>
              <Link
                to={hrefFor(item)}
                className={styles.page}
                aria-label={`Page ${item}`}
                aria-current={item === page ? 'page' : undefined}
              >
                {item}
              </Link>
            </li>
          ),
        )}
      </ol>

      <PageLink
        to={page < totalPages ? hrefFor(page + 1) : null}
        label="Next page"
        className={styles.step}
      >
        <span className={styles.stepText}>Next</span>
        <Icon name="chevronRight" size={18} />
      </PageLink>
    </nav>
  )
}

function PageLink({ to, label, className, children }) {
  if (!to) {
    return (
      <span className={`${className} ${styles.disabled}`} aria-disabled="true" aria-label={label}>
        {children}
      </span>
    )
  }
  return (
    <Link to={to} className={className} aria-label={label}>
      {children}
    </Link>
  )
}
