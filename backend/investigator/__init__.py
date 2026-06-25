"""AI Investigator (P4) — the evidence-packet → safe-summary LLM seam."""
from .investigator import MODEL, investigate

__all__ = ["investigate", "MODEL"]
