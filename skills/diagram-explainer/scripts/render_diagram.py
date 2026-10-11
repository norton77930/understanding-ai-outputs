# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "playwright==1.62.*",
# ]
# ///
"""Render a Mermaid file to SVG and PNG, or an SVG file to PNG, in a headless browser.

Usage:
    uv run render_diagram.py FILE.mmd [--out DIR]
    uv run render_diagram.py FILE.svg [--out DIR]

Mermaid (any file not ending in .svg): writes DIR/<name>.svg and
DIR/<name>.png (DIR defaults to the folder of FILE). The PNG is a screenshot
of the rendered diagram at device scale 2, with a small white margin.

SVG (FILE ends in .svg): writes only DIR/<name>.png and never rewrites the
SVG. The SVG is shown in an <img> element, as a host page shows it (no
scripts, no outside resources), at its own size: width and height when they
are plain numbers, otherwise the viewBox size (300 x 150 without either).
The PNG is that image at device scale 2, with no margin. "svg" in the result
is the input path; "mermaid_version" is null. Needs no network.

Prints one JSON object on stdout (UTF-8):

    {"svg": path | null, "png": path | null,
     "width": int | null, "height": int | null,   PNG size in pixels
     "mermaid_version": str | null, "browser": str | null,
     "error": str | null,
     "hint": str}                                   only with exit 2

Exit code:
    0  rendered
    1  Mermaid reported a parse or render error, or the browser could not
       load the SVG ("error" has the message), or the render did not finish
       within 30 seconds ("error" says "Render timed out"); no files are
       written
    2  environment or input problem ("hint" says what to do): Playwright
       missing, no browser, Mermaid or one of its lazy-loaded diagram chunks
       not loadable (no network), unreadable input file, unexpected crash

Mermaid is loaded from cdn.jsdelivr.net at the pinned version MERMAID_VERSION.
The page is served from memory through Playwright request routing; nothing is
written outside DIR (the browser keeps its own temporary profile).

Browser policy: this script NEVER downloads a browser. It tries, in order:
    1. Playwright's bundled Chromium, if already installed (location follows
       PLAYWRIGHT_BROWSERS_PATH)
    2. Google Chrome   (channel "chrome")
    3. Microsoft Edge  (channel "msedge")
If none launches, it exits 2 with the install command and download size.

Testing hooks (environment variables):
    DIAGRAM_RENDER_SIMULATE=no-playwright | no-browser   act as if that part of
        the environment is missing
    DIAGRAM_RENDER_SIMULATE=chunk-fetch-failure          act as if Mermaid
        failed to fetch a lazy-loaded diagram chunk (exit 2; Mermaid input)
    DIAGRAM_RENDER_SIMULATE=crash                        raise an unexpected
        exception (exit 2)
    DIAGRAM_RENDER_TIMEOUT_MS=N                          render time limit in
        milliseconds (default 30000)
"""

import argparse
import base64
import json
import math
import os
import re
import struct
import sys
from pathlib import Path

MERMAID_VERSION = "11.17.2"
MERMAID_URL = f"https://cdn.jsdelivr.net/npm/mermaid@{MERMAID_VERSION}/dist/mermaid.esm.min.mjs"
PAGE_URL = "http://render-diagram.localhost/index.html"
LOAD_TIMEOUT_MS = 30_000
RENDER_TIMEOUT_MS = 30_000

# Messages a browser gives when a lazy-loaded Mermaid chunk cannot be fetched
# (Chromium, Firefox, WebKit, and raw network errors).
_NETWORK_ERROR_RE = re.compile(
    r"Failed to fetch dynamically imported module|"
    r"error loading dynamically imported module|"
    r"Importing a module script failed|"
    r"NetworkError|net::ERR_|Failed to fetch|Load failed", re.IGNORECASE)
SIMULATED_CHUNK_ERROR = (
    "Failed to fetch dynamically imported module: "
    f"https://cdn.jsdelivr.net/npm/mermaid@{MERMAID_VERSION}/dist/chunks/"
    "mermaid.esm.min/flowDiagram.mjs (simulated)")

