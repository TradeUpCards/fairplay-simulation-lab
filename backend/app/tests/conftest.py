"""Put the ``backend`` dir on sys.path so ``import app`` / ``import play`` resolve."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]  # backend/app/tests -> backend
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
