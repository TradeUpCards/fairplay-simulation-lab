"""Evidence packet — Contract 3 (the P3 → P4 seam).

The pit-boss/AI-Investigator contract. P3 (scoring) **produces** this; P4 (the AI
Investigator) **consumes** it and writes a human-readable case summary. This module
assembles the packet from already-computed P3 outputs — it does **no** new analytics.

Hard rules this seam enforces (CLAUDE.md):
  * **Structured evidence only — never raw data.** A packet carries scores,
    reason-code details, and entity *IDs*; it never carries raw player/session rows.
    The AI Investigator sees this packet and nothing else, which is what makes
    "the LLM is never the detector" true by construction.
  * **Counter-evidence is always surfaced** (``counter_evidence``) and the things
    the AI must hedge on are explicit (``uncertainties``).
  * **Health risk ≠ integrity risk.** ``case_type`` keeps the lenses distinct.
  * **Never enforce.** ``recommended_action`` is always a *human* action and
    ``allowed_actions`` is a safe operator menu — never a ban/freeze/auto-restrict.

Schema (Contract 3 canonical fields + minimal context):
    case_id · case_type · scores · top_evidence · counter_evidence · uncertainties
    · recommended_action · allowed_actions          (the eight PRD fields)
    + title · subjects · provenance                  (context; IDs only, no raw rows)

`top_evidence` / `counter_evidence` items are ``{code, detail, signals}`` — the same
reason-code shape P3 already emits, so the AI gets uniform, groundable evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# The safe operator menu — the only actions the pit-boss may take. There is no
# "ban"/"freeze"/"restrict": the system recommends and explains; the human decides.
ALLOWED_ACTIONS = [
    "accept",                       # accept the recommendation as-is
    "override",                     # operator disagrees, records a different call
    "monitor",                      # keep watching, no action yet
    "suppress_table_for_player",    # stop recommending one table to one player
    "escalate",                     # route to a human integrity reviewer
]

# case_type vocabulary — keeps the health / integrity / promo / bot lenses distinct.
CASE_TYPES = {
    "table_health_risk",   # an unhealthy *table state* (a health concern, not an accusation)
    "integrity_risk",      # a coordination/collusion *signal* for human review
    "promo_abuse",         # bonus optimization — distinct from cheating
    "bot_account",         # automation-like account — its own review queue
}


@dataclass
class EvidencePacket:
    case_id: str
    case_type: str
    title: str
    subjects: dict[str, Any]                       # entity IDs only (group/players/table)
    scores: dict[str, Any]
    top_evidence: list[dict[str, Any]]
    counter_evidence: list[dict[str, Any]]
    uncertainties: list[str]
    recommended_action: str
    allowed_actions: list[str] = field(default_factory=lambda: list(ALLOWED_ACTIONS))
    provenance: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── universal hedges every packet carries ────────────────────────────────────
_BASE_UNCERTAINTY = (
    "This is an elevated-for-review signal, not a determination of wrongdoing. "
    "A human operator decides; no automatic action is taken."
)
_SYNTHETIC_UNCERTAINTY = (
    "All signals are simulated fields on synthetic data — not real device "
    "telemetry, KYC, location, or real-time gameplay/RTA."
)

# per-lens hedges the AI Investigator must carry into its summary
_LENS_UNCERTAINTY = {
    "integrity_risk": [
        "Convergent signals are consistent with coordination but can also reflect "
        "benign shared context (household, friends, similar schedules); none is "
        "individually conclusive.",
    ],
    "table_health_risk": [
        "Health and seating scores are composition-based projections of table "
        "state, not realized outcomes — an unhealthy mix is a risk, not proof of harm.",
    ],
    "promo_abuse": [
        "A promo-redemption pattern indicates bonus optimization, which is a "
        "policy/health matter and distinct from collusion or cheating.",
    ],
    "bot_account": [
        "Bot-similarity is a heuristic that warrants review, not proof of "
        "automation; route to the bot-review queue, do not enforce.",
    ],
}


def _uncertainties(case_type: str, extra: list[str] | None = None) -> list[str]:
    out = [_BASE_UNCERTAINTY, _SYNTHETIC_UNCERTAINTY]
    out += _LENS_UNCERTAINTY.get(case_type, [])
    if extra:
        out += extra
    return out


# injected when no exculpatory signal exists, so counter_evidence is never empty
# (the guardrail: counter-evidence is *always* surfaced, even if only to say none
# was found — absence is not corroboration).
_NO_COUNTER = {
    "code": "no_material_counter_evidence",
    "detail": (
        "Counter-evidence was assessed; no material exculpatory signal was found "
        "in the available evidence. Absence of counter-evidence is not "
        "corroboration — weigh the primary signals against the uncertainties."
    ),
    "signals": {},
}


def _ev(items: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Normalize reason-code/signal-family items to {code, detail, signals}."""
    norm = []
    for it in items or []:
        norm.append({
            "code": it.get("code", ""),
            "detail": it.get("detail", ""),
            "signals": it.get("signals", {}),
        })
    return norm


