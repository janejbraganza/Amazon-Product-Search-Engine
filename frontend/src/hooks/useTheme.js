import { useCallback, useEffect, useState, useSyncExternalStore } from 'react'
import {
  applyTheme,
  readStoredTheme,
  storeTheme,
  subscribeToSystemTheme,
  systemTheme,
} from '../utils/theme.js'

/**
 * The active colour theme. Without a saved choice it follows the operating system (and
 * updates live when that changes); ``toggle`` switches light <-> dark and saves the choice.
 * @returns {{theme: 'light'|'dark', toggle: () => void}}
 */
export function useTheme() {
  const [chosen, setChosen] = useState(readStoredTheme)
  const system = useSyncExternalStore(subscribeToSystemTheme, systemTheme, () => 'light')
  const theme = chosen ?? system

  useEffect(() => {
    applyTheme(chosen)
  }, [chosen])

  const toggle = useCallback(() => {
    const next = theme === 'dark' ? 'light' : 'dark'
    storeTheme(next)
    setChosen(next)
  }, [theme])

  return { theme, toggle }
}
