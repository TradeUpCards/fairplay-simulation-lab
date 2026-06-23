import type { ReactNode } from 'react'
import pokerTable from '../assets/poker-table.png'
import type { TableRosterEntry } from '../data/types'
import { ARCHETYPE_LABEL, ptlTone, type SeatInfo } from '../lib/table'

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
 */
export function SeatRing({
  table,
  seats,
  compact = false,
  centerContent,
}: {
  table: TableRosterEntry
  seats: SeatInfo[]
  compact?: boolean
  centerContent?: ReactNode
}) {
  return (
    <div className={`seat-ring${compact ? ' is-compact' : ''}`} aria-label={`seat ring for ${table.table_id}`}>
      <img className="seat-ring-felt" src={pokerTable} alt="" aria-hidden="true" />
      {centerContent ? (
        <div className="seat-ring-center">{centerContent}</div>
      ) : (
        !compact && (
          <div className="seat-ring-center">
            <span className="ring-table-id">{table.table_id}</span>
            <span className="ring-occupancy">
              {table.seated_count}/{table.max_seats} seated
            </span>
          </div>
        )
      )}
      {seats.map((seat) => (
        <Seat key={seat.index} seat={seat} compact={compact} />
      ))}
    </div>
  )
}

function Seat({ seat, compact }: { seat: SeatInfo; compact: boolean }) {
  // In compact mode re-seat the players onto the card mini-table's brass rim — a
  // tighter ellipse whose extremes land on the measured rim positions: left
  // 10.6269% / 89.3731% (±39.3731), top 17.8% / 82.2% (±32.2). Base radii in
  // seatPositions() are 42% (x) and 40% (y), so scale the deviation from centre.
  const left = compact ? 50 + (seat.leftPct - 50) * (39.3731 / 42) : seat.leftPct
  const top = compact ? 50 + (seat.topPct - 50) * (32.2 / 40) : seat.topPct
  const style = { left: `${left}%`, top: `${top}%` }

  if (!seat.playerId) {
    return (
      <div className="seat seat-open" style={style} data-testid="seat" data-open="true">
        {!compact && <span className="seat-empty">Open</span>}
      </div>
    )
  }

  const tone = ptlTone(seat.ptl)
  const flagged = Boolean(seat.flaggedGroupId)
  const title = [seat.archetypeWhy, seat.ptlWhy].filter(Boolean).join(' — ')
  return (
    <div
      className={`seat seat-occupied ptl-${tone}${flagged ? ' seat-flagged' : ''}`}
      style={style}
      data-testid="seat"
      data-flagged={flagged ? 'true' : 'false'}
      data-ptl-tone={tone}
      title={title || undefined}
    >
      <span className="seat-ptl-dot" aria-hidden="true" />
      <span className="seat-player">{seat.playerId}</span>
      {!compact && seat.archetype && (
        <span className="seat-archetype">{ARCHETYPE_LABEL[seat.archetype]}</span>
      )}
      {flagged && (
        <span className="seat-flag" aria-label="under integrity review">
          ⚑
        </span>
      )}
    </div>
  )
}
