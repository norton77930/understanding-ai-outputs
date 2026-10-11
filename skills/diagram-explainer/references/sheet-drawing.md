# Drawing an overview sheet

An overview sheet is one hand-written SVG with 3 to 6 small panels that together explain a whole topic on one page. It follows every rule in `svg-drawing.md` (structure, self-contained, background, contrast, font stack). This file adds what is different for a sheet.

## When to make a sheet

Make a sheet only when the user explicitly asks for a whole-topic overview on one image: "one sheet that explains X", "an overview poster of X", "X at a glance on one page", "一張圖看懂 X", "整理成一張總覽圖", "畫一張 X 的總覽圖". "Cheat sheet" alone is not a sheet request (it usually means a text list); "cheat sheet" together with a picture word ("畫成 cheat sheet", "a cheat sheet as an image") is.

Without such a request, keep the normal path: one question, one diagram (Mermaid or SVG), at most 3 diagrams. Do not turn a single question into a sheet because the topic is large.

## Plan the panels

1. Write down 3 to 6 sub-questions that, answered together, give the overview. Each panel answers one of them. Fewer panels with more room are better than six cramped ones.
2. Give each panel a letter tab (A, B, C ...) in reading order and a one-line heading that names its sub-question.
3. Pick the panel kind from the content of that sub-question, not from variety:

| The sub-question is about | Panel kind | Draw |
| --- | --- | --- |
| What is made of what, which part belongs where | Tree or hierarchy | Boxes on levels with elbow connectors; the root at the top |
| What each part of one line means (a header, a command, a sentence, a config line) | Annotated line | The line in monospace, one `<text>` per token at a fixed `x`; a bracket under each part and a short note under the bracket |
| Which option does what, or is allowed | Status table | Rows with a light stripe; a result column with a symbol and a word (✓ allowed, ✗ not allowed) in the legend colors |
| How much, how full, which limit | Value bars | A track with a filled part and tick labels; the number next to the bar |
| When things happen, how long something lasts | Timeline | One axis with ticks and units; spans as bars, events as dots with a dashed line up to their label |
| A short process with a branch | Small flow | 2 to 5 boxes and arrows (`marker-end` with a `#id` marker); the branch outcomes in the legend colors |

A sheet usually mixes kinds. Two panels of the same kind are fine when the content calls for it.

## Layout

- **Canvas**: landscape, viewBox 1600 units wide, 650 to 1000 high. At 1600 wide one unit is one pixel at the sheet display width (1600 px), so the sizes below read directly. A 2400-wide canvas also works; multiply every size by 1.5.
- **Grid**: panels in rows of two or three, all panels in a row the same height, a 20 to 24 unit gap and margin. The title block and the legend take one cell or a strip:
  - 3 panels: one row of three, title block and legend in a strip below
  - 4 panels: two rows of two, title block and legend in a column on the right
  - 5 panels: three on top, two below, title block and legend stacked in the last cell
  - 6 panels: two rows of three, title block and legend in a strip below
- **Reading order**: left to right, then top to bottom. The letters follow it. Put the panel that sets up the terms (where things are, what they are) first.
- **Panel frame**: a white rect with a dark border, a dark square tab with the white letter at the top left, the heading next to it, and a rule under the heading. Group each panel in `<g transform="translate(x y)">` so its contents use local coordinates.
- **Inside a panel**: keep 16 to 24 units of padding. Keep text 10 or more units away from the panel border. The checker warns only about text outside the canvas, not outside a panel, so look for clipped text in the PNG.

## Text size

The checker runs with `--sheet` (display width 1600). The hard floor does not change: 11 units per 1200 units of canvas width, so 14.67 units on a 1600-wide canvas. That floor is above the 1600 px recommendation, so on a sheet the floor is the limit that counts. Sizes that pass on a 1600-wide canvas:

| Text | Size |
| --- | --- |
| Sheet title (title block) | 26 to 30 |
| Panel heading, tab letter | 20 to 22, bold |
| Labels, table cells, code | 16 to 18 |
| Detail lines, notes, axis labels, column headers | 15 (never below 14.67) |

## Long text

