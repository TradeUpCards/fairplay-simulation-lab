import { useState } from "react";
import { Slide } from "../Slide";
import { StageControl } from "./agentic";
import { useStageKeys } from "../useStageKeys";
import type { SlideDef } from "../types";
import type { LobbySequence, OperatorTableDetail } from "../../data/types";
import { LobbySidecar } from "../../components/LobbySidecar";
import lobbySequenceRaw from "@data/derived/lobby_sequence.json";

/**
 * "A busy table isn't a healthy one." — the naïve standard-routing story.
 *
 * Standard routing just lists open tables sorted by how full they are. A new
 * player picks a busy one and joins; on the surface everything looks fine. This
 * slide stages that reveal in three beats, reusing the real lobby UI:
 *   0 · the lobby grid (full / partial / empty, filterable) — naïve view
 *   1 · the chosen table in the *player view* (handles + stacks, looks lively)
 *   2 · the same table with the curtain pulled back (LobbySidecar pit-boss view)
 *       — a predator pile-up around one recreational player, short seat time.
 *
 * All seated data is the frozen lobby fixture; LR-33 is a real fragile,
 * predator-heavy table from step 0 of the sequence.
 */
const SEQ = lobbySequenceRaw as unknown as LobbySequence;
const OD: Record<string, OperatorTableDetail> = SEQ.steps[0]?.op_detail ?? {};

/** The table our recreational player drifts toward — 5/6, looks lively; really a
 *  fragile predator pile-up (2 aggressive predators vs 1 recreational). */
const REVEAL_ID = "LR-33";
const reveal = OD[REVEAL_ID];

// A curated lobby spanning the three buckets (a few full, several partial incl.
// the mark table, a few empty) so the filter chips have something to do.
const LOBBY_IDS = [
  "LR-10",
  "LR-24",
  "LR-27", // full
  "LR-33",
  "LR-06",
  "LR-19",
  "LR-01",
  "LR-05",
  "LR-12", // partial (LR-33 = the mark)
  "LR-36",
  "LR-37",
  "LR-44", // empty
];

type Bucket = "full" | "partial" | "empty";
type Filter = "all" | Bucket;
const bucketOf = (d: OperatorTableDetail): Bucket =>
  d.open_seats === 0 ? "full" : d.seated_count === 0 ? "empty" : "partial";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "full", label: "Full" },
  { key: "partial", label: "Partial" },
  { key: "empty", label: "Empty" },
];

