import { useEffect } from 'react'
import { Link, useLocation, useParams } from 'react-router'
import Breadcrumbs from '../components/product/Breadcrumbs.jsx'
import ProductDetails from '../components/product/ProductDetails.jsx'
import detailStyles from '../components/product/ProductDetails.module.css'
import SimilarProducts from '../components/product/SimilarProducts.jsx'
import ErrorState from '../components/states/ErrorState.jsx'
import Icon from '../components/ui/Icon.jsx'
import { useProduct } from '../hooks/useProduct.js'
import { categoryUrl, returnToSearch } from '../utils/catalogue.js'
import styles from './Page.module.css'

/**
 * Product details from GET /api/v1/products/{id}.
 *
 * When the product was opened from search results, the result card passes that results
 * URL as router state, so "Back to results" and the breadcrumb return to exactly the same
 * search (query, filters, sort and page). Router state survives a page refresh.
 * Product IDs that cannot exist ("abc", "0") are rejected without asking the API.
 */
export default function ProductPage() {
  const { productId } = useParams()
  const location = useLocation()
  const returnTo = returnToSearch(location.state)
  const { status, product, error, retry } = useProduct(productId)

  // Opening another product (e.g. a similar product) starts at the top of the page.
  useEffect(() => {
    window.scrollTo({ top: 0 })
  }, [productId])

  const trail = [{ label: 'Home', to: '/' }]
  if (returnTo) trail.push({ label: `Results for “${returnTo.query}”`, to: returnTo.path })
  if (product) trail.push({ label: product.category, to: categoryUrl(product.category) })
  trail.push({ label: product ? product.product_name : 'Product' })

  return (
    <section className={styles.stack}>
      <title>
        {product
          ? `${product.product_name} – Product Search`
          : status === 'loading'
            ? 'Loading product – Product Search'
            : 'Product not available – Product Search'}
      </title>

      <div className={styles.topBar}>
        <Link to={returnTo ? returnTo.path : '/'} className={styles.back}>
          <Icon name="arrowLeft" size={16} />
          {returnTo ? 'Back to results' : 'Back to home'}
        </Link>
        <Breadcrumbs items={trail} />
      </div>

      {status === 'loading' && <ProductSkeleton />}

      {status === 'success' && (
        <>
          <ProductDetails product={product} />
          <SimilarProducts product={product} fromSearch={returnTo?.path} />
        </>
      )}

      {(status === 'not-found' || status === 'invalid') && (
        <div className={styles.centered}>
          <p className={styles.eyebrow}>{status === 'invalid' ? 'Invalid link' : '404'}</p>
          <h1 className={styles.title}>Product not found</h1>
          <p className={styles.muted}>
            {status === 'invalid'
              ? `“${productId}” is not a valid product ID.`
              : `There is no product with ID ${productId}. It may have been removed.`}
          </p>
          <Link to={returnTo ? returnTo.path : '/'} className={styles.button}>
            {returnTo ? 'Back to results' : 'Search for products'}
          </Link>
        </div>
      )}

      {status === 'error' && (
        <div>
          <h1 className="visually-hidden">Product {productId}</h1>
          <ErrorState error={error} onRetry={retry} title="Couldn’t load this product" />
        </div>
      )}
    </section>
  )
}

/** Placeholder in the shape of the details view; announced as "Loading product…". */
function ProductSkeleton() {
  return (
    <div role="status">
      <span className="visually-hidden">Loading product…</span>
      <div className={detailStyles.skeleton} aria-hidden="true">
        <div className={detailStyles.visual} />
        <div className={detailStyles.skeletonText}>
          <div className={detailStyles.skeletonLine} style={{ width: '30%' }} />
          <div className={detailStyles.skeletonLine} style={{ width: '85%', height: 28 }} />
          <div className={detailStyles.skeletonLine} style={{ width: '45%' }} />
          <div className={detailStyles.skeletonLine} style={{ width: '25%', height: 32 }} />
          <div className={detailStyles.skeletonLine} />
          <div className={detailStyles.skeletonLine} />
          <div className={detailStyles.skeletonLine} style={{ width: '70%' }} />
        </div>
      </div>
    </div>
  )
}