SVG does not wrap text. Break lines by hand:

- One line is one `<text>` or one `<tspan>` with the same `x` and a `dy` (22 to 26 units for 15 to 17 px text).
- Keep a line under about 30 CJK characters or 55 Latin characters at 15 to 16 px in a 500-wide panel. The checker estimates CJK at 1 em and other characters at 0.6 em; leave room, because real fonts vary.
- Put each token of a code or header line in its own `<text>` with an explicit `x`, so brackets and notes line up in every font.
- Prefer two short notes to one long one. A panel needs at most two lines of notes.

## Title block and legend

- **Title block**: a small framed table with labeled cells: the title (the topic, for example "一張圖看懂 HTTP 快取"), the source (where the facts come from: a spec, a doc, the conversation), and the date. Small grey labels above bold values.
- **Legend**: one legend for the whole sheet. Each color keeps one meaning in every panel (for example green "uses the cached copy", red "does not use the cache"). If a color would mean two things in two panels, change one panel. Every color that carries meaning has a swatch and a name; a short detail can follow the name.
- Also put the topic in the `<title>` element.

## Save and check

Save `sheet.svg` and `caption.md` in `out/diagram-explainer/<slug>/`. The caption is one line that tells the reader where to start and what the colors mean. Check with `python <skill folder>/scripts/svg_check.py sheet.svg --sheet`, render with `render_diagram.py`, and do the layout check (at most two rounds). On a sheet, also look for text clipped by a panel border, labels that crowd each other, a color used against the legend, and a panel with large empty space (make the panels shorter).

## Example

