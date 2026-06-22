"""Scorecard panel — the WoE / IV / points / KS view of the OvR challenger.

Builds the FICO/SAS-style scorecard for all 10 archetype classes, plus the
argmax-combination view that reconciles with the champion-vs-challenger panel.
Emits ``data/derived/scorecards.json`` + a self-contained
``docs/scorecard.html`` (data server-rendered; no CDN).

Run:  python scripts/build_scorecard.py   (requires scikit-learn)
"""

from __future__ import annotations

import json
import sys
import warnings
from html import escape
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.challenger import build_frame  # noqa: E402
from ml.scorecard import all_scorecards, combine, PDO  # noqa: E402

OUT_JSON = ROOT / "data" / "derived" / "scorecards.json"
OUT_HTML = ROOT / "docs" / "scorecard.html"
TOP_FEATURES_WITH_BINS = 3  # show WoE+points bins for the top-N IV features per class


def truth_of(pid: str) -> str:
    n = int(pid.split("-")[1])
    for hi, lab in [(107, "new"), (141, "recreational"), (163, "regular"),
                    (175, "grinder"), (183, "aggressive_predatory"),
                    (191, "promo_hunter"), (197, "shared_device_household"),
                    (202, "cluster_member"), (220, "healthy_anchor")]:
        if n <= hi:
            return lab
    return "bot_like"


def compute() -> dict:
    players = json.loads((ROOT / "data" / "players.json").read_text(encoding="utf-8"))["players"]
    df = build_frame(players, truth_of)
    cards = all_scorecards(df)
    comb = combine(df, cards)
    # Strip internal model handles before serializing.
    clean = []
    for c in cards:
        clean.append({k: v for k, v in c.items() if not k.startswith("_")})
    return {
        "meta": {
            "schema_version": "1.0.0",
            "title": "Classification ① — Scorecards (one-vs-rest)",
            "pdo": PDO,
            "development_note": ("In-sample development view on all 122 players "
                                 "(how scorecards are built). The honest "
                                 "out-of-sample accuracy vs the rule champion is "
                                 "the leave-one-out 85.2% in "
                                 "champion-vs-challenger.html."),
            "synthetic_caveat": ("IVs are extreme (>2) and KS/AUC ~1.0 because "
                                 "the synthetic data has near-perfectly separable "
                                 "classes. On real data IV is typically 0.1–0.5 "
                                 "and KS 0.3–0.6."),
        },
        "scorecards": clean,
        "combination": {k: v for k, v in comb.items()},
    }


# ── HTML ─────────────────────────────────────────────────────────────────────

def _pts(p: int) -> str:
    cls = "pos" if p > 0 else ("neg" if p < 0 else "zero")
    return f'<span class="pts {cls}">{p:+d}</span>'


def _iv_table(card: dict) -> str:
    rows = ""
    for f in card["features"]:
        sw = {"unpredictive": "w0", "weak": "w1", "medium": "w2",
              "strong": "w3", "very strong": "w4"}.get(f["strength"], "w2")
        rows += (f'<tr><td class="mono">{escape(f["feature"])}</td>'
                 f'<td>{f["iv"]:.2f}</td>'
                 f'<td><span class="sb {sw}">{escape(f["strength"])}</span></td>'
                 f'<td class="mono dim">{f["coef"]:+.2f}</td></tr>')
    return (f'<table class="iv"><thead><tr><th>Feature</th><th>IV</th>'
            f'<th>Strength</th><th>WoE coef</th></tr></thead><tbody>{rows}</tbody></table>')


