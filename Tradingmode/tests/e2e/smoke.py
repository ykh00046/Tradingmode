"""P0-2 frontend smoke test (Playwright).

Loads the app in demo mode and verifies every tab renders with zero
uncaught JS errors, plus four core interactions. Self-contained — spawns
its own static server on a dedicated port, so it never collides with a
dev server already on :5500.

Run:      python tests/e2e/smoke.py      (from the Tradingmode/ dir)
Prereq:   pip install -r ../backend/requirements-dev.txt
          playwright install chromium

Exit code: 0 = all checks pass, 1 = any failure.
See docs/02-design/features/improvement-plan.design.md  §4 (P0-2).
"""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# Korean labels are printed — keep stdout UTF-8 even on a cp949 console.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from playwright.sync_api import sync_playwright

FRONTEND_DIR = Path(__file__).resolve().parents[2]   # .../Tradingmode (frontend)
PORT = 5599
BASE = f"http://localhost:{PORT}"

# (tab label, page root selector that must appear after clicking it)
TABS = [
    ("차트 분석", ".chart-page"),
    ("매매 신호", ".signals-page"),
    ("백테스팅", ".backtest-page"),
    ("포트폴리오", ".portfolio-page"),
    ("Strategy Coach", ".strategy-coach-page"),
]

_results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    _results.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  {mark}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


def _wait_server(url: str, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def run() -> int:
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT)],
        cwd=str(FRONTEND_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        if not _wait_server(f"{BASE}/index.html"):
            check("static server starts", False, "no response on :%d" % PORT)
            return 1

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 1000})
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))

            page.goto(f"{BASE}/?demo=1")
            page.wait_for_load_state("networkidle")
            page.wait_for_selector(".chart-pane", timeout=15000)
            page.wait_for_timeout(1500)

            # --- every tab renders with no new JS error ---
            for label, root in TABS:
                before = len(errors)
                page.get_by_text(label, exact=True).first.click()
                try:
                    page.wait_for_selector(root, timeout=6000)
                    rendered = True
                except Exception:
                    rendered = False
                page.wait_for_timeout(400)
                no_new_err = len(errors) == before
                check(
                    f"tab '{label}' renders ({root})",
                    rendered and no_new_err,
                    "root not rendered" if not rendered else "JS error during render",
                )

            # --- core interactions (chart tab) ---
            page.get_by_text("차트 분석", exact=True).first.click()
            page.wait_for_selector(".chart-pane", timeout=6000)
            page.wait_for_timeout(500)

            before = len(errors)
            page.locator(".wl-row").nth(1).click()              # switch symbol
            page.wait_for_timeout(700)
            check("interaction: watchlist symbol switch", len(errors) == before)

            before = len(errors)
            page.locator(".ind-toggle").first.click()           # toggle indicator
            page.wait_for_timeout(400)
            check("interaction: indicator toggle", len(errors) == before)

            before = len(errors)
            page.get_by_text("주", exact=True).first.click()    # interval switch
            page.wait_for_timeout(700)
            check("interaction: interval switch (week)", len(errors) == before)

            before = len(errors)
            page.get_by_text("매매 신호", exact=True).first.click()
            page.wait_for_selector(".feed-row", timeout=6000)
            page.locator(".feed-row").first.click()             # expand a signal
            page.wait_for_timeout(700)
            check("interaction: signal feed expand", len(errors) == before)

            browser.close()

        check(
            "zero uncaught JS errors overall",
            len(errors) == 0,
            f"{len(errors)} error(s): {errors[:3]}",
        )
    finally:
        server.terminate()

    passed = sum(1 for _, ok, _ in _results if ok)
    print(f"\n{passed}/{len(_results)} checks passed")
    return 0 if passed == len(_results) else 1


if __name__ == "__main__":
    sys.exit(run())
