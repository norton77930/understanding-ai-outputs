# Design baseline

Every page follows these rules. `scripts/page_check.py` enforces the file rules. `scripts/render_check.py` and the layout check cover the rest.

## File rules (checked by `page_check.py`)

- One file: `index.html`. Put all CSS in one `<style>` block and all JS in one `<script>` block. No build step, no server.
- No external resources by default. If a library is necessary, load it only from `cdnjs.cloudflare.com`, `cdn.jsdelivr.net/npm/` or `unpkg.com`, with an exact version in the URL: `cdn.jsdelivr.net/npm/<name>@1.2.3/...`, `unpkg.com/<name>@1.2.3/...` or `cdnjs.cloudflare.com/ajax/libs/<name>/1.2.3/...`. This also applies to `import` and `fetch` URLs in the script. Tell the user that the page then needs a network connection.
- No local resources: no relative paths, no `file:` URLs. Inline images as SVG or `data:` URLs.
- `<html lang="...">` matches the page language, for example `en`. For zh-TW, see "Text" in `SKILL.md`.
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

## Visual rules (checked by the layout check)

The rules above are a floor. They do not set a look.

- Structure: a `<header>` with the `<h1>` title and a lead paragraph that states the main conclusion, then one `<section>` per key point. Start each section with an `<h2>` that states its point.
- State colors: three custom properties, `--current`, `--changed` and `--done`, each with a dark-mode value. Use the same state color for the same state in every section.
- Color marks state but is never the only cue. Add a label (`Step 2 of 4`, "Done"), a shape, a border or a font weight.
- Use CSS transitions or animations for state changes (a cell that moves, a bar that grows, a part that fades). Show the change, not only its result.
- Respect `prefers-reduced-motion: reduce`: turn transitions and animations off in that media query. Autoplay starts only when the reader presses a button.

## Design

Design each page for its topic as a polished, bespoke explainer, not as a template. Choose a layout, a type scale and a visual treatment that fit the topic: for example a wide two-column band for a chart and its numbers, a large display figure, numbered section markers, or a full-width animated diagram. Do not reuse a fixed look from page to page, and do not copy the look of the examples in `interaction-patterns.md`.

Some techniques help the reader understand. Use them where they fit the point, not as a checklist:

- Put cases side by side, so the reader compares them at once. For example, three learning rates that animate together.
- Put a live calculation or state panel next to a visualization. It shows the numbers behind the picture, step by step.
- End with a short summary of the key points.

## Skeleton

This skeleton is the required minimum, not a design. It passes `page_check.py`. Keep the head elements, the token names and the reduced-motion rule. Change the token values to fit your design, and keep a dark value for each. Build the page in `<main>`, and replace the placeholder button.

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
    --current: #0b62c4; --changed: #a04a00; --done: #1b7a3a;
    color-scheme: light dark;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #121417; --fg: #e8eaed; --muted: #a9b0ba;
      --accent: #6fb1ff; --panel: #1f242b; --border: #3b424c;
      --current: #6fb1ff; --changed: #ffb26b; --done: #6fd38d;
    }
  }
  body { background: var(--bg); color: var(--fg); }
  :focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
  @media (prefers-reduced-motion: reduce) {
    * { transition: none !important; animation: none !important; }
  }
</style>
</head>
<body>
<main>
  <!-- Design the page for this topic here. -->
  <button type="button" id="placeholder">Placeholder control</button>
</main>
<script>
  document.getElementById("placeholder").addEventListener("click", (e) => {
    e.currentTarget.textContent = "Pressed";
  });
</script>
</body>
</html>
```

## Language

- Write the page in the conversation's language. Set `lang` to match.
- For zh-TW (the `lang` value and the wording are in "Text" in `SKILL.md`), add `"Noto Sans TC", "Microsoft JhengHei", "PingFang TC"` before `sans-serif` in the font stack.
- Format numbers with `toLocaleString(document.documentElement.lang)`.
