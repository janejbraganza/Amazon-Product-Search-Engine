import { Outlet } from 'react-router'
import AppFooter from './AppFooter.jsx'
import AppHeader from './AppHeader.jsx'
import styles from './AppLayout.module.css'

/** Page frame shared by every route: skip link, header, main content, footer. */
export default function AppLayout() {
  return (
    <div className={styles.layout}>
      <a href="#main-content" className={styles.skipLink}>
        Skip to content
      </a>
      <AppHeader />
      <main id="main-content" className={styles.main} tabIndex={-1}>
        <Outlet />
      </main>
      <AppFooter />
    </div>
  )
}
