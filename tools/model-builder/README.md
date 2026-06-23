# FairPlay Model Builder (Dash + AG Grid)

A FICO-Model-Builder-style scorecard workbench for the one-vs-rest
classification challenger. Internal P3/dev tool — **not** part of the
deterministic demo path.

```bash
pip install -r tools/model-builder/requirements.txt   # add --user on Windows w/o admin
python tools/model-builder/app.py                      # → http://127.0.0.1:8050
```

## What it does

**Scorecard Editor** — one attribute grid: every candidate predictor with an
**in/out checkbox** and an **editable bin count**. Tick/untick a variable → the
model re-fits and the relative-importance chart + KS/AUC/divergence update. Edit
`bins` inline, or **double-click a row** to open its **Interactive Binner** (WoE
plot + bin table + points + a coarse-classing slider).

**Reports** — Challenger (your edits) vs auto-built **Champion**: KS curve, ROC
overlay, model-training table, and a Fit-Odds plot.

**Combine (OvR)** — argmax of the 10 scorecards vs the rule champion (88.5%),
with a leave-one-out honesty button and a per-player breakdown.

## Architecture

```
ml/service.py         ← pure, JSON-returning model functions (the seam)
tools/model-builder/  ← Dash UI shell (this app) — calls ml/service only
ml/scorecard.py       ← WoE / IV / points / KS engine
ml/challenger.py      ← one-vs-rest logistic
```

All modeling goes through `ml/service.py`, which returns plain
JSON-serializable dicts. The Dash app imports it directly; a future
**React + FastAPI** build would wrap the *same* service unchanged and rebuild
only the UI shell. The engine and the service seam are the durable parts.

## Honesty note

The data is synthetic and the archetype classes are near-perfectly separable, so
IV / KS / divergence are inflated (real-world IV 0.1–0.5, KS 0.3–0.6). The
in-sample accuracy is optimistic; the leave-one-out number (≈85.2%) is the honest
one. See `docs/champion-vs-challenger.html`.
