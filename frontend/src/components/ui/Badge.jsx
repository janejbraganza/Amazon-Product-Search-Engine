import styles from './Badge.module.css'

/** Small status label. ``tone`` sets the colour; the text always carries the meaning. */
export default function Badge({ tone = 'neutral', children }) {
  return <span className={`${styles.badge} ${styles[tone]}`}>{children}</span>
}
