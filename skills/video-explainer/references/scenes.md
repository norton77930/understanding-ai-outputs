# Writing scenes

The scenes module is a Python file with one function per storyboard scene id. `make_video.py` renders all scenes in order, inside one ManimCE scene, and calls each function with a `SceneContext` (`ctx`). The helper `scripts/video_helper.py` owns the layout grid, safe area, caption area and timing. Scene code is free inside those rails.

## Hard rules

1. **ManimCE 0.21 only.** Import from `manim`. Never use ManimGL (`manimlib`) APIs. Mixing the two is a known failure. Do not use these ManimGL names: `from manimlib import *`, `ShowCreation` (use `Create`), `TexText`, `InteractiveScene`, `self.embed()`, `self.camera.frame` (the scene is a plain `Scene`; use `ctx.camera` for camera moves, see "Camera moves").
2. **`Text` only, no LaTeX, unless the doctor reports LaTeX.** Do not use `MathTex`, `Tex`, `Matrix`, `DecimalNumber`, `Integer` or axis numbers and labels (`include_numbers`, `get_axis_labels`). They need a LaTeX install (`latex` and `dvisvgm`). Write formulas as plain text, for example `ctx.text("y = x²")`. Exception: when `doctor.py` reports `capabilities.latex.available` as true, `MathTex`, `Tex` and `DecimalNumber` are allowed (Example 6). When it is false, this rule stays as written.
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
- **Counting numbers.** Show a value that changes as a number that counts up or down: a `ValueTracker` and an `always_redraw` that rebuilds a `ctx.text(...)`. Do not use `DecimalNumber` or `Integer` (they need LaTeX), unless the doctor reported LaTeX (Example 6). Example 5 shows the `Text` way.

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

## Example 6: en, a formula and a counting number (only when doctor reports LaTeX)

Use this only when `doctor.py` reports `capabilities.latex.available` as true. `MathTex` and `DecimalNumber` run `latex` and `dvisvgm`, so they fail on a machine without LaTeX. When it is false, use the fallback below. `s1` shows the formula and carries it. `s2` fills in the numbers and counts `c²` up to 25.

```python
from manim import DOWN, YELLOW, ChangeDecimalToValue, DecimalNumber, FadeIn, MathTex, VGroup, Write

STATE = {}
COLORS = {"formula": YELLOW}


def s1(ctx):
    title = ctx.title("Pythagoras")
    formula = MathTex(r"a^2 + b^2 = c^2", color=COLORS["formula"])
    ctx.layout.fit(formula, ctx.layout.content)
    formula.move_to(ctx.layout.content.point(0.5, 0.7))  # leave room below for s2
    caption = ctx.caption("Two short sides, one long side")
    STATE.update(formula=formula, caption=caption)
    ctx.carry(formula, caption)  # s2 continues this formula
    ctx.beats([(FadeIn(title), 1), (Write(formula), 2), (FadeIn(caption), 1)])


def s2(ctx):
    formula = STATE["formula"]
    result = VGroup(MathTex(r"3^2 + 4^2 = ", color=COLORS["formula"]),
                    DecimalNumber(0, num_decimal_places=0, color=COLORS["formula"]))
    result.arrange(buff=0.2)
    ctx.layout.fit(result, ctx.layout.content)
    result.next_to(formula, DOWN, buff=0.6 * ctx.layout.text_scale)
    ctx.layout.keep_inside(result)
    caption = ctx.caption("Three and four give twenty-five")
    ctx.beats([
        (FadeIn(result), 1),
        (ChangeDecimalToValue(result[1], 25), 2),
        (ctx.swap_caption(STATE["caption"], caption), 1),
    ])
    STATE["caption"] = caption
```

### Example 6 fallback: the same two scenes with `Text` only

Use this when `latex.available` is false. The formula is plain text, and the number counts with a `ValueTracker` as in Example 5.

```python
from manim import DOWN, YELLOW, FadeIn, ValueTracker, always_redraw

STATE = {}
COLORS = {"formula": YELLOW}


def s1(ctx):
    title = ctx.title("Pythagoras")
    formula = ctx.text("a² + b² = c²", size=64, color=COLORS["formula"])
    ctx.layout.fit(formula, ctx.layout.content)
    formula.move_to(ctx.layout.content.point(0.5, 0.7))  # leave room below for s2
    caption = ctx.caption("Two short sides, one long side")
    STATE.update(formula=formula, caption=caption)
    ctx.carry(formula, caption)
    ctx.beats([(FadeIn(title), 1), (FadeIn(formula), 2), (FadeIn(caption), 1)])


def s2(ctx):
    formula = STATE["formula"]
    total = ValueTracker(0)
    anchor = formula.get_bottom() + DOWN * 1.0 * ctx.layout.text_scale
    result = always_redraw(lambda: ctx.text(f"3² + 4² = {round(total.get_value())}", size=64,
                                            color=COLORS["formula"]).move_to(anchor))
    caption = ctx.caption("Three and four give twenty-five")
    ctx.beats([
        (FadeIn(result), 1),
        (total.animate.set_value(25), 2),
        (ctx.swap_caption(STATE["caption"], caption), 1),
    ])
    STATE["caption"] = caption
```

