"""FairPlay Model Builder — a FICO-Model-Builder-style scorecard workbench (Streamlit).

Builds the one-vs-rest classification challenger the way FICO Model Builder
builds a credit scorecard, recreated within Streamlit's constraints:

  • Project-tree sidebar (datasets / models / binning libraries / reports)
  • Data Set Editor — binary good/bad target mapping + build the model
  • Scorecard Editor — selected-variable list + relative-importance chart
  • Interactive Binner — per-variable WoE plot + editable (coarse-class) bins
  • Reports — Performance (KS/ROC vs Champion), Training, Fit-Odds
  • Combine (OvR) — assemble the 10 scorecards into the classifier
  • Console / Jobs — a running log of modeling actions

Streamlit is a web-app framework, not a dockable desktop IDE, so the panes are
approximated with a tree sidebar + tabbed main area + a console expander; the
*workflow* matches FICO even if the window chrome can't.

Run:
    pip install -r ml/requirements.txt
    python -m streamlit run ml/scorecard_app.py
    # use `python -m streamlit` (not bare `streamlit`) — the console script is
    # often not on PATH on Windows. No virtualenv required. Opens localhost:8501.

A workbench for building/exploring the challenger — not part of the deterministic
demo path. Frozen read-only snapshots live in docs/scorecard.html and
docs/champion-vs-challenger.html.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

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
DEFAULT_BINS = 4


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


def divergence(prob: np.ndarray, y: np.ndarray) -> float:
    """Separation between Good/Bad score distributions (FICO 'divergence')."""
    g, b = prob[y == 1], prob[y == 0]
    if len(g) < 2 or len(b) < 2:
        return float("nan")
    return float((g.mean() - b.mean()) ** 2 / (0.5 * (g.var() + b.var()) + 1e-9))


def build_model(df: pd.DataFrame, target: str, var_bins: dict[str, int],
                selected: list[str], C: float, balanced: bool) -> dict:
    """Fit a WoE-scorecard for the binary 'is target' problem on the selected
    variables with their per-variable bin counts."""
    y = (df["archetype"] == target).astype(int)
    cols, ivs, tables = {}, {}, {}
    for f in selected:
        g, iv, row = woe_iv(df[f], y, bins=var_bins.get(f, DEFAULT_BINS))
        cols[f], ivs[f], tables[f] = row, iv, g
    X = pd.DataFrame(cols)
    model = LogisticRegression(max_iter=2000, C=C,
                               class_weight="balanced" if balanced else None)
    model.fit(X.to_numpy(), y.to_numpy())
    prob = model.predict_proba(X.to_numpy())[:, 1]
    yv = y.to_numpy()
    return dict(model=model, prob=prob, y=yv, ivs=ivs, tables=tables,
                coef=dict(zip(selected, model.coef_[0])),
                intercept=float(model.intercept_[0]),
                ks=_ks(yv, prob) if y.sum() >= 2 else float("nan"),
                auc=roc_auc_score(yv, prob) if y.sum() >= 2 else float("nan"),
                divergence=divergence(prob, yv), n_pos=int(y.sum()))


@st.cache_data
def champion(target: str) -> dict:
    """Champion baseline = the auto-built default model (all variables, 4 bins).
    The user's edits become the Challenger, compared against this."""
    return build_model(load(), target, {}, list(FEATURES), 1.0, True)


def log(msg: str) -> None:
    st.session_state.jobs.insert(0, msg)


# ── state ────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="FairPlay Model Builder", page_icon="◆", layout="wide")
ss = st.session_state
ss.setdefault("target", "grinder")
ss.setdefault("model_name", "grinder_GB_scorecard")
ss.setdefault("selected", list(FEATURES))
ss.setdefault("var_bins", {})         # per-variable bin-count overrides
ss.setdefault("C", 1.0)
ss.setdefault("balanced", True)
ss.setdefault("pdo", 20)
ss.setdefault("jobs", ["[session started] workspace: fairplay-archetypes"])

df = load()

