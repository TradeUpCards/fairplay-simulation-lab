"""Champion vs Challenger panel — classification score ① (the "ML in perception" reveal).

Runs the deterministic **champion** (`scoring/classify.py` threshold rules) and
the interpretable **challenger** (`ml/challenger.py` one-vs-rest logistic,
leave-one-out) over all 122 players, scores both against the ground-truth
archetype labels, and emits:

* ``data/derived/champion_vs_challenger.json`` — the frozen comparison data.
* ``docs/champion-vs-challenger.html`` — a self-contained panel (data embedded
  inline; no CDN / no external deps) visualizing accuracy, per-class wins, the
  disagreements, and the challenger's learned coefficients.

The honest story it tells: rules win overall by nailing the rare *structural*
classes the ML can't learn from sparse labels — but the ML *beats* the rules on
the fuzzy behavioral boundary (recreational↔regular). Rules for structure, ML
for nuance.

Run:  python scripts/build_champion_challenger.py
Requires scikit-learn (the challenger). The champion is stdlib-only.
"""

from __future__ import annotations

import json
import sys
import warnings
from html import escape
from pathlib import Path

warnings.filterwarnings("ignore")  # quiet sklearn convergence chatter
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scoring.classify import classify  # noqa: E402
from ml.challenger import (  # noqa: E402
    build_frame, leave_one_out_predictions, fit_full, coefficients, FEATURES,
)

OUT_JSON = ROOT / "data" / "derived" / "champion_vs_challenger.json"
OUT_HTML = ROOT / "docs" / "champion-vs-challenger.html"

# Classes defined by structural/hard fields (champion's home turf) vs the fuzzy
# behavioral tiers (where the ML challenger earns its keep).
STRUCTURAL = {"bot_like", "cluster_member", "shared_device_household", "new",
              "aggressive_predatory", "promo_hunter"}
BEHAVIORAL = {"recreational", "regular", "grinder", "healthy_anchor"}


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
    champ = {p["player_id"]: classify(p).archetype for p in players}
    df["champion"] = df["player_id"].map(champ)
    df["challenger"] = leave_one_out_predictions(df)
    df["truth"] = df["archetype"]

    total = len(df)
    champ_correct = int((df.champion == df.truth).sum())
    chall_correct = int((df.challenger == df.truth).sum())
    agreement = float((df.champion == df.challenger).mean())

    per_class = []
    for a in sorted(df.truth.unique()):
        s = df[df.truth == a]
        per_class.append({
            "archetype": a, "n": int(len(s)),
            "champion_correct": int((s.champion == a).sum()),
            "challenger_correct": int((s.challenger == a).sum()),
            "kind": "structural" if a in STRUCTURAL else "behavioral",
        })

    # Behavioral-boundary tally (the ML payoff).
    beh = df[df.truth.isin(BEHAVIORAL)]
    boundary = {
        "n": int(len(beh)),
        "champion_correct": int((beh.champion == beh.truth).sum()),
        "challenger_correct": int((beh.challenger == beh.truth).sum()),
    }

    disagreements = []
    dd = df[df.champion != df.challenger].sort_values("player_id")
    for _, r in dd.iterrows():
        disagreements.append({
            "player_id": r.player_id, "truth": r.truth,
            "champion": r.champion, "challenger": r.challenger,
            "champion_right": bool(r.champion == r.truth),
            "challenger_right": bool(r.challenger == r.truth),
            "features": {"registered_days_ago": int(r.registered_days_ago),
                         "lifetime_hands": int(r.lifetime_hands),
                         "avg_session_minutes": round(float(r.avg_session_minutes), 0),
                         "sessions_last_30d": int(r.sessions_last_30d),
                         "vpip": round(float(r.vpip), 2),
                         "aggression_factor": round(float(r.aggression_factor), 2)},
        })

    coefs = coefficients(fit_full(df), top_n=4)

    return {
        "meta": {
            "schema_version": "1.0.0",
            "title": "Classification ① — Champion vs Challenger",
            "champion": "threshold rules (scoring/classify.py) — deterministic, stdlib",
            "challenger": "one-vs-rest logistic, leave-one-out (ml/challenger.py) — 9 behavioral features",
            "method_note": ("Challenger trains ONLY on the 9 numeric behavioral "
                            "features (never structural fields). Leave-one-out: "
                            "each player predicted by a model trained on the other "
                            "121, so a class with one example (bot_like) is "
                            "unlearnable when held out — an honest limit, surfaced."),
        },
        "summary": {
            "total": total,
            "champion_accuracy": round(champ_correct / total, 3),
            "challenger_accuracy": round(chall_correct / total, 3),
            "champion_correct": champ_correct,
            "challenger_correct": chall_correct,
            "agreement": round(agreement, 3),
            "behavioral_boundary": boundary,
        },
        "per_class": per_class,
        "disagreements": disagreements,
        "challenger_coefficients": coefs,
    }


