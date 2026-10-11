"""Scenes module fixture for the camera-move tests (end-to-end, local only).

Each scene records, on every frame, where its fixed elements (title, captions,
the burned narration) and one content object are. After ctx.beats() it raises
when a fixed element moved, when the content did not move, or when the camera
is not back home. A raise marks the scene "failed" in the preview JSON.
"""

import numpy as np
from manim import BLUE_E, RIGHT, YELLOW, FadeIn, Rectangle, VGroup

STATE = {}


def track(ctx, *mobjects):
    """Record each mobject's center on every frame. Returns the record lists."""
    records = []
    for mob in mobjects:
        seen = []
        mob.add_updater(lambda m, dt, seen=seen: seen.append(m.get_center().copy()))
        records.append(seen)
    return records


def drift(seen):
    """Largest distance from the first recorded center."""
    return max(float(np.linalg.norm(p - seen[0])) for p in seen)


def check(ctx, fixed, moving):
    for name, seen in fixed.items():
        if drift(seen) > 1e-6:
            raise AssertionError(f"{ctx.id}: fixed {name} moved by {drift(seen):.4f}")
    if drift(moving) < 0.5 * ctx.layout.text_scale:
        raise AssertionError(f"{ctx.id}: content did not move ({drift(moving):.4f})")
    if not ctx.camera.is_home:
        raise AssertionError(f"{ctx.id}: camera not home at scene end")


def burned(ctx):
    """The burned narration caption make_video.py added (short preset only)."""
    return [m for m in ctx.scene.mobjects if getattr(m, "_video_helper_fixed", False)
            and m not in STATE.values()]


def s1(ctx):
    title = ctx.title("A long row")
    cells = VGroup(*[Rectangle(width=1.0, height=1.0, color=BLUE_E, fill_opacity=0.35)
                     for _ in range(12)]).arrange(RIGHT, buff=0.15)
    ctx.layout.fit(cells, ctx.layout.content)
    caption = ctx.caption("Zoom on one cell")
    STATE.update(title=title, cells=cells, caption=caption)
    home = cells[2].get_center().copy()
    t_seen, c_seen, cell_seen = track(ctx, title, caption, cells[2])
    ctx.carry(cells, caption)
    ctx.beats([
        ([FadeIn(title), FadeIn(cells), FadeIn(caption)], 1),
        (ctx.camera.zoom(cells[2]), 1),
        (None, 1),
        (ctx.camera.restore(), 1),
    ])
    for mob in (title, caption, cells[2]):
        mob.clear_updaters()
    check(ctx, {"title": t_seen, "caption": c_seen}, cell_seen)
    if np.linalg.norm(cells[2].get_center() - home) > 1e-6:
        raise AssertionError("s1: restore did not bring the content home")


def s2(ctx):
    # The caption was made in s1 (another SceneContext); it must stay fixed too.
    cells, old = STATE["cells"], STATE["caption"]
    hud = ctx.camera.fix(ctx.text("HUD", color=YELLOW).move_to(ctx.layout.title.center))
    caption = ctx.caption("Pan along the row")
    others = burned(ctx)
    seen = track(ctx, old, caption, hud, cells[0], *others)
    ctx.beats([
        ([FadeIn(hud), ctx.camera.zoom(cells[:3], scale=2.0)], 1),
        (ctx.camera.pan(cells[-1]), 2),
        (ctx.swap_caption(old, caption), 1),
        (ctx.camera.restore(), 1),
    ])
    for mob in (old, caption, hud, cells[0], *others):
        mob.clear_updaters()
    fixed = {"old caption": seen[0], "new caption": seen[1], "HUD": seen[2]}
    fixed.update({f"burned {i}": s for i, s in enumerate(seen[4:])})
    check(ctx, fixed, seen[3])


def s3(ctx):
    # Left zoomed on purpose: the next scene's camera still starts home.
    cells = STATE["cells"]
    ctx.beats([(ctx.camera.zoom(cells[5:7]), 1), (None, 1)])
    if ctx.camera.is_home:
        raise AssertionError("s3: a zoom left the camera home")
