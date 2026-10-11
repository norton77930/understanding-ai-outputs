# Drawing SVG by hand

## When to draw SVG

Draw SVG when the idea has a shape that boxes and arrows cannot show:

- **Concept**: the parts of an idea and how they relate, where the layout itself carries meaning (layers, a stack, a cycle drawn as a ring).
- **Spatial relation**: what sits where, what is inside what, what is near or far.
- **Proportion**: how full, how much of the whole (a context window that fills up, a budget split, a countdown bar).
- **Timeline**: events and spans on a time axis.

Use Mermaid for steps and arrows: a flow, a sequence of messages, the states of one thing. Mermaid is easier to edit and renders on GitHub as code. If the user names a tool, use that tool.

## Design

There is no template. Design each SVG for its topic and draw the idea itself: a bar that fills up for a proportion, parts placed where they are for a spatial relation, an axis with marks for a timeline. The checker is a floor (safe, readable); it does not judge the design. Keep the same discipline as the Mermaid path: one question per diagram, two-line labels, STE-principle wording, colors with one fixed meaning and a legend.

## Required structure

- **Root**: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 W H">`. A viewBox lets the image scale. Leave out `width` and `height`, or set them equal to W and H.
- **Width**: about 800 units is a good canvas width. The image is usually shown about 800 px wide; a wider canvas shrinks every text (see the font-size rules below).
- **`<title>`** as the first child: the topic in one line (screen readers and tooltips use it). Also draw the title as visible text at the top.
- **Background**: a first `<rect>` that fills the whole viewBox with an opaque color, for example `<rect width="800" height="300" fill="#ffffff"/>`.
- **Fonts**: one `<style>` rule with a font stack that has CJK fallbacks: `font-family: system-ui, -apple-system, "Segoe UI", "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif`. Do not load web fonts.
- **Labels**: a name line and, where a detail helps, a detail line in a smaller size: two `<tspan>` elements with the same `x` and a `dy` on the second. Name line about 5 words or 10 CJK characters, detail line about 8 words or 16 CJK characters.
- **Colors**: each color has one meaning. Put the text color on the element or class; dark text on light fills. Draw a legend in the image for every color that carries meaning.
- **Text positions**: use `x`, `y`, `text-anchor` and `translate()` on groups. Avoid `rotate`, `scale` and `matrix` on text when you can: the checker cannot place such text.
- **Self-contained**: no `<script>`, no `on...` attributes, no `<foreignObject>`, no links or `url(...)` to other files or the web, no `@import`. Use `#id` references (`url(#gradient)`, `href="#shape"`) and `data:image/...` only.

## Example

A proportion (a timer bar). It passes `scripts/svg_check.py` and renders with `scripts/render_diagram.py`.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 300" role="img" aria-labelledby="t">
  <title id="t">How long a cached prompt stays warm</title>
  <style>
    text { font-family: system-ui, -apple-system, "Segoe UI", "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif; fill: #1f2937; }
    .title { font-size: 24px; font-weight: 700; }
    .name { font-size: 16px; font-weight: 600; }
    .detail { font-size: 13px; fill: #4b5563; }
  </style>
  <rect width="800" height="300" fill="#ffffff"/>
  <text class="title" x="40" y="48">How long a cached prompt stays warm</text>
  <g transform="translate(40 90)">
    <rect width="720" height="56" rx="8" fill="#f3f4f6" stroke="#9ca3af"/>
    <rect width="480" height="56" rx="8" fill="#d4edda" stroke="#2e7d32"/>
    <text x="240" text-anchor="middle">
      <tspan class="name" x="240" y="24" style="fill: #1b3d1f">Warm: 0 to 5 min</tspan>
      <tspan class="detail" x="240" dy="20" style="fill: #1b3d1f">each hit resets the timer</tspan>
    </text>
    <text class="name" x="600" y="34" text-anchor="middle">Expired</text>
    <text class="detail" x="0" y="80">0 min</text>
    <text class="detail" x="480" y="80" text-anchor="middle">5 min</text>
  </g>
  <g transform="translate(40 230)">
    <rect width="18" height="18" fill="#d4edda" stroke="#2e7d32"/>
    <text class="detail" x="28" y="14">Cache hit: cheap and fast</text>
    <rect x="240" width="18" height="18" fill="#f3f4f6" stroke="#9ca3af"/>
    <text class="detail" x="268" y="14">Cache miss: full price</text>
  </g>
</svg>
```

Caption: Look at the green part: every cache hit inside 5 minutes resets the timer.

A CSS rule beats a `fill` attribute. Here `text { fill: ... }` sets the default text color, so the labels on the green bar set their color with `style="fill: ..."`, not with `fill="..."`.

## Checker rules in plain words

`scripts/svg_check.py` fails the check (exit 1) when:

- the file is not well-formed XML, or the root is not `<svg>` with the SVG `xmlns`
- it has a DOCTYPE or ENTITY declaration (rejected before parsing)
- it has no usable `viewBox`
- it has a `<script>`, an `on...` attribute or a `<foreignObject>`
- it points outside the file: `href` other than `#...` or `data:image/...`, `url(...)` to anything else, or any `@import`
- no opaque shape covers the whole viewBox (no background)
- a text has less than 4.5:1 contrast against the color under it, when both colors resolve
- a text is smaller than the font-size floor

Font size has two tiers:

- **Floor** (fails): `11 × max(1, viewBox width / 1200)` units. Below it, text is too small on any normal screen. Hand-written diagrams that readers rated well stay above it.
- **Recommendation** (warning `small-text-advisory`): `12 × max(1, viewBox width / 800)` units. 12 px is comfortable text, and 800 px is a normal display width (a chat reply, a GitHub README, a doc page). An 800-wide canvas should use 12 or more; a 1600-wide canvas should use 24 or more, because it is shown at half size. Follow the recommendation when the layout allows.

It warns (no failure) about text below the recommended size, text that probably falls outside the viewBox, text it cannot place (a transform other than `translate`), colors it cannot read (gradients, `hsl()`, unknown names) and files over about 200 KB. The estimates are rough: CJK characters count 1 em wide, other characters 0.6 em. Check every warning in the rendered PNG. Flags and JSON fields are in `checks.md`.

## Light and dark hosts

The same SVG file shows on light pages (GitHub light, most docs) and dark pages (GitHub dark, dark chat apps). Without its own background, dark text disappears on a dark page. So:

- Always paint the opaque background rect. The image then looks the same on every host.
- Pick text colors against that background and against the fill under each label, not against the page.
- Do not use `@media (prefers-color-scheme: dark)` in the SVG. Hosts apply it differently, the checker ignores it, and the PNG shows only the light version.
- Do not rely on color alone: add a label or a legend entry for every color that carries meaning.
