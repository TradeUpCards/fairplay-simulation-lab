import type { ReactNode } from 'react'
import pokerTable from '../assets/poker-table.png'
import type { TableRosterEntry } from '../data/types'
import { ARCHETYPE_LABEL, ptlTone, type PtlTone, type SeatInfo } from '../lib/table'

// PTL heat → seat-dot colour. Pending stays neutral until scored.
const PTL_DOT: Record<PtlTone, string> = {
  pending: 'bg-[#4a5466]',
  cool: 'bg-[#5fcf8a]',
  warm: 'bg-[#e3b25f]',
  hot: 'bg-[#ff7b7b]',
}

/**
 * The signature pit-boss element: a round seat-ring over the poker-table felt.
 * Seats are positioned around the ring from the roster; each shows the player,
 * archetype, an integrity flag if their group is under review, and a PTL heat
 * dot. PTL (propensity to leave) flows from `lib/ptl` through `seat.ptl` into
 * `ptlTone` — vulnerable seats run hot at unhealthy tables, anchored ones cool.
 *
 * `compact` renders the same felt + positioned players shrunk to fit inside a
 * table card on the floor grid: no archetype, top/bottom seats pulled onto the
 * brass rim to save height. `centerContent` overrides the centre label (the card
 * puts the health score + seat count there).
 *
 * When `onStand` / `onSeatOpen` are supplied (the live detail panel), occupied
 * seats grow a stand-up control and open seats become clickable to seat a player.
 * Omit them (the floor cards, tests) and the ring is purely read-only.
 */
export function SeatRing({
  table,
  seats,
  compact = false,
  centerContent,
  onStand,
  onSeatOpen,
}: {
  table: TableRosterEntry
  seats: SeatInfo[]
  compact?: boolean
  centerContent?: ReactNode
  onStand?: (playerId: string) => void
  onSeatOpen?: (seatIndex: number) => void
}) {
  return (
    <div
      className={`relative mx-auto aspect-4/3 w-full ${compact ? 'max-w-full' : 'max-w-[680px]'}`}
      aria-label={`seat ring for ${table.table_id}`}
    >
      <img
        className="absolute inset-0 h-full w-full object-contain opacity-[0.92]"
        src={pokerTable}
        alt=""
        aria-hidden="true"
      />
      {centerContent ? (
        <div className={centerClass(compact)}>{centerContent}</div>
      ) : (
        !compact && (
          <div className={centerClass(compact)}>
            <span className="text-[1.1rem] font-bold">{table.table_id}</span>
            <span className="text-[0.72rem] text-[#c3c9d6]">
              {table.seated_count}/{table.max_seats} seated
            </span>
          </div>
        )
      )}
      {seats.map((seat) => (
        <Seat key={seat.index} seat={seat} compact={compact} onStand={onStand} onSeatOpen={onSeatOpen} />
      ))}
    </div>
  )
}

function centerClass(compact: boolean) {
  return `absolute left-1/2 top-1/2 grid -translate-x-1/2 -translate-y-1/2 justify-items-center gap-[0.15rem] ${
    compact ? 'pointer-events-auto z-5' : 'pointer-events-none'
  }`
}

