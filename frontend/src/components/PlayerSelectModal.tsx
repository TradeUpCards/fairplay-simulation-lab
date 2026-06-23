import { useEffect, useMemo, useState } from 'react'
import type { Classification, TableRosterEntry } from '../data/types'
import { ARCHETYPE_LABEL } from '../lib/table'

/**
 * Centered modal for seating a player at a table. Lists the player universe
 * (from classifications — id + archetype), filtered by a search box and with
 * anyone already at THIS table removed (can't double-seat one table). Since a
 * player may sit at several tables, those seated elsewhere stay selectable and
 * are tagged with where they currently sit. Esc / backdrop / ✕ dismiss.
 */
export function PlayerSelectModal({
  open,
  tableId,
  tables,
  classifications,
  onSelect,
  onClose,
}: {
  open: boolean
  tableId: string
  tables: TableRosterEntry[]
  classifications: Classification[]
  onSelect: (playerId: string) => void
  onClose: () => void
}) {
  const [q, setQ] = useState('')

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  useEffect(() => {
    if (open) setQ('')
  }, [open, tableId])

  const seatedHere = useMemo(
    () => new Set(tables.find((t) => t.table_id === tableId)?.seated_player_ids ?? []),
    [tables, tableId],
  )
  const whereSeated = useMemo(() => {
    const m = new Map<string, string[]>()
    for (const t of tables) for (const pid of t.seated_player_ids) m.set(pid, [...(m.get(pid) ?? []), t.table_id])
    return m
  }, [tables])

  const available = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return classifications
      .filter((c) => !seatedHere.has(c.player_id))
      .filter((c) => {
        if (!needle) return true
        const arch = ARCHETYPE_LABEL[c.archetype]?.toLowerCase() ?? ''
        return c.player_id.toLowerCase().includes(needle) || arch.includes(needle)
      })
      .sort((a, b) => a.player_id.localeCompare(b.player_id, undefined, { numeric: true }))
  }, [classifications, seatedHere, q])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-70 flex items-center justify-center bg-black/60 p-6"
      role="dialog"
      aria-modal="true"
      aria-label={`Seat a player at ${tableId}`}
      onClick={onClose}
    >
      <div
        className="flex max-h-[80vh] w-full max-w-[420px] flex-col rounded-xl border border-line bg-ink shadow-[0_24px_60px_rgba(0,0,0,0.6)]"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-line px-4 py-3">
          <h3 className="m-0 text-[0.95rem] font-semibold">
            Seat a player at <span className="font-mono text-brass">{tableId}</span>
          </h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="close"
            className="flex h-7 w-7 items-center justify-center rounded-full border border-line bg-transparent p-0 text-muted hover:border-brass hover:text-brass"
          >
            ✕
          </button>
        </header>

        <div className="px-4 pt-3">
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search by player id or type…"
            aria-label="search players"
            className="w-full rounded-lg border border-line bg-surface-2 px-3 py-2 text-[0.82rem] text-text placeholder:text-faint"
          />
        </div>

        <ul className="m-0 flex-1 list-none overflow-y-auto p-3">
          {available.length === 0 ? (
            <li className="px-1 py-2 text-[0.82rem] text-muted">No matching players.</li>
          ) : (
            available.map((c) => {
              const elsewhere = whereSeated.get(c.player_id) ?? []
              return (
                <li key={c.player_id}>
                  <button
                    type="button"
                    onClick={() => onSelect(c.player_id)}
                    className="flex w-full items-center gap-2 rounded-lg border border-transparent bg-transparent px-2 py-[0.4rem] text-left hover:border-line hover:bg-surface"
                  >
                    <span className="font-mono text-[0.82rem] text-text">{c.player_id}</span>
                    <span className="text-[0.72rem] text-muted">{ARCHETYPE_LABEL[c.archetype]}</span>
                    {elsewhere.length > 0 && (
                      <span className="ml-auto text-[0.66rem] text-faint">seated at {elsewhere.join(', ')}</span>
                    )}
                  </button>
                </li>
              )
            })
          )}
        </ul>
      </div>
    </div>
  )
}
