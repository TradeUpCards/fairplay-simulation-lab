import { useEffect, useSyncExternalStore } from 'react'
import type { LobbyRow, LobbySequence, OperatorTableDetail, SeatEvent } from '../data/types'
import { loadLobbySequence } from '../data/shim'
import { useResource } from '../state/useResource'
import { lobbyStore } from '../state/lobbyStore'
import { ResourceBoundary } from './ResourceBoundary'
import { LobbyDataTable } from './LobbyDataTable'
import { LobbySidecar } from './LobbySidecar'
import { SeatAvatar, ARCH_AVATAR } from './tableArt'
import { avatarFor, handleFor, forecastFor, archetypeBadge } from '../lib/lobbyIdentity'

type OpDetailMap = Record<string, OperatorTableDetail>
const tShort = (id: string | null | undefined) => (id ?? '—').replace('LR-', 'T-')

/**
 * Demo Part 2 — staged as scenes. Scene 1 ("curtain down"): just the Standard
 * lobby, so the room looks like any cash-game lobby; selecting a table previews
 * who's seated (player-safe). Scene 2 ("curtain up"): the same arrivals seated by
 * each policy, side by side — Standard packs the fullest tables (concentration),
 * FairPlay routes via the real router (spread) — with a headline that calls out the
 * difference, a churn stepper, and the operator seat-events drawer. State lives in
 * `lobbyStore` so the scene survives leaving and re-entering the player page. Data
 * is the player-safe `lobby_sequence.json`; no scores in the lobby itself.
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

  // Esc closes the seat-events drawer.
  useEffect(() => {
    if (!ui.diagOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') lobbyStore.toggleDiag()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [ui.diagOpen])

  // Focus mode: when a table is open in pit-boss view, the panel grows wide and the
  // lobby recedes behind it (easier to call out the operator evidence).
  const expanded = ui.pitboss && !!ui.selected && !!cur.op_detail?.[ui.selected]
  const lobbyAreaCls = `transition-opacity duration-500 ${expanded ? 'opacity-40' : ''}`

  const sidecar = (
    <div
      className={`flex h-[62vh] w-full flex-col transition-[width] duration-500 xl:h-[calc(62vh+2.875rem)] xl:shrink-0 ${
        expanded ? 'xl:w-[46rem]' : 'xl:w-[23rem]'
      }`}
    >
      {ui.selected && cur.op_detail?.[ui.selected] ? (
        <LobbySidecar
          key={ui.selected}
          detail={cur.op_detail[ui.selected]}
          pitboss={ui.pitboss}
          onPitbossChange={lobbyStore.setPitboss}
          expanded={expanded}
          onClose={() => lobbyStore.setSelected(null)}
        />
      ) : (
        <div className="flex min-h-0 flex-1 items-center justify-center rounded-md border border-dashed border-[#2a2e36] bg-[rgba(0,0,0,0.15)] p-6 text-center text-[0.78rem] text-[#6f7682]">
          {ui.revealed
            ? "Select a table to preview its seats — then switch to Pit-boss view for why it's ranked where it is."
            : 'Select a table to see who’s sitting there.'}
        </div>
      )}
    </div>
  )

  // ── Scene 1 — curtain down: just the Standard lobby ───────────────────────────
  if (!ui.revealed) {
    return (
      <section aria-label="standard lobby">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-baseline gap-3">
            <span className="text-[0.74rem] uppercase tracking-[0.14em] text-[#8b8276]">Cash games</span>
            <span className="font-mono text-[0.9rem] font-semibold text-[#f3ece0]">Standard lobby</span>
            <span className="text-[0.74rem] text-[#a9b0bb]">most-full tables first</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              data-testid="reveal"
              onClick={() => lobbyStore.setRevealed(true)}
              className="group rounded-md border border-brass bg-[linear-gradient(180deg,#e6c47e,#b78a3c)] px-3.5 py-1.5 text-[0.82rem] font-semibold text-[#241806] shadow-[0_0_0_0_rgba(224,189,118,0.5)] transition hover:brightness-105 hover:shadow-[0_0_18px_2px_rgba(224,189,118,0.35)]"
            >
              Pull back the curtain
              <span className="ml-1.5 inline-block transition-transform group-hover:translate-x-0.5">→</span>
            </button>
          </div>
        </div>

        <div className="flex flex-col gap-4 xl:flex-row">
          <div className={`flex min-w-0 flex-1 flex-col ${lobbyAreaCls}`}>
            <LobbyDataTable
              rows={cur.standard}
              policy="Standard"
              blurb="fills the fullest tables first"
              showBadges={false}
              selected={ui.selected}
              onSelect={lobbyStore.toggleSelected}
              accent="standard"
            />
          </div>
          {sidecar}
        </div>

        <p className="mt-3 text-[0.72rem] text-[#6f7682]">
          A normal cash-game lobby, sorted the usual way — fullest tables first. Click any table to
          see who’s sitting there, then{' '}
          <span className="text-[#8b8276]">pull back the curtain</span> to compare how FairPlay would
          seat the same players. Illustrative synthetic room — not a live cash game.
        </p>
      </section>
    )
  }

  // ── Scene 2 — curtain up: Standard vs FairPlay side by side ────────────────────
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
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => lobbyStore.setRevealed(false)}
            className="rounded-md border border-[#3a3f47] px-2.5 py-1.5 text-[0.74rem] text-[#b8c0cf] transition hover:border-brass hover:text-brass"
          >
            ← Standard only
          </button>
          <button
            type="button"
            data-testid="shuffle"
            onClick={advance}
            className="rounded-md border border-brass bg-brass px-3 py-1.5 text-[0.8rem] font-semibold text-[#1a1407] transition hover:brightness-105"
          >
            {atEnd ? '↺ Reset room' : 'Simulate room activity →'}
          </button>
        </div>
      </div>

      <RevealHeadline standard={cur.standard} fairplay={cur.fairplay} />

      <div className="flex flex-col gap-4 xl:flex-row">
        <div className={`flex min-w-0 flex-1 flex-col gap-5 lg:flex-row ${lobbyAreaCls}`}>
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
        {sidecar}
      </div>

      <div className="mt-3 rounded-md border border-[#262a32] bg-[rgba(0,0,0,0.2)]">
        <button
          type="button"
          onClick={lobbyStore.toggleDiag}
          className="flex w-full cursor-pointer select-none items-center gap-1 px-3 py-2 text-left text-[0.78rem] text-[#b8c0cf]"
        >
          <span className="text-[#6f7682]">{ui.diagOpen ? '▾' : '▸'}</span>
          <span className="font-semibold">How each policy seated this round</span>
          {sits + stands > 0 ? (
            <span className="text-[0.72rem] text-[#8b8276]">
              {' '}· {sits} sat, {stands} stood
            </span>
          ) : null}
        </button>
      </div>

      <p className="mt-3 text-[0.72rem] text-[#6f7682]">
        Same arrivals, seated by each policy — Standard packs the fullest tables (they fill and drop
        to the bottom as <span className="text-[#8b8276]">Waitlist</span>); FairPlay routes toward
        healthy tables. The <span className="text-[#8b8276]">vs</span> column shows each table’s rank
        in the other room; click a table to inspect it (preview + pit-boss view). Illustrative
        synthetic room — not a live cash game.
      </p>

      {/* seat-events bottom drawer — slides up on click, closes back down */}
      <div
        className={`fixed inset-0 z-[80] bg-black/50 transition-opacity duration-300 ${
          ui.diagOpen ? 'opacity-100' : 'pointer-events-none opacity-0'
        }`}
        onClick={lobbyStore.toggleDiag}
        aria-hidden="true"
      />
      <aside
        className={`fixed inset-x-0 bottom-0 z-[81] flex max-h-[72vh] flex-col rounded-t-2xl border-t-2 border-t-brass bg-[#0e1014] shadow-[0_-22px_54px_rgba(0,0,0,0.55)] transition-[transform,opacity] duration-[340ms] ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none ${
          ui.diagOpen ? 'translate-y-0 opacity-100' : 'pointer-events-none translate-y-full opacity-0'
        }`}
        role="dialog"
        aria-label="seat events this round"
        aria-hidden={!ui.diagOpen}
      >
        <div className="mx-auto flex w-full max-w-[1100px] flex-col overflow-hidden px-4 pb-5 pt-3.5">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <div className="text-[1.3rem] font-semibold text-[#f3ece0]">
                How each policy seated this round
              </div>
              {sits + stands > 0 && (
                <div className="text-[0.95rem] text-[#8b8276]">
                  {sits} sat · {stands} stood — same arrivals, two policies
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={lobbyStore.toggleDiag}
              aria-label="close"
              className="rounded-md border border-[#3a3f47] px-2 py-0.5 text-[0.95rem] text-[#b8c0cf] hover:border-brass hover:text-brass"
            >
              ×
            </button>
          </div>
          <div className="grid gap-6 overflow-y-auto md:grid-cols-2">
            <EventColumn
              title="Standard"
              subtitle="packs the fullest table"
              accent="standard"
              events={cur.events?.standard ?? []}
              opDetail={cur.op_detail}
              prevOpDetail={prev?.op_detail}
            />
            <EventColumn
              title="FairPlay"
              subtitle="routes toward a healthy seat"
              accent="fairplay"
              events={cur.events?.fairplay ?? []}
              opDetail={cur.op_detail}
              prevOpDetail={prev?.op_detail}
            />
          </div>
        </div>
      </aside>
    </section>
  )
}

