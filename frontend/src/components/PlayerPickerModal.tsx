import { useEffect, useMemo, useState } from 'react'
import type { PlayerOption } from '../data/types'
import { ARCHETYPE_LABEL } from '../lib/table'

/**
 * Centered, searchable modal for the lobby impersonator's "Viewing as" control —
 * the player-facing twin of the pit boss `PlayerSelectModal`. Lists the player
 * universe with each player's archetype and how many tables they're seated at,
 * searchable by id / name / type. This is the one place archetype (operator
 * language) appears in the player view — it's a presenter/impersonator control,
 * not a real player-facing card. Esc / backdrop / ✕ dismiss; current is marked.
 */
export function PlayerPickerModal({
  open,
  current,
  players,
  onSelect,
  onClose,
}: {
  open: boolean
  current: string
  players: PlayerOption[]
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
  }, [open])

  const matches = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return players
      .filter((p) => {
        if (!needle) return true
        const arch = p.archetype ? ARCHETYPE_LABEL[p.archetype].toLowerCase() : ''
        return (
          p.player_id.toLowerCase().includes(needle) ||
          p.display_name.toLowerCase().includes(needle) ||
          arch.includes(needle)
        )
      })
      .sort((a, b) => a.player_id.localeCompare(b.player_id, undefined, { numeric: true }))
  }, [players, q])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-70 flex items-center justify-center bg-black/60 p-6"
      role="dialog"
      aria-modal="true"
      aria-label="View the lobby as another player"
      onClick={onClose}
    >
      <div
        className="flex max-h-[80vh] w-full max-w-[420px] flex-col rounded-xl border border-line bg-ink shadow-[0_24px_60px_rgba(0,0,0,0.6)]"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-line px-4 py-3">
          <h3 className="m-0 text-[0.95rem] font-semibold">
            View as <span className="font-mono text-brass">{current}</span>
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
            placeholder="Search by player id, name, or type…"
            aria-label="search players"
            className="w-full rounded-lg border border-line bg-surface-2 px-3 py-2 text-[0.82rem] text-text placeholder:text-faint"
          />
        </div>

        <ul className="m-0 flex-1 list-none overflow-y-auto p-3">
          {matches.length === 0 ? (
            <li className="px-1 py-2 text-[0.82rem] text-muted">No matching players.</li>
          ) : (
            matches.map((p) => {
              const active = p.player_id === current
              const seats = p.seated_count ?? 0
              return (
                <li key={p.player_id}>
                  <button
                    type="button"
                    onClick={() => onSelect(p.player_id)}
                    aria-current={active ? 'true' : undefined}
                    className={`flex w-full items-center gap-2 rounded-lg border px-2 py-[0.4rem] text-left ${
                      active
                        ? 'border-brass/60 bg-surface'
                        : 'border-transparent bg-transparent hover:border-line hover:bg-surface'
                    }`}
                  >
                    <span className="font-mono text-[0.82rem] text-text">{p.player_id}</span>
                    {p.archetype && (
                      <span className="rounded-full border border-line px-[0.45rem] py-[0.05rem] text-[0.66rem] text-muted">
                        {ARCHETYPE_LABEL[p.archetype]}
                      </span>
                    )}
                    <span className="ml-auto whitespace-nowrap text-[0.7rem] text-faint">
                      {active && <span className="mr-2 text-brass">current</span>}
                      {seats === 0 ? 'not seated' : seats === 1 ? '1 table' : `${seats} tables`}
                    </span>
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
