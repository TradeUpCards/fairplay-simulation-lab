# PRD — Poker-style lobby + "shuffle" re-rank (demo moment)

**Date:** 2026-06-26 (Fri)
**For:** Cory + Claude (build). Pairs with Sargon's dashboard (separate piece).
**Status:** draft for review. Build window: **Sat 6/27**; rehearse Sun 6/28; **demo Mon 6/29**.
**Demo beat it serves:** Part 2 of the demo — "Show Standard vs FairPlay lobby; the
table sort is driven by different rank orders; click a button → players churn → lobby
re-ranks into a different order."

---

## 1. Goal (one sentence)

Make the lobby look like a real poker-site cash-game lobby (a sortable data table), and
let the presenter **flip between Standard and FairPlay ordering** and **trigger a room
churn** so the audience *sees* the same room rank differently — without ever exposing a
score (the player/operator wall stays intact).

## 1b. Visual reference (Cory's screenshots, 2026-06-26)

Three reference shots provided:
- `OneDrive/Pictures/Screenshots/Screenshot 2026-06-26 211825.png` — **PokerOK**: dark
  red/black dense data-table, per-row Open/Join, table preview on the right, game tabs.
- `OneDrive/Pictures/Screenshots/Screenshot 2026-06-26 212034.png` — **GGPoker**: dark
  green/black, columns Game · Stakes · Buy-in · Players · Tables · Hands/hr · green Join.
- `OneDrive/Pictures/Screenshots/Screenshot 2026-06-26 212729.png` — **WSOP**: the
  clearest rows/columns layout — Table · Type · Limit · Stakes · Plrs · Avg pot ·
  Plrs/Flop% · Hnds/Hr, a highlighted selected row, and a right-side **Table details**
  panel (seat list + Join / Waiting list), plus stake filters and a legend.

**Chosen direction:** dark theme (GG/PokerOK — matches our existing brass/dark UI), with
the **WSOP column set and the right-side table-details panel**. Game-type tabs / stake
filters / legend are decorative chrome (static is fine).

## 2. Why

- The current lobby is a 3-column **card grid** (`PlayerLobby.tsx` → `TableTile`). It
  doesn't read as a real poker lobby, and it shows only one ordering.
- The demo's whole Part-2 point is the **difference in ordering** between the two
  policies, made tangible by live churn. A tabular lobby + a sort toggle + a shuffle
  button delivers exactly that.

## 3. Scope (ruthless — one build day)

**Locked decisions (2026-06-26):** side-by-side Standard | FairPlay (not a toggle); the
poker-table view becomes the **default**, with the existing **card grid kept as an
optional alternate view** (a Table | Cards switch; cards likely better on mobile);
seat-details panel **included as a stretch**.

**IN:**
1. Tabular lobby (rows/columns) styled like a poker site — the **default** view. The
   existing card grid stays as an **optional alternate** (Table | Cards switch; the card
   view is the responsive/mobile-friendly layout). Nothing deleted → lower risk.
2. **Side-by-side** Standard | FairPlay lobbies: the *same* rooms shown in both orders at
   once, so the difference is visible without flipping.
3. A **"Simulate room activity" (shuffle)** button: ~10 players stand, ~6 sit → table
   fullness changes → **both** lobbies re-rank, with visible row movement.
4. Synthesized poker-stats columns (avg pot / plrs-flop% / hnds-hr), seeded + stable.
5. Player/operator wall preserved: no scores, risk, archetype, or integrity language.

**Stretch (cut first if behind):** right-side table-details / seat panel (§4.1b).

**OUT (cut for Monday):**
- Many live tables actually dealing hands (the separate, expensive piece — cut).
- Functional waitlist, filters, multi-stake tabs (static decorative chrome only).

## 4. UX spec

### 4.1 The lobby table (columns)

Column set mirrors the WSOP reference. Real columns come from `LobbyTable` (no backend
change); the three poker-stats columns are **synthesized** (seeded, stable per table) —
they're included because every reference lobby has them and they're what sells the look.

| Column | Source | Notes |
|---|---|---|
| Table | `table_id` (+ friendly name) | left-aligned |
| Type | `game_type` | NL / PL |
| Stakes | `stakes` | e.g. `$1/$2` |
| Plrs | `seated_count`/`max_seats` | e.g. `5/6`; **Standard sort key** |
| Avg pot | *synthesized* (seeded) | $ value, stable per table |
| Plrs/Flop% | *synthesized* (seeded) | e.g. `38%` |
| Hnds/Hr | *synthesized* (seeded) | e.g. `62` |
| Speed | `pace_label` | optional, if it fits |
| Fit | `badge` / `badge_label` | "Recommended for you" / Good fit / Available — the player-safe FairPlay signal; **FairPlay sort key** |
| (action) | — | green **Join** button per row |

Synthesized values must be **deterministic per `table_id`** (seeded hash) so they don't
flicker on every re-rank — they read as real, stable table stats.

### 4.1b Right-side "Table details" panel (high realism — stretch)

