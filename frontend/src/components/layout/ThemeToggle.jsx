import { useTheme } from '../../hooks/useTheme.js'
import Icon from '../ui/Icon.jsx'
import styles from './AppHeader.module.css'

/**
 * Light/dark switch: a toggle button ("Dark theme", pressed when dark is on). The icon
 * shows the theme you would switch to.
 */
export default function ThemeToggle() {
  const { theme, toggle } = useTheme()
  const dark = theme === 'dark'
  return (
    <button
      type="button"
      className={styles.iconButton}
      onClick={toggle}
      aria-pressed={dark}
      title={dark ? 'Switch to light theme' : 'Switch to dark theme'}
    >
      <Icon name={dark ? 'sun' : 'moon'} size={20} />
      <span className="visually-hidden">Dark theme</span>
    </button>
  )
}