## Camera moves

A camera move zooms in on a detail or pans along a long object, then comes back. It is a 3Blue1Brown hallmark. Use it only when a detail is too small to read at full view, or an object is too long to show at a readable size. Use at most two moves per scene, then `ctx.camera.restore()`.

The helper moves the content, not the scene camera (the scene stays a plain `Scene`). Titles, captions, the burned narration and anything you pass to `ctx.camera.fix()` stay where they are and stay readable. Each move is an animation: put it in `ctx.beats()` like any other, so the helper timing stays exact.

| Call | Returns |
| --- | --- |
| `ctx.camera.zoom(target, scale=None, buff=None)` | Animation: fit `target` (a mobject, or an `Area` in scene-start coordinates) into the content area, centered. `scale` sets the zoom factor instead of fitting. |
| `ctx.camera.pan(target)` | Animation: move `target` to the center of the content area at the current zoom. |
| `ctx.camera.restore()` | Animation: bring all content back to where it was at the scene start. |
| `ctx.camera.fix(mob)` | Keeps `mob` fixed on screen during camera moves (a HUD). Returns `mob`. `ctx.title` and `ctx.caption` are fixed already. |
| `ctx.camera.is_home` | `True` when the camera is at its scene-start state. |

Rules:

- **One move per beat.** Give each move its own beat. Do not animate the moving content in the same beat. Fading in a fixed object (a caption or a HUD) in the same beat is fine.
- **A move takes what is on screen when it starts.** Show the objects before the move. An object that appears after a zoom is drawn at its own size and place, not zoomed. Show labels before the move or after the restore.
- **End the scene at home.** End with `ctx.camera.restore()`. Each scene's camera starts at home, and a carried object keeps the size and place it has at the scene end.
- **Neighbors may leave the frame.** Zoomed content can pass beyond the frame edge or under the title and caption. Zoom on a part of a row or a line, so the neighbors stay in the content band.
- `always_redraw` objects redraw at their own coordinates and do not follow a move. Do not zoom on a counting number.

## Example 7: en, zoom on a detail and pan along a row (camera moves)

`s1` zooms in to read one small cell and comes back. `s2` zooms in on the start of the row, pans to the end and comes back. The title and the captions stay fixed and readable. In a portrait frame the row is narrow, so the zoom matters more.

```python
from manim import BLUE, RIGHT, YELLOW, FadeIn, Rectangle, VGroup

STATE = {}
COLORS = {"cell": BLUE, "focus": YELLOW}
VALUES = [4, 9, 15, 16, 23, 42, 8, 11, 30, 7, 19, 27]


def cell(ctx, value, color):
    box = Rectangle(width=1.0, height=1.0, color=color, fill_opacity=0.3)
    return VGroup(box, ctx.text(str(value), size=24).move_to(box))


def s1(ctx):
    title = ctx.title("A long row of cells")
    cells = VGroup(*[cell(ctx, v, COLORS["focus"] if i == 4 else COLORS["cell"])
                     for i, v in enumerate(VALUES)]).arrange(RIGHT, buff=0.1)
    ctx.layout.fit(cells, ctx.layout.content)
    caption = ctx.caption("Zoom in to read one cell")
    STATE.update(cells=cells, caption=caption)
    ctx.carry(cells, caption)
    ctx.beats([
        ([FadeIn(title), FadeIn(cells), FadeIn(caption)], 1),
        (ctx.camera.zoom(cells[4]), 1),  # move 1: the detail fills the content area
        (None, 1),
        (ctx.camera.restore(), 1),  # back home before the scene ends
    ])


def s2(ctx):
    cells = STATE["cells"]
    caption = ctx.caption("Pan from start to end")
    ctx.beats([
        (ctx.swap_caption(STATE["caption"], caption), 1),
        (ctx.camera.zoom(cells[:3]), 1),  # move 1: the start of the row
        (ctx.camera.pan(cells[-3:]), 2),  # move 2: slide to the end at the same zoom
        (ctx.camera.restore(), 1),
    ])
    STATE["caption"] = caption
```
