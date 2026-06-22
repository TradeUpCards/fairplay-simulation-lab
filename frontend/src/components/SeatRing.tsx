import pokerTable from '../assets/poker-table.png'
import logoWatermark from '../assets/fairplay-iq-logo-black.svg'
import type { TableRosterEntry } from '../data/types'
import { ARCHETYPE_LABEL, ptlTone, type SeatInfo } from '../lib/table'

/**
 * The signature pit-boss element: a round seat-ring over the poker-table felt.
 * Seats are positioned around the ring from the roster; each shows the player,
 * archetype, an integrity flag if their group is under review, and a PTL heat
 * dot. PTL is stubbed neutral (`pending`) until U2 ships per-seat scores — when
 * it lands, `seat.ptl` flows straight into `ptlTone` and the dots colour in.
 */
export function SeatRing({ table, seats }: { table: TableRosterEntry; seats: SeatInfo[] }) {
  return (
    <div className="seat-ring" aria-label={`seat ring for ${table.table_id}`}>
      <img className="seat-ring-felt" src={pokerTable} alt="" aria-hidden="true" />
      <img
        className="seat-ring-watermark"
        src={logoWatermark}
        alt=""
        aria-hidden="true"
        data-testid="table-watermark"
      />
      <div className="seat-ring-center">
        <span className="ring-table-id">{table.table_id}</span>
        <span className="ring-occupancy">
          {table.seated_count}/{table.max_seats} seated
        </span>
      </div>
      {seats.map((seat) => (
        <Seat key={seat.index} seat={seat} />
      ))}
    </div>
  )
}

function Seat({ seat }: { seat: SeatInfo }) {
  const style = { left: `${seat.leftPct}%`, top: `${seat.topPct}%` }

  if (!seat.playerId) {
    return (
      <div className="seat seat-open" style={style} data-testid="seat" data-open="true">
        <span className="seat-empty">Open</span>
      </div>
    )
  }

  const tone = ptlTone(seat.ptl)
  const flagged = Boolean(seat.flaggedGroupId)
  return (
    <div
      className={`seat seat-occupied ptl-${tone}${flagged ? ' seat-flagged' : ''}`}
      style={style}
      data-testid="seat"
      data-flagged={flagged ? 'true' : 'false'}
      data-ptl-tone={tone}
      title={seat.archetypeWhy}
    >
      <span className="seat-ptl-dot" aria-hidden="true" />
      <span className="seat-player">{seat.playerId}</span>
      {seat.archetype && <span className="seat-archetype">{ARCHETYPE_LABEL[seat.archetype]}</span>}
      {flagged && (
        <span className="seat-flag" aria-label="under integrity review">
          ⚑
        </span>
      )}
    </div>
  )
}