# ── sidebar: project tree + model config ─────────────────────────────────────
with st.sidebar:
    st.markdown("### ◆ FairPlay Model Builder")
    sel_n, tot_n = len(ss.selected), len(FEATURES)
    st.markdown(
        f"""<div style='font-family:monospace;font-size:12px;line-height:1.9;color:#7a9c80'>
        📁 <b style='color:#c9a84c'>fairplay-archetypes</b><br>
        &nbsp;├─ 📁 datasets<br>
        &nbsp;│&nbsp;&nbsp;└─ 📄 players <span style='color:#3a553f'>(122)</span><br>
        &nbsp;├─ 📁 models<br>
        &nbsp;│&nbsp;&nbsp;└─ 📄 <b style='color:#d8ecda'>{ss.model_name}</b><br>
        &nbsp;├─ 📁 binning-libraries<br>
        &nbsp;│&nbsp;&nbsp;└─ 📄 {ss.target} <span style='color:#3a553f'>({sel_n}/{tot_n} vars)</span><br>
        &nbsp;└─ 📁 reports
        </div>""", unsafe_allow_html=True)
    st.divider()
    st.caption("MODEL CONFIG")
    new_target = st.selectbox("Target class (one-vs-rest)", ARCHETYPES,
                              index=ARCHETYPES.index(ss.target))
    if new_target != ss.target:
        ss.target = new_target
        ss.model_name = f"{new_target}_GB_scorecard"
        ss.selected = list(FEATURES)
        ss.var_bins = {}
        log(f"[target] switched to '{new_target}' — model reset")
        st.rerun()
    ss.model_name = st.text_input("Model name", ss.model_name)
    ss.C = st.select_slider("Regularization C", [0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0], value=ss.C)
    ss.balanced = st.checkbox("class_weight = balanced", value=ss.balanced)
    ss.pdo = st.slider("PDO (points to double odds)", 10, 40, ss.pdo, step=5)
    st.divider()
    st.caption("⚠ Synthetic data: classes are near-separable, so IV/KS are inflated "
               "(real-world IV .1–.5, KS .3–.6).")

target = ss.target
y_full = (df["archetype"] == target).astype(int)
n_pos = int(y_full.sum())

# Build the current (Challenger) model + the Champion baseline.
chal = build_model(df, target, ss.var_bins, ss.selected, ss.C, ss.balanced) if ss.selected else None
champ = champion(target)
factor = ss.pdo / np.log(2)

st.markdown(f"#### Scorecard Model Editor — *{ss.model_name}*  "
            f"<span style='color:#7a9c80;font-size:13px'>· target `{target}` (Good/Bad) · "
            f"binary one-vs-rest</span>", unsafe_allow_html=True)

tabs = st.tabs(["📊 Data Set Editor", "🗂 Scorecard Editor", "🔬 Interactive Binner",
                "📈 Reports", "🧩 Combine (OvR)"])

# ── TAB 1 · DATA SET EDITOR ──────────────────────────────────────────────────
with tabs[0]:
    st.markdown("**Binary target mapping** — one-vs-rest maps the 10-way archetype label to a "
                f"`Good/Bad` target: **Good = is `{target}`**, **Bad = every other archetype**.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Good (in-class)", n_pos)
    c2.metric("Bad (rest)", len(df) - n_pos)
    c3.metric("base rate", f"{n_pos/len(df):.1%}")
    if n_pos < 4:
        st.warning(f"Only {n_pos} Good case(s) for '{target}' — binning/scorecard is unreliable "
                   "(can't bin one positive). Real classes need more cases.")
    st.altair_chart(alt.Chart(pd.DataFrame({"class": ["Good (in-class)", "Bad (rest)"],
                    "n": [n_pos, len(df) - n_pos]})).mark_bar().encode(
        x="n:Q", y=alt.Y("class:N", sort="-x"),
        color=alt.Color("class:N", legend=None)).properties(height=110), width="stretch")
    st.caption("Candidate predictors (binning library) — the 9 behavioural features. The auto-built "
               "Champion uses every variable at 4 bins; edit in the Scorecard Editor and Interactive "
               "Binner to build your Challenger.")
    st.dataframe(pd.DataFrame({"predictor": FEATURES,
                 "in model": [f in ss.selected for f in FEATURES],
                 "bins": [ss.var_bins.get(f, DEFAULT_BINS) for f in FEATURES]}),
                 hide_index=True, width="stretch")

