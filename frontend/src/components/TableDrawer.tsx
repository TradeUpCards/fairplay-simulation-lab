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
      className={`fixed right-0 top-0 z-60 flex h-screen w-[min(66.6vw,1040px)] flex-col border-l-2 border-l-brass shadow-[-22px_0_54px_rgba(0,0,0,0.55)] transition-transform duration-340 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none ${
        open ? 'translate-x-0' : 'translate-x-[101%]'
      }`}
      style={{
        // same carpet as the floor (resolved once in styles.css as var(--carpet)),
        // dimmed by a gradient wash so the panel reads as part of the room
        backgroundColor: '#0d0a07',
        backgroundImage:
          'linear-gradient(rgba(13,10,7,0.8), rgba(13,10,7,0.88)), var(--carpet)',
        backgroundRepeat: 'no-repeat, repeat',
        backgroundSize: 'auto, 150px auto',
      }}
      role="dialog"
      aria-label="table detail"
      aria-hidden={!open}
    >
      <button
        type="button"
        className="absolute right-5 top-5 z-2 flex h-8 w-8 items-center justify-center rounded-full border border-line bg-[rgba(0,0,0,0.45)] p-0 text-[0.85rem] leading-none text-text hover:border-brass hover:text-brass"
        onClick={onClose}
        aria-label="close detail"
      >
        ✕
      </button>
      <div className="overflow-y-auto px-9 pb-12 pt-8">{children}</div>
    </aside>
  )
}
