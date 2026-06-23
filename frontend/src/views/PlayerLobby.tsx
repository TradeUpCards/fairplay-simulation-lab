import { type ReactNode, useEffect, useMemo, useState } from 'react'
import type { LobbyTable, PlayerFloorData, PlayerOption, RouterLobbyFile } from '../data/types'
import { loadRouterLobby } from '../data/shim'
import { useResource } from '../state/useResource'
import { useLiveRoom, playerApi, liveRoom } from '../state/liveRoom'
import { ResourceBoundary } from '../components/ResourceBoundary'
import { TableTile } from '../components/TableTile'
import { PlayerPickerModal } from '../components/PlayerPickerModal'

const DEFAULT_PLAYER = 'P-104'

/** Badge → colour trio. Keyed by the three player-safe badges (never hidden_gated). */
const BADGE_TONE: Record<LobbyTable['badge'], string> = {
  recommended: 'border-[#2f7d4a] bg-[#16341f] text-[#8be3a7]',
  good_fit: 'border-[#2f6a8a] bg-[#1a2c3a] text-[#8fd0ef]',
  available: 'border-[#3a4757] bg-[#21242c] text-[#b8c0cf]',
}

/** "My Tables" cards wear a neutral green "Seated" badge instead of a fit chip. */
const SEATED_BADGE = { toneClass: 'border-[#2f7d4a] bg-[#16341f] text-[#8be3a7]', label: 'Seated' }

const FLOOR_GRID =
  'mt-7 grid grid-cols-3 gap-x-6 gap-y-11 max-[880px]:grid-cols-2 max-[560px]:grid-cols-1'
const SELECT_CLS = 'rounded-md border border-[#3a3024] bg-[rgba(0,0,0,0.3)] px-[0.4rem] py-1 text-[#f3ece0]'

/**
 * Player lobby — the load-bearing player/operator wall (CLAUDE.md hard rule #3).
 * Bound ONLY to player-safe shapes (neutral badges + table facts; never a score,
 * archetype, risk, or integrity term). When the live API is up it becomes an
 * impersonator: pick ANY player and toggle between their **Lobby** (routed
 * recommendations) and **My Tables** (where they're currently seated), both
 * served by `/api/lobby/{id}`. Offline it falls back to the frozen P-104 lobby.
 */
export function PlayerLobby() {
  const live = useLiveRoom()
  const staticLobby = useResource(loadRouterLobby, (d) => d.routed.length === 0)

  if (live.connected) return <LivePlayerFloor lastUpdatedAt={live.lastUpdated?.at ?? 0} />

  return (
    <ResourceBoundary state={staticLobby} label="lobby">
      {(data) => <PlayerLobbyView data={data} />}
    </ResourceBoundary>
  )
}

