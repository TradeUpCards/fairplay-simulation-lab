# Archetype Play Profiles — agent spec for simulating poker play

> **Purpose.** A behavioral spec for agents that **actually play hands**, one per player archetype, so a simulation can produce realistic table dynamics. Each archetype's **stat distribution is computed from the real 122-player fixture** (`data/players.json`); the **play-policy translation is the design layer** — how an agent should act to land on those stats.
>
> **Responsible-use framing.** This is for the FairPlay **integrity-detection simulation lab** — synthetic agents in a sandbox, generating table dynamics so the detector can be tested. Simulating the predatory / collusion / bot archetypes exists so the system learns to *flag* them. It is **not** a tool for real-money play, RTA, actual collusion, or enforcement (see `CLAUDE.md` non-goals).
>
> Regenerate: `python scripts/build_archetype_profiles.py`

---

## How to read a stat as a play policy

The fixture defines archetypes by **aggregate stats**, not strategy. To drive a hand-playing agent, map each stat onto a decision knob:

| Stat | Meaning | Agent knob |
|---|---|---|
| `vpip` | % of hands voluntarily played | **preflop looseness** — entering range width (vpip .38 ≈ play ~38% of starting hands) |
| `pfr` | % of hands raised preflop | **preflop aggression** — raise-first frequency. `vpip − pfr` = limp/call gap (passivity) |
| `aggression_factor` | (bets+raises)/calls postflop | **postflop aggression** — AF 4.3 = barrels/bluffs; AF < 1 = calling station |
| `avg_pot_size_bb` | mean pot when involved | **bet sizing / stakes** — pot-building tendency |
| `avg_session_minutes` · `sessions_last_30d` | session length / frequency | **stamina, stop-loss, schedule** — when the agent sits and quits |
| `lifetime_hands` | total volume | **experience / skill proxy** |
| `promo_redemptions_30d` | bonus redemptions | **promo-chasing trigger** (promo_hunter) |
| `soft_play_delta` | EV given up vs cluster members | **collusion soft-play** — negative = chip-dump / fold to teammate (cluster_member) |
| `timing_regularity` | action-timing consistency | **timing jitter** — ~1.0 = robotic, no human variance (bot_like) |

---

## Master table (medians, computed)

| archetype | n | vpip | pfr | AF | pot(bb) | session(min) | sessions/30d | integrity tell |
|---|--:|--:|--:|--:|--:|--:|--:|---|
| **new** | 8 | 0.36 | 0.08 | 0.89 | 8 | 20 | 4 | — |
| **recreational** | 34 | 0.38 | 0.12 | 1.18 | 11 | 73 | 9 | — |
| **regular** | 22 | 0.28 | 0.22 | 2.06 | 19 | 135 | 16 | — |
| **grinder** | 12 | 0.23 | 0.21 | 2.69 | 27 | 325 | 25 | — |
| **aggressive_predatory** | 8 | 0.59 | 0.45 | 4.30 | 43 | 251 | 20 | — |
| **promo_hunter** | 8 | 0.30 | 0.13 | 1.10 | 10 | 39 | 20 | 13.5 promo/30d |
| **healthy_anchor** | 18 | 0.28 | 0.18 | 1.88 | 18 | 209 | 20 | — |
| **shared_device_household** | 6 | 0.33 | 0.16 | 1.55 | 15 | 119 | 12 | shared device, divergent play |
| **cluster_member** | 5 | 0.30 | 0.23 | 2.15 | 20 | 178 | 21 | soft_play ≤ −0.60 |
| **bot_like** | 1 | 0.24 | 0.20 | 2.05 | 20 | 182 | 28 | timing_reg ≈ 0.88 |

---

## Per-archetype agent profiles

### new  ·  *Brand-new, tentative, loose-passive — busts or logs off fast.*
<sub>n = 8 players in the fixture</sub>

**Stats (median [range]):** `vpip` 0.36 _[0.30–0.44]_ · `pfr` 0.08 _[0.06–0.11]_ · `aggression factor` 0.89 _[0.72–1.05]_ · `avg pot (bb)` 7.65 _[5.80–9.10]_ · `session (min)` 20.50 _[15.00–26.00]_ · `sessions/30d` 4.50 _[2.00–6.00]_ · `lifetime hands` 29.50 _[9.00–58.00]_ · `promo/30d` 0.00 _[0.00–1.00]_

