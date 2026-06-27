import { useEffect, useState } from "react";
import { getStyles } from "../api";
import type { Style } from "../types";

// Tier order for the section headers (Trained bots last).
const TIER_ORDER = ["Beginner", "Intermediate", "Advanced", "Expert", "Trained"];

function groupByTier(styles: Style[]): [string, Style[]][] {
  const by = new Map<string, Style[]>();
  for (const s of styles) {
    const tier = s.kind === "rl" ? "Trained" : s.tier ?? "Intermediate";
    (by.get(tier) ?? by.set(tier, []).get(tier)!).push(s);
  }
  return TIER_ORDER.filter((t) => by.has(t)).map((t) => [t, by.get(t)!]);
}

function StyleCard({ s, busy, onPick }: { s: Style; busy: boolean; onPick: (k: string) => void }) {
  return (
    <button
      disabled={busy}
      onClick={() => onPick(s.key)}
      className="rounded-xl border border-line bg-surface px-5 py-4 text-left transition hover:border-brass hover:bg-surface-2"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="font-bold text-brass">{s.name}</div>
        {s.kind === "rl" ? (
          <span className="rounded-full border border-felt/50 bg-felt/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-felt">
            Trained · PPO
          </span>
        ) : (
          <span className="rounded-full border border-line px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-faint">
            Heuristic
          </span>
        )}
      </div>
      <div className="mt-1 text-sm text-muted">{s.blurb}</div>
    </button>
  );
}

export function StylePicker({ busy, onPick }: { busy: boolean; onPick: (key: string) => void }) {
  const [styles, setStyles] = useState<Style[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    getStyles().then(setStyles).catch((e) => setErr(String(e)));
  }, []);

  const hasTrained = styles.some((s) => s.kind === "rl");
  const groups = groupByTier(styles);

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="font-serif text-3xl tracking-tight">Choose your opponent</h1>
      <p className="mt-1 text-muted">
        Pick a difficulty. Hand-tuned characters have a distinct, exploitable style — learn to read
        it. Bots you train yourself have no fixed leak; they just play to win.
      </p>

      {err && (
        <p className="mt-4 rounded-lg border border-loss/40 bg-loss/10 px-4 py-3 text-loss">
          Can't reach the server. Start it on :8000 (see README). <span className="text-faint">{err}</span>
        </p>
      )}

      {groups.map(([tier, items]) => (
        <div key={tier} className="mt-6">
          <div className="mb-2 flex items-center gap-3">
            <h2 className="text-xs font-bold uppercase tracking-widest text-faint">{tier}</h2>
            <div className="h-px flex-1 bg-line" />
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {items.map((s) => (
              <StyleCard key={s.key} s={s} busy={busy} onPick={onPick} />
            ))}
          </div>
        </div>
      ))}

      {!err && !hasTrained && (
        <p className="mt-5 text-sm text-faint">
          No trained bots yet. Train one (<span className="text-muted">python -m pokerlab.rl.train …</span>,
          or <span className="text-muted">train_selfplay</span>, see the README) and it appears here under
          “Trained”.
        </p>
      )}
    </div>
  );
}
