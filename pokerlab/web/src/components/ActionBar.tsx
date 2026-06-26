import { useEffect, useState } from "react";
import type { GameState } from "../types";

export function ActionBar({
  state,
  busy,
  onAction,
}: {
  state: GameState;
  busy: boolean;
  onAction: (kind: string, amount?: number) => void;
}) {
  const { legal, bb, pot } = state;
  const [raiseTo, setRaiseTo] = useState(0);

  useEffect(() => {
    if (legal?.can_raise) setRaiseTo(legal.min_raise_to);
  }, [legal?.can_raise, legal?.min_raise_to]);

  if (state.over || !state.your_turn || !legal) {
    return <div className="h-12" />;
  }

  const callLabel =
    legal.to_call > 0 ? `Call ${(legal.to_call / bb).toFixed(1)} bb` : "Check";

  const clamp = (n: number) => Math.max(legal.min_raise_to, Math.min(legal.max_raise_to, Math.round(n)));
  const potSize = clamp(legal.to_call + pot);
  const halfPot = clamp(legal.to_call + pot * 0.5);

  return (
    <div className="flex flex-wrap items-center justify-center gap-3 rounded-2xl border border-line bg-surface/80 px-5 py-4">
      {legal.can_fold && (
        <button
          onClick={() => onAction("fold")}
          disabled={busy}
          className="rounded-lg border border-line bg-surface-2 px-5 py-2 font-semibold text-loss hover:border-loss"
        >
          Fold
        </button>
      )}

      <button
        onClick={() => onAction("check_call")}
        disabled={busy}
        className="rounded-lg border border-line bg-surface-2 px-5 py-2 font-semibold hover:border-brass"
      >
        {callLabel}
      </button>

      {legal.can_raise && (
        <div className="flex items-center gap-3 rounded-lg border border-line bg-surface-2 px-3 py-2">
          <div className="flex gap-1 text-xs">
            <button className="rounded bg-ink px-2 py-1 hover:text-brass" onClick={() => setRaiseTo(halfPot)}>½ pot</button>
            <button className="rounded bg-ink px-2 py-1 hover:text-brass" onClick={() => setRaiseTo(potSize)}>pot</button>
            <button className="rounded bg-ink px-2 py-1 hover:text-brass" onClick={() => setRaiseTo(legal.max_raise_to)}>all-in</button>
          </div>
          <input
            type="range"
            min={legal.min_raise_to}
            max={legal.max_raise_to}
            value={raiseTo}
            onChange={(e) => setRaiseTo(Number(e.target.value))}
            className="accent-brass"
          />
          <button
            onClick={() => onAction("raise", raiseTo)}
            disabled={busy}
            className="rounded-lg bg-brass px-5 py-2 font-bold text-ink hover:brightness-110"
          >
            {legal.to_call > 0 ? "Raise to" : "Bet"} {(raiseTo / bb).toFixed(1)} bb
          </button>
        </div>
      )}
    </div>
  );
}
