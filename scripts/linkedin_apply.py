#!/usr/bin/env python3
"""Push the résumé-derived LinkedIn profile onto the live profile, via real Chrome.

Syncs three things from linkedin-profile.json (scripts/linkedin_export.py --json):
  - Headline   (intro editor)
  - About      (about editor)
  - Experience (--experience): each position's DESCRIPTION, matched to a résumé
    entry by company. Titles/dates are left untouched; The Rumpus and the flat
    "Earlier experience" list are skipped. Edit EXPERIENCE_TARGETS to change the
    set of positions synced.
The driver never re-parses the résumé, so the LinkedIn copy can't drift from it.

Design (why it does not break easily):
  - Real Chrome via Playwright channel="chrome" + anti-automation flags. The
    probe (scripts/linkedin_browser_probe.py) showed this is the only launch
    config that hides navigator.webdriver AND keeps a real fingerprint. Falls
    back to bundled Chromium with --browser chromium.
  - Headed + a persistent, DEDICATED profile dir (.linkedin-chrome-profile/):
    log in once, reused forever; you watch every step. The dir holds session
    cookies, so it is gitignored — treat it like a credential. A crashed run's
    stale profile lock is self-healed on the next launch.
  - No CSS-class selectors. Every target comes from linkedin_selectors.py with
    ordered fallbacks (first visible wins) — that file is the ONE place to edit
    when LinkedIn's DOM shifts. Both editable fields are contenteditable divs,
    so they read via inner_text and write via real keystrokes.
  - Safe by default: DRY-RUN unless --commit; even with --commit it asks before
    each Save unless --yes; closing an editor navigates away (can never save).
    Idempotent: a field already matching is skipped. After each save it VERIFIES
    by re-reading the field. Every step → linkedin-runs/<ts>/ (screenshots +
    run.json).

ToS note: automating profile edits crosses LinkedIn's terms. This is built for
one-time, human-supervised, self-owned edits; the risk is yours to accept.

Usage:
    # dry run (default): fills Headline + About, screenshots, saves NOTHING
    .venv/bin/python scripts/linkedin_apply.py

    # commit Headline + About, confirming before each save
    .venv/bin/python scripts/linkedin_apply.py --commit

    # experience descriptions only, dry run
    .venv/bin/python scripts/linkedin_apply.py --experience --fields ""

    # everything, no per-save prompt
    .venv/bin/python scripts/linkedin_apply.py --experience --commit --yes
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import (
    sync_playwright, Locator, Page,
    Error as PWError, TimeoutError as PWTimeout,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import linkedin_selectors as sel  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
DEFAULT_JSON = REPO / "linkedin-profile.json"
DEFAULT_PROFILE_DIR = REPO / ".linkedin-chrome-profile"
RUNS_DIR = REPO / "linkedin-runs"

# Phase A fields: logical name → the pencil selector that opens its editor.
# The editable control is always "editor_field" (the single open-modal textbox).
FIELDS = {
    "headline": {"open": "edit_intro"},
    "about": {"open": "edit_about"},
}


# -----------------------------------------------------------------------------
# selector resolution
# -----------------------------------------------------------------------------

def resolve(root, key: str, timeout: int = 6000) -> Locator:
    """Return the first visible Locator among linkedin_selectors[key]'s factories."""
    factories = sel.SELECTORS[key]
    per = max(1500, timeout // len(factories))
    last_err: Exception | None = None
    for make in factories:
        loc = make(root).first
        try:
            loc.wait_for(state="visible", timeout=per)
            return loc
        except PWTimeout as e:
            last_err = e
    raise LookupError(f"no visible element for {key!r} (tried {len(factories)} selectors)") from last_err


# -----------------------------------------------------------------------------
# helpers
# -----------------------------------------------------------------------------

def _norm(s: str) -> str:
    """Whitespace-insensitive compare key for idempotency."""
    return re.sub(r"\s+", " ", (s or "")).strip()


def _read_value(field: Locator) -> str:
    """Both fields are contenteditable divs → inner_text (fall back to value)."""
    try:
        return field.inner_text()
    except Exception:
        try:
            return field.input_value()
        except Exception:
            return ""


def _write_value(page: Page, field: Locator, text: str) -> None:
    """Replace a contenteditable field's content with real keystrokes so
    LinkedIn's editor registers the change (a raw DOM set would not persist).
    Multi-line text (e.g. bulleted descriptions) is typed line by line with
    real Enter presses so the line breaks survive."""
    field.click()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.press("Delete")
    for i, line in enumerate(text.split("\n")):
        if i:
            page.keyboard.press("Enter")
        if line:
            page.keyboard.type(line, delay=4)


def close_editor(page: Page, profile_url: str) -> None:
    """Abandon whatever editor is open by navigating back to the profile. This
    can NEVER save — LinkedIn only persists on an explicit Save click — so it is
    the safe, selector-free way to close a dirty modal (no Discard dance)."""
    page.goto(profile_url, wait_until="domcontentloaded")


def _clean_profile_lock(user_data_dir: Path) -> None:
    """Release a DEDICATED profile a prior crashed run left locked. Safe: it only
    targets processes launched against THIS dir and this dir's own lock files;
    it never touches your everyday Chrome (a different profile)."""
    subprocess.run(["pkill", "-f", f"--user-data-dir={user_data_dir}"], check=False)
    time.sleep(1)
    for lock in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        try:
            (user_data_dir / lock).unlink()
        except (FileNotFoundError, OSError):
            pass


def launch_browser(p, user_data_dir: Path, browser: str, headless: bool):
    """Hardened real-Chrome (or bundled-Chromium) persistent context. Retries
    once after self-healing a stale profile lock — the one failure that recurs
    when a previous run crashed mid-flight."""
    kwargs = dict(
        headless=headless,
        ignore_default_args=["--enable-automation"],  # → navigator.webdriver=false
        args=["--disable-blink-features=AutomationControlled"],
        viewport={"width": 1280, "height": 1000},
    )
    if browser == "chrome":
        kwargs["channel"] = "chrome"  # real Chrome fingerprint (see probe)
    try:
        return p.chromium.launch_persistent_context(str(user_data_dir), **kwargs)
    except PWError as e:
        msg = str(e).lower()
        if "in use" in msg or "existing browser session" in msg:
            print("  profile busy/stale; clearing its lock and retrying once...")
            _clean_profile_lock(user_data_dir)
            return p.chromium.launch_persistent_context(str(user_data_dir), **kwargs)
        raise


def _logged_in(page: Page) -> bool:
    """Logged-in iff LinkedIn's auth cookie (li_at) is present. Read from the
    browser context, so it works no matter what page you're on — the login wait
    NEVER navigates or reloads the page."""
    try:
        return any(c.get("name") == "li_at" and c.get("value")
                   for c in page.context.cookies())
    except Exception:
        return False


def ensure_ready(page: Page, profile_url: str, login_timeout_s: int) -> None:
    """Wait (passively) for a manual login, then land on the owner's profile with
    edit affordances visible. No credentials touched; no page reloads while you
    are logging in."""
    if not _logged_in(page):
        # One navigation to a clean login form, then hands off entirely.
        try:
            page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        except Exception:
            pass
        print("\n  → Log in to LinkedIn in the Chrome window that opened.")
        print("    Take your time. This is just watching for your login; it will")
        print("    NOT touch or reload the page while you type.\n")
        deadline = datetime.now().timestamp() + login_timeout_s
        while datetime.now().timestamp() < deadline:
            if _logged_in(page):
                break
            page.wait_for_timeout(2000)  # sleep only; no navigation
        else:
            raise TimeoutError("timed out waiting for LinkedIn login (li_at cookie)")

    # Logged in: now (and only now) go to the profile and confirm edit controls.
    page.goto(profile_url, wait_until="domcontentloaded")
    try:
        resolve(page, "edit_intro", timeout=15000)
    except LookupError as e:
        raise TimeoutError(f"logged in, but profile edit controls not found: {e}")


# -----------------------------------------------------------------------------
# per-field application
# -----------------------------------------------------------------------------

def _open_field(page: Page, cfg: dict) -> Locator:
    """Click the pencil and return the editor's single contenteditable field."""
    resolve(page, cfg["open"]).click()
    field = resolve(page, "editor_field", timeout=12000)
    field.wait_for(state="visible", timeout=8000)
    return field


def apply_field(page: Page, name: str, desired: str, commit: bool, confirm: bool,
                run_dir: Path, profile_url: str) -> dict:
    cfg = FIELDS[name]
    result = {"field": name, "action": None, "detail": ""}

    field = _open_field(page, cfg)
    current = _read_value(field)

    if _norm(current) == _norm(desired):
        result["action"] = "skip"
        result["detail"] = "already matches résumé"
        close_editor(page, profile_url)
        return result

    _write_value(page, field, desired)
    shot = run_dir / f"{name}-filled.png"
    page.screenshot(path=str(shot))
    result["screenshot"] = str(shot.relative_to(REPO))

    if not commit:
        result["action"] = "dry-run"
        result["detail"] = f"would change ({len(current)}→{len(desired)} chars)"
        close_editor(page, profile_url)  # navigating away discards; nothing saved
        return result

    if confirm and not _ask(f"Save new {name}? ({len(current)}→{len(desired)} chars)"):
        result["action"] = "declined"
        close_editor(page, profile_url)
        return result

    resolve(page, "save_button").click()
    try:
        field.wait_for(state="detached", timeout=10000)  # modal closed = saved
    except PWTimeout:
        result["action"] = "save-uncertain"
        result["detail"] = "editor did not close after Save"
        page.screenshot(path=str(run_dir / f"{name}-after-save.png"))
        close_editor(page, profile_url)
        return result

    # Verify: reopen and re-read the field in the editor (not the styled render).
    saved = _read_value(_open_field(page, cfg))
    close_editor(page, profile_url)
    if _norm(saved) == _norm(desired):
        result["action"] = "saved"
        result["detail"] = "verified"
    else:
        result["action"] = "saved-mismatch"
        result["detail"] = f"editor shows {len(saved)} chars, expected {len(desired)}"
    return result


# Experience: sync each position's DESCRIPTION to the résumé. Positions are
# matched to the profile JSON by company. Titles/dates are left untouched (per
# the user's choice); The Rumpus and the flat "Earlier experience" list are
# excluded (the latter has no per-role description in the master).
#   (json company substring, company keyword in the LinkedIn edit pencil)
EXPERIENCE_TARGETS = [
    ("Independent", "Independent"),
    ("Fabulosa", "Fabulosa"),
    ("San Francisco State", "San Francisco State"),
    ("Slack", "Slack"),
    ("Appthority", "Appthority"),
    ("GoPro", "GoPro"),
]


def _open_position(page: Page, keyword: str, details_url: str) -> Locator:
    """From the experience detail page, click the Edit pencil for the position at
    `keyword` company and return the modal's Description contenteditable."""
    page.goto(details_url, wait_until="domcontentloaded")
    for _ in range(4):
        page.mouse.wheel(0, 500)
        page.wait_for_timeout(250)
    pencil = page.locator(
        f'a[aria-label^="Edit"][aria-label*="{keyword}" i]').first
    pencil.wait_for(state="visible", timeout=8000)
    pencil.click()
    field = resolve(page, "editor_field", timeout=12000)
    field.wait_for(state="visible", timeout=8000)
    return field


def apply_experience(page: Page, experience: list[dict], commit: bool,
                     confirm: bool, run_dir: Path, profile_url: str) -> list[dict]:
    details_url = profile_url + "details/experience/"
    by_company = {e["company"]: e for e in experience}
    results: list[dict] = []
    for json_sub, keyword in EXPERIENCE_TARGETS:
        entry = next((e for c, e in by_company.items() if json_sub.lower() in c.lower()), None)
        r = {"field": f"exp:{keyword}", "action": None, "detail": ""}
        if not entry:
            r["action"] = "error"; r["detail"] = f"no JSON entry for {json_sub!r}"
            results.append(r); continue
        desired = entry["description"]
        try:
            field = _open_position(page, keyword, details_url)
            current = _read_value(field)
            if _norm(current) == _norm(desired):
                r["action"] = "skip"; r["detail"] = "already matches résumé"
                results.append(r); continue
            _write_value(page, field, desired)
            shot = run_dir / f"exp-{keyword.split()[0]}-filled.png"
            page.screenshot(path=str(shot))
            r["screenshot"] = str(shot.relative_to(REPO))
            if not commit:
                r["action"] = "dry-run"
                r["detail"] = f"would change ({len(current)}→{len(desired)} chars)"
                results.append(r); continue
            if confirm and not _ask(f"Save new description for {keyword}? "
                                    f"({len(current)}→{len(desired)} chars)"):
                r["action"] = "declined"; results.append(r); continue
            resolve(page, "save_button").click()
            try:
                field.wait_for(state="detached", timeout=10000)
            except PWTimeout:
                r["action"] = "save-uncertain"; r["detail"] = "modal did not close"
                page.screenshot(path=str(run_dir / f"exp-{keyword.split()[0]}-after.png"))
                results.append(r); continue
            saved = _read_value(_open_position(page, keyword, details_url))
            r["action"] = "saved" if _norm(saved) == _norm(desired) else "saved-mismatch"
            r["detail"] = "verified" if r["action"] == "saved" else \
                f"editor shows {len(saved)} chars, expected {len(desired)}"
        except (LookupError, PWTimeout) as e:
            r["action"] = "error"; r["detail"] = repr(e)[:150]
            try:
                page.screenshot(path=str(run_dir / f"exp-{keyword.split()[0]}-error.png"))
            except Exception:
                pass
        results.append(r)
    page.goto(profile_url, wait_until="domcontentloaded")  # leave clean
    return results


def _ask(question: str) -> bool:
    if not sys.stdin.isatty():
        raise SystemExit("commit needs a TTY to confirm each save (or pass --yes)")
    return input(f"  {question} [y/N] ").strip().lower() in ("y", "yes")


# -----------------------------------------------------------------------------
# main
# -----------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", type=Path, default=DEFAULT_JSON,
                    help="linkedin-profile.json (from linkedin_export.py --json)")
    ap.add_argument("--fields", default="headline,about",
                    help="comma list of fields to apply (default: headline,about); "
                         "pass '' to skip them (e.g. with --experience only)")
    ap.add_argument("--experience", action="store_true",
                    help="sync each position's DESCRIPTION to the résumé "
                         "(titles/dates untouched; skips The Rumpus)")
    ap.add_argument("--commit", action="store_true",
                    help="actually save (default: dry-run, saves nothing)")
    ap.add_argument("--yes", action="store_true",
                    help="with --commit, skip the per-save confirmation prompt")
    ap.add_argument("--headless", action="store_true",
                    help="hide the browser (NOT recommended; you can't log in or watch)")
    ap.add_argument("--browser", choices=("chrome", "chromium"), default="chrome",
                    help="chrome = real Chrome (best fingerprint, default); "
                         "chromium = bundled (fallback if real Chrome won't launch)")
    ap.add_argument("--user-data-dir", type=Path, default=DEFAULT_PROFILE_DIR,
                    help="persistent Chrome profile dir (holds your session)")
    ap.add_argument("--profile-url", default=None,
                    help="override the profile URL (default: from the JSON)")
    ap.add_argument("--login-timeout", type=int, default=240,
                    help="seconds to wait for a manual login (default: 240)")
    args = ap.parse_args()

    if not args.profile.exists():
        sys.exit(f"profile JSON not found: {args.profile}\n"
                 f"generate it: .venv/bin/python scripts/linkedin_export.py "
                 f"--target education --json {args.profile}")
    data = json.loads(args.profile.read_text(encoding="utf-8"))

    want = [f.strip() for f in args.fields.split(",") if f.strip()]
    unknown = [f for f in want if f not in FIELDS]
    if unknown:
        sys.exit(f"unknown field(s): {unknown}; known: {sorted(FIELDS)}")

    profile_url = args.profile_url or data.get("links", {}).get("linkedin", "")
    if not profile_url:
        sys.exit("no profile URL in JSON and none passed via --profile-url")
    profile_url = re.sub(r"^https?://(www\.)?", "https://www.", profile_url).rstrip("/") + "/"

    run_dir = RUNS_DIR / datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    if not want and not args.experience:
        sys.exit("nothing to do: --fields is empty and --experience not set")

    mode = "COMMIT" if args.commit else "DRY-RUN"
    print(f"[{mode}] fields={want} experience={args.experience}  profile={profile_url}")
    print(f"        chrome profile: {args.user_data_dir}")
    print(f"        run artifacts:  {run_dir.relative_to(REPO)}/")

    results: list[dict] = []
    with sync_playwright() as p:
        ctx = launch_browser(p, args.user_data_dir, args.browser, args.headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(profile_url, wait_until="domcontentloaded")
            try:
                ensure_ready(page, profile_url, args.login_timeout)
            except TimeoutError as e:
                page.screenshot(path=str(run_dir / "login-timeout.png"))
                print(f"\nnot ready: {e}")
                print("Log in within the window next time, or raise --login-timeout.")
                return 2  # finally writes run.json + closes the context
            for name in want:
                try:
                    r = apply_field(page, name, data[name], args.commit,
                                    confirm=not args.yes, run_dir=run_dir,
                                    profile_url=profile_url)
                except (LookupError, PWTimeout) as e:
                    r = {"field": name, "action": "error", "detail": repr(e)[:160]}
                    try:
                        page.screenshot(path=str(run_dir / f"{name}-error.png"))
                    except Exception:
                        pass
                    close_editor(page, profile_url)
                print(f"  - {r['field']:<9} {r['action']:<15} {r.get('detail','')}")
                results.append(r)

            if args.experience:
                exp_results = apply_experience(
                    page, data.get("experience", []), args.commit,
                    confirm=not args.yes, run_dir=run_dir, profile_url=profile_url)
                for r in exp_results:
                    print(f"  - {r['field']:<16} {r['action']:<15} {r.get('detail','')}")
                results.extend(exp_results)
        finally:
            (run_dir / "run.json").write_text(
                json.dumps({"mode": mode, "profile_url": profile_url,
                            "results": results}, indent=2), encoding="utf-8")
            ctx.close()

    bad = [r for r in results if r["action"] in ("error", "saved-mismatch", "save-uncertain")]
    print(f"\n{mode} complete. {len(results)} item(s); {len(bad)} need attention.")
    print(f"Screenshots + run.json in {run_dir.relative_to(REPO)}/")
    if not args.commit:
        print("This was a DRY RUN. Review the screenshots, then re-run with --commit.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