def _bins_table(card: dict) -> str:
    out = ""
    for f in card["features"][:TOP_FEATURES_WITH_BINS]:
        rows = ""
        for b in f["bins"]:
            rows += (f'<tr><td class="mono">{escape(b["range"])}</td>'
                     f'<td>{b["n"]}</td><td>{b["pos"]}</td>'
                     f'<td class="mono">{b["woe"]:+.2f}</td>'
                     f'<td>{_pts(b["points"])}</td></tr>')
        out += (f'<div class="bins"><div class="bh">{escape(f["feature"])} '
                f'<span class="dim">· IV {f["iv"]:.2f}</span></div>'
                f'<table><thead><tr><th>Bin (range)</th><th>n</th><th>in-class</th>'
                f'<th>WoE</th><th>Points</th></tr></thead><tbody>{rows}</tbody></table></div>')
    return out


def _card(card: dict, idx: int) -> str:
    ks = "—" if card["ks"] is None else f'{card["ks"]:.2f}'
    auc = "—" if card["auc"] is None else f'{card["auc"]:.2f}'
    flag = (' <span class="lc">⚠ {} example(s) — bins unreliable</span>'
            .format(card["n_positive"]) if card["low_confidence"] else "")
    op = " open" if idx == 0 else ""
    return (f'<details class="card"{op}><summary>'
            f'<span class="arch">{escape(card["archetype"])}</span>'
            f'<span class="meta">n={card["n_positive"]} · base {card["base_points"]} · '
            f'KS {ks} · AUC {auc}{flag}</span></summary>'
            f'<div class="cbody"><div class="ivcol"><h4>Feature power (IV-ranked)</h4>'
            f'{_iv_table(card)}</div>'
            f'<div class="bincol"><h4>WoE bins &amp; points — top {TOP_FEATURES_WITH_BINS} features</h4>'
            f'{_bins_table(card)}</div></div></details>')


def _example(pid: str, ex: dict) -> str:
    bars = ""
    top = ex["scores"][0]["prob"] or 1
    for s in ex["scores"]:
        win = " win" if s["archetype"] == ex["predicted"] else ""
        tru = " truth" if s["archetype"] == ex["truth"] else ""
        w = (s["prob"] / top * 100) if top else 0
        bars += (f'<div class="exrow{win}{tru}"><span class="exa">{escape(s["archetype"])}</span>'
                 f'<span class="exbar"><span class="exfill" style="width:{w:.0f}%"></span></span>'
                 f'<span class="exp">{s["prob"]:.2f}</span></div>')
    ok = "✓ correct" if ex["predicted"] == ex["truth"] else "✗ miss"
    okc = "ok" if ex["predicted"] == ex["truth"] else "no"
    return (f'<div class="excard"><div class="exhd"><b>{escape(pid)}</b> · truth '
            f'<b>{escape(ex["truth"])}</b> → argmax picks <b>{escape(ex["predicted"])}</b> '
            f'<span class="{okc}">{ok}</span></div>{bars}</div>')


