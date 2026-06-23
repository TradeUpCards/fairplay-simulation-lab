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
      <p
        className="mt-4 flex items-center gap-2 rounded-[10px] border border-line bg-surface-2 px-4 py-[0.85rem] text-[0.76rem] text-faint"
        data-testid="floor-controls"
      >
        <span className="h-2 w-2 flex-none rounded-full bg-[#4a5466]" aria-hidden="true" />
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
    <div
      className="mt-4 rounded-[10px] border border-line bg-surface-2 px-4 py-[0.85rem] text-[0.82rem]"
      data-testid="floor-controls"
    >
      <div className="mb-[0.7rem] flex items-center gap-[0.45rem] text-muted">
        <span
          className="h-2 w-2 flex-none animate-live-pulse rounded-full bg-felt shadow-[0_0_0_3px_rgba(47,143,91,0.2)]"
          aria-hidden="true"
        />
        Live floor — move a player, watch <strong>{table.table_id}</strong> recompute
      </div>

      {table.seated_player_ids.length > 0 && (
        <ul className="m-0 mb-[0.7rem] flex list-none flex-wrap gap-[0.4rem] p-0" aria-label="seated players">
          {table.seated_player_ids.map((pid) => (
            <li
              key={pid}
              className="inline-flex items-center gap-[0.35rem] rounded-full border border-line py-[0.2rem] pl-[0.55rem] pr-[0.2rem]"
            >
              <span className="font-mono text-[0.74rem] text-text">{pid}</span>
              <button type="button" className={FLOOR_BTN} disabled={busy} onClick={() => void run(() => liveRoom.stand(pid))}>
                Stand up
              </button>
            </li>
          ))}
        </ul>
      )}

      <form className="flex gap-[0.4rem]" onSubmit={onSeat}>
        <input
          className="min-w-0 flex-1 rounded-lg border border-line bg-ink px-[0.6rem] py-[0.32rem] font-mono text-[0.74rem] text-text"
          aria-label="player to seat"
          placeholder="player id (e.g. P-176)"
          value={playerId}
          onChange={(e) => setPlayerId(e.target.value)}
        />
        <button
          type="submit"
          className={`${FLOOR_BTN} whitespace-nowrap`}
          disabled={busy || !playerId.trim() || table.open_seats <= 0}
        >
          Seat at {table.table_id}
        </button>
      </form>

      {table.open_seats <= 0 && (
        <p className="mt-2 text-[0.72rem] text-faint">Table full — stand someone up first.</p>
      )}
      {error && (
        <p className="mt-2 text-[0.74rem] text-[#ff7b7b]" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}

// brass pill buttons used for stand/sit — quiet until hovered
const FLOOR_BTN =
  'cursor-pointer rounded-full border border-brass-soft bg-transparent px-[0.7rem] py-[0.28rem] text-[0.72rem] text-brass enabled:hover:bg-[rgba(199,154,75,0.12)] disabled:cursor-not-allowed disabled:opacity-40'
