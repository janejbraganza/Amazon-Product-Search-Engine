import { Link } from 'react-router'
import styles from './Page.module.css'

export default function NotFoundPage() {
  return (
    <section className={styles.centered} aria-labelledby="not-found-title">
      <p className={styles.eyebrow}>404</p>
      <h1 id="not-found-title" className={styles.title}>
        Page not found
      </h1>
      <p className={styles.muted}>The page you’re looking for doesn’t exist or has moved.</p>
      <Link to="/" className={styles.button}>
        Go to search
      </Link>
    </section>
  )
}