Three panels (tree, status table, timeline), a title block and one legend. It passes `scripts/svg_check.py --sheet` with no issues and no warnings, and renders with `scripts/render_diagram.py`.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 652" role="img" aria-labelledby="t">
  <title id="t">Git branches at a glance</title>
  <style>
    text { font-family: system-ui, -apple-system, "Segoe UI", "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif; fill: #1f2937; font-size: 16px; }
    .tab { font-size: 22px; font-weight: 700; fill: #ffffff; }
    .h { font-size: 20px; font-weight: 700; }
    .name { font-size: 17px; font-weight: 600; }
    .small { font-size: 15px; fill: #4b5563; }
    .mono { font-family: Consolas, "Courier New", monospace; font-size: 16px; }
    .frame { fill: #ffffff; stroke: #1f2937; stroke-width: 2; }
    .rule { stroke: #1f2937; stroke-width: 2; }
    .ref { fill: #dbeafe; stroke: #1d4ed8; stroke-width: 1.5; }
    .done { fill: #d4edda; stroke: #2e7d32; stroke-width: 1.5; }
    .work { fill: #fdecc8; stroke: #b45309; stroke-width: 1.5; }
    .wire { stroke: #4b5563; stroke-width: 2; fill: none; }
  </style>
  <rect width="1600" height="652" fill="#f3f4f6"/>

  <!-- A: tree -->
  <g transform="translate(24 24)">
    <rect class="frame" width="504" height="412"/>
    <rect width="44" height="44" fill="#1f2937"/>
    <text class="tab" x="22" y="30" text-anchor="middle">A</text>
    <text class="h" x="60" y="29">What a branch is</text>
    <line class="rule" x1="0" y1="44" x2="504" y2="44"/>
    <rect class="ref" x="172" y="80" width="160" height="60" rx="6"/>
    <text x="252" text-anchor="middle"><tspan class="name" x="252" y="106">HEAD</tspan><tspan class="small" x="252" dy="22">where you are</tspan></text>
    <path class="wire" d="M252 140 V180"/>
    <rect class="ref" x="152" y="180" width="200" height="60" rx="6"/>
    <text x="252" text-anchor="middle"><tspan class="name" x="252" y="206">feature</tspan><tspan class="small" x="252" dy="22">a name for one commit</tspan></text>
    <path class="wire" d="M252 240 V280"/>
    <rect class="done" x="152" y="280" width="200" height="60" rx="6"/>
    <text x="252" text-anchor="middle"><tspan class="name" x="252" y="306">Commit c3</tspan><tspan class="small" x="252" dy="22">points to its parent</tspan></text>
    <text class="small" x="24" y="368">A new commit moves the name forward.</text>
    <text class="small" x="24" y="390">The old commits do not change.</text>
  </g>

  <!-- B: status table -->
  <g transform="translate(548 24)">
    <rect class="frame" width="504" height="412"/>
    <rect width="44" height="44" fill="#1f2937"/>
    <text class="tab" x="22" y="30" text-anchor="middle">B</text>
    <text class="h" x="60" y="29">Where a change is</text>
    <line class="rule" x1="0" y1="44" x2="504" y2="44"/>
    <text class="small" x="20" y="82">State</text>
    <text class="small" x="200" y="82">Command that moves it on</text>
    <rect class="work" x="2" y="100" width="500" height="56"/>
    <text class="name" x="20" y="134">Modified</text>
    <text class="mono" x="200" y="134">git add file</text>
    <rect class="work" x="2" y="166" width="500" height="56"/>
    <text class="name" x="20" y="200">Staged</text>
    <text class="mono" x="200" y="200">git commit</text>
    <rect class="done" x="2" y="232" width="500" height="56"/>
    <text class="name" x="20" y="266">Committed</text>
    <text class="mono" x="200" y="266">git push</text>
    <text class="small" x="20" y="340">Only committed changes are on a branch.</text>
  </g>

  <!-- C: timeline -->
  <g transform="translate(1072 24)">
    <rect class="frame" width="504" height="412"/>
    <rect width="44" height="44" fill="#1f2937"/>
    <text class="tab" x="22" y="30" text-anchor="middle">C</text>
    <text class="h" x="60" y="29">A feature branch over time</text>
    <line class="rule" x1="0" y1="44" x2="504" y2="44"/>
    <path class="wire" d="M40 180 H464"/>
    <path class="wire" d="M120 180 L180 280 H340 L400 180"/>
    <circle cx="40" cy="180" r="10" fill="#2e7d32"/>
    <circle cx="120" cy="180" r="10" fill="#2e7d32"/>
    <circle cx="400" cy="180" r="10" fill="#2e7d32"/>
    <circle cx="180" cy="280" r="10" fill="#2e7d32"/>
    <circle cx="260" cy="280" r="10" fill="#2e7d32"/>
    <circle cx="340" cy="280" r="10" fill="#2e7d32"/>
    <text class="name" x="40" y="150">main</text>
    <text class="name" x="260" y="324" text-anchor="middle">feature: 3 commits</text>
    <text class="small" x="120" y="122" text-anchor="middle">branch</text>
    <text class="small" x="400" y="122" text-anchor="middle">merge</text>
    <text class="small" x="24" y="372">Merge joins the two lines again.</text>
  </g>

  <!-- Title block -->
  <g transform="translate(24 456)">
    <rect class="frame" width="760" height="172"/>
    <text class="small" x="20" y="32">Title</text>
    <text x="20" y="70" style="font-size: 28px; font-weight: 700">Git branches at a glance</text>
    <line class="rule" x1="0" y1="96" x2="760" y2="96"/>
    <line class="rule" x1="380" y1="96" x2="380" y2="172"/>
    <text class="small" x="20" y="124">Source</text>
    <text class="name" x="20" y="152">Pro Git, chapter 3</text>
    <text class="small" x="400" y="124">Date</text>
    <text class="name" x="400" y="152">2026-10-11</text>
  </g>

  <!-- Legend: one for the sheet -->
  <g transform="translate(804 456)">
    <rect class="frame" width="772" height="172"/>
    <text class="h" x="20" y="36">Legend: one meaning on the whole sheet</text>
    <rect class="ref" x="20" y="64" width="28" height="26"/>
    <text class="name" x="60" y="83">Name or pointer</text>
    <rect class="done" x="20" y="112" width="28" height="26"/>
    <text class="name" x="60" y="131">Saved in a commit</text>
    <rect class="work" x="400" y="64" width="28" height="26"/>
    <text class="name" x="440" y="83">Change not yet committed</text>
  </g>
</svg>
```

Caption: Start at A: a branch is only a name; green is everything already saved in a commit.
