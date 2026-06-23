import { useEffect, useRef, useState } from 'react'

/**
 * A number that counts from its previous value to a new one when `value`
 * changes — the "watch the score recalculate" effect over the SSE stream. On the
 * very first render it shows the target immediately (no animation), so static
 * renders and unit tests see the final value with no frame ticking.
 */
export function AnimatedNumber({
  value,
  durationMs = 650,
  format = (n) => n.toFixed(0),
}: {
  value: number
  durationMs?: number
  format?: (n: number) => string
}) {
  const [display, setDisplay] = useState(value)
  const fromRef = useRef(value)
  const frameRef = useRef<number | null>(null)
  const startedRef = useRef(false)

  useEffect(() => {
    // First mount: snap to the value, don't animate.
    if (!startedRef.current) {
      startedRef.current = true
      fromRef.current = value
      setDisplay(value)
      return
    }
    const from = fromRef.current
    const to = value
    if (from === to) return

    let startTs: number | null = null
    const tick = (ts: number) => {
      if (startTs === null) startTs = ts
      const t = Math.min(1, (ts - startTs) / durationMs)
      const eased = 1 - (1 - t) * (1 - t) // easeOutQuad
      setDisplay(from + (to - from) * eased)
      if (t < 1) {
        frameRef.current = requestAnimationFrame(tick)
      } else {
        fromRef.current = to
      }
    }
    frameRef.current = requestAnimationFrame(tick)
    return () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current)
    }
  }, [value, durationMs])

  // tabular-nums keeps the width steady so the digits don't jitter while counting
  return <span className="tabular-nums">{format(display)}</span>
}
