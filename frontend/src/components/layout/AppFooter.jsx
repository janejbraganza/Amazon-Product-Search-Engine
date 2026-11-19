import { Link } from 'react-router'
import styles from './AppFooter.module.css'

export default function AppFooter() {
  return (
    <footer className={styles.footer}>
      <div className={styles.inner}>
        <div className={styles.about}>
          <p className={styles.name}>Product Search Engine</p>
          <p>
            A software engineering portfolio project. The catalogue is synthetic demo data:
            products, brands, prices, ratings and reviews are generated, not real.
          </p>
          <p className={styles.stack}>
            FastAPI · PostgreSQL · inverted index with BM25 ranking · Trie autocomplete · Redis
            caching · React
          </p>
        </div>
        <nav aria-label="Footer">
          <ul className={styles.links}>
            <li>
              <Link to="/">Home</Link>
            </li>
            <li>
              <Link to="/#categories">Browse categories</Link>
            </li>
          </ul>
        </nav>
      </div>
    </footer>
  )
}
