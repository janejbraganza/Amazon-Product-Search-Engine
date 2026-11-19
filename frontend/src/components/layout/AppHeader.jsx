import { Link, NavLink, useLocation } from 'react-router'
import SearchForm from '../search/SearchForm.jsx'
import Icon from '../ui/Icon.jsx'
import styles from './AppHeader.module.css'
import ThemeToggle from './ThemeToggle.jsx'

/**
 * Site header on every page: logo (home), the search box (except on the home page, which
 * has its own large one), navigation and the light/dark theme toggle.
 * Wide screens: one row. Phones: logo, links and toggle on the first row, the search box
 * full width below - every item stays visible, so no menu button is needed.
 */
export default function AppHeader() {
  const { pathname } = useLocation()
  const showSearch = pathname !== '/'

  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <Link to="/" className={styles.brand} aria-label="Product Search home">
          <Icon name="logo" size={26} className={styles.logo} />
          <span className={styles.brandName}>Product Search</span>
        </Link>
        {showSearch && (
          <div className={styles.search}>
            <SearchForm />
          </div>
        )}
        <nav className={styles.nav} aria-label="Main">
          <ul className={styles.navList}>
            <li>
              <NavLink to="/" end className={styles.navLink}>
                Home
              </NavLink>
            </li>
            <li>
              <Link to="/#categories" className={styles.navLink}>
                Categories
              </Link>
            </li>
          </ul>
          <ThemeToggle />
        </nav>
      </div>
    </header>
  )
}
