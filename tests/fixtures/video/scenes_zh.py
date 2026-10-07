"""zh-TW scenes module fixture for tests/test_make_video.py (end-to-end, local only).

Text goes through ctx.title/ctx.caption/ctx.label, so it uses the Traditional
Chinese font that video_helper picks for zh-TW.
"""

from manim import BLUE_E, DOWN, RIGHT, YELLOW, Create, FadeIn, Rectangle, VGroup

STATE = {}


def s1(ctx):
    title = ctx.title("二分搜尋")
    boxes = VGroup(*[Rectangle(width=1.0, height=1.0, color=BLUE_E, fill_opacity=0.35)
                     for _ in range(8)]).arrange(RIGHT, buff=0.15)
    ctx.layout.fit(boxes, ctx.layout.content)
    caption = ctx.caption("八個格子，找一個數字")
    STATE.update(boxes=boxes, caption=caption)
    ctx.beats([
        (FadeIn(title), 1),
        (Create(boxes), 2),
        (FadeIn(caption), 1),
    ])


def s2(ctx):
    boxes = STATE["boxes"]
    mid = boxes[3]
    label = ctx.label("中間", mid, DOWN)
    caption = ctx.caption("太小：丟掉左邊一半")
    ctx.beats([
        ([mid.animate.set_stroke(YELLOW, width=6), FadeIn(label)], 1),
        ([b.animate.set_opacity(0.15) for b in boxes[:4]], 1.5),
        (ctx.swap_caption(STATE["caption"], caption), 1),
    ])
