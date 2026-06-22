"""Interactive OvR scorecard MODEL BUILDER (Streamlit).

A guided, stage-by-stage workbench for building the one-vs-rest classification
challenger — modeled on the FICO Model Builder scorecard workflow:

    1 Target → 2 Binning → 3 WoE → 4 IV & selection → 5 Fit → 6 Points
    → 7 Validation → 8 Combine (one-vs-rest)

Each stage explains what it does, shows the artifact for that step on the real
122-player data, and carries your choices forward. Stage 8 assembles the 10
per-class scorecards into the full classifier and scores it.

Run it:
    pip install -r ml/requirements.txt
    python -m streamlit run ml/scorecard_app.py
    # use `python -m streamlit` (not bare `streamlit`) — the console script is
    # often not on PATH on Windows. No virtualenv required. Opens localhost:8501.

This is a *workbench* for building/exploring the challenger — not part of the
deterministic demo path. The frozen panels (docs/scorecard.html,
docs/champion-vs-challenger.html) are the read-only snapshots.
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

STEPS = ["Target", "Binning", "Weight of Evidence", "Info Value & selection",
         "Fit logistic", "Scale to points", "Validation", "Combine (OvR)"]
STEP_LABELS = [f"{i+1}. {s}" for i, s in enumerate(STEPS)]


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


@st.cache_data
def feature_tables(target: str, bins: int):
    """Per-feature WoE/IV table + row-WoE for the binary 'is target' problem."""
    df = load()
    y = (df["archetype"] == target).astype(int)
    out = {}
    for f in FEATURES:
        g, iv, row = woe_iv(df[f], y, bins=bins)
        out[f] = {"table": g, "iv": iv, "row_woe": row}
    return out, y


def fit_card(target, bins, feats, C, balanced):
    tables, y = feature_tables(target, bins)
    woe_X = pd.DataFrame({f: tables[f]["row_woe"] for f in feats})
    model = LogisticRegression(max_iter=2000, C=C,
                               class_weight="balanced" if balanced else None)
    model.fit(woe_X.to_numpy(), y.to_numpy())
    prob = model.predict_proba(woe_X.to_numpy())[:, 1]
    return tables, y, model, prob, dict(zip(feats, model.coef_[0]))


# ── session state ────────────────────────────────────────────────────────────
st.set_page_config(page_title="OvR Scorecard Model Builder", page_icon="◆", layout="wide")
ss = st.session_state
ss.setdefault("step", 0)
ss.setdefault("target", "grinder")
ss.setdefault("bins", 4)
ss.setdefault("kept", list(FEATURES))
ss.setdefault("C", 1.0)
ss.setdefault("balanced", True)
ss.setdefault("pdo", 20)
ss.setdefault("nav_radio", STEP_LABELS[0])


def goto(i: int) -> None:
    """Single source of truth for the active stage — keeps the jump radio in sync
    so it never fights the Back/Next buttons."""
    i = max(0, min(len(STEPS) - 1, i))
    ss.step = i
    ss.nav_radio = STEP_LABELS[i]


def on_jump() -> None:
    ss.step = STEP_LABELS.index(ss.nav_radio)

df = load()
N = len(STEPS)
factor = ss.pdo / np.log(2)


def stepper_html(active: int) -> str:
    cells = ""
    for i, name in enumerate(STEPS):
        done = i < active
        cur = i == active
        bg = "#1f3c25" if cur else ("#0e1c12" if done else "transparent")
        col = "#c9a84c" if cur else ("#3fcc6a" if done else "#3a553f")
        bd = "#c9a84c" if cur else "#182d1c"
        mark = "✓" if done else str(i + 1)
        cells += (f'<div style="flex:1;text-align:center;padding:6px 4px;border-bottom:2px solid {bd};'
                  f'background:{bg}">'
                  f'<div style="font-family:monospace;font-size:10px;color:{col};font-weight:700">{mark}</div>'
                  f'<div style="font-size:10px;color:{col};line-height:1.25">{name}</div></div>')
    return f'<div style="display:flex;gap:3px;margin:4px 0 18px">{cells}</div>'


# ── header + stepper ─────────────────────────────────────────────────────────
st.markdown("### ◆ OvR Scorecard Model Builder")
st.caption("Build the classification challenger the FICO Model-Builder way — one stage at a time, "
           "on the real 122-player data. Target: **one-vs-rest** logistic scorecards.")
st.markdown(stepper_html(ss.step), unsafe_allow_html=True)

with st.sidebar:
    st.subheader("Current model")
    st.write(f"**Target:** `{ss.target}`")
    st.write(f"**Bins:** {ss.bins}  ·  **C:** {ss.C}  ·  **PDO:** {ss.pdo}")
    st.write(f"**Characteristics:** {len(ss.kept)}/{len(FEATURES)}")
    st.divider()
    st.radio("Jump to stage", STEP_LABELS, key="nav_radio", on_change=on_jump)
    st.divider()
    st.caption("⚠ Synthetic data: classes are near-perfectly separable, so IVs blow past the "
               "textbook scale (weak .02–.1 · strong .3–.5) and KS hits ~1.0. On real data expect "
               "IV .1–.5, KS .3–.6.")

step = ss.step
y = (df["archetype"] == ss.target).astype(int)
n_pos = int(y.sum())

# ── STEP 1 · TARGET ──────────────────────────────────────────────────────────
if step == 0:
    st.subheader("1 · Define the target (score formula)")
    st.write("One-vs-rest builds **one yes/no model per archetype**. Pick the class to model — "
             "every player is either that class (**good = 1**) or not (**bad = 0**). Repeat for all "
             "10 in the final stage.")
    ss.target = st.selectbox("Target archetype", ARCHETYPES, index=ARCHETYPES.index(ss.target))
    y = (df["archetype"] == ss.target).astype(int)
    n_pos = int(y.sum())
    c1, c2, c3 = st.columns(3)
    c1.metric("in-class (good = 1)", n_pos)
    c2.metric("rest (bad = 0)", len(df) - n_pos)
    c3.metric("base rate", f"{n_pos/len(df):.1%}")
    if n_pos < 4:
        st.warning(f"Only {n_pos} example(s) of `{ss.target}` — a scorecard on this class is "
                   "unreliable (you can't bin 1 positive). Real-world classes need more cases.")
    st.altair_chart(alt.Chart(pd.DataFrame(
        {"label": ["in-class", "rest"], "n": [n_pos, len(df) - n_pos]})).mark_bar().encode(
        x="n:Q", y=alt.Y("label:N", sort="-x"),
        color=alt.Color("label:N", legend=None)).properties(height=90), width="stretch")

# ── STEP 2 · BINNING ─────────────────────────────────────────────────────────
elif step == 1:
    st.subheader("2 · Bin the characteristics (fine classing)")
    st.write("Each numeric characteristic is cut into ranges (**bins**). Binning tames outliers and "
             "lets each range carry its own risk. More bins = finer detail but less stability.")
    ss.bins = st.slider("Number of bins per characteristic", 2, 6, ss.bins)
    tables, _ = feature_tables(ss.target, ss.bins)
    pick = st.selectbox("Inspect a characteristic", FEATURES,
                        index=FEATURES.index("aggression_factor"))
    g = tables[pick]["table"].reset_index()
    g = g.rename(columns={g.columns[0]: "bin"})
    show = g[["bin", "n", "pos", "neg"]].copy()
    show["bin"] = show["bin"].astype(str)
    show = show.rename(columns={"pos": "in-class", "neg": "rest"})
    st.dataframe(show, hide_index=True, width="stretch")
    st.altair_chart(alt.Chart(show).transform_fold(["in-class", "rest"]).mark_bar().encode(
        x=alt.X("bin:N", sort=None), y="value:Q", color="key:N").properties(height=200),
        width="stretch")

# ── STEP 3 · WOE ─────────────────────────────────────────────────────────────
elif step == 2:
    st.subheader("3 · Weight of Evidence (WoE)")
    st.write("Replace each bin with a single number: **WoE = ln( %in-class / %rest )**. Positive = "
             "the range leans toward the class; negative = away. This is the binary-native transform "
             "one-vs-rest is built for.")
    tables, _ = feature_tables(ss.target, ss.bins)
    pick = st.selectbox("Characteristic", FEATURES, index=FEATURES.index("aggression_factor"))
    g = tables[pick]["table"].reset_index()
    g = g.rename(columns={g.columns[0]: "bin"})
    g["bin"] = g["bin"].astype(str)
    g["WoE"] = g["woe"].round(2)
    st.altair_chart(alt.Chart(g).mark_bar().encode(
        x=alt.X("bin:N", sort=None), y="WoE:Q",
        color=alt.condition(alt.datum.WoE > 0, alt.value("#3fcc6a"), alt.value("#e05c4a")),
        tooltip=["bin", "n", "WoE"]).properties(height=220,
        title=f"WoE by bin · {pick}"), width="stretch")
    st.dataframe(g[["bin", "n", "WoE"]], hide_index=True, width="stretch")

# ── STEP 4 · IV & SELECTION ──────────────────────────────────────────────────
elif step == 3:
    st.subheader("4 · Information Value & characteristic selection")
    st.write("**IV = Σ (%in-class − %rest)·WoE** scores how well a whole characteristic separates the "
             "class. Rank by IV, keep the strong ones, drop dead weight. Selected characteristics go "
             "into the model.")
    tables, _ = feature_tables(ss.target, ss.bins)
    iv_df = pd.DataFrame({"characteristic": FEATURES,
                          "IV": [round(tables[f]["iv"], 3) for f in FEATURES]}
                         ).sort_values("IV", ascending=False)
    iv_df["strength"] = iv_df["IV"].map(iv_strength)
    st.altair_chart(alt.Chart(iv_df).mark_bar().encode(
        x="IV:Q", y=alt.Y("characteristic:N", sort="-x"),
        color=alt.Color("strength:N", legend=None),
        tooltip=["characteristic", "IV", "strength"]).properties(height=30 * len(iv_df)),
        width="stretch")
    ss.kept = st.multiselect("Characteristics to keep in the model", FEATURES,
                             default=[f for f in iv_df["characteristic"] if f in ss.kept])
    st.dataframe(iv_df, hide_index=True, width="stretch")

# ── STEP 5 · FIT ─────────────────────────────────────────────────────────────
elif step == 4:
    st.subheader("5 · Fit the logistic regression")
    st.write("Fit a logistic model on the **WoE-transformed** selected characteristics. The "
             "coefficients say how much each characteristic moves the score. `C` is regularization "
             "(smaller = simpler); balanced class-weights help the rarer in-class group.")
    if not ss.kept:
        st.warning("No characteristics selected — go back to stage 4.")
        st.stop()
    c1, c2 = st.columns(2)
    ss.C = c1.select_slider("Regularization C", [0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0], value=ss.C)
    ss.balanced = c2.checkbox("class_weight = balanced", value=ss.balanced)
    _, _, model, prob, coef = fit_card(ss.target, ss.bins, ss.kept, ss.C, ss.balanced)
    cf = (pd.DataFrame({"characteristic": list(coef), "WoE coef": [round(v, 3) for v in coef.values()]})
          .sort_values("WoE coef", key=lambda s: s.abs(), ascending=False))
    st.altair_chart(alt.Chart(cf).mark_bar().encode(
        x="WoE coef:Q", y=alt.Y("characteristic:N", sort="-x"),
        color=alt.condition(alt.datum["WoE coef"] > 0, alt.value("#3fcc6a"), alt.value("#e05c4a")),
        tooltip=["characteristic", "WoE coef"]).properties(height=30 * len(cf)), width="stretch")
    st.dataframe(cf, hide_index=True, width="stretch")

# ── STEP 6 · POINTS ──────────────────────────────────────────────────────────
elif step == 5:
    st.subheader("6 · Scale to points (the scorecard)")
    st.write("Turn the fit into an auditable **points table**: `points = coef × WoE × factor`, where "
             "`factor = PDO / ln 2`. Every bin gets integer points; **+ pushes toward the class**. "
             "A player's score is the sum of their bins' points.")
    if not ss.kept:
        st.warning("No characteristics selected — go back to stage 4.")
        st.stop()
    ss.pdo = st.slider("PDO (points to double the odds)", 10, 40, ss.pdo, step=5)
    factor = ss.pdo / np.log(2)
    tables, _, model, prob, coef = fit_card(ss.target, ss.bins, ss.kept, ss.C, ss.balanced)
    rows = []
    for f in ss.kept:
        g = tables[f]["table"]
        for interval, r in g.iterrows():
            rows.append({"characteristic": f, "bin": str(interval), "n": int(r["n"]),
                         "WoE": round(float(r["woe"]), 2),
                         "points": int(round(factor * coef[f] * float(r["woe"])))})
    sc = pd.DataFrame(rows)
    st.dataframe(sc, hide_index=True, width="stretch",
                 column_config={"points": st.column_config.NumberColumn("points", format="%+d")})
    st.download_button("⬇ Export scorecard (JSON)",
                       json.dumps({"target": ss.target, "pdo": ss.pdo,
                                   "config": {"bins": ss.bins, "C": ss.C,
                                              "balanced": ss.balanced, "characteristics": ss.kept},
                                   "scorecard": rows}, indent=2),
                       file_name=f"scorecard_{ss.target}.json", mime="application/json")

# ── STEP 7 · VALIDATION ──────────────────────────────────────────────────────
elif step == 6:
    st.subheader("7 · Validate (separation: KS · AUC · ROC)")
    st.write("How cleanly does the scorecard separate in-class from rest? **KS** = biggest gap between "
             "the two score distributions; **AUC** = ranking quality. (Development sample — in-sample.)")
    if not ss.kept:
        st.warning("No characteristics selected — go back to stage 4.")
        st.stop()
    _, yv, model, prob, _ = fit_card(ss.target, ss.bins, ss.kept, ss.C, ss.balanced)
    yv = yv.to_numpy()
    if n_pos >= 2:
        c1, c2, c3 = st.columns(3)
        c1.metric("KS", f"{_ks(yv, prob):.2f}")
        c2.metric("AUC", f"{roc_auc_score(yv, prob):.2f}")
        c3.metric("in-class / total", f"{n_pos}/{len(df)}")
        fpr, tpr, _ = roc_curve(yv, prob)
        st.altair_chart(alt.Chart(pd.DataFrame({"FPR": fpr, "TPR": tpr})).mark_line(
            color="#4f8ef7").encode(x="FPR:Q", y="TPR:Q").properties(
            height=240, title="ROC curve"), width="stretch")
        dist = pd.DataFrame({"score": prob, "group": np.where(yv == 1, "in-class", "rest")})
        st.altair_chart(alt.Chart(dist).mark_bar(opacity=0.6).encode(
            x=alt.X("score:Q", bin=alt.Bin(maxbins=20)), y="count()",
            color="group:N").properties(height=180, title="Score distribution"), width="stretch")
    else:
        st.warning(f"Only {n_pos} in-class example — not enough to validate.")

# ── STEP 8 · COMBINE ─────────────────────────────────────────────────────────
elif step == 7:
    st.subheader("8 · Combine the 10 scorecards (one-vs-rest)")
    st.write("Build the scorecard for **all 10** classes with the current settings, then predict each "
             "player by **argmax** — the class whose scorecard scores them highest. That ensemble is "
             "the OvR challenger.")
    feats = ss.kept if ss.kept else list(FEATURES)
    probs = np.column_stack([
        fit_card(c, ss.bins, feats, ss.C, ss.balanced)[3] for c in ARCHETYPES])
    pred = np.array(ARCHETYPES)[probs.argmax(axis=1)]
    truth = df["archetype"].to_numpy()
    acc = float((pred == truth).mean())

    c1, c2 = st.columns(2)
    c1.metric("in-sample accuracy (this config)", f"{acc:.1%}")
    with c2:
        if st.button("Compute honest leave-one-out (slower)"):
            pipe = make_pipeline(StandardScaler(), OneVsRestClassifier(LogisticRegression(
                max_iter=2000, C=ss.C, class_weight="balanced" if ss.balanced else None)))
            loo = cross_val_predict(pipe, df[feats].to_numpy(), truth, cv=LeaveOneOut())
            st.metric("leave-one-out accuracy", f"{(loo == truth).mean():.1%}",
                      help="Each player predicted by a model that never saw it. Rule champion = 88.5%.")
    st.caption("In-sample is optimistic. The honest out-of-sample number is leave-one-out; "
               "the rule champion scores **88.5%**. See docs/champion-vs-challenger.html.")

    st.divider()
    pid = st.selectbox("Score one player under all 10 scorecards",
                       df["player_id"].tolist(), index=df["player_id"].tolist().index("P-104"))
    pos = df.index.get_loc(df.index[df["player_id"] == pid][0])
    pr = pd.DataFrame({"class": ARCHETYPES, "P(class)": probs[pos]}).sort_values(
        "P(class)", ascending=False)
    winner = pr.iloc[0]["class"]
    pr["is_winner"] = pr["class"] == winner
    st.write(f"**{pid}** · truth **{df.iloc[pos]['archetype']}** → argmax picks **{winner}** "
             + ("✅" if winner == df.iloc[pos]["archetype"] else "❌"))
    st.altair_chart(alt.Chart(pr).mark_bar().encode(
        x="P(class):Q", y=alt.Y("class:N", sort="-x"),
        color=alt.condition(alt.datum.is_winner, alt.value("#4f8ef7"), alt.value("#2b4231")),
        tooltip=["class", "P(class)"]).properties(height=28 * len(ARCHETYPES)), width="stretch")

# ── nav ──────────────────────────────────────────────────────────────────────
st.divider()
b1, b2, b3 = st.columns([1, 6, 1])
b1.button("← Back", disabled=step == 0, width="stretch", on_click=goto, args=(step - 1,))
b2.markdown(f"<div style='text-align:center;color:#3a553f;font-size:12px;padding-top:6px'>"
            f"Stage {step+1} of {N} · {STEPS[step]}</div>", unsafe_allow_html=True)
b3.button("Next →", disabled=step == N - 1, width="stretch", on_click=goto, args=(step + 1,))