- **Style:** Plays lots of hands out of curiosity but almost never the aggressor (pfr .08); passive postflop (AF < 1 = calls far more than it bets). Tiny pots, ~20-min sessions, churns quickly — especially at a tough table (CASE-A: 12 min then exit).
- **Preflop:** Enter ~36% of hands, but raise-first-in only ~8% — mostly open-limp / cold-call. No 3-betting.
- **Postflop:** Calling station: chases draws, calls down light, rarely bets or raises. Makes -EV calls (low skill).
- **Sizing:** Min-bets and flat-calls; never builds a pot (~8bb).
- **Session / stamina:** 15–26 min, 2–6 sessions/mo. Logs off on a loss or after a short stretch — model a low stop-loss / low stamina.
- **Agent knobs:** looseness HIGH · aggression VERY LOW · skill LOW · stamina VERY LOW · tilt-to-quit HIGH

### recreational  ·  *The casual fish — loosest range, still passive. The cohort to protect.*
<sub>n = 34 players in the fixture</sub>

**Stats (median [range]):** `vpip` 0.38 _[0.28–0.45]_ · `pfr` 0.12 _[0.09–0.19]_ · `aggression factor` 1.18 _[0.85–1.60]_ · `avg pot (bb)` 10.80 _[8.00–16.00]_ · `session (min)` 73.00 _[48.00–110]_ · `sessions/30d` 9.00 _[6.00–14.00]_ · `lifetime hands` 600 _[215–4,500]_ · `promo/30d` 2.00 _[0.00–4.00]_

- **Style:** Widest vpip (.38) but low aggression (pfr .12, AF ~1.2). Plays for fun; medium sessions; calls too much.
- **Preflop:** Enter ~38% (widest), raise ~12%, lots of limp/call. Defends blinds too wide.
- **Postflop:** Slightly aggressive on made hands, otherwise call-happy; chases draws and pays off value.
- **Sizing:** Small–medium pots (~11bb).
- **Session / stamina:** ~73 min, ~9 sessions/mo.
- **Agent knobs:** looseness HIGHEST · aggression LOW · skill LOW–MED · stamina MED · loss-aversion LOW (plays through losses)

### regular  ·  *Solid TAG — tight, aggressive, competent.*
<sub>n = 22 players in the fixture</sub>

**Stats (median [range]):** `vpip` 0.28 _[0.22–0.35]_ · `pfr` 0.22 _[0.16–0.27]_ · `aggression factor` 2.06 _[1.60–2.42]_ · `avg pot (bb)` 18.90 _[14.20–23.20]_ · `session (min)` 135 _[95.00–180]_ · `sessions/30d` 16.00 _[12.00–21.00]_ · `lifetime hands` 7,850 _[1,900–16,400]_ · `promo/30d` 1.00 _[0.00–2.00]_

- **Style:** Tighter (.28), raises most hands it plays (small vpip–pfr gap → few limps), genuinely aggressive postflop (AF 2.06).
- **Preflop:** ~28% range, raise-first ~22% (mostly raise-or-fold), few limps; will 3-bet.
- **Postflop:** Balanced aggression — c-bets, value-bets, occasional bluff; folds to real pressure.
- **Sizing:** Standard ~19bb pots.
- **Session / stamina:** ~135 min, ~16 sessions/mo.
- **Agent knobs:** looseness MED–LOW · aggression MED–HIGH · skill MED–HIGH · stamina MED

### grinder  ·  *High-volume professional — tight, relentless, marathon sessions.*
<sub>n = 12 players in the fixture</sub>

**Stats (median [range]):** `vpip` 0.23 _[0.20–0.26]_ · `pfr` 0.21 _[0.19–0.22]_ · `aggression factor` 2.69 _[2.50–3.00]_ · `avg pot (bb)` 26.90 _[23.80–32.00]_ · `session (min)` 325 _[260–420]_ · `sessions/30d` 25.00 _[21.00–28.00]_ · `lifetime hands` 190,000 _[75,000–580,000]_ · `promo/30d` 0.00 _[0.00–0.00]_

