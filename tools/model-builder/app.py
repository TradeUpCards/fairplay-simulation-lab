"""FairPlay Model Builder — Dash + AG Grid (FICO Model Builder-style).

The Scorecard Editor is ONE attribute grid: every candidate predictor with an
in/out checkbox and a data-driven bin count. Toggle a checkbox → the model
re-fits and the relative-importance chart + metrics update. **Double-click a
row** → its Interactive Binner opens (WoE plot + bin table + points), where you
**coarse-class** by merging the automatic fine bins.

Binning is two-stage best practice: fine classing is automatic and data-driven
(a supervised decision tree finds cut points per variable — see
``ml/scorecard.auto_fine_cuts``); coarse classing is the analyst merging
adjacent bins (toggling cut points off).

All modeling goes through ``ml/service.py`` (pure, JSON-returning) — this file
is only the UI shell. A future React+FastAPI build would reuse that same service.

Run:
    pip install -r tools/model-builder/requirements.txt
    python tools/model-builder/app.py            # → http://127.0.0.1:8050

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

# ── neutral enterprise-IDE palette (FICO Model Builder-like) ─────────────────
WIN, PANEL, HDR = "#d4d7da", "#ffffff", "#e7e9eb"
BORDER, GRIDLINE, SEL = "#9aa3ab", "#dfe3e6", "#cfe3f7"
TEXT, MUTED, FAINT = "#1b1e21", "#586068", "#8a929a"
ACCENT, BAR, GOOD, BAD = "#2f6fb3", "#3f7cc0", "#2e8b57", "#c0533a"
MONO = "Consolas,Menlo,monospace"


def default_cfg() -> dict:
    return {"target": "grinder", "selected": list(FEATURES), "var_cuts": {},
            "C": 1.0, "balanced": True, "pdo": 20}


def theme(fig: go.Figure, h: int = 230, title: str = "") -> go.Figure:
    fig.update_layout(paper_bgcolor=PANEL, plot_bgcolor=PANEL, font=dict(color=TEXT, size=11),
                      height=h, margin=dict(l=8, r=8, t=24 if title else 6, b=6),
                      title=dict(text=title, font=dict(size=11.5, color=TEXT)),
                      showlegend=bool(fig.data) and len(fig.data) > 1,
                      legend=dict(font=dict(size=10), orientation="h", y=1.12, x=0))
    fig.update_xaxes(gridcolor=GRIDLINE, zerolinecolor=GRIDLINE, linecolor=BORDER, tickfont=dict(size=10))
    fig.update_yaxes(gridcolor=GRIDLINE, zerolinecolor=GRIDLINE, linecolor=BORDER, tickfont=dict(size=10))
    return fig


def pane(title: str, *children, flex: str = None, height: str = None) -> html.Div:
    style = {"background": PANEL, "border": f"1px solid {BORDER}", "display": "flex",
             "flexDirection": "column", "minWidth": "0"}
    if flex:
        style["flex"] = flex
    if height:
        style["height"] = height
    return html.Div(style=style, children=[
        html.Div(title, style={"background": HDR, "borderBottom": f"1px solid {BORDER}",
                               "padding": "3px 9px", "fontSize": "11px", "fontWeight": 600,
                               "color": TEXT, "letterSpacing": ".01em"}),
        html.Div(style={"padding": "8px 9px", "flex": "1", "overflow": "auto"}, children=list(children)),
    ])


# ── grid ─────────────────────────────────────────────────────────────────────
BAR_STYLE = {"function": "params.value==null?{}:{'background':'linear-gradient(90deg,#cfe0f3 '"
             "+Math.min(100,params.value/3*100)+'%, transparent '+Math.min(100,params.value/3*100)+'%)',"
             "'fontFamily':'Consolas,monospace'}"}
COLUMN_DEFS = [
    {"field": "in_model", "headerName": "", "cellRenderer": "agCheckboxCellRenderer",
     "editable": True, "width": 46, "cellEditor": "agCheckboxCellEditor",
     "cellStyle": {"display": "flex", "alignItems": "center", "justifyContent": "center"}},
    {"field": "variable", "headerName": "attribute", "editable": False, "minWidth": 200,
     "tooltipField": "variable", "cellStyle": {"fontFamily": MONO}},
    {"field": "contribution", "headerName": "contribution (IV)", "editable": False,
     "type": "numericColumn", "minWidth": 150, "cellStyle": BAR_STYLE,
     "valueFormatter": {"function": "d3.format('.3f')(params.value)"}},
    {"field": "strength", "headerName": "strength", "editable": False, "minWidth": 96},
    {"field": "weight", "headerName": "weight", "editable": False, "type": "numericColumn",
     "width": 90, "valueFormatter": {"function": "params.value==null?'':d3.format('+.2f')(params.value)"}},
    {"field": "bins", "headerName": "bins", "editable": False, "type": "numericColumn", "width": 60,
     "headerTooltip": "auto fine bins (data-driven). Coarse-class in the binner."},
]

GRID = dag.AgGrid(
    id="grid", columnDefs=COLUMN_DEFS, rowData=[], columnSize="autoSize",
    className="ag-theme-balham",
    dashGridOptions={"rowHeight": 26, "headerHeight": 28, "animateRows": False,
                     "tooltipShowDelay": 300, "stopEditingWhenCellsLoseFocus": True,
                     "rowSelection": "single"},
    style={"height": "266px"})

# ── interactive binner: flat grid; coarse bins expand to their fine bins ──
# (AG Grid treeData is Enterprise-only, so expand/collapse is done manually.)
# WoE = horizontal diverging bar via a cellStyle gradient (from a centre line:
# right/green = toward class, left/red = away). Pure expression (no IIFE).
WOE_BAR = {"function":
    "params.value==null?{}:(params.value>=0?"
    "{'background':'linear-gradient(90deg,transparent 50%,#2e8b5759 50%,#2e8b5759 '"
    "+(50+Math.min(50,params.value/6*50))+'%,transparent '+(50+Math.min(50,params.value/6*50))+'%)',"
    "'color':'#2e8b57','fontWeight':600,'fontFamily':'Consolas,monospace','textAlign':'center'}:"
    "{'background':'linear-gradient(90deg,transparent '+(50+Math.max(-50,params.value/6*50))+'%,"
    "#c0533a59 '+(50+Math.max(-50,params.value/6*50))+'%,#c0533a59 50%,transparent 50%)',"
    "'color':'#c0533a','fontWeight':600,'fontFamily':'Consolas,monospace','textAlign':'center'})"}
BIN_COLUMN_DEFS = [
    {"field": "expand", "headerName": "", "minWidth": 30, "maxWidth": 36, "sortable": False,
     "cellStyle": {"cursor": "pointer", "textAlign": "center", "color": ACCENT, "fontWeight": 700}},
    {"field": "bin", "headerName": "bin (range)", "minWidth": 220, "cellStyle": {"fontFamily": MONO}},
    {"field": "idx", "hide": True},
    {"field": "n", "headerName": "count", "type": "numericColumn", "minWidth": 64},
    {"field": "good", "headerName": "Good", "type": "numericColumn", "minWidth": 60},
    {"field": "bad", "headerName": "Bad", "type": "numericColumn", "minWidth": 54},
    {"field": "event_pct", "headerName": "event %", "type": "numericColumn", "minWidth": 72},
    {"field": "woe", "headerName": "WoE   (◄ bad · good ►)", "minWidth": 164, "cellStyle": WOE_BAR,
     "valueFormatter": {"function": "params.value==null?'':d3.format('+.2f')(params.value)"}},
    {"field": "iv_part", "headerName": "IV", "type": "numericColumn", "minWidth": 60,
     "valueFormatter": {"function": "params.value==null?'':d3.format('.3f')(params.value)"}},
    {"field": "points", "headerName": "pts", "type": "numericColumn", "minWidth": 50},
]
BIN_GRID = dag.AgGrid(
    id="bin-grid", columnDefs=BIN_COLUMN_DEFS, rowData=[], columnSize="autoSize", className="ag-theme-balham",
    dashGridOptions={"rowHeight": 27, "headerHeight": 28, "rowSelection": "multiple",
                     "suppressRowClickSelection": False,
                     "isRowSelectable": {"function": "params.data && params.data.idx != null"},
                     "getRowStyle": {"function": "params.data && params.data.idx==null ? "
                                     "{'background':'#f4f6f8','color':'#586068','fontStyle':'italic'} : {}"}},
    style={"height": "276px"})

btn = {"fontSize": "11px", "background": HDR, "color": TEXT, "border": f"1px solid {BORDER}",
       "padding": "3px 11px", "cursor": "pointer", "marginRight": "6px"}


def tree(cfg: dict) -> html.Div:
    sel = len(cfg["selected"])
    line = lambda t, **s: html.Div(t, style={"whiteSpace": "pre", **s})
    return html.Div(style={"fontFamily": MONO, "fontSize": "11.5px", "lineHeight": "1.75",
                           "color": TEXT}, children=[
        line("▾ fairplay-archetypes", fontWeight=600),
        line("  ▾ datasets"),
        line("      players", color=MUTED),
        line("  ▾ models"),
        line(f"      {cfg['target']}_GB_scorecard", color=ACCENT, fontWeight=600),
        line("  ▾ binning-libraries"),
        line(f"      {cfg['target']}  ({sel}/{len(FEATURES)})", color=MUTED),
        line("  ▸ reports", color=MUTED),
    ])


# ── layout ───────────────────────────────────────────────────────────────────
app = Dash(__name__, title="FairPlay Model Builder",
           assets_folder=str(Path(__file__).resolve().parent / "assets"))

menu = html.Div(style={"background": HDR, "borderBottom": f"1px solid {BORDER}",
                       "padding": "3px 10px", "fontSize": "12px", "color": TEXT,
                       "display": "flex", "gap": "18px"},
                children=[html.Span("◆ FairPlay Model Builder", style={"fontWeight": 700, "color": ACCENT})]
                + [html.Span(m, style={"color": MUTED}) for m in
                   ["File", "Edit", "Model", "Binning", "Reports", "Window", "Help"]])

ctrl_lbl = {"fontSize": "10px", "color": MUTED, "marginRight": "5px"}
toolbar = html.Div(style={"background": "#eceef0", "borderBottom": f"1px solid {BORDER}",
                          "padding": "5px 10px", "display": "flex", "gap": "16px",
                          "alignItems": "center", "flexWrap": "wrap"}, children=[
    html.Span("Target", style=ctrl_lbl),
    dcc.Dropdown(id="target", options=ARCHETYPES, value="grinder", clearable=False,
                 style={"width": "180px", "fontSize": "12px"}),
    html.Span("C", style=ctrl_lbl),
    dcc.Dropdown(id="C", options=C_OPTIONS, value=1.0, clearable=False,
                 style={"width": "80px", "fontSize": "12px"}),
    html.Span("PDO", style=ctrl_lbl),
    dcc.Dropdown(id="pdo", options=[10, 15, 20, 25, 30, 40], value=20, clearable=False,
                 style={"width": "78px", "fontSize": "12px"}),
    dcc.Checklist(id="balanced", options=[{"label": " class_weight=balanced", "value": "bal"}],
                  value=["bal"], style={"color": MUTED, "fontSize": "12px"}),
])

tab_style = {"background": "#dfe2e5", "color": MUTED, "border": f"1px solid {BORDER}",
             "padding": "4px 14px", "fontSize": "12px"}
tab_sel = {"background": PANEL, "color": TEXT, "fontWeight": 600, "border": f"1px solid {BORDER}",
           "borderBottom": f"2px solid {ACCENT}", "padding": "4px 14px", "fontSize": "12px"}

app.layout = html.Div(style={"background": WIN, "color": TEXT, "minHeight": "100vh",
                             "fontFamily": "Segoe UI,-apple-system,system-ui,sans-serif", "fontSize": "12px"},
                      children=[
    dcc.Store(id="cfg", data=default_cfg()),
    dcc.Store(id="focus", data="aggression_factor"),
    dcc.Store(id="expanded", data=[]),
    menu, toolbar,
    html.Div(style={"display": "flex", "gap": "6px", "padding": "6px"}, children=[
        # left: project explorer
        pane("Project Explorer", html.Div(id="tree"), height="calc(100vh - 96px)",
             flex="0 0 196px"),
        # right: main
        html.Div(style={"flex": "1", "minWidth": "0", "display": "flex", "flexDirection": "column", "gap": "6px"}, children=[
            dcc.Tabs(id="view", value="editor", children=[
                dcc.Tab(label="Scorecard Editor", value="editor", style=tab_style, selected_style=tab_sel, children=[
                    html.Div(style={"display": "flex", "flexDirection": "column", "gap": "6px", "marginTop": "6px"}, children=[
                        html.Div(id="ds-summary", style={"color": MUTED, "fontSize": "11.5px", "padding": "0 2px"}),
                        # variable list — full width, relative-importance bar INLINE (contribution column)
                        pane("Scorecard Model Editor — variable list",
                             GRID, html.Div(id="metrics", style={"padding": "5px 2px 0"}),
                             html.Div("tick / untick the 'in' box to add or remove a variable (model re-fits) "
                                      "· the contribution column is the relative-importance bar "
                                      "· click any row to open it in the Interactive Binner below",
                                      style={"fontSize": "10.5px", "color": FAINT, "marginTop": "4px"})),
                        # interactive binner — a grid of bins you select + combine/separate
                        pane(html.Span(id="binner-title"),
                             html.Div([
                                 html.Button("◧ Combine selected", id="bin-combine", style=btn),
                                 html.Button("◨ Separate", id="bin-separate", style=btn),
                                 html.Button("↺ Reset to auto", id="bin-reset", style=btn),
                                 html.Span("select two or more adjacent bins, then Combine — watch IV / WoE react",
                                           style={"fontSize": "10px", "color": FAINT, "marginLeft": "6px"}),
                             ], style={"marginBottom": "6px"}),
                             BIN_GRID,
                             html.Div(id="binner-stats", style={"fontSize": "10.5px", "color": MUTED,
                                      "fontFamily": MONO, "marginTop": "6px"})),
                    ]),
                ]),
                dcc.Tab(label="Reports", value="reports", style=tab_style, selected_style=tab_sel,
                        children=[html.Div(id="reports", style={"marginTop": "6px"})]),
                dcc.Tab(label="Combine (OvR)", value="combine", style=tab_style, selected_style=tab_sel, children=[
                    pane("Combine — one-vs-rest ensemble",
                         html.Div(id="combine-summary"),
                         html.Button("Compute leave-one-out (slower)", id="loo-btn",
                                     style={"margin": "8px 0", "background": HDR, "color": TEXT,
                                            "border": f"1px solid {BORDER}", "padding": "4px 12px",
                                            "fontSize": "12px", "cursor": "pointer"}),
                         html.Div(id="loo-out", style={"color": GOOD, "fontSize": "12px", "marginBottom": "8px"}),
                         dcc.Dropdown(id="player", options=svc.player_ids(), value="P-104", clearable=False,
                                      style={"width": "180px", "fontSize": "12px"}),
                         dcc.Graph(id="player-graph", config={"displayModeBar": False})),
                ]),
            ]),
            # console / jobs
            html.Div(style={"background": PANEL, "border": f"1px solid {BORDER}", "height": "104px",
                            "display": "flex", "flexDirection": "column"}, children=[
                html.Div(style={"display": "flex", "background": HDR, "borderBottom": f"1px solid {BORDER}"}, children=[
                    html.Div("Console", style={"padding": "3px 12px", "fontSize": "11px", "fontWeight": 600,
                             "background": PANEL, "borderRight": f"1px solid {BORDER}"}),
                    html.Div("Jobs", style={"padding": "3px 12px", "fontSize": "11px", "color": MUTED,
                             "borderRight": f"1px solid {BORDER}"})]),
                html.Div(id="console", style={"padding": "6px 10px", "fontFamily": MONO, "fontSize": "11px",
                         "color": MUTED, "overflow": "auto", "flex": "1"})]),
        ]),
    ]),
])


# ── callbacks ────────────────────────────────────────────────────────────────
@callback(Output("cfg", "data"),
          Input("target", "value"), Input("C", "value"), Input("balanced", "value"),
          Input("pdo", "value"), Input("grid", "cellValueChanged"),
          Input("bin-combine", "n_clicks"), Input("bin-separate", "n_clicks"),
          Input("bin-reset", "n_clicks"),
          State("bin-grid", "selectedRows"), State("cfg", "data"), State("focus", "data"),
          prevent_initial_call=False)
def update_cfg(target, C, balanced, pdo, cell, n_comb, n_sep, n_reset, sel_bins, cfg, focus):
    cfg = cfg or default_cfg()
    trig = ctx.triggered_id
    if trig == "target" and target != cfg["target"]:
        return {"target": target, "selected": list(FEATURES), "var_cuts": {},
                "C": cfg["C"], "balanced": cfg["balanced"], "pdo": cfg["pdo"]}
    if trig == "C":
        cfg["C"] = C
    elif trig == "balanced":
        cfg["balanced"] = "bal" in (balanced or [])
    elif trig == "pdo":
        cfg["pdo"] = pdo
    elif trig == "grid" and cell:
        for ch in (cell if isinstance(cell, list) else [cell]):
            if ch["colId"] == "in_model":
                var, sel = ch["data"]["variable"], set(cfg["selected"])
                sel.add(var) if ch["value"] else sel.discard(var)
                cfg["selected"] = [f for f in FEATURES if f in sel]
    elif focus and trig in ("bin-combine", "bin-separate", "bin-reset"):
        idxs = [int(r["idx"]) for r in (sel_bins or [])]
        if trig == "bin-combine" and len(idxs) >= 2:
            cfg["var_cuts"][focus] = svc.combine_bins(cfg["target"], focus, cfg["var_cuts"], idxs)
        elif trig == "bin-separate" and idxs:
            cfg["var_cuts"][focus] = svc.split_bin(cfg["target"], focus, cfg["var_cuts"], idxs[0])
        elif trig == "bin-reset":
            cfg["var_cuts"].pop(focus, None)
    return cfg


@callback(Output("focus", "data"), Input("grid", "selectedRows"),
          State("focus", "data"), prevent_initial_call=True)
def set_focus(rows, focus):
    if rows and rows[0].get("variable"):
        return rows[0]["variable"]
    return focus or no_update


@callback(Output("grid", "rowData"),
          Output("metrics", "children"), Output("tree", "children"),
          Output("ds-summary", "children"), Output("console", "children"), Input("cfg", "data"))
def render_editor(cfg):
    rows = svc.attribute_rows(cfg["target"], cfg["selected"], cfg["var_cuts"], cfg["C"], cfg["balanced"])
    met = svc.model_metrics(cfg["target"], cfg["selected"], cfg["var_cuts"], cfg["C"], cfg["balanced"], cfg["pdo"])
    ds = svc.dataset_summary(cfg["target"])
    summary = (f"Binary target  ·  Good = is '{cfg['target']}' ({ds['good']})  ·  Bad = rest "
               f"({ds['bad']})  ·  base rate {ds['base_rate']:.1%}"
               + ("   ⚠ too few Good cases" if ds["low_confidence"] else ""))
    def m(v):
        return "—" if v is None else (f"{v:.2f}" if abs(v) < 100 else f"{v:.0f}")
    cell = lambda lab, val: html.Div([html.Span(lab + "  ", style={"color": MUTED}),
                                      html.B(val, style={"fontFamily": MONO})])
    metrics = html.Div(style={"display": "flex", "gap": "24px", "fontSize": "12.5px"}, children=[
        cell("KS", m(met["ks"])), cell("AUC", m(met["auc"])), cell("divergence", m(met["divergence"])),
        cell("Σ contribution", m(met["total_iv"])), cell("variables", str(len(cfg["selected"]))),
        cell("base points", "—" if met["base_points"] is None else str(met["base_points"]))])
    console = [
        html.Div(f"[build]  target={cfg['target']}  vars={len(cfg['selected'])}/{len(FEATURES)}  "
                 f"KS={m(met['ks'])}  AUC={m(met['auc'])}  divergence={m(met['divergence'])}", style={"color": TEXT}),
        html.Div(f"[data]   122 players · Good={ds['good']} Bad={ds['bad']} · base rate {ds['base_rate']:.1%}"),
        html.Div("[note]   synthetic data — classes near-separable, so IV/KS/divergence are inflated."),
    ]
    return rows, metrics, tree(cfg), summary, console


@callback(Output("expanded", "data"), Input("focus", "data"), Input("bin-grid", "cellClicked"),
          State("expanded", "data"), prevent_initial_call=True)
def toggle_expand(focus, click, expanded):
    if ctx.triggered_id == "focus":
        return []                                     # collapse all when variable changes
    if click and click.get("colId") == "expand":
        idx = (click.get("data") or {}).get("idx")
        if idx is not None:
            ex = set(expanded or [])
            ex.symmetric_difference_update({idx})
            return sorted(ex)
    return expanded or []


@callback(Output("binner-title", "children"), Output("bin-grid", "rowData"),
          Output("binner-stats", "children"),
          Input("cfg", "data"), Input("focus", "data"), Input("expanded", "data"))
def render_binner(cfg, focus, expanded):
    focus = focus or FEATURES[0]
    exp = set(expanded or [])
    bd = svc.bin_detail(cfg["target"], focus, cfg["var_cuts"], cfg["selected"],
                        cfg["C"], cfg["balanced"], cfg["pdo"])
    # flat rowData; coarse bins with >1 fine show an ▸/▾ toggle and expand inline
    rows = []
    for node in bd["tree"]:
        has_kids = node["n_fine"] > 1
        rows.append({"expand": ("▾" if node["idx"] in exp else "▸") if has_kids else "",
                     "bin": node["bin"] + (f"   ({node['n_fine']} fine bins)" if has_kids else ""),
                     "idx": node["idx"], "n": node["n"], "good": node["good"], "bad": node["bad"],
                     "event_pct": node["event_pct"], "woe": node["woe"],
                     "iv_part": node["iv_part"], "points": node["points"]})
        if has_kids and node["idx"] in exp:
            for fb in node["children"]:
                rows.append({"expand": "", "bin": "      └ " + fb["bin"], "idx": None, "n": fb["n"],
                             "good": fb["good"], "bad": fb["bad"], "event_pct": fb["event_pct"],
                             "woe": fb["woe"], "iv_part": None, "points": None})
    edited = set(bd["active_cuts"]) != set(bd["auto_cuts"])
    title = (f"Interactive Binner — {focus}   ·   IV {bd['iv']}   ·   "
             f"{'monotonic' if bd['monotonic'] else 'non-monotonic'}"
             f"{'   · coarse-classed' if edited else ''}")
    bins = bd["bins"]
    tot_good = sum(b["good"] for b in bins); tot_bad = sum(b["bad"] for b in bins)
    woe_rng = [b["woe"] for b in bins] or [0]
    stats = (f"Good {tot_good} / Bad {tot_bad}  ·  {len(bins)} bins "
             f"({bd['n_fine']} fine)  ·  IV {bd['iv']} ({bd['strength']})  ·  "
             f"WoE [{min(woe_rng):+.2f}, {max(woe_rng):+.2f}]  ·  "
             f"{'in model' if bd['in_model'] else 'not in model'}")
    return title, rows, stats


@callback(Output("reports", "children"), Input("cfg", "data"), Input("view", "value"))
def render_reports(cfg, view):
    if view != "reports":
        return no_update
    rep = svc.reports(cfg["target"], cfg["selected"], cfg["var_cuts"], cfg["C"], cfg["balanced"])
    if rep.get("insufficient"):
        return pane("Reports", html.Div("Too few Good cases to report on this target.", style={"color": MUTED}))
    th = lambda c: html.Th(c, style={"color": MUTED, "textAlign": "left", "fontSize": "10px",
                                     "fontWeight": 600, "borderBottom": f"1px solid {BORDER}", "padding": "3px 8px"})
    td = lambda c: html.Td(c, style={"padding": "2px 8px", "fontFamily": MONO, "fontSize": "11px"})
    comp_tbl = html.Table([html.Tr([th(c) for c in ["model", "KS", "AUC", "divergence", "variables"]])] +
        [html.Tr([td(r["model"]), td(r["ks"]), td(r["auc"]), td(r["divergence"]), td(r["variables"])])
         for r in rep["comparison"]], style={"width": "100%", "borderCollapse": "collapse"})
    roc = go.Figure()
    roc.add_scatter(x=[p["fpr"] for p in rep["roc_challenger"]], y=[p["tpr"] for p in rep["roc_challenger"]],
                    mode="lines", name="Challenger", line_color=ACCENT)
    roc.add_scatter(x=[p["fpr"] for p in rep["roc_champion"]], y=[p["tpr"] for p in rep["roc_champion"]],
                    mode="lines", name="Champion", line_color=MUTED)
    ks = go.Figure()
    ks.add_scatter(x=[p["pct"] for p in rep["ks_curve"]], y=[p["good"] for p in rep["ks_curve"]],
                   mode="lines", name="good", line_color=GOOD)
    ks.add_scatter(x=[p["pct"] for p in rep["ks_curve"]], y=[p["bad"] for p in rep["ks_curve"]],
                   mode="lines", name="bad", line_color=BAD)
    fo = go.Figure()
    fo.add_scatter(x=[p["score"] for p in rep["fit_odds"]], y=[p["log_odds"] for p in rep["fit_odds"]],
                   mode="markers", marker=dict(color=ACCENT, size=8))
    train_tbl = html.Table([html.Tr([th(c) for c in ["variable", "in", "contribution", "bins", "weight"]])] +
        [html.Tr([td(t["variable"]), td("✓" if t["selected"] else ""), td(t["contribution"]),
                  td(t["bins"]), td("" if t["weight"] is None else f"{t['weight']:+.2f}")])
         for t in rep["training"]], style={"width": "100%", "borderCollapse": "collapse"})
    return html.Div(style={"display": "flex", "flexDirection": "column", "gap": "6px"}, children=[
        pane("Performance — Challenger vs Champion", comp_tbl,
             html.Div(style={"display": "flex", "gap": "6px"}, children=[
                 html.Div(dcc.Graph(figure=theme(roc, 230, "ROC"), config={"displayModeBar": False}), style={"flex": "1"}),
                 html.Div(dcc.Graph(figure=theme(ks, 230, f"KS = {rep['ks']}"), config={"displayModeBar": False}), style={"flex": "1"})])),
        html.Div(style={"display": "flex", "gap": "6px", "alignItems": "stretch"}, children=[
            pane("Fit Odds", dcc.Graph(figure=theme(fo, 230, "score vs actual log-odds"),
                 config={"displayModeBar": False}), flex="1"),
            pane("Model Training", train_tbl, flex="1")]),
    ])


@callback(Output("combine-summary", "children"), Output("player-graph", "figure"),
          Input("cfg", "data"), Input("view", "value"), Input("player", "value"))
def render_combine(cfg, view, player):
    if view != "combine":
        return no_update, no_update
    cb = svc.combine(cfg["selected"], cfg["var_cuts"], cfg["C"], cfg["balanced"])
    pl = svc.combine_player(player, cfg["selected"], cfg["var_cuts"], cfg["C"], cfg["balanced"])
    summary = html.Div([
        html.Span("OvR in-sample accuracy  ", style={"color": MUTED}),
        html.B(f"{cb['in_sample_accuracy']:.1%}", style={"fontSize": "18px", "color": ACCENT}),
        html.Span(f"   ·  {cb['variables']} variables  ·  rule champion {cb['rule_champion']:.1%} "
                  f"(honest LOO ≈ 85.2% with all vars)", style={"color": MUTED})])
    fig = go.Figure()
    fig.add_bar(x=[s["prob"] for s in reversed(pl["scores"])],
                y=[s["archetype"] for s in reversed(pl["scores"])], orientation="h",
                marker_color=[ACCENT if s["archetype"] == pl["predicted"] else "#c4ccd2"
                              for s in reversed(pl["scores"])])
    ok = "✓" if pl["predicted"] == pl["truth"] else "✗"
    fig = theme(fig, 300, f"{player}  ·  truth {pl['truth']} → argmax {pl['predicted']} {ok}")
    return summary, fig


@callback(Output("loo-out", "children"), Input("loo-btn", "n_clicks"),
          State("cfg", "data"), prevent_initial_call=True)
def run_loo(n, cfg):
    r = svc.combine_loo(cfg["selected"], cfg["C"], cfg["balanced"])
    return f"Leave-one-out accuracy: {r['loo_accuracy']:.1%}  (rule champion {r['rule_champion']:.1%})"


if __name__ == "__main__":
    app.run(debug=False, port=8050)
