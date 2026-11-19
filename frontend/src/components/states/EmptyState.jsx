import { Link } from 'react-router'
import Icon from '../ui/Icon.jsx'
import styles from './StateMessage.module.css'

/**
 * No results. Suggestions are based only on what the request actually was:
 * - "Match any word" when all words were required and there are several words,
 * - "Include partial words" when "Exact words only" was on,
 * - "Clear all filters" when filters were active.
 * ``links`` holds ready-made URLs for those alternatives (null when not applicable).
 */
export default function EmptyState({ query, unmatchedTerms = [], links }) {
  const unmatched = unmatchedTerms.map((term) =>
    term.endsWith('*') ? `words starting with “${term.slice(0, -1)}”` : `“${term}”`,
  )
  const hasAlternatives = links.anyWord || links.partialWords || links.clearFilters

  return (
    <section className={styles.state} aria-labelledby="empty-title">
      <Icon name="searchOff" size={40} className={styles.icon} />
      <h2 id="empty-title" className={styles.title}>
        No products match “{query}”
      </h2>
      {unmatched.length > 0 && (
        <p className={styles.text}>No product contains {unmatched.join(', ')}.</p>
      )}
      <ul className={styles.tips}>
        {links.anyWord && (
          <li>
            <Link to={links.anyWord}>Show products matching any of these words</Link>
          </li>
        )}
        {links.partialWords && (
          <li>
            <Link to={links.partialWords}>Include partial word matches</Link>
          </li>
        )}
        {links.clearFilters && (
          <li>
            <Link to={links.clearFilters}>Clear all filters</Link>
          </li>
        )}
        <li>
          {hasAlternatives ? 'Or check' : 'Check'} the spelling, or try fewer or more general words.
        </li>
      </ul>
    </section>
  )
}