# ── TAB 2 · SCORECARD EDITOR ─────────────────────────────────────────────────
with tabs[1]:
    st.markdown("**Selected variables & relative importance** — each predictor's marginal "
                "contribution (Information Value) to the model's total separation. Toggle variables "
                "to do stepwise selection.")
    all_iv = {f: woe_iv(df[f], y_full, bins=ss.var_bins.get(f, DEFAULT_BINS))[1] for f in FEATURES}
    total_iv = sum(all_iv[f] for f in ss.selected) if ss.selected else 0.0
    new_sel = st.multiselect("Variables in the model (stepwise selection)", FEATURES, default=ss.selected)
    if new_sel != ss.selected:
        ss.selected = new_sel
        log(f"[stepwise] model now uses {len(new_sel)} variable(s)")
        st.rerun()

    if ss.selected and chal:
        imp = (pd.DataFrame({"predictor": ss.selected,
                             "contribution": [round(all_iv[f], 3) for f in ss.selected],
                             "weight": [round(chal["coef"][f], 3) for f in ss.selected]})
               .sort_values("contribution", ascending=False))
        imp["strength"] = imp["contribution"].map(iv_strength)
        cL, cR = st.columns([1.1, 1])
        with cL:
            st.caption(f"Total contribution (Σ IV) = **{total_iv:.2f}** across {len(ss.selected)} variables")
            st.dataframe(imp, hide_index=True, width="stretch")
        with cR:
            st.altair_chart(alt.Chart(imp).mark_bar().encode(
                x=alt.X("contribution:Q", title="marginal contribution (IV)"),
                y=alt.Y("predictor:N", sort="-x"),
                color=alt.Color("strength:N", legend=None),
                tooltip=["predictor", "contribution", "weight", "strength"]
            ).properties(height=34 * len(imp), title="Relative importance"), width="stretch")
        m1, m2, m3 = st.columns(3)
        m1.metric("KS", f"{chal['ks']:.2f}" if not np.isnan(chal['ks']) else "—")
        m2.metric("AUC", f"{chal['auc']:.2f}" if not np.isnan(chal['auc']) else "—")
        m3.metric("divergence", f"{chal['divergence']:.2f}" if not np.isnan(chal['divergence']) else "—")
    else:
        st.warning("No variables selected — add at least one above.")

