import { formatCount } from '../../utils/format.js'
import styles from './SearchSummary.module.css'

/**
 * "Showing 21–40 of 231 results for “wireless ear”" plus details taken from the response:
 * the words a partial last word was expanded to, words that matched nothing, the response
 * time measured by the browser, and whether Redis served it (X-Cache: HIT).
 */
export default function SearchSummary({ data, meta }) {
  const { total, offset, items, query, prefix, expanded_terms: expanded } = data
  const first = total === 0 ? 0 : offset + 1
  const last = offset + items.length
  const unmatched = data.unmatched_terms.map((term) =>
    term.endsWith('*') ? `words starting with “${term.slice(0, -1)}”` : `“${term}”`,
  )

  return (
    <div className={styles.summary}>
      <p className={styles.count}>
        {total === 0 ? (
          <>No results for “{query.trim()}”</>
        ) : items.length === 0 ? (
          // A page past the end: never print an impossible range like "981–980".
          <>
            <strong>{formatCount(total)}</strong> {total === 1 ? 'result' : 'results'} for “
            {query.trim()}”
          </>
        ) : (
          <>
            Showing {formatCount(first)}–{formatCount(last)} of{' '}
            <strong>{formatCount(total)}</strong> {total === 1 ? 'result' : 'results'} for “
            {query.trim()}”
          </>
        )}
      </p>
      <p className={styles.details}>
        {prefix && expanded.length > 0 && (
          <span>
            “{prefix}” matched: {expanded.join(', ')}
          </span>
        )}
        {unmatched.length > 0 && total > 0 && (
          <span>No products contain {unmatched.join(', ')}</span>
        )}
        {meta && (
          <span className={styles.timing}>
            {meta.durationMs} ms{meta.cacheStatus === 'HIT' ? ' · served from cache' : ''}
          </span>
        )}
      </p>
    </div>
  )
}
