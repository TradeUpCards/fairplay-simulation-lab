# Playsim model limitation: no table formation / growth — and why it biases Standard vs FairPlay

**Date:** 2026-06-25
**Audience:** playsim owners (P2b/P2c) + anyone quoting the room-routing findings
**Status:** open limitation / proposed model fix — *not* a defect report; it builds on
the honest findings in `docs/learn/playsim-room-routing-findings.md`.
**Source code:** `playsim/playsim/room.py`

---

## TL;DR

The room simulator can only **drain**: tables are a fixed roster, pre-filled at
start, and they can **shrink and break but never form or grow from short-handed**.
Combined with finite one-shot arrivals, room liquidity decreases monotonically over
the horizon. This **structurally favors concentration (Standard / most-full)** and
**denies health-routing (FairPlay) its natural real-world mechanism** — seating a
vulnerable player at a *fresh, forming* table away from predators and letting it grow
healthy. So the documented "Standard beats FairPlay, and the gap grows by 8h" result
is *partly an artifact of the missing formation dynamic*, not only a property of the
routing policy.

This is arguably a **more fundamental gap than calibration or the metric**: it's not
that the retention numbers are uncalibrated (they are), it's that the model cannot
*represent* the dynamic by which full healthy tables come to exist in a real room.

---

## What the code does (evidence)

- **Fixed table set, created once.** `self.tables` is loaded from the table roster at
  init (`room.py:183-186`). No table is created during the run; the count only ever
  goes down (breaks).
- **Full tables are inherited, never produced.** They exist only because the fixture
  seeds them ~95% full at hour 0. The sim never grows a short-handed table into a full
  one.
- **A break is permanent shrinkage.** `active (dealable) = seated >= 2`
  (`room.py:570, 585`); below 2 the table can't deal, breaks, and its occupants are
  displaced. There is no short-handed "forming/playable" state and no re-open.
- **Displaced players are *refused* an empty table.** On a break re-seek
  (`require_pair=True`), if the chosen table has `< 1` seated it is rejected as
  `"no_dealable_seat"` and the player **balks** (`room.py:355-357`). So a displaced
  player cannot go start a fresh table.
- **The one partial exception doesn't create real formation.** A *normal* arrival can
  technically be seated at an empty table — but a lone player **isn't dealt to**
  (needs ≥2), accrues **no seat-time**, and nothing grows that table toward full.
  And `StandardPolicy` picks the **most-full** open table, so it effectively never
  seeds an empty one until everything else is full.

Net: the only way to have dealable tables is to keep the pre-seeded ones alive →
concentration is rewarded by construction; scattering is punished with no recovery
path.

---

## Why it matters

1. **One-way drain.** Finite one-shot arrivals + attrition + no table regeneration ⇒
   liquidity can only degrade. The longer the run, the more "keep surviving tables
   alive" dominates — which is exactly the mechanism by which Standard's lead *grows*
   from ~tie at 4h to ahead at 8h. Some of that horizon effect is the missing
   formation dynamic, not a real degradation of routing.
2. **FairPlay is denied its mechanism.** Real-room harm reduction works by *forming /
   growing a healthy table* for the vulnerable player. Here there is no forming table
   to route them to, and routing a fish to a "healthy" *empty* table just parks them
   at a non-dealing seat. Health-routing's upside cannot express.
3. **Interpretation caveat for the headline.** "Standard beats FairPlay because of
   table-liveness/churn" is correct *within this model* — but the model makes table
   liveness a one-way ratchet. A model that can reform liquidity might rank the
   policies differently. This belongs next to the existing throughput-metric and
   calibration caveats.

---

## Proposed fixes (in rough order of leverage)

1. **Table formation / short-handed growth (the big one).** Let a short-handed table
   be a first-class *forming* state — dealable at a lower quorum, or held briefly as
   "waiting to fill" — and let policies intentionally *seed and grow* a fresh table
   toward full. This is what lets FairPlay route a vulnerable player to a new healthy
   table that then grows.
2. **Continuous arrivals** instead of one-shot. So the room refills and liquidity
   regenerates over the horizon instead of monotonically draining. Removes the
   artificial "8h collapse."
