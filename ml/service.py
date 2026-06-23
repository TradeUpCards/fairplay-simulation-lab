"""Model-builder service layer — pure, UI-agnostic, JSON-serializable.

The seam between the scoring/ML engine (ml/challenger.py, ml/scorecard.py) and
whatever UI sits on top. Every function takes plain arguments and returns plain
JSON-serializable dicts/lists. The Dash app imports these directly; a future
FastAPI service would wrap them unchanged.

Binning model (best practice, two stages):
  * **Fine classing — automatic, data-driven.** Each variable is binned by a
    supervised decision tree on the target (``auto_fine_cuts``): the cut points
    isolate where the class actually lives, with a variable bin count per
    variable (NOT a flat quantile split). Handles non-monotonic relationships.
  * **Coarse classing — the analyst.** Starting from the fine cuts, the user
    merges adjacent bins (drops cut points). Binning is therefore carried as a
    list of **cut points** per variable, not a bin count.

Config shape:
    target    : str
    selected  : list[str]               — variables in the model
    var_cuts  : dict[str, list[float]]  — coarse cut points (subset of the auto
                                          fine cuts); absent → use the auto cuts
    C         : float · balanced : bool · pdo : int

Requires scikit-learn / pandas / numpy.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ml.challenger import FEATURES
from ml.scorecard import auto_fine_cuts, woe_from_cuts, iv_strength, _ks

ROOT = Path(__file__).resolve().parents[1]
ARCHETYPES = ["new", "recreational", "regular", "grinder", "aggressive_predatory",
              "promo_hunter", "shared_device_household", "cluster_member",
              "healthy_anchor", "bot_like"]
RULE_CHAMPION_ACCURACY = 0.885


def truth_of(pid: str) -> str:
    n = int(pid.split("-")[1])
    for hi, lab in [(107, "new"), (141, "recreational"), (163, "regular"),
                    (175, "grinder"), (183, "aggressive_predatory"),
                    (191, "promo_hunter"), (197, "shared_device_household"),
                    (202, "cluster_member"), (220, "healthy_anchor")]:
        if n <= hi:
            return lab
    return "bot_like"


@lru_cache(maxsize=1)
def _df() -> pd.DataFrame:
    players = json.loads((ROOT / "data" / "players.json").read_text(encoding="utf-8"))["players"]
    df = pd.DataFrame(players)
    df["archetype"] = df["player_id"].map(truth_of)
    df[FEATURES] = df[FEATURES].fillna(df[FEATURES].median())
    return df


@lru_cache(maxsize=512)
def _auto(target: str, variable: str) -> tuple[float, ...]:
    """Cached auto fine cuts for one (target, variable)."""
    df = _df()
    y = (df["archetype"] == target).astype(int)
    return tuple(auto_fine_cuts(df[variable], y))


def _cuts(target: str, variable: str, var_cuts: dict) -> list[float]:
    """Active cut points: the user's coarse subset if set, else the auto fine cuts."""
    if var_cuts and variable in var_cuts:
        return [float(c) for c in var_cuts[variable]]
    return list(_auto(target, variable))


def _nan(x) -> float | None:
    return None if (x is None or (isinstance(x, float) and math.isnan(x))) else round(float(x), 4)


def _divergence(prob: np.ndarray, y: np.ndarray) -> float:
    g, b = prob[y == 1], prob[y == 0]
    if len(g) < 2 or len(b) < 2:
        return float("nan")
    return float((g.mean() - b.mean()) ** 2 / (0.5 * (g.var() + b.var()) + 1e-9))


