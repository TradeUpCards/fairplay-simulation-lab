/**
 * Shared table art — the same avatar/seat-ring design the training table uses, so
 * the lobby's table preview matches the rest of the product instead of a one-off.
 * (Avatars, hue hashing, and ellipse seat layout originate in TrainingTable.)
 */

/** Deterministic per-archetype glyph (matches the training table). */
export const ARCH_AVATAR: Record<string, string> = {
  recreational: '🐟',
  aggressive_predatory: '🔥',
  promo_hunter: '🪨',
  grinder: '⚙️',
  regular: '🎯',
  solver_like: '🤖',
  new: '🌱',
}

/** Stable hue from a label, so a given seat/table looks the same across renders. */
export function hashHue(s: string): number {
  let h = 0
  for (const ch of s) h = (h * 31 + ch.charCodeAt(0)) % 360
  return h
}

/** Seats evenly around an ellipse, slot 0 at the bottom (matches the training table). */
export function seatPositions(n: number): { top: string; left: string }[] {
  return Array.from({ length: Math.max(n, 1) }, (_, i) => {
    const theta = Math.PI / 2 + (i / Math.max(n, 1)) * Math.PI * 2
    return { left: `${50 + 48 * Math.cos(theta)}%`, top: `${50 + 35 * Math.sin(theta)}%` }
  })
}

/** A round seat avatar — archetype glyph on a hue-derived felt, same as the table. */
export function SeatAvatar({
  archetype,
  label,
  isHero = false,
  size = 'md',
}: {
  archetype?: string | null
  label: string
  isHero?: boolean
  size?: 'sm' | 'md'
}) {
  const emoji = isHero ? '🧑' : (ARCH_AVATAR[archetype ?? ''] ?? '🎭')
  const hue = hashHue(label)
  const dim = size === 'sm' ? 'h-7 w-7 border text-[0.85rem]' : 'h-11 w-11 border-2 text-[1.35rem]'
  return (
    <div
      className={`grid ${dim} shrink-0 place-items-center rounded-full leading-none shadow-[0_1px_4px_rgba(0,0,0,0.45)]`}
      style={{
        borderColor: isHero ? 'var(--color-brass)' : '#3a4555',
        background: `radial-gradient(circle at 30% 25%, hsl(${hue} 42% 36%), hsl(${hue} 46% 15%))`,
      }}
      aria-hidden="true"
    >
      {emoji}
    </div>
  )
}
