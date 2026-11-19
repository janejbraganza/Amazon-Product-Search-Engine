/**
 * Colour theme helpers. The CSS (styles/tokens.css) follows the operating-system setting
 * unless <html data-theme="light|dark"> is set; the header toggle sets that attribute and
 * remembers the choice in localStorage. index.html applies a stored choice before the first
 * paint (same key), so the page never flashes the wrong theme.
 */
export const THEME_STORAGE_KEY = 'pse-theme'
const THEMES = ['light', 'dark']
const DARK_QUERY = '(prefers-color-scheme: dark)'

/** The visitor's saved choice, or null (no choice, storage blocked or a bad value). */
export function readStoredTheme() {
  try {
    const value = window.localStorage.getItem(THEME_STORAGE_KEY)
    return THEMES.includes(value) ? value : null
  } catch {
    return null
  }
}

/** Save the choice; returns false when storage is unavailable (the toggle still works). */
export function storeTheme(theme) {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme)
    return true
  } catch {
    return false
  }
}

/** Set or remove <html data-theme>; null means "follow the operating system". */
export function applyTheme(theme) {
  const root = document.documentElement
  if (theme) root.dataset.theme = theme
  else delete root.dataset.theme
}

function darkQuery() {
  return typeof window.matchMedia === 'function' ? window.matchMedia(DARK_QUERY) : null
}

/** 'dark' when the operating system prefers dark colours, otherwise 'light'. */
export function systemTheme() {
  return darkQuery()?.matches ? 'dark' : 'light'
}

/** Call ``onChange`` when the operating-system preference changes; returns an unsubscribe. */
export function subscribeToSystemTheme(onChange) {
  const query = darkQuery()
  if (!query) return () => {}
  query.addEventListener('change', onChange)
  return () => query.removeEventListener('change', onChange)
}
