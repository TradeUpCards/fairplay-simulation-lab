import pokerTable from '../assets/poker-table.png'
import type { NeutralTable } from '../data/types'

/**
 * A lit table on the dark player floor — the shared card for both the lobby
 * (recommendations, badged by fit) and "My Tables" (current seats, badged
 * "Seated"). Shows only neutral facts (stakes / seats / pace): no scores,
 * archetypes, or risk language (the player/operator wall). Lifts on hover with a
 * glow spilling onto the carpet and a spotlight on the felt.
 */
export function TableTile({
  table,
  badge,
  testId = 'lobby-card',
}: {
  table: NeutralTable
  badge?: { toneClass: string; label: string } | null
  testId?: string
}) {
  return (
    <li data-testid={testId} className="group relative rounded-[14px] transition-transform duration-280 before:pointer-events-none before:absolute before:left-1/2 before:top-1/2 before:z-0 before:h-[165%] before:w-[150%] before:-translate-x-1/2 before:-translate-y-1/2 before:bg-[radial-gradient(46%_44%_at_50%_50%,rgba(255,222,168,0.42),rgba(255,206,148,0.13)_52%,transparent_76%)] before:opacity-0 before:blur-[10px] before:transition-opacity before:duration-340 before:content-[''] hover:-translate-y-1 focus-within:-translate-y-1 hover:before:opacity-100 focus-within:before:opacity-100 motion-reduce:transition-none">
      <div className="relative z-1 aspect-3/2 after:pointer-events-none after:absolute after:inset-0 after:bg-[radial-gradient(52%_50%_at_50%_50%,rgba(255,240,212,0.5),rgba(255,230,190,0.12)_46%,transparent_72%)] after:opacity-0 after:mix-blend-screen after:transition-opacity after:duration-320 after:content-[''] group-hover:after:opacity-100 group-focus-within:after:opacity-100">
        <img
          className="block h-full w-full object-cover brightness-[0.6] saturate-[0.92] transition-[filter,transform] duration-320 group-hover:scale-[1.03] group-hover:brightness-[1.06] group-hover:saturate-[1.05] group-focus-within:scale-[1.03] group-focus-within:brightness-[1.06] group-focus-within:saturate-[1.05] motion-reduce:transition-none motion-reduce:group-hover:transform-none"
          src={pokerTable}
          alt=""
          aria-hidden="true"
        />
        <dl className="absolute left-1/2 top-1/2 z-2 m-0 flex w-[72%] -translate-x-1/2 -translate-y-1/2 flex-wrap justify-center gap-x-[1.7rem] gap-y-2 text-center">
          <div className="flex flex-col gap-[0.05rem]">
            <dt className="text-[0.6rem] uppercase tracking-[0.14em] text-[rgba(228,240,224,0.55)]">Stakes</dt>
            <dd className="m-0 text-[0.92rem] font-semibold text-[#f3efe4] [text-shadow:0_1px_4px_rgba(0,0,0,0.6)]">
              {table.stakes}
            </dd>
          </div>
          <div className="flex flex-col gap-[0.05rem]">
            <dt className="text-[0.6rem] uppercase tracking-[0.14em] text-[rgba(228,240,224,0.55)]">Seats</dt>
            <dd className="m-0 text-[0.92rem] font-semibold text-[#f3efe4] [text-shadow:0_1px_4px_rgba(0,0,0,0.6)]">
              {table.seated_count}/{table.max_seats} · {table.open_seats} open
            </dd>
          </div>
          <div className="flex flex-col gap-[0.05rem]">
            <dt className="text-[0.6rem] uppercase tracking-[0.14em] text-[rgba(228,240,224,0.55)]">Pace</dt>
            <dd className="m-0 text-[0.92rem] font-semibold text-[#f3efe4] [text-shadow:0_1px_4px_rgba(0,0,0,0.6)]">
              {table.pace_label}
            </dd>
          </div>
        </dl>
      </div>
      {badge && (
        <span
          className={`absolute left-1/2 top-[calc(19%-15px)] z-3 -translate-x-1/2 -translate-y-1/2 rounded-full border px-2 py-[0.15rem] text-[0.72rem] shadow-[0_2px_8px_rgba(0,0,0,0.55)] ${badge.toneClass}`}
        >
          {badge.label}
        </span>
      )}
      <span className="absolute left-1/2 top-[calc(82%+15px)] z-3 -translate-x-1/2 -translate-y-1/2 rounded-[5px] border border-[rgba(0,0,0,0.4)] bg-[linear-gradient(180deg,#e0bd76,#b78a3c)] px-[0.7rem] py-[0.18rem] text-[0.82rem] font-bold tracking-wider text-[#2c1f08] shadow-[0_2px_6px_rgba(0,0,0,0.5),inset_0_1px_0_rgba(255,255,255,0.35)]">
        {table.table_id}
      </span>
    </li>
  )
}