function Seat({
  seat,
  compact,
  onStand,
  onSeatOpen,
}: {
  seat: SeatInfo
  compact: boolean
  onStand?: (playerId: string) => void
  onSeatOpen?: (seatIndex: number) => void
}) {
  // In compact mode re-seat the players onto the card mini-table's brass rim — a
  // tighter ellipse whose extremes land on the measured rim positions: left
  // 10.6269% / 89.3731% (±39.3731), top 17.8% / 82.2% (±32.2). Base radii in
  // seatPositions() are 42% (x) and 40% (y), so scale the deviation from centre.
  const left = compact ? 50 + (seat.leftPct - 50) * (39.3731 / 42) : seat.leftPct
  const top = compact ? 50 + (seat.topPct - 50) * (32.2 / 40) : seat.topPct
  const style = { left: `${left}%`, top: `${top}%` }

  // Common seat box: an absolutely-placed, centred grid that anchors the flag.
  const base = 'absolute grid -translate-x-1/2 -translate-y-1/2 justify-items-center text-center'

  if (!seat.playerId) {
    const openCls = compact
      ? 'h-[0.9rem] w-[0.9rem] gap-0 rounded-full p-0'
      : 'w-[4.6rem] gap-[0.1rem] rounded-[9px] px-[0.2rem] py-[0.3rem]'
    // Interactive open seat (live panel): click to seat a player.
    if (onSeatOpen) {
      return (
        <button
          type="button"
          className={`${base} ${openCls} cursor-pointer border border-dashed border-[#2c3543] bg-[rgba(14,17,22,0.86)] text-faint opacity-70 transition hover:border-brass hover:text-brass hover:opacity-100`}
          style={style}
          data-testid="seat"
          data-open="true"
          onClick={() => onSeatOpen(seat.index)}
          aria-label="Seat a player here"
        >
          {compact ? '+' : <span className="text-[0.72rem]">＋ Seat</span>}
        </button>
      )
    }
    return (
      <div
        className={`${base} ${openCls} border border-dashed border-[#2c3543] bg-[rgba(14,17,22,0.86)] opacity-[0.55]`}
        style={style}
        data-testid="seat"
        data-open="true"
      >
        {!compact && <span className="text-[0.72rem] text-[#6b7283]">Open</span>}
      </div>
    )
  }

  const tone = ptlTone(seat.ptl)
  const flagged = Boolean(seat.flaggedGroupId)
  const title = [seat.archetypeWhy, seat.ptlWhy].filter(Boolean).join(' — ')

  const sizeCls = compact
    ? 'w-[3.2rem] gap-0 rounded-md px-[0.08rem] py-[0.12rem]'
    : 'w-[4.6rem] gap-[0.1rem] rounded-[9px] px-[0.2rem] py-[0.3rem]'
  const borderCls = flagged
    ? 'border-[#b3455a] shadow-[0_0_0_1px_#b3455a]'
    : 'border-[#2c3543]'

  return (
    <div
      className={`${base} ${sizeCls} border bg-[rgba(14,17,22,0.86)] ${borderCls}`}
      style={style}
      data-testid="seat"
      data-flagged={flagged ? 'true' : 'false'}
      data-ptl-tone={tone}
      title={title || undefined}
    >
      {onStand && (
        <button
          type="button"
          className="absolute -left-[0.5rem] -top-[0.5rem] flex h-[1.15rem] w-[1.15rem] items-center justify-center rounded-full border border-line bg-[rgba(0,0,0,0.72)] p-0 text-[0.7rem] leading-none text-muted hover:border-brass hover:text-brass"
          onClick={() => onStand(seat.playerId!)}
          aria-label={`Stand ${seat.playerId} up`}
          title={`Stand ${seat.playerId} up`}
        >
          ⏏
        </button>
      )}
      <span
        className={`rounded-full ${compact ? 'h-[0.4rem] w-[0.4rem]' : 'h-[0.55rem] w-[0.55rem]'} ${PTL_DOT[tone]}`}
        aria-hidden="true"
      />
      <span className={`font-semibold tabular-nums ${compact ? 'text-[0.58rem]' : 'text-[0.74rem]'}`}>
        {seat.playerId}
      </span>
      {!compact && seat.archetype && (
        <span className="text-[0.64rem] text-[#9aa2b3]">{ARCHETYPE_LABEL[seat.archetype]}</span>
      )}
      {flagged && (
        <span
          className={`absolute -right-[0.5rem] text-[#ff9b9b] ${
            compact ? '-top-[0.35rem] text-[0.6rem]' : '-top-[0.5rem] text-[0.8rem]'
          }`}
          aria-label="under integrity review"
        >
          ⚑
        </span>
      )}
    </div>
  )
}
