# Checks

Two scripts check a page. Run both from the user's project root.

## Static check: `page_check.py`

Python standard library only. Run it with `python` (`python3` if `python` is missing).

```
python <skill folder>/scripts/page_check.py FILE [--max-kb N]
```

- `--max-kb N`: size budget in KB (default 500, 1 KB = 1024 bytes).

It prints one JSON object:

```
{"file": str, "size_kb": float, "lang": str|null, "title": str|null,
 "issues": [{"rule": str, "line": int|null, "message": str}],
 "stats": {"words": int, "cjk_chars": int, "controls": int, "external": [str]},
 "pass": bool}
```

`line` is the 1-based line of the problem, or null when something is missing.

| `rule` | Meaning | Fix |
| --- | --- | --- |
| `external-host` | A resource is not on cdnjs.cloudflare.com, cdn.jsdelivr.net/npm/ or unpkg.com, or uses another scheme | Inline it, or load it from an allowed host |
| `unpinned-version` | An allowed-host URL has no exact version | Use `@1.2.3` or `/1.2.3/` in the URL |
| `local-resource` | A relative or `file:` path | Inline it as SVG or a `data:` URL |
| `missing-lang` | No `lang` on `<html>` | Add the page language |
| `missing-title` | No non-empty `<title>` | Add a title |
| `missing-viewport` | No viewport meta with `width=device-width` | Add the viewport meta |
| `missing-dark-mode` | No `prefers-color-scheme: dark` in an inline `<style>` | Add the dark-mode override |
| `no-interaction` | No button, range/checkbox/radio/number input, select or details | Add an interaction pattern |
| `inline-handler` | An `on*=` attribute | Use `addEventListener` |
| `too-large` | File is over the budget | Remove data or libraries |

Resources checked: `<script src>`, `<link href>` (stylesheet, preload, icon, modulepreload), `<img src>`, `<iframe src>`, `<source src>`, and CSS `@import` and `url()`. `<a href>` links are not resources. `data:` URLs and `#` fragments are allowed.

`stats.words` counts non-CJK words in the visible text. `stats.cjk_chars` counts CJK characters. Use them to keep the text short.

Exit codes: 0 = every rule passed, 1 = at least one issue, 2 = usage or input error (missing file, not UTF-8, bad flag).

## Render check: `render_check.py`

Needs `uv`. `uv` reads the inline (PEP 723) block and installs the Python Playwright package on first use. That step downloads no browser.

```
uv run <skill folder>/scripts/render_check.py FILE [--out DIR]
```

- `--out DIR`: screenshot folder (default: `<folder of FILE>/screenshots`).

What it does:

1. Opens FILE through `file://` in headless Chromium.
2. Saves full-page screenshots at 390x844 and 1280x800, in light and dark mode: `390x844-light.png`, `390x844-dark.png`, `1280x800-light.png`, `1280x800-dark.png`.
3. Collects console errors and uncaught page errors from every load.
4. At 390 px (light), measures horizontal overflow: `scrollWidth > clientWidth + 1`.
5. Does one interaction at 390 px (light): clicks the first visible `<button>`; else moves the first visible range input to its max; else opens the first `<details>`. Then saves `390x844-light-interaction.png`. Checkboxes, radios and selects are not used. With only those controls, `interaction` is null and there is no fifth screenshot.

It prints one JSON object:

```
{"file": str, "browser": str, "console_errors": [str], "page_errors": [str],
 "overflow_390": {"scroll_width": int, "client_width": int, "overflow": bool},
 "interaction": {"kind": "button"|"range"|"details", "selector": str}|null,
 "screenshots": [str], "pass": bool}
```

On exit 2 the object is `{"file", "error", "hint", "pass": false}`.

Exit codes: 0 = no console or page errors and no overflow; 1 = at least one of those; 2 = environment or input problem (missing file, Playwright not importable, no usable browser, render failure), with a `hint`.

A disabled or hidden first button makes the click time out. The check then exits 2 with `render failed`. Make the first visible button enabled on load.

### Browser

The script never downloads a browser. It tries, in order:

1. `bundled`: Chromium that Playwright installed under `PLAYWRIGHT_BROWSERS_PATH` (default `%LOCALAPPDATA%\ms-playwright` on Windows, `~/.cache/ms-playwright` on Linux, `~/Library/Caches/ms-playwright` on macOS).
2. `chrome`: an installed Google Chrome.
3. `msedge`: an installed Microsoft Edge.

Environment variables:

- `RENDER_CHECK_BROWSERS`: comma list of `bundled`, `chrome`, `msedge`. Limits or reorders the candidates.
- `PLAYWRIGHT_BROWSERS_PATH`: where Playwright's browsers are. Use the same value for the install and for the check.
- `UV_CACHE_DIR`: where `uv` keeps the Playwright package.

If no browser is found, ask the user before an install. Tell them the size (about 150-200 MB) and the command: `uv run --with playwright playwright install chromium`. Or the user can install Google Chrome or Microsoft Edge.

## Layout check

Look at each screenshot from the render check. Look for:

- overlapping elements, text clipped at an edge, content cut off at 390 px
- text too small or too faint to read, in light or in dark mode
- dark mode that leaves a light area (a missing `background` on `body` or a panel)
- an interaction screenshot that does not show a change