- **Style:** Tight (.23), virtually never limps (vpip–pfr gap ~.02 = raise-or-fold), strong postflop aggression (2.69). 5+ hour sessions, 25/mo, enormous lifetime volume. A table-HEALTH concern (CASE-B), NOT integrity.
- **Preflop:** ~23% tight range, raise-first ~21%, essentially zero limps; positional 3-bets.
- **Postflop:** Multi-street barreling, thin value, balanced bluffs; exploits weak opponents.
- **Sizing:** Bigger pots (~27bb), plays higher stakes.
- **Session / stamina:** 260–420 min, 21–28 sessions/mo — near-daily long grinds.
- **Agent knobs:** looseness LOW · aggression HIGH · skill HIGH · stamina VERY HIGH · exploit-weak ON

### aggressive_predatory  ·  *Hyper-LAG table-killer — the predation pressure new/rec players feel.*
<sub>n = 8 players in the fixture</sub>

**Stats (median [range]):** `vpip` 0.59 _[0.54–0.65]_ · `pfr` 0.45 _[0.40–0.50]_ · `aggression factor` 4.30 _[3.85–4.85]_ · `avg pot (bb)` 43.25 _[38.50–52.00]_ · `session (min)` 251 _[195–300]_ · `sessions/30d` 20.50 _[17.00–23.00]_ · `lifetime hands` 106,500 _[52,000–185,000]_ · `promo/30d` 0.00 _[0.00–1.00]_

- **Style:** Very loose (.59) AND very aggressive (pfr .45, AF 4.3 — bets/raises ~4× as often as it calls). Big pots (43bb). Makes weak players bust fast. NOT cheating — a dangerous skilled aggressor (CASE-A aggressors P-176/177).
- **Preflop:** Enter ~59%, raise-first ~45% — relentless isolation/3-betting, attacks limpers and blinds.
- **Postflop:** Maximal aggression: barrels, bluffs, applies constant pressure; targets the weakest player at the table.
- **Sizing:** Large pots and oversized bets to pressure (~43bb).
- **Session / stamina:** ~250 min, ~20 sessions/mo — hunts soft tables.
- **Agent knobs:** looseness HIGH · aggression MAXED · skill HIGH · target-weak-players ON · bluff-freq HIGH

### promo_hunter  ·  *Bonus-clearer — minimal-risk volume to clear promos (13.5/mo tell).*
<sub>n = 8 players in the fixture</sub>

**Stats (median [range]):** `vpip` 0.30 _[0.27–0.34]_ · `pfr` 0.13 _[0.11–0.15]_ · `aggression factor` 1.10 _[1.02–1.18]_ · `avg pot (bb)` 10.35 _[9.20–12.20]_ · `session (min)` 39.00 _[30.00–55.00]_ · `sessions/30d` 20.00 _[16.00–22.00]_ · `lifetime hands` 2,450 _[980–5,800]_ · `promo/30d` 13.50 _[8.00–21.00]_

- **Style:** Plays low-variance to grind rake/bonus requirements. Short frequent sessions (39 min × 20/mo), low aggression, small pots; the giveaway is 13.5 promo redemptions/mo. A health/economics concern (CASE-F), NOT collusion.
- **Preflop:** ~30% range but the OBJECTIVE is hands-volume to clear the bonus, not winning; low raise (~13%).
- **Postflop:** Passive and risk-averse — avoid variance, fold to aggression, protect the bonus EV.
- **Sizing:** Small pots (~10bb); declines marginal +EV spots that add variance.
- **Session / stamina:** Many short sessions timed to promo availability; stops when the requirement clears.
- **Agent knobs:** aggression LOW · risk-aversion HIGH · session-trigger = promo-available · hands-volume TARGET · stakes LOW

### healthy_anchor  ·  *The good stabilizing regular — solid, friendly, sticks around. NON-predatory.*
<sub>n = 18 players in the fixture</sub>

