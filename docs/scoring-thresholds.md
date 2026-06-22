# Scoring Thresholds (D8) — the numeric cutoffs P3 computes and P4 validates

> **Owner:** P3. **Read by:** P4 (eval checks), P1 (display bands).
> **Status:** §1 classification · §2 health bands · §3 integrity bands · §4
> seating scores · §4d/§5 router — **published**. **All eight scores shipped,
> calibrated, and validated.**
>
> This is the single source of truth for every numeric cutoff in the scoring
> engine. The constants live in code (`scoring/*.py`) and are mirrored here in
> plain language so P4 can write eval checks and P1 can label bands without
> reading Python. If a constant changes, change it in both places.

---

## 1. Classification champion (score ①) — **published**

Threshold-rule classifier, first-match-wins cascade. Rules are ordered by
signal strength / stakes, not population frequency. Source of truth:
`scoring/classify.py`; validated by `scripts/validate_classify.py`.

| # | Archetype | Rule (fires top-down; first match wins) | Source of threshold |
|---|---|---|---|
| 1 | `bot_like` | `bot_similarity_score ≥ 0.80` **and** `timing_regularity ≥ 0.80` | extreme-fingerprint floor (P-221 = 0.87/0.88) |
| 2 | `cluster_member` | `cluster_id` is set | structured truth field |
| 3 | `shared_device_household` | `household_id` is set | structured truth field |
| 4 | `new` | `registered_days_ago ≤ 14` | **documented** (players.json inference note) |
| 5 | `promo_hunter` | `promo_redemptions_30d ≥ 8` **and** `avg_session_minutes ≤ 60` | **documented** (≥8) + short-session guard |
| 6 | `aggressive_predatory` | `vpip ≥ 0.54` **and** `pfr ≥ 0.40` | **documented** (players.json inference note) |
| 7 | `grinder` | `aggression_factor ≥ 2.45` **and** `lifetime_hands ≥ 50,000` | calibrated (grinder AF 2.5–3.0; clean separator) |
| 8 | `healthy_anchor` | `lifetime_hands ≥ 17,000` **or** `avg_session_minutes ≥ 160` | calibrated (above regular ceiling) |
| 9 | `regular` | `lifetime_hands ≥ 1,700` **or** `avg_session_minutes ≥ 95` **or** `sessions_last_30d ≥ 12` | calibrated |
| 10 | `recreational` | default (none of the above) | — |

**Precedence rationale.** Integrity-membership flags (rows 1–3) are checked
before behavioral tiers because they are the highest-stakes labels and are set
directly by P2's truth model. Where rules *do* overlap — e.g. the predatory
aggressors P-176/P-177 also clear the grinder AF/hands floor — the earlier rule
wins by design (predatory before grinder); the ordering is documented and
auditable rather than incidental. The behavioral volume ladder (rows 7–10) is
**fuzzy by design**: recreational/regular/healthy_anchor overlap on volume, and
that overlap is exactly why score ① has an interpretable ML challenger.

**Measured performance** (champion vs documented ID-range truth, all 122
players): **88.5% overall**, **100% on every sign-posted and case-pinned class**
(new, aggressive_predatory, promo_hunter, grinder, cluster_member,
shared_device_household, bot_like, healthy_anchor). All residual error is the
recreational↔regular boundary. This is the baseline the ML challenger must beat
to be promoted.

**D7 (LOCKED 2026-06-22).** The canonical set is **10** archetypes — the nine
behavioral/structural types plus `bot_like` (kickoff §8 pins `P-221 = bot_like`
and Eval G needs it). `bot_like` routes to its own account-level bot review
queue, kept out of the coordinated-cluster path. See `docs/DECISIONS.md` D7.

---

## 2. Health bands (score ⑥) — **published**

`Health(T) = 100 − P_pred − P_frag − P_clus − P_bleed`, clamped [0, 100].
Source of truth: `scoring/health.py`; validated by `scripts/validate_health.py`.
Term taxonomy + band semantics from `docs/index.html §03`.

**Bands** (display ranges from index.html §03; assignment rule is **half-open
on the lower cutoff** — see note):

| Band | Health(T) display | Assignment rule (`band_for`) | Routing |
|---|---|---|---|
| healthy | 70–100 | `h ≥ 70` | no intervention · may promote to new players |
| fragile | 50–69 | `50 ≤ h < 70` | monitor · throttle new-player routing |
| beginner_unfriendly | 30–49 | `30 ≤ h < 50` | suppress from new-player lobby · route away |
| collapsed | 0–29 | `h < 30` | remove from lobby · notify pit boss |
| **integrity_candidate** (flag, not a range) | any | seated **high**-band cluster | surface to pit-boss queue regardless of score |

