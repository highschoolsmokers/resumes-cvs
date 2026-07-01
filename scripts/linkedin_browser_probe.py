#!/usr/bin/env python3
"""Diagnostic: compare browser-driving strategies for the LinkedIn updater on
stability + bot-detection posture. Re-run when LinkedIn changes or a run starts
tripping challenges, to re-confirm the driver's launch strategy is still best.

No login and no evasion: one navigation per mode to the public LinkedIn entry
page, plus the fingerprint signals that predict detection (navigator.webdriver,
plugin count, headless UA) and an accessible-name locator resolution check.

    python scripts/linkedin_browser_probe.py

Findings that drove scripts/linkedin_apply.py's choice (2026-06-30):
  - bundled Chromium leaks (plugins:0, HeadlessChrome UA) — rejected.
  - real Chrome via channel="chrome" launched by Playwright → webdriver:true.
  - real Chrome + ignore_default_args=["--enable-automation"] +
    args=["--disable-blink-features=AutomationControlled"] → webdriver:false,
    plugins:5. Matches CDP-attach stealth with no subprocess dance. WINNER.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import time

from playwright.sync_api import sync_playwright

URL = "https://www.linkedin.com/"

MODES = [
    # label, channel, hardened
    ("bundled-chromium", None, False),
    ("real-chrome (plain)", "chrome", False),
    ("real-chrome (hardened)", "chrome", True),  # ← the driver's config
]


def probe(page) -> dict:
    out = {"final_url": page.url, "title": (page.title() or "")[:60]}
    for name, js in {
        "webdriver": "navigator.webdriver",
        "plugins": "navigator.plugins.length",
        "headless_ua": "/Headless/.test(navigator.userAgent)",
    }.items():
        try:
            out[name] = page.evaluate(js)
        except Exception as e:
            out[name] = f"ERR {repr(e)[:40]}"
    u = out["final_url"].lower()
    out["flagged"] = any(k in u for k in ("authwall", "checkpoint", "challenge"))
    try:
        out["signin_locator"] = page.get_by_role(
            "link", name="Sign in").first.is_visible(timeout=3000)
    except Exception:
        out["signin_locator"] = False
    return out


def run_mode(label: str, channel, hardened: bool, headless: bool) -> dict:
    tmp = tempfile.mkdtemp(prefix="pw-probe-")
    res = {"mode": label}
    kw = {"headless": headless, "channel": channel}
    if hardened:
        kw["ignore_default_args"] = ["--enable-automation"]
        kw["args"] = ["--disable-blink-features=AutomationControlled"]
    t0 = time.time()
    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(tmp, **kw)
            res["launch_ms"] = int((time.time() - t0) * 1000)
            page = ctx.new_page()
            page.goto(URL, wait_until="domcontentloaded", timeout=30000)
            res.update(probe(page))
            ctx.close()
        res["ok"] = True
    except Exception as e:
        res["ok"] = False
        res["error"] = repr(e)[:160]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return res


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--headed", action="store_true",
                    help="show the browser windows (default: headless)")
    args = ap.parse_args()
    results = [run_mode(l, c, h, headless=not args.headed) for l, c, h in MODES]
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
