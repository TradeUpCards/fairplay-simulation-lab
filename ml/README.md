# `ml/` — Classification challenger & scorecard tools

The interpretable ML **challenger** for the classification score (①), raced
against the deterministic rule **champion** in `scoring/classify.py`. Requires
scikit-learn / pandas / numpy (and streamlit for the workbench) — the scoring
core stays stdlib-only.

```bash
pip install -r ml/requirements.txt
```

## What's here

| File | What it is |
|---|---|
| `challenger.py` | One-vs-rest logistic (10 binary models on the 9 behavioral features), leave-one-out eval, coefficients. |
| `scorecard.py` | The scorecard math: WoE binning, Information Value, points (PDO), KS/AUC. |
| `scorecard_app.py` | **Interactive workbench** (Streamlit) — build/tune OvR scorecards live. |

## The three ways to use it

1. **Frozen read-only panels** (built by `scripts/build_*.py`, viewable by
   double-click, no Python needed):
   - `docs/champion-vs-challenger.html` — accuracy head-to-head vs the rules.
   - `docs/scorecard.html` — all 10 scorecards + the argmax combination.
2. **Interactive workbench** — the SAS/FICO Model-Builder pattern. Pick a target
   class, toggle features, adjust WoE bins / regularization / class-weighting,
   and IV / WoE / points / KS / AUC refit live; or switch to "combine" mode to
   see the 10 scorecards argmax into the OvR classifier (with a leave-one-out
   button for the honest accuracy):
   ```bash
   python -m streamlit run ml/scorecard_app.py
   ```
   Opens in your browser at http://localhost:8501 (stop with Ctrl+C). Use the
   `python -m streamlit` form rather than a bare `streamlit` — on Windows the
   `streamlit` console script often isn't on PATH even after a successful
   install. No virtualenv required.
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
