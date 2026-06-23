import type { TableRosterEntry } from '../data/types'
import { useLiveRoom } from '../state/liveRoom'

/**
 * Live-floor status line. The seating controls themselves now live on the
 * seat-ring (the ⏏ on each player, and clickable open seats); this just reports
 * whether the scoring API is connected — so the operator knows the ring is live
 * and editable, or read-only with only the frozen snapshot showing.
 */
export function LiveFloorControls({ table }: { table: TableRosterEntry }) {
  const live = useLiveRoom()

  if (!live.connected) {
    return (
      <p
        className="mt-4 flex items-center gap-2 rounded-[10px] border border-line bg-surface-2 px-4 py-[0.85rem] text-[0.76rem] text-faint"
        data-testid="floor-controls"
      >
        <span className="h-2 w-2 flex-none rounded-full bg-[#4a5466]" aria-hidden="true" />
        Live scoring offline — the seat-ring is read-only. Start the API to move players and watch
        scores recompute.
      </p>
    )
  }

  return (
    <p
      className="mt-4 flex items-center gap-2 rounded-[10px] border border-line bg-surface-2 px-4 py-[0.85rem] text-[0.82rem] text-muted"
      data-testid="floor-controls"
    >
      <span
        className="h-2 w-2 flex-none animate-live-pulse rounded-full bg-felt shadow-[0_0_0_3px_rgba(47,143,91,0.2)]"
        aria-hidden="true"
      />
      Live floor — use the ⏏ on a player to stand them up, or click an open seat to seat one. Watch{' '}
      <strong className="text-text">{table.table_id}</strong> recompute.
    </p>
  )
}
