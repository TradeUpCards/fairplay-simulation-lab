"""Put the ``backend`` dir on sys.path so ``import play`` / ``import coach`` resolve
(``play.session`` adds the sibling ``playsim`` package itself)."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]  # backend/play/tests -> backend
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
