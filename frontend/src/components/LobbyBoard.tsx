import { useState } from 'react'
import type { LobbySequence } from '../data/types'
import { loadLobbySequence } from '../data/shim'
import { useResource } from '../state/useResource'
import { ResourceBoundary } from './ResourceBoundary'
import { LobbyDataTable } from './LobbyDataTable'

/**
 * Demo Part 2 — the same room shown two ways at once: Standard (sorts by fullest
 * table) vs FairPlay (the router, routes toward healthy tables). The "Simulate
 * room activity" button steps a seeded churn (players stand / sit), which
 * re-ranks both sides — Standard by fullness, FairPlay by the real router. Data
 * is the player-safe `lobby_sequence.json` (playsim → router pipeline). The
 * presenter narrates *why* FairPlay reorders; no scores are ever shown.
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
  const [step, setStep] = useState(0)
  const cur = seq.steps[step]
  const prev = step > 0 ? seq.steps[step - 1] : undefined
  const atEnd = step >= seq.steps.length - 1
  const advance = () => setStep((s) => (s >= seq.steps.length - 1 ? 0 : s + 1))

  return (
    <section aria-label="standard vs fairplay lobby">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <span className="text-[0.74rem] uppercase tracking-[0.14em] text-[#8b8276]">Room state</span>
          <span className="font-mono text-[0.9rem] font-semibold text-[#f3ece0]">{cur.label}</span>
          {cur.churn && (
            <span className="text-[0.74rem] text-[#a9b0bb]">
              {cur.churn.stood} stood · {cur.churn.sat} sat
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
          accent="standard"
        />
        <LobbyDataTable
          rows={cur.fairplay}
          policy="FairPlay"
          blurb="routes toward healthy tables"
          showBadges
          prevOrderIds={prev?.fairplay.map((r) => r.table_id)}
          accent="fairplay"
        />
      </div>

      <p className="mt-3 text-[0.72rem] text-[#6f7682]">
        Same {cur.fairplay.length} tables, ordered two ways. Illustrative synthetic room —
        not a live cash game.
      </p>
    </section>
  )
}
