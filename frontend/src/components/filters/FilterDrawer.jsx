import { useEffect, useId, useRef } from 'react'
import Icon from '../ui/Icon.jsx'
import styles from './FilterDrawer.module.css'

const FOCUSABLE =
  'button:not([disabled]), input:not([disabled]), select:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])'

/**
 * Modal filter panel for small screens (accessible dialog).
 * - Focus moves into the dialog when it opens and back to the opening button when it closes.
 * - Tab / Shift+Tab stay inside the dialog; Escape or the close button closes it.
 * - The page behind does not scroll while it is open.
 */
export default function FilterDrawer({ onClose, onApply, onClear, applyDisabled, children }) {
  const titleId = useId()
  const dialogRef = useRef(null)

  useEffect(() => {
    const opener = document.activeElement
    const { overflow } = document.body.style
    document.body.style.overflow = 'hidden'
    dialogRef.current?.querySelector(FOCUSABLE)?.focus()
    return () => {
      document.body.style.overflow = overflow
      if (opener instanceof HTMLElement) opener.focus()
    }
  }, [])

  function handleKeyDown(event) {
    if (event.key === 'Escape') {
      event.stopPropagation()
      onClose()
      return
    }
    if (event.key !== 'Tab') return
    const focusable = [...dialogRef.current.querySelectorAll(FOCUSABLE)]
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  return (
    <div className={styles.backdrop} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div
        ref={dialogRef}
        className={styles.drawer}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onKeyDown={handleKeyDown}
      >
        <header className={styles.header}>
          <h2 id={titleId} className={styles.title}>
            Filters
          </h2>
          <button
            type="button"
            className={styles.close}
            onClick={onClose}
            aria-label="Close filters"
          >
            <Icon name="close" size={20} />
          </button>
        </header>
        <div className={styles.body}>{children}</div>
        <footer className={styles.footer}>
          <button type="button" className={styles.secondary} onClick={onClear}>
            Clear
          </button>
          <button
            type="button"
            className={styles.primary}
            onClick={onApply}
            disabled={applyDisabled}
          >
            Show results
          </button>
        </footer>
      </div>
    </div>
  )
}