**Stats (median [range]):** `vpip` 0.28 _[0.22–0.32]_ · `pfr` 0.18 _[0.17–0.20]_ · `aggression factor` 1.88 _[1.72–2.00]_ · `avg pot (bb)` 17.50 _[15.80–19.00]_ · `session (min)` 209 _[162–315]_ · `sessions/30d` 19.50 _[16.00–26.00]_ · `lifetime hands` 33,500 _[12,000–108,000]_ · `promo/30d` 0.00 _[0.00–1.00]_

- **Style:** Tight-ish (.28), moderate aggression (1.88 — below grinder/regular), long friendly sessions (209 min), high frequency. Keeps tables alive without crushing recreationals.
- **Preflop:** ~28% range, raise ~18%; straightforward, not a maniac.
- **Postflop:** Moderate, honest aggression; value-heavy, light on bluffs; does NOT hunt the weakest player.
- **Sizing:** Standard ~17bb pots.
- **Session / stamina:** 162–315 min, ~20 sessions/mo — a reliable presence.
- **Agent knobs:** looseness MED–LOW · aggression MED · skill MED · stamina HIGH · target-weak OFF (stabilizer, not predator)

### shared_device_household  ·  *Two people, one device, DIFFERENT styles — the false-positive trap.*
<sub>n = 6 players in the fixture</sub>

**Stats (median [range]):** `vpip` 0.33 _[0.24–0.42]_ · `pfr` 0.16 _[0.11–0.22]_ · `aggression factor` 1.55 _[1.05–2.12]_ · `avg pot (bb)` 14.75 _[10.50–20.00]_ · `session (min)` 119 _[72.00–162]_ · `sessions/30d` 12.50 _[10.00–15.00]_ · `lifetime hands` 7,150 _[2,800–11,000]_ · `promo/30d` 2.00 _[0.00–5.00]_

- **Style:** Each account plays like an ordinary recreational/regular, but the load-bearing simulation property is TWO accounts on one device_group that are behaviorally INDEPENDENT: divergent schedules (e.g. one evenings ~145 min, one mornings ~110 min), different vpip/pfr, and LOW co-seating — they do NOT play together. Benign — monitor, never escalate (CASE-E).
- **Preflop:** Per-account, like a recreational/regular blend — but distinct between the two accounts.
- **Postflop:** Ordinary; crucially NO soft-play between the two (soft_play_delta = 0).
- **Sizing:** Normal for their level (~15bb).
- **Session / stamina:** The two accounts deliberately occupy DIFFERENT time windows and rarely share a table.
- **Agent knobs:** model as TWO independent sub-agents · shared device_group_id · DIVERGENT schedule+style params · co_seating LOW · soft_play OFF

### cluster_member  ·  *Coordinated collusion ring — soft vs each other, hard on outsiders.*
<sub>n = 5 players in the fixture</sub>

**Stats (median [range]):** `vpip` 0.30 _[0.28–0.33]_ · `pfr` 0.23 _[0.21–0.25]_ · `aggression factor` 2.15 _[1.98–2.28]_ · `avg pot (bb)` 20.20 _[18.80–22.50]_ · `session (min)` 178 _[145–195]_ · `sessions/30d` 21.00 _[17.00–23.00]_ · `lifetime hands` 24,500 _[12,500–31,000]_ · `promo/30d` 0.00 _[0.00–1.00]_ · `soft_play_delta` -0.75 _[-0.82–-0.30]_

- **Style:** Competent regulars (.30/.23/2.15) whose DEFINING behavior is coordination: they sit together (high co-seating), play SOFT against each other (soft_play_delta ≤ −0.60 → give up EV / chip-dump in member-vs-member pots), gang up on non-members, and have correlated action timing. The true-positive integrity case (CASE-C).
- **Preflop:** Vs outsiders: aggressive isolation and squeezing. Vs members: avoid raising into each other; fold marginal spots to a teammate.
- **Postflop:** Vs outsiders: apply coordinated pressure (whipsaw/squeeze). Vs members: check down, don't barrel each other, chip-dump on demand (the soft-play signal).
- **Sizing:** Normal vs outsiders; suppressed / value-giving vs members.
- **Session / stamina:** Coordinated table selection — members converge on the same tables (high co-seating rate).
- **Agent knobs:** MEMBER-SET awareness REQUIRED · soft_play toggle (cut aggression+EV vs members) · co-seat preference HIGH · outsider-targeting ON · timing-correlation across members

