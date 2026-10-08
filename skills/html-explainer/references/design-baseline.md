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

## Visual design (checked by the layout check)

The rules above are a floor. Make the page look designed.

- Visual hierarchy: a `<header>` with the `<h1>` title and a lead paragraph that states the main conclusion, then one `<section>` per key point. Show each section as a card or a band: its own background, border or spacing. Start each section with an `<h2>` that states its point.
- A small palette: one accent color and three state colors as custom properties, `--current`, `--changed` and `--done`, each with a dark-mode value. Use the same state color for the same state in every section.
- Color marks state but is never the only cue. Add a label (`Step 2 of 4`, "Done"), a shape, a border or a font weight.
- Use CSS transitions for state changes (a cell that moves, a bar that grows, a part that fades), 0.2 to 0.5 s. Show the change, not only its result.
- Respect `prefers-reduced-motion: reduce`: turn transitions and animations off in that media query. Autoplay starts only when the reader presses a button.

## Skeleton

This skeleton passes `page_check.py`. Replace the title, the lead and the sections. Add one section per key point.

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
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--fg); font: 1rem/1.5 system-ui, sans-serif; }
  main { max-width: 46rem; margin: 0 auto; padding: 1rem; }
  header { padding: 1rem 0 0.5rem; }
  .lead { font-size: 1.15rem; color: var(--muted); }
  section { background: var(--panel); border: 1px solid var(--border); border-radius: 0.6rem; padding: 1rem; margin: 1rem 0; }
  h2 { margin-top: 0; font-size: 1.2rem; }
  img, svg { max-width: 100%; height: auto; }
  pre { overflow-x: auto; }
  button, input, select, summary { font: inherit; }
  button { padding: 0.4rem 0.9rem; border: 1px solid var(--border); border-radius: 0.4rem;
           background: var(--bg); color: var(--fg); cursor: pointer; }
  :focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
  .parts { display: flex; flex-wrap: wrap; gap: 0.4rem; padding: 0; list-style: none; }
  .parts li { padding: 0.3rem 0.6rem; border: 2px solid var(--border); border-radius: 0.3rem; transition: border-color 0.3s, transform 0.3s; }
  .parts li.current { border-color: var(--current); font-weight: bold; transform: translateY(-0.3rem); }
  .parts li.done { border-color: var(--done); }
  .parts li.done::after { content: " ✓"; }
  @media (prefers-reduced-motion: reduce) {
    * { transition: none !important; animation: none !important; }
  }
</style>
</head>
<body>
<main>
  <header>
    <h1>Topic in a few words</h1>
    <p class="lead">The main conclusion in one or two short sentences.</p>
  </header>
  <section aria-labelledby="p1">
    <h2 id="p1">Key point 1, stated as a sentence</h2>
    <p>One or two sentences that name the point. The control below demonstrates it.</p>
    <ol class="parts" id="parts"><li>Part 1</li><li>Part 2</li><li>Part 3</li></ol>
    <button type="button" id="go">Show the next part</button>
    <p id="state" aria-live="polite"></p>
  </section>
  <section aria-labelledby="p2">
    <h2 id="p2">Key point 2, stated as a sentence</h2>
    <p>Each key point gets its own section and its own pattern.</p>
  </section>
</main>
<script>
  const items = document.querySelectorAll("#parts li");
  const state = document.getElementById("state");
  let part = 0;
  function show() {
    items.forEach((li, k) => {
      li.classList.toggle("current", k === part);
      li.classList.toggle("done", k < part);
    });
    state.textContent = `Part ${part + 1} of ${items.length}.`;
  }
  document.getElementById("go").addEventListener("click", () => {
    part = (part + 1) % items.length;
    show();
  });
  show();
</script>
</body>
</html>
```

## Language

- Write the page in the conversation's language. Set `lang` to match.
- For zh-TW (the `lang` value and the wording are in "Text" in `SKILL.md`), add `"Noto Sans TC", "Microsoft JhengHei", "PingFang TC"` before `sans-serif` in the font stack.
- Format numbers with `toLocaleString(document.documentElement.lang)`.
