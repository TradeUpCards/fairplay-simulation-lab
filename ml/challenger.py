"""Classification challenger — interpretable one-vs-rest logistic regression.

The ML "challenger" for score ① (classification), raced against the
threshold-rule **champion** in `scoring/classify.py`. Per the kickoff (§2 ①,
§4) and `docs/learn/ovr-notebook.ipynb`, the recommended challenger is
**one-vs-rest binary logistic regression** — it keeps the scorecard control
surface (each class is a yes/no model whose coefficients ARE the reason codes).

Honest evaluation: this trains ONLY on the 9 numeric **behavioral** features
(never the structural membership fields `cluster_id` / `household_id` /
`bot_similarity_score` that make the champion's structural classes trivial). So
the comparison is "rules-with-structural-shortcuts vs ML-on-behavior" — which is
exactly the interesting question.

Determinism: LBFGS logistic + StandardScaler + leave-one-out CV have no random
component, so predictions are reproducible without a seed.

Requires: scikit-learn, pandas, numpy (NOT part of the stdlib-only scoring core).
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

# The 9 numeric behavioral features (kickoff §2 ①; same as the OvR notebook).
FEATURES = [
    "registered_days_ago", "lifetime_hands", "avg_session_minutes",
    "sessions_last_30d", "vpip", "pfr", "aggression_factor",
    "avg_pot_size_bb", "promo_redemptions_30d",
]


def _pipeline() -> Any:
    """OvR logistic: scale → 9 one-vs-rest binary logistic models."""
    return make_pipeline(
        StandardScaler(),
        OneVsRestClassifier(
            LogisticRegression(max_iter=2000, class_weight="balanced"),
        ),
    )


def build_frame(players: list[Mapping[str, Any]],
                truth_of) -> pd.DataFrame:
    """DataFrame of features + truth label, median-imputed like the notebook.

    ``truth_of(player_id) -> archetype`` supplies the ground-truth label."""
    df = pd.DataFrame(players)
    df["archetype"] = df["player_id"].map(truth_of)
    df[FEATURES] = df[FEATURES].fillna(df[FEATURES].median())
    return df


def leave_one_out_predictions(df: pd.DataFrame) -> np.ndarray:
    """Honest per-player predictions: each player classified by a model trained
    on the other 121. Classes with a single example (e.g. ``bot_like``) are
    therefore unlearnable when held out — an intentional, surfaced limitation."""
    X = df[FEATURES].to_numpy()
    y = df["archetype"].to_numpy()
    return cross_val_predict(_pipeline(), X, y, cv=LeaveOneOut())


def fit_full(df: pd.DataFrame) -> Any:
    """Fit on all rows — used only to read learned coefficients (interpretability)."""
    pipe = _pipeline()
    pipe.fit(df[FEATURES].to_numpy(), df["archetype"].to_numpy())
    return pipe


def coefficients(pipe: Any, top_n: int = 4) -> dict[str, list[dict[str, Any]]]:
    """Per-class learned weights — the challenger's 'reason codes'.

    Returns ``{archetype: [{feature, weight}, ...]}`` with the strongest
    ``top_n`` signed weights per class (positive pushes toward the class)."""
    ovr = pipe.named_steps["onevsrestclassifier"]
    classes = list(ovr.classes_)
    out: dict[str, list[dict[str, Any]]] = {}
    for i, cls in enumerate(classes):
        est = ovr.estimators_[i]
        weights = est.coef_[0]
        order = np.argsort(np.abs(weights))[::-1][:top_n]
        out[cls] = [{"feature": FEATURES[j], "weight": round(float(weights[j]), 2)}
                    for j in order]
    return out
