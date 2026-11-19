import { useSearch } from '../../hooks/useSearch.js'
import { similarQuery } from '../../utils/catalogue.js'
import ProductCard from '../search/ProductCard.jsx'
import styles from './ProductDetails.module.css'

const SHOWN = 4

/**
 * "Similar products": a real search, not a recommendation model. The existing search API
 * is asked for the product's own name in "any word" mode, restricted to the product's
 * category, so BM25 ranks the products sharing the most (and rarest) words first. The
 * product itself is removed. Nothing is shown while loading, on failure, or when the
 * search finds no other products, so the page never shows invented or stale items.
 */
export default function SimilarProducts({ product, fromSearch }) {
  const { data, error, isCurrent } = useSearch({
    q: similarQuery(product.product_name),
    mode: 'any',
    prefix: false,
    limit: SHOWN + 1, // one extra in case the product itself is among the results
    category: [product.category],
  })
  if (error || !isCurrent || !data) return null
  const items = data.items.filter((item) => item.id !== product.id).slice(0, SHOWN)
  if (items.length === 0) return null

  return (
    <section className={styles.similar} aria-labelledby="similar-title">
      <h2 id="similar-title" className={styles.sectionTitle}>
        Similar products
      </h2>
      <p className={styles.sectionNote}>
        Other {product.category} products whose names share words with this one, ranked by BM25
        relevance.
      </p>
      <ul className={styles.similarGrid}>
        {items.map((item) => (
          <li key={item.id}>
            <ProductCard product={item} fromSearch={fromSearch} headingLevel={3} />
          </li>
        ))}
      </ul>
    </section>
  )
}
