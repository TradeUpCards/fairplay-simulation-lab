import type { HealthTerms } from '../data/types'
import { TERM_CAP, type TermKey } from '../lib/health'

const TERMS: { key: TermKey; label: string }[] = [
  { key: 'P_pred', label: 'Predation' },
  { key: 'P_frag', label: 'Fragility' },
  { key: 'P_clus', label: 'Cluster' },
  { key: 'P_bleed', label: 'Bleed' },
]

/**
 * The four health-penalty terms as labelled bars (each scaled to its own cap).
 * Two side-by-side containers that together span 50% of the panel: the labels box
 * shrinks to the widest label, the bars box fills the rest. Both use the same
 * fixed row height so every label lines up with its bar across the two containers.
 */
export function TermBars({ terms }: { terms: HealthTerms }) {
  return (
    <div className="flex gap-3" aria-label="health penalty terms">
      {/* text container — only as wide as the longest label */}
      <div className="flex shrink-0 flex-col gap-1 rounded-lg border border-line bg-surface px-3 py-2">
        {TERMS.map(({ key, label }) => (
          <span key={key} className="flex h-6 items-center text-[0.78rem] text-muted">
            {label}
          </span>
        ))}
      </div>

      {/* bars + values container — fills the rest of the 50% */}
      <div className="flex flex-1 flex-col gap-1 rounded-lg border border-line bg-surface px-3 py-2">
        {TERMS.map(({ key }) => (
          <div key={key} className="flex h-6 items-center gap-[0.4rem] text-[0.78rem]">
            <span className="h-1.5 flex-1 overflow-hidden rounded-[3px] bg-line">
              <span
                className="block h-full bg-[#5f7fd9]"
                style={{ width: `${(terms[key] / TERM_CAP[key]) * 100}%` }}
              />
            </span>
            <span className="tabular-nums text-[#c3c9d6]">{terms[key]}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
