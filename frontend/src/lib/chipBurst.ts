/**
 * Canvas chip-burst particle effect for the replay finish — ported from
 * demo/fairplay-live-sim.html. Draws poker chips bursting up-and-out from
 * `(x, y)` in the canvas's own coordinate space (the chart uses an 820×460
 * coordinate box, matching the SVG viewBox, so callers pass chart coords). The
 * returned function cancels and clears. No-ops if the 2D context is unavailable
 * (e.g. jsdom), so it's safe to call unconditionally.
 */
const CHIP_COLORS = ['#e5484d', '#4f7cff', '#2ecc71', '#f5c451', '#eef1f5', '#1c2230']

interface Chip {
  x: number
  y: number
  vx: number
  vy: number
  r: number
  rot: number
  vr: number
  c: string
}

function drawChip(
  g: CanvasRenderingContext2D,
  x: number,
  y: number,
  r: number,
  rot: number,
  color: string,
): void {
  g.save()
  g.translate(x, y)
  g.rotate(rot)
  g.beginPath()
  g.arc(0, 0, r, 0, Math.PI * 2)
  g.fillStyle = color
  g.fill()
  g.lineWidth = 2
  g.strokeStyle = 'rgba(255,255,255,.85)'
  for (let i = 0; i < 6; i++) {
    g.save()
    g.rotate((i * Math.PI) / 3)
    g.beginPath()
    g.moveTo(0, -r)
    g.lineTo(0, -r + 5)
    g.stroke()
    g.restore()
  }
  g.beginPath()
  g.arc(0, 0, r * 0.58, 0, Math.PI * 2)
  g.strokeStyle = 'rgba(255,255,255,.55)'
  g.lineWidth = 1.5
  g.stroke()
  g.restore()
}

export function runChipBurst(canvas: HTMLCanvasElement, x: number, y: number): () => void {
  let g: CanvasRenderingContext2D | null = null
  try {
    g = canvas.getContext('2d')
  } catch {
    return () => {}
  }
  if (!g) return () => {}
  const W = canvas.width
  const H = canvas.height
  const chips: Chip[] = []
  for (let i = 0; i < 28; i++) {
    const a = -Math.PI / 2 + (Math.random() - 0.5) * 1.8
    const sp = 4 + Math.random() * 7.5
    chips.push({
      x,
      y,
      vx: Math.cos(a) * sp + (Math.random() - 0.5) * 2,
      vy: Math.sin(a) * sp - 2.5,
      r: 7 + Math.random() * 6,
      rot: Math.random() * 6.28,
      vr: (Math.random() - 0.5) * 0.5,
      c: CHIP_COLORS[i % CHIP_COLORS.length],
    })
  }
  let raf = 0
  let t0 = 0
  const step = (ts: number) => {
    if (!t0) t0 = ts
    const e = (ts - t0) / 1000
    g.clearRect(0, 0, W, H)
    let alive = false
    for (const c of chips) {
      c.vy += 0.34
      c.x += c.vx
      c.y += c.vy
      c.vx *= 0.99
      c.rot += c.vr
      const alpha = Math.max(0, 1 - e / 1.5)
      if (c.y < H + 50 && alpha > 0) {
        alive = true
        g.globalAlpha = alpha
        drawChip(g, c.x, c.y, c.r, c.rot, c.c)
      }
    }
    g.globalAlpha = 1
    if (alive && e < 1.7) raf = requestAnimationFrame(step)
    else g.clearRect(0, 0, W, H)
  }
  raf = requestAnimationFrame(step)
  return () => {
    cancelAnimationFrame(raf)
    g.clearRect(0, 0, W, H)
  }
}
