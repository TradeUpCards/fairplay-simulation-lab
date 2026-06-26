import { useState } from "react";
import type { HandHistoryEntry, History } from "../types";
import { CoachPanel } from "./CoachPanel";

function outcomeClass(o: string) {
  return o === "won" ? "text-gain" : o === "lost" ? "text-loss" : "text-muted";
}

function Row({ h, open, onToggle }: { h: HandHistoryEntry; open: boolean; onToggle: () => void }) {
  const leak = h.coaching.summary.ev_lost_bb;
  return (
    <div className="border-t border-line/60 first:border-t-0">
      <button
        onClick={onToggle}
        className="flex w-full items-center gap-3 px-1 py-2 text-left text-sm hover:bg-surface-2/40"
      >
        <span className="w-9 shrink-0 text-faint">#{h.hand_no + 1}</span>
        <span className="w-16 shrink-0 font-mono text-brass">{h.hole.join(" ")}</span>
        <span className="flex-1 truncate font-mono text-xs text-faint">{h.board.join(" ") || "—"}</span>
        {leak > 0 && <span className="shrink-0 font-mono text-xs text-loss">−{leak.toFixed(1)}</span>}
        <span className={`w-16 shrink-0 text-right font-mono ${outcomeClass(h.outcome)}`}>
          {h.net_bb >= 0 ? "+" : ""}
          {h.net_bb.toFixed(1)}bb
        </span>
        <span className="w-4 shrink-0 text-faint">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="pb-2">
          <CoachPanel coaching={h.coaching} />
        </div>
      )}
    </div>
  );
}

export function HistoryPanel({ history }: { history: History }) {
  const [open, setOpen] = useState<number | null>(null);

  return (
    <div className="mt-4 rounded-2xl border border-line bg-surface/70 px-4 py-3">
      <h3 className="mb-2 font-serif text-lg">Session review</h3>
      {history.hands.length === 0 ? (
        <p className="text-sm text-faint">No hands played yet — play a few, then review them here.</p>
      ) : (
        <div>
          {history.hands.map((h) => (
            <Row
              key={h.hand_no}
              h={h}
              open={open === h.hand_no}
              onToggle={() => setOpen(open === h.hand_no ? null : h.hand_no)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
