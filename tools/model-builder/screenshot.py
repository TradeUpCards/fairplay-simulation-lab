"""Dev-only visual harness: render the Dash app headless and save a screenshot.

Runs the app in a background thread (same process — no external server) and uses
Selenium + headless Chrome to capture the rendered page. For iterating on the UI.

    python tools/model-builder/screenshot.py [out.png]
"""
from __future__ import annotations

import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import importlib.util

spec = importlib.util.spec_from_file_location("mbapp", ROOT / "tools" / "model-builder" / "app.py")
mb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mb)

PORT = 8077
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else (ROOT / "tools" / "model-builder" / "_shot.png")


def _serve():
    mb.app.run(port=PORT, debug=False, use_reloader=False)


def main() -> int:
    threading.Thread(target=_serve, daemon=True).start()
    url = f"http://127.0.0.1:{PORT}/"
    for _ in range(60):
        try:
            urllib.request.urlopen(url, timeout=1)
            break
        except Exception:
            time.sleep(0.25)

    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    o = Options()
    o.add_argument("--headless=new")
    o.add_argument("--window-size=1500,950")
    o.add_argument("--force-device-scale-factor=1")
    tab = sys.argv[2] if len(sys.argv) > 2 else None  # optional tab label to click first
    d = webdriver.Chrome(options=o)
    try:
        d.get(url)
        WebDriverWait(d, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ag-row")))
        time.sleep(1.5)
        if tab:
            for el in d.find_elements(By.CSS_SELECTOR, ".tab, [role='tab']"):
                if tab.lower() in (el.text or "").lower():
                    el.click()
                    break
            time.sleep(1.8)  # let the tab's callbacks render
        time.sleep(1.2)
        d.save_screenshot(str(OUT))
        print(f"saved {OUT} ({OUT.stat().st_size} bytes)")
    finally:
        d.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
