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
| `unpinned-version` | An allowed-host URL has no exact version where that host puts it | Use `cdn.jsdelivr.net/npm/<name>@1.2.3/...`, `unpkg.com/<name>@1.2.3/...` or `cdnjs.cloudflare.com/ajax/libs/<name>/1.2.3/...` (`<name>` can be `@scope/name` on jsDelivr and unpkg) |
| `local-resource` | A relative or `file:` path | Inline it as SVG or a `data:` URL |
| `bad-url` | A resource URL that cannot be parsed, such as `http://[::1/x` | Correct the URL |
| `missing-lang` | No `lang` on `<html>` | Add the page language |
| `missing-title` | No non-empty `<title>` | Add a title |
| `missing-viewport` | No viewport meta with `width=device-width` | Add the viewport meta |
| `missing-dark-mode` | No `prefers-color-scheme: dark` in an inline `<style>` | Add the dark-mode override |
| `no-interaction` | No button, range/checkbox/radio/number input, select or details | Add an interaction pattern |
| `inline-handler` | An event handler attribute: `on` + 3 or more letters (`onclick`, `oncut`). `one`, `only`, `online`, `onset`, `onward(s)` are not handlers | Use `addEventListener` |
| `too-large` | File is over the budget | Remove data or libraries |

Resources checked:

- `<script src>`; `<link href>` with rel `stylesheet`, `preload`, `modulepreload`, `prefetch`, `prerender`, `manifest` or any `*icon*`; `<link rel="preconnect">` and `dns-prefetch` (host only, no version needed).
- `src` of `<img>`, `<iframe>`, `<source>`, `<embed>`, `<video>`, `<audio>`, `<track>`; `srcset` of `<img>` and `<source>`; `<video poster>`; `<object data>`.
- `href` and `xlink:href` of `<image>`, `<use>`, `<feImage>` and `<script>` inside `<svg>`.
- CSS `@import` and `url()` in inline `<style>` and `style` attributes.
- Inline `<script>` text, including `type="module"`: `import ... from "x"`, `import "x"` and `import("x")` with an absolute URL or a `./`, `../` or `/` path (bare names such as `"d3"` are skipped); `fetch("x")` and `new URL("x")` with an absolute `http(s)` or `//` URL; every quoted URL or path in `<script type="importmap">`. This is a text scan, so a URL in a comment also counts.

`<a href>` links are not resources. `data:` URLs and `#` fragments are allowed.

`stats.words` counts non-CJK words in the visible text. `stats.cjk_chars` counts CJK characters. Use them to keep the text short.

Exit codes: 0 = every rule passed, 1 = at least one issue, 2 = usage or input error (missing file, not UTF-8, bad flag: a message on stderr, no JSON). An unexpected internal error also exits 2 and prints `{"file", "error", "pass": false}`.

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
5. Does one interaction at 390 px (light) on the first usable control. Usable means visible, not disabled (also not inside a disabled `<fieldset>`) and not `pointer-events: none`. It clicks the first usable `<button>`; else moves the first usable range input to its max; else clicks the first usable checkbox; else opens the first `<details>`. Then it saves `390x844-light-interaction.png`. Radios, number inputs and selects are not used. With only those controls, `interaction` is null and there is no fifth screenshot.

It prints one JSON object:

```
{"file": str, "browser": str, "load_error": str|null,
 "console_errors": [str], "page_errors": [str],
 "overflow_390": {"scroll_width": int, "client_width": int, "overflow": bool}|null,
 "interaction": {"kind": "button"|"range"|"checkbox"|"details", "selector": str}|null,
 "interaction_error": str|null,
 "screenshots": [str], "pass": bool}
```

- `interaction_error`: the interaction failed. Usually another element covers the control, so the click times out after 5 s. The other results and the four screenshots are still there; there is no interaction screenshot. Fix the page.
- `load_error`: a load did not finish in 30 s, for example because an external resource never answers. The remaining views are skipped. Fix or remove the resource.

On exit 2 the object is `{"file", "error", "hint", "pass": false}`.

Exit codes: 0 = no page problem; 1 = a page problem: console or page errors, overflow, `interaction_error` or `load_error`; 2 = environment or input problem (missing file, Playwright not importable, no usable browser, or `render failed` when the browser stops unexpectedly), with a `hint`.

### Browser

The script never downloads a browser. It tries, in order:

1. `bundled`: Chromium that Playwright installed under `PLAYWRIGHT_BROWSERS_PATH` (default `%LOCALAPPDATA%\ms-playwright` on Windows, `~/.cache/ms-playwright` on Linux, `~/Library/Caches/ms-playwright` on macOS; `0` means the `.local-browsers` folder inside the playwright package). The script pins `playwright==1.62.*`, which uses Chromium build 1234 (`chromium-1234`). Other installed `chromium-*` builds are tried after it.
2. `chrome`: an installed Google Chrome.
3. `msedge`: an installed Microsoft Edge.

Environment variables:

- `RENDER_CHECK_BROWSERS`: comma list of `bundled`, `chrome`, `msedge`. Limits or reorders the candidates.
- `PLAYWRIGHT_BROWSERS_PATH`: where Playwright's browsers are. Use the same value for the install and for the check.
- `UV_CACHE_DIR`: where `uv` keeps the Playwright package.

If no browser is found, ask the user before an install. Tell them the size (about 300 MB download, about 700 MB on disk) and the command: `uv run --with playwright==1.62.* playwright install chromium`. Or the user can install Google Chrome or Microsoft Edge.

## Layout check

Look at each screenshot from the render check. Look for:

- overlapping elements, text clipped at an edge, content cut off at 390 px
- text too small or too faint to read, in light or in dark mode
- dark mode that leaves a light area (a missing `background` on `body` or a panel)
- an interaction screenshot that does not show a change
- keyboard and focus (in the page source): the controls are native elements in a logical order, with no positive `tabindex`, so Tab reaches each one; a `:focus-visible` rule gives a visible outline, and no `outline: none` removes it without a replacement
