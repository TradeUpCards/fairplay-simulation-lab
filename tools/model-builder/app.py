"""FairPlay Model Builder — Dash + AG Grid (FICO Model Builder-style).

The Scorecard Editor is ONE attribute grid: every candidate predictor with an
in/out checkbox and an editable bin count. Toggle a checkbox → the model re-fits
and the relative-importance chart + metrics update. **Double-click a row** →
its Interactive Binner opens (WoE plot + bin table + points), where you adjust
the binning.

All modeling goes through ``ml/service.py`` (pure, JSON-returning) — this file
is only the UI shell. A future React+FastAPI build would reuse that same service.

Run:
    pip install -r tools/model-builder/requirements.txt
    python tools/model-builder/app.py
    # opens http://127.0.0.1:8050

Internal P3/dev tool — not part of the deterministic demo path.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import dash_ag_grid as dag
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, callback, ctx, dcc, html, no_update

import ml.service as svc

FEATURES = svc.features()
ARCHETYPES = svc.archetypes()
C_OPTIONS = [0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0]

# palette
BG, PANEL, BORDER, TEXT, MUTED, GOLD, BLUE, GREEN, RED = (
    "#081109", "#0e1c12", "#1f3c25", "#d8ecda", "#7a9c80", "#c9a84c",
    "#5b9bf5", "#46c98b", "#e05c4a")


def default_cfg() -> dict:
    return {"target": "grinder", "selected": list(FEATURES), "var_bins": {},
            "C": 1.0, "balanced": True, "pdo": 20}


def dark(fig: go.Figure, h: int = 240, title: str = "") -> go.Figure:
    fig.update_layout(paper_bgcolor=PANEL, plot_bgcolor=PANEL, font_color=TEXT,
                      height=h, margin=dict(l=12, r=12, t=34 if title else 12, b=12),
                      title=dict(text=title, font=dict(size=13, color=GOLD)),
                      showlegend=bool(fig.data) and len(fig.data) > 1, legend=dict(font=dict(size=10)))
    fig.update_xaxes(gridcolor=BORDER, zerolinecolor=BORDER)
    fig.update_yaxes(gridcolor=BORDER, zerolinecolor=BORDER)
    return fig


# ── grid ─────────────────────────────────────────────────────────────────────
COLUMN_DEFS = [
    {"field": "in_model", "headerName": "in", "cellRenderer": "agCheckboxCellRenderer",
     "editable": True, "width": 64, "cellEditor": "agCheckboxCellEditor"},
    {"field": "variable", "headerName": "attribute", "editable": False, "flex": 2,
     "tooltipField": "variable"},
    {"field": "contribution", "headerName": "contribution (IV)", "editable": False,
     "type": "numericColumn", "flex": 1, "valueFormatter": {"function": "d3.format('.3f')(params.value)"}},
    {"field": "strength", "headerName": "strength", "editable": False, "flex": 1},
    {"field": "weight", "headerName": "weight", "editable": False, "type": "numericColumn",
     "flex": 1, "valueFormatter": {"function": "params.value==null?'':d3.format('+.2f')(params.value)"}},
    {"field": "bins", "headerName": "bins", "editable": True, "type": "numericColumn", "width": 80,
     "cellEditor": "agNumberCellEditor", "cellEditorParams": {"min": 2, "max": 8, "precision": 0}},
]

GRID = dag.AgGrid(
    id="grid", columnDefs=COLUMN_DEFS, rowData=[], columnSize="responsiveSizeToFit",
    className="ag-theme-alpine-dark",
    dashGridOptions={"rowHeight": 30, "animateRows": True, "tooltipShowDelay": 300,
                     "stopEditingWhenCellsLoseFocus": True},
    style={"height": "330px"})


def tree(cfg: dict) -> html.Div:
    sel = len(cfg["selected"])
    return html.Div(style={"fontFamily": "monospace", "fontSize": "12px",
                           "lineHeight": "1.9", "color": MUTED}, children=[
        html.Div(["📁 ", html.B("fairplay-archetypes", style={"color": GOLD})]),
        html.Div("  ├─ 📁 datasets"),
        html.Div(["  │   └─ 📄 players ", html.Span("(122)", style={"color": "#3a553f"})]),
        html.Div("  ├─ 📁 models"),
        html.Div(["  │   └─ 📄 ", html.B(f"{cfg['target']}_GB_scorecard", style={"color": TEXT})]),
        html.Div("  ├─ 📁 binning-libraries"),
        html.Div([f"  │   └─ 📄 {cfg['target']} ",
                  html.Span(f"({sel}/{len(FEATURES)} vars)", style={"color": "#3a553f"})]),
        html.Div("  └─ 📁 reports"),
    ])


# ── layout ───────────────────────────────────────────────────────────────────
app = Dash(__name__, title="FairPlay Model Builder")
panel = {"background": PANEL, "border": f"1px solid {BORDER}", "borderRadius": "8px",
         "padding": "14px 16px"}

app.layout = html.Div(style={"background": BG, "color": TEXT, "minHeight": "100vh",
                             "fontFamily": "-apple-system,Segoe UI,system-ui,sans-serif",
                             "padding": "16px 22px"}, children=[
    dcc.Store(id="cfg", data=default_cfg()),
    dcc.Store(id="focus", data="aggression_factor"),
    html.Div(style={"display": "flex", "alignItems": "baseline", "gap": "14px"}, children=[
        html.H3("◆ FairPlay Model Builder", style={"color": GOLD, "margin": "0"}),
        html.Span("FICO-style scorecard workbench · one-vs-rest", style={"color": MUTED, "fontSize": "13px"}),
    ]),
    # config bar
    html.Div(style={"display": "flex", "gap": "18px", "flexWrap": "wrap", "alignItems": "center",
                    "margin": "12px 0", **panel}, children=[
        html.Div([html.Label("Target (Good/Bad)", style={"fontSize": "11px", "color": MUTED}),
                  dcc.Dropdown(id="target", options=ARCHETYPES, value="grinder", clearable=False,
                               style={"width": "210px", "color": "#111"})]),
        html.Div([html.Label("Regularization C", style={"fontSize": "11px", "color": MUTED}),
                  dcc.Dropdown(id="C", options=C_OPTIONS, value=1.0, clearable=False,
                               style={"width": "110px", "color": "#111"})]),
        html.Div([html.Label("PDO", style={"fontSize": "11px", "color": MUTED}),
                  dcc.Slider(id="pdo", min=10, max=40, step=5, value=20,
                             marks={10: "10", 20: "20", 30: "30", 40: "40"})],
                 style={"width": "180px"}),
        dcc.Checklist(id="balanced", options=[{"label": " class_weight=balanced", "value": "bal"}],
                      value=["bal"], style={"color": MUTED, "fontSize": "13px"}),
    ]),
    html.Div(style={"display": "grid", "gridTemplateColumns": "220px 1fr", "gap": "16px"}, children=[
        # left: project tree
        html.Div(style=panel, children=[html.Div("WORKSPACE", style={"fontSize": "10px",
                 "letterSpacing": ".1em", "color": GOLD, "marginBottom": "8px"}),
                 html.Div(id="tree")]),
        # right: tabs
        dcc.Tabs(id="view", value="editor", colors={"border": BORDER, "primary": GOLD, "background": PANEL},
                 children=[
            dcc.Tab(label="Scorecard Editor", value="editor", style={"background": PANEL, "color": MUTED,
                    "border": f"1px solid {BORDER}"}, selected_style={"background": PANEL, "color": GOLD,
                    "border": f"1px solid {BORDER}", "borderTop": f"2px solid {GOLD}"}, children=[
                html.Div(style={"marginTop": "12px"}, children=[
                    html.Div(id="ds-summary", style={"color": MUTED, "fontSize": "13px", "marginBottom": "8px"}),
                    GRID,
                    html.Div("⟸ tick/untick 'in' to add/remove a variable · edit 'bins' inline · "
                             "double-click a row to open its binner",
                             style={"fontSize": "11px", "color": "#3a553f", "margin": "6px 0 14px"}),
                    html.Div(style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "16px"}, children=[
                        html.Div(style=panel, children=[dcc.Graph(id="importance", config={"displayModeBar": False})]),
                        html.Div(style=panel, children=[
                            html.Div(id="binner-title", style={"color": GOLD, "fontSize": "13px", "marginBottom": "6px"}),
                            dcc.Graph(id="binner-woe", config={"displayModeBar": False}),
                            html.Div([html.Label("bins (coarse classing)", style={"fontSize": "11px", "color": MUTED}),
                                      dcc.Slider(id="binner-bins", min=2, max=8, step=1, value=4,
                                                 marks={i: str(i) for i in range(2, 9)})]),
                            html.Div(id="binner-table", style={"marginTop": "8px"})]),
                    ]),
                    html.Div(id="metrics", style={"marginTop": "12px"}),
                ]),
            ]),
            dcc.Tab(label="Reports", value="reports", style={"background": PANEL, "color": MUTED,
                    "border": f"1px solid {BORDER}"}, selected_style={"background": PANEL, "color": GOLD,
                    "border": f"1px solid {BORDER}", "borderTop": f"2px solid {GOLD}"}, children=[
                html.Div(id="reports", style={"marginTop": "12px"})]),
            dcc.Tab(label="Combine (OvR)", value="combine", style={"background": PANEL, "color": MUTED,
                    "border": f"1px solid {BORDER}"}, selected_style={"background": PANEL, "color": GOLD,
                    "border": f"1px solid {BORDER}", "borderTop": f"2px solid {GOLD}"}, children=[
                html.Div(style={"marginTop": "12px"}, children=[
                    html.Div(id="combine-summary"),
                    html.Button("Compute honest leave-one-out (slower)", id="loo-btn",
                                style={"margin": "10px 0", "background": PANEL, "color": GOLD,
                                       "border": f"1px solid {BORDER}", "padding": "6px 12px",
                                       "borderRadius": "6px", "cursor": "pointer"}),
                    html.Div(id="loo-out", style={"color": GREEN, "marginBottom": "12px"}),
                    dcc.Dropdown(id="player", options=svc.player_ids(), value="P-104", clearable=False,
                                 style={"width": "200px", "color": "#111"}),
                    dcc.Graph(id="player-graph", config={"displayModeBar": False})]),
            ]),
        ]),
    ]),
    html.Div(style={"marginTop": "10px", "fontSize": "11px", "color": "#3a553f"},
             children="⚠ Synthetic data: classes are near-separable, so IV/KS/divergence are "
                      "inflated (real-world IV .1–.5, KS .3–.6). Internal dev tool — not the demo path."),
])


# ── callbacks ────────────────────────────────────────────────────────────────
@callback(Output("cfg", "data"),
          Input("target", "value"), Input("C", "value"), Input("balanced", "value"),
          Input("pdo", "value"), Input("grid", "cellValueChanged"), Input("binner-bins", "value"),
          State("cfg", "data"), State("focus", "data"), prevent_initial_call=False)
def update_cfg(target, C, balanced, pdo, cell, binner_bins, cfg, focus):
    cfg = cfg or default_cfg()
    trig = ctx.triggered_id
    if trig == "target" and target != cfg["target"]:
        return {"target": target, "selected": list(FEATURES), "var_bins": {},
                "C": cfg["C"], "balanced": cfg["balanced"], "pdo": cfg["pdo"]}
    if trig == "C":
        cfg["C"] = C
    elif trig == "balanced":
        cfg["balanced"] = "bal" in (balanced or [])
    elif trig == "pdo":
        cfg["pdo"] = pdo
    elif trig == "grid" and cell:
        for ch in (cell if isinstance(cell, list) else [cell]):
            var = ch["data"]["variable"]
            if ch["colId"] == "in_model":
                sel = set(cfg["selected"])
                sel.add(var) if ch["value"] else sel.discard(var)
                cfg["selected"] = [f for f in FEATURES if f in sel]
            elif ch["colId"] == "bins":
                cfg["var_bins"][var] = int(ch["value"])
    elif trig == "binner-bins" and focus:
        cfg["var_bins"][focus] = int(binner_bins)
    return cfg


@callback(Output("focus", "data"), Input("grid", "cellDoubleClicked"),
          State("focus", "data"), prevent_initial_call=True)
def set_focus(dbl, focus):
    if dbl and dbl.get("data"):
        return dbl["data"]["variable"]
    return focus or no_update


@callback(Output("grid", "rowData"), Output("importance", "figure"),
          Output("metrics", "children"), Output("tree", "children"),
          Output("ds-summary", "children"), Input("cfg", "data"))
def render_editor(cfg):
    rows = svc.attribute_rows(cfg["target"], cfg["selected"], cfg["var_bins"], cfg["C"], cfg["balanced"])
    met = svc.model_metrics(cfg["target"], cfg["selected"], cfg["var_bins"], cfg["C"], cfg["balanced"], cfg["pdo"])
    imp = met["importance"]
    fig = go.Figure()
    if imp:
        imp = list(reversed(imp))
        fig.add_bar(x=[r["contribution"] for r in imp], y=[r["variable"] for r in imp],
                    orientation="h", marker_color=GOLD)
    fig = dark(fig, h=300, title="Relative importance (marginal contribution · IV)")
    ds = svc.dataset_summary(cfg["target"])
    summary = (f"Binary target: Good = is `{cfg['target']}` ({ds['good']}) · Bad = rest "
               f"({ds['bad']}) · base rate {ds['base_rate']:.1%}"
               + ("  ⚠ too few Good cases" if ds["low_confidence"] else ""))
    def m(v):
        return "—" if v is None else (f"{v:.2f}" if abs(v) < 100 else f"{v:.0f}")
    metrics = html.Div(style={"display": "flex", "gap": "26px", "fontSize": "14px"}, children=[
        html.Div([html.Span("KS ", style={"color": MUTED}), html.B(m(met["ks"]))]),
        html.Div([html.Span("AUC ", style={"color": MUTED}), html.B(m(met["auc"]))]),
        html.Div([html.Span("divergence ", style={"color": MUTED}), html.B(m(met["divergence"]))]),
        html.Div([html.Span("Σ contribution ", style={"color": MUTED}), html.B(m(met["total_iv"]))]),
        html.Div([html.Span("variables ", style={"color": MUTED}), html.B(len(cfg["selected"]))]),
    ])
    return rows, fig, metrics, tree(cfg), summary


@callback(Output("binner-title", "children"), Output("binner-woe", "figure"),
          Output("binner-table", "children"), Output("binner-bins", "value"),
          Input("cfg", "data"), Input("focus", "data"))
def render_binner(cfg, focus):
    focus = focus or FEATURES[0]
    nb = int(cfg["var_bins"].get(focus, 4))
    bd = svc.bin_detail(cfg["target"], focus, nb, cfg["selected"], cfg["var_bins"],
                        cfg["C"], cfg["balanced"], cfg["pdo"])
    fig = go.Figure()
    fig.add_bar(x=[b["bin"] for b in bd["bins"]], y=[b["woe"] for b in bd["bins"]],
                marker_color=[GREEN if b["woe"] > 0 else RED for b in bd["bins"]])
    fig = dark(fig, h=200, title=f"Weight of Evidence · {focus}")
    title = (f"🔬 Interactive Binner — {focus}  ·  IV {bd['iv']} ({bd['strength']})  ·  "
             f"{'monotonic ✓' if bd['monotonic'] else 'non-monotonic ✗'}")
    head = html.Tr([html.Th(c, style={"textAlign": "left", "color": GOLD, "fontSize": "10px"})
                    for c in ["bin", "n", "Good", "Bad", "WoE", "pts"]])
    body = [html.Tr([html.Td(b["bin"], style={"fontSize": "11px"}), html.Td(b["n"]),
                     html.Td(b["good"]), html.Td(b["bad"]), html.Td(b["woe"]),
                     html.Td(f"{b['points']:+d}")], style={"fontSize": "11.5px"}) for b in bd["bins"]]
    table = html.Table([head] + body, style={"width": "100%", "color": MUTED})
    return title, fig, table, nb


@callback(Output("reports", "children"), Input("cfg", "data"), Input("view", "value"))
def render_reports(cfg, view):
    if view != "reports":
        return no_update
    rep = svc.reports(cfg["target"], cfg["selected"], cfg["var_bins"], cfg["C"], cfg["balanced"])
    if rep.get("insufficient"):
        return html.Div("Too few Good cases to report on this target.", style={"color": MUTED})
    comp = rep["comparison"]
    comp_tbl = html.Table([
        html.Tr([html.Th(c, style={"color": GOLD, "textAlign": "left", "fontSize": "11px"})
                 for c in ["model", "KS", "AUC", "divergence", "variables"]])] +
        [html.Tr([html.Td(r["model"]), html.Td(r["ks"]), html.Td(r["auc"]),
                  html.Td(r["divergence"]), html.Td(r["variables"])]) for r in comp],
        style={"width": "100%", "color": TEXT, "marginBottom": "12px"})
    roc = go.Figure()
    roc.add_scatter(x=[p["fpr"] for p in rep["roc_challenger"]], y=[p["tpr"] for p in rep["roc_challenger"]],
                    mode="lines", name="Challenger", line_color=BLUE)
    roc.add_scatter(x=[p["fpr"] for p in rep["roc_champion"]], y=[p["tpr"] for p in rep["roc_champion"]],
                    mode="lines", name="Champion", line_color=GOLD)
    ks = go.Figure()
    ks.add_scatter(x=[p["pct"] for p in rep["ks_curve"]], y=[p["good"] for p in rep["ks_curve"]],
                   mode="lines", name="good", line_color=GREEN)
    ks.add_scatter(x=[p["pct"] for p in rep["ks_curve"]], y=[p["bad"] for p in rep["ks_curve"]],
                   mode="lines", name="bad", line_color=RED)
    fo = go.Figure()
    fo.add_scatter(x=[p["score"] for p in rep["fit_odds"]], y=[p["log_odds"] for p in rep["fit_odds"]],
                   mode="markers", marker=dict(color=GOLD, size=9))
    train_tbl = html.Table([
        html.Tr([html.Th(c, style={"color": GOLD, "textAlign": "left", "fontSize": "10px"})
                 for c in ["variable", "selected", "contribution", "bins", "weight"]])] +
        [html.Tr([html.Td(t["variable"], style={"fontSize": "11px"}), html.Td("✓" if t["selected"] else ""),
                  html.Td(t["contribution"]), html.Td(t["bins"]),
                  html.Td("" if t["weight"] is None else f"{t['weight']:+.2f}")]) for t in rep["training"]],
        style={"width": "100%", "color": MUTED})
    return html.Div([
        html.H4("Performance — Challenger vs Champion", style={"color": GOLD}),
        comp_tbl,
        html.Div(style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "14px"}, children=[
            dcc.Graph(figure=dark(roc, 260, "ROC"), config={"displayModeBar": False}),
            dcc.Graph(figure=dark(ks, 260, f"KS curve · {rep['ks']}"), config={"displayModeBar": False})]),
        html.H4("Fit Odds", style={"color": GOLD, "marginTop": "10px"}),
        dcc.Graph(figure=dark(fo, 240, "score vs actual log-odds (linear = well-scaled)"),
                  config={"displayModeBar": False}),
        html.H4("Model Training", style={"color": GOLD, "marginTop": "10px"}),
        train_tbl,
    ])


@callback(Output("combine-summary", "children"), Output("player-graph", "figure"),
          Input("cfg", "data"), Input("view", "value"), Input("player", "value"))
def render_combine(cfg, view, player):
    if view != "combine":
        return no_update, no_update
    cb = svc.combine(cfg["selected"], cfg["var_bins"], cfg["C"], cfg["balanced"])
    pl = svc.combine_player(player, cfg["selected"], cfg["var_bins"], cfg["C"], cfg["balanced"])
    summary = html.Div([
        html.Span("OvR in-sample accuracy ", style={"color": MUTED}),
        html.B(f"{cb['in_sample_accuracy']:.1%}", style={"fontSize": "20px", "color": BLUE}),
        html.Span(f"  · {cb['variables']} variables · rule champion "
                  f"{cb['rule_champion']:.1%} (honest LOO ≈ 85.2% with all vars)", style={"color": MUTED})])
    fig = go.Figure()
    fig.add_bar(x=[s["prob"] for s in reversed(pl["scores"])],
                y=[s["archetype"] for s in reversed(pl["scores"])], orientation="h",
                marker_color=[BLUE if s["archetype"] == pl["predicted"] else "#2b4231"
                              for s in reversed(pl["scores"])])
    ok = "✅" if pl["predicted"] == pl["truth"] else "❌"
    fig = dark(fig, 300, f"{player} · truth {pl['truth']} → argmax {pl['predicted']} {ok}")
    return summary, fig


@callback(Output("loo-out", "children"), Input("loo-btn", "n_clicks"),
          State("cfg", "data"), prevent_initial_call=True)
def run_loo(n, cfg):
    r = svc.combine_loo(cfg["selected"], cfg["C"], cfg["balanced"])
    return f"Leave-one-out accuracy: {r['loo_accuracy']:.1%}  (rule champion {r['rule_champion']:.1%})"


if __name__ == "__main__":
    app.run(debug=False, port=8050)