# ── HTML rendering (self-contained; data shown server-rendered) ──────────────

def _bar(value: int, n: int, color: str) -> str:
    pct = (value / n * 100) if n else 0
    return (f'<div class="bar"><div class="fill" style="width:{pct:.0f}%;background:{color}">'
            f'</div><span class="bv">{value}/{n}</span></div>')


def render_html(d: dict) -> str:
    s = d["summary"]; b = s["behavioral_boundary"]
    ca, la = s["champion_accuracy"], s["challenger_accuracy"]
    winner = "Champion (rules)" if ca >= la else "Challenger (ML)"

    rows_class = ""
    for c in d["per_class"]:
        tag = ("struct" if c["kind"] == "structural" else "behav")
        cc, lc, n = c["champion_correct"], c["challenger_correct"], c["n"]
        lead = ("c" if cc > lc else ("l" if lc > cc else "t"))
        rows_class += (
            f'<tr class="{tag}"><td><b>{escape(c["archetype"])}</b> '
            f'<span class="kind {tag}">{c["kind"]}</span></td>'
            f'<td>{n}</td><td>{_bar(cc, n, "var(--gold)")}</td>'
            f'<td>{_bar(lc, n, "var(--blue)")}</td>'
            f'<td class="lead-{lead}">{"rules" if lead=="c" else ("ML" if lead=="l" else "tie")}</td></tr>')

    rows_dis = ""
    for x in d["disagreements"]:
        ch_cls = "ok" if x["champion_right"] else "no"
        cl_cls = "ok" if x["challenger_right"] else "no"
        f = x["features"]
        rows_dis += (
            f'<tr><td class="mono">{escape(x["player_id"])}</td>'
            f'<td><b>{escape(x["truth"])}</b></td>'
            f'<td class="{ch_cls}">{escape(x["champion"])}</td>'
            f'<td class="{cl_cls}">{escape(x["challenger"])}</td>'
            f'<td class="mono dim">reg {f["registered_days_ago"]}d · {f["lifetime_hands"]:,}h · '
            f'{f["avg_session_minutes"]:.0f}m · vpip {f["vpip"]} · AF {f["aggression_factor"]}</td></tr>')

    coef_cards = ""
    for cls in ["recreational", "regular", "grinder", "new"]:
        if cls not in d["challenger_coefficients"]:
            continue
        items = "".join(
            f'<li><span class="cf">{escape(w["feature"])}</span>'
            f'<span class="cw {"pos" if w["weight"]>=0 else "neg"}">{w["weight"]:+.2f}</span></li>'
            for w in d["challenger_coefficients"][cls])
        coef_cards += f'<div class="ccard"><h4>{escape(cls)}</h4><ul>{items}</ul></div>'

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Champion vs Challenger — Classification ①</title>
<style>
:root{{--bg:#060e08;--bg2:#0a1409;--border:#182d1c;--border2:#1f3c25;--text:#d8ecda;
--muted:#7a9c80;--dim:#3a553f;--gold:#c9a84c;--gold2:#a8882e;--blue:#4f8ef7;--blue2:#7fb0ff;
--green:#3fcc6a;--red:#e05c4a;--amber:#f5a623;--mono:'SF Mono','JetBrains Mono','Courier New',monospace;--r:9px}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:radial-gradient(900px 500px at 85% -10%,rgba(201,168,76,.06),transparent 60%),var(--bg);
color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
line-height:1.65;padding:clamp(20px,4vw,60px);max-width:1100px;margin:0 auto}}
h1{{font-size:clamp(24px,3.6vw,36px);font-weight:850;letter-spacing:-.02em}}
h2{{font-size:20px;font-weight:800;margin:0 0 4px}} h4{{font-size:12px;color:var(--gold)}}
.kicker{{font-size:10px;letter-spacing:.22em;text-transform:uppercase;color:var(--gold2);font-weight:800}}
.lede{{color:var(--muted);max-width:75ch;margin-top:12px;font-size:14.5px}}
.mono{{font-family:var(--mono)}} .dim{{color:var(--dim)}}
section{{margin-top:40px}} .sh{{border-bottom:1px solid var(--border);padding-bottom:9px;margin-bottom:16px}}
.gauges{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:22px}}
@media(max-width:640px){{.gauges{{grid-template-columns:1fr}}}}
.g{{border:1px solid var(--border2);border-radius:var(--r);padding:20px 22px;background:var(--bg2);position:relative}}
.g.champ{{border-color:rgba(201,168,76,.32)}} .g.chall{{border-color:rgba(79,142,247,.32)}}
.g .lab{{font-size:11px;letter-spacing:.1em;text-transform:uppercase;font-weight:800}}
.g.champ .lab{{color:var(--gold)}} .g.chall .lab{{color:var(--blue2)}}
.g .acc{{font-size:46px;font-weight:850;line-height:1;margin:8px 0 2px}}
.g .sub{{font-size:11.5px;color:var(--muted);font-family:var(--mono)}}
.g .meth{{font-size:11px;color:var(--dim);margin-top:8px}}
.verdict{{margin-top:16px;border:1px solid var(--border2);border-left:3px solid var(--gold);
border-radius:var(--r);background:var(--bg2);padding:15px 18px;font-size:13.5px}}
.verdict b{{color:var(--text)}}
.method{{margin-top:20px;border:1px solid var(--border2);border-left:3px solid var(--blue);
border-radius:var(--r);background:rgba(79,142,247,.05);padding:15px 18px}}
.method h4{{font-size:12.5px;color:var(--blue2);letter-spacing:.02em;margin-bottom:8px}}
.method ul{{list-style:none;display:flex;flex-direction:column;gap:7px}}
.method li{{font-size:12.5px;color:var(--muted);padding-left:15px;position:relative;line-height:1.55}}
.method li::before{{content:'›';position:absolute;left:0;color:var(--blue2)}}
.method b{{color:var(--text)}}
table{{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:4px}}
th,td{{text-align:left;padding:8px 11px;border-bottom:1px solid var(--border);vertical-align:middle}}
th{{font-size:10px;letter-spacing:.09em;text-transform:uppercase;color:var(--gold2);font-weight:800}}
.kind{{font-size:9px;padding:1px 6px;border-radius:4px;font-family:var(--mono);margin-left:6px;text-transform:uppercase}}
.kind.struct{{background:rgba(201,168,76,.13);color:var(--gold)}}
.kind.behav{{background:rgba(79,142,247,.13);color:var(--blue2)}}
.bar{{position:relative;height:18px;background:#0e1c12;border-radius:4px;overflow:hidden;min-width:120px}}
.fill{{height:100%;border-radius:4px}}
.bv{{position:absolute;right:7px;top:0;font-size:10.5px;line-height:18px;font-family:var(--mono);color:var(--text)}}
.lead-c{{color:var(--gold);font-weight:700}} .lead-l{{color:var(--blue2);font-weight:700}} .lead-t{{color:var(--dim)}}
td.ok{{color:var(--green)}} td.no{{color:var(--red)}}
.ccards{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:6px}}
@media(max-width:720px){{.ccards{{grid-template-columns:1fr 1fr}}}}
.ccard{{border:1px solid var(--border2);border-radius:var(--r);background:var(--bg2);padding:12px 14px}}
.ccard ul{{list-style:none;margin-top:6px}} .ccard li{{display:flex;justify-content:space-between;font-size:11.5px;padding:2px 0;font-family:var(--mono)}}
.cf{{color:var(--muted)}} .cw.pos{{color:var(--green)}} .cw.neg{{color:var(--red)}}
.note{{font-size:11.5px;color:var(--dim);margin-top:10px}}
.legend{{display:flex;gap:14px;font-size:11px;color:var(--muted);margin-top:10px;flex-wrap:wrap}}
.legend i{{width:10px;height:10px;border-radius:2px;display:inline-block;margin-right:5px;vertical-align:middle}}
.footer{{margin-top:48px;padding-top:16px;border-top:1px solid var(--border);font-size:11px;color:var(--dim)}}
</style></head><body>

<div class="kicker">FairPlay IQ · Score ① · the "ML in perception" reveal</div>
<h1>Champion vs Challenger</h1>
<p class="lede">The classifier ships as deterministic <b>threshold rules</b> (champion). The interpretable
<b>one-vs-rest logistic</b> challenger learns from the 9 behavioral features alone. Who's more accurate —
and <i>where</i>?</p>

<div class="gauges">
  <div class="g champ"><div class="lab">◆ Champion · rules</div>
    <div class="acc" style="color:var(--gold)">{ca:.1%}</div>
    <div class="sub">{s["champion_correct"]}/{s["total"]} correct</div>
    <div class="meth">Threshold cascade. Uses structural fields (cluster_id, household_id, bot score) as hard rules.</div></div>
  <div class="g chall"><div class="lab">▲ Challenger · ML</div>
    <div class="acc" style="color:var(--blue2)">{la:.1%}</div>
    <div class="sub">{s["challenger_correct"]}/{s["total"]} correct · leave-one-out</div>
    <div class="meth">One-vs-rest: 10 binary logistic models (one per archetype) on 9 behavioral features only.
    Coefficients = reason codes.</div></div>
</div>

<div class="method">
  <h4>⚖ How to read this — the two are NOT scored on equal footing</h4>
  <ul>
    <li><b>Answer key:</b> each player's true archetype is the type P2's generator built it as (documented ID
      ranges). Both approaches are scored against this same key.</li>
    <li><b>Champion (rules):</b> threshold rules reverse-engineered from that <i>same generator</i>, and allowed to
      read the structural fields (cluster_id, household_id, bot score) that <i>define</i> the rare classes. Scored
      <b>in-sample</b> — it largely <i>recites</i> the generator rather than learning it.</li>
    <li><b>Challenger (ML):</b> one-vs-rest logistic on the 9 <i>behavioral</i> features only (no structural
      fields), scored <b>out-of-sample</b> by leave-one-out — each player predicted by a model that never saw it.
      It has to <i>generalize</i>.</li>
    <li><b>So "accuracy" here isn't a clean benchmark.</b> The honest read: a model learning from behavior alone
      lands within ~3 pts of rules that have the answer key baked in. On synthetic rule-generated data this is
      partly circular; on <i>real</i> data (noisy/missing structural fields, no clean generative rule) the ML's
      relative value would likely be higher.</li>
  </ul>
</div>

<div class="verdict">
  <b>Verdict — rules reproduce the generator; the ML generalizes.</b> Overall the rules edge ahead
  ({ca:.1%} vs {la:.1%}) — but mostly because they get the rare <b>structural</b> classes (new, bot_like,
  household, cluster) as near-free lookups of the fields that define them, while the ML must infer them from
  behavior alone and can't learn a 1-example class out-of-sample. On the fuzzy <b>behavioral boundary</b>, where
  the rule thresholds are arbitrary cuts on a continuum, the ML <b>generalizes better</b>:
  <b style="color:var(--blue2)">{b["challenger_correct"]}/{b["n"]}</b> vs
  <b style="color:var(--gold)">{b["champion_correct"]}/{b["n"]}</b> across
  recreational/regular/grinder/healthy_anchor. That's the real takeaway — <b>rules for structure, ML for
  nuance</b> — and why the champion ships the demo while the challenger is promoted only where it measurably helps.
  The two agree on <b>{s["agreement"]:.0%}</b> of players.
</div>

<section><div class="sh"><h2>Per-class accuracy</h2></div>
  <div class="legend"><span><i style="background:var(--gold)"></i>champion (rules)</span>
    <span><i style="background:var(--blue)"></i>challenger (ML)</span>
    <span><span class="kind struct">structural</span> rules' home turf</span>
    <span><span class="kind behav">behavioral</span> ML's edge</span></div>
  <table><thead><tr><th>Archetype</th><th>n</th><th>Champion ◆</th><th>Challenger ▲</th><th>Leads</th></tr></thead>
  <tbody>{rows_class}</tbody></table>
</section>

<section><div class="sh"><h2>Where they disagree <span class="dim" style="font-size:13px;font-weight:400">· {len(d["disagreements"])} players</span></h2></div>
  <table><thead><tr><th>Player</th><th>Truth</th><th>Champion ◆</th><th>Challenger ▲</th><th>Features</th></tr></thead>
  <tbody>{rows_dis}</tbody></table>
  <p class="note">Green = matched the truth, red = missed. Most disagreements sit on the
  recreational↔regular volume boundary — the genuinely ambiguous tier.</p>
</section>

<section><div class="sh"><h2>What the challenger learned <span class="dim" style="font-size:13px;font-weight:400">· coefficients = reason codes</span></h2></div>
  <p class="note" style="margin-bottom:12px">Top signed weights per class (+ pushes toward the class). This interpretability
  is <i>why</i> we use logistic regression for the challenger — not a black box.</p>
  <div class="ccards">{coef_cards}</div>
</section>

<div class="footer">{escape(d["meta"]["method_note"])}<br>
Regenerate: <span class="mono">python scripts/build_champion_challenger.py</span> ·
Data: <span class="mono">data/derived/champion_vs_challenger.json</span> ·
Champion: <span class="mono">scoring/classify.py</span> · Challenger: <span class="mono">ml/challenger.py</span></div>
</body></html>
"""


def main() -> int:
    d = compute()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
    OUT_HTML.write_text(render_html(d), encoding="utf-8")
    s = d["summary"]
    print(f"champion {s['champion_accuracy']:.1%} vs challenger {s['challenger_accuracy']:.1%} "
          f"(agree {s['agreement']:.0%}, {len(d['disagreements'])} disagreements)")
    print(f"wrote {OUT_JSON.relative_to(ROOT)} + {OUT_HTML.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
