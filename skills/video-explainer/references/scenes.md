# Writing scenes

The scenes module is a Python file with one function per storyboard scene id. `make_video.py` renders all scenes in order, inside one ManimCE scene, and calls each function with a `SceneContext` (`ctx`). The helper `scripts/video_helper.py` owns the layout grid, safe area, caption area and timing. Scene code is free inside those rails.

## Hard rules

1. **ManimCE 0.21 only.** Import from `manim`. Never use ManimGL (`manimlib`) APIs. Mixing the two is a known failure. Do not use these ManimGL names: `from manimlib import *`, `ShowCreation` (use `Create`), `TexText`, `InteractiveScene`, `self.embed()`, `self.camera.frame` (no camera moves: the scene is a plain `Scene`).
2. **`Text` only, no LaTeX.** Do not use `MathTex`, `Tex`, `Matrix`, `DecimalNumber`, `Integer` or axis numbers and labels (`include_numbers`, `get_axis_labels`). They need a LaTeX install, which v1 does not support. Write formulas as plain text, for example `ctx.text("y = x²")`.
3. **Make all text with the helper:** `ctx.text`, `ctx.title`, `ctx.caption`, `ctx.label`. They use the font picked for the narration language (a Traditional Chinese font for zh-TW) and scale with the frame. A bare `Text(...)` can show empty boxes for Chinese.
4. **Place with layout areas, not fixed coordinates.** Use `ctx.layout.title`, `.content`, `.caption`, `.grid()`, `.fit()` and `.keep_inside()`. Do not write `LEFT * 6` or `UP * 3.5`: the `short` preset frame is 4.5 units wide, not 14.2.
5. **Time everything with `ctx.beats()`.** It fills exactly `ctx.duration`, the measured narration length. Do not call `ctx.scene.play()` or `ctx.scene.wait()` with your own run times.
6. **Change a caption with `ctx.swap_caption(old, new)`.** A cross-fade at one position leaves a ghost of the old text.
7. **The helper clears what you do not carry.** When a scene starts, the helper fades out everything the previous scene left on screen (0.3 s, taken from the new scene's time). This is the safe default. To reuse objects in the next scene, call `ctx.carry(obj, ...)` in the scene that leaves them, and keep them in a module-level dict. A carried part keeps its whole on-screen group. `ctx.carry()` with no arguments keeps everything. Carry again in each scene that passes an object on. See "Style" below for when to carry.
8. **Never draw in `layout.narration`.** The `short` preset burns the narration captions into that band. In other presets it has zero height.

## Style (every mode)

Aim for a 3Blue1Brown-like video: the viewer sees one idea develop, not a slide deck.

- **Continuity.** When the next scene continues the idea, `ctx.carry()` its objects and change them there with `Transform` or `.animate` (move, recolor, reshape). Keep a clean screen for a new idea. Example 4 shows this.
- **One color per concept.** Give each concept one color for the whole video, in one module-level dict (for example `COLORS = {"value": BLUE, "focus": YELLOW}`). Do not reuse a concept's color for another concept.
- **Counting numbers.** Show a value that changes as a number that counts up or down: a `ValueTracker` and an `always_redraw` that rebuilds a `ctx.text(...)`. Do not use `DecimalNumber` or `Integer` (they need LaTeX). Example 5 shows this.

## Helper API

`ctx` attributes: `scene` (the ManimCE scene), `id`, `narration`, `lang`, `font`, `duration` (seconds to fill), `speech_seconds`, `layout`.

| Call | Returns |
| --- | --- |
| `ctx.text(s, size=30, color=WHITE, **kw)` | `Text` in the scene font, sized for the frame. Not added. |
| `ctx.title(s, color=WHITE)` | Title fitted into the title area. Not added. |
| `ctx.caption(s, color=WHITE)` | Caption fitted into the caption area. Not added. |
| `ctx.label(s, target, direction=DOWN, buff=0.2)` | Label next to `target`, kept inside the safe area. Not added. |
| `ctx.swap_caption(old, new)` | Animation: fade `old` out, then fade `new` in. `old` can be `None`. |
| `ctx.beats(steps)` | Plays `steps`, a list of `(animation, weight)`. The animation can be one animation, a list played together, or `None` (wait). The scene time left is split by weight, then a 0.4 s still hold ends the scene. |
| `ctx.carry(*mobjects)` | Keeps these objects on screen into the next scene. With no arguments, keeps everything on screen at the scene end. |
| `ctx.layout.title`, `.content`, `.caption`, `.safe`, `.narration` | `Area` with `left`, `right`, `bottom`, `top`, `width`, `height`, `center`, `point(fx, fy)`. |
| `ctx.layout.grid(rows, cols, area=None)` | `rows` x `cols` list of `Area` cells (default: content), top row first. |
| `ctx.layout.fit(mob, area, buff=0)` | Scales `mob` down (never up) to fit `area` and centers it there. |
| `ctx.layout.keep_inside(mob, area=None)` | Shifts `mob` into `area` (default: safe area). |
| `ctx.layout.frame_width`, `.frame_height` | Frame size in scene units. Portrait when width < height. |
| `ctx.layout.text_scale` | Font and spacing factor for the current frame. |

Each `ctx.beats()` call ends the scene. Use one call per scene, as the last statement.

## Tips for a clean layout check

- Build a group first, then call `ctx.layout.fit(group, area)` once. Fit after you arrange, not before.
- For the `short` preset, stack vertically. Check `portrait = ctx.layout.frame_width < ctx.layout.frame_height` and switch `arrange(RIGHT)` to `arrange(DOWN)` or use `arrange_in_grid`.
- Keep 1 title, at most 1 caption and about 3 to 8 visual elements per scene.
- Use short on-screen text. The narration carries the sentences.
- Multiply hand-set sizes and buffers by `ctx.layout.text_scale`.

## Example 1: zh-TW, a row that halves

Storyboard scenes `s1` and `s2`. The row wraps to two rows in a portrait frame.

```python
from manim import BLUE_E, UP, YELLOW, Create, FadeIn, Rectangle, VGroup

STATE = {}
VALUES = [3, 8, 12, 17, 23, 31, 37, 42]


def cell(ctx, value):
    box = Rectangle(width=1.0, height=1.0, color=BLUE_E, fill_opacity=0.3)
    return VGroup(box, ctx.text(str(value)).move_to(box))


def s1(ctx):
    portrait = ctx.layout.frame_width < ctx.layout.frame_height
    title = ctx.title("二分搜尋")
    cells = VGroup(*[cell(ctx, v) for v in VALUES])
    cells.arrange_in_grid(rows=2 if portrait else 1, buff=0.15)
    ctx.layout.fit(cells, ctx.layout.content)
    caption = ctx.caption("八個排好的數字")
    STATE.update(cells=cells, caption=caption)
    ctx.carry(cells, caption)  # the title fades out when s2 starts
    ctx.beats([(FadeIn(title), 1), (Create(cells), 2), (FadeIn(caption), 1)])


def s2(ctx):
    cells = STATE["cells"]
    middle = cells[3]
    label = ctx.label("中間", middle, UP)  # DOWN would cover the second row in 9:16
    caption = ctx.caption("太小：丟掉左邊一半")
    ctx.beats([
        ([middle[0].animate.set_stroke(YELLOW, width=6), FadeIn(label)], 1),
        ([c.animate.set_opacity(0.15) for c in cells[:4]], 1.5),
        (ctx.swap_caption(STATE["caption"], caption), 1),
    ])
    STATE["caption"] = caption
```

## Example 2: en, a packet that travels (works in 16:9 and 9:16)

The nodes go left to right in a landscape frame and top to bottom in a portrait frame.

```python
from manim import (BLUE, DOWN, LEFT, RIGHT, UP, YELLOW, Arrow, Dot, FadeIn, GrowArrow,
                   RoundedRectangle, VGroup)

STATE = {}


def node(ctx, name, area):
    label = ctx.text(name)
    pad = 0.5 * ctx.layout.text_scale
    box = RoundedRectangle(corner_radius=0.15, width=label.width + pad,
                           height=label.height + pad, color=BLUE)
    return ctx.layout.fit(VGroup(box, label.move_to(box)), area, buff=0.2)


def s1(ctx):
    portrait = ctx.layout.frame_width < ctx.layout.frame_height
    grid = ctx.layout.grid(3, 1) if portrait else ctx.layout.grid(1, 3)
    areas = [row[0] for row in grid] if portrait else grid[0]
    nodes = VGroup(*[node(ctx, n, a) for n, a in zip(["Browser", "DNS", "Server"], areas)])
    # Arrow from edge to edge, so it stays straight in both orientations.
    out_edge, in_edge = (DOWN, UP) if portrait else (RIGHT, LEFT)
    arrows = VGroup(*[Arrow(a.get_critical_point(out_edge), b.get_critical_point(in_edge),
                            buff=0.1) for a, b in zip(nodes[:-1], nodes[1:])])
    title = ctx.title("Life of a request")
    caption = ctx.caption("Three stops")
    # The packet waits beside a node, never on top of its label.
    STATE.update(nodes=nodes, caption=caption, side=RIGHT if portrait else UP)
    ctx.carry(nodes, arrows, caption)
    ctx.beats([
        (FadeIn(title), 1),
        ([FadeIn(n) for n in nodes], 1.5),
        ([GrowArrow(a) for a in arrows], 1),
        (FadeIn(caption), 1),
    ])


def s2(ctx):
    browser, dns, server = STATE["nodes"]
    side = STATE["side"]
    packet = Dot(color=YELLOW, radius=0.12 * ctx.layout.text_scale).next_to(browser, side)
    caption = ctx.caption("Name in, address out")
    ctx.beats([
        (FadeIn(packet), 0.5),
        (packet.animate.next_to(dns, side), 1.5),
        (ctx.swap_caption(STATE["caption"], caption), 1),
        (packet.animate.next_to(server, side), 1.5),
    ])
    STATE.update(caption=caption, packet=packet)
```

## Example 3: en, a ball rolling down a curve

`Axes` and `plot` need no LaTeX as long as you add no numbers or axis labels.

```python
from manim import BLUE, YELLOW, Axes, Create, Dot, FadeIn, VGroup

STATE = {}


def s1(ctx):
    title = ctx.title("Gradient descent")
    axes = Axes(x_range=[-3, 3, 1], y_range=[0, 9, 3], tips=False)
    curve = axes.plot(lambda x: x * x, color=BLUE)
    ctx.layout.fit(VGroup(axes, curve), ctx.layout.content)
    ball = Dot(axes.c2p(-2.5, 6.25), color=YELLOW, radius=0.12 * ctx.layout.text_scale)
    caption = ctx.caption("Start high on the slope")
    STATE.update(axes=axes, ball=ball, caption=caption)
    ctx.carry(axes, curve, ball, caption)
    ctx.beats([(FadeIn(title), 1), ([Create(axes), Create(curve)], 2),
               ([FadeIn(ball), FadeIn(caption)], 1)])


def s2(ctx):
    axes, ball = STATE["axes"], STATE["ball"]
    caption = ctx.caption("Small steps go downhill")
    steps = [(ball.animate.move_to(axes.c2p(x, x * x)), 1) for x in (-1.6, -0.9, -0.4, 0)]
    ctx.beats([(ctx.swap_caption(STATE["caption"], caption), 1), *steps])
    STATE["caption"] = caption
```

## Example 4: en, continuity: the same bars, sorted (carry + Transform)

Scene `s2` continues the idea of `s1`, so `s1` carries the bars and `s2` transforms them in place. The title is not carried, so it fades out. Each bar keeps its color and height: the viewer sees the same values move.

```python
from manim import BLUE, DOWN, RIGHT, YELLOW, FadeIn, Rectangle, Transform, VGroup

STATE = {}
VALUES = [5, 2, 7, 1, 6, 3]
COLORS = {"value": BLUE, "focus": YELLOW}  # one color per concept, for the whole video


def s1(ctx):
    title = ctx.title("Sorting")
    bars = VGroup(*[Rectangle(width=0.6, height=0.5 * v, color=COLORS["value"],
                              fill_opacity=0.6) for v in VALUES])
    bars.arrange(RIGHT, buff=0.25, aligned_edge=DOWN)
    ctx.layout.fit(bars, ctx.layout.content)
    caption = ctx.caption("Six values, out of order")
    STATE.update(bars=bars, caption=caption)
    ctx.carry(bars, caption)  # s2 continues this idea
    ctx.beats([(FadeIn(title), 1), (FadeIn(bars), 2), (FadeIn(caption), 1)])


def s2(ctx):
    bars = STATE["bars"]
    slots = [bar.get_bottom() for bar in bars]  # left to right
    order = sorted(range(len(VALUES)), key=VALUES.__getitem__)
    target = bars.copy()
    for rank, i in enumerate(order):
        target[i].move_to(slots[rank], aligned_edge=DOWN)  # bar i goes to its sorted slot
    target[order[0]].set_color(COLORS["focus"])  # the smallest value
    caption = ctx.caption("Same values, now in order")
    ctx.beats([(Transform(bars, target), 2), (ctx.swap_caption(STATE["caption"], caption), 1)])
    STATE["caption"] = caption
```

## Example 5: zh-TW, a number that counts down (Text and an updater)

A `ValueTracker` holds the value. `always_redraw` rebuilds the `Text` from it on every frame, so the number counts while the tracker animates. `s1` carries the number and the tracker, and `s2` keeps counting.

```python
from manim import YELLOW, FadeIn, ValueTracker, always_redraw

STATE = {}
COLORS = {"count": YELLOW}


def s1(ctx):
    title = ctx.title("還剩幾個？")
    left = ValueTracker(16)
    anchor = ctx.layout.content.center
    count = always_redraw(lambda: ctx.text(str(round(left.get_value())), size=96,
                                           color=COLORS["count"]).move_to(anchor))
    caption = ctx.caption("十六個數字")
    STATE.update(left=left, count=count, caption=caption)
    ctx.carry(count, left, caption)  # s2 keeps counting the same number
    ctx.beats([([FadeIn(title), FadeIn(count)], 1), (FadeIn(caption), 1), (None, 1)])


def s2(ctx):
    left = STATE["left"]
    caption = ctx.caption("每次少一半")
    ctx.beats([
        (ctx.swap_caption(STATE["caption"], caption), 1),
        *[(left.animate.set_value(n), 1) for n in (8, 4, 2, 1)],
    ])
    STATE["caption"] = caption
```
