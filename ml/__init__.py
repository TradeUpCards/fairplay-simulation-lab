"""ML challengers for the scoring engine (P4 eval-lab territory).

These are the interpretable **challenger** models raced against the
deterministic **champions** in `scoring/`. Unlike the stdlib-only scoring core,
this package depends on scikit-learn / pandas / numpy and is NOT on the demo's
critical path — a challenger is promoted only if it beats the champion on
labeled accuracy AND stays interpretable. The decision layer (router) never has
a challenger.
"""