> **Half-open semantics (load-bearing).** `Health(T)` is a real number, not an
> integer, so bands are assigned by **lower cutoff only**: `band_for` walks the
> bands high→low and returns the first whose lower cutoff `h` clears, i.e. each
> band is the half-open interval `[lo, next_lo)`. The display column above (e.g.
> "50–69") is the integer-rounded face of `[50, 70)`. This matters at fractional
> boundaries: `69.5 → fragile` (**not** collapsed), `49.5 → beginner_unfriendly`,
> `29.5 → collapsed`. Boundary values land in the **higher** band
> (`70.0 → healthy`, `50.0 → fragile`, `30.0 → beginner_unfriendly`); fractional
> values **round down** into the band below their display range's top. An earlier
> closed-interval implementation (`lo ≤ h ≤ hi`) left gaps — `69.5` matched no
> band and fell through to collapsed — which is the misroute this rule prevents.

Acceptance anchor: **Health(T-22) = 38** → beginner_unfriendly (CASE-A seed).
T-11 (CL-001 seated) = 43.9 with P_clus 15 + integrity_candidate flag.

**The four penalty terms:**

| Term | Range | Rule | Key constants |
|---|---|---|---|
| `P_pred` | 0–45 | `45·(1 − e^(−K·pressure))`, `pressure = agg_weight / (vulnerable + 1)` | `K = ln(9)/2 ≈ 1.099` (calibrated so T-22 → 40); aggressor weights `aggressive_predatory 1.0`, `grinder 0.35`; vulnerable = `new + recreational` |
| `P_frag` | 0–25 | `min(25, 30·(1 − occupancy) + trend_penalty)` | trend penalty `growing 0 · stable 2 · flat 7 · declining 12` |
| `P_clus` | 0–30 | `Σ 30 · severity · seat_fraction` over seated clusters | severity from integrity band ② `high 1.0 · neutral 0.35 · low 0.15 · manual_review 0.0` (bot queue is account-level, not a table cluster) |
| `P_bleed` | 0–20 | `min(20, 7 · truncated_recreational_sessions)` | truncation = session `< 0.5 ×` archetype baseline (`new 30m · rec 60m`); **counterfactual scenario sessions excluded** |

**Calibration note.** Only `K_PRED` is fit to the T-22=38 anchor (`P_frag` has
no challenger — its constants are hand-calibrated, per kickoff §2). `P_pred(T-22)
= 40` (2 aggressors, 0 recreational → pressure 2.0) and `P_frag(T-22) = 22`
(3/6 seats, flat trend) sum to 62 → Health 38.000.

**P_bleed is 0 across the Day-2 static snapshot** by construction: roster
sessions are still `active`, and the only completed sessions are CASE-A's
`standard`/`fairplay` counterfactual projections, which are excluded from
realized-history bleed. The observed term activates in the counterfactual sim —
composition leads, bleed follows (index.html §03 / §04).

---

## 3. Integrity bands (score ②) — **published**

Per-group band from the **convergence rule** (count of independent PRIMARY
signal families that fire, net of named counter-evidence). NOT a trained model.
Source of truth: `scoring/integrity.py`; validated by
`scripts/validate_integrity.py`.

**The four PRIMARY signal families** (counted toward convergence):

| Family | Fires when | Source |
|---|---|---|
| `device_link` | group shares a `device_group_id` / has a `device_link` edge | — |
| `timing_correlation` | any pairwise `timing_correlation ≥ 0.80` | CL-001: 0.85, 0.88 |
| `co_seating` | `co_seating.rate ≥ 0.60` | CL-001: 0.778 |
| `soft_play` | `min(soft_play_delta) ≤ −0.60` | **documented** escalation threshold |

`outsider_pressure_signal` and casual-exit impact are **corroborating** context
— surfaced in the packet but **not** counted, so the convergence count stays
interpretable (and matches the CASE-C "4 families converge" story exactly).

**Counter-evidence** (always surfaced; neutralizes a family or caps the band):

| Counter-evidence | Effect |
|---|---|
| `low_sample_size_counter_evidence` | soft-play present but sub-threshold → soft_play family does not fire (CL-002) |
| `household_counter_evidence` | shared device + divergent profiles → caps band at **neutral** (CASE-E) |
| `legitimate_regular_counter_evidence` | high co-seating explained by schedule, no device/soft-play → band **low** (CASE-D) |

**Convergence count → band:**

| Band | Rule | Recommended action | Acceptance |
|---|---|---|---|
| low | 0 net families | `monitor` | OVL-001 (CASE-D) |
| neutral | 1–2 net families (or capped by household counter-evidence) | `monitor` | CL-002, H-01/02/03 (CASE-E) |
| high | ≥ 3 net families, no neutralizing counter-evidence | `hold_for_pitboss_review` | CL-001 (CASE-C), 4 families |
| manual_review | account-level bot queue (`bot_similarity_score ≥ 0.80`), kept OUT of the collusion path | `route_to_bot_review_queue` | P-221 (CASE-G) |

Hard rules (CLAUDE.md): **never escalate the household** and **never
over-escalate a schedule overlap** — both are failing evals; the counter-evidence
caps enforce them structurally. Counter-evidence is **always** surfaced.

---

## 4. Seating scores (score ⑦) — **published**

Three player×table scores the router (⑧) consumes. Source of truth:
`scoring/seating.py`; validated by `scripts/validate_seating.py`. Term
semantics from `docs/index.html §04–§05`.

### 4a. Fit(P,T) — 0–100 (champion: archetype × table-style matrix)

