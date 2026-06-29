import { useEffect, useRef, useState, type ReactNode } from 'react'

/**
 * Scale a fixed-width block down to fill the available box (height + width) so an
 * embedded live view shows as large as possible without scrolling or clipping.
 * CSS transforms don't change layout size, so scrollHeight/Width report the
 * natural (unscaled) size — we divide to get the fit scale, and re-fit on resize.
 */
export function FitToBox({ width, children }: { width: number; children: ReactNode }) {
  const outer = useRef<HTMLDivElement>(null)
  const inner = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(0)

  useEffect(() => {
    const fit = () => {
      const o = outer.current
      const i = inner.current
      if (!o || !i) return
      // Measure the content child, not the transformed wrapper: a `position:fixed`
      // descendant (e.g. the lobby's seat-events drawer, translated off-screen when
      // closed) is contained by this transformed ancestor and inflates the wrapper's
      // scrollHeight. The child's own box reports the true natural size.
      const c = (i.firstElementChild as HTMLElement) ?? i
      const natH = c.offsetHeight || i.scrollHeight
      const natW = c.offsetWidth || i.scrollWidth
      const s = Math.min(1, o.clientHeight / natH, o.clientWidth / natW)
      setScale(s > 0 ? s : 1)
    }
    fit()
    const ro = new ResizeObserver(fit)
    if (outer.current) ro.observe(outer.current)
    if (inner.current) ro.observe(inner.current)
    return () => ro.disconnect()
  }, [])

  return (
    <div ref={outer} className="relative min-h-0 flex-1 overflow-hidden">
      <div className="absolute inset-0 flex items-center justify-center">
        <div
          ref={inner}
          className="origin-center shrink-0"
          style={{ width, transform: `scale(${scale})`, visibility: scale ? 'visible' : 'hidden' }}
        >
          {children}
        </div>
      </div>
    </div>
  )
}