# ── TAB 3 · INTERACTIVE BINNER ───────────────────────────────────────────────
with tabs[2]:
    st.markdown("**Interactive Binner** — inspect a variable's bins and Weight-of-Evidence, and "
                "**coarse-class** it by changing the bin count. Fewer bins = coarser/smoother; watch "
                "the WoE trend and IV update.")
    var = st.selectbox("Variable", FEATURES,
                       index=FEATURES.index(ss.selected[0]) if ss.selected else 0)
    cur_bins = ss.var_bins.get(var, DEFAULT_BINS)
    nb = st.slider(f"Bins for `{var}` (coarse classing)", 2, 8, cur_bins, key=f"bin_{var}")
    if nb != cur_bins:
        ss.var_bins[var] = nb
        log(f"[binner] '{var}' re-binned to {nb} bins")
        st.rerun()

    g, iv, _ = woe_iv(df[var], y_full, bins=nb)
    gt = g.reset_index().rename(columns={g.reset_index().columns[0]: "bin"})
    gt["bin"] = gt["bin"].astype(str)
    gt["WoE"] = gt["woe"].round(2)
    coef_v = chal["coef"].get(var, 0.0) if chal else 0.0
    gt["points"] = [int(round(factor * coef_v * w)) for w in gt["woe"]]
    gt = gt.rename(columns={"pos": "Good", "neg": "Bad"})
    woes = list(gt["WoE"])
    mono = (all(woes[i] <= woes[i+1] for i in range(len(woes)-1)) or
            all(woes[i] >= woes[i+1] for i in range(len(woes)-1)))
    c1, c2, c3 = st.columns(3)
    c1.metric(f"IV ({var})", f"{iv:.3f}", iv_strength(iv), delta_color="off")
    c2.metric("WoE monotonic?", "yes ✓" if mono else "no ✗",
              help="Monotonic WoE across bins is usually preferred; try fewer bins if not.")
    c3.metric("in model", "yes" if var in ss.selected else "no")
    cL, cR = st.columns([1, 1])
    with cL:
        st.altair_chart(alt.Chart(gt).mark_bar().encode(
            x=alt.X("bin:N", sort=None), y="WoE:Q",
            color=alt.condition(alt.datum.WoE > 0, alt.value("#46c98b"), alt.value("#e05c4a")),
            tooltip=["bin", "n", "Good", "Bad", "WoE"]).properties(height=240,
            title=f"Weight of Evidence · {var}"), width="stretch")
    with cR:
        st.dataframe(gt[["bin", "n", "Good", "Bad", "WoE", "points"]], hide_index=True,
                     width="stretch")
    if not mono:
        st.info("WoE is non-monotonic across these bins — coarser bins often restore a clean trend.")

# ── TAB 4 · REPORTS ──────────────────────────────────────────────────────────
with tabs[3]:
    st.markdown("**Reports** — Challenger (your edited model) vs **Champion** (auto-built: all "
                "variables, 4 bins). " + ("" if n_pos >= 2 else "⚠ Too few Good cases to report."))
    if n_pos >= 2 and ss.selected and chal:
        rtabs = st.tabs(["Performance (KS / ROC)", "Model Training", "Fit Odds"])
        with rtabs[0]:
            cc = pd.DataFrame({
                "model": ["Challenger", "Champion"],
                "KS": [round(chal["ks"], 3), round(champ["ks"], 3)],
                "AUC": [round(chal["auc"], 3), round(champ["auc"], 3)],
                "divergence": [round(chal["divergence"], 3), round(champ["divergence"], 3)],
                "variables": [len(ss.selected), len(FEATURES)]})
            st.dataframe(cc, hide_index=True, width="stretch")
            roc_rows = []
            for name, m in [("Challenger", chal), ("Champion", champ)]:
                fpr, tpr, _ = roc_curve(m["y"], m["prob"])
                roc_rows.append(pd.DataFrame({"FPR": fpr, "TPR": tpr, "model": name}))
            st.altair_chart(alt.Chart(pd.concat(roc_rows)).mark_line().encode(
                x="FPR:Q", y="TPR:Q", color="model:N").properties(
                height=260, title="ROC — Challenger vs Champion"), width="stretch")
            d = pd.DataFrame({"p": chal["prob"], "y": chal["y"]}).sort_values("p")
            d["cum_good"] = (d.y == 1).cumsum() / max((d.y == 1).sum(), 1)
            d["cum_bad"] = (d.y == 0).cumsum() / max((d.y == 0).sum(), 1)
            d["pct"] = np.linspace(0, 1, len(d))
            ksdf = pd.concat([d.assign(curve="good", v=d.cum_good),
                              d.assign(curve="bad", v=d.cum_bad)])
            st.altair_chart(alt.Chart(ksdf).mark_line().encode(
                x=alt.X("pct:Q", title="population sorted by score"),
                y=alt.Y("v:Q", title="cumulative"), color="curve:N").properties(
                height=220, title=f"KS curve · Challenger KS = {chal['ks']:.2f}"),
                width="stretch")
        with rtabs[1]:
            st.caption("Selected vs candidate variables, contribution (IV), and model weights.")
            st.dataframe(pd.DataFrame({"variable": FEATURES,
                "selected": [f in ss.selected for f in FEATURES],
                "contribution (IV)": [round(all_iv[f], 3) for f in FEATURES],
                "bins": [ss.var_bins.get(f, DEFAULT_BINS) for f in FEATURES],
                "weight": [round(chal["coef"].get(f, float("nan")), 3) for f in FEATURES]}),
                hide_index=True, width="stretch")
            st.caption(f"Score statistics — KS {chal['ks']:.3f} · AUC {chal['auc']:.3f} · "
                       f"divergence {chal['divergence']:.3f} · intercept {chal['intercept']:.3f} · "
                       f"base points {int(round(100 + factor*chal['intercept']))}")
        with rtabs[2]:
            st.caption("Fit Odds — does the score line up linearly with the actual log-odds? "
                       "(Used for scaling / scorecard alignment.)")
            d = pd.DataFrame({"p": chal["prob"], "y": chal["y"]})
            q = min(10, max(2, n_pos))
            d["band"] = pd.qcut(d["p"].rank(method="first"), q=q, labels=False)
            fo = d.groupby("band").agg(score=("p", "mean"), good=("y", "sum"),
                                       n=("y", "size")).reset_index()
            fo["bad"] = fo["n"] - fo["good"]
            fo["log_odds"] = np.log((fo["good"] + 0.5) / (fo["bad"] + 0.5))
            st.altair_chart(alt.Chart(fo).mark_circle(size=70, color="#c9a84c").encode(
                x=alt.X("score:Q", title="mean model score (by band)"),
                y=alt.Y("log_odds:Q", title="actual log-odds"),
                tooltip=["band", "score", "good", "bad", "log_odds"]).properties(
                height=260, title="Fit Odds (closer to a straight line = better calibrated)"),
                width="stretch")
    elif not ss.selected:
        st.warning("No variables selected.")

