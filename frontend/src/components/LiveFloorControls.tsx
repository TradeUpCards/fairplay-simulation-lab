import { useState } from 'react'
import type { TableRosterEntry } from '../data/types'
import { liveRoom, useLiveRoom } from '../state/liveRoom'

/**
 * Operator floor controls (live only). Stand a seated player up, or seat one
 * here — each POSTs to the scoring API, which recomputes the affected table and
 * streams the new score back, so the health number above animates to its new
 * value. When the API is offline the whole app still works from the frozen
 * snapshot; this just shows a quiet "offline" note instead of the buttons.
 */
export function LiveFloorControls({ table }: { table: TableRosterEntry }) {
  const live = useLiveRoom()
  const [playerId, setPlayerId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (!live.connected) {
    return (
      <p className="floor-controls is-offline" data-testid="floor-controls">
        <span className="live-dot is-offline" aria-hidden="true" />
        Live scoring offline — showing the frozen snapshot. Start the API to move players.
      </p>
    )
  }

  const run = async (fn: () => Promise<void>) => {
    setError(null)
    setBusy(true)
    try {
      await fn()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const onSeat = (e: React.FormEvent) => {
    e.preventDefault()
    const id = playerId.trim()
    if (!id) return
    void run(() => liveRoom.sit(id, table.table_id)).then(() => setPlayerId(''))
  }

  return (
    <div className="floor-controls" data-testid="floor-controls">
      <div className="floor-controls-head">
        <span className="live-dot is-online" aria-hidden="true" />
        Live floor — move a player, watch <strong>{table.table_id}</strong> recompute
      </div>

      {table.seated_player_ids.length > 0 && (
        <ul className="seat-actions" aria-label="seated players">
          {table.seated_player_ids.map((pid) => (
            <li key={pid}>
              <span className="seat-action-id">{pid}</span>
              <button type="button" disabled={busy} onClick={() => void run(() => liveRoom.stand(pid))}>
                Stand up
              </button>
            </li>
          ))}
        </ul>
      )}

      <form className="sit-form" onSubmit={onSeat}>
        <input
          aria-label="player to seat"
          placeholder="player id (e.g. P-176)"
          value={playerId}
          onChange={(e) => setPlayerId(e.target.value)}
        />
        <button type="submit" disabled={busy || !playerId.trim() || table.open_seats <= 0}>
          Seat at {table.table_id}
        </button>
      </form>

      {table.open_seats <= 0 && <p className="floor-note">Table full — stand someone up first.</p>}
      {error && (
        <p className="floor-error" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
