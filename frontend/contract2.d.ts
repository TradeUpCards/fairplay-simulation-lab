/**
 * Contract 2 — Scores + Recommendations (P3 → frontend)
 * ======================================================
 * TypeScript types for the frozen `data/derived/*.json` artifacts the P3
 * scoring engine emits. Hand-maintained to mirror the Python `as_dict()`
 * outputs; the source of truth for the *values* is `docs/scoring-thresholds.md`
 * and the `scoring/*.py` modules.
 *
 * These describe the SHAPE of the data, independent of transport — they apply
 * whether the frontend imports the JSON file today or fetches it from an API
 * later (the API would serve identical shapes).
 *
 * ─────────────────────────────────────────────────────────────────────────────
 *  THE LOAD-BEARING RULE, ENFORCED BY THE TYPE SYSTEM
 * ─────────────────────────────────────────────────────────────────────────────
 * The player lobby must NEVER expose numeric scores, classifications,
 * seating-risk, or integrity language (CLAUDE.md hard rule). The player-facing
 * type below — `LobbyTable` — is deliberately NARROWED: it structurally has no
 * `health`, `rank`, `seating_risk`, `archetype`, or integrity field. The
 * `OperatorOnly` branded type makes the separation a COMPILE ERROR:
 *
 *     function renderLobbyCard(t: LobbyTable) { ... }
 *     renderLobbyCard(operatorView[0]);   // ❌ does not compile
 *     renderLobbyCard(lobby[0]);          // ✅
 *
 * Bind player screens to `LobbyTable` only. Everything else is operator-facing.
 */

// ── Shared primitives ────────────────────────────────────────────────────────

/** JSON-serializable signal values attached to a reason code (for tooltips). */
export type SignalValue = string | number | boolean | null;
export type Signals = Record<string, SignalValue>;

/**
 * The "why" behind any score. ALWAYS render `detail` verbatim — never
 * hand-write explanation copy (PRD DoD). `code` is a stable key for icon/switch
 * logic; `signals` are the raw values behind it.
 */
export interface ReasonCode {
  code: string;
  detail: string;
  signals: Signals;
}

/**
 * Brand marking a type as operator-facing-only. A `LobbyTable` is intentionally
 * NOT branded, so the two cannot be assigned to each other by mistake.
 */
declare const OPERATOR_ONLY: unique symbol;
export type OperatorOnly<T> = T & { readonly [OPERATOR_ONLY]: true };

export interface Contract2Meta {
  schema_version: string;
  contract: string;
  score: string;
  note?: string;
  [k: string]: SignalValue | string[] | undefined;
}

// ── ① Classification (operator-facing) ───────────────────────────────────────

export type Archetype =
  | "new" | "recreational" | "regular" | "grinder" | "aggressive_predatory"
  | "promo_hunter" | "shared_device_household" | "cluster_member"
  | "healthy_anchor" | "bot_like";

export type Classification = OperatorOnly<{
  player_id: string;
  archetype: Archetype;
  reason_codes: ReasonCode[];
}>;

export interface ClassificationsFile {
  meta: Contract2Meta;
  classifications: Classification[];
}

// ── ② Integrity (operator-facing) ────────────────────────────────────────────

export type IntegrityBand = "low" | "neutral" | "high" | "manual_review";
export type IntegrityGroupKind =
  | "cluster" | "household" | "regular_overlap" | "bot_account";
export type IntegrityAction =
  | "monitor" | "hold_for_pitboss_review" | "route_to_bot_review_queue";

export type IntegrityAssessment = OperatorOnly<{
  group_id: string;
  group_kind: IntegrityGroupKind;
  member_ids: string[];
  band: IntegrityBand;
  convergence_count: number;
  recommended_action: IntegrityAction;
  /** PRIMARY signal families that fired (counted toward convergence). */
  signal_families: ReasonCode[];
  /** Supporting context, not counted toward the band. */
  corroborating: ReasonCode[];
  /** Exculpatory evidence — ALWAYS render this next to the finding (guardrail). */
  counter_evidence: ReasonCode[];
  note: string;
}>;

