import { useSyncExternalStore } from 'react'
import type { LobbySequence, SeatEvent } from '../data/types'
import { loadLobbySequence } from '../data/shim'
import { useResource } from '../state/useResource'
import { lobbyStore } from '../state/lobbyStore'
import { ResourceBoundary } from './ResourceBoundary'
import { LobbyDataTable } from './LobbyDataTable'
import { LobbySidecar } from './LobbySidecar'

/**
 * Demo Part 2 — the same arrivals seated by each policy, side by side: Standard
 * packs the fullest tables (concentration); FairPlay routes via the real router
 * (spread). "Simulate room activity" steps a seeded round of arrivals/departures
 * and the two rooms diverge. State lives in `lobbyStore` so it survives leaving
 * and re-entering the player page. Data is the player-safe `lobby_sequence.json`
 * (playsim → router pipeline); no scores shown in the lobby itself.
 */
export function LobbyBoard() {
  const seq = useResource(loadLobbySequence, (d) => d.steps.length === 0)
  return (
    <ResourceBoundary state={seq} label="lobby">
      {(data) => <LobbyBoardView seq={data} />}
    </ResourceBoundary>
  )
}

function LobbyBoardView({ seq }: { seq: LobbySequence }) {
  const ui = useSyncExternalStore(lobbyStore.subscribe, lobbyStore.getState)
  const step = Math.min(ui.step, seq.steps.length - 1)
  const cur = seq.steps[step]
  const prev = step > 0 ? seq.steps[step - 1] : undefined
  const atEnd = step >= seq.steps.length - 1
  const advance = () => lobbyStore.setStep(step >= seq.steps.length - 1 ? 0 : step + 1)

  const ev = cur.events?.standard ?? []
  const sits = ev.filter((e) => e.action === 'sit').length
  const stands = ev.filter((e) => e.action === 'stand').length

  return (
    <section aria-label="standard vs fairplay lobby">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <span className="text-[0.74rem] uppercase tracking-[0.14em] text-[#8b8276]">Room state</span>
          <span className="font-mono text-[0.9rem] font-semibold text-[#f3ece0]">{cur.label}</span>
          {sits + stands > 0 && (
            <span className="text-[0.74rem] text-[#a9b0bb]">
              {sits} arrived · {stands} left · seated by each policy
            </span>
          )}
          <span className="text-[0.7rem] text-[#6f7682]">
            step {step + 1}/{seq.steps.length}
          </span>
        </div>
        <button
          type="button"
          data-testid="shuffle"
          onClick={advance}
          className="rounded-md border border-brass bg-brass px-3 py-1.5 text-[0.8rem] font-semibold text-[#1a1407] transition hover:brightness-105"
        >
          {atEnd ? '↺ Reset room' : 'Simulate room activity →'}
        </button>
      </div>

      <div className="flex flex-col gap-4 xl:flex-row">
        <div className="flex min-w-0 flex-1 flex-col gap-5 lg:flex-row">
        <LobbyDataTable
          rows={cur.standard}
          policy="Standard"
          blurb="fills the fullest tables first"
          showBadges={false}
          prevOrderIds={prev?.standard.map((r) => r.table_id)}
          crossOrderIds={cur.fairplay.map((r) => r.table_id)}
          crossLabel="FP"
          selected={ui.selected}
          onSelect={lobbyStore.toggleSelected}
          accent="standard"
        />
        <LobbyDataTable
          rows={cur.fairplay}
          policy="FairPlay"
          blurb="routes toward healthy tables"
          showBadges
          prevOrderIds={prev?.fairplay.map((r) => r.table_id)}
          crossOrderIds={cur.standard.map((r) => r.table_id)}
          crossLabel="Std"
          selected={ui.selected}
          onSelect={lobbyStore.toggleSelected}
          accent="fairplay"
        />
        </div>
        <div className="flex h-[62vh] w-full flex-col xl:h-auto xl:min-h-0 xl:w-[23rem] xl:shrink-0">
          {ui.selected && cur.op_detail?.[ui.selected] ? (
            <LobbySidecar
              key={ui.selected}
              detail={cur.op_detail[ui.selected]}
              onClose={() => lobbyStore.setSelected(null)}
            />
          ) : (
            <div className="flex min-h-0 flex-1 items-center justify-center rounded-md border border-dashed border-[#2a2e36] bg-[rgba(0,0,0,0.15)] p-6 text-center text-[0.78rem] text-[#6f7682]">
              Select a table to preview its seats — then switch to Pit-boss view for why it's
              ranked where it is.
            </div>
          )}
        </div>
      </div>

      <div className="mt-3 rounded-md border border-[#262a32] bg-[rgba(0,0,0,0.2)]">
        <button
          type="button"
          onClick={lobbyStore.toggleDiag}
          className="flex w-full cursor-pointer select-none items-center gap-1 px-3 py-1.5 text-left text-[0.72rem] text-[#8b8276]"
        >
          <span className="text-[#6f7682]">{ui.diagOpen ? '▾' : '▸'}</span>
          Admin · seating this step
          {sits + stands > 0 ? ` (${sits} sat, ${stands} stood per policy)` : ''}
        </button>
        {ui.diagOpen && (
          <div className="grid gap-4 border-t border-[#1e2128] px-3 py-2 md:grid-cols-2">
            <EventList title="Standard — most-full" events={cur.events?.standard ?? []} />
            <EventList title="FairPlay — router" events={cur.events?.fairplay ?? []} />
          </div>
        )}
      </div>

      <p className="mt-3 text-[0.72rem] text-[#6f7682]">
        Same arrivals, seated by each policy — Standard packs the fullest tables (they fill and
        drop to the bottom as <span className="text-[#8b8276]">Waitlist</span>); FairPlay routes
        toward healthy tables. The <span className="text-[#8b8276]">vs</span> column shows each
        table's rank in the other room; click a table to inspect it (preview + pit-boss view).
        Illustrative synthetic room — not a live cash game.
      </p>
    </section>
  )
}

function EventList({ title, events }: { title: string; events: SeatEvent[] }) {
  return (
    <div>
      <div className="mb-1 text-[0.66rem] uppercase tracking-wider text-[#7e8694]">{title}</div>
      <div className="max-h-48 overflow-y-auto pr-1 text-[0.72rem]">
        {events.length === 0 && <div className="text-[#6f7682]">no activity</div>}
        {events.map((e, i) => (
          <div key={i} className="flex items-center gap-1.5 py-[0.06rem]">
            <span className={e.action === 'sit' ? 'text-[#8be3a7]' : 'text-[#c98b93]'}>
              {e.action === 'sit' ? '+' : '–'}
            </span>
            <span className="text-[#a9b0bb]">{e.archetype ?? e.player_id}</span>
            <span className="text-[#6f7682]">{e.action === 'sit' ? '→' : 'left'}</span>
            <span className="font-mono text-[#d8d2c6]">{e.table_id ?? '—'}</span>
            {e.occ_after && <span className="text-[#6f7682]">({e.occ_after})</span>}
          </div>
        ))}
      </div>
    </div>
  )
}