Selecting a row shows a table-details panel (like WSOP/PokerOK): the selected table's
**seats** (player handles + stacks) and a **Join / Waiting list** button. We already have
seat data (the pit-boss seat ring uses it); the player-facing version shows handles +
stacks only, **no archetype/score**. High visual payoff; mark **stretch** for Saturday.

### 4.2 The two orderings (the heart of the beat)

A toggle: **[ Standard | FairPlay ]**, both player-safe orderings of the *same* tables:

- **Standard** = most-full first (`seated_count` desc). The "fill the fullest table"
  policy. Player-safe (just a sort by player count).
- **FairPlay** = the router's recommended order ("Recommended for you" first, then good
  fit, then available). Player-safe (badge ordering, no scores shown).

Flipping the toggle **animates rows to their new positions** so the reordering is
obvious. Presenter narrates *why* (health/fairness) — the reasoning is spoken, not shown
as numbers, which keeps the wall intact.

### 4.3 The shuffle / churn button

A single button — label TBD ("Simulate 5 minutes" / "Room activity"):

- Triggers a **seeded batch**: ~10 seated players stand, ~6 new players sit (numbers
  tunable). Deterministic so it's identical every rehearsal/run.
- Table fullness changes → the lobby **re-ranks under the active policy** → rows animate
  to new spots. Under Standard the newly-full tables jump up; under FairPlay a different
  set leads.
- **Build options (pick one):**
  - **A. Backend churn endpoint** (`POST /api/demo/churn`): mutates room state, broadcasts
    `score_update`, the existing SSE re-fetch re-ranks. Most honest; ~2–3h. Reuses the
    live seat/stand + SSE machinery already in `main.py`.
  - **B. Front-end seeded shuffle:** mutate a local copy of the table list, re-sort,
    animate. Safest/fastest for a live demo; ~1–2h. Less "real."
  - *Recommendation:* try A; keep B as the rehearsed fallback.

## 5. Data & wiring

- Source: the live `/api/lobby/{id}` (impersonator) when servers are up; frozen
  `router_lobby.json` as fallback. Both already exist.
- Standard order is computed client-side (sort by `seated_count`). FairPlay order is the
  order the router already returns. So **no scoring change needed** — we're presenting
  two sorts of one player-safe list.
- The build replaces the card grid in `PlayerLobby.tsx` with the table component;
  keep the existing data binding + the `LobbyTable`/`OperatorOnly` types so the
  player/operator-wall tests stay green.

## 6. Acceptance criteria (demo-able checklist)

- [ ] Lobby renders as a poker-site-style data table with the real columns above.
- [ ] Standard/FairPlay toggle visibly reorders rows (with animation).
- [ ] Shuffle button changes table fullness and re-ranks live, rows visibly moving.
- [ ] No score / risk / archetype / integrity text anywhere in the player lobby.
- [ ] Works with servers up; degrades to frozen data if the API drops.
- [ ] `tsc --noEmit` + `vite build` + Vitest stay green (update lobby tests for the new layout).

## 7. Build plan (Saturday, ordered)

1. **Tabular lobby component** — replace `TableTile` grid with a `<table>` mapping
   `LobbyTable` → columns. (~half day)
2. **Sort toggle + row-move animation** — Standard vs FairPlay. (~2h)
3. **Shuffle/churn** — option A endpoint or B front-end. (~2–3h)
4. **Synthesized stats columns** — seeded avg pot / plrs-flop% / hands-hr (deterministic
   per table_id). Included (sells the look). (~1–2h)
5. **(stretch) right-side table-details / seat panel** on row select. (~2–3h, cut first if behind)
6. **Styling pass to match reference screenshots** (dark GG/PokerOK look, WSOP columns). (Sun, ~1–2h)

## 8. Risks & fallbacks

- **Live churn flaky →** fall back to front-end seeded shuffle (option B).
- **Styling eats time →** ship a clean functional table; polish Sunday from screenshots.
- **Tests break on layout change →** update the lobby unit tests alongside (same data,
  new DOM).
- **Branch:** build on a branch off `main` (`feat/demo-lobby-shuffle`), not the
  training-sim branch, so it stays clean and demo-focused.

## 9. Open questions (need from Cory)

1. ~~Reference screenshots~~ — **received** (PokerOK / GGPoker / WSOP). Direction: dark
   GG/PokerOK theme + WSOP column set + table-details panel.
2. **Toggle vs side-by-side** for Standard/FairPlay — toggle is the safe default; want
   side-by-side as a stretch?
3. **Churn numbers** — ~10 stand / ~6 sit ok, or a different magnitude for visual punch?
4. **Replace the real lobby** vs a dedicated demo route? (Recommend replace.)
5. ~~Cosmetic columns~~ — **resolved: include** (synthesized; they sell the look).
6. **Right-side seat panel** (§4.1b) — worth the stretch, or skip for Monday?

## Related
- Demo storyboard (Cory's 5-part version) — this is Part 2.
- `frontend/src/views/PlayerLobby.tsx`, `frontend/src/components/TableTile.tsx` — what we replace.
- `frontend/contract2.d.ts` `LobbyTable` — the player-safe column source.
