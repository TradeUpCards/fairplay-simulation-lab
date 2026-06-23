# `ml/` — Classification challenger & scorecard tools

The interpretable ML **challenger** for the classification score (①), raced
against the deterministic rule **champion** in `scoring/classify.py`. Requires
scikit-learn / pandas / numpy — the scoring core stays stdlib-only.

```bash
pip install -r ml/requirements.txt
```

## What's here

| File | What it is |
|---|---|
| `challenger.py` | One-vs-rest logistic (10 binary models on the 9 behavioral features), leave-one-out eval, coefficients. |
| `scorecard.py` | The scorecard math: WoE binning, Information Value, points (PDO), KS/AUC. |
| `service.py` | Pure, JSON-returning model-builder API (the UI-agnostic seam). |

## The three ways to use it

1. **Frozen read-only panels** (built by `scripts/build_*.py`, viewable by
   double-click, no Python needed):
   - `docs/champion-vs-challenger.html` — accuracy head-to-head vs the rules.
   - `docs/scorecard.html` — all 10 scorecards + the argmax combination.
2. **Interactive Model Builder** — the FICO-Model-Builder-style workbench (Dash
   + AG Grid): one attribute grid with in/out checkboxes + editable bins,
   double-click a row to open its binner, Reports vs a Champion, and the OvR
   combine view. It calls `ml/service.py` only.
   ```bash
   pip install -r tools/model-builder/requirements.txt
   python tools/model-builder/app.py            # → http://127.0.0.1:8050
   ```
   See `tools/model-builder/README.md`.
3. **Regenerate the frozen artifacts** after a data/model change:
   ```bash
   python scripts/build_champion_challenger.py
   python scripts/build_scorecard.py
   ```

## Honesty notes (also surfaced in the panels)

- The comparison is **not a clean benchmark**: the champion is reverse-engineered
  from the data generator and reads the structural fields that define the rare
  classes (in-sample); the challenger uses behavioral features only and is scored
  out-of-sample (leave-one-out). Champion 88.5% vs challenger 85.2%.
- On this **synthetic** data the classes are near-perfectly separable, so IVs
  blow past the textbook scale and KS ≈ 1.0. On real data expect IV 0.1–0.5,
  KS 0.3–0.6.
