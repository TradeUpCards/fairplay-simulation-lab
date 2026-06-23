import pokerTable from '../assets/poker-table.png'
import type { NeutralTable } from '../data/types'

/** A click affordance straddling a tile's bottom-right corner. */
export interface TileAction {
  kind: 'join' | 'leave'
  onClick: () => void
  busy?: boolean
}

/**
 * A lit table on the dark player floor — the shared card for both the lobby
 * (recommendations, badged by fit) and "My Tables" (current seats, badged
 * "Seated"). Shows only neutral facts (stakes / seats / pace): no scores,
 * archetypes, or risk language (the player/operator wall).
 *
 * Two visual modes:
 *  - `variant="lobby"` (default): the felt sits dimmed and brightens to a warm
 *    "light highlight" (glow + felt spotlight) on hover/focus — no scale, no
 *    lift. `featured` pins that lit state on at rest, so the top recommendation
 *    reads as highlighted by default. An optional Join control (dashed circle
 *    straddling the bottom-right) seats the viewer.
 *  - `variant="seated"` (My Tables): the felt is full-colour at rest with no
 *    hover glow or zoom; the only hover affordance is the Leave control, which
 *    lights up red.
 */
export function TableTile({
  table,
  badge,
  testId = 'lobby-card',
  variant = 'lobby',
  featured = false,
  action,
}: {
  table: NeutralTable
  badge?: { toneClass: string; label: string } | null
  testId?: string
  variant?: 'lobby' | 'seated'
  featured?: boolean
  action?: TileAction | null
}) {
  const seated = variant === 'seated'

  // Wrapper carpet-glow (the "light highlight"). Lobby tiles glow on hover/focus
  // and, when featured, at rest too. Seated tiles never glow.
  const wrapperCls = seated
    ? 'group relative rounded-[14px]'
    : `group relative rounded-[14px] before:pointer-events-none before:absolute before:left-1/2 before:top-1/2 before:z-0 before:h-[165%] before:w-[150%] before:-translate-x-1/2 before:-translate-y-1/2 before:bg-[radial-gradient(46%_44%_at_50%_50%,rgba(255,222,168,0.42),rgba(255,206,148,0.13)_52%,transparent_76%)] before:opacity-0 before:blur-[10px] before:transition-opacity before:duration-340 before:content-[''] hover:before:opacity-100 focus-within:before:opacity-100 ${
        featured ? 'before:opacity-100' : ''
      }`

  // Felt spotlight (lobby only; pinned when featured).
  const feltCls = seated
    ? 'relative z-1 aspect-3/2'
    : `relative z-1 aspect-3/2 after:pointer-events-none after:absolute after:inset-0 after:bg-[radial-gradient(52%_50%_at_50%_50%,rgba(255,240,212,0.5),rgba(255,230,190,0.12)_46%,transparent_72%)] after:opacity-0 after:mix-blend-screen after:transition-opacity after:duration-320 after:content-[''] group-hover:after:opacity-100 group-focus-within:after:opacity-100 ${
        featured ? 'after:opacity-100' : ''
      }`

  // The felt image. Seated → full colour at rest, no hover change. Lobby →
  // dimmed, brightening to the lit state on hover/focus (and at rest when
  // featured). No scale/zoom in either mode.
  const imgCls = seated
    ? 'block h-full w-full object-cover'
    : `block h-full w-full object-cover transition-[filter] duration-320 ${
        featured ? 'brightness-[1.06] saturate-[1.05]' : 'brightness-[0.6] saturate-[0.92]'
      } group-hover:brightness-[1.06] group-hover:saturate-[1.05] group-focus-within:brightness-[1.06] group-focus-within:saturate-[1.05] motion-reduce:transition-none`

  return (
    <li data-testid={testId} className={wrapperCls}>
      <div className={feltCls}>
        <img className={imgCls} src={pokerTable} alt="" aria-hidden="true" />
        <dl className="absolute left-1/2 top-1/2 z-2 m-0 flex w-[72%] -translate-x-1/2 -translate-y-1/2 flex-wrap justify-center gap-x-[1.7rem] gap-y-2 text-center">
          <div className="flex flex-col gap-[0.05rem]">
            <dt className="text-[0.6rem] uppercase tracking-[0.14em] text-[rgba(228,240,224,0.55)]">Stakes</dt>
            <dd className="m-0 text-[0.92rem] font-semibold text-[#f3efe4] [text-shadow:0_1px_4px_rgba(0,0,0,0.6)]">
              {table.stakes}
            </dd>
          </div>
          <div className="flex flex-col gap-[0.05rem]">
            <dt className="text-[0.6rem] uppercase tracking-[0.14em] text-[rgba(228,240,224,0.55)]">Seats</dt>
            <dd className="m-0 text-[0.92rem] font-semibold text-[#f3efe4] [text-shadow:0_1px_4px_rgba(0,0,0,0.6)]">
              {table.seated_count}/{table.max_seats} · {table.open_seats} open
            </dd>
          </div>
          <div className="flex flex-col gap-[0.05rem]">
            <dt className="text-[0.6rem] uppercase tracking-[0.14em] text-[rgba(228,240,224,0.55)]">Pace</dt>
            <dd className="m-0 text-[0.92rem] font-semibold text-[#f3efe4] [text-shadow:0_1px_4px_rgba(0,0,0,0.6)]">
              {table.pace_label}
            </dd>
          </div>
        </dl>
      </div>
      {badge && (
        <span
          className={`absolute left-1/2 top-[calc(19%-15px)] z-3 -translate-x-1/2 -translate-y-1/2 rounded-full border px-2 py-[0.15rem] text-[0.72rem] shadow-[0_2px_8px_rgba(0,0,0,0.55)] ${badge.toneClass}`}
        >
          {badge.label}
        </span>
      )}
      <span className="absolute left-1/2 top-[calc(82%+15px)] z-3 -translate-x-1/2 -translate-y-1/2 rounded-[5px] border border-[rgba(0,0,0,0.4)] bg-[linear-gradient(180deg,#e0bd76,#b78a3c)] px-[0.7rem] py-[0.18rem] text-[0.82rem] font-bold tracking-wider text-[#2c1f08] shadow-[0_2px_6px_rgba(0,0,0,0.5),inset_0_1px_0_rgba(255,255,255,0.35)]">
        {table.table_id}
      </span>
      {action?.kind === 'join' && (
        <button
          type="button"
          data-testid="join-table"
          disabled={action.busy}
          onClick={action.onClick}
          aria-label={`Join ${table.table_id}`}
          title={`Join ${table.table_id}`}
          className="absolute left-[83%] top-[79%] z-4 flex h-12 w-12 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-dashed border-[#5a6678] bg-[rgba(14,17,22,0.9)] text-[0.6rem] font-semibold uppercase tracking-wider text-faint shadow-[0_2px_8px_rgba(0,0,0,0.55)] transition hover:border-brass hover:bg-[rgba(34,28,12,0.92)] hover:text-brass disabled:cursor-wait disabled:opacity-50"
        >
          {action.busy ? '…' : 'Join'}
        </button>
      )}
      {action?.kind === 'leave' && (
        <button
          type="button"
          data-testid="leave-table"
          disabled={action.busy}
          onClick={action.onClick}
          aria-label={`Leave ${table.table_id}`}
          title={`Leave ${table.table_id}`}
          className="absolute left-[83%] top-[79%] z-4 flex h-12 w-12 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-[#7a3a44] bg-[rgba(14,17,22,0.9)] text-[0.58rem] font-semibold uppercase tracking-wider text-[#c98b93] shadow-[0_2px_8px_rgba(0,0,0,0.55)] transition group-hover:border-[#d0556a] group-hover:text-[#ff9ba6] hover:border-[#ff7b8b] hover:bg-[rgba(46,18,22,0.95)] hover:text-[#ffd0d6] disabled:cursor-wait disabled:opacity-50"
        >
          {action.busy ? '…' : 'Leave'}
        </button>
      )}
    </li>
  )
}
