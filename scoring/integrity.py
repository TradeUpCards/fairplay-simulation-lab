"""Integrity score — score ② of the eight (kickoff §2, §4).

Per-group integrity assessment by a **convergence rule**, NOT a trained model:
build the relationship graph from ``relationships.json``, then for each group
count the **independent signal families** that fire, net of named
**counter-evidence**, and map the count to a band:
``low · neutral · high · manual_review``.

Why not a model: the truth labels here are synthetic, generated *from* the same
signals we'd train on — a classifier would be circular and, worse, would learn
to over-escalate the false-positive traps the eval exists to catch. Counting
convergent independent families is transparent, auditable, and makes the
guardrail ("no single signal is proof") structural rather than hoped-for.

Guardrails baked in (CLAUDE.md hard rules):
* Output is **health-risk vs integrity-risk separated** — this module is the
  integrity lens only; grinders/promo abuse are NOT integrity findings.
* **Counter-evidence is always surfaced**, never silently dropped — every
  false-positive trap carries the exculpatory evidence that holds it down.
* **Never escalate the household** (CASE-E) and **never over-escalate a
  schedule overlap** (CASE-D): household/legitimate-regular counter-evidence
  caps the band at monitor.
* The bot-similarity account queue (CASE-G) is kept **out** of the
  cluster/collusion path — its own ``manual_review`` queue.
* No verdicts: bands recommend a human review action; they never assert
  collusion as fact.

Vocabulary follows ``docs/graph/fixture-vocab-mapping.md`` (Contract-1 →
Contract-3). Thresholds mirror ``docs/scoring-thresholds.md §3``.
"""

from __future__ import annotations

from typing import Any, Mapping, NamedTuple

# --- Calibrated thresholds (mirror in scoring-thresholds.md §3) ---
SOFT_PLAY_ESCALATION = -0.60   # documented: soft_play_delta <= -0.60 fires (CL-001: -0.75..-0.82)
CO_SEATING_HIGH = 0.60         # repeated co-seating that counts as a family (CL-001: 0.778)
TIMING_CORRELATION_HIGH = 0.80 # pairwise timing edge that counts (CL-001: 0.85, 0.88)
BOT_SIMILARITY_REVIEW = 0.80   # account-level bot queue floor (P-221: 0.87)

# Convergence-count → band cutoffs (net independent PRIMARY families).
CONVERGENCE_HIGH = 3           # >= 3 convergent families with no neutralizing counter-evidence
CONVERGENCE_NEUTRAL = 1        # 1-2 families → monitor

# The four PRIMARY signal families counted for convergence. outsider_pressure /
# casual-exit impact are CORROBORATING context (surfaced, not counted) so the
# count stays interpretable and matches the CASE-C "4 families converge" story.
PRIMARY_FAMILIES = ("device_link", "timing_correlation", "co_seating", "soft_play")


class Evidence(NamedTuple):
    code: str
    detail: str
    signals: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "detail": self.detail, "signals": self.signals}


class IntegrityAssessment(NamedTuple):
    group_id: str
    group_kind: str                 # "cluster" | "household" | "regular_overlap" | "bot_account"
    member_ids: list[str]
    band: str                       # low | neutral | high | manual_review
    convergence_count: int
    recommended_action: str
    signal_families: list[Evidence]   # PRIMARY families that fired
    corroborating: list[Evidence]     # supporting context, not counted
    counter_evidence: list[Evidence]  # exculpatory — ALWAYS surfaced
    note: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "group_kind": self.group_kind,
            "member_ids": self.member_ids,
            "band": self.band,
            "convergence_count": self.convergence_count,
            "recommended_action": self.recommended_action,
            "signal_families": [e.as_dict() for e in self.signal_families],
            "corroborating": [e.as_dict() for e in self.corroborating],
            "counter_evidence": [e.as_dict() for e in self.counter_evidence],
            "note": self.note,
        }


ACTION_BY_BAND = {
    "low": "monitor",
    "neutral": "monitor",
    "high": "hold_for_pitboss_review",
    "manual_review": "route_to_bot_review_queue",
}


def _min_soft_play(member_ids: list[str], players_by_id: Mapping[str, Mapping]) -> float | None:
    deltas = [players_by_id[m].get("soft_play_delta") for m in member_ids
              if m in players_by_id and players_by_id[m].get("soft_play_delta") is not None]
    return min(deltas) if deltas else None


def _shares_device(group: Mapping, member_ids: list[str],
                   players_by_id: Mapping[str, Mapping]) -> str | None:
    """Return a device-group id if a device link is present, else None."""
    if group.get("device_group_id"):
        return group["device_group_id"]
    if group.get("device_link") is True:
        return "device_link"
    for e in group.get("edges", []):
        if e.get("edge_type") == "device_link":
            return e.get("device_group_id", "device_link")
    dgs = {players_by_id[m].get("device_group_id") for m in member_ids
           if m in players_by_id and players_by_id[m].get("device_group_id")}
    return next(iter(dgs)) if dgs else None