3. **Liveness-aware routing** (already on Sargon's list): a quorum/liquidity term in
   the rank so FairPlay prefers healthy tables that *stay alive*, rather than
   scattering naively.

(1) and (2) are the ones that change *what the model can represent*; (3) is a policy
tweak inside the current representation.

---

## Implementation status: instrumentation, arrivals, and forming mode

The first implementation is now a controlled room-sim variation, not just a note:

- **No new synthetic players.** Continuous arrivals draw from the existing unseated
  fixture pool without replacement.
- **Continuous arrivals are supported.** The same seeded arrival stream is generated
  once per seed and injected into every policy arm, preserving the A/B invariant.
- **Forming tables are supported behind a flag.** With `--formation-mode forming`,
  a seeker can seed an empty table. The table state becomes `forming`; it does not
  deal hands or accrue paid seat-time until a second player joins and the table
  becomes `active`.
- **Default behavior remains conservative.** `--formation-mode none` is the default.
  It preserves the prior headline behavior and keeps this as an explicit experiment,
  not a silent change to the routing result.
- **Continuation propensity is not modeled yet.** Players still use reason-based
  re-seek + wait tolerance, not a decaying willingness-to-continue score. That means
  repeated failed formation attempts are not yet accumulated as frustration/fatigue.

This deliberately does **not** prove FairPlay improves. It gives us a way to test
whether the missing formation dynamic materially changes the Standard-vs-FairPlay
comparison.

### New controls

```bash
.venv/bin/python -m playsim.cli room-sim \
  --arrival-mode fixture-once \
  --formation-mode none \
  --seeds 42,7,99 --horizon 480 --out-dir out

.venv/bin/python -m playsim.cli room-sim \
  --arrival-mode fixture-once \
  --formation-mode forming \
  --seeds 42,7,99 --horizon 480 --out-dir out

.venv/bin/python -m playsim.cli room-sim \
  --arrival-mode continuous --arrival-rate-per-hour 8 \
  --formation-mode forming \
  --seeds 42,7,99 --horizon 480 --out-dir out
```

This now supports the implementation side of the 2x2:

| | no explicit forming | forming enabled |
|---|---|---|
| fixture-once arrivals | supported | supported |
| continuous arrivals | supported | supported |

### New summary metrics

New fields in `room_sim_*.json`:

- `no_good_existing_seat_count` — routing attempts where no currently active open
  table existed (`>=2` seated with an open seat).
- `empty_table_available_count` — attempts where an empty table was available.
- `sub_quorum_table_available_count` — attempts where a one-player, non-dealing
  table was available.
- `break_to_reseat_success` — break-displaced players who successfully re-seated.
- `break_to_wait_balk` — table-break waiters who timed out.
- `table_reactivation_count` — broken tables that later returned to dealable state.
- `forming_seat_count` — runtime seats that left a table in `forming` state.
- `formation_activation_count` — times a forming table reached active/dealing quorum.

### Design caveats

- **A forming seat is not paid seat-time.** Seat-time accrues only while hands are
  dealt at tables with at least two players.
- **Health scoring still penalizes short-handed active tables.** Under current
  health scoring, clean 2/6 and 3/6 tables top out around 80 and 85 because
  `P_frag` penalizes low occupancy. To model intentional short-handed poker well,
  the next scoring question is whether fragility should consider `target_seats` /
  table mode, not only `seated_count / max_seats`.
- **Continuation propensity may buy us realism later.** It is useful once forming
  tables exist because repeated waits/breaks should reduce a player's willingness
  to keep trying. It is not required to test whether formation changes the table
  liveness result, but it is likely needed before claiming behavioral fidelity.

The next analysis should compare:

```text
fixture-once + formation none
fixture-once + formation forming
continuous + formation none
continuous + formation forming
```

and report both paid seat-hours and formation mechanics (`forming_seat_count`,
`formation_activation_count`, breaks, wait-balks).

---

## Suggested experiment to quantify the impact

Minimal version: add a rule that a player may *open* a new table (or grow a
short-handed one) when no dealable healthy seat exists, and/or switch arrivals to a
continuous Poisson stream. Re-run `room-sim --seed 42 --horizon 480` for both
behaviors and compare the Standard-vs-FairPlay paid-seat-time gap and breaks against
the current baseline (Standard ahead ~13–14% at 8h, FairPlay breaks ~38–40 vs 23).
**Hypothesis:** with formation enabled, the gap narrows materially or flips, because
scattering stops being a one-way liquidity loss.

---

## Related

- Primary findings (what we found and why): `docs/learn/playsim-room-routing-findings.md`
- Why the numbers stay illustrative: `docs/learn/playsim-calibration-data.md`
- Behavioral model spec: `docs/brainstorms/2026-06-24-behavioral-fidelity-fit-model-requirements.md`
