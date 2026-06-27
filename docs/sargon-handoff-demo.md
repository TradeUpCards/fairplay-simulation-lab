# Handoff — Monday demo: one room, two surfaces (lobby + dashboard)

**Date:** 2026-06-26 (Fri)
**From:** Cory (lobby) + Claude
**For:** Sargon (playsim + dashboard)

---

## TL;DR

The lobby (demo Part 2) is built and **already runs on the large-room playsim fixture
(`playsim/out/large-room-data`, seed 42)** — 50 tables, real router orderings,
Standard vs FairPlay + churn. The fixture is deterministic, so if your dashboard uses the
**same seed-42 large-room fixture**, the lobby and dashboard are already one world.

**One thing to confirm:** are you on the default seed-42 large-room fixture (same arrival
rate family, 20/40)? If yes, we're aligned and there's nothing to hand off. If you regen
with a different seed, tell me the seed and I repoint the lobby (one CLI flag).

## Dashboard scope (Part 3) — what I'm assuming you own

- Standard vs FairPlay at **20 & 40** arrival rates,
- **total paid seat-time** over the session,
- **saturation / full-table rate** (derive from active/empty/forming counts the sweep emits),
- **hands played**, plus anything that reads well,
- a closing line on **when FairPlay outperforms and when it doesn't** (regime-dependence
  from `playsim-fairplay-retention-diagnostics-results.md`).

Numbers already exist in `out/sweep-diag.json` (Standard/FairPlay × rates 10–40) — reuse
or rerun `large-room-sweep`.

## Lobby status (so you know it's done)

- `feat/demo-lobby-shuffle`: poker-style side-by-side Standard|FairPlay + churn stepper,
  driven by the **real router** on the seed-42 large-room fixture. `tsc`/`vite build` green.
- Repoint to a different seed (if needed):
  ```bash
  python backend/scripts/build_lobby_sequence.py \
    --data-root playsim/out/large-room-data --player P-10001 --stand 10 --sit 6
  ```

## Related
- `docs/brainstorms/2026-06-26-lobby-shuffle-demo-prd.md` — lobby PRD.
- `docs/learn/playsim-fairplay-retention-diagnostics-results.md` — the regime result.
