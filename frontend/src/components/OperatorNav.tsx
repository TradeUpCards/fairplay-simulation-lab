export type OperatorView = 'console' | 'simulator' | 'eval'

/**
 * The order is the demo spine inside the back of house: the lobby hands off to
 * the pit-boss **Console** (review/override), which opens the **Simulator**
 * (Standard vs FairPlay), which is proven out in **Eval**. A quiet tab bar under
 * the brass header — subordinate to the Operator|Player toggle, which is still
 * the primary nav.
 */
const TABS: { id: OperatorView; label: string; hint: string }[] = [
  { id: 'console', label: 'Console', hint: 'Pit-boss review' },
  { id: 'simulator', label: 'Simulator', hint: 'Standard vs FairPlay' },
  { id: 'eval', label: 'Eval', hint: 'Evidence & proof' },
]

export function OperatorNav({
  view,
  onViewChange,
}: {
  view: OperatorView
  onViewChange: (view: OperatorView) => void
}) {
  return (
    <nav className="mb-7 border-b border-line" aria-label="Operator views">
      <div className="inline-flex gap-[0.4rem]" role="tablist">
        {TABS.map((tab) => {
          const active = view === tab.id
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={active}
              className={`group -mb-px flex flex-col gap-[0.15rem] border-0 border-b-2 bg-transparent px-[1.05rem] pb-[0.6rem] pt-[0.55rem] text-left ${
                active ? 'border-b-brass' : 'border-b-transparent'
              }`}
              onClick={() => onViewChange(tab.id)}
            >
              <span
                className={`text-[0.92rem] tracking-[0.02em] ${
                  active ? 'font-semibold text-brass' : 'text-muted group-hover:text-text'
                }`}
              >
                {tab.label}
              </span>
              <span className="font-mono text-[0.62rem] uppercase tracking-[0.13em] text-faint">
                {tab.hint}
              </span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}