/**
 * Scene-2 callout — a one-line, data-derived contrast of the two policies at this
 * step. Player-safe: occupancy facts only, never a score or archetype. The honest
 * difference between the rooms is concentration: the SAME players fill the SAME
 * number of tables, but Standard packs more of them to capacity (a few crowded
 * tables) while FairPlay leaves seats open (spread thinner). Derived, not written.
 */
function RevealHeadline({ standard, fairplay }: { standard: LobbyRow[]; fairplay: LobbyRow[] }) {
  const fullCount = (rs: LobbyRow[]) => rs.filter((r) => r.open_seats <= 0).length
  const seated = standard.reduce((n, r) => n + r.seated_count, 0)
  const stdFull = fullCount(standard)
  const fpFull = fullCount(fairplay)
  const diverged = stdFull !== fpFull

  return (
    <div
      className="mb-3 flex flex-wrap items-center gap-x-1.5 gap-y-1 rounded-md border border-[#33415a] bg-[linear-gradient(180deg,rgba(47,106,138,0.16),rgba(0,0,0,0.18))] px-3 py-2 text-[0.84rem]"
      data-testid="reveal-headline"
    >
      <span aria-hidden className="mr-0.5 text-[1rem]">⚖️</span>
      {diverged ? (
        <>
          <span className="text-[#cdd4df]">
            Same <strong className="text-[#f3ece0]">{seated}</strong> players —
          </span>
          <span className="font-semibold text-[#f0c98b]">Standard</span>
          <span className="text-[#cdd4df]">
            packs <strong className="text-[#f3ece0]">{stdFull}</strong> tables to capacity;
          </span>
          <span className="font-semibold text-[#8be3a7]">FairPlay</span>
          <span className="text-[#cdd4df]">
            keeps only <strong className="text-[#f3ece0]">{fpFull}</strong> full — open seats let it
            spread players apart.
          </span>
        </>
      ) : (
        <span className="text-[#cdd4df]">
          Same room so far. Hit{' '}
          <span className="font-semibold text-[#f0c98b]">Simulate room activity</span> and watch{' '}
          <span className="font-semibold text-[#f0c98b]">Standard</span> pack tables full while{' '}
          <span className="font-semibold text-[#8be3a7]">FairPlay</span> keeps seats open.
        </span>
      )}
    </div>
  )
}

