import { useSyncExternalStore } from 'react'
import type { LobbySequence } from '../data/types'
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

      <div className="flex flex-col gap-5 lg:flex-row">
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
          events={cur.events?.standard}
          diagOpen={ui.diagOpen}
          onToggleDiag={lobbyStore.toggleDiag}
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
          events={cur.events?.fairplay}
          diagOpen={ui.diagOpen}
          onToggleDiag={lobbyStore.toggleDiag}
          accent="fairplay"
        />
      </div>

      <p className="mt-3 text-[0.72rem] text-[#6f7682]">
        Same arrivals, seated by each policy — Standard packs the fullest tables (they fill and
        drop to the bottom as <span className="text-[#8b8276]">Waitlist</span>); FairPlay routes
        toward healthy tables. The <span className="text-[#8b8276]">vs</span> column shows each
        table's rank in the other room; click a table to highlight it in both; expand the admin box
        for the per-step seating. Illustrative synthetic room — not a live cash game.
      </p>

      {ui.selected && cur.op_detail?.[ui.selected] && (
        <LobbySidecar
          detail={cur.op_detail[ui.selected]}
          onClose={() => lobbyStore.setSelected(null)}
        />
      )}
    </section>
  )
}