def render_html(d: dict) -> str:
    cards = "".join(_card(c, i) for i, c in enumerate(d["scorecards"]))
    comb = d["combination"]
    examples = "".join(_example(pid, ex) for pid, ex in comb["examples"].items())
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Scorecards — Classification ① (one-vs-rest)</title>
<style>
:root{{--bg:#060e08;--bg2:#0a1409;--border:#182d1c;--border2:#1f3c25;--text:#d8ecda;
--muted:#7a9c80;--dim:#3a553f;--gold:#c9a84c;--gold2:#a8882e;--blue:#4f8ef7;--blue2:#7fb0ff;
--green:#3fcc6a;--red:#e05c4a;--amber:#f5a623;--mono:'SF Mono','JetBrains Mono','Courier New',monospace;--r:9px}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:radial-gradient(900px 500px at 85% -10%,rgba(201,168,76,.06),transparent 60%),var(--bg);
color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
line-height:1.6;padding:clamp(20px,4vw,60px);max-width:1080px;margin:0 auto}}
h1{{font-size:clamp(24px,3.6vw,34px);font-weight:850;letter-spacing:-.02em}}
h2{{font-size:19px;font-weight:800;margin:0 0 4px}} h4{{font-size:11px;color:var(--gold);text-transform:uppercase;letter-spacing:.08em;margin-bottom:7px}}
.kicker{{font-size:10px;letter-spacing:.22em;text-transform:uppercase;color:var(--gold2);font-weight:800}}
.lede{{color:var(--muted);max-width:76ch;margin-top:12px;font-size:14.5px}}
.mono{{font-family:var(--mono)}} .dim{{color:var(--dim)}}
section{{margin-top:36px}} .sh{{border-bottom:1px solid var(--border);padding-bottom:8px;margin-bottom:14px}}
.caveat{{margin-top:20px;border:1px solid var(--border2);border-left:3px solid var(--amber);
border-radius:var(--r);background:rgba(245,166,35,.05);padding:14px 17px;font-size:12.5px;color:var(--muted)}}
.caveat b{{color:var(--text)}}
details.card{{border:1px solid var(--border2);border-radius:var(--r);background:var(--bg2);margin-bottom:9px;overflow:hidden}}
details.card[open]{{border-color:var(--gold2)}}
summary{{cursor:pointer;padding:12px 16px;display:flex;flex-wrap:wrap;align-items:baseline;gap:12px;list-style:none}}
summary::-webkit-details-marker{{display:none}}
summary::before{{content:'▸';color:var(--gold2);margin-right:2px;font-size:11px}}
details[open] summary::before{{content:'▾'}}
.arch{{font-weight:800;font-size:14px;color:var(--text)}}
summary .meta{{font-size:11px;color:var(--muted);font-family:var(--mono)}}
.lc{{color:var(--amber)}}
.cbody{{display:grid;grid-template-columns:1fr 1.4fr;gap:18px;padding:4px 16px 16px}}
@media(max-width:740px){{.cbody{{grid-template-columns:1fr}}}}
table{{width:100%;border-collapse:collapse;font-size:11.5px}}
th,td{{text-align:left;padding:5px 9px;border-bottom:1px solid var(--border)}}
th{{font-size:9px;letter-spacing:.07em;text-transform:uppercase;color:var(--gold2);font-weight:800}}
.sb{{font-size:9px;padding:1px 6px;border-radius:4px;font-family:var(--mono)}}
.sb.w0{{background:#13201700;color:var(--dim)}} .sb.w1{{background:rgba(122,156,128,.13);color:var(--muted)}}
.sb.w2{{background:rgba(79,142,247,.13);color:var(--blue2)}} .sb.w3{{background:rgba(63,204,106,.13);color:var(--green)}}
.sb.w4{{background:rgba(201,168,76,.16);color:var(--gold)}}
.bins{{margin-bottom:12px}} .bh{{font-family:var(--mono);font-size:11px;color:var(--text);margin-bottom:3px}}
.pts{{font-family:var(--mono);font-weight:700}} .pts.pos{{color:var(--green)}} .pts.neg{{color:var(--red)}} .pts.zero{{color:var(--dim)}}
.excard{{border:1px solid var(--border2);border-radius:var(--r);background:var(--bg2);padding:14px 16px;margin-bottom:12px}}
.exhd{{font-size:13px;margin-bottom:10px}} .exhd b{{color:var(--text)}}
.ok{{color:var(--green)}} .no{{color:var(--red)}}
.exrow{{display:grid;grid-template-columns:150px 1fr 42px;align-items:center;gap:9px;font-size:11.5px;padding:1.5px 0}}
.exa{{font-family:var(--mono);color:var(--muted);text-align:right}}
.exbar{{height:11px;background:#0e1c12;border-radius:3px;overflow:hidden}}
.exfill{{height:100%;background:var(--blue);border-radius:3px;opacity:.5}}
.exp{{font-family:var(--mono);color:var(--muted);text-align:right}}
.exrow.win .exa{{color:var(--blue2);font-weight:700}} .exrow.win .exfill{{opacity:1}}
.exrow.truth .exa::after{{content:' ◆';color:var(--gold)}}
.combo{{border:1px solid var(--border2);border-radius:var(--r);background:var(--bg2);padding:16px 18px;margin-bottom:16px}}
.combo .big{{font-size:30px;font-weight:850;color:var(--blue2)}}
.reconcile{{border-left:3px solid var(--gold);background:rgba(201,168,76,.05);border-radius:var(--r);padding:13px 16px;font-size:12.5px;color:var(--muted);margin-top:6px}}
.reconcile b{{color:var(--text)}} a{{color:var(--gold)}}
.footer{{margin-top:46px;padding-top:16px;border-top:1px solid var(--border);font-size:11px;color:var(--dim)}}
</style></head><body>

<div class="kicker">FairPlay IQ · Score ① · the scorecard view</div>
<h1>One-vs-Rest Scorecards</h1>
<p class="lede">Each archetype is a standalone yes/no <b>scorecard</b> — the binary-native craft the kickoff
picks OvR for. Per feature: <b>WoE</b> bins (how class-ish each range is), <b>IV</b> (the feature's separating
power), integer <b>points</b> (PDO = {int(d["meta"]["pdo"])}, + pushes toward the class), and <b>KS/AUC</b>
(separation). Then all 10 combine by <b>argmax</b> — and that ensemble is the OvR challenger.</p>

<div class="caveat"><b>Read this first — synthetic-data artifact.</b> {escape(d["meta"]["synthetic_caveat"])}
The textbook IV scale (weak 0.02–0.1 · medium 0.1–0.3 · strong 0.3–0.5) is blown out here because the generator
made classes cleanly separable — most signal lands in a single bin and KS hits 1.0. That's a property of synthetic
data, not a great model. {escape(d["meta"]["development_note"])}</div>

<section><div class="sh"><h2>The 10 scorecards <span class="dim" style="font-size:13px;font-weight:400">· click to expand</span></h2></div>
{cards}
</section>

<section><div class="sh"><h2>How the 10 combine → the OvR prediction</h2></div>
  <div class="combo">
    <div style="font-size:12px;color:var(--muted);margin-bottom:4px">Rule: <span class="mono">{escape(comb["rule"])}</span></div>
    <span class="big">{comb["in_sample_accuracy"]:.1%}</span>
    <span style="color:var(--muted)"> in-sample · {comb["in_sample_correct"]}/{comb["total"]} correct (development)</span>
    <div class="reconcile"><b>Reconciling with the champion.</b> This {comb["in_sample_accuracy"]:.1%} is
    <i>in-sample</i> (scored on the same players the scorecards were built from). The honest, out-of-sample number —
    each player predicted by a model that never saw it — is <b>85.2%</b> (leave-one-out), vs the rule champion's
    <b>88.5%</b>. See <a href="champion-vs-challenger.html">champion-vs-challenger.html</a> for that head-to-head and
    why the rules lead on the rare structural classes.</div>
  </div>
  <h4 style="margin-bottom:10px">Worked examples — one player scored under all 10 scorecards (◆ = truth, bar = P(class))</h4>
  {examples}
</section>

<div class="footer">Regenerate: <span class="mono">python scripts/build_scorecard.py</span> ·
Data: <span class="mono">data/derived/scorecards.json</span> ·
Model: <span class="mono">ml/scorecard.py</span> (WoE-fitted one-vs-rest logistic) ·
Honest accuracy: <span class="mono">docs/champion-vs-challenger.html</span></div>
</body></html>
"""


def main() -> int:
    d = compute()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
    OUT_HTML.write_text(render_html(d), encoding="utf-8")
    c = d["combination"]
    print(f"10 scorecards · combine in-sample {c['in_sample_accuracy']:.1%} "
          f"({c['in_sample_correct']}/{c['total']})")
    print(f"wrote {OUT_JSON.relative_to(ROOT)} + {OUT_HTML.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