# ── per-source assemblers ─────────────────────────────────────────────────────
def _from_integrity(case: dict, assessment: dict) -> tuple[dict, list, list, str, list[str]]:
    """Integrity-sourced packet (cluster / overlap / household / bot account)."""
    scores = {
        "integrity_band": assessment.get("band"),
        "convergence_count": assessment.get("convergence_count"),
        "group_kind": assessment.get("group_kind"),
    }
    top = _ev(assessment.get("signal_families")) + _ev(assessment.get("corroborating"))
    counter = _ev(assessment.get("counter_evidence"))
    rec = assessment.get("recommended_action", "hold_for_pitboss_review")
    extra_unc = []
    note = assessment.get("note")
    if note:
        extra_unc.append(str(note))
    if case.get("is_false_positive_trap"):
        extra_unc.append(
            "Flagged in the data as a false-positive trap: the convergent-looking "
            "overlap has a benign explanation (see counter-evidence)."
        )
    return scores, top, counter, rec, extra_unc


def _from_health(case: dict, health: dict | None, seating: dict | None,
                 classification: dict | None) -> tuple[dict, list, list, str, list[str]]:
    """Health/seating/classification-sourced packet (new player, grinder, promo)."""
    seed = case.get("pit_boss_evidence_seed", {}) or {}
    scores: dict[str, Any] = {}
    top: list[dict[str, Any]] = []
    counter: list[dict[str, Any]] = []

    if health:
        scores["table_health"] = health.get("health")
        scores["health_band"] = health.get("band")
        top += _ev(health.get("reason_codes"))
    if seed:
        # surface the seeded pit-boss numbers (already structured, no raw rows)
        for k in ("table_health_score", "new_player_seating_risk", "occupancy",
                  "predicted_state"):
            if k in seed:
                scores.setdefault(k, seed[k])
    if seating:
        # seating candidate is the recommended *reroute target*, not the seeded
        # (bad) table — key it distinctly so it isn't read as the case's own risk.
        scores["reroute_target_seating_risk"] = seating.get("seating_risk")
        top += _ev(seating.get("reason_codes"))
    if classification:
        scores.setdefault("archetype", classification.get("archetype"))
        top += _ev(classification.get("reason_codes"))

    # health cases rarely carry stored counter-evidence; make the benign reading explicit
    if case.get("is_false_positive_trap"):
        counter.append({
            "code": "benign_explanation",
            "detail": (
                "No integrity signals (no device link, soft-play, or correlated "
                "win/loss). The pattern is explained by skill / legitimate play, "
                "not coordination — a health lens, not an integrity accusation."
            ),
            "signals": {"is_false_positive_trap": True},
        })

    rec = case.get("expected_seating_action", "monitor")
    return scores, top, counter, rec, []


# group_id resolver: which integrity assessment (if any) a case points at
def _group_id_for(case: dict) -> str | None:
    e = case.get("seeded_entities", {}) or {}
    for key in ("cluster_id", "overlap_record", "household_id", "bot_candidate"):
        if e.get(key):
            return e[key]
    return None


def _case_type(case: dict) -> str:
    label = case.get("prd_label", "")
    if "promo" in label:
        return "promo_abuse"
    if "bot" in label:
        return "bot_account"
    ents = case.get("seeded_entities", {}) or {}
    # any relationship-group case (cluster / overlap / household) is an integrity
    # lens — including the false-positive traps, where the integrity engine
    # correctly declines to escalate.
    if any(ents.get(k) for k in ("cluster_id", "overlap_record", "household_id")):
        return "integrity_risk"
    if case.get("expected_risk_lens") == "integrity_risk":
        return "integrity_risk"
    return "table_health_risk"


def _title(case: dict) -> str:
    return (case.get("prd_label", case["case_id"]).replace("_", " ").capitalize())


# ── public API ────────────────────────────────────────────────────────────────
def assemble_packets(
    cases: list[dict],
    *,
    integrity_by_group: dict[str, dict],
    health_by_table: dict[str, dict],
    seating_by_player: dict[str, dict],
    classification_by_player: dict[str, dict],
) -> list[EvidencePacket]:
    """Build one evidence packet per seeded case from frozen P3 outputs.

    Pure: takes already-parsed P3 data, returns packets. No file IO, no raw rows.
    """
    packets: list[EvidencePacket] = []
    for case in cases:
        case_type = _case_type(case)
        ents = case.get("seeded_entities", {}) or {}
        gid = _group_id_for(case)

        if gid and gid in integrity_by_group:
            scores, top, counter, rec, extra = _from_integrity(case, integrity_by_group[gid])
        else:
            # resolve the single subject player + its seeded table, if any
            pid = (ents.get("new_player") or ents.get("grinder") or ents.get("promo_abuser")
                   or ents.get("bot_candidate"))
            tid = ents.get("seeded_table_label")
            scores, top, counter, rec, extra = _from_health(
                case,
                health_by_table.get(tid) if tid else None,
                seating_by_player.get(pid) if pid else None,
                classification_by_player.get(pid) if pid else None,
            )

        if not counter:
            counter = [dict(_NO_COUNTER)]

        packets.append(EvidencePacket(
            case_id=case["case_id"],
            case_type=case_type,
            title=_title(case),
            subjects={
                "entities": ents,
                "primary_group": gid,
                "false_positive_trap": bool(case.get("is_false_positive_trap")),
            },
            scores=scores,
            top_evidence=top,
            counter_evidence=counter,
            uncertainties=_uncertainties(case_type, extra),
            recommended_action=rec,
            provenance={
                "produced_by": "P3 / scoring.evidence",
                "prd_ref": case.get("prd_ref"),
                "sources": ["integrity_scores" if gid else "health/seating/classifications",
                            "seeded_case_labels"],
                "note": "Structured evidence only — assembled from frozen P3 outputs; no raw rows.",
            },
        ))
    return packets