def _build(target: str, selected: list[str], var_cuts: dict, C: float, balanced: bool) -> dict | None:
    if not selected:
        return None
    df = _df()
    y = (df["archetype"] == target).astype(int)
    cols, ivs = {}, {}
    for f in selected:
        g, iv, row = woe_from_cuts(df[f], y, _cuts(target, f, var_cuts))
        cols[f], ivs[f] = row, iv
    X = pd.DataFrame(cols)
    m = LogisticRegression(max_iter=2000, C=C, class_weight="balanced" if balanced else None)
    m.fit(X.to_numpy(), y.to_numpy())
    prob = m.predict_proba(X.to_numpy())[:, 1]
    yv = y.to_numpy()
    return dict(model=m, prob=prob, y=yv, ivs=ivs, coef=dict(zip(selected, m.coef_[0])),
                intercept=float(m.intercept_[0]),
                ks=_ks(yv, prob) if y.sum() >= 2 else float("nan"),
                auc=roc_auc_score(yv, prob) if y.sum() >= 2 else float("nan"),
                divergence=_divergence(prob, yv), n_pos=int(y.sum()))


# ── public API ───────────────────────────────────────────────────────────────

def archetypes() -> list[str]:
    return list(ARCHETYPES)


def features() -> list[str]:
    return list(FEATURES)


def player_ids() -> list[str]:
    return _df()["player_id"].tolist()


def dataset_summary(target: str) -> dict[str, Any]:
    df = _df()
    good = int((df["archetype"] == target).sum())
    return {"target": target, "good": good, "bad": len(df) - good, "total": len(df),
            "base_rate": round(good / len(df), 4), "low_confidence": good < 4}


def n_bins(target: str, variable: str, var_cuts: dict) -> int:
    return len(_cuts(target, variable, var_cuts)) + 1


def attribute_rows(target: str, selected: list[str], var_cuts: dict, C: float, balanced: bool):
    df = _df()
    y = (df["archetype"] == target).astype(int)
    m = _build(target, selected, var_cuts, C, balanced)
    rows = []
    for f in FEATURES:
        cuts = _cuts(target, f, var_cuts)
        _, iv, _ = woe_from_cuts(df[f], y, cuts)
        rows.append({"variable": f, "in_model": f in selected, "contribution": _nan(iv),
                     "strength": iv_strength(iv),
                     "weight": _nan(m["coef"][f]) if (m and f in m["coef"]) else None,
                     "bins": len(cuts) + 1})
    rows.sort(key=lambda r: (not r["in_model"], -(r["contribution"] or 0)))
    return rows


def model_metrics(target: str, selected: list[str], var_cuts: dict, C: float, balanced: bool, pdo: int):
    m = _build(target, selected, var_cuts, C, balanced)
    if not m:
        return {"ks": None, "auc": None, "divergence": None, "total_iv": 0.0,
                "n_pos": dataset_summary(target)["good"], "base_points": None, "importance": []}
    factor = pdo / math.log(2)
    importance = sorted([{"variable": f, "contribution": _nan(m["ivs"][f]),
                          "weight": _nan(m["coef"][f]), "strength": iv_strength(m["ivs"][f])}
                         for f in selected], key=lambda r: -(r["contribution"] or 0))
    return {"ks": _nan(m["ks"]), "auc": _nan(m["auc"]), "divergence": _nan(m["divergence"]),
            "total_iv": round(sum(m["ivs"].values()), 3), "n_pos": m["n_pos"],
            "base_points": int(round(100 + factor * m["intercept"])), "importance": importance}