export interface IntegrityScoresFile {
  meta: Contract2Meta;
  assessments: IntegrityAssessment[];
}

// ── ③–⑥ Table health (operator-facing) ───────────────────────────────────────

export type HealthBand =
  | "healthy" | "fragile" | "beginner_unfriendly" | "collapsed";

export interface HealthTerms {
  P_pred: number;   // predation pressure, 0–45
  P_frag: number;   // fragility, 0–25
  P_clus: number;   // active-cluster severity, 0–30
  P_bleed: number;  // observed bleed, 0–20 (0 in the static snapshot by design)
}

export type HealthScore = OperatorOnly<{
  table_id: string;
  health: number;          // 0–100
  band: HealthBand;
  /** A seated high-band cluster → surface to the pit-boss queue regardless of score. */
  integrity_candidate: boolean;
  terms: HealthTerms;
  reason_codes: ReasonCode[];
}>;

export interface HealthScoresFile {
  meta: Contract2Meta;
  health_scores: HealthScore[];
}

// ── ⑦ Seating (operator-facing) ──────────────────────────────────────────────

export type SeatingRisk = "low" | "medium" | "high";

export type SeatingCandidate = OperatorOnly<{
  player_id: string;
  table_id: string;
  fit: number;             // 0–100
  delta_health: number;    // marginal ΔHealth if seated
  seating_risk: SeatingRisk;
  integrity_gated: boolean;
  reason_codes: ReasonCode[];
  table_health: number;
  table_band: HealthBand;
}>;

export interface SeekingPlayer {
  player_id: string;
  candidate_tables: SeatingCandidate[];
}

export interface SeatingScoresFile {
  meta: Contract2Meta;
  seeking_players: SeekingPlayer[];
}

// ── ⑧ Router (mixed — operator_view 🔴 vs player_lobby 🟢) ─────────────────────

export type Badge = "recommended" | "good_fit" | "available" | "hidden_gated";

/** Full routing breakdown for the pit-boss console. OPERATOR-FACING. */
export type RouterOperatorRow = OperatorOnly<{
  table_id: string;
  rank: number;
  badge: Badge;
  fit: number;
  health: number;
  health_band: HealthBand;
  delta_health: number;
  seating_risk: SeatingRisk;
  integrity_gated: boolean;
}>;

/**
 * 🟢 PLAYER-FACING. The ONLY type a player screen may bind to.
 *
 * Structurally narrowed: it has NO `rank`, `health`, `seating_risk`,
 * `archetype`, or integrity field — so an operator value cannot be passed to a
 * lobby component without a compile error. `hidden_gated` tables are already
 * absent from the lobby array, so `badge` here is never `hidden_gated`.
 *
 * Bind lobby chips to `badge_label`; show only the neutral table facts present.
 */
export interface LobbyTable {
  table_id: string;
  stakes: string;
  game_type: string;
  max_seats: number;
  seated_count: number;
  open_seats: number;
  pace_label: string;
  badge: Exclude<Badge, "hidden_gated">;
  badge_label: "Recommended for you" | "Good fit" | "Available";
}

export interface RouterPolicy {
  w_fit: number;
  w_health: number;
  w_delta: number;
  rec_rank_min: number;
  goodfit_rank_min: number;
}

export interface RoutedPlayer {
  player_id: string;
  policy: RouterPolicy;
  /** 🔴 OPERATOR-FACING — pit-boss console only. */
  operator_view: RouterOperatorRow[];
  /** 🟢 PLAYER-FACING — the lobby. Already filtered + gated-tables removed. */
  player_lobby: LobbyTable[];
}

export interface RouterLobbyFile {
  meta: Contract2Meta;
  routed: RoutedPlayer[];
}

// ── Convenience: the full Contract-2 bundle ──────────────────────────────────

export interface Contract2 {
  classifications: ClassificationsFile;   // data/derived/classifications.json
  integrity: IntegrityScoresFile;         // data/derived/integrity_scores.json
  health: HealthScoresFile;               // data/derived/health_scores.json
  seating: SeatingScoresFile;             // data/derived/seating_scores.json
  router: RouterLobbyFile;                // data/derived/router_lobby.json
}
