import type { HealthTerms } from '../data/types'
import { TERM_CAP, TERM_META, TERM_ORDER } from '../lib/health'
import { Tooltip } from './Tooltip'

/**
 * The four health-penalty terms as labelled bars (each scaled to its own cap).
 * Two side-by-side containers that together span 50% of the panel: the labels box
 * shrinks to the widest label, the bars box fills the rest. Both use the same
 * fixed row height so every label lines up with its bar across the two containers.
 *
 * Each label carries an (i) tooltip explaining what the metric measures; hovering
 * a score explains what that value says about this table (copy in TERM_META).
 */
export function TermBars({ terms }: { terms: HealthTerms }) {
  return (
    <div className="flex gap-3" aria-label="health penalty terms">
      {/* text container — only as wide as the longest label (+ its info icon) */}
      <div className="flex shrink-0 flex-col gap-1 rounded-lg border border-line bg-surface px-3 py-2">
        {TERM_ORDER.map((key) => {
          const meta = TERM_META[key]
          return (
            <span key={key} className="flex h-6 items-center gap-1 text-[0.78rem] text-muted">
              {meta.label}
              <Tooltip content={meta.explain}>
                <button
                  type="button"
                  className="inline-flex h-[0.85rem] w-[0.85rem] cursor-help items-center justify-center rounded-full border border-faint bg-transparent p-0 text-[0.58rem] font-semibold leading-none text-faint hover:border-text hover:text-text"
                  aria-label={`What is ${meta.label}?`}
                >
                  i
                </button>
              </Tooltip>
            </span>
          )
        })}
      </div>

      {/* bars + values container — fills the rest of the 50% */}
      <div className="flex flex-1 flex-col gap-1 rounded-lg border border-line bg-surface px-3 py-2">
        {TERM_ORDER.map((key) => (
          <div key={key} className="flex h-6 items-center gap-[0.4rem] text-[0.78rem]">
            <span className="h-1.5 flex-1 overflow-hidden rounded-[3px] bg-line">
              <span
                className="block h-full bg-[#5f7fd9]"
                style={{ width: `${(terms[key] / TERM_CAP[key]) * 100}%` }}
              />
            </span>
            <Tooltip content={TERM_META[key].reads(terms[key])}>
              <span className="cursor-help tabular-nums text-[#c3c9d6]">{terms[key]}</span>
            </Tooltip>
          </div>
        ))}
      </div>
    </div>
  )
}
