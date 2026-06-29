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
      const s = Math.min(1, o.clientHeight / i.scrollHeight, o.clientWidth / i.scrollWidth)
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
      <div className="absolute inset-x-0 top-0 flex justify-center">
        <div
          ref={inner}
          className="origin-top"
          style={{ width, transform: `scale(${scale})`, visibility: scale ? 'visible' : 'hidden' }}
        >
          {children}
        </div>
      </div>
    </div>
  )
}
