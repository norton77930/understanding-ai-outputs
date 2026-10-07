# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "playwright==1.62.*",
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
- In the 390 px light page, do one interaction on the first usable control
  (visible, not disabled, pointer-events not none): click a <button>; else
  move an <input type=range> to its max; else click an
  <input type=checkbox>; else open the first <details>. Then save one more
  screenshot (5 in total). If the interaction fails (for example the click
  times out because another element covers the button), "interaction_error"
  says why and there is no fifth screenshot.

Output shape:
    {"file": str, "browser": str, "load_error": str|null,
     "console_errors": [str], "page_errors": [str],
     "overflow_390": {"scroll_width": int, "client_width": int,
                      "overflow": bool}|null,
     "interaction": {"kind": "button"|"range"|"checkbox"|"details",
                     "selector": str}|null,
     "interaction_error": str|null,
     "screenshots": [str], "pass": bool}
"load_error" is set when a load does not finish in 30 s (for example a
resource that never answers); the remaining views are skipped.
On exit 2 the object is {"file", "error", "hint", "pass": false} instead.

Exit code: 0 = the page loaded, no console or page errors, no overflow and
no interaction error; 1 = a page problem (any of those); 2 = environment or
input problem (missing file, Playwright not importable, no usable browser,
the browser stopped unexpectedly), with a hint.

Browser policy: this script never downloads a browser. It tries, in order:
1. "bundled": Chromium that Playwright already installed under
   PLAYWRIGHT_BROWSERS_PATH (default: %LOCALAPPDATA%\\ms-playwright on
   Windows, ~/.cache/ms-playwright on Linux, ~/Library/Caches/ms-playwright on
   macOS; "0" means the .local-browsers folder inside the playwright
   package). Playwright's own default first (Playwright 1.62 uses Chromium
   build 1234), then any installed chromium-* build by its executable path.
