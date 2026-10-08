"""Scenes module fixture whose s2 raises (tests/test_make_video.py, local only).

s1 and s3 match scenes.py; s2 raises in the middle of an animation, the way
a broken scene does halfway through. s3 does not depend on anything from s2.
"""

from manim import BLUE_E, GREEN, RIGHT, Create, FadeIn, Rectangle, VGroup

STATE = {}


def s1(ctx):
    title = ctx.title("Halving a search")
    boxes = VGroup(*[Rectangle(width=1.0, height=1.0, color=BLUE_E, fill_opacity=0.35)
                     for _ in range(8)]).arrange(RIGHT, buff=0.15)
    ctx.layout.fit(boxes, ctx.layout.content)
    caption = ctx.caption("Eight boxes, one target")
    STATE.update(title=title, boxes=boxes, caption=caption)
    ctx.carry(boxes, caption)
    ctx.beats([(FadeIn(title), 1), (Create(boxes), 2), (FadeIn(caption), 1)])


def s2(ctx):
    label = ctx.label("half drawn", STATE["boxes"][3])

    def explode(mob, dt):
        if ctx.scene.renderer.time > ctx.start + 0.5:
            raise ValueError("deliberate failure in s2")

    label.add_updater(explode)
    ctx.beats([(FadeIn(label), 1)])  # raises in the middle of this animation


def s3(ctx):
    boxes = STATE["boxes"]
    caption = ctx.caption("Each step halves the work", color=GREEN)
    ctx.beats([
        ([b.animate.set_fill(GREEN, opacity=0.6) for b in boxes[4:]], 1.5),
        (ctx.swap_caption(STATE["caption"], caption), 1),
        (None, 0.5),
    ])