/** Live impersonator: any player's lobby + tables, re-fetched as seating changes. */
function LivePlayerFloor({ lastUpdatedAt }: { lastUpdatedAt: number }) {
  const [playerId, setPlayerId] = useState(DEFAULT_PLAYER)
  const [tab, setTab] = useState<'lobby' | 'tables'>('lobby')
  const [players, setPlayers] = useState<PlayerOption[]>([])
  const [floor, setFloor] = useState<PlayerFloorData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pickerOpen, setPickerOpen] = useState(false)
  // Tables with a seat change in flight — disables their Join/Leave control until
  // the resulting score_update re-fetches the floor and the table moves lists.
  const [busy, setBusy] = useState<Set<string>>(() => new Set())

  // Re-fetch on each live seat change too, so the picker's per-player seat counts
  // stay current as tables fill and empty.
  useEffect(() => {
    let alive = true
    playerApi.players().then((ps) => alive && setPlayers(ps)).catch(() => {})
    return () => {
      alive = false
    }
  }, [lastUpdatedAt])

  // Re-fetch on player change AND on any live seat change, so "My Tables" tracks
  // what the operator does on the floor in real time.
  useEffect(() => {
    let alive = true
    setError(null)
    playerApi
      .lobby(playerId)
      .then((f) => alive && setFloor(f))
      .catch((e) => alive && setError(e instanceof Error ? e.message : String(e)))
    return () => {
      alive = false
    }
  }, [playerId, lastUpdatedAt])

  // Join (sit) / Leave (stand) go through the live API; the resulting SSE
  // score_update bumps `lastUpdatedAt`, which re-runs the fetch above so the
  // table hops from Lobby → My Tables (or back). Locked decision: seating is
  // live-only, so these controls render only here, never in the static fallback.
  const seatMove = (tableId: string, fn: () => Promise<void>) => {
    setBusy((b) => new Set(b).add(tableId))
    setError(null)
    fn()
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() =>
        setBusy((b) => {
          const next = new Set(b)
          next.delete(tableId)
          return next
        }),
      )
  }
  const join = (tableId: string) => seatMove(tableId, () => liveRoom.sit(playerId, tableId))
  const leave = (tableId: string) => seatMove(tableId, () => liveRoom.stand(playerId, tableId))

  const options = players.length ? players : [{ player_id: playerId, display_name: playerId }]
  const lobby = floor?.player_lobby ?? []
  const tables = floor?.tables ?? []

  return (
    <section aria-label="player view">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div
          className="inline-flex gap-0.5 rounded-full border border-line bg-surface-2 p-0.5"
          role="tablist"
          aria-label="lobby or my tables"
        >
          <FloorTab active={tab === 'lobby'} onClick={() => setTab('lobby')}>
            Lobby
          </FloorTab>
          <FloorTab active={tab === 'tables'} onClick={() => setTab('tables')}>
            My Tables{tables.length ? ` (${tables.length})` : ''}
          </FloorTab>
        </div>

        <button
          type="button"
          onClick={() => setPickerOpen(true)}
          aria-haspopup="dialog"
          aria-label="select player"
          className={`${SELECT_CLS} inline-flex items-center gap-1.5 text-[0.85rem] hover:border-brass`}
        >
          <span className="text-[#b8ab95]">Viewing as</span>
          <span className="font-mono font-semibold text-[#f3ece0]">{playerId}</span>
          <span className="text-[0.7rem] text-[#b8ab95]">▾</span>
        </button>
      </div>

      {tab === 'lobby' ? (
        lobby.length === 0 ? (
          <p className="mt-7 text-[#b8ab95]">No tables available for {playerId} right now.</p>
        ) : (
          <ul className={FLOOR_GRID} aria-label="lobby">
            {lobby.map((t, i) => (
              <TableTile
                key={t.table_id}
                table={t}
                featured={i === 0}
                badge={{ toneClass: BADGE_TONE[t.badge], label: t.badge_label }}
                action={{ kind: 'join', onClick: () => join(t.table_id), busy: busy.has(t.table_id) }}
              />
            ))}
          </ul>
        )
      ) : tables.length === 0 ? (
        <p className="mt-7 text-[#b8ab95]">
          {playerId} isn’t seated at any table yet — seat them from the Pit Boss console.
        </p>
      ) : (
        <ul className={FLOOR_GRID} aria-label="my tables">
          {tables.map((t) => (
            <TableTile
              key={t.table_id}
              table={t}
              variant="seated"
              badge={SEATED_BADGE}
              testId="my-table-card"
              action={{ kind: 'leave', onClick: () => leave(t.table_id), busy: busy.has(t.table_id) }}
            />
          ))}
        </ul>
      )}

      {error && (
        <p className="mt-4 text-[0.78rem] text-[#ff7b7b]" role="alert">
          {error}
        </p>
      )}

      <PlayerPickerModal
        open={pickerOpen}
        current={playerId}
        players={options}
        onSelect={(id) => {
          setPlayerId(id)
          setPickerOpen(false)
        }}
        onClose={() => setPickerOpen(false)}
      />
    </section>
  )
}

function FloorTab({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`rounded-full border-none px-[0.95rem] py-[0.32rem] text-[0.74rem] tracking-wider ${
        active ? 'bg-brass font-semibold text-[#1a1407]' : 'bg-transparent text-muted hover:text-text'
      }`}
    >
      {children}
    </button>
  )
}

/**
 * Static fallback render from an already-loaded router file (the frozen P-104
 * lobby) — used when the live API is offline, and driven directly by the unit
 * tests. Pure: no API, no live state.
 *
 * Typed to `LobbyTable` on purpose — passing an operator row here fails to
 * compile (the OperatorOnly brand + missing neutral fields).
 */
export function PlayerLobbyView({
  data,
  initialPlayerId = DEFAULT_PLAYER,
}: {
  data: RouterLobbyFile
  initialPlayerId?: string
}) {
  const playerIds = useMemo(() => data.routed.map((r) => r.player_id), [data])
  const [playerId, setPlayerId] = useState(() =>
    playerIds.includes(initialPlayerId) ? initialPlayerId : (playerIds[0] ?? ''),
  )

  const routed = data.routed.find((r) => r.player_id === playerId)
  const tables: LobbyTable[] = routed?.player_lobby ?? []

  return (
    <section aria-label="player lobby">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="m-0 text-[1.15rem] text-[#f3ece0]">Find a table</h2>
        <label className="text-[0.85rem] text-[#b8ab95]">
          Showing tables for{' '}
          <select
            className={SELECT_CLS}
            aria-label="select player"
            value={playerId}
            onChange={(e) => setPlayerId(e.target.value)}
          >
            {playerIds.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
        </label>
      </header>

      {tables.length === 0 ? (
        <p className="text-[#b8ab95]">No tables available right now.</p>
      ) : (
        <ul className={FLOOR_GRID} aria-label="lobby">
          {tables.map((t, i) => (
            <TableTile
              key={t.table_id}
              table={t}
              featured={i === 0}
              badge={{ toneClass: BADGE_TONE[t.badge], label: t.badge_label }}
            />
          ))}
        </ul>
      )}
    </section>
  )
}
