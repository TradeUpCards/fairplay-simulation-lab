import type { Coaching, CoachDecision, Verdict } from "../types";

const V: Record<Verdict, { dot: string; label: string; text: string }> = {
  good: { dot: "bg-gain", label: "GOOD", text: "text-gain" },
  ok: { dot: "bg-muted", label: "OK", text: "text-muted" },
  mistake: { dot: "bg-loss", label: "LEAK", text: "text-loss" },
  info: { dot: "bg-brass", label: "NOTE", text: "text-brass" },
};

const pct = (x: number) => `${Math.round(x * 100)}%`;

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <span className="text-faint">
      {label} <span className="text-text">{value}</span>
    </span>
  );
}

function Row({ d }: { d: CoachDecision }) {
  const v = V[d.verdict] ?? V.info;
  return (
    <li className="flex gap-3 border-t border-line/60 py-2 first:border-t-0">
      <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${v.dot}`} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2 text-sm">
          <span className={`text-[10px] font-bold uppercase tracking-wider ${v.text}`}>{v.label}</span>
          <span className="text-faint">{d.street_name}</span>
          <span className="font-semibold text-text">
            {d.action}
            {d.amount > 0 ? ` ${d.amount}` : ""}
          </span>
        </div>
        <div className="text-sm text-muted">{d.note}</div>
        <div className="mt-0.5 flex flex-wrap gap-x-4 font-mono text-xs">
          <Metric label="equity" value={pct(d.equity)} />
          {d.pot_odds !== null && <Metric label="need" value={pct(d.pot_odds)} />}
          {d.ev_bb !== null && (
            <span className="text-faint">
              EV{" "}
              <span className={d.ev_bb < 0 ? "text-loss" : "text-gain"}>
                {d.ev_bb >= 0 ? "+" : ""}
                {d.ev_bb.toFixed(1)}bb
              </span>
            </span>
          )}
          <Metric label="actual" value={pct(d.actual_equity)} />
        </div>
      </div>
    </li>
  );
}

export function CoachPanel({ coaching }: { coaching: Coaching }) {
  const c = coaching;
  const leak = c.summary.ev_lost_bb > 0;
  return (
    <div className="mt-4 rounded-2xl border border-line bg-surface/70 px-5 py-4">
      <div className="flex items-center justify-between">
        <h3 className="font-serif text-lg">Hand review</h3>
        <span className="font-mono text-xs text-faint">villain had {c.opp_hole.join(" ")}</span>
      </div>
      <p className={`mt-1 text-sm ${leak ? "text-loss" : "text-muted"}`}>{c.summary.headline}</p>

      {c.decisions.length === 0 ? (
        <p className="mt-2 text-sm text-faint">Nothing to grade — you had no voluntary action.</p>
      ) : (
        <ul className="mt-2">
          {c.decisions.map((d, i) => (
            <Row key={i} d={d} />
          ))}
        </ul>
      )}

      <p className="mt-3 text-[11px] leading-snug text-faint">
        <span className="text-muted">Equity</span> = your hand vs a random hand at that moment (what you
        could know). <span className="text-muted">Actual</span> is hindsight vs the villain's real cards —
        shown to learn from, never used to grade the decision.
      </p>
    </div>
  );
}
