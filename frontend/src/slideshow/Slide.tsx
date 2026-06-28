import type { ReactNode } from 'react'

/**
 * The slide-authoring kit. Compose these to build a slide that matches the
 * FairPlay IQ "back of house" look (ink + brass + felt, mono accents) for free.
 *
 * The deck shell (views/Slideshow.tsx) supplies the outer chrome — full-screen
 * background, logo, page number, arrow nav. A slide only fills the stage. Start
 * every slide with <Slide kicker=… title=…> and drop the kit pieces inside.
 */

/** The frame every slide should use. `center` vertically centers the content
 * (good for title / statement slides); the default top-aligns it. */
export function Slide({
  kicker,
  title,
  children,
  center = false,
}: {
  kicker?: ReactNode
  title?: ReactNode
  children?: ReactNode
  center?: boolean
}) {
  return (
    <div className={`flex h-full w-full flex-col ${center ? 'justify-center' : 'justify-start'}`}>
      {kicker && (
        <div className="mb-3 font-mono text-[0.8rem] uppercase tracking-[0.28em] text-brass">
          {kicker}
        </div>
      )}
      {title && (
        <h2 className="m-0 mb-7 text-[2.6rem] font-bold leading-[1.08] tracking-[-0.01em] text-text">
          {title}
        </h2>
      )}
      <div className="min-h-0 flex-1 text-[1.15rem] leading-relaxed text-muted">{children}</div>
    </div>
  )
}

/** A big lead sentence — the one thing you want the room to read. */
export function Lead({ children }: { children: ReactNode }) {
  return <p className="m-0 max-w-[46ch] text-[1.6rem] leading-snug text-text">{children}</p>
}

/** A bordered surface panel — the deck's default container for grouped content. */
export function Card({
  children,
  brassTop = false,
  className = '',
}: {
  children: ReactNode
  brassTop?: boolean
  className?: string
}) {
  return (
    <div
      className={`rounded-xl border border-line bg-surface p-6 shadow-[0_10px_24px_rgba(0,0,0,0.38)] ${
        brassTop ? 'border-t-2 border-t-brass' : ''
      } ${className}`}
    >
      {children}
    </div>
  )
}

/** A headline number with a label. The deck's primary "show a metric" element. */
export function Stat({
  value,
  label,
  sub,
  tone = 'brass',
}: {
  value: ReactNode
  label: ReactNode
  sub?: ReactNode
  tone?: 'brass' | 'felt' | 'text'
}) {
  const valueColor =
    tone === 'felt' ? 'text-[#5fcf8a]' : tone === 'text' ? 'text-text' : 'text-brass'
  return (
    <div>
      <div className={`font-mono text-[3rem] font-bold leading-none tabular-nums ${valueColor}`}>
        {value}
      </div>
      <div className="mt-2 text-[1rem] text-text">{label}</div>
      {sub && <div className="mt-1 text-[0.85rem] text-faint">{sub}</div>}
    </div>
  )
}

/** A small pill chip — for tags, badges, or a row of guardrail words. */
export function Pill({
  children,
  tone = 'neutral',
}: {
  children: ReactNode
  tone?: 'neutral' | 'brass' | 'felt'
}) {
  const tones = {
    neutral: 'border-line bg-surface-2 text-muted',
    brass: 'border-brass bg-[rgba(199,154,75,0.12)] text-brass',
    felt: 'border-[#2f7d4a] bg-[#16341f] text-[#8be3a7]',
  }
  return (
    <span
      className={`inline-flex items-center rounded-full border px-3 py-1 text-[0.8rem] tracking-wider ${tones[tone]}`}
    >
      {children}
    </span>
  )
}

/** A two-or-more column row. Pass `cols` to control the grid. */
export function Columns({ cols = 2, children }: { cols?: number; children: ReactNode }) {
  return (
    <div className="grid gap-5" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
      {children}
    </div>
  )
}

/** A clean bullet list with brass markers. */
export function Bullets({ items }: { items: ReactNode[] }) {
  return (
    <ul className="m-0 flex list-none flex-col gap-3 p-0">
      {items.map((item, i) => (
        <li key={i} className="flex gap-3">
          <span className="mt-[0.6em] h-[0.4rem] w-[0.4rem] shrink-0 rounded-full bg-brass" />
          <span className="text-text">{item}</span>
        </li>
      ))}
    </ul>
  )
}

/** A muted source / footnote line — use it under web-sourced figures. */
export function Cite({ children }: { children: ReactNode }) {
  return <p className="m-0 mt-4 font-mono text-[0.72rem] text-faint">{children}</p>
}

/** A dashed "drop your view here" panel for slides a colleague will fill in. */
export function Placeholder({ title, children }: { title: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex h-full min-h-[18rem] flex-col items-center justify-center rounded-xl border-2 border-dashed border-[#2c3543] bg-[rgba(255,255,255,0.015)] p-8 text-center">
      <div className="font-mono text-[0.78rem] uppercase tracking-[0.28em] text-brass">
        Placeholder
      </div>
      <div className="mt-3 text-[1.5rem] font-semibold text-text">{title}</div>
      {children && <div className="mt-3 max-w-[52ch] text-[1rem] text-muted">{children}</div>}
    </div>
  )
}
