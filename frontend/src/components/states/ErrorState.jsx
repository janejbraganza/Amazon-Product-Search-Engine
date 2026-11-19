import Icon from '../ui/Icon.jsx'
import styles from './StateMessage.module.css'

/**
 * A failed request. ``error`` is an ApiError, whose message is always user-safe.
 * A 422 means the query itself was rejected (e.g. only stop words), so retrying the same
 * request would not help: the message asks for different words instead of offering Retry.
 * ``title`` replaces the default heading (e.g. on the product page).
 */
export default function ErrorState({ error, onRetry, title }) {
  const rejectedQuery = error?.status === 422
  return (
    <section className={`${styles.state} ${styles.error}`} role="alert">
      <Icon name="alert" size={40} className={styles.icon} />
      <h2 className={styles.title}>
        {title ?? (rejectedQuery ? 'Try a different search' : 'Search is unavailable right now')}
      </h2>
      <p className={styles.text}>{error?.message ?? 'Something went wrong.'}</p>
      {rejectedQuery ? (
        <p className={styles.text}>Use words that describe a product, brand or category.</p>
      ) : (
        <button type="button" className={styles.button} onClick={onRetry}>
          Try again
        </button>
      )}
    </section>
  )
}
