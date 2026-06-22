"""Classification champion — score ① of the eight (kickoff §2, §8).

A deterministic threshold-rule classifier that maps one ``players.json`` record
to one of the 10 archetypes plus the structured **reason codes** behind the
call. This is the ROOT dependency for the rest of the scoring engine and the
"champion" that ships the demo; the interpretable ML challenger (one-vs-rest
logistic, see ``docs/learn/ovr-notebook.ipynb``) is an additive upgrade raced
in P4's eval lab — it never replaces these rules unless it both wins on labeled
accuracy and stays interpretable.

Design notes
------------
* **Reason codes everywhere** (kickoff §3). ``classify`` returns the archetype
  *and* the list of rules that fired with the exact feature values, so no UI or
  evidence packet ever hand-writes the "why". For the ML challenger these same
  codes become the model coefficients.
* **First-match-wins cascade.** Rules are ordered by signal strength /
  stakes, not by population frequency. Structured integrity-membership flags
  (``cluster_id``, ``household_id``) and the bot fingerprint are checked before
  behavioral tiers because they are the highest-stakes labels and are set
  directly by P2's truth model. The behavioral volume ladder
  (recreational < regular < healthy_anchor < grinder) is genuinely fuzzy by
  design — that overlap is *why* score ① has an ML challenger — so the champion
  uses transparent volume thresholds and accepts imperfect accuracy on those
  filler tiers. The acceptance-pinned case players all live in the strongly
  sign-posted classes.

Thresholds come from ``players.json``'s documented inference note where one is
given (``registered_days_ago<=14``, ``vpip>=0.54 & pfr>=0.40``,
``promo_redemptions_30d>=8``); the volume-ladder cutoffs were calibrated from
the per-archetype distributions in the committed fixture (see
``scripts/validate_classify.py``).

Decision **D7 (LOCKED 2026-06-22)**: the canonical set is **10** archetypes —
the nine behavioral/structural types plus ``bot_like`` (kickoff §8 pins
``P-221=bot_like`` and Eval G needs it). ``bot_like`` routes to its own
account-level bot review queue, kept out of the coordinated-cluster path.
"""

from __future__ import annotations

from typing import Any, Mapping, NamedTuple


# Canonical labels (D7 LOCKED — 10 archetypes incl. ``bot_like``).
ARCHETYPES = (
    "new",
    "recreational",
    "regular",
    "grinder",
    "aggressive_predatory",
    "promo_hunter",
    "shared_device_household",
    "cluster_member",
    "healthy_anchor",
    "bot_like",
)


class ReasonCode(NamedTuple):
    """One rule that fired, with the evidence that triggered it.

    ``code``    stable machine key (safe for UI / evidence-packet wiring).
    ``detail``  human-readable, operator-facing explanation.
    ``signals`` the exact feature values behind the call, for audit.
    """

    code: str
    detail: str
    signals: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "detail": self.detail, "signals": self.signals}


class Classification(NamedTuple):
    archetype: str
    reason_codes: list[ReasonCode]

    def as_dict(self) -> dict[str, Any]:
        return {
            "archetype": self.archetype,
            "reason_codes": [rc.as_dict() for rc in self.reason_codes],
        }


# --- Calibrated thresholds (single source of truth; mirror in scoring-thresholds.md) ---
BOT_SIMILARITY_MIN = 0.80          # extreme bot-fingerprint floor (P-221 = 0.87)
BOT_TIMING_MIN = 0.80              # paired with timing regularity (P-221 = 0.88)
NEW_MAX_DAYS = 14                  # documented: registered_days_ago <= 14
PROMO_MIN_REDEMPTIONS = 8          # documented: promo_redemptions_30d >= 8
PROMO_MAX_SESSION_MIN = 60         # "short sessions" guard (promo_hunter median ~39)
PREDATORY_VPIP_MIN = 0.54          # documented: vpip >= 0.54 & pfr >= 0.40
PREDATORY_PFR_MIN = 0.40
GRINDER_AF_MIN = 2.45              # grinders AF 2.5-3.0; all softer tiers < 2.45
GRINDER_HANDS_MIN = 50_000         # corroborating volume floor (grinder min 75k)
HEALTHY_HANDS_MIN = 17_000         # above the regular ceiling (~16.4k)
HEALTHY_SESSION_MIN = 160          # established long-session anchor
REGULAR_HANDS_MIN = 1_700          # above the recreational core
REGULAR_SESSION_MIN = 95
REGULAR_SESSIONS_30D_MIN = 12


