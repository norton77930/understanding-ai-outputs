"""Scenes module fixture for tests/test_make_video.py (end-to-end, local only).

One function per storyboard scene id. Each takes the SceneContext from
video_helper and fills ctx.duration through ctx.beats().
"""

from manim import BLUE_E, DOWN, GREEN, RIGHT, YELLOW, Create, FadeIn, Rectangle, VGroup

STATE = {}


def s1(ctx):
    title = ctx.title("Halving a search")
    boxes = VGroup(*[Rectangle(width=1.0, height=1.0, color=BLUE_E, fill_opacity=0.35)
                     for _ in range(8)]).arrange(RIGHT, buff=0.15)
    ctx.layout.fit(boxes, ctx.layout.content)
    caption = ctx.caption("Eight boxes, one target")
    STATE.update(title=title, boxes=boxes, caption=caption)
    ctx.beats([
        (FadeIn(title), 1),
        (Create(boxes), 2),
        (FadeIn(caption), 1),
    ])


def s2(ctx):
    boxes = STATE["boxes"]
    mid = boxes[3]
    label = ctx.label("middle", mid, DOWN)
    caption = ctx.caption("Too small: drop the left half")
    ctx.beats([
        ([mid.animate.set_stroke(YELLOW, width=6), FadeIn(label)], 1),
        ([b.animate.set_opacity(0.15) for b in boxes[:4]], 1.5),
        (ctx.swap_caption(STATE["caption"], caption), 1),
    ])
    STATE.update(caption=caption, label=label)


def s3(ctx):
    boxes = STATE["boxes"]
    caption = ctx.caption("Each step halves the work", color=GREEN)
    ctx.beats([
        ([b.animate.set_fill(GREEN, opacity=0.6) for b in boxes[4:]], 1.5),
        (ctx.swap_caption(STATE["caption"], caption), 1),
        (None, 0.5),
    ])
