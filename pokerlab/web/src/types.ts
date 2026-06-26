export interface Seat {
  seat: number;
  player_id: number;
  name: string;
  is_human: boolean;
  stack: number;
  folded: boolean;
  is_button: boolean;
  hole: string[] | null;
  to_act: boolean;
}

export interface Legal {
  can_fold: boolean;
  can_check: boolean;
  to_call: number;
  can_raise: boolean;
  min_raise_to: number;
  max_raise_to: number;
}

export interface LogEvent {
  seat: number;
  player_id: number;
  street: number;
  action: string;
  amount: number;
  pot_before: number;
  to_call?: number;
}

export type Verdict = "good" | "ok" | "mistake" | "info";

export interface CoachDecision {
  street: number;
  street_name: string;
  action: string;
  amount: number;
  to_call: number;
  pot_before: number;
  equity: number;
  pot_odds: number | null;
  ev_bb: number | null;
  verdict: Verdict;
  note: string;
  actual_equity: number;
}

export interface Coaching {
  hole: string[];
  opp_hole: string[];
  board: string[];
  net_bb: number;
  decisions: CoachDecision[];
  summary: {
    net_bb: number;
    ev_lost_bb: number;
    headline: string;
    biggest_leak: CoachDecision | null;
  };
}

export interface Result {
  payoffs: Record<string, number>;
  net_you: number;
  board: string[];
  showdown: boolean;
  reloaded: boolean;
}

export interface GameState {
  hand_no: number;
  sb: number;
  bb: number;
  board: string[];
  pot: number;
  seats: Seat[];
  your_turn: boolean;
  legal: Legal | null;
  log: LogEvent[];
  over: boolean;
  result: Result | null;
  walks?: { count: number; net_bb: number } | null;
  stats?: SessionStats;
  bot: { style: string; name: string; kind?: StyleKind; blurb?: string };
}

export interface SessionStats {
  hands_played: number;
  walks_won: number;
  net_bb: number;
  bb_per_100: number;
  won: number;
  lost: number;
  tie: number;
  win_rate: number;
  ev_lost_bb: number;
}

export interface HandHistoryEntry {
  hand_no: number;
  hole: string[];
  board: string[];
  net_bb: number;
  outcome: "won" | "lost" | "tie";
  showdown: boolean;
  coaching: Coaching;
}

export interface History {
  stats: SessionStats;
  hands: HandHistoryEntry[];
}

export type StyleKind = "heuristic" | "rl";

export interface Style {
  key: string;
  name: string;
  blurb: string;
  kind?: StyleKind;
  difficulty?: number;
  tier?: string;
}
