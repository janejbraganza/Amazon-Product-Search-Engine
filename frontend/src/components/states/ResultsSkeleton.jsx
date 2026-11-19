import styles from './ResultsSkeleton.module.css'

/** Placeholder cards in the shape of the results grid, so nothing jumps when data arrives. */
export default function ResultsSkeleton({ count = 6 }) {
  return (
    <div role="status" className={styles.wrapper}>
      <span className="visually-hidden">Loading results…</span>
      <ul className={styles.grid} aria-hidden="true">
        {Array.from({ length: count }, (_, i) => (
          <li key={i} className={styles.card}>
            <div className={styles.thumb} />
            <div className={styles.body}>
              <div className={`${styles.line} ${styles.short}`} />
              <div className={styles.line} />
              <div className={`${styles.line} ${styles.medium}`} />
              <div className={`${styles.line} ${styles.price}`} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