2. "chrome": an installed Google Chrome (channel="chrome").
3. "msedge": an installed Microsoft Edge (channel="msedge").
The environment variable RENDER_CHECK_BROWSERS (comma list of bundled,
chrome, msedge) limits or reorders the candidates.
"""

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

EXIT_PASS, EXIT_FAIL, EXIT_ENV = 0, 1, 2

VIEWS = [  # (name, width, height, color scheme, measure overflow and interact)
    ("390x844-light", 390, 844, "light", True),
    ("390x844-dark", 390, 844, "dark", False),
    ("1280x800-light", 1280, 800, "light", False),
    ("1280x800-dark", 1280, 800, "dark", False),
]
DEFAULT_CANDIDATES = ("bundled", "chrome", "msedge")
SETTLE_MS = 300
LOAD_TIMEOUT_MS = 30_000
CLICK_TIMEOUT_MS = 5_000

# Same Playwright pin and install wording as diagram-explainer's
# render_diagram.py (Playwright 1.62 uses Chromium build 1234).
INSTALL_HINT = (
    "No browser could start. This check does not download one. Install "
    "Google Chrome or Microsoft Edge, or install Playwright's Chromium (about "
    "300 MB download, about 700 MB on disk) with: uv run --with "
    "playwright==1.62.* playwright install chromium. Set "
    "PLAYWRIGHT_BROWSERS_PATH first to choose the install folder (default: "
    "%LOCALAPPDATA%\\ms-playwright on Windows, ~/.cache/ms-playwright on "
    "Linux, ~/Library/Caches/ms-playwright on macOS) and keep it set when you "
    "run this check. Ask the user before this download.")
IMPORT_HINT = (
    "Python Playwright is not importable. Run this script with "
    "`uv run render_check.py FILE` so uv installs the playwright package. "
    "No browser is downloaded by that step. Install uv from "
    "https://docs.astral.sh/uv/.")

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
  const usable = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden'
      && s.display !== 'none' && s.pointerEvents !== 'none' && !el.matches(':disabled');
  };
  const pick = (sel, kind, needUsable) => {
    const all = Array.from(document.querySelectorAll(sel));
    for (const [i, el] of all.entries()) {
      if (!needUsable || usable(el)) {
        el.setAttribute('data-render-check', kind);
        const selector = el.id ? sel + '#' + CSS.escape(el.id) : sel + ' >> nth=' + i;
        return {kind, selector};
      }
    }
    return null;
  };
  return pick('button', 'button', true)
    || pick('input[type=range]', 'range', true)
    || pick('input[type=checkbox]', 'checkbox', true)
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


def playwright_package_dir():
    """Folder of the installed playwright package, or None. Does not import it."""
    try:
        spec = importlib.util.find_spec("playwright")
    except (ImportError, ValueError):
        return None
    return Path(spec.origin).parent if spec and spec.origin else None


def browsers_root():
    """Where Playwright keeps its browsers, or None when that is unknown."""
    env = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if env == "0":  # browsers live inside the playwright package
        package = playwright_package_dir()
        return package / "driver" / "package" / ".local-browsers" if package else None
    if env:
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
    if root is None or not root.is_dir():
        return []
    dirs = [d for d in root.glob("chromium*-*") if (d / "INSTALLATION_COMPLETE").exists()]
    full = sorted((d for d in dirs if d.name.startswith("chromium-")), key=revision, reverse=True)
    shell = sorted((d for d in dirs if d not in full), key=revision, reverse=True)
    exes = []
    for d in full + shell:
        for pattern in EXE_PATTERNS:
            exes.extend(p for p in d.glob(pattern) if p.is_file())
    return exes


def candidate_names():
    raw = os.environ.get("RENDER_CHECK_BROWSERS")
    return [n.strip() for n in raw.split(",")] if raw else list(DEFAULT_CANDIDATES)


def candidate_list():
    """(launch kwargs, label) pairs in the order to try them."""
    out = []
    for name in candidate_names():
        if name == "bundled":
            exes = bundled_executables(browsers_root())
            if exes:
                out.append(({}, "playwright-chromium (default)"))
                out.extend(({"executable_path": str(e)},
                            f"playwright-chromium ({e.parent.parent.name})") for e in exes)
        elif name in ("chrome", "msedge"):
            out.append(({"channel": name}, name))
    return out


def launch(pw, candidates):
    errors = []
    for kwargs, label in candidates:
        try:
            browser = pw.chromium.launch(headless=True, **kwargs)
            return browser, f"{label} {browser.version}", errors
        except Exception as exc:  # noqa: BLE001 - try the next candidate
            errors.append(f"{label}: {str(exc).splitlines()[0]}")
    return None, None, errors


def add_unique(items, text):
    if text not in items:
        items.append(text)


def first_line(exc):
    return (str(exc).strip().splitlines() or [type(exc).__name__])[0]


def interact(page, interaction, shot_path, pw_error):
    """Do the interaction; return (screenshot path, None) or (None, error text).

    A control that cannot be used (a click that times out because something
    covers it, and so on) is a page problem, not an environment problem."""
    el = page.locator(f"[data-render-check={interaction['kind']}]").first
    try:
        if interaction["kind"] in ("button", "checkbox"):
            el.click(timeout=CLICK_TIMEOUT_MS)
        elif interaction["kind"] == "range":
            el.evaluate(RANGE_TO_MAX_JS)
        else:
            el.evaluate("(d) => { d.open = true; }")
        page.wait_for_timeout(SETTLE_MS)
    except pw_error as exc:
        return None, f"{interaction['kind']} {interaction['selector']}: {first_line(exc)}"
    page.screenshot(path=str(shot_path), full_page=True)
    return str(shot_path), None


def render(pw, candidates, url, out_dir, result):
    from playwright.sync_api import Error as PwError, TimeoutError as PwTimeout

    browser, label, errors = launch(pw, candidates)
    if browser is None:
        return None, errors
    result["browser"] = label
    console, page_errors, shots = result["console_errors"], result["page_errors"], result["screenshots"]
    out_dir.mkdir(parents=True, exist_ok=True)
    interaction_shot = None
    try:
        for name, width, height, scheme, main_view in VIEWS:
            context = browser.new_context(viewport={"width": width, "height": height},
                                          color_scheme=scheme)
            page = context.new_page()
            page.on("console", lambda m: m.type == "error" and add_unique(console, m.text))
            page.on("pageerror", lambda e: add_unique(page_errors, str(e)))
            try:
                page.goto(url, wait_until="load", timeout=LOAD_TIMEOUT_MS)
            except PwTimeout as exc:  # for example a resource that never loads
                result["load_error"] = f"{name}: {first_line(exc)}"
                context.close()
                break
            page.wait_for_timeout(SETTLE_MS)
            shot = out_dir / f"{name}.png"
            page.screenshot(path=str(shot), full_page=True)
            shots.append(str(shot))
            if main_view:
                m = page.evaluate(OVERFLOW_JS)
                m["overflow"] = m["scroll_width"] > m["client_width"] + 1
                result["overflow_390"] = m
                interaction = page.evaluate(FIND_CONTROL_JS)
                if interaction:
                    result["interaction"] = interaction
                    interaction_shot, result["interaction_error"] = interact(
                        page, interaction, out_dir / f"{name}-interaction.png", PwError)
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
        names = ", ".join(candidate_names())
        return env_error(str(path), f"no browser candidate available (tried: {names})",
                         INSTALL_HINT)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return env_error(str(path), "playwright is not installed", IMPORT_HINT)

    result = {"file": str(path), "browser": None, "load_error": None,
              "console_errors": [], "page_errors": [], "overflow_390": None,
              "interaction": None, "interaction_error": None,
              "screenshots": [], "pass": False}
    try:
        with sync_playwright() as pw:
            label, errors = render(pw, candidates, path.as_uri(), out_dir, result)
    except Exception as exc:  # noqa: BLE001 - report as JSON, not a traceback
        return env_error(str(path), f"render failed: {first_line(exc)}",
                         "The browser stopped unexpectedly. Run the check again; "
                         "if it fails again, try another browser with "
                         "RENDER_CHECK_BROWSERS.")
    if label is None:
        return env_error(str(path), "no browser could be launched: " + "; ".join(errors),
                         INSTALL_HINT)

    overflow = result["overflow_390"]
    failed = bool(result["load_error"] or result["interaction_error"]
                  or result["console_errors"] or result["page_errors"]
                  or (overflow and overflow["overflow"]))
    result["pass"] = not failed
    return emit(result, EXIT_FAIL if failed else EXIT_PASS)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
