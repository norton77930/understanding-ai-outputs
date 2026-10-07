# Design baseline

Every page follows these rules. `scripts/page_check.py` enforces the file rules. `scripts/render_check.py` and the layout check cover the rest.

## File rules (checked by `page_check.py`)

- One file: `index.html`. Put all CSS in one `<style>` block and all JS in one `<script>` block. No build step, no server.
- No external resources by default. If a library is necessary, load it only from `cdnjs.cloudflare.com`, `cdn.jsdelivr.net/npm/` or `unpkg.com`, with an exact version in the URL (`@1.2.3` or `/1.2.3/`). Tell the user that the page then needs a network connection.
- No local resources: no relative paths, no `file:` URLs. Inline images as SVG or `data:` URLs.
- `<html lang="...">` matches the page language: `en`, `zh-Hant-TW` (or `zh-TW`), and so on.
- A non-empty `<title>`.
- `<meta name="viewport" content="width=device-width, initial-scale=1">`.
- Colors as CSS custom properties on `:root`, with a `@media (prefers-color-scheme: dark)` override in the inline `<style>`.
- At least one native control: `<button>`, `<input type="range|checkbox|radio|number">`, `<select>` or `<details>`.
- No inline handler attributes (`onclick=`, `oninput=` ...). Use `addEventListener` in the script.
- File size 500 KB or less.

## Layout and access rules (checked by `render_check.py` and the layout check)

- Set the `body` background and text color from the custom properties, so dark mode covers the whole page.
- No horizontal scroll at 390 px. Use `max-width` on the content column, `flex-wrap` for rows, `max-width: 100%` for SVG and images, and `overflow-x: auto` for `<pre>` and wide tables.
- No console errors and no uncaught exceptions.
- Every control works with the keyboard and shows a visible focus ring (`:focus-visible`).
- Give every control a visible label (`<label>`, `<legend>`, button text). Show a live value in an `<output>` element.
- Text contrast stays readable in light and dark mode. Do not use color as the only signal; add a label, a border or a pattern.
- The key idea is visible before any interaction. Put it in the first paragraph.

## Minimal skeleton

This skeleton passes `page_check.py`. Replace the title, the text and the control.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Topic in a few words</title>
<style>
  :root {
    --bg: #ffffff; --fg: #1a1a1a; --muted: #555b63;
    --accent: #0b62c4; --panel: #eef1f5; --border: #c4cad3;
    color-scheme: light dark;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #121417; --fg: #e8eaed; --muted: #a9b0ba;
      --accent: #6fb1ff; --panel: #1f242b; --border: #3b424c;
    }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--fg); font: 1rem/1.5 system-ui, sans-serif; }
  main { max-width: 42rem; margin: 0 auto; padding: 1rem; }
  img, svg { max-width: 100%; height: auto; }
  pre { overflow-x: auto; }
  button, input, select, summary { font: inherit; }
  button { padding: 0.4rem 0.9rem; border: 1px solid var(--border); border-radius: 0.4rem;
           background: var(--panel); color: var(--fg); cursor: pointer; }
  :focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
  .panel { background: var(--panel); border: 1px solid var(--border); border-radius: 0.5rem; padding: 1rem; }
</style>
</head>
<body>
<main>
  <h1>Topic in a few words</h1>
  <p>The key idea in one or two short sentences.</p>
  <div class="panel">
    <button type="button" id="go">Show the next part</button>
    <p id="state">Part 1 of 3.</p>
  </div>
</main>
<script>
  const state = document.getElementById("state");
  let part = 1;
  document.getElementById("go").addEventListener("click", () => {
    part = part % 3 + 1;
    state.textContent = `Part ${part} of 3.`;
  });
</script>
</body>
</html>
```

## Language

- Write the page in the conversation's language. Set `lang` to match.
- For zh-TW, use `lang="zh-Hant-TW"` and Taiwan wording (程式, 資料, 伺服器). Add `"Noto Sans TC", "Microsoft JhengHei", "PingFang TC"` before `sans-serif` in the font stack.
- Format numbers with `toLocaleString(document.documentElement.lang)`.
