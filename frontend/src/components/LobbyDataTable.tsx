import { useEffect, useRef } from 'react'
import type { LobbyRow } from '../data/types'

/**
 * A poker-site-style cash-game lobby table (rows = tables, columns = facts), the
 * default lobby view. Renders ONE ordering of a player-safe `LobbyRow[]`; the
 * board places two of these side by side (Standard vs FairPlay). Player-safe:
 * only neutral table facts + the fit badge — never a score/archetype/risk term.
 */
export function LobbyDataTable({
  rows,
  policy,
  blurb,
  showBadges,
  prevOrderIds,
  crossOrderIds,
  crossLabel,
  selected,
  onSelect,
  accent,
}: {
  rows: LobbyRow[]
  policy: string
  blurb: string
  /** FairPlay side surfaces the fit badge; Standard side stays neutral. */
  showBadges: boolean
  /** table_id order from the previous step, to flag rows that moved up/down. */
  prevOrderIds?: string[]
  /** the OTHER strategy's table_id order — to show how this policy diverges from it. */
  crossOrderIds?: string[]
  /** short name of the other strategy, e.g. "Std" / "FP". */
  crossLabel?: string
  /** the table currently selected in either lobby (highlighted in both). */
  selected?: string | null
  onSelect?: (id: string) => void
  accent: 'standard' | 'fairplay'
}) {
  const prevIndex = new Map((prevOrderIds ?? []).map((id, i) => [id, i]))
  const crossIndex = new Map((crossOrderIds ?? []).map((id, i) => [id, i]))
  const headTone =
    accent === 'fairplay' ? 'text-[#8be3a7] border-[#2f7d4a]' : 'text-[#b8c0cf] border-[#3a4757]'

  // How different is this top-10 from the other strategy's top-10?
  const crossOn = crossIndex.size > 0
  const topN = 10
  const otherTop = new Set((crossOrderIds ?? []).slice(0, topN))
  const sharedTop = rows.slice(0, topN).filter((r) => otherTop.has(r.table_id)).length

  // When the selection changes, bring the matching row into view in this table too.
  const containerRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!selected) return
    const el = containerRef.current?.querySelector(`[data-tableid="${selected}"]`)
    el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [selected])

  return (
    <section className="min-w-0 flex-1" aria-label={`${policy} lobby`}>
      <header className={`mb-2 flex items-baseline justify-between border-b pb-1.5 ${headTone}`}>
        <h3 className="m-0 text-[0.95rem] font-semibold tracking-wide">{policy}</h3>
        <span className="text-[0.72rem] text-[#8b8276]">
          {blurb}
          {crossOn && (
            <span className="ml-1 text-[#6f7682]">
              · top 10: {sharedTop}/{topN} shared with {crossLabel}
            </span>
          )}
        </span>
      </header>

      <div
        ref={containerRef}
        className="max-h-[62vh] overflow-y-auto rounded-md border border-[#262a32] bg-[rgba(0,0,0,0.25)]"
      >
        <table className="w-full table-fixed border-collapse whitespace-nowrap text-[0.78rem] [&_td]:overflow-hidden [&_th]:overflow-hidden">
          <colgroup>
            <col className="w-[12%]" />
            <col className="w-[15%]" />
            <col className="w-[9%]" />
            <col className="w-[7%]" />
            <col className="w-[10%]" />
            <col className="w-[10%]" />
            <col className="w-[10%]" />
            <col className="w-[17%]" />
            <col className="w-[10%]" />
          </colgroup>
          <thead className="sticky top-0 z-10 bg-[#15171c]">
            <tr className="text-[0.64rem] uppercase tracking-[0.1em] text-[#7e8694]">
              <th className="px-2 py-1.5 text-left font-medium">{crossLabel ? `vs ${crossLabel}` : ''}</th>
              <th className="px-2 py-1.5 text-left font-medium">Table</th>
              <th className="px-2 py-1.5 text-left font-medium">Stakes</th>
              <th className="px-2 py-1.5 text-center font-medium">Plrs</th>
              <th className="px-2 py-1.5 text-right font-medium">Avg pot</th>
              <th className="px-2 py-1.5 text-right font-medium">Plrs/Flop</th>
              <th className="px-2 py-1.5 text-right font-medium">Hnds/Hr</th>
              <th className="px-2 py-1.5 text-left font-medium">{showBadges ? 'Fit' : ''}</th>
              <th className="px-2 py-1.5 text-right font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const was = prevIndex.get(r.table_id)
              const moved = was === undefined ? 0 : was - i // >0 = moved up
              const full = r.open_seats <= 0
              const otherIdx = crossIndex.get(r.table_id)
              const cross = otherIdx === undefined ? 0 : otherIdx - i // >0 = ranked higher here than the other
              const isSel = selected === r.table_id
              return (
                <tr
                  key={r.table_id}
                  data-testid="lobby-row"
                  data-tableid={r.table_id}
                  onClick={() => onSelect?.(r.table_id)}
                  className={`cursor-pointer border-t border-[#1e2128] transition-colors duration-500 ${
                    isSel
                      ? 'bg-[rgba(224,189,118,0.16)] ring-1 ring-inset ring-brass'
                      : moved > 0
                        ? 'bg-[rgba(47,125,74,0.16)]'
                        : 'odd:bg-[rgba(255,255,255,0.012)] hover:bg-[rgba(255,255,255,0.04)]'
                  }`}
                >
                  <td className="px-2 py-1.5 whitespace-nowrap">
                    {crossOn && otherIdx !== undefined ? (
                      <span className="inline-flex items-center gap-1">
                        <span
                          className={
                            cross > 0
                              ? 'text-[#8be3a7]'
                              : cross < 0
                                ? 'text-[#c98b93]'
                                : 'text-[#6f7682]'
                          }
                        >
                          {cross > 0 ? `▲${cross}` : cross < 0 ? `▼${-cross}` : '='}
                        </span>
                        <span className="text-[0.66rem] text-[#6f7682]">
                          {crossLabel} #{otherIdx + 1}
                        </span>
                      </span>
                    ) : null}
                  </td>
                  <td className="px-2 py-1.5">
                    <span className="inline-flex items-center gap-1.5">
                      <span className="rounded-[4px] bg-[linear-gradient(180deg,#e0bd76,#b78a3c)] px-1.5 py-[0.06rem] font-mono text-[0.72rem] font-bold text-[#2c1f08]">
                        {r.table_id}
                      </span>
                      {moved > 0 && <span className="text-[0.62rem] text-[#8be3a7]">▲{moved}</span>}
                      {moved < 0 && <span className="text-[0.62rem] text-[#c98b93]">▼{-moved}</span>}
                    </span>
                  </td>
                  <td className="px-2 py-1.5 text-[#d8d2c6]">{r.stakes}</td>
                  <td className="px-2 py-1.5 text-center">
                    <span className={full ? 'text-[#c98b93]' : 'text-[#d8d2c6]'}>
                      {r.seated_count}/{r.max_seats}
                    </span>
                  </td>
                  <td className="px-2 py-1.5 text-right text-[#d8d2c6]">
                    {r.avg_pot_usd != null ? `$${r.avg_pot_usd}` : '—'}
                  </td>
                  <td className="px-2 py-1.5 text-right text-[#a9b0bb]">
                    {r.plrs_per_flop_pct != null ? `${r.plrs_per_flop_pct}%` : '—'}
                  </td>
                  <td className="px-2 py-1.5 text-right text-[#a9b0bb]">{r.hands_per_hour ?? '—'}</td>
                  <td className="px-2 py-1.5">
                    {showBadges && r.badge === 'recommended' && (
                      <span className="rounded-full border border-[#2f7d4a] bg-[#16341f] px-1.5 py-[0.05rem] text-[0.62rem] text-[#8be3a7]">
                        Recommended
                      </span>
                    )}
                    {showBadges && r.badge === 'good_fit' && (
                      <span className="rounded-full border border-[#2f6a8a] bg-[#1a2c3a] px-1.5 py-[0.05rem] text-[0.62rem] text-[#8fd0ef]">
                        Good fit
                      </span>
                    )}
                  </td>
                  <td className="px-2 py-1.5 text-right">
                    <button
                      type="button"
                      disabled={full}
                      className="rounded border border-[#2f7d4a] bg-[#16341f] px-2 py-[0.1rem] text-[0.68rem] font-semibold text-[#8be3a7] transition hover:bg-[#1c4429] disabled:cursor-not-allowed disabled:border-[#3a3f47] disabled:bg-transparent disabled:text-[#5b626c]"
                    >
                      {full ? 'Full' : 'Join'}
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