/** Health-change chip: table health before → after this round (real engine scores).
 *  Lower health is worse, so a drop is warm/red, a rise cool/green. */
function HealthDelta({ before, after }: { before?: number; after?: number }) {
  if (after == null) return null
  if (before == null) {
    return <span className="text-[#a9b0bb]">health <strong className="text-[#d8d2c6]">{Math.round(after)}</strong></span>
  }
  const d = after - before
  const tone = d < -0.5 ? 'text-[#e3a08b]' : d > 0.5 ? 'text-[#8be3a7]' : 'text-[#9098a4]'
  const arrow = d < -0.5 ? '▼' : d > 0.5 ? '▲' : '•'
  return (
    <span className="text-[#a9b0bb]">
      health <strong className="text-[#d8d2c6]">{Math.round(before)}</strong>
      <span className="text-[#6f7682]">→</span>
      <strong className="text-[#d8d2c6]">{Math.round(after)}</strong>{' '}
      <span className={tone}>{arrow}{Math.abs(Math.round(d))}</span>
    </span>
  )
}

function EventColumn({
  title,
  subtitle,
  accent,
  events,
  opDetail,
  prevOpDetail,
}: {
  title: string
  subtitle: string
  accent: 'standard' | 'fairplay'
  events: SeatEvent[]
  opDetail?: OpDetailMap
  prevOpDetail?: OpDetailMap
}) {
  const head = accent === 'fairplay' ? 'text-[#8be3a7]' : 'text-[#cdd4df]'
  const sits = events.filter((e) => e.action === 'sit')
  return (
    <div>
      <div className="mb-3 flex items-baseline gap-3 border-b border-[#1e2128] pb-2.5">
        <span className={`text-[1.5rem] font-semibold ${head}`}>{title}</span>
        <span className="text-[1.1rem] text-[#7e8694]">{subtitle}</span>
      </div>
      <div className="max-h-[52vh] space-y-2.5 overflow-y-auto pr-1">
        {sits.length === 0 && <div className="text-[1.1rem] text-[#6f7682]">no arrivals this round</div>}
        {sits.map((e, i) => {
          const id = e.player_id
          const t = e.table_id ?? undefined
          const after = t ? opDetail?.[t]?.health : undefined
          const before = t ? prevOpDetail?.[t]?.health : undefined
          const mins = forecastFor(id, e.archetype, after)
          return (
            <div
              key={`${id}-${i}`}
              className="flex items-center gap-4 rounded-xl border border-[#23262d] bg-[rgba(0,0,0,0.22)] px-4 py-3.5"
            >
              <div className="relative shrink-0">
                <SeatAvatar label={id} imageUrl={avatarFor(id)} size="xl" />
                {archetypeBadge(e.archetype) ? (
                  <img
                    src={archetypeBadge(e.archetype) as string}
                    alt=""
                    title={(e.archetype ?? '').replace(/_/g, ' ')}
                    className="absolute -bottom-1.5 -right-1.5 h-9 w-9 rounded-full border-2 border-[#0e1014] bg-[#0e1014] object-cover"
                  />
                ) : e.archetype ? (
                  <span className="absolute -bottom-1 -right-1 grid h-8 w-8 place-items-center rounded-full border border-[#0e1014] bg-[#1c2028] text-[0.95rem]">
                    {ARCH_AVATAR[e.archetype] ?? ''}
                  </span>
                ) : null}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2.5">
                  <span className="truncate text-[1.35rem] font-semibold text-[#f3ece0]">
                    {handleFor(id)}
                  </span>
                  <span className="font-mono text-[1.05rem] text-[#7e8694]">→ {tShort(e.table_id)}</span>
                  {e.occ_after && (
                    <span className="rounded-[5px] bg-[rgba(255,255,255,0.06)] px-2 py-[0.1rem] font-mono text-[1rem] text-[#cdb98a]">
                      now {e.occ_after}
                    </span>
                  )}
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-x-3 text-[1.15rem]">
                  <HealthDelta before={before} after={after} />
                  <span className="text-[#6f7682]">·</span>
                  <span className="text-[#a9b0bb]">
                    sits <strong className="text-[#d8d2c6]">~{mins} min</strong> (est.)
                  </span>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
