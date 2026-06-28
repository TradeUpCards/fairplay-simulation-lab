"""Put the ``backend`` dir on sys.path so ``import coach`` resolves (mirrors how the
other backend packages are imported), regardless of pytest's rootdir."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]  # backend/coach/tests -> backend
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
