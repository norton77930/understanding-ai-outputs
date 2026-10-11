# Style: blueprint

Read this file only when the user names this style: "blueprint", "engineering drawing", "工程圖", "工程圖紙風格" or "藍圖風格". Without a named style, do not use it.

The look of a technical drawing: ink lines on drafting paper in light mode, light lines on blueprint paper in dark mode, a hairline frame, lettered panels, a title block, numbered pins and line drawings. This file sets the look. It does not set the structure: plan the sections and the patterns from the topic, as `SKILL.md` and "Design" in `design-baseline.md` describe. Use the components that help the topic, not all of them. All rules in `design-baseline.md` still apply.

## Tokens

Start from these values. Keep a dark value for each token you use.

```css
:root {
  --paper: #f5f8fc; --ink: #0d2a4a; --muted: #44607f;
  --line: #1d4f8c; --grid: #dbe5f1; --panel: #ffffff;
  --done: #1d4f8c; --assumed: #8a4b00; --future: #5b6b80;
  --focus: #b3261e;
  color-scheme: light dark;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #0b2545; --ink: #e6eef8; --muted: #a9c0dc;
    --line: #9cc3ff; --grid: #16365e; --panel: #0e2c52;
    --done: #9cc3ff; --assumed: #ffc46b; --future: #a9b6c8;
    --focus: #ffd166;
  }
}
body {
  background-color: var(--paper); color: var(--ink);
  background-image:
    linear-gradient(var(--grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--grid) 1px, transparent 1px);
  background-size: 24px 24px;
}
```

- Text on `--paper` and `--panel` stays at 4.5:1 or more in both modes with these values. Check again if you change them.
- Keep the grid faint. It sits behind panels with a solid `--panel` background, never behind body text.

## Type

- Body: `system-ui, "Segoe UI", Roboto, "Noto Sans TC", "Microsoft JhengHei", "PingFang TC", sans-serif`.
- Labels, tabs, pins and the title block: `ui-monospace, "Cascadia Mono", "SF Mono", Consolas, "Noto Sans Mono CJK TC", "Microsoft JhengHei", monospace`. Latin labels may use `text-transform: uppercase` and `letter-spacing: 0.08em`. Do not letter-space CJK text.
- Only the CJK fonts that match the page language go in the stack (see "Language" in `design-baseline.md`).
- Use system fonts. A web font is an external resource; `page_check.py` allows it only from the allowed CDN hosts, and the page then needs a network connection.

## Components

- **Frame.** A sheet with a hairline border and a second line a few pixels outside it: `border: 1px solid var(--line); box-shadow: 0 0 0 4px var(--paper), 0 0 0 5px var(--line);`. Square corners. Keep the margin small at 390 px.
- **Panels with letter tabs.** Each section is a panel with a solid `--panel` background and a 1px `--line` border. A small tab on its top edge holds a letter (A, B, C), in the label font: `.panel::before { content: attr(data-tab); }` or a `<span>` in the `<h2>`. Refer to panels by letter in the text ("see panel B").
- **Title block.** A small bordered grid of cells, as on a drawing sheet: title, revision, date, and source. Put it in the header, or at the end on a wide screen. It wraps to one column at 390 px. Take the values from the source. If the source has no revision, use "Rev 1" and today's date. The source cell names where the content came from (for example "Answer in this conversation"). Never invent an author.
- **Numbered pins.** Small circles with a number on the figure (`<circle>` and `<text>` in the SVG), and a numbered list next to the figure with the same numbers. A pin can be a `<button>` that reveals its note (the Reveal pattern). The number and the note use the same term.
- **Line figures.** Draw figures as hand-written inline SVG: boxes, arrows and dimension lines with `fill: none` or `fill: var(--panel)`, `stroke: var(--line)`, `stroke-width: 1.5`, and labels in the label font. Use `vector-effect: non-scaling-stroke` so lines stay thin on a phone. Give the SVG a `viewBox`, `max-width: 100%` and a `<title>`.
- **Status strokes.** When a figure shows status, use the line style as the main cue and the color as the second cue:

  ```css
  .done    { stroke: var(--done); }
  .assumed { stroke: var(--assumed); stroke-dasharray: 6 4; }
  .future  { stroke: var(--future); stroke-dasharray: 1 5; stroke-linecap: round; }
  ```

  Solid means done (or decided), dashed means assumed, dotted means future. Put a legend with the three line samples and their words next to the figure. Use status strokes only when the source gives the status (see "Make the assumptions visible" in `interaction-patterns.md`).

## With the interaction patterns

The patterns in `interaction-patterns.md` work unchanged. Give the controls the look: square corners, a 1px `--line` border, the label font, and a solid fill for the pressed or current state (`aria-pressed="true"`, the current step) plus a word or a weight change. A step-through can mark the current panel with a thicker frame and its letter ("Step 2 of 4: panel B"). The focus ring uses `--focus`, a color that the drawing does not use for lines. Transitions stay short (lines that draw in with `stroke-dashoffset`, a panel that fades in) and turn off for `prefers-reduced-motion: reduce`. The first `<button>` rule of the render check still applies.
