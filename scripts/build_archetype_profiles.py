"""Build docs/archetype-play-profiles.md — agent behavioral spec for simulating
poker play per archetype.

Computes each archetype's real stat distribution from data/players.json and
merges it with an authored poker-policy translation (how an agent that actually
plays hands should behave to land on those stats). The output is a single
self-contained markdown doc to hand to a model / teammate designing the
play-simulation agent harness.

Run:  python scripts/build_archetype_profiles.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "archetype-play-profiles.md"

ORDER = ["new", "recreational", "regular", "grinder", "aggressive_predatory",
         "promo_hunter", "healthy_anchor", "shared_device_household",
         "cluster_member", "bot_like"]


def truth_of(pid: str) -> str:
    n = int(pid.split("-")[1])
    for hi, lab in [(107, "new"), (141, "recreational"), (163, "regular"),
                    (175, "grinder"), (183, "aggressive_predatory"),
                    (191, "promo_hunter"), (197, "shared_device_household"),
                    (202, "cluster_member"), (220, "healthy_anchor")]:
        if n <= hi:
            return lab
    return "bot_like"


# Authored poker-policy translation per archetype. Stats are computed; this is
# the "how an agent plays to hit them" design layer.
NOTES = {
    "new": dict(
        tag="Brand-new, tentative, loose-passive — busts or logs off fast.",
        style="Plays lots of hands out of curiosity but almost never the aggressor (pfr .08); passive postflop (AF < 1 = calls far more than it bets). Tiny pots, ~20-min sessions, churns quickly — especially at a tough table (CASE-A: 12 min then exit).",
        preflop="Enter ~36% of hands, but raise-first-in only ~8% — mostly open-limp / cold-call. No 3-betting.",
        postflop="Calling station: chases draws, calls down light, rarely bets or raises. Makes -EV calls (low skill).",
        sizing="Min-bets and flat-calls; never builds a pot (~8bb).",
        session="15–26 min, 2–6 sessions/mo. Logs off on a loss or after a short stretch — model a low stop-loss / low stamina.",
        knobs="looseness HIGH · aggression VERY LOW · skill LOW · stamina VERY LOW · tilt-to-quit HIGH"),
    "recreational": dict(
        tag="The casual fish — loosest range, still passive. The cohort to protect.",
        style="Widest vpip (.38) but low aggression (pfr .12, AF ~1.2). Plays for fun; medium sessions; calls too much.",
        preflop="Enter ~38% (widest), raise ~12%, lots of limp/call. Defends blinds too wide.",
        postflop="Slightly aggressive on made hands, otherwise call-happy; chases draws and pays off value.",
        sizing="Small–medium pots (~11bb).",
        session="~73 min, ~9 sessions/mo.",
        knobs="looseness HIGHEST · aggression LOW · skill LOW–MED · stamina MED · loss-aversion LOW (plays through losses)"),
    "regular": dict(
        tag="Solid TAG — tight, aggressive, competent.",
        style="Tighter (.28), raises most hands it plays (small vpip–pfr gap → few limps), genuinely aggressive postflop (AF 2.06).",
        preflop="~28% range, raise-first ~22% (mostly raise-or-fold), few limps; will 3-bet.",
        postflop="Balanced aggression — c-bets, value-bets, occasional bluff; folds to real pressure.",
        sizing="Standard ~19bb pots.",
        session="~135 min, ~16 sessions/mo.",
        knobs="looseness MED–LOW · aggression MED–HIGH · skill MED–HIGH · stamina MED"),
    "grinder": dict(
        tag="High-volume professional — tight, relentless, marathon sessions.",
        style="Tight (.23), virtually never limps (vpip–pfr gap ~.02 = raise-or-fold), strong postflop aggression (2.69). 5+ hour sessions, 25/mo, enormous lifetime volume. A table-HEALTH concern (CASE-B), NOT integrity.",
        preflop="~23% tight range, raise-first ~21%, essentially zero limps; positional 3-bets.",
        postflop="Multi-street barreling, thin value, balanced bluffs; exploits weak opponents.",
        sizing="Bigger pots (~27bb), plays higher stakes.",
        session="260–420 min, 21–28 sessions/mo — near-daily long grinds.",
        knobs="looseness LOW · aggression HIGH · skill HIGH · stamina VERY HIGH · exploit-weak ON"),
    "aggressive_predatory": dict(
        tag="Hyper-LAG table-killer — the predation pressure new/rec players feel.",
        style="Very loose (.59) AND very aggressive (pfr .45, AF 4.3 — bets/raises ~4× as often as it calls). Big pots (43bb). Makes weak players bust fast. NOT cheating — a dangerous skilled aggressor (CASE-A aggressors P-176/177).",
        preflop="Enter ~59%, raise-first ~45% — relentless isolation/3-betting, attacks limpers and blinds.",
        postflop="Maximal aggression: barrels, bluffs, applies constant pressure; targets the weakest player at the table.",
        sizing="Large pots and oversized bets to pressure (~43bb).",
        session="~250 min, ~20 sessions/mo — hunts soft tables.",
        knobs="looseness HIGH · aggression MAXED · skill HIGH · target-weak-players ON · bluff-freq HIGH"),
    "promo_hunter": dict(
        tag="Bonus-clearer — minimal-risk volume to clear promos (13.5/mo tell).",
        style="Plays low-variance to grind rake/bonus requirements. Short frequent sessions (39 min × 20/mo), low aggression, small pots; the giveaway is 13.5 promo redemptions/mo. A health/economics concern (CASE-F), NOT collusion.",
        preflop="~30% range but the OBJECTIVE is hands-volume to clear the bonus, not winning; low raise (~13%).",
        postflop="Passive and risk-averse — avoid variance, fold to aggression, protect the bonus EV.",
        sizing="Small pots (~10bb); declines marginal +EV spots that add variance.",
        session="Many short sessions timed to promo availability; stops when the requirement clears.",
        knobs="aggression LOW · risk-aversion HIGH · session-trigger = promo-available · hands-volume TARGET · stakes LOW"),
    "healthy_anchor": dict(
        tag="The good stabilizing regular — solid, friendly, sticks around. NON-predatory.",
        style="Tight-ish (.28), moderate aggression (1.88 — below grinder/regular), long friendly sessions (209 min), high frequency. Keeps tables alive without crushing recreationals.",
        preflop="~28% range, raise ~18%; straightforward, not a maniac.",
        postflop="Moderate, honest aggression; value-heavy, light on bluffs; does NOT hunt the weakest player.",
        sizing="Standard ~17bb pots.",
        session="162–315 min, ~20 sessions/mo — a reliable presence.",
        knobs="looseness MED–LOW · aggression MED · skill MED · stamina HIGH · target-weak OFF (stabilizer, not predator)"),
    "shared_device_household": dict(
        tag="Two people, one device, DIFFERENT styles — the false-positive trap.",
        style="Each account plays like an ordinary recreational/regular, but the load-bearing simulation property is TWO accounts on one device_group that are behaviorally INDEPENDENT: divergent schedules (e.g. one evenings ~145 min, one mornings ~110 min), different vpip/pfr, and LOW co-seating — they do NOT play together. Benign — monitor, never escalate (CASE-E).",
        preflop="Per-account, like a recreational/regular blend — but distinct between the two accounts.",
        postflop="Ordinary; crucially NO soft-play between the two (soft_play_delta = 0).",
        sizing="Normal for their level (~15bb).",
        session="The two accounts deliberately occupy DIFFERENT time windows and rarely share a table.",
        knobs="model as TWO independent sub-agents · shared device_group_id · DIVERGENT schedule+style params · co_seating LOW · soft_play OFF"),
    "cluster_member": dict(
        tag="Coordinated collusion ring — soft vs each other, hard on outsiders.",
        style="Competent regulars (.30/.23/2.15) whose DEFINING behavior is coordination: they sit together (high co-seating), play SOFT against each other (soft_play_delta ≤ −0.60 → give up EV / chip-dump in member-vs-member pots), gang up on non-members, and have correlated action timing. The true-positive integrity case (CASE-C).",
        preflop="Vs outsiders: aggressive isolation and squeezing. Vs members: avoid raising into each other; fold marginal spots to a teammate.",
        postflop="Vs outsiders: apply coordinated pressure (whipsaw/squeeze). Vs members: check down, don't barrel each other, chip-dump on demand (the soft-play signal).",
        sizing="Normal vs outsiders; suppressed / value-giving vs members.",
        session="Coordinated table selection — members converge on the same tables (high co-seating rate).",
        knobs="MEMBER-SET awareness REQUIRED · soft_play toggle (cut aggression+EV vs members) · co-seat preference HIGH · outsider-targeting ON · timing-correlation across members"),
    "bot_like": dict(
        tag="A bot — mechanically consistent, no human timing variance.",
        style="Reasonable stats, but the tell is timing_regularity .88 (near-uniform action timing) + very high session frequency (28/mo, robotic schedule). Plays a fixed rule-based / GTO-ish policy with no tilt and no variance. Own review queue (CASE-G), separate from collusion.",
        preflop="Consistent, unemotional fixed ranges; identical decisions in identical spots.",
        postflop="Deterministic policy; same sizing every time; no timing tells, no tilt, no fatigue.",
        sizing="Uniform, rule-based (~20bb).",
        session="Robotic cadence and near-24/7 availability; action latency has very low jitter (the detection signal).",
        knobs="DETERMINISTIC policy · action-timing JITTER ≈ 0 · tilt OFF · fatigue OFF · availability ~24/7"),
}

# Which fields to show in each archetype's stat block.
CORE = ["vpip", "pfr", "aggression_factor", "avg_pot_size_bb",
        "avg_session_minutes", "sessions_last_30d", "lifetime_hands",
        "promo_redemptions_30d"]
INTEGRITY = ["soft_play_delta", "timing_regularity", "bot_similarity_score"]
LABELS = {"vpip": "vpip", "pfr": "pfr", "aggression_factor": "aggression factor",
          "avg_pot_size_bb": "avg pot (bb)", "avg_session_minutes": "session (min)",
          "sessions_last_30d": "sessions/30d", "lifetime_hands": "lifetime hands",
          "promo_redemptions_30d": "promo/30d", "soft_play_delta": "soft_play_delta",
          "timing_regularity": "timing_regularity", "bot_similarity_score": "bot_similarity"}


def fmt(v: float) -> str:
    return f"{v:,.0f}" if abs(v) >= 100 else f"{v:.2f}"


def main() -> int:
    df = pd.DataFrame(json.loads((ROOT / "data" / "players.json").read_text(encoding="utf-8"))["players"])
    df["a"] = df["player_id"].map(truth_of)

    def med_range(sub, f):
        return sub[f].median(), sub[f].min(), sub[f].max()

    L = []
    L.append("# Archetype Play Profiles — agent spec for simulating poker play")
    L.append("")
    L.append("> **Purpose.** A behavioral spec for agents that **actually play hands**, one per "
             "player archetype, so a simulation can produce realistic table dynamics. Each archetype's "
             "**stat distribution is computed from the real 122-player fixture** (`data/players.json`); "
             "the **play-policy translation is the design layer** — how an agent should act to land on "
             "those stats.")
    L.append(">")
    L.append("> **Responsible-use framing.** This is for the FairPlay **integrity-detection simulation "
             "lab** — synthetic agents in a sandbox, generating table dynamics so the detector can be "
             "tested. Simulating the predatory / collusion / bot archetypes exists so the system learns "
             "to *flag* them. It is **not** a tool for real-money play, RTA, actual collusion, or "
             "enforcement (see `CLAUDE.md` non-goals).")
    L.append(">")
    L.append("> Regenerate: `python scripts/build_archetype_profiles.py`")
    L.append("")
    L.append("---")
    L.append("")

    # Primer
    L.append("## How to read a stat as a play policy")
    L.append("")
    L.append("The fixture defines archetypes by **aggregate stats**, not strategy. To drive a "
             "hand-playing agent, map each stat onto a decision knob:")
    L.append("")
    L.append("| Stat | Meaning | Agent knob |")
    L.append("|---|---|---|")
    L.append("| `vpip` | % of hands voluntarily played | **preflop looseness** — entering range width (vpip .38 ≈ play ~38% of starting hands) |")
    L.append("| `pfr` | % of hands raised preflop | **preflop aggression** — raise-first frequency. `vpip − pfr` = limp/call gap (passivity) |")
    L.append("| `aggression_factor` | (bets+raises)/calls postflop | **postflop aggression** — AF 4.3 = barrels/bluffs; AF < 1 = calling station |")
    L.append("| `avg_pot_size_bb` | mean pot when involved | **bet sizing / stakes** — pot-building tendency |")
    L.append("| `avg_session_minutes` · `sessions_last_30d` | session length / frequency | **stamina, stop-loss, schedule** — when the agent sits and quits |")
    L.append("| `lifetime_hands` | total volume | **experience / skill proxy** |")
    L.append("| `promo_redemptions_30d` | bonus redemptions | **promo-chasing trigger** (promo_hunter) |")
    L.append("| `soft_play_delta` | EV given up vs cluster members | **collusion soft-play** — negative = chip-dump / fold to teammate (cluster_member) |")
    L.append("| `timing_regularity` | action-timing consistency | **timing jitter** — ~1.0 = robotic, no human variance (bot_like) |")
    L.append("")
    L.append("---")
    L.append("")

    # Master table
    L.append("## Master table (medians, computed)")
    L.append("")
    L.append("| archetype | n | vpip | pfr | AF | pot(bb) | session(min) | sessions/30d | integrity tell |")
    L.append("|---|--:|--:|--:|--:|--:|--:|--:|---|")
    tells = {"cluster_member": "soft_play ≤ −0.60", "bot_like": "timing_reg ≈ 0.88",
             "shared_device_household": "shared device, divergent play", "promo_hunter": "13.5 promo/30d"}
    for a in ORDER:
        s = df[df.a == a]
        L.append(f"| **{a}** | {len(s)} | {s.vpip.median():.2f} | {s.pfr.median():.2f} | "
                 f"{s.aggression_factor.median():.2f} | {s.avg_pot_size_bb.median():.0f} | "
                 f"{s.avg_session_minutes.median():.0f} | {s.sessions_last_30d.median():.0f} | "
                 f"{tells.get(a, '—')} |")
    L.append("")
    L.append("---")
    L.append("")

    # Per-archetype profiles
    L.append("## Per-archetype agent profiles")
    for a in ORDER:
        s = df[df.a == a]
        nt = NOTES[a]
        L.append("")
        L.append(f"### {a}  ·  *{nt['tag']}*")
        L.append(f"<sub>n = {len(s)} players in the fixture</sub>")
        L.append("")
        # stat block
        cells = []
        for f in CORE:
            m, lo, hi = med_range(s, f)
            cells.append(f"`{LABELS[f]}` {fmt(m)} _[{fmt(lo)}–{fmt(hi)}]_")
        integ = [f for f in INTEGRITY if not (s[f].abs().max() < 0.2 and f == "soft_play_delta")]
        # always show the integrity tell fields that matter for this archetype
        if a == "cluster_member":
            m, lo, hi = med_range(s, "soft_play_delta")
            cells.append(f"`soft_play_delta` {fmt(m)} _[{fmt(lo)}–{fmt(hi)}]_")
        if a in ("bot_like",):
            m, lo, hi = med_range(s, "timing_regularity")
            cells.append(f"`timing_regularity` {fmt(m)}")
            m, lo, hi = med_range(s, "bot_similarity_score")
            cells.append(f"`bot_similarity` {fmt(m)}")
        L.append("**Stats (median [range]):** " + " · ".join(cells))
        L.append("")
        L.append(f"- **Style:** {nt['style']}")
        L.append(f"- **Preflop:** {nt['preflop']}")
        L.append(f"- **Postflop:** {nt['postflop']}")
        L.append(f"- **Sizing:** {nt['sizing']}")
        L.append(f"- **Session / stamina:** {nt['session']}")
        L.append(f"- **Agent knobs:** {nt['knobs']}")
    L.append("")
    L.append("---")
    L.append("")

    # Harness design
    L.append("## Suggested agent-harness design (agents that play hands)")
    L.append("")
    L.append("1. **One parameterized policy, ten knob-sets.** Build a single decision policy and "
             "instantiate each archetype as a vector of knobs: `{looseness, preflop_aggression, "
             "postflop_aggression, sizing, skill, stamina, risk_aversion}` plus integrity flags "
             "`{soft_play_members, target_weak, timing_jitter, promo_trigger}`. The tables above give "
             "the target value for each.")
    L.append("2. **Decision engine.** Per street: estimate hand strength / equity vs a range model, then "
             "let the knobs bias the thresholds — looseness lowers the equity needed to enter; "
             "aggression converts marginal calls into bets/raises; sizing sets bet amounts. Position and "
             "stack depth modulate.")
    L.append("3. **Calibration loop (closes play ↔ stats).** Run each agent over many seeded hands, "
             "measure its *realized* vpip / pfr / AF / pot size, and tune the knobs until they match the "
             "archetype's empirical targets in the master table. This is the bridge between *agents "
             "playing hands* and *the aggregate fields our scoring engine consumes*.")
    L.append("4. **Integrity behaviors are layered policies.** `cluster_member` needs member-set "
             "awareness (soft vs members → negative `soft_play_delta`; coordinated table selection → "
             "high co-seating; gang up on outsiders). `shared_device_household` = two INDEPENDENT "
             "sub-agents sharing a `device_group_id` with divergent schedules and **no** soft-play. "
             "`bot_like` = deterministic policy with near-zero action-timing jitter.")
    L.append("5. **Determinism.** Seed every agent and the dealer so a run is reproducible — matches the "
             "lab's existing seeded-fixture ethos. The agents' hand histories aggregate back into the "
             "same player features (vpip/pfr/AF/…), keeping **Contract-1 compatibility** with the "
             "current static generator while adding real gameplay underneath.")
    L.append("")
    L.append("## Grounded vs. invented")
    L.append("")
    L.append("- **Grounded in the fixture** (targets the agent must hit): vpip, pfr, aggression factor, "
             "avg pot size, session length/frequency, lifetime volume, promo rate, `soft_play_delta`, "
             "`timing_regularity`, plus the relationship structure (clusters/households/co-seating) in "
             "`data/relationships.json`.")
    L.append("- **The designer must invent** (the data gives aggregate targets, not strategy): concrete "
             "preflop hand ranges, postflop decision trees, bet-sizing distributions, bluff frequencies, "
             "position/stack awareness, the equity model, tilt dynamics, and the exact mechanics of "
             "soft-play and outsider-targeting. Use the knobs above as the calibration targets.")
    L.append("")
    L.append("---")
    L.append("")
    L.append("**Related:** `docs/scoring-thresholds.md` §1 (the classifier thresholds these profiles "
             "feed), `data/players.json` meta (field glossary), `data/relationships.json` (cluster / "
             "household / co-seating structure), `CLAUDE.md` (hard rules + non-goals).")
    L.append("")

    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(df)} players, {len(ORDER)} archetypes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