def _max_timing_corr(group: Mapping) -> float:
    corrs = [e.get("correlation", e.get("strength", 0.0)) for e in group.get("edges", [])
             if e.get("edge_type") == "timing_correlation"]
    return max(corrs) if corrs else 0.0


def _band_from_count(count: int) -> str:
    if count >= CONVERGENCE_HIGH:
        return "high"
    if count >= CONVERGENCE_NEUTRAL:
        return "neutral"
    return "low"


def score_cluster(cluster: Mapping, players_by_id: Mapping[str, Mapping]) -> IntegrityAssessment:
    members = list(cluster.get("member_ids", []))
    fired: list[Evidence] = []
    corroborating: list[Evidence] = []
    counter: list[Evidence] = []

    # device_link
    dg = _shares_device(cluster, members, players_by_id)
    if dg:
        fired.append(Evidence("device_link",
            f"Shared device link ({dg}) ties cluster accounts to the same device group.",
            {"device_group_id": dg}))

    # timing_correlation
    tc = _max_timing_corr(cluster)
    if tc >= TIMING_CORRELATION_HIGH:
        fired.append(Evidence("timing_correlation",
            f"Pairwise session-timing correlation up to {tc:.2f} "
            f"(>= {TIMING_CORRELATION_HIGH}) across members.",
            {"max_timing_correlation": tc}))

    # co_seating
    co = cluster.get("co_seating", {})
    rate = co.get("rate", 0.0)
    if rate >= CO_SEATING_HIGH:
        fired.append(Evidence("co_seating",
            f"Repeated co-seating: {co.get('recent_shared_tables')}/"
            f"{co.get('opportunities')} shared tables (rate {rate:.2f} "
            f">= {CO_SEATING_HIGH}).",
            {"rate": rate, "shared_tables": co.get("recent_shared_tables"),
             "opportunities": co.get("opportunities")}))

    # soft_play (with sub-threshold counter-evidence)
    spd = _min_soft_play(members, players_by_id)
    if spd is not None and spd <= SOFT_PLAY_ESCALATION:
        fired.append(Evidence("soft_play",
            f"Within-cluster soft-play: soft_play_delta down to {spd:.2f} "
            f"(<= {SOFT_PLAY_ESCALATION}) — value given away in member-vs-member hands.",
            {"min_soft_play_delta": spd}))
    elif cluster.get("soft_play_signal") and spd is not None:
        counter.append(Evidence("low_sample_size_counter_evidence",
            f"Soft-play signal present but sub-threshold (soft_play_delta "
            f"{spd:.2f} > {SOFT_PLAY_ESCALATION}); insufficient to count as a "
            f"convergent family.",
            {"min_soft_play_delta": spd, "threshold": SOFT_PLAY_ESCALATION}))

    # corroborating (not counted toward convergence)
    if cluster.get("outsider_pressure_signal"):
        corroborating.append(Evidence("outsider_targeting",
            "Outsider-pressure signal present (coordinated aggression toward "
            "non-members); corroborating context, not a primary family.", {}))
    if cluster.get("high_casual_exit_impact"):
        corroborating.append(Evidence("casual_exit_impact",
            "Elevated casual-player exit impact at affected tables.", {}))

    count = len([e for e in fired if e.code in PRIMARY_FAMILIES])
    band = _band_from_count(count)
    note = cluster.get("note", "")
    return IntegrityAssessment(
        group_id=cluster.get("cluster_id", "?"), group_kind="cluster",
        member_ids=members, band=band, convergence_count=count,
        recommended_action=ACTION_BY_BAND[band], signal_families=fired,
        corroborating=corroborating, counter_evidence=counter, note=note)


def score_household(hh: Mapping, players_by_id: Mapping[str, Mapping]) -> IntegrityAssessment:
    """Households are an exculpatory lens (CASE-E): a shared device with
    divergent play is benign. Device link is acknowledged, but household
    counter-evidence caps the band at ``neutral`` (monitor) — never escalate."""
    members = list(hh.get("member_ids", []))
    fired: list[Evidence] = []
    counter: list[Evidence] = []

    dg = _shares_device(hh, members, players_by_id)
    if dg:
        fired.append(Evidence("device_link",
            f"Shared device ({dg}) — expected for a household; not incriminating "
            f"on its own.", {"device_group_id": dg}))

    co = hh.get("co_seating", {})
    rate = co.get("rate", 0.0)

    # Counter-evidence: the household frame is itself exculpatory (CASE-E), and
    # we ALWAYS surface it on a capped household — never leave the band capped
    # with an empty counter-evidence list (a load-bearing guardrail). When the
    # textbook divergent-profile pattern holds we say so; if a household ever
    # carried a positive signal we still surface the household context AND flag
    # the signal for the human reviewer rather than silently escalating.
    clean = not hh.get("session_pattern_overlap", False) and not hh.get("soft_play_signal", False)
    ds = hh.get("distinguishing_signals", {})
    if clean:
        counter.append(Evidence("household_counter_evidence",
            f"Divergent session profiles and low co-seating (rate {rate:.2f}); "
            f"no soft-play, no correlated profitability. Shared-device overlap is "
            f"explained by household, not collusion.",
            {"co_seating_rate": rate, **ds}))
    else:
        counter.append(Evidence("household_counter_evidence",
            f"Known household (shared-device, co-seating rate {rate:.2f}); "
            f"membership is exculpatory context. A positive signal is present — "
            f"surfaced for human review, NOT auto-escalated.",
            {"co_seating_rate": rate,
             "session_pattern_overlap": hh.get("session_pattern_overlap", False),
             "soft_play_signal": hh.get("soft_play_signal", False), **ds}))

    count = len([e for e in fired if e.code in PRIMARY_FAMILIES])  # device only → 1
    # Hard cap: a household with counter-evidence never exceeds neutral.
    band = "neutral" if count >= 1 else "low"
    note = hh.get("note", "")
    return IntegrityAssessment(
        group_id=hh.get("household_id", "?"), group_kind="household",
        member_ids=members, band=band, convergence_count=count,
        recommended_action=ACTION_BY_BAND[band], signal_families=fired,
        corroborating=[], counter_evidence=counter, note=note)


