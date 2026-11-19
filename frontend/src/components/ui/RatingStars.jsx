import { formatRating } from '../../utils/format.js'
import styles from './RatingStars.module.css'

/** Five stars filled to the rating (e.g. 4.3 -> 86%), announced as "Rated 4.3 out of 5". */
export default function RatingStars({ rating }) {
  const value = Number(rating)
  const percent = Math.max(0, Math.min(100, (value / 5) * 100))
  return (
    <span className={styles.stars} role="img" aria-label={`Rated ${formatRating(value)} out of 5`}>
      <span className={styles.empty} aria-hidden="true">
        ★★★★★
      </span>
      <span className={styles.filled} style={{ width: `${percent}%` }} aria-hidden="true">
        ★★★★★
      </span>
    </span>
  )
}