def _num(player: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    """Read a numeric feature, tolerating null/missing (a fragile-fixture guard)."""
    v = player.get(key)
    return default if v is None else float(v)


def classify(player: Mapping[str, Any]) -> Classification:
    """Classify one player record into ``(archetype, reason_codes)``.

    ``player`` is one element of ``data/players.json``'s ``players`` array.
    Returns a :class:`Classification`; call ``.as_dict()`` for JSON output.
    """
    pid = player.get("player_id", "?")

    bot = _num(player, "bot_similarity_score")
    timing = _num(player, "timing_regularity")
    reg_days = _num(player, "registered_days_ago", default=10_000)
    vpip = _num(player, "vpip")
    pfr = _num(player, "pfr")
    promo = _num(player, "promo_redemptions_30d")
    af = _num(player, "aggression_factor")
    hands = _num(player, "lifetime_hands")
    session_min = _num(player, "avg_session_minutes")
    sessions_30d = _num(player, "sessions_last_30d")
    cluster_id = player.get("cluster_id")
    household_id = player.get("household_id")

    # 1. bot_like — extreme, paired timing/pattern fingerprint (Eval G, P-221).
    #    Checked first: highest-stakes integrity label, and the only one keyed
    #    purely off the two simulated bot signals.
    if bot >= BOT_SIMILARITY_MIN and timing >= BOT_TIMING_MIN:
        return Classification("bot_like", [ReasonCode(
            "bot_fingerprint",
            f"Extreme bot-similarity ({bot:.2f}) with near-perfect timing "
            f"regularity ({timing:.2f}) — routed to its own review queue, not a verdict.",
            {"bot_similarity_score": bot, "timing_regularity": timing},
        )])

    # 2. cluster_member — flagged coordination cluster membership (CASE-C).
    if cluster_id:
        return Classification("cluster_member", [ReasonCode(
            "cluster_membership",
            f"Member of flagged coordination cluster {cluster_id}; integrity is "
            f"scored at the cluster level, not asserted against this account.",
            {"cluster_id": cluster_id},
        )])

    # 3. shared_device_household — known household / shared device (CASE-E).
    #    Distinct lens from cluster: monitor-only, must NOT escalate.
    if household_id:
        return Classification("shared_device_household", [ReasonCode(
            "household_membership",
            f"Belongs to known household {household_id} (shared-device link). "
            f"Benign overlap by default — monitor, do not escalate.",
            {"household_id": household_id},
        )])

    # 4. new — brand-new account (CASE-A vulnerable player).
    if reg_days <= NEW_MAX_DAYS:
        return Classification("new", [ReasonCode(
            "recent_registration",
            f"Account registered {int(reg_days)} day(s) ago "
            f"(<= {NEW_MAX_DAYS}); treat as a new, vulnerable player.",
            {"registered_days_ago": reg_days},
        )])

    # 5. promo_hunter — heavy promo redemption + short sessions (CASE-F).
    if promo >= PROMO_MIN_REDEMPTIONS and session_min <= PROMO_MAX_SESSION_MIN:
        return Classification("promo_hunter", [ReasonCode(
            "promo_redemption_rate",
            f"{int(promo)} promo redemptions in 30d with short "
            f"~{int(session_min)}-min sessions — promo abuse, a health/economics "
            f"concern, not collusion.",
            {"promo_redemptions_30d": promo, "avg_session_minutes": session_min},
        )])

    # 6. aggressive_predatory — documented vpip/pfr signature (CASE-A aggressors).
    if vpip >= PREDATORY_VPIP_MIN and pfr >= PREDATORY_PFR_MIN:
        return Classification("aggressive_predatory", [ReasonCode(
            "loose_aggressive_profile",
            f"Loose-aggressive profile (vpip {vpip:.2f} >= {PREDATORY_VPIP_MIN}, "
            f"pfr {pfr:.2f} >= {PREDATORY_PFR_MIN}); raises predation pressure on "
            f"softer tables.",
            {"vpip": vpip, "pfr": pfr, "aggression_factor": af},
        )])

    # --- Behavioral volume ladder (fuzzy by design; ML-challenger territory) ---

    # 7. grinder — high-volume, high-postflop-aggression professional (CASE-B).
    #    Aggression factor is the clean separator from healthy_anchor/regular.
    if af >= GRINDER_AF_MIN and hands >= GRINDER_HANDS_MIN:
        return Classification("grinder", [ReasonCode(
            "high_volume_professional",
            f"High-volume grind ({int(hands):,} lifetime hands) with strong "
            f"postflop aggression (AF {af:.2f}); a table-health consideration, "
            f"explicitly NOT an integrity flag.",
            {"lifetime_hands": hands, "aggression_factor": af,
             "sessions_last_30d": sessions_30d},
        )])

    # 8. healthy_anchor — established, high-engagement, low-aggression stabilizer.
    if hands >= HEALTHY_HANDS_MIN or session_min >= HEALTHY_SESSION_MIN:
        return Classification("healthy_anchor", [ReasonCode(
            "established_stabilizer",
            f"Established, high-engagement regular ({int(hands):,} hands, "
            f"~{int(session_min)}-min sessions) with moderate aggression "
            f"(AF {af:.2f}) — a stabilizing presence at the table.",
            {"lifetime_hands": hands, "avg_session_minutes": session_min,
             "aggression_factor": af},
        )])

    # 9. regular — steady mid-volume player.
    if (hands >= REGULAR_HANDS_MIN or session_min >= REGULAR_SESSION_MIN
            or sessions_30d >= REGULAR_SESSIONS_30D_MIN):
        return Classification("regular", [ReasonCode(
            "steady_midvolume",
            f"Steady mid-volume play ({int(hands):,} hands, "
            f"{int(sessions_30d)} sessions/30d) — ordinary engaged regular.",
            {"lifetime_hands": hands, "avg_session_minutes": session_min,
             "sessions_last_30d": sessions_30d},
        )])

    # 10. recreational — default tier: low volume, short sessions, casual.
    return Classification("recreational", [ReasonCode(
        "low_volume_casual",
        f"Low-volume casual play ({int(hands):,} hands, ~{int(session_min)}-min "
        f"sessions) — the recreational majority this room is built to protect.",
        {"lifetime_hands": hands, "avg_session_minutes": session_min,
         "sessions_last_30d": sessions_30d},
    )])


def classify_all(players: list[Mapping[str, Any]]) -> dict[str, Classification]:
    """Classify a list of player records, keyed by ``player_id``."""
    return {p.get("player_id", f"idx-{i}"): classify(p)
            for i, p in enumerate(players)}
