import { Link } from 'react-router'
import { formatCount, formatPrice, formatRating, stockStatus } from '../../utils/format.js'
import Badge from '../ui/Badge.jsx'
import Icon from '../ui/Icon.jsx'
import RatingStars from '../ui/RatingStars.jsx'
import HighlightedText from './HighlightedText.jsx'
import styles from './ProductCard.module.css'

/**
 * One search result. Shows only fields the API returns: name, brand, category,
 * description, price, rating, review_count, stock_quantity (no images exist).
 * ``headingLevel`` keeps the outline correct where cards sit under an h2 (e.g. h3).
 */
export default function ProductCard({ product, terms = [], fromSearch, headingLevel = 2 }) {
  const Heading = `h${headingLevel}`
  const stock = stockStatus(product.stock_quantity)
  const titleId = `product-${product.id}-title`
  return (
    <article className={styles.card} aria-labelledby={titleId}>
      <div className={styles.thumb} aria-hidden="true">
        <Icon name="package" size={28} />
      </div>
      <div className={styles.body}>
        <p className={styles.meta}>
          <span className={styles.brand}>{product.brand}</span>
          <span className={styles.dot} aria-hidden="true">
            ·
          </span>
          <span>{product.category}</span>
        </p>
        <Heading id={titleId} className={styles.title}>
          <Link to={`/products/${product.id}`} state={{ fromSearch }} className={styles.link}>
            <HighlightedText text={product.product_name} terms={terms} />
          </Link>
        </Heading>
        <p className={styles.description}>{product.description}</p>
        <div className={styles.rating}>
          <RatingStars rating={product.rating} />
          <span className={styles.ratingValue}>{formatRating(product.rating)}</span>
          <span className={styles.reviews}>({formatCount(product.review_count)} reviews)</span>
        </div>
        <div className={styles.footer}>
          <span className={styles.price}>{formatPrice(product.price)}</span>
          <Badge tone={stock.tone}>{stock.label}</Badge>
        </div>
      </div>
    </article>
  )
}