### bot_like  ·  *A bot — mechanically consistent, no human timing variance.*
<sub>n = 1 players in the fixture</sub>

**Stats (median [range]):** `vpip` 0.24 _[0.24–0.24]_ · `pfr` 0.20 _[0.20–0.20]_ · `aggression factor` 2.05 _[2.05–2.05]_ · `avg pot (bb)` 19.50 _[19.50–19.50]_ · `session (min)` 182 _[182–182]_ · `sessions/30d` 28.00 _[28.00–28.00]_ · `lifetime hands` 8,500 _[8,500–8,500]_ · `promo/30d` 0.00 _[0.00–0.00]_ · `timing_regularity` 0.88 · `bot_similarity` 0.87

- **Style:** Reasonable stats, but the tell is timing_regularity .88 (near-uniform action timing) + very high session frequency (28/mo, robotic schedule). Plays a fixed rule-based / GTO-ish policy with no tilt and no variance. Own review queue (CASE-G), separate from collusion.
- **Preflop:** Consistent, unemotional fixed ranges; identical decisions in identical spots.
- **Postflop:** Deterministic policy; same sizing every time; no timing tells, no tilt, no fatigue.
- **Sizing:** Uniform, rule-based (~20bb).
- **Session / stamina:** Robotic cadence and near-24/7 availability; action latency has very low jitter (the detection signal).
- **Agent knobs:** DETERMINISTIC policy · action-timing JITTER ≈ 0 · tilt OFF · fatigue OFF · availability ~24/7

---

## Suggested agent-harness design (agents that play hands)

1. **One parameterized policy, ten knob-sets.** Build a single decision policy and instantiate each archetype as a vector of knobs: `{looseness, preflop_aggression, postflop_aggression, sizing, skill, stamina, risk_aversion}` plus integrity flags `{soft_play_members, target_weak, timing_jitter, promo_trigger}`. The tables above give the target value for each.
2. **Decision engine.** Per street: estimate hand strength / equity vs a range model, then let the knobs bias the thresholds — looseness lowers the equity needed to enter; aggression converts marginal calls into bets/raises; sizing sets bet amounts. Position and stack depth modulate.
3. **Calibration loop (closes play ↔ stats).** Run each agent over many seeded hands, measure its *realized* vpip / pfr / AF / pot size, and tune the knobs until they match the archetype's empirical targets in the master table. This is the bridge between *agents playing hands* and *the aggregate fields our scoring engine consumes*.
4. **Integrity behaviors are layered policies.** `cluster_member` needs member-set awareness (soft vs members → negative `soft_play_delta`; coordinated table selection → high co-seating; gang up on outsiders). `shared_device_household` = two INDEPENDENT sub-agents sharing a `device_group_id` with divergent schedules and **no** soft-play. `bot_like` = deterministic policy with near-zero action-timing jitter.
5. **Determinism.** Seed every agent and the dealer so a run is reproducible — matches the lab's existing seeded-fixture ethos. The agents' hand histories aggregate back into the same player features (vpip/pfr/AF/…), keeping **Contract-1 compatibility** with the current static generator while adding real gameplay underneath.

## Grounded vs. invented

- **Grounded in the fixture** (targets the agent must hit): vpip, pfr, aggression factor, avg pot size, session length/frequency, lifetime volume, promo rate, `soft_play_delta`, `timing_regularity`, plus the relationship structure (clusters/households/co-seating) in `data/relationships.json`.
- **The designer must invent** (the data gives aggregate targets, not strategy): concrete preflop hand ranges, postflop decision trees, bet-sizing distributions, bluff frequencies, position/stack awareness, the equity model, tilt dynamics, and the exact mechanics of soft-play and outsider-targeting. Use the knobs above as the calibration targets.

---

**Related:** `docs/scoring-thresholds.md` §1 (the classifier thresholds these profiles feed), `data/players.json` meta (field glossary), `data/relationships.json` (cluster / household / co-seating structure), `CLAUDE.md` (hard rules + non-goals).
