import { Link } from 'react-router'
import styles from './Breadcrumbs.module.css'

/**
 * Breadcrumb trail (WAI-ARIA breadcrumb pattern): a labelled nav with an ordered list.
 * Every item but the last is a link; the last is the current page (aria-current="page").
 * @param {{items: {label: string, to?: string}[]}} props
 */
export default function Breadcrumbs({ items }) {
  return (
    <nav aria-label="Breadcrumb" className={styles.nav}>
      <ol className={styles.list}>
        {items.map((item, index) => {
          const current = index === items.length - 1
          return (
            <li key={`${index}-${item.label}`} className={styles.item}>
              {current ? (
                <span aria-current="page" className={styles.current}>
                  {item.label}
                </span>
              ) : (
                <Link to={item.to} className={styles.link}>
                  {item.label}
                </Link>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
