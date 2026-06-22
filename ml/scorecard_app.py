"""Interactive OvR scorecard workbench (Streamlit).

A live model-building UI for the one-vs-rest classification challenger — the
SAS/FICO Model-Builder pattern. Pick a target archetype, toggle features, adjust
the WoE binning / regularization / class-weighting, and the Information Value,
WoE bins, points table, KS and AUC all refit live. Then switch to the "combine"
mode to see how the per-class scorecards argmax together into the OvR classifier.

Run it:
    pip install -r ml/requirements.txt
    python -m streamlit run ml/scorecard_app.py
    # use `python -m streamlit` (not bare `streamlit`) — the console script is
    # often not on PATH on Windows. No virtualenv required. Opens localhost:8501.

This is a *workbench* for exploring the challenger — not part of the deterministic
demo path. The frozen panels (docs/scorecard.html, docs/champion-vs-challenger.html)
are the read-only snapshots; this is where you build/tune.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure the repo root is importable so `ml.*` resolves however the app is launched.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ml.challenger import FEATURES
from ml.scorecard import woe_iv, iv_strength, _ks
ARCHETYPES = ["new", "recreational", "regular", "grinder", "aggressive_predatory",
              "promo_hunter", "shared_device_household", "cluster_member",
              "healthy_anchor", "bot_like"]


def truth_of(pid: str) -> str:
    n = int(pid.split("-")[1])
    for hi, lab in [(107, "new"), (141, "recreational"), (163, "regular"),
                    (175, "grinder"), (183, "aggressive_predatory"),
                    (191, "promo_hunter"), (197, "shared_device_household"),
                    (202, "cluster_member"), (220, "healthy_anchor")]:
        if n <= hi:
            return lab
    return "bot_like"


@st.cache_data
def load() -> pd.DataFrame:
    players = json.loads((ROOT / "data" / "players.json").read_text(encoding="utf-8"))["players"]
    df = pd.DataFrame(players)
    df["archetype"] = df["player_id"].map(truth_of)
    df[FEATURES] = df[FEATURES].fillna(df[FEATURES].median())
    return df


def build_card(df, cls, feats, bins, C, balanced, pdo):
    """Fit one WoE-scorecard for class `cls` with the chosen config. Returns a
    dict of IV table, per-feature WoE bins + points, fitted model, probs, KS/AUC."""
    y = (df["archetype"] == cls).astype(int)
    factor = pdo / np.log(2)
    iv, bin_tbl, woe_cols = {}, {}, {}
    for f in feats:
        g, ivf, row = woe_iv(df[f], y, bins=bins)
        iv[f], bin_tbl[f], woe_cols[f] = ivf, g, row
    woe_X = pd.DataFrame(woe_cols)
    cw = "balanced" if balanced else None
    model = LogisticRegression(max_iter=2000, C=C, class_weight=cw)
    model.fit(woe_X.to_numpy(), y.to_numpy())
    coef = dict(zip(feats, model.coef_[0]))
    prob = model.predict_proba(woe_X.to_numpy())[:, 1]
    n_pos = int(y.sum())
    auc = float(roc_auc_score(y, prob)) if n_pos >= 2 else None
    ks = _ks(y.to_numpy(), prob) if n_pos >= 2 else None

    points = {}
    for f in feats:
        rows = []
        for interval, r in bin_tbl[f].iterrows():
            w = float(r["woe"])
            rows.append({"bin": str(interval), "n": int(r["n"]), "in_class": int(r["pos"]),
                         "WoE": round(w, 2), "points": int(round(factor * coef[f] * w))})
        points[f] = rows
    return {"y": y, "prob": prob, "iv": iv, "points": points,
            "coef": coef, "ks": ks, "auc": auc, "n_pos": n_pos, "model": model,
            "woe_cols": woe_cols}


# ── UI ───────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="OvR Scorecard Workbench", page_icon="◆", layout="wide")
df = load()

st.title("◆ OvR Scorecard Workbench")
st.caption("Build & tune the one-vs-rest classification challenger live — WoE · IV · points · KS. "
           "Frozen snapshots live in `docs/scorecard.html`; this is the builder.")

with st.sidebar:
    st.header("Controls")
    mode = st.radio("Mode", ["Single-class scorecard", "Combine all 10 (OvR)"])
    if mode == "Single-class scorecard":
        target = st.selectbox("Target class", ARCHETYPES, index=ARCHETYPES.index("grinder"))
    feats = st.multiselect("Features", FEATURES, default=FEATURES)
    bins = st.slider("WoE bins", 2, 6, 4)
    C = st.select_slider("Regularization C", options=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0], value=1.0)
    balanced = st.checkbox("class_weight = balanced", value=True)
    pdo = st.slider("PDO (points to double odds)", 10, 40, 20, step=5)
    st.divider()
    st.caption("⚠ Synthetic data: classes are near-perfectly separable, so IVs "
               "blow past the textbook scale (weak .02–.1 · strong .3–.5) and KS "
               "hits ~1.0. On real data expect IV .1–.5, KS .3–.6.")

if not feats:
    st.warning("Select at least one feature.")
    st.stop()

if mode == "Single-class scorecard":
    card = build_card(df, target, feats, bins, C, balanced, pdo)
    n = len(df)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("positives", f"{card['n_pos']} / {n}")
    c2.metric("KS", "—" if card["ks"] is None else f"{card['ks']:.2f}")
    c3.metric("AUC", "—" if card["auc"] is None else f"{card['auc']:.2f}")
    c4.metric("features in", len(feats))
    if card["n_pos"] < 4:
        st.warning(f"Only {card['n_pos']} example(s) of '{target}' — WoE bins are unreliable.")

    left, right = st.columns([1, 1.3])
    with left:
        st.subheader("Feature power · Information Value")
        iv_df = (pd.DataFrame({"feature": list(card["iv"]),
                               "IV": [round(v, 3) for v in card["iv"].values()]})
                 .sort_values("IV", ascending=False))
        iv_df["strength"] = iv_df["IV"].map(iv_strength)
        st.altair_chart(
            alt.Chart(iv_df).mark_bar().encode(
                x=alt.X("IV:Q"), y=alt.Y("feature:N", sort="-x"),
                color=alt.Color("strength:N", legend=None),
                tooltip=["feature", "IV", "strength"]).properties(height=28 * len(iv_df)),
            width="stretch")
        st.dataframe(iv_df, hide_index=True, width="stretch")

    with right:
        st.subheader("WoE bins & points")
        topf = max(card["iv"], key=card["iv"].get)
        pick = st.selectbox("Feature", sorted(feats, key=lambda k: card["iv"][k], reverse=True),
                            index=0, key="binfeat")
        pts = pd.DataFrame(card["points"][pick])
        st.altair_chart(
            alt.Chart(pts).mark_bar().encode(
                x=alt.X("bin:N", sort=None, title=f"{pick} bin"),
                y=alt.Y("points:Q"),
                color=alt.condition(alt.datum.points > 0, alt.value("#3fcc6a"), alt.value("#e05c4a")),
                tooltip=["bin", "n", "in_class", "WoE", "points"]).properties(height=200),
            width="stretch")
        st.dataframe(pts, hide_index=True, width="stretch")

    with st.expander("ROC curve & coefficients"):
        if card["auc"] is not None:
            fpr, tpr, _ = roc_curve(card["y"], card["prob"])
            roc = pd.DataFrame({"FPR": fpr, "TPR": tpr})
            st.altair_chart(
                alt.Chart(roc).mark_line(color="#4f8ef7").encode(x="FPR:Q", y="TPR:Q")
                .properties(height=240, title=f"ROC · AUC {card['auc']:.2f}"),
                width="stretch")
        st.dataframe(pd.DataFrame({"feature": list(card["coef"]),
                                   "WoE coef": [round(v, 3) for v in card["coef"].values()]}),
                     hide_index=True, width="stretch")

    st.download_button(
        "⬇ Export this scorecard (JSON)",
        json.dumps({"target": target, "config": {"features": feats, "bins": bins,
                    "C": C, "balanced": balanced, "pdo": pdo},
                    "iv": {k: round(v, 3) for k, v in card["iv"].items()},
                    "ks": card["ks"], "auc": card["auc"], "points": card["points"]}, indent=2),
        file_name=f"scorecard_{target}.json", mime="application/json")

else:  # Combine all 10
    st.subheader("Combine the 10 scorecards → OvR prediction")
    st.caption("Rule: predict = argmax over the 10 class scorecards of P(class). "
               "Each scorecard uses the current sidebar config.")
    cards = {c: build_card(df, c, feats, bins, C, balanced, pdo) for c in ARCHETYPES}
    proba = np.column_stack([cards[c]["prob"] for c in ARCHETYPES])
    pred = [ARCHETYPES[i] for i in proba.argmax(axis=1)]
    truth = df["archetype"].tolist()
    acc = sum(p == t for p, t in zip(pred, truth)) / len(df)

    c1, c2 = st.columns(2)
    c1.metric("in-sample accuracy (this config)", f"{acc:.1%}")
    with c2:
        if st.button("Compute honest leave-one-out (slower)"):
            pipe = make_pipeline(StandardScaler(),
                                 OneVsRestClassifier(LogisticRegression(
                                     max_iter=2000, C=C,
                                     class_weight="balanced" if balanced else None)))
            loo = cross_val_predict(pipe, df[feats].to_numpy(),
                                    df["archetype"].to_numpy(), cv=LeaveOneOut())
            la = (loo == df["archetype"].to_numpy()).mean()
            st.metric("leave-one-out accuracy", f"{la:.1%}",
                      help="Each player predicted by a model that never saw it. "
                           "Compare to the rule champion's 88.5%.")
    st.caption("In-sample is optimistic (scored on the training players). The honest "
               "out-of-sample number is leave-one-out. Rule champion = 88.5%.")

    st.divider()
    st.subheader("Score one player under all 10 scorecards")
    pid = st.selectbox("Player", df["player_id"].tolist(),
                       index=df["player_id"].tolist().index("P-104"))
    pos = df.index[df["player_id"] == pid][0]
    row = df.loc[pos]
    probs = pd.DataFrame({"class": ARCHETYPES, "P(class)": [proba[df.index.get_loc(pos), j]
                          for j in range(len(ARCHETYPES))]}).sort_values("P(class)", ascending=False)
    winner = probs.iloc[0]["class"]
    st.write(f"**{pid}** · truth **{row['archetype']}** → argmax picks **{winner}** "
             + ("✅" if winner == row["archetype"] else "❌"))
    probs["is_winner"] = probs["class"] == winner
    st.altair_chart(
        alt.Chart(probs).mark_bar().encode(
            x=alt.X("P(class):Q"), y=alt.Y("class:N", sort="-x"),
            color=alt.condition(alt.datum.is_winner, alt.value("#4f8ef7"), alt.value("#2b4231")),
            tooltip=["class", "P(class)"]).properties(height=28 * len(ARCHETYPES)),
        width="stretch")