# ── TAB 5 · COMBINE (OvR) ────────────────────────────────────────────────────
with tabs[4]:
    st.markdown("**Combine all 10 scorecards (one-vs-rest)** — build every class's scorecard with "
                "the current settings, predict each player by argmax, and compare to the rule "
                "**Champion** (88.5%).")
    feats = ss.selected if ss.selected else list(FEATURES)
    probs = np.column_stack([build_model(df, c, ss.var_bins, feats, ss.C, ss.balanced)["prob"]
                             for c in ARCHETYPES])
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
            log(f"[combine] LOO accuracy {(loo==truth).mean():.1%}")
            st.metric("leave-one-out accuracy", f"{(loo == truth).mean():.1%}",
                      help="Each player predicted by a model that never saw it. Rule champion = 88.5%.")
    st.caption("In-sample is optimistic; the honest out-of-sample number is leave-one-out. "
               "Rule champion = **88.5%**. See docs/champion-vs-challenger.html.")
    pid = st.selectbox("Score one player under all 10 scorecards", df["player_id"].tolist(),
                       index=df["player_id"].tolist().index("P-104"))
    pos = df.index.get_loc(df.index[df["player_id"] == pid][0])
    pr = pd.DataFrame({"class": ARCHETYPES, "P(class)": probs[pos]}).sort_values("P(class)", ascending=False)
    win = pr.iloc[0]["class"]; pr["win"] = pr["class"] == win
    st.write(f"**{pid}** · truth **{df.iloc[pos]['archetype']}** → argmax **{win}** "
             + ("✅" if win == df.iloc[pos]["archetype"] else "❌"))
    st.altair_chart(alt.Chart(pr).mark_bar().encode(
        x="P(class):Q", y=alt.Y("class:N", sort="-x"),
        color=alt.condition(alt.datum.win, alt.value("#5b9bf5"), alt.value("#2b4231")),
        tooltip=["class", "P(class)"]).properties(height=28 * len(ARCHETYPES)), width="stretch")

# ── console / jobs ───────────────────────────────────────────────────────────
with st.expander("🖥 Console / Jobs", expanded=False):
    st.code("\n".join(ss.jobs[:14]) or "(no activity)", language="text")
