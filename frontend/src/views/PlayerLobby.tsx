import { useMemo, useState } from 'react'
import pokerTable from '../assets/poker-table.png'
import type { LobbyTable, RouterLobbyFile } from '../data/types'
import { loadRouterLobby } from '../data/shim'
import { useResource } from '../state/useResource'
import { ResourceBoundary } from '../components/ResourceBoundary'

const DEFAULT_PLAYER = 'P-104'

/** Badge → CSS modifier. Keyed by the three player-safe badges (never hidden_gated). */
const BADGE_TONE: Record<LobbyTable['badge'], string> = {
  recommended: 'is-recommended',
  good_fit: 'is-good-fit',
  available: 'is-available',
}

/**
 * Player lobby — the load-bearing player/operator wall (CLAUDE.md hard rule #3,
 * guide §0/§3a). Binds ONLY to `router_lobby.json → routed[i].player_lobby`,
 * which P3 has pre-filtered and gated: gated tables (e.g. T-11 under review) are
 * already absent. Shows neutral badges + table facts — never a score, archetype,
 * risk, or integrity term. The `LobbyTable` typing is the primary guardrail:
 * passing operator data into `LobbyCard` is a compile error (OperatorOnly brand).
 */
export function PlayerLobby() {
  const lobby = useResource(loadRouterLobby, (d) => d.routed.length === 0)
  return (
    <ResourceBoundary state={lobby} label="lobby">
      {(data) => <PlayerLobbyView data={data} />}
    </ResourceBoundary>
  )
}

/** Pure render from an already-loaded file — the unit tests drive this directly. */
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
    <section className="player-lobby" aria-label="player lobby">
      <header className="lobby-header">
        <h2>Find a table</h2>
        <label className="player-select">
          Showing tables for{' '}
          <select
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
        <p className="rb-empty">No tables available right now.</p>
      ) : (
        <ul className="lobby-list">
          {tables.map((table) => (
            <LobbyCard key={table.table_id} table={table} />
          ))}
        </ul>
      )}
    </section>
  )
}

/**
 * Typed to `LobbyTable` on purpose — DO NOT widen this prop. Passing an operator
 * row here fails to compile (the OperatorOnly brand + missing neutral fields).
 */
function LobbyCard({ table }: { table: LobbyTable }) {
  return (
    <li className="lobby-card">
      <div className="table-stage">
        <img className="table-art" src={pokerTable} alt="" aria-hidden="true" />
        <span className={`lobby-badge ${BADGE_TONE[table.badge]}`}>{table.badge_label}</span>
        <span className="table-stage-id">{table.table_id}</span>
      </div>
      <div className="lobby-card-body">
        <dl className="lobby-facts">
          <div>
            <dt>Stakes</dt>
            <dd>{table.stakes}</dd>
          </div>
          <div>
            <dt>Game</dt>
            <dd>{table.game_type}</dd>
          </div>
          <div>
            <dt>Seats</dt>
            <dd>
              {table.seated_count}/{table.max_seats} · {table.open_seats} open
            </dd>
          </div>
          <div>
            <dt>Pace</dt>
            <dd>{table.pace_label}</dd>
          </div>
        </dl>
      </div>
    </li>
  )
}
