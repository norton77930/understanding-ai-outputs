# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "playwright>=1.50,<2",
# ]
# ///
"""Render one HTML explainer page in a headless browser and check it.

Usage:
    uv run render_check.py FILE [--out DIR]

Opens FILE through file:// in headless Chromium and prints one JSON object on
stdout (UTF-8). Screenshots go to DIR (default: <folder of FILE>/screenshots).

Steps:
- Load the page at 390x844 and 1280x800, each in the light and the dark color
  scheme, and save a full-page PNG of each (4 screenshots).
- Collect console messages of type "error" and uncaught page errors from
  every load (duplicates removed, first-seen order).
- At 390 px (light), measure horizontal overflow on the root element:
  overflow when scrollWidth > clientWidth + 1.
- In the 390 px light page, do one interaction: click the first visible
  <button>; else move the first visible <input type=range> to its max; else
  open the first <details>. Then save one more screenshot (5 in total).

Output shape:
    {"file": str, "browser": str, "console_errors": [str], "page_errors": [str],
     "overflow_390": {"scroll_width": int, "client_width": int,
                      "overflow": bool},
     "interaction": {"kind": "button"|"range"|"details", "selector": str}|null,
     "screenshots": [str], "pass": bool}
On exit 2 the object is {"file", "error", "hint", "pass": false} instead.

Exit code: 0 = no console or page errors and no overflow; 1 = at least one
of those; 2 = environment or input problem (missing file, Playwright not
importable, no usable browser), with a hint.

Browser policy: this script never downloads a browser. It tries, in order:
1. "bundled": Chromium that Playwright already installed under
   PLAYWRIGHT_BROWSERS_PATH (default: %LOCALAPPDATA%\\ms-playwright on
   Windows, ~/.cache/ms-playwright on Linux, ~/Library/Caches/ms-playwright on
   macOS). Playwright's own default first, then any installed chromium-*
   build by its executable path.
2. "chrome": an installed Google Chrome (channel="chrome").
3. "msedge": an installed Microsoft Edge (channel="msedge").
The environment variable RENDER_CHECK_BROWSERS (comma list of bundled,
chrome, msedge) limits or reorders the candidates.
"""

import argparse
import json
import os
import sys
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_ENV = 0, 1, 2

VIEWS = [  # (name, width, height, color scheme)
    ("390x844-light", 390, 844, "light"),
    ("390x844-dark", 390, 844, "dark"),
    ("1280x800-light", 1280, 800, "light"),
    ("1280x800-dark", 1280, 800, "dark"),
]
DEFAULT_CANDIDATES = ("bundled", "chrome", "msedge")
SETTLE_MS = 300

INSTALL_HINT = (
    "No usable browser found. This check does not download one. To install "
    "Playwright's Chromium (about 150-200 MB download), ask the user first, "
    "then run: uv run --with playwright playwright install chromium. Set "
    "PLAYWRIGHT_BROWSERS_PATH to choose where it goes (for example a folder "
    "on another drive); use the same value when you run this check. Or "
    "install Google Chrome or Microsoft Edge.")
IMPORT_HINT = (
    "Python Playwright is not importable. Run this script with "
    "`uv run render_check.py FILE` so uv installs the playwright package. "
    "No browser is downloaded by that step; if none is found, run "
    "`playwright install chromium` (about 150-200 MB) after the user agrees.")

# Executable paths inside a Playwright browser folder, per platform.
EXE_PATTERNS = [
    "chrome-win64/chrome.exe", "chrome-win/chrome.exe",
    "chrome-linux64/chrome", "chrome-linux/chrome",
    "chrome-mac*/Chromium.app/Contents/MacOS/Chromium",
    "chrome-mac*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
    "chrome-headless-shell-*/chrome-headless-shell.exe",
    "chrome-headless-shell-*/chrome-headless-shell",
]

FIND_CONTROL_JS = """
() => {
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const pick = (sel, kind, needVisible) => {
    const all = Array.from(document.querySelectorAll(sel));
    for (const [i, el] of all.entries()) {
      if (!needVisible || visible(el)) {
        el.setAttribute('data-render-check', kind);
        const selector = el.id ? sel + '#' + CSS.escape(el.id) : sel + ' >> nth=' + i;
        return {kind, selector};
      }
    }
    return null;
  };
  return pick('button', 'button', true)
    || pick('input[type=range]', 'range', true)
    || pick('details', 'details', false);
}
"""

RANGE_TO_MAX_JS = """
(el) => {
  el.value = el.max === '' ? '100' : el.max;
  el.dispatchEvent(new Event('input', {bubbles: true}));
  el.dispatchEvent(new Event('change', {bubbles: true}));
}
"""

OVERFLOW_JS = """
() => {
  const d = document.documentElement;
  return {scroll_width: d.scrollWidth, client_width: d.clientWidth};
}
"""


def emit(obj, code):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    return code


def env_error(file, error, hint):
    return emit({"file": file, "error": error, "hint": hint, "pass": False}, EXIT_ENV)


def browsers_root():
    env = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if env and env != "0":
        return Path(env)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "ms-playwright"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "ms-playwright"