def bin_detail(target: str, variable: str, var_cuts: dict, selected: list[str],
               C: float, balanced: bool, pdo: int) -> dict[str, Any]:
    """Interactive Binner panel for one variable: the current (coarse) bins +
    the full set of auto fine cuts available to merge/keep."""
    df = _df()
    y = (df["archetype"] == target).astype(int)
    auto = list(_auto(target, variable))
    active = _cuts(target, variable, var_cuts)
    g, iv, _ = woe_from_cuts(df[variable], y, active)
    m = _build(target, selected, var_cuts, C, balanced)
    coef = m["coef"].get(variable, 0.0) if m else 0.0
    factor = pdo / math.log(2)
    edges = [float("-inf")] + active + [float("inf")]
    tot_pos = max(int(g["pos"].sum()), 1)
    bins = []
    for i, (label, row) in enumerate(g.iterrows()):
        woe = float(row["woe"])
        n, pos = int(row["n"]), int(row["pos"])
        bins.append({"idx": i, "bin": str(label), "lo": edges[i], "hi": edges[i + 1],
                     "n": n, "good": pos, "bad": n - pos,
                     "event_pct": round(100 * pos / n, 1) if n else 0.0,
                     "share_pct": round(100 * pos / tot_pos, 1),
                     "woe": round(woe, 2), "iv_part": round(float(row["iv_part"]), 3),
                     "points": int(round(factor * coef * woe))})
    woes = [b["woe"] for b in bins]
    mono = (all(woes[i] <= woes[i + 1] for i in range(len(woes) - 1)) or
            all(woes[i] >= woes[i + 1] for i in range(len(woes) - 1)))

    # fine bins (the full auto binning) so a collapsed coarse bin can be expanded
    fg, _, _ = woe_from_cuts(df[variable], y, auto)
    fedges = [float("-inf")] + auto + [float("inf")]
    fine = []
    for i, (label, row) in enumerate(fg.iterrows()):
        n, pos = int(row["n"]), int(row["pos"])
        fine.append({"bin": str(label), "lo": fedges[i], "hi": fedges[i + 1], "n": n,
                     "good": pos, "bad": n - pos,
                     "event_pct": round(100 * pos / n, 1) if n else 0.0,
                     "woe": round(float(row["woe"]), 2)})
    tree = []
    for cb in bins:
        kids = [fb for fb in fine if cb["lo"] <= fb["lo"] and fb["hi"] <= cb["hi"]]
        node = dict(cb)
        node["n_fine"] = len(kids)
        node["children"] = kids if len(kids) > 1 else []
        tree.append(node)

    return {"variable": variable, "iv": _nan(iv), "strength": iv_strength(iv),
            "monotonic": mono, "in_model": variable in selected, "bins": bins, "tree": tree,
            "n_fine": len(fine),
            "auto_cuts": [round(c, 4) for c in auto], "active_cuts": [round(c, 4) for c in active]}


def combine_bins(target: str, variable: str, var_cuts: dict, bin_indices: list[int]) -> list[float]:
    """Merge the selected (adjacent) bins into one by dropping the cut points
    between them. Returns the new active cut list."""
    active = _cuts(target, variable, var_cuts)
    idxs = sorted(int(i) for i in bin_indices)
    if len(idxs) < 2:
        return active
    a, b = idxs[0], idxs[-1]
    return active[:a] + active[b:]          # remove boundary cuts a..b-1


