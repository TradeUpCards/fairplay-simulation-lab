"""Scorecard view of the one-vs-rest challenger — WoE · IV · points · KS.

For each archetype this builds the classic FICO/SAS-style **scorecard** for its
binary "is this player class C?" model:

* **WoE** (Weight of Evidence) — bin each feature, replace each bin with
  ``ln(P(bin | class) / P(bin | not-class))``: how class-ish that range is.
* **IV** (Information Value) — ``Σ (dist_pos − dist_neg)·WoE`` per feature: how
  well the whole feature separates the class (the feature-ranking number).
* **Points** — the WoE-fitted logistic's per-bin contribution scaled to integer
  scorecard points (PDO = points to double the odds). Higher total → more like C.
* **KS / AUC** — the binary model's separation on the development sample.

These are **binary-native** tools — the reason the kickoff picks one-vs-rest over
multinomial: each class stays a standalone, auditable scorecard.

The 10 scorecards combine by **argmax**: score a player under all 10, predict the
class whose scorecard scores highest. That ensemble IS the OvR challenger.

Development view: everything here is computed in-sample on all 122 players (how
scorecards are built/presented). The honest out-of-sample accuracy vs the rule
champion is the leave-one-out number in the champion-vs-challenger panel.

Requires scikit-learn / pandas / numpy.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from .challenger import FEATURES

PDO = 20.0                       # points to double the odds
FACTOR = PDO / np.log(2)
BASE_SCORE = 500.0               # nominal base points per class scorecard
N_BINS = 4
LOW_CONFIDENCE_POS = 4           # < this many positives → WoE bins are unreliable


def woe_iv(x: pd.Series, y: pd.Series, bins: int = N_BINS):
    """Bin a feature and compute per-bin WoE + total IV (Laplace-smoothed).

    Returns ``(bin_table, iv, row_woe)`` where ``row_woe`` is the per-row WoE
    aligned to the input index (for WoE-transforming the design matrix)."""
    d = pd.DataFrame({"x": np.asarray(x, dtype=float), "y": np.asarray(y, dtype=int)})
    try:
        d["bin"] = pd.qcut(d["x"], q=bins, duplicates="drop")
    except (ValueError, IndexError):
        nun = max(1, d["x"].nunique())
        d["bin"] = pd.cut(d["x"], bins=min(bins, nun))
    g = d.groupby("bin", observed=True)["y"].agg(n="count", pos="sum")
    g["neg"] = g["n"] - g["pos"]
    k = max(len(g), 1)
    tot_pos, tot_neg = max(int(g["pos"].sum()), 1), max(int(g["neg"].sum()), 1)
    # Laplace smoothing so empty bins don't blow up the log.
    g["dist_pos"] = (g["pos"] + 0.5) / (tot_pos + 0.5 * k)
    g["dist_neg"] = (g["neg"] + 0.5) / (tot_neg + 0.5 * k)
    g["woe"] = np.log(g["dist_pos"] / g["dist_neg"])
    g["iv_part"] = (g["dist_pos"] - g["dist_neg"]) * g["woe"]
    iv = float(g["iv_part"].sum())
    row_woe = d["bin"].map(g["woe"]).astype(float)
    row_woe.index = x.index
    return g, iv, row_woe


def iv_strength(iv: float) -> str:
    if iv < 0.02: return "unpredictive"
    if iv < 0.1: return "weak"
    if iv < 0.3: return "medium"
    if iv < 0.5: return "strong"
    return "very strong"


def _ks(y: np.ndarray, p: np.ndarray) -> float:
    d = pd.DataFrame({"y": y, "p": p}).sort_values("p")
    cum_pos = (d.y == 1).cumsum() / max((d.y == 1).sum(), 1)
    cum_neg = (d.y == 0).cumsum() / max((d.y == 0).sum(), 1)
    return float((cum_pos - cum_neg).abs().max())


def class_scorecard(df: pd.DataFrame, cls: str) -> dict[str, Any]:
    """Full scorecard for one class: per-feature IV, WoE bins + points, KS/AUC."""
    y = (df["archetype"] == cls).astype(int)
    n_pos = int(y.sum())

    bin_tables, ivs, woe_cols = {}, {}, {}
    for f in FEATURES:
        g, iv, row_woe = woe_iv(df[f], y)
        bin_tables[f], ivs[f], woe_cols[f] = g, iv, row_woe

    woe_X = pd.DataFrame(woe_cols)
    model = LogisticRegression(max_iter=2000, class_weight="balanced")
    model.fit(woe_X.to_numpy(), y.to_numpy())
    coef = dict(zip(FEATURES, model.coef_[0]))
    intercept = float(model.intercept_[0])

    prob = model.predict_proba(woe_X.to_numpy())[:, 1]
    auc = float(roc_auc_score(y, prob)) if n_pos >= 2 else None
    ks = _ks(y.to_numpy(), prob) if n_pos >= 2 else None

    # Per-feature scorecard, IV-ranked.
    features_out = []
    for f in sorted(FEATURES, key=lambda k: ivs[k], reverse=True):
        g = bin_tables[f]
        bins = []
        for interval, row in g.iterrows():
            woe = float(row["woe"])
            pts = int(round(FACTOR * coef[f] * woe))  # + → toward class
            bins.append({
                "range": str(interval),
                "n": int(row["n"]), "pos": int(row["pos"]),
                "woe": round(woe, 2), "points": pts,
            })
        features_out.append({
            "feature": f, "iv": round(ivs[f], 3), "strength": iv_strength(ivs[f]),
            "coef": round(coef[f], 2), "bins": bins,
        })

    return {
        "archetype": cls, "n_positive": n_pos,
        "low_confidence": n_pos < LOW_CONFIDENCE_POS,
        "base_points": int(round(BASE_SCORE + FACTOR * intercept)),
        "ks": round(ks, 2) if ks is not None else None,
        "auc": round(auc, 2) if auc is not None else None,
        "features": features_out,
        "_model": model, "_woe_cols": woe_cols,  # internal, stripped before JSON
    }


def all_scorecards(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [class_scorecard(df, c) for c in sorted(df["archetype"].unique())]


def combine(df: pd.DataFrame, cards: list[dict[str, Any]]) -> dict[str, Any]:
    """Combine the 10 scorecards by argmax of P(class) and report the in-sample
    development accuracy + a per-player score matrix for worked examples."""
    classes = [c["archetype"] for c in cards]
    # Score every player under every class scorecard.
    proba = np.column_stack([
        c["_model"].predict_proba(pd.DataFrame(c["_woe_cols"]).to_numpy())[:, 1]
        for c in cards
    ])
    pred_idx = proba.argmax(axis=1)
    pred = [classes[i] for i in pred_idx]
    truth = df["archetype"].tolist()
    correct = sum(p == t for p, t in zip(pred, truth))

    examples = {}
    for pid in ("P-104", "P-164", "P-198"):
        if pid in df["player_id"].values:
            i = df.index[df["player_id"] == pid][0]
            pos = df.index.get_loc(i)
            scored = sorted(
                ({"archetype": classes[j], "prob": round(float(proba[pos, j]), 3)}
                 for j in range(len(classes))),
                key=lambda r: r["prob"], reverse=True)
            examples[pid] = {
                "truth": df.loc[i, "archetype"],
                "predicted": pred[pos],
                "scores": scored,
            }

    return {
        "classes": classes,
        "in_sample_accuracy": round(correct / len(df), 3),
        "in_sample_correct": correct, "total": len(df),
        "rule": "predict = argmax over the 10 class scorecards of P(class)",
        "examples": examples,
    }
