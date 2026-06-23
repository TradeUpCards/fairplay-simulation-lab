import type { ReactNode } from 'react'

/**
 * A small hover/focus tooltip. Wraps a trigger and reveals a styled bubble on
 * hover (or keyboard focus). Uses a *named* group (`group/tip`) so each instance
 * only responds to its own trigger, not sibling tooltips. Defaults to opening
 * below-and-left of the trigger — the safe direction inside the scrollable
 * detail drawer, where a top/centered bubble can clip at the edges.
 */
export function Tooltip({
  content,
  children,
  side = 'bottom',
  align = 'left',
}: {
  content: ReactNode
  children: ReactNode
  side?: 'top' | 'bottom'
  align?: 'left' | 'center'
}) {
  const vy =
    side === 'top'
      ? 'bottom-[calc(100%+0.4rem)] translate-y-1'
      : 'top-[calc(100%+0.4rem)] -translate-y-1'
  const hx = align === 'center' ? 'left-1/2 -translate-x-1/2' : 'left-0'
  return (
    <span className="group/tip relative inline-flex">
      {children}
      <span
        role="tooltip"
        className={`pointer-events-none invisible absolute z-20 w-max max-w-[260px] ${hx} ${vy} rounded-lg border border-line bg-[rgba(8,10,14,0.97)] px-[0.6rem] py-[0.45rem] text-left text-[0.7rem] font-normal normal-case leading-[1.4] tracking-normal text-text opacity-0 shadow-[0_10px_24px_rgba(0,0,0,0.5)] transition-[opacity,transform] duration-140 [text-shadow:none] group-hover/tip:visible group-hover/tip:translate-y-0 group-hover/tip:opacity-100 group-focus-within/tip:visible group-focus-within/tip:translate-y-0 group-focus-within/tip:opacity-100`}
      >
        {content}
      </span>
    </span>
  )
}
