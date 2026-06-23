"""Model-builder service layer — pure, UI-agnostic, JSON-serializable.

This is the seam between the scoring/ML engine (ml/challenger.py, ml/scorecard.py)
and whatever UI sits on top. Every function takes plain arguments and returns
plain JSON-serializable dicts/lists (no numpy types, no sklearn objects leak
out). The Dash app imports these directly; a future FastAPI service would wrap
the same functions unchanged, and a React front-end would call that. Build the
boundary once, swap the UI freely.

Config shape used throughout:
    target    : str  — the archetype being modeled one-vs-rest
    selected  : list[str]            — variables in the model
    var_bins  : dict[str, int]       — per-variable bin count (default 4)
    C         : float                — logistic regularization
    balanced  : bool                 — class_weight balanced
    pdo       : int                  — points to double the odds (scorecard scaling)

Requires scikit-learn / pandas / numpy (not the stdlib scoring core).
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
from ml.scorecard import woe_iv, iv_strength, _ks

ROOT = Path(__file__).resolve().parents[1]
ARCHETYPES = ["new", "recreational", "regular", "grinder", "aggressive_predatory",
              "promo_hunter", "shared_device_household", "cluster_member",
              "healthy_anchor", "bot_like"]
DEFAULT_BINS = 4
RULE_CHAMPION_ACCURACY = 0.885  # scoring/classify.py threshold rules vs ground truth


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


def _nan(x: float) -> float | None:
    return None if (x is None or (isinstance(x, float) and math.isnan(x))) else round(float(x), 4)


def _divergence(prob: np.ndarray, y: np.ndarray) -> float:
    g, b = prob[y == 1], prob[y == 0]
    if len(g) < 2 or len(b) < 2:
        return float("nan")
    return float((g.mean() - b.mean()) ** 2 / (0.5 * (g.var() + b.var()) + 1e-9))


def _build(target: str, selected: list[str], var_bins: dict[str, int],
           C: float, balanced: bool) -> dict | None:
    """Fit the WoE-scorecard for the binary 'is target' problem. Internal —
    returns live objects (model/arrays); service functions project to JSON."""
    if not selected:
        return None
    df = _df()
    y = (df["archetype"] == target).astype(int)
    cols, ivs, tables = {}, {}, {}
    for f in selected:
        g, iv, row = woe_iv(df[f], y, bins=int(var_bins.get(f, DEFAULT_BINS)))
        cols[f], ivs[f], tables[f] = row, iv, g
    X = pd.DataFrame(cols)
    m = LogisticRegression(max_iter=2000, C=C,
                           class_weight="balanced" if balanced else None)
    m.fit(X.to_numpy(), y.to_numpy())
    prob = m.predict_proba(X.to_numpy())[:, 1]
    yv = y.to_numpy()
    return dict(model=m, prob=prob, y=yv, ivs=ivs, tables=tables,
                coef=dict(zip(selected, m.coef_[0])), intercept=float(m.intercept_[0]),
                ks=_ks(yv, prob) if y.sum() >= 2 else float("nan"),
                auc=roc_auc_score(yv, prob) if y.sum() >= 2 else float("nan"),
                divergence=_divergence(prob, yv), n_pos=int(y.sum()))


# ── public service API (all JSON-serializable) ───────────────────────────────

def archetypes() -> list[str]:
    return list(ARCHETYPES)


def features() -> list[str]:
    return list(FEATURES)


def dataset_summary(target: str) -> dict[str, Any]:
    df = _df()
    y = (df["archetype"] == target).astype(int)
    good = int(y.sum())
    return {"target": target, "good": good, "bad": len(df) - good,
            "total": len(df), "base_rate": round(good / len(df), 4),
            "low_confidence": good < 4}


def attribute_rows(target: str, selected: list[str], var_bins: dict[str, int],
                   C: float, balanced: bool) -> list[dict[str, Any]]:
    """One row per candidate predictor — the Scorecard Editor grid."""
    df = _df()
    y = (df["archetype"] == target).astype(int)
    m = _build(target, selected, var_bins, C, balanced)
    rows = []
    for f in FEATURES:
        _, iv, _ = woe_iv(df[f], y, bins=int(var_bins.get(f, DEFAULT_BINS)))
        rows.append({
            "variable": f, "in_model": f in selected,
            "contribution": _nan(iv), "strength": iv_strength(iv),
            "weight": _nan(m["coef"][f]) if (m and f in m["coef"]) else None,
            "bins": int(var_bins.get(f, DEFAULT_BINS)),
        })
    rows.sort(key=lambda r: (not r["in_model"], -(r["contribution"] or 0)))
    return rows


def model_metrics(target: str, selected: list[str], var_bins: dict[str, int],
                  C: float, balanced: bool, pdo: int) -> dict[str, Any]:
    m = _build(target, selected, var_bins, C, balanced)
    if not m:
        return {"ks": None, "auc": None, "divergence": None, "total_iv": 0.0,
                "n_pos": dataset_summary(target)["good"], "base_points": None,
                "importance": []}
    factor = pdo / math.log(2)
    importance = sorted(
        [{"variable": f, "contribution": _nan(m["ivs"][f]),
          "weight": _nan(m["coef"][f]), "strength": iv_strength(m["ivs"][f])}
         for f in selected],
        key=lambda r: -(r["contribution"] or 0))
    return {"ks": _nan(m["ks"]), "auc": _nan(m["auc"]),
            "divergence": _nan(m["divergence"]),
            "total_iv": round(sum(m["ivs"].values()), 3), "n_pos": m["n_pos"],
            "base_points": int(round(100 + factor * m["intercept"])),
            "importance": importance}


def bin_detail(target: str, variable: str, nbins: int, selected: list[str],
               var_bins: dict[str, int], C: float, balanced: bool, pdo: int) -> dict[str, Any]:
    """WoE bins + points for one variable — the Interactive Binner panel."""
    df = _df()
    y = (df["archetype"] == target).astype(int)
    g, iv, _ = woe_iv(df[variable], y, bins=int(nbins))
    m = _build(target, selected, var_bins, C, balanced)
    coef = m["coef"].get(variable, 0.0) if m else 0.0
    factor = pdo / math.log(2)
    bins = []
    for interval, row in g.iterrows():
        woe = float(row["woe"])
        bins.append({"bin": str(interval), "n": int(row["n"]),
                     "good": int(row["pos"]), "bad": int(row["neg"]),
                     "woe": round(woe, 2), "points": int(round(factor * coef * woe))})
    woes = [b["woe"] for b in bins]
    mono = (all(woes[i] <= woes[i + 1] for i in range(len(woes) - 1)) or
            all(woes[i] >= woes[i + 1] for i in range(len(woes) - 1)))
    return {"variable": variable, "iv": _nan(iv), "strength": iv_strength(iv),
            "monotonic": mono, "in_model": variable in selected,
            "nbins": int(nbins), "bins": bins}


def reports(target: str, selected: list[str], var_bins: dict[str, int],
            C: float, balanced: bool) -> dict[str, Any]:
    """Challenger (current edits) vs Champion (auto: all vars, 4 bins)."""
    chal = _build(target, selected, var_bins, C, balanced)
    champ = _build(target, list(FEATURES), {}, 1.0, True)
    if not chal or chal["n_pos"] < 2:
        return {"insufficient": True}

    def roc_pts(m):
        fpr, tpr, _ = roc_curve(m["y"], m["prob"])
        return [{"fpr": round(float(a), 4), "tpr": round(float(b), 4)}
                for a, b in zip(fpr, tpr)]

    # KS curve for the challenger
    d = pd.DataFrame({"p": chal["prob"], "y": chal["y"]}).sort_values("p").reset_index(drop=True)
    cg = (d.y == 1).cumsum() / max((d.y == 1).sum(), 1)
    cb = (d.y == 0).cumsum() / max((d.y == 0).sum(), 1)
    pct = np.linspace(0, 1, len(d))
    ks_curve = [{"pct": round(float(p), 4), "good": round(float(a), 4), "bad": round(float(b), 4)}
                for p, a, b in zip(pct, cg, cb)]

    # Fit-odds: bin score into deciles, actual log-odds per band
    q = min(10, max(2, chal["n_pos"]))
    d["band"] = pd.qcut(d["p"].rank(method="first"), q=q, labels=False)
    fo = d.groupby("band").agg(score=("p", "mean"), good=("y", "sum"), n=("y", "size")).reset_index()
    fo["bad"] = fo["n"] - fo["good"]
    fit_odds = [{"score": round(float(s), 4), "log_odds": round(float(np.log((gd + 0.5) / (bd + 0.5))), 3)}
                for s, gd, bd in zip(fo["score"], fo["good"], fo["bad"])]

    df = _df()
    y = (df["archetype"] == target).astype(int)
    training = [{"variable": f, "selected": f in selected,
                 "contribution": _nan(woe_iv(df[f], y, bins=int(var_bins.get(f, DEFAULT_BINS)))[1]),
                 "bins": int(var_bins.get(f, DEFAULT_BINS)),
                 "weight": _nan(chal["coef"].get(f)) if f in chal["coef"] else None}
                for f in FEATURES]

    return {
        "insufficient": False,
        "comparison": [
            {"model": "Challenger", "ks": _nan(chal["ks"]), "auc": _nan(chal["auc"]),
             "divergence": _nan(chal["divergence"]), "variables": len(selected)},
            {"model": "Champion", "ks": _nan(champ["ks"]), "auc": _nan(champ["auc"]),
             "divergence": _nan(champ["divergence"]), "variables": len(FEATURES)},
        ],
        "roc_challenger": roc_pts(chal), "roc_champion": roc_pts(champ),
        "ks_curve": ks_curve, "ks": _nan(chal["ks"]),
        "training": training, "fit_odds": fit_odds,
    }


def combine(selected: list[str], var_bins: dict[str, int], C: float, balanced: bool) -> dict[str, Any]:
    """OvR ensemble in-sample accuracy with the current config."""
    df = _df()
    feats = selected or list(FEATURES)
    probs = np.column_stack([_build(c, feats, var_bins, C, balanced)["prob"] for c in ARCHETYPES])
    pred = np.array(ARCHETYPES)[probs.argmax(axis=1)]
    truth = df["archetype"].to_numpy()
    return {"in_sample_accuracy": round(float((pred == truth).mean()), 4),
            "rule_champion": RULE_CHAMPION_ACCURACY, "variables": len(feats)}


def combine_player(pid: str, selected: list[str], var_bins: dict[str, int],
                   C: float, balanced: bool) -> dict[str, Any]:
    df = _df()
    feats = selected or list(FEATURES)
    probs = {c: _build(c, feats, var_bins, C, balanced)["prob"] for c in ARCHETYPES}
    pos = df.index.get_loc(df.index[df["player_id"] == pid][0])
    scores = sorted([{"archetype": c, "prob": round(float(probs[c][pos]), 4)} for c in ARCHETYPES],
                    key=lambda r: -r["prob"])
    return {"player_id": pid, "truth": df.iloc[pos]["archetype"],
            "predicted": scores[0]["archetype"], "scores": scores}


def combine_loo(selected: list[str], C: float, balanced: bool) -> dict[str, Any]:
    """Honest leave-one-out accuracy (slower) for the OvR ensemble."""
    df = _df()
    feats = selected or list(FEATURES)
    truth = df["archetype"].to_numpy()
    pipe = make_pipeline(StandardScaler(), OneVsRestClassifier(LogisticRegression(
        max_iter=2000, C=C, class_weight="balanced" if balanced else None)))
    loo = cross_val_predict(pipe, df[feats].to_numpy(), truth, cv=LeaveOneOut())
    return {"loo_accuracy": round(float((loo == truth).mean()), 4),
            "rule_champion": RULE_CHAMPION_ACCURACY}


def player_ids() -> list[str]:
    return _df()["player_id"].tolist()