def score_regular_overlap(ovl: Mapping, players_by_id: Mapping[str, Mapping]) -> IntegrityAssessment:
    """Regular schedule overlap (CASE-D): high co-seating fully explained by
    shared stake/time, with no device link and no soft-play. Must stay low —
    over-escalating this is a failing eval."""
    members = list(ovl.get("member_ids", []))
    fired: list[Evidence] = []
    counter: list[Evidence] = []

    dg = _shares_device(ovl, members, players_by_id)
    if dg and ovl.get("device_link") is not False:
        fired.append(Evidence("device_link",
            f"Shared device link ({dg}).", {"device_group_id": dg}))

    spd = _min_soft_play(members, players_by_id)
    if spd is not None and spd <= SOFT_PLAY_ESCALATION:
        fired.append(Evidence("soft_play",
            f"Soft-play below threshold ({spd:.2f}).", {"min_soft_play_delta": spd}))

    co = ovl.get("co_seating", {})
    rate = co.get("rate", 0.0)
    # Counter-evidence: overlap explained by schedule, no integrity signals.
    if not ovl.get("device_link", False) and not ovl.get("soft_play_signal", False) \
            and not ovl.get("correlated_profitability", False):
        counter.append(Evidence("legitimate_regular_counter_evidence",
            f"High co-seating (rate {rate:.2f}) but no device link, no soft-play, "
            f"no correlated win/loss — explained by shared stake/time preference, "
            f"not coordination.",
            {"co_seating_rate": rate}))

    count = len([e for e in fired if e.code in PRIMARY_FAMILIES])
    band = _band_from_count(count)  # 0 families → low
    note = ovl.get("note", "")
    return IntegrityAssessment(
        group_id=ovl.get("overlap_id", "?"), group_kind="regular_overlap",
        member_ids=members, band=band, convergence_count=count,
        recommended_action=ACTION_BY_BAND[band], signal_families=fired,
        corroborating=[], counter_evidence=counter, note=note)


def bot_review_queue(players: list[Mapping[str, Any]]) -> list[IntegrityAssessment]:
    """Account-level bot-similarity queue (CASE-G). Kept OUT of the
    cluster/collusion path — its own ``manual_review`` queue, never asserted as
    a verdict."""
    out = []
    for p in players:
        bot = p.get("bot_similarity_score")
        if bot is not None and bot >= BOT_SIMILARITY_REVIEW:
            pid = p["player_id"]
            ev = Evidence("bot_fingerprint",
                f"Account-level bot-similarity {bot:.2f} (>= {BOT_SIMILARITY_REVIEW}) "
                f"with timing regularity {p.get('timing_regularity')}. Routed to a "
                f"dedicated bot-review queue, separate from collusion review.",
                {"bot_similarity_score": bot,
                 "timing_regularity": p.get("timing_regularity")})
            out.append(IntegrityAssessment(
                group_id=pid, group_kind="bot_account", member_ids=[pid],
                band="manual_review", convergence_count=0,
                recommended_action=ACTION_BY_BAND["manual_review"],
                signal_families=[ev], corroborating=[], counter_evidence=[],
                note="Account-level bot signal — own review queue, not collusion."))
    return out


def score_integrity(relationships: Mapping[str, Any],
                    players: list[Mapping[str, Any]]) -> list[IntegrityAssessment]:
    """Score every integrity group in ``relationships.json`` plus the
    account-level bot queue. Returns a flat list of assessments."""
    players_by_id = {p["player_id"]: p for p in players}
    out: list[IntegrityAssessment] = []
    for c in relationships.get("clusters", []):
        out.append(score_cluster(c, players_by_id))
    for h in relationships.get("households", []):
        out.append(score_household(h, players_by_id))
    for o in relationships.get("regular_overlaps", []):
        out.append(score_regular_overlap(o, players_by_id))
    out.extend(bot_review_queue(players))
    return out
