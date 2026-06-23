import { useEffect, type ReactNode } from 'react'

/**
 * The detail drawer — slides in from the right over ~2/3 of the screen when a
 * table card is opened, carrying the full pit-boss detail (seat-ring, vitals,
 * integrity case, stand/sit controls). Its background is the same carpet as the
 * floor, so the panel reads as part of the room rather than a modal. Esc or the
 * close button dismisses it and the grid returns.
 */
export function TableDrawer({
  open,
  onClose,
  children,
}: {
  open: boolean
  onClose: () => void
  children: ReactNode
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  return (
    <aside
      className={`table-drawer${open ? ' is-open' : ''}`}
      role="dialog"
      aria-label="table detail"
      aria-hidden={!open}
    >
      <button type="button" className="drawer-close" onClick={onClose} aria-label="close detail">
        ✕
      </button>
      <div className="drawer-body">{children}</div>
    </aside>
  )
}