def split_bin(target: str, variable: str, var_cuts: dict, bin_index: int) -> list[float]:
    """Re-introduce an automatic fine cut inside the selected bin (un-merge)."""
    active = _cuts(target, variable, var_cuts)
    auto = list(_auto(target, variable))
    edges = [float("-inf")] + active + [float("inf")]
    lo, hi = edges[int(bin_index)], edges[int(bin_index) + 1]
    cand = [c for c in auto if lo < c < hi and c not in active]
    if not cand:
        return active
    return sorted(active + [cand[len(cand) // 2]])  # add the middle available cut


def reports(target: str, selected: list[str], var_cuts: dict, C: float, balanced: bool) -> dict[str, Any]:
    chal = _build(target, selected, var_cuts, C, balanced)
    champ = _build(target, list(FEATURES), {}, 1.0, True)  # auto fine cuts, all vars
    if not chal or chal["n_pos"] < 2:
        return {"insufficient": True}

    def roc_pts(m):
        fpr, tpr, _ = roc_curve(m["y"], m["prob"])
        return [{"fpr": round(float(a), 4), "tpr": round(float(b), 4)} for a, b in zip(fpr, tpr)]

    d = pd.DataFrame({"p": chal["prob"], "y": chal["y"]}).sort_values("p").reset_index(drop=True)
    cg = (d.y == 1).cumsum() / max((d.y == 1).sum(), 1)
    cb = (d.y == 0).cumsum() / max((d.y == 0).sum(), 1)
    pct = np.linspace(0, 1, len(d))
    ks_curve = [{"pct": round(float(p), 4), "good": round(float(a), 4), "bad": round(float(b), 4)}
                for p, a, b in zip(pct, cg, cb)]
    q = min(10, max(2, chal["n_pos"]))
    d["band"] = pd.qcut(d["p"].rank(method="first"), q=q, labels=False)
    fo = d.groupby("band").agg(score=("p", "mean"), good=("y", "sum"), n=("y", "size")).reset_index()
    fo["bad"] = fo["n"] - fo["good"]
    fit_odds = [{"score": round(float(s), 4), "log_odds": round(float(np.log((gd + 0.5) / (bd + 0.5))), 3)}
                for s, gd, bd in zip(fo["score"], fo["good"], fo["bad"])]
    df = _df()
    y = (df["archetype"] == target).astype(int)
    training = [{"variable": f, "selected": f in selected,
                 "contribution": _nan(woe_from_cuts(df[f], y, _cuts(target, f, var_cuts))[1]),
                 "bins": len(_cuts(target, f, var_cuts)) + 1,
                 "weight": _nan(chal["coef"].get(f)) if f in chal["coef"] else None}
                for f in FEATURES]
    return {"insufficient": False,
            "comparison": [
                {"model": "Challenger", "ks": _nan(chal["ks"]), "auc": _nan(chal["auc"]),
                 "divergence": _nan(chal["divergence"]), "variables": len(selected)},
                {"model": "Champion", "ks": _nan(champ["ks"]), "auc": _nan(champ["auc"]),
                 "divergence": _nan(champ["divergence"]), "variables": len(FEATURES)}],
            "roc_challenger": roc_pts(chal), "roc_champion": roc_pts(champ),
            "ks_curve": ks_curve, "ks": _nan(chal["ks"]), "training": training, "fit_odds": fit_odds}


def combine(selected: list[str], var_cuts: dict, C: float, balanced: bool) -> dict[str, Any]:
    df = _df()
    feats = selected or list(FEATURES)
    probs = np.column_stack([_build(c, feats, var_cuts, C, balanced)["prob"] for c in ARCHETYPES])
    pred = np.array(ARCHETYPES)[probs.argmax(axis=1)]
    truth = df["archetype"].to_numpy()
    return {"in_sample_accuracy": round(float((pred == truth).mean()), 4),
            "rule_champion": RULE_CHAMPION_ACCURACY, "variables": len(feats)}


def combine_player(pid: str, selected: list[str], var_cuts: dict, C: float, balanced: bool):
    df = _df()
    feats = selected or list(FEATURES)
    probs = {c: _build(c, feats, var_cuts, C, balanced)["prob"] for c in ARCHETYPES}
    pos = df.index.get_loc(df.index[df["player_id"] == pid][0])
    scores = sorted([{"archetype": c, "prob": round(float(probs[c][pos]), 4)} for c in ARCHETYPES],
                    key=lambda r: -r["prob"])
    return {"player_id": pid, "truth": df.iloc[pos]["archetype"],
            "predicted": scores[0]["archetype"], "scores": scores}


def combine_loo(selected: list[str], C: float, balanced: bool) -> dict[str, Any]:
    df = _df()
    feats = selected or list(FEATURES)
    truth = df["archetype"].to_numpy()
    pipe = make_pipeline(StandardScaler(), OneVsRestClassifier(LogisticRegression(
        max_iter=2000, C=C, class_weight="balanced" if balanced else None)))
    loo = cross_val_predict(pipe, df[feats].to_numpy(), truth, cv=LeaveOneOut())
    return {"loo_accuracy": round(float((loo == truth).mean()), 4),
            "rule_champion": RULE_CHAMPION_ACCURACY}
