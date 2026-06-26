import type { GameState, Seat } from "../types";
import { Card } from "./Card";

function SeatView({ s, bb }: { s: Seat; bb: number }) {
  const ring = s.to_act ? "ring-2 ring-brass shadow-[0_0_24px_var(--color-brass-soft)]" : "ring-1 ring-line";
  return (
    <div className={`flex flex-col items-center gap-2 rounded-xl bg-surface/80 px-4 py-3 ${ring} ${s.folded ? "opacity-40" : ""}`}>
      <div className="flex items-center gap-2 text-sm">
        <span className="font-semibold">{s.name}</span>
        {s.is_button && (
          <span className="grid h-5 w-5 place-items-center rounded-full bg-brass text-[10px] font-black text-ink">D</span>
        )}
      </div>
      <div className="flex gap-1">
        <Card c={s.hole?.[0] ?? null} size="md" />
        <Card c={s.hole?.[1] ?? null} size="md" />
      </div>
      <div className="font-mono text-sm text-muted">
        <span className="text-text">{(s.stack / bb).toFixed(0)}</span> bb
      </div>
    </div>
  );
}

export function Table({ state }: { state: GameState }) {
  const opp = state.seats.find((s) => !s.is_human)!;
  const you = state.seats.find((s) => s.is_human)!;
  const board = [...state.board, ...Array(Math.max(0, 5 - state.board.length)).fill(null)] as (string | null)[];

  return (
    <div className="felt mx-auto flex w-full max-w-3xl flex-col items-center gap-6 rounded-[44px] px-6 py-8">
      <SeatView s={opp} bb={state.bb} />

      <div className="flex flex-col items-center gap-2">
        <div className="flex gap-2">
          {board.map((c, i) => <Card key={i} c={c} size="lg" />)}
        </div>
        <div className="mt-1 rounded-full bg-ink/70 px-4 py-1 font-mono text-sm">
          <span className="text-muted">pot </span>
          <span className="font-bold text-brass">{(state.pot / state.bb).toFixed(1)} bb</span>
        </div>
      </div>

      <SeatView s={you} bb={state.bb} />
    </div>
  );
}
