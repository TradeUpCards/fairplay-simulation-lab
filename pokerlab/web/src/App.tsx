import { useEffect, useState, type ReactNode } from "react";
import { act, getCoaching, getHistory, getNarration, getNarratorAvailable, newGame, nextHand } from "./api";
import { ActionBar } from "./components/ActionBar";
import { CoachPanel } from "./components/CoachPanel";
import { HistoryPanel } from "./components/HistoryPanel";
import { StatsBar } from "./components/StatsBar";
import { StylePicker } from "./components/StylePicker";
import { Table } from "./components/Table";
import type { Coaching, GameState, History, LogEvent } from "./types";

function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen px-4 py-6">
      <div className="mx-auto max-w-4xl">
        <div className="mb-6 flex items-center gap-3">
          <span className="grid h-8 w-8 rotate-45 place-items-center bg-brass font-black text-ink">
            <span className="-rotate-45 text-sm">FP</span>
          </span>
          <div>
            <div className="font-serif text-lg leading-none">FairPlay · AI Poker Lab</div>
            <div className="text-xs uppercase tracking-widest text-faint">train against the agents</div>
          </div>
        </div>
        {children}
      </div>
    </div>
  );
}

function ActionLog({ log }: { log: LogEvent[] }) {
  const STREET = ["preflop", "flop", "turn", "river"];
  return (
    <div className="mt-4 max-h-28 overflow-y-auto rounded-lg border border-line bg-surface-2/60 px-4 py-2 font-mono text-xs text-muted">
      {log.length === 0 && <div className="text-faint">— new hand —</div>}
      {log.map((e, i) => (
        <div key={i}>
          <span className="text-faint">[{STREET[e.street] ?? e.street}]</span>{" "}
          P{e.player_id} <span className="text-text">{e.action}</span>
          {e.amount > 0 && <span> {e.amount}</span>}
        </div>
      ))}
    </div>
  );
}

function ResultPanel({ state, busy, onNext }: { state: GameState; busy: boolean; onNext: () => void }) {
  const r = state.result!;
  const won = r.net_you > 0;
  const tie = r.net_you === 0;
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-line bg-surface/80 px-6 py-4">
      <div className="text-lg font-bold">
        {tie ? "Split pot" : won ? <span className="text-gain">You won</span> : <span className="text-loss">You lost</span>}
        {!tie && (
          <span className="ml-2 font-mono text-base">
            {won ? "+" : ""}
            {(r.net_you / state.bb).toFixed(1)} bb
          </span>
        )}
      </div>
      {r.showdown && <div className="text-xs text-muted">went to showdown</div>}
      {r.reloaded && <div className="text-xs text-brass">stacks reloaded</div>}
      <button
        onClick={onNext}
        disabled={busy}
        className="rounded-lg bg-brass px-6 py-2 font-bold text-ink hover:brightness-110"
      >
        Next hand →
      </button>
    </div>
  );
}

export default function App() {
  const [gid, setGid] = useState<string | null>(null);
  const [state, setState] = useState<GameState | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [coaching, setCoaching] = useState<Coaching | null>(null);
  const [history, setHistory] = useState<History | null>(null);
  const [narratorOn, setNarratorOn] = useState(false);
  const [narration, setNarration] = useState<string | null>(null);
  const [narrating, setNarrating] = useState(false);

  // Is the optional LLM narrator configured on the server? (cheap, no model call)
  useEffect(() => {
    getNarratorAvailable().then(setNarratorOn);
  }, []);

  // Fetch the post-hand review once a hand ends; clear it (and any narration) next hand.
  useEffect(() => {
    setNarration(null);
    if (gid && state?.over) {
      let live = true;
      getCoaching(gid).then((c) => live && setCoaching(c)).catch(() => {});
      return () => { live = false; };
    }
    setCoaching(null);
  }, [gid, state?.over, state?.hand_no]);

  const askCoach = async () => {
    if (!gid) return;
    setNarrating(true);
    try {
      setNarration((await getNarration(gid)) ?? "(no take available)");
    } catch (e) {
      setErr(String(e));
    } finally {
      setNarrating(false);
    }
  };

  // Refresh the session-review list whenever it's open and a hand completes.
  useEffect(() => {
    if (gid && history !== null) {
      getHistory(gid).then(setHistory).catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gid, state?.hand_no, state?.over]);

  const toggleHistory = async () => {
    if (history !== null) { setHistory(null); return; }
    if (gid) {
      try { setHistory(await getHistory(gid)); } catch (e) { setErr(String(e)); }
    }
  };

  const guard = async (fn: () => Promise<{ state: GameState }>) => {
    setBusy(true);
    setErr(null);
    try {
      setState((await fn()).state);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  async function start(style: string) {
    setBusy(true);
    setErr(null);
    try {
      const r = await newGame(style);
      setGid(r.game_id);
      setState(r.state);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  if (!gid || !state) {
    return (
      <Shell>
        <StylePicker busy={busy} onPick={start} />
      </Shell>
    );
  }

  return (
    <Shell>
      <div className="mb-3 flex items-center justify-between text-sm">
        <div>
          vs <span className="font-semibold text-brass">{state.bot.name}</span>
          <span className="ml-3 text-muted">hand #{state.hand_no + 1}</span>
        </div>
        <div className="flex items-center gap-4">
          <button onClick={toggleHistory} className="text-muted hover:text-brass">
            {history !== null ? "hide review" : "session review"}
          </button>
          <button
            onClick={() => { setGid(null); setState(null); setHistory(null); }}
            className="text-muted hover:text-brass"
          >
            change opponent
          </button>
        </div>
      </div>

      {state.stats && <div className="mb-3"><StatsBar stats={state.stats} /></div>}

      {state.walks && state.walks.count > 0 && (
        <div className="mb-3 rounded-lg border border-brass/30 bg-brass/5 px-4 py-2 text-center text-sm text-muted">
          {state.bot.name} folded {state.walks.count} hand{state.walks.count > 1 ? "s" : ""} preflop —
          you took the blinds{" "}
          <span className="font-mono text-gain">+{state.walks.net_bb.toFixed(1)} bb</span>. You're
          in the big blind; here's the next playable hand.
        </div>
      )}

      <Table state={state} />

      <div className="mt-5 flex justify-center">
        {state.over ? (
          <ResultPanel state={state} busy={busy} onNext={() => guard(() => nextHand(gid))} />
        ) : (
          <ActionBar state={state} busy={busy} onAction={(k, a) => guard(() => act(gid, k, a))} />
        )}
      </div>

      {err && <p className="mt-3 text-center text-loss">{err}</p>}

      {state.over && coaching && narratorOn && (
        <div className="mt-4 rounded-2xl border border-felt/30 bg-felt/5 px-5 py-4">
          <div className="flex items-center justify-between gap-3">
            <h3 className="font-serif text-lg text-felt">Coach's take</h3>
            {!narration && (
              <button
                onClick={askCoach}
                disabled={narrating}
                className="rounded-lg border border-felt/50 bg-felt/10 px-4 py-1.5 text-sm font-semibold text-felt hover:bg-felt/20"
              >
                {narrating ? "thinking…" : "Ask the coach"}
              </button>
            )}
          </div>
          {narration && <p className="mt-2 text-sm leading-relaxed text-text">{narration}</p>}
        </div>
      )}

      {state.over && coaching && <CoachPanel coaching={coaching} />}
      <ActionLog log={state.log} />
      {history !== null && <HistoryPanel history={history} />}
    </Shell>
  );
}
