#!/usr/bin/env python3
"""The ONE file to edit when LinkedIn's DOM shifts.

scripts/linkedin_apply.py never hard-codes a selector; it asks this module for a
logical target ("edit_intro", "headline_field", "save_button") and gets back an
ordered list of locator factories. Each factory takes a Playwright root (a Page
or a Locator, e.g. the open dialog) and returns a Locator. The driver tries them
in order and uses the first that becomes visible, so a single stale selector
degrades gracefully instead of breaking the run.

Rules that keep this stable:
  - Prefer role + accessible-name (aria-label / visible text). LinkedIn's CSS
    class names are auto-generated garbage; its aria-labels are localized but
    stable. NEVER select by class.
  - English UI is assumed. The names below are LinkedIn's English labels; on a
    non-English profile, translate them here (only here).
  - Confirm against the live logged-in DOM on the first `--dry-run`; the driver
    screenshots every step precisely so you can eyeball a drift and fix it here.
"""
from __future__ import annotations

from typing import Callable

# A factory: given a root (Page | Locator), return a Locator (pre-.first).
Factory = Callable[[object], object]

# Verified against the live logged-in profile 2026-06-30. LinkedIn's edit UI:
#   - the pencils are <a> links to overlay URLs (NOT buttons);
#   - clicking one opens a MODAL that carries no role="dialog" and no .modal
#     class (an a11y gap on their end), so it can't be scoped that way;
#   - while a modal is open there is exactly ONE contenteditable textbox on the
#     page (the field we want) and exactly ONE "Save" button;
#   - both Headline and About are div[role=textbox][contenteditable] — NOT
#     <textarea>/<input>, so they read via inner_text and write via keystrokes.
SELECTORS: dict[str, list[Factory]] = {
    # Pencil that opens the intro editor (Headline lives inside it).
    "edit_intro": [
        lambda r: r.locator('a[href*="/edit/intro/"]'),
        lambda r: r.get_by_role("link", name="Edit profile", exact=True),
    ],
    # Pencil that opens the About editor.
    "edit_about": [
        lambda r: r.locator('a[href*="/edit/forms/summary"]'),
        lambda r: r.get_by_role("link", name="Edit about", exact=True),
    ],
    # The editable field in whichever editor modal is currently open. Unique
    # while a modal is open; the driver only queries it after clicking a pencil.
    "editor_field": [
        lambda r: r.locator('[role="textbox"][contenteditable="true"]'),
        lambda r: r.locator('div[contenteditable="true"]'),
    ],
    # The modal's Save button (there is only one Save on the page when open).
    "save_button": [
        lambda r: r.get_by_role("button", name="Save", exact=True),
        lambda r: r.locator('button:has-text("Save")'),
    ],
}