/** A neutral, player-facing lobby card — seats as dots, no scores, no archetypes. */
function LobbyCard({ d, mark }: { d: OperatorTableDetail; mark: boolean }) {
  return (
    <div
      className={`rounded-xl border bg-surface p-3 transition-colors ${
        mark
          ? "border-brass shadow-[0_0_0_1px_var(--color-brass)]"
          : "border-line"
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="font-mono text-[0.92rem] font-bold tracking-[0.03em] text-brass">
          {d.table_id.replace("LR-", "T-")}
        </span>
        <span className="text-[0.72rem] text-muted">{d.stakes}</span>
      </div>
      <div className="mt-2.5 flex gap-1" aria-hidden="true">
        {Array.from({ length: d.max_seats }, (_, i) => (
          <span
            key={i}
            className={`h-2.5 w-2.5 rounded-full ${
              i < d.seated_count
                ? "bg-[#6b7283]"
                : "border border-dashed border-[#3a4757]"
            }`}
          />
        ))}
      </div>
      <div className="mt-2.5 flex items-center justify-between text-[0.72rem]">
        <span className="text-faint">
          {d.seated_count}/{d.max_seats} seated
        </span>
        {mark ? (
          <span className="font-semibold text-brass">◀ your pick</span>
        ) : d.open_seats === 0 ? (
          <span className="text-faint">full</span>
        ) : d.seated_count === 0 ? (
          <span className="text-faint">empty</span>
        ) : null}
      </div>
    </div>
  );
}

/** Stage 0 — the naïve lobby: filterable grid of tables, the mark highlighted. */
function LobbyStage({
  filter,
  setFilter,
}: {
  filter: Filter;
  setFilter: (f: Filter) => void;
}) {
  const cards = LOBBY_IDS.map((id) => OD[id]).filter(
    (d): d is OperatorTableDetail =>
      !!d && (filter === "all" || bucketOf(d) === filter),
  );
  return (
    <div className="flex flex-col gap-4">
      <p className="m-0 max-w-[78ch] text-[1.05rem] leading-relaxed text-muted">
        <span className="text-text">Standard routing</span> just lists the open
        tables — sorted by how full they are — and you filter to taste. More
        players means more action, right? Our recreational player picks{" "}
        <span className="text-brass">T-33</span>: five seated, one seat open, a
        lively game. It all looks fine on the surface.
      </p>

      <div className="flex gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => setFilter(f.key)}
            className={`rounded-full border px-3 py-1 text-[0.74rem] tracking-wider ${
              filter === f.key
                ? "border-brass bg-[rgba(199,154,75,0.12)] text-brass"
                : "border-line bg-surface-2 text-muted hover:text-text"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-4 gap-3 max-[900px]:grid-cols-3">
        {cards.map((d) => (
          <LobbyCard key={d.table_id} d={d} mark={d.table_id === REVEAL_ID} />
        ))}
      </div>
    </div>
  );
}

/** Stages 1–2 — the chosen table: player view, then curtain pulled back. */
function FocusStage({
  stage,
  setStage,
}: {
  stage: number;
  setStage: (n: number) => void;
}) {
  if (!reveal)
    return (
      <p className="text-muted">Lobby fixture missing table {REVEAL_ID}.</p>
    );
  const revealed = stage >= 2;
  return (
    <div
      className="grid gap-6 max-[900px]:grid-cols-1"
      style={{ gridTemplateColumns: "minmax(0,360px) minmax(0,1fr)" }}
    >
      <div className="flex h-[30rem]">
        <LobbySidecar
          detail={reveal}
          pitboss={revealed}
          onPitbossChange={(v) => setStage(v ? 2 : 1)}
          onClose={() => setStage(0)}
        />
      </div>

      <div className="flex flex-col justify-center gap-4">
        {!revealed ? (
          <>
            <div className="font-mono text-[0.8rem] uppercase tracking-[0.22em] text-brass">
              What the player sees
            </div>
            <p className="m-0 max-w-[46ch] text-[1.35rem] leading-snug text-text">
              Handles and stacks. Five players in, one open seat — a lively
              $0.50/$1 game.
            </p>
            <p className="m-0 max-w-[52ch] text-[1.05rem] leading-relaxed text-muted">
              Standard routing surfaced T-33 because it&apos;s nearly full.
              Nothing here hints at <span className="text-text">who</span> is
              actually sitting there — or how long our recreational player will
              last.
            </p>
          </>
        ) : (
          <>
            <div className="font-mono text-[0.8rem] uppercase tracking-[0.22em] text-[#e38b8b]">
              What the pit boss sees
            </div>
            <p className="m-0 max-w-[48ch] text-[1.35rem] leading-snug text-text">
              Two aggressive predators stacked against a single recreational
              player.
            </p>
            <p className="m-0 max-w-[52ch] text-[1.15rem] leading-snug text-text">
              Naïve routing optimized for a{" "}
              <span className="text-brass">full</span> table — and fed the
              recreational to the sharks. A full table, a short session: the{" "}
              <span className="text-[#e38b8b]">opposite</span> of seat time.
            </p>
          </>
        )}
      </div>
    </div>
  );
}

function StandardRoutingSlide() {
  const [stage, setStage] = useState(0);
  const [filter, setFilter] = useState<Filter>("all");
  // → / ← step lobby → player view → curtain reveal before the deck moves on
  useStageKeys(stage, 3, setStage);
  const STAGE_LABELS = ["Inspect the table", "Pull back the curtain", "Replay"];
  const advance = () => setStage((s) => (s >= 2 ? 0 : s + 1));

  return (
    <Slide
      kicker="Standard routing · the hidden problem"
      title="Busy tables don't always mean they're healthy."
    >
      <div className="flex flex-col gap-6">
        {stage === 0 ? (
          <LobbyStage filter={filter} setFilter={setFilter} />
        ) : (
          <FocusStage stage={stage} setStage={setStage} />
        )}
        <StageControl
          label={STAGE_LABELS[stage]}
          stage={stage}
          total={3}
          onAdvance={advance}
        />
      </div>
    </Slide>
  );
}

export const standardRoutingSlide: SlideDef = {
  id: "standard-routing",
  label: "Standard routing",
  Component: StandardRoutingSlide,
};
