import { Link } from 'react-router'
import { brandUrl, categoryIcon, categoryUrl } from '../../utils/catalogue.js'
import {
  formatCount,
  formatDate,
  formatPrice,
  formatRating,
  stockStatus,
} from '../../utils/format.js'
import Badge from '../ui/Badge.jsx'
import Icon from '../ui/Icon.jsx'
import RatingStars from '../ui/RatingStars.jsx'
import styles from './ProductDetails.module.css'

/**
 * Everything GET /api/v1/products/{id} returns about one product. There are no product
 * images in the data, so the picture area shows the category's icon.
 */
export default function ProductDetails({ product }) {
  const stock = stockStatus(product.stock_quantity)
  const added = formatDate(product.created_at)
  const reviews = `${formatCount(product.review_count)} ${product.review_count === 1 ? 'review' : 'reviews'}`

  return (
    <article className={styles.detail} aria-labelledby="product-title">
      <div className={styles.visual} aria-hidden="true">
        <Icon name={categoryIcon(product.category)} size={72} />
      </div>

      <div className={styles.info}>
        <p className={styles.meta}>
          <Link to={brandUrl(product.brand)} className={styles.metaLink}>
            {product.brand}
          </Link>
          <span aria-hidden="true">·</span>
          <Link to={categoryUrl(product.category)} className={styles.metaLink}>
            {product.category}
          </Link>
        </p>
        <h1 id="product-title" className={styles.title}>
          {product.product_name}
        </h1>

        <div className={styles.rating}>
          <RatingStars rating={product.rating} />
          <span className={styles.ratingValue}>{formatRating(product.rating)} out of 5</span>
          <span className={styles.muted}>({reviews})</span>
        </div>

        <p className={styles.price}>{formatPrice(product.price)}</p>
        <p className={styles.stock}>
          <Badge tone={stock.tone}>{stock.label}</Badge>
        </p>

        <section aria-labelledby="description-title" className={styles.block}>
          <h2 id="description-title" className={styles.blockTitle}>
            Description
          </h2>
          <p className={styles.description}>{product.description}</p>
        </section>

        <section aria-labelledby="details-title" className={styles.block}>
          <h2 id="details-title" className={styles.blockTitle}>
            Product details
          </h2>
          <dl className={styles.facts}>
            <div>
              <dt>Brand</dt>
              <dd>{product.brand}</dd>
            </div>
            <div>
              <dt>Category</dt>
              <dd>{product.category}</dd>
            </div>
            <div>
              <dt>Customer rating</dt>
              <dd>
                {formatRating(product.rating)} out of 5 ({reviews})
              </dd>
            </div>
            <div>
              <dt>Units in stock</dt>
              <dd>{formatCount(product.stock_quantity)}</dd>
            </div>
            {added && (
              <div>
                <dt>Added to catalogue</dt>
                <dd>{added}</dd>
              </div>
            )}
            <div>
              <dt>Product ID</dt>
              <dd className={styles.mono}>{product.id}</dd>
            </div>
          </dl>
        </section>
      </div>
    </article>
  )
}