HINT_NO_PLAYWRIGHT = (
    "Run this script with uv so that its Playwright dependency is installed: "
    "uv run render_diagram.py FILE.mmd. Install uv from https://docs.astral.sh/uv/."
)
HINT_NO_BROWSER = (
    "No browser could start. Install Google Chrome or Microsoft Edge, or "
    "install Playwright's Chromium (about 300 MB download, about 700 MB on "
    "disk) with: uv run --with playwright==1.62.* playwright install chromium. "
    "Set PLAYWRIGHT_BROWSERS_PATH first to choose the install folder (default: "
    "%LOCALAPPDATA%\\ms-playwright on Windows, ~/.cache/ms-playwright on Linux, "
    "~/Library/Caches/ms-playwright on macOS) and keep it set when you render. "
    "Ask the user before this download."
)
HINT_NO_NETWORK = (
    f"Mermaid could not load from {MERMAID_URL}. Check the network connection "
    "and proxy settings, then run again. Without network, deliver the Mermaid "
    "source only and say that rendering was skipped."
)

PAGE_HTML = f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
  html, body {{ margin: 0; background: #ffffff; }}
  #out {{ display: inline-block; padding: 16px; background: #ffffff; }}
</style></head>
<body><div id="out"></div>
<script type="module">
  try {{
    const m = await import("{MERMAID_URL}");
    m.default.initialize({{ startOnLoad: false }});
    window.__mermaid = m.default;
    window.__state = "ready";
  }} catch (e) {{
    window.__loadError = String(e && e.message ? e.message : e);
    window.__state = "error";
  }}
</script></body></html>
"""

# Starts the render and returns at once. The outcome lands in window.__rendered,
# which Python waits for with a time limit.
RENDER_JS = """(source) => {
  window.__rendered = undefined;
  const message = (e) => String(e && e.message ? e.message : e);
  (async () => {
    const out = document.getElementById("out");
    try {
      const { svg } = await window.__mermaid.render("diagram", source);
      out.innerHTML = svg;
    } catch (e) {
      document.querySelectorAll("[id^='ddiagram']").forEach((n) => n.remove());
      return { error: message(e) };
    }
    // Show the diagram at its natural size (Mermaid sets width 100%).
    const el = out.querySelector("svg");
    const vb = el.viewBox.baseVal;
    if (vb && vb.width && vb.height) {
      el.style.maxWidth = "none";
      el.setAttribute("width", vb.width);
      el.setAttribute("height", vb.height);
    }
    return { svg: out.innerHTML };
  })().then(
    (r) => { window.__rendered = r; },
    (e) => { window.__rendered = { error: message(e) }; });
}"""


SVG_PAGE_HTML = """<!doctype html>
<html><head><meta charset="utf-8">
<style>html, body { margin: 0; background: #ffffff; } img { display: block; }</style>
</head><body></body></html>
"""

# Parses the SVG for its size, then shows it in an <img> (how a host page shows
# it). The outcome lands in window.__rendered, as in RENDER_JS.
SVG_RENDER_JS = """([dataUrl, text]) => {
  window.__rendered = undefined;
  const doc = new DOMParser().parseFromString(text, "image/svg+xml");
  const failure = doc.getElementsByTagName("parsererror")[0];
  const root = doc.documentElement;
  if (failure || root.localName !== "svg") {
    const detail = failure ? failure.textContent.trim().split("\\n")[0] : "the root is not <svg>";
    window.__rendered = { error: "The SVG did not parse: " + detail };
    return;
  }
  const plain = (v) => {
    const m = /^\\s*([0-9]*\\.?[0-9]+)\\s*(px)?\\s*$/.exec(v || "");
    return m ? parseFloat(m[1]) : null;
  };
  const vb = (root.getAttribute("viewBox") || "").trim().split(/[\\s,]+/).map(Number);
  let w = plain(root.getAttribute("width")), h = plain(root.getAttribute("height"));
  if (vb.length === 4 && vb.every(Number.isFinite) && vb[2] > 0 && vb[3] > 0) {
    if (w === null && h === null) { w = vb[2]; h = vb[3]; }
    else if (w === null) { w = h * vb[2] / vb[3]; }
    else if (h === null) { h = w * vb[3] / vb[2]; }
  }
  w = w || 300; h = h || 150;
  const img = new Image();
  img.id = "out";
  img.style.width = w + "px";
  img.style.height = h + "px";
  document.body.appendChild(img);
  img.src = dataUrl;
  img.decode().then(
    () => { window.__rendered = { width: w, height: h }; },
    () => { img.remove();
            window.__rendered = { error: "The browser could not load the SVG as an image." }; });
}"""

SIMULATED_WITHOUT_BROWSER = ("crash", "chunk-fetch-failure")


def result(**fields):
    base = {"svg": None, "png": None, "width": None, "height": None,
            "mermaid_version": MERMAID_VERSION, "browser": None, "error": None}
    base.update(fields)
    return base


def emit(data, code):
    sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    sys.stdout.flush()
    return code


def render_timeout_ms():
    """Render time limit; DIAGRAM_RENDER_TIMEOUT_MS overrides it (tests)."""
    try:
        value = int(os.environ.get("DIAGRAM_RENDER_TIMEOUT_MS", ""))
    except ValueError:
        return RENDER_TIMEOUT_MS
    return value if value > 0 else RENDER_TIMEOUT_MS


def render_failure(message, browser):
    """Map a Mermaid render error to (exit code, result).

    A failed fetch of a lazy-loaded chunk is an environment problem (exit 2).
    Anything else is Mermaid's own parse or render error (exit 1)."""
    if _NETWORK_ERROR_RE.search(message):
        return 2, result(browser=browser, error=f"Mermaid could not load: {message}",
                         hint=HINT_NO_NETWORK)
    return 1, result(browser=browser, error=message)


def png_size(data):
    """Width and height from a PNG header."""
    return struct.unpack(">II", data[16:24])


def launch_browser(playwright):
    """Try the bundled Chromium, then Chrome, then Edge. Never downloads."""
    attempts = [("playwright-chromium", {}), ("chrome", {"channel": "chrome"}),
                ("msedge", {"channel": "msedge"})]
    failures = []
    for name, kwargs in attempts:
        try:
            browser = playwright.chromium.launch(headless=True, **kwargs)
        except Exception as exc:  # Playwright raises its own Error type
            first = (str(exc).strip().splitlines() or [type(exc).__name__])[0]
            failures.append(f"{name}: {first}")
            continue
        return browser, f"{name} {browser.version}", failures
    return None, None, failures


def render(source, svg_path, png_path):
    """Return (exit code, result dict)."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser, label, failures = launch_browser(p)
        if browser is None:
            return 2, result(error="No browser could start. " + "; ".join(failures),
                             hint=HINT_NO_BROWSER)
        try:
            context = browser.new_context(device_scale_factor=2,
                                          viewport={"width": 1600, "height": 1200})
            page = context.new_page()
            page.route(PAGE_URL, lambda route: route.fulfill(
                status=200, content_type="text/html; charset=utf-8", body=PAGE_HTML))
            page.goto(PAGE_URL)
            try:
                page.wait_for_function("window.__state !== undefined",
                                       timeout=LOAD_TIMEOUT_MS)
            except Exception:
                return 2, result(browser=label, error="Timed out loading Mermaid.",
                                 hint=HINT_NO_NETWORK)
            if page.evaluate("window.__state") != "ready":
                err = page.evaluate("window.__loadError")
                return 2, result(browser=label, error=f"Mermaid did not load: {err}",
                                 hint=HINT_NO_NETWORK)

            timeout_ms = render_timeout_ms()
            page.evaluate(RENDER_JS, source)
            try:
                page.wait_for_function("window.__rendered !== undefined",
                                       timeout=timeout_ms)
            except PlaywrightTimeout:
                return 1, result(browser=label,
                                 error=f"Render timed out after {timeout_ms / 1000:g} "
                                       "seconds; simplify the diagram or run again.")
            rendered = page.evaluate("window.__rendered")
            if "error" in rendered:
                return render_failure(rendered["error"], label)

            png = page.locator("#out").screenshot(type="png")
            svg_path.parent.mkdir(parents=True, exist_ok=True)
            svg_path.write_text(rendered["svg"], encoding="utf-8")
            png_path.write_bytes(png)
            width, height = png_size(png)
            return 0, result(svg=str(svg_path), png=str(png_path), width=width,
                             height=height, browser=label)
        finally:
            browser.close()


def render_svg(raw, text, src_path, png_path):
    """Show an SVG file in an <img> and save a PNG. Return (exit code, result)."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright

    data_url = "data:image/svg+xml;base64," + base64.b64encode(raw).decode("ascii")
    with sync_playwright() as p:
        browser, label, failures = launch_browser(p)
        if browser is None:
            return 2, result(error="No browser could start. " + "; ".join(failures),
                             hint=HINT_NO_BROWSER, mermaid_version=None)
        try:
            context = browser.new_context(device_scale_factor=2,
                                          viewport={"width": 1600, "height": 1200})
            page = context.new_page()
            page.route(PAGE_URL, lambda route: route.fulfill(
                status=200, content_type="text/html; charset=utf-8", body=SVG_PAGE_HTML))
            page.goto(PAGE_URL)
            timeout_ms = render_timeout_ms()
            page.evaluate(SVG_RENDER_JS, [data_url, text])
            try:
                page.wait_for_function("window.__rendered !== undefined",
                                       timeout=timeout_ms)
            except PlaywrightTimeout:
                return 1, result(browser=label, mermaid_version=None,
                                 error=f"Render timed out after {timeout_ms / 1000:g} "
                                       "seconds; simplify the SVG or run again.")
            rendered = page.evaluate("window.__rendered")
            if "error" in rendered:
                return 1, result(browser=label, mermaid_version=None,
                                 error=rendered["error"])
            # Make room for a large image so the screenshot is not cut.
            page.set_viewport_size({
                "width": max(1600, math.ceil(rendered["width"])),
                "height": max(1200, math.ceil(rendered["height"]))})
            png = page.locator("#out").screenshot(type="png")
            png_path.parent.mkdir(parents=True, exist_ok=True)
            png_path.write_bytes(png)
            width, height = png_size(png)
            return 0, result(svg=str(src_path), png=str(png_path), width=width,
                             height=height, browser=label, mermaid_version=None)
        finally:
            browser.close()


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("file", help="Mermaid source file (.mmd) or SVG file (.svg)")
    parser.add_argument("--out", help="output folder (default: folder of FILE)")
    args = parser.parse_args(argv)

    src = Path(args.file).resolve()
    is_svg = src.suffix.lower() == ".svg"
    extra = {"mermaid_version": None} if is_svg else {}
    try:
        raw = src.read_bytes()
        source = raw.decode("utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        kind = "SVG" if is_svg else "Mermaid"
        return emit(result(error=f"Cannot read {args.file}: {exc}",
                           hint=f"Pass the path of a UTF-8 {kind} file.", **extra), 2)
    out_dir = Path(args.out).resolve() if args.out else src.parent
    svg_path = out_dir / f"{src.stem}.svg"
    png_path = out_dir / f"{src.stem}.png"

    simulate = os.environ.get("DIAGRAM_RENDER_SIMULATE", "")
    if simulate == "no-browser":
        return emit(result(error="No browser could start (simulated).",
                           hint=HINT_NO_BROWSER, **extra), 2)
    try:
        if simulate == "no-playwright":
            raise ImportError("simulated")
        if simulate not in SIMULATED_WITHOUT_BROWSER:
            import playwright.sync_api  # noqa: F401
    except ImportError:
        return emit(result(error="Python package playwright is not installed.",
                           hint=HINT_NO_PLAYWRIGHT, **extra), 2)

    try:
        if simulate == "crash":
            raise RuntimeError("simulated crash")
        if simulate == "chunk-fetch-failure":
            code, data = render_failure(SIMULATED_CHUNK_ERROR, None)
        elif is_svg:
            code, data = render_svg(raw, source, src, png_path)
        else:
            code, data = render(source, svg_path, png_path)
    except Exception as exc:  # browser crash, driver error
        return emit(result(error=f"{type(exc).__name__}: {exc}",
                           hint="Run again. If it fails again, check the browser "
                                "installation (see PLAYWRIGHT_BROWSERS_PATH).",
                           **extra), 2)
    return emit(data, code)


if __name__ == "__main__":
    sys.exit(main())
