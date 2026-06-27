# Handoff — Monday demo: one room, two surfaces (lobby + dashboard)

**Date:** 2026-06-26 (Fri)
**From:** Cory (lobby) + Claude
**For:** Sargon (playsim + dashboard)
**Re:** keeping the lobby (demo Part 2) and the dashboard (demo Part 3) coherent for Monday.

---

## TL;DR

The lobby and your dashboard should be **derived from the same room-sim run** (same
seed, arrival rate, fixture). One world, two surfaces. I need one thing from you: which
run/seed/arrival-rate the dashboard uses, and where the large-room fixture lives — then I
point the lobby pipeline at it.

## 1. The shared-world principle

The demo is one story: *Standard concentrates players; FairPlay routes toward healthy
tables; here's the room, and here's how it plays out.* That only holds if the **lobby**
(Part 2, side-by-side Standard vs FairPlay + churn) and the **dashboard** (Part 3,
seat-time over a session) come from the *same* simulated room. Different runs = two
unrelated datasets on screen.

## 2. What I need from you (the ask)

- **Seed + arrival rate** the dashboard is built on (e.g. seed 42, rate 20 and/or 40).
- **Where the large-room fixture data-root is** (e.g. `playsim/out/large-room-data` from
  `large-room-fixture`), or the command/seed to regenerate it deterministically.
- **A representative vulnerable seeking player id** in that fixture (a `new` /
  `recreational` archetype) — the lobby shows FairPlay protecting *that* player. (Today
  it defaults to `P-104`, which only exists in the small room.)

Once I have those, the lobby is a one-line repoint (no code change):
```bash
python backend/scripts/build_lobby_sequence.py \
  --data-root playsim/out/large-room-data \
  --player <vulnerable-id> --steps 4 --stand 10 --sit 6 --seed <seed>
```

## 3. The lobby pipeline's data contract

`backend/scripts/build_lobby_sequence.py` reads, from `--data-root`:

| File | Used for | In the large-room fixture? |
|---|---|---|
| `players.json` | archetypes + integrity fields (router scoring) | ✅ yes |
| `table_roster.json` | tables: `seated_player_ids`, occupancy, stakes, `avg_pot_size_usd`, `hands_per_hour` | ✅ yes |
| `relationships.json` | clusters/households (integrity) | ✅ yes (empty graph, fine) |
| `sessions.json` | `P_bleed` health term | ⚠️ optional — pipeline runs fine without it (treats as none) |

It then runs the **real scoring router** (`route()` + `score_integrity` + `score_all_tables`)
across seeded churn steps → player-safe `data/derived/lobby_sequence.json` (the same
tables, ordered Standard vs FairPlay, re-ranked as the room churns).

**One integration risk to confirm:** that `route()`/health/integrity run cleanly on the
large-room fixture shapes (the room-sim already routes via `router_adapter`, so this
should just work — but worth a 5-min check when we repoint). If a field is missing, it's
a small adapter tweak, not a redesign.

## 4. Dashboard scope (Part 3) — so we build to the same target

From the demo storyboard, the dashboard shows (you own this):
- **Standard vs FairPlay** at **20 & 40** arrival rates,
- **total paid seat-time** over the session (8h or 24h),
- **saturation / full-table rate** (the capacity KPI — derive from active/empty/forming
  table counts; the sweep emits those),
- **hands played**, plus anything else that reads well,
- a closing line on **when FairPlay outperforms and when it doesn't** (the honest
  regime-dependence from `playsim-fairplay-retention-diagnostics-results.md`).

The numbers already exist in the sweep we ran (`out/sweep-diag.json`) — reuse or rerun
`large-room-sweep` as you prefer.

## 5. Status of the lobby (so you know what's done)

- Built + pushed on `feat/demo-lobby-shuffle`: poker-style side-by-side lobby + churn
  stepper, driven by the **real router** (12-table roster for now). `tsc`/`vite build`
  green. Viewable on the worktree dev server.
- Saturday: repoint to your large-room run (this doc), styling polish, optional seat panel.

## Related
- `docs/brainstorms/2026-06-26-lobby-shuffle-demo-prd.md` — the lobby PRD.
- `docs/learn/playsim-fairplay-retention-diagnostics-results.md` — the regime-dependence result.
- `backend/scripts/build_lobby_sequence.py` — the pipeline to repoint.
