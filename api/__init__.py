"""FairPlay live-scoring API — a thin FastAPI layer over the scoring engine.

The engine (`scoring/*.py`) is the canonical source of truth and is NOT ported
or reimplemented here; this package only wraps it so table health + recommendations
can be recomputed on the fly (a player stands up / sits down) and streamed to the
frontend over SSE. See `api/README.md`.
"""