The table's `style_volatility_label` maps (first keyword wins) to a canonical
**style key**: `predatory · grinder_heavy · healthy_anchor · beginner_friendly
· promo_short · long_session · recreational_heavy · regular_heavy · balanced ·
mixed`. `Fit = FIT_MATRIX[archetype][style]`. The `new` row is calibrated to the
index.html §05 worked example — **Fit(P-104): T-8 balanced = 74, T-14
regular_heavy = 58, T-22 predatory = 22**; other rows are directional. The ML
challenger (session-length predictor) is raced later in P4's lab.

### 4b. ΔHealth(P→T) — re-score composition terms, hold P_bleed fixed

`ΔHealth = Health'(T∪{P}) − Health(T)`, recomputing only P_pred/P_frag/P_clus
(P_bleed lags). Analytic, O(1) per table.

> **Known divergence (flagged for reconciliation).** ΔHealth measures the
> **table's composition**, not the joining player's danger. Adding a vulnerable
> player to a predator-heavy table yields a *small positive* ΔHealth (it dilutes
> the aggressor ratio and fills a seat): computed **ΔHealth(P-104→T-22) = +15.0**,
> whereas the index.html §04 illustration shows ≈ −8 by conflating table-health
> with player-risk. We implement the kickoff's literal instruction ("re-score
> composition terms, take the delta"). The danger to P-104 lives in
> **seating-risk** (§4c), which is the actually-pinned acceptance — so the demo
> story (route P-104 to T-8, suppress T-22) holds via seating-risk + band, not
> the ΔHealth sign. *(Same class of drift as the index.html §05 T-11 card; both
> to reconcile with P1.)*

### 4c. Seating-risk(P,T) — low · medium · high (the player-protection signal)

Composite of integrity gate + health band + new-player vulnerability + ΔHealth:

1. **Integrity hard-gate (first):** if the table is `integrity_candidate` (a
   seated **high**-band cluster), it is **gated out of candidates entirely** and
   seating-risk = `high`. (Player may still self-select; the badge reflects the
   recommendation only.)
2. **Vulnerable player** (`new`/`recreational`) → risk from the table band:
   `healthy → low · fragile → medium · beginner_unfriendly/collapsed → high`.
3. **Non-vulnerable player** → `low` at healthy/fragile tables, else `medium`
   (the band is a table-health concern, not a per-seat protection issue).
4. **ΔHealth bump:** `ΔHealth ≤ −6.0` raises the level one step.

Acceptance: **Seating-risk(P-104, T-22) = HIGH** (new player + beginner_unfriendly
band) and LOW at T-8/T-14; T-11 (CL-001 seated) is hard-gated.

### 4d. Router weights (score ⑧ — frozen policy, v0 defaults)

`Rank(P,T) = 0.30·Fit + 0.40·Health + 0.30·ΔHealth`. Source of truth:
`scoring/router.py`; validated by `scripts/validate_router.py`. Weights
`w_fit 0.30 · w_h 0.40 · w_Δ 0.30` (index.html §05; calibrated offline).

**Two gates wrap the rank, in order:**
1. **Integrity hard-gate (first):** a seated high-band cluster removes the table
   from candidates entirely → badge `hidden_gated` (absent from lobby).
2. **Vulnerable-protection gate:** a table is only *promoted* if the seeking
   player's seating-risk is **LOW**; medium/high → `available` (visible, not
   promoted). This is what enforces CASE-A ("T-22 not promoted to new players").

**Badge tiers** (among low-risk candidates, by rank):

| Badge | Rule | Player-facing label |
|---|---|---|
| `recommended` | low-risk **and** `rank ≥ 58.0` | "Recommended for you" |
| `good_fit` | low-risk **and** `rank ≥ 40.0` | "Good fit" |
| `available` | otherwise (incl. all medium/high-risk) | "Available" |
| `hidden_gated` | integrity hard-gate | *(not shown in lobby)* |

Tier cutoffs `REC_RANK_MIN 58.0 · GOODFIT_RANK_MIN 40.0` are calibrated to the
CASE-A demo: for P-104, **T-8 → recommended, T-14 → good_fit, T-22 → available,
T-11 → hidden_gated**. ⚠️ `REC_RANK_MIN 58.0` is **co-calibrated with the Health
champion** — it sits in the ~2.5-pt gap between T-8 (60.5) and T-14 (56.1), so a
change to `health.py`'s healthy-table output can shift these badges. Re-run
`validate_router.py` after any Health re-calibration. (Absolute rank numbers differ from the index.html §05
illustration — 60.5 / 56.1 / 26.3 vs 55.2 / 44.2 / 13.0 — because the Health
champion is anchored to the only pinned value T-22=38, compressing healthy-table
health to ~90+. The badge **ordering** is what's pinned, and it holds.)

**Player-facing / operator-facing seam.** `route` emits two views:
`operator_view` (full rank/score/risk/band — pit-boss console) and
`player_lobby` (neutral badges + safe table facts only — `LOBBY_SAFE_FIELDS`,
**no** rank, health, seating-risk, archetype, or integrity language). The leakage
guardrail is asserted in `validate_router.py`.