def revision(path):
    tail = path.name.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else -1


def bundled_executables(root):
    """Installed Playwright Chromium executables, full builds first, newest first."""
    if not root.is_dir():
        return []
    dirs = [d for d in root.glob("chromium*-*") if (d / "INSTALLATION_COMPLETE").exists()]
    full = sorted((d for d in dirs if d.name.startswith("chromium-")), key=revision, reverse=True)
    shell = sorted((d for d in dirs if d not in full), key=revision, reverse=True)
    exes = []
    for d in full + shell:
        for pattern in EXE_PATTERNS:
            exes.extend(p for p in d.glob(pattern) if p.is_file())
    return exes


def candidate_list():
    raw = os.environ.get("RENDER_CHECK_BROWSERS")
    names = [n.strip() for n in raw.split(",")] if raw else list(DEFAULT_CANDIDATES)
    out = []
    for name in names:
        if name == "bundled":
            exes = bundled_executables(browsers_root())
            if exes:
                out.append(("bundled", {}, "playwright-chromium (default)"))
                out.extend(("bundled", {"executable_path": str(e)},
                            f"playwright-chromium ({e.parent.parent.name})") for e in exes)
        elif name in ("chrome", "msedge"):
            out.append((name, {"channel": name}, name))
    return out


def launch(pw, candidates):
    errors = []
    for _, kwargs, label in candidates:
        try:
            browser = pw.chromium.launch(headless=True, **kwargs)
            return browser, f"{label} {browser.version}", errors
        except Exception as exc:  # noqa: BLE001 - try the next candidate
            errors.append(f"{label}: {str(exc).splitlines()[0]}")
    return None, None, errors


def add_unique(items, text):
    if text not in items:
        items.append(text)


def render(pw, candidates, url, out_dir, result):
    browser, label, errors = launch(pw, candidates)
    if browser is None:
        return None, errors
    result["browser"] = label
    console, page_errors, shots = result["console_errors"], result["page_errors"], result["screenshots"]
    out_dir.mkdir(parents=True, exist_ok=True)
    interaction_shot = None
    try:
        for name, width, height, scheme in VIEWS:
            context = browser.new_context(viewport={"width": width, "height": height},
                                          color_scheme=scheme)
            page = context.new_page()
            page.on("console", lambda m: m.type == "error" and add_unique(console, m.text))
            page.on("pageerror", lambda e: add_unique(page_errors, str(e)))
            page.goto(url, wait_until="load")
            page.wait_for_timeout(SETTLE_MS)
            shot = out_dir / f"{name}.png"
            page.screenshot(path=str(shot), full_page=True)
            shots.append(str(shot))
            if name == "390x844-light":
                m = page.evaluate(OVERFLOW_JS)
                m["overflow"] = m["scroll_width"] > m["client_width"] + 1
                result["overflow_390"] = m
                interaction = page.evaluate(FIND_CONTROL_JS)
                if interaction:
                    el = page.locator(f"[data-render-check={interaction['kind']}]").first
                    if interaction["kind"] == "button":
                        el.click(timeout=5000)
                    elif interaction["kind"] == "range":
                        el.evaluate(RANGE_TO_MAX_JS)
                    else:
                        el.evaluate("(d) => { d.open = true; }")
                    page.wait_for_timeout(SETTLE_MS)
                    after = out_dir / f"{name}-interaction.png"
                    page.screenshot(path=str(after), full_page=True)
                    result["interaction"] = interaction
                    interaction_shot = str(after)
            context.close()
        if interaction_shot:
            shots.append(interaction_shot)
    finally:
        browser.close()
    return label, errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("file", help="HTML file to render")
    parser.add_argument("--out", help="screenshot folder (default: <file dir>/screenshots)")
    args = parser.parse_args(argv)

    path = Path(args.file).resolve()
    if not path.is_file():
        return env_error(str(path), f"file not found: {path}",
                         "Pass the path of an existing .html file.")
    out_dir = Path(args.out).resolve() if args.out else path.parent / "screenshots"

    candidates = candidate_list()
    if not candidates:
        return env_error(str(path), "no browser candidate available", INSTALL_HINT)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return env_error(str(path), "playwright is not installed", IMPORT_HINT)

    result = {"file": str(path), "browser": None, "console_errors": [],
              "page_errors": [], "overflow_390": None, "interaction": None,
              "screenshots": [], "pass": False}
    try:
        with sync_playwright() as pw:
            label, errors = render(pw, candidates, path.as_uri(), out_dir, result)
    except Exception as exc:  # noqa: BLE001 - report as JSON, not a traceback
        return env_error(str(path), f"render failed: {str(exc).splitlines()[0]}",
                         "Check that the page loads in a browser; rerun the check.")
    if label is None:
        return env_error(str(path), "no browser could be launched: " + "; ".join(errors),
                         INSTALL_HINT)

    failed = bool(result["console_errors"] or result["page_errors"]
                  or result["overflow_390"]["overflow"])
    result["pass"] = not failed
    return emit(result, EXIT_FAIL if failed else EXIT_PASS)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
