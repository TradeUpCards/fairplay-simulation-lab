import logo from '../assets/fairplay-iq-logo-brass.svg'

export type ViewMode = 'operator' | 'player' | 'training'

/**
 * App header — the brass rail atop the console. The FairPlay IQ wordmark anchors
 * it; the Operator|Player toggle is the app's primary navigation and makes the
 * player/operator wall a visible boundary (player screens never expose scores).
 * A monospace "synthetic data" status states the responsible-use framing up
 * front. Deliberately quiet — the app's signature is the seat-ring, not the chrome.
 */
export function Header({
  mode,
  onModeChange,
  route = 'home',
  onOpenDashboard,
  slideshowHref,
}: {
  mode: ViewMode
  onModeChange: (mode: ViewMode) => void
  route?: 'home' | 'dashboard' | 'slideshow'
  onOpenDashboard?: () => void
  slideshowHref?: string
}) {
  return (
    <header
      className="sticky top-0 z-50 border-t-2 border-t-brass border-b border-b-line bg-[linear-gradient(180deg,#0c1015,var(--color-ink))]"
      role="banner"
    >
      <div className="mx-auto flex max-w-[1360px] items-center justify-between gap-4 px-6 py-[0.7rem]">
        <div className="flex items-center gap-[0.8rem]">
          <img className="block h-[30px] w-auto" src={logo} alt="FairPlay IQ" />
          <span className="h-[22px] w-px bg-brass-soft" aria-hidden="true" />
          <span className="font-mono text-[0.7rem] uppercase tracking-[0.2em] text-muted">
            Simulation Lab
          </span>
        </div>

        <div
          className="ml-auto inline-flex gap-0.5 rounded-full border border-line bg-surface-2 p-0.5"
          role="tablist"
          aria-label="Audience view"
        >
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'player'}
            className={`rounded-full border-none px-[0.95rem] py-[0.32rem] text-[0.74rem] tracking-wider ${
              mode === 'player'
                ? 'bg-brass font-semibold text-[#1a1407]'
                : 'bg-transparent text-muted hover:text-text'
            }`}
            onClick={() => onModeChange('player')}
          >
            Player
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'training'}
            className={`rounded-full border-none px-[0.95rem] py-[0.32rem] text-[0.74rem] tracking-wider ${
              mode === 'training'
                ? 'bg-brass font-semibold text-[#1a1407]'
                : 'bg-transparent text-muted hover:text-text'
            }`}
            onClick={() => onModeChange('training')}
          >
            Train
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'operator'}
            className={`rounded-full border-none px-[0.95rem] py-[0.32rem] text-[0.74rem] tracking-wider ${
              mode === 'operator'
                ? 'bg-brass font-semibold text-[#1a1407]'
                : 'bg-transparent text-muted hover:text-text'
            }`}
            onClick={() => onModeChange('operator')}
          >
            Pit Boss
          </button>
        </div>

        {onOpenDashboard && (
          <button
            type="button"
            onClick={onOpenDashboard}
            aria-current={route === 'dashboard' ? 'page' : undefined}
            className={`rounded-full border px-[0.9rem] py-[0.32rem] text-[0.72rem] tracking-wider ${
              route === 'dashboard'
                ? 'border-brass bg-[rgba(199,154,75,0.12)] text-brass'
                : 'border-line bg-surface-2 text-muted hover:text-text'
            }`}
          >
            Sweep Dashboard
          </button>
        )}

        {slideshowHref && (
          <a
            href={slideshowHref}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center rounded-full border border-line bg-surface-2 px-[0.9rem] py-[0.32rem] text-[0.72rem] tracking-wider text-muted no-underline hover:text-text"
          >
            Slideshow ↗
          </a>
        )}

        <p className="m-0 flex items-center gap-[0.45rem] font-mono text-[0.66rem] uppercase tracking-[0.16em] text-faint max-[560px]:hidden">
          <span
            className="h-2 w-2 rounded-full bg-felt shadow-[0_0_0_3px_rgba(47,143,91,0.18)]"
            aria-hidden="true"
          />
          Synthetic data
        </p>
      </div>
    </header>
  )
}
