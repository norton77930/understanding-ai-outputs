"""Helper for video-explainer scenes modules (ManimCE 0.21, Text by default; LaTeX only when doctor reports it).

A scenes module has one function per storyboard scene id. make_video.py calls
each function with a SceneContext:

    def s1(ctx):
        title = ctx.title("Binary search")
        boxes = ctx.layout.fit(VGroup(...).arrange(RIGHT), ctx.layout.content)
        ctx.beats([(FadeIn(title), 1), (Create(boxes), 2), (None, 1)])

Rules the helper keeps for you:
- Layout areas (safe, title, content, caption, narration) are fractions of the frame, so
  the same code works at 16:9 and 9:16.
- ctx.beats() fills exactly ctx.duration (the measured narration length) and
  ends with a short still hold, so frames sampled near the scene end are settled.
- ctx.swap_caption() fades the old caption out before the new one fades in
  (a cross-fade at one position ghosts).
- fallback_scene() draws a title and bullets from the narration for a scene
  the storyboard marks "fallback": true (make_video.py calls it).
- ctx.camera zooms and pans the content (opt-in, see Camera). Titles,
  captions and the burned narration stay fixed; the helper timing stays exact.
- Each scene starts on a clean screen: clear_previous() fades out what the
  previous scene left (make_video.py calls it). To keep objects for the next
  scene, call ctx.carry(obj, ...) in the scene that made them (ctx.carry()
  with no arguments keeps everything). Keep the carried objects in a
  module-level dict so the next scene can use them.
"""

import re
import textwrap
from dataclasses import dataclass

import numpy as np
from manim import (DOWN, LEFT, ORIGIN, RIGHT, WHITE, Animation, FadeIn, FadeOut, Group,
                   LaggedStart, Mobject, Paragraph, Succession, Text, VGroup)

import doctor  # stdlib only; owns the Traditional Chinese font order

# Still time at the end of every ctx.beats() call (seconds). make_video.py
# samples preview frames 0.2 s before the scene end, inside this hold.
HOLD_SECONDS = 0.4

# Fade-out of the previous scene's objects at the start of a scene (seconds;
# at most a quarter of the scene). The scene's beats share the rest.
CLEAR_SECONDS = 0.3

# Same order as the doctor's report (one source of truth: doctor.FONTS).
ZH_FONTS = tuple(name for name, _, _ in doctor.FONTS)
LATIN_FONTS = ("Segoe UI", "Helvetica Neue", "DejaVu Sans", "Noto Sans")

# Font sizes for a frame whose shorter side is 8 Manim units (16:9 default).
TITLE_SIZE = 40
TEXT_SIZE = 30
CAPTION_SIZE = 28
NARRATION_SIZE = 40  # burned-in narration captions (short preset): larger text


def pick_font(lang):
    """Return the first installed font for lang, or "" for the Manim default."""
    import manimpango

    installed = set(manimpango.list_fonts())
    wanted = ZH_FONTS if lang.lower().startswith("zh") else LATIN_FONTS
    return next((f for f in wanted if f in installed), "")


def allocate(duration, weights, hold=HOLD_SECONDS):
    """Split duration - hold across beats in proportion to weights.

    Returns one run time per weight; the list sums to max(duration - hold, 0).
    """
    usable = max(duration - min(hold, duration), 0.0)
    total = float(sum(weights))
    if total <= 0:
        raise ValueError("beat weights must sum to more than zero")
    return [usable * w / total for w in weights]


@dataclass(frozen=True)
class Area:
    """Axis-aligned rectangle in Manim scene units."""

    left: float
    right: float
    bottom: float
    top: float

    @property
    def width(self):
        return self.right - self.left

    @property
    def height(self):
        return self.top - self.bottom

    @property
    def center(self):
        return np.array([(self.left + self.right) / 2, (self.bottom + self.top) / 2, 0.0])

    def point(self, fx, fy):
        """Point at fraction (fx, fy) of the area; (0, 0) is bottom-left."""
        return np.array([self.left + fx * self.width, self.bottom + fy * self.height, 0.0])


class Layout:
    """Frame layout relative to frame size (aspect-ratio agnostic).

    Areas, top to bottom inside the safe area: title, content, caption, and
    narration. bottom_inset reserves an extra fraction of the frame height at
    the bottom (for app controls on vertical video). narration is the band
    for burned-in narration captions, right above that bottom zone; it is
    empty (zero height) unless narration_fraction > 0, which is a fraction of
    the safe height.
    """

    def __init__(self, frame_width, frame_height, margin=0.06, title_fraction=0.16,
                 caption_fraction=0.16, gap_fraction=0.03, bottom_inset=0.0,
                 narration_fraction=0.0):
        self.frame_width, self.frame_height = frame_width, frame_height
        m = margin * min(frame_width, frame_height)
        self.safe = Area(-frame_width / 2 + m, frame_width / 2 - m,
                         -frame_height / 2 + m + bottom_inset * frame_height,
                         frame_height / 2 - m)
        h, gap = self.safe.height, gap_fraction * self.safe.height
        title_bottom = self.safe.top - title_fraction * h
        narration_top = self.safe.bottom + narration_fraction * h
        caption_bottom = narration_top + (gap if narration_fraction else 0.0)
        caption_top = caption_bottom + caption_fraction * h
        self.title = Area(self.safe.left, self.safe.right, title_bottom, self.safe.top)
        self.narration = Area(self.safe.left, self.safe.right, self.safe.bottom, narration_top)
        self.caption = Area(self.safe.left, self.safe.right, caption_bottom, caption_top)
        self.content = Area(self.safe.left, self.safe.right, caption_top + gap,
                            title_bottom - gap)

    @property
    def text_scale(self):
        """Font-size factor: 1.0 when the shorter frame side is 8 units."""
        return min(self.frame_width, self.frame_height) / 8.0

    def grid(self, rows, cols, area=None):
        """Split area (default: content) into rows x cols cells, top row first."""
        area = area or self.content
        w, h = area.width / cols, area.height / rows
        return [[Area(area.left + c * w, area.left + (c + 1) * w,
                      area.top - (r + 1) * h, area.top - r * h)
                 for c in range(cols)] for r in range(rows)]

    def fit(self, mobject, area, buff=0.0):
        """Scale mobject down (never up) to fit area minus buff, centered. Returns it."""
        max_w, max_h = area.width - 2 * buff, area.height - 2 * buff
        factor = min(1.0, max_w / max(mobject.width, 1e-6), max_h / max(mobject.height, 1e-6))
        if factor < 1.0:
            mobject.scale(factor)
        return mobject.move_to(area.center)

    def keep_inside(self, mobject, area=None):
        """Shift mobject so it lies inside area (default: safe). Returns it."""
        area = area or self.safe
        dx = max(area.left - mobject.get_left()[0], 0) - max(mobject.get_right()[0] - area.right, 0)
        dy = max(area.bottom - mobject.get_bottom()[1], 0) - max(mobject.get_top()[1] - area.top, 0)
        return mobject.shift(np.array([dx, dy, 0.0]))


class SceneContext:
    """What a scene function gets. Attributes:

    scene           the ManimCE Scene (use scene.add/remove/play if needed)
    id, narration   from the storyboard
    lang, font      narration language and the font picked for it
    duration        seconds this scene must fill (speech + pad)
    speech_seconds  seconds of actual speech inside duration
    layout          Layout for the current frame
    """

    def __init__(self, scene, scene_id, narration, lang, start, duration, speech_seconds,
                 layout, font, fps):
        self.scene, self.id, self.narration, self.lang = scene, scene_id, narration, lang
        self.start, self.duration, self.speech_seconds = start, duration, speech_seconds
        self.layout, self.font, self.fps = layout, font, fps
        self._carried, self._carry_all = [], False
        self._camera = None

    def carry(self, *mobjects):
        """Keep mobjects on screen into the next scene instead of fading them
        out when it starts. A carried part keeps its whole on-screen group.
        With no arguments, keep everything that is on screen at the scene end."""
        if mobjects:
            self._carried.extend(mobjects)
        else:
            self._carry_all = True

    def carried(self):
        """Objects to keep into the next scene (make_video.py reads this)."""
        if self._carry_all:
            return list(self.scene.mobjects)
        return list(self._carried)

    @property
    def camera(self):
        """Camera moves for this scene (see Camera). Each scene starts at home."""
        if self._camera is None:
            self._camera = Camera(self)
        return self._camera

    def text(self, s, size=TEXT_SIZE, color=WHITE, **kwargs):
        """Text in the scene font, sized relative to the frame."""
        kwargs.setdefault("font", self.font)
        return Text(s, font_size=size * self.layout.text_scale, color=color, **kwargs)

    def title(self, s, color=WHITE):
        """Title text fitted into the title area (not yet added). Fixed on
        screen during camera moves."""
        return fix(self.layout.fit(self.text(s, TITLE_SIZE, color), self.layout.title))

    def caption(self, s, color=WHITE):
        """Caption text fitted into the caption area (not yet added). Fixed on
        screen during camera moves."""
        return fix(self.layout.fit(self.text(s, CAPTION_SIZE, color), self.layout.caption))

    def narration_caption(self, lines, color=WHITE):
        """Burned-in narration caption: lines of one scene's narration, in the
        narration area, larger than scene captions (not yet added). Used by
        make_video.py for presets that burn captions; scene code need not call it."""
        paragraph = Paragraph(*lines, alignment="center", font=self.font, color=color,
                              font_size=NARRATION_SIZE * self.layout.text_scale,
                              line_spacing=0.6)
        return fix(self.layout.fit(paragraph, self.layout.narration))

    def label(self, s, target, direction=DOWN, buff=0.2, size=TEXT_SIZE * 0.8, color=WHITE):
        """Label next to target, kept inside the safe area (not yet added)."""
        mob = self.text(s, size, color).next_to(target, direction, buff=buff)
        return self.layout.keep_inside(mob)

    def swap_caption(self, old, new):
        """Animation: fade old out fully, then fade new in. old may be None."""
        if old is None:
            return FadeIn(new)
        return Succession(FadeOut(old), FadeIn(new))

    def beats(self, steps, hold=HOLD_SECONDS):
        """Play beats that fill ctx.duration exactly, then hold still.

        steps: list of (animation | list of animations | None, weight).
        None means wait. Time is split by weight (see allocate()).
        """
        # Start from now, not from ctx.start: the scene may begin with the
        # fade-out of the previous scene's objects (clear_previous()).
        begin = max(self.start, self.scene.renderer.time)
        times = allocate(self.start + self.duration - begin, [w for _, w in steps], hold)
        target = begin
        for (anims, _), run_time in zip(steps, times):
            target += run_time
            seconds = self._frames_until(target) / self.fps
            if seconds <= 0:
                continue
            if anims is None:
                self.scene.wait(seconds)
            else:
                anims = anims if isinstance(anims, (list, tuple)) else [anims]
                self.scene.play(*anims, run_time=seconds)
        self.wait_until(self.start + self.duration)

    def wait_until(self, t):
        """Wait (still frame) until absolute video time t, if not past it."""
        frames = self._frames_until(t)
        if frames > 0:
            # +0.5 frame: a frozen wait writes int(seconds * fps) frames.
            self.scene.wait((frames + 0.5) / self.fps)

    def _frames_until(self, t):
        return int(round((t - self.scene.renderer.time) * self.fps))


def carried_on_screen(scene, keep):
    """Top-level objects on screen that are in keep or contain a part of it."""
    return [m for m in scene.mobjects
            if any(k is m or k in m.get_family() for k in keep)]


def clear_previous(ctx, keep):
    """Fade out every object on screen except those in keep (objects the
    previous scene passed to ctx.carry()). An on-screen group stays when it
    or any part of it is in keep. Takes CLEAR_SECONDS, at most a quarter of
    the scene."""
    scene = ctx.scene
    stay = carried_on_screen(scene, keep)
    gone = [m for m in scene.mobjects if m not in stay]
    if not gone:
        return
    frames = int(round(min(CLEAR_SECONDS, ctx.duration / 4) * ctx.fps))
    if frames < 1:
        scene.remove(*gone)
        return
    scene.play(*[FadeOut(m) for m in gone], run_time=frames / ctx.fps)


# ---------------------------------------------------------------- camera
#
# A camera move is an animation of the content, not of the ManimCE camera:
# make_video.py renders a plain Scene, and its title, captions and burned
# narration are ordinary mobjects. A move maps every non-fixed object on
# screen through p -> k * p + t, frame by frame, the way a moving camera frame
# would show it (stroke widths stay). Fixed objects are not touched, so they
# keep their exact place in the safe area at any aspect ratio. The camera
# state (k, t) is relative to the scene start, and each scene starts at home.

FIXED_ATTR = "_video_helper_fixed"
HOME = (1.0, np.zeros(3))


def fix(mobject):
    """Mark mobject as fixed on screen: camera moves leave it in place. Returns it."""
    setattr(mobject, FIXED_ATTR, True)
    return mobject


def is_fixed(mobject):
    return getattr(mobject, FIXED_ATTR, False)


def fit_view(center, width, height, area, buff=0.0, scale=None):
    """Map (factor, shift) that centers a box (center, width, height) in area,
    scaled to fit area minus buff on each side, or scaled by scale when given.
    A point p goes to factor * p + shift."""
    if scale is None:
        scale = min((area.width - 2 * buff) / max(width, 1e-6),
                    (area.height - 2 * buff) / max(height, 1e-6))
    if scale <= 0:
        raise ValueError("camera zoom factor must be positive")
    return scale, area.center - scale * np.asarray(center, dtype=float)


def compose(state, factor, shift):
    """Camera state after a further map p -> factor * p + shift."""
    k, t = state
    return k * factor, factor * np.asarray(t, dtype=float) + shift


def between(start, end, alpha):
    """Camera state at alpha (0 to 1) from start to end. Like a moving camera
    frame, the visible size and the visible center change linearly."""
    (k0, t0), (k1, t1) = start, end
    k = 1.0 / ((1 - alpha) / k0 + alpha / k1)
    center = (1 - alpha) * (-np.asarray(t0) / k0) + alpha * (-np.asarray(t1) / k1)
    return k, -k * center


def movers_and_fixed(mobjects):
    """Split on-screen objects into the ones a camera move moves and the fixed
    ones. A group that holds a fixed part is split into its parts."""
    movers, fixed = [], []
    for mob in mobjects:
        if is_fixed(mob):
            fixed.append(mob)
        elif any(is_fixed(part) for part in mob.get_family()):
            inner_movers, inner_fixed = movers_and_fixed(mob.submobjects)
            movers += inner_movers
            fixed += inner_fixed
        else:
            movers.append(mob)
    return movers, fixed


def _apply(mobjects, factor, shift):
    # Stroke widths stay as drawn: a 10x zoom in the 9:16 frame would turn
    # outlines into thick bars.
    for mob in mobjects:
        mob.scale(factor, about_point=ORIGIN).shift(shift)


class CameraMove(Animation):
    """Moves the non-fixed objects on screen from the camera state at its start
    to end_state(start state). Built by Camera; play it through ctx.beats()."""

    def __init__(self, camera, end_state, **kwargs):
        self.camera, self.end_state = camera, end_state
        # introducer: the scene must not add the (empty) group; _setup_scene
        # fills it with what is on screen when the move starts.
        super().__init__(Group(), introducer=True, suspend_mobject_updating=False, **kwargs)

    def _setup_scene(self, scene):
        movers, fixed = movers_and_fixed(scene.mobjects)
        self.movers = movers
        self.mobject = Group(*movers)  # marks them as moving for the renderer
        # Fixed objects draw over zoomed content.
        scene.bring_to_front(*[m for m in fixed if m in scene.mobjects])

    def begin(self):
        self.start = self.camera.state
        self.end = self.end_state(self.start)
        self.applied = self.start

    def interpolate_mobject(self, alpha):
        k, t = between(self.start, self.end, self.rate_func(alpha))
        k0, t0 = self.applied
        factor = k / k0
        _apply(self.movers, factor, t - factor * t0)
        self.applied = self.camera.state = (k, t)

    def update_mobjects(self, dt):
        pass  # the scene runs the updaters; running them here would run them twice

    def finish(self):
        super().finish()
        self.camera.state = self.end


class Camera:
    """Camera moves of one scene: ctx.camera. Each method returns an animation
    for ctx.beats(); the move is computed when it starts, from what is on
    screen then. Titles, captions, the burned narration and objects passed to
    fix() stay in place."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.state = HOME

    @property
    def is_home(self):
        k, t = self.state
        return abs(k - 1.0) < 1e-9 and bool(np.allclose(t, 0.0, atol=1e-9))

    def fix(self, mobject):
        """Keep mobject fixed on screen during camera moves. Returns it."""
        return fix(mobject)

    def _box(self, target):
        """Center, width and height of target as shown now."""
        if isinstance(target, Mobject):
            return target.get_center(), target.width, target.height
        if isinstance(target, Area):  # scene-start coordinates
            k, t = self.state
            return k * target.center + t, k * target.width, k * target.height
        raise TypeError("camera target must be a mobject or an Area")

    def zoom(self, target, scale=None, buff=None):
        """Animation: fit target into the content area, centered. scale sets
        the zoom factor (relative to the scene start) instead of fitting."""
        buff = 0.25 * self.ctx.layout.text_scale if buff is None else buff

        def end(state):
            center, width, height = self._box(target)
            factor = None if scale is None else scale / state[0]
            return compose(state, *fit_view(center, width, height, self.ctx.layout.content,
                                            buff, factor))
        return CameraMove(self, end)

    def pan(self, target):
        """Animation: move target to the center of the content area, same zoom."""
        def end(state):
            center, _, _ = self._box(target)
            return compose(state, 1.0, self.ctx.layout.content.center - center)
        return CameraMove(self, end)

    def restore(self):
        """Animation: bring the content back to where it was at the scene start."""
        return CameraMove(self, lambda state: HOME)


# ---------------------------------------------------------------- fallback scene

CLAUSE_RE = re.compile(r"[^,.;:!?，。；：！？、]+[,.;:!?，。；：！？、]*")
CLAUSE_END = ",.;:!?，。；：！？、 "
# Bullet line width in characters: (portrait, landscape) per script.
BULLET_CHARS = {"zh": (10, 18), "default": (22, 40)}


def fallback_text(narration, title=None, max_bullets=4):
    """Title and 2 to max_bullets bullets drawn from a scene's narration.

    The title is the given one, else the narration's first clause; the
    bullets are the following clauses (all clauses when fewer than two follow).
    """
    clauses = [c.strip().rstrip(CLAUSE_END) for c in CLAUSE_RE.findall(narration.strip())]
    clauses = [c for c in clauses if c] or [narration.strip()]
    rest = clauses if title else clauses[1:]
    title = title or clauses[0]
    if len(rest) < 2:
        rest = clauses
    if len(rest) < 2:
        rest = _halve(rest[0])
    return title, rest[:max_bullets]


def _halve(text):
    words = text.split()
    if len(words) > 1:
        mid = (len(words) + 1) // 2
        return [" ".join(words[:mid]), " ".join(words[mid:])]
    mid = (len(text) + 1) // 2
    return [text[:mid], text[mid:]] if len(text) > 1 else [text]


def _wrap(text, width, zh):
    if zh:
        return [text[i:i + width] for i in range(0, len(text), width)]
    return textwrap.wrap(text, width) or [text]


def fallback_scene(ctx, title=None):
    """Draw the fallback for a scene that cannot be rendered: a title and 2-4
    bullets from ctx.narration, filling ctx.duration. Works in any aspect
    ratio. make_video.py uses it for storyboard scenes marked "fallback": true;
    it clears the screen first and afterwards restores the objects carried
    into the scene, so the next scene still gets them."""
    title_text, bullets = fallback_text(ctx.narration, title)
    zh = ctx.lang.lower().startswith("zh")
    portrait = ctx.layout.frame_width < ctx.layout.frame_height
    width = BULLET_CHARS["zh" if zh else "default"][0 if portrait else 1]
    heading = ctx.title(title_text)
    items = []
    for bullet in bullets:
        dot = ctx.text("•")
        lines = Paragraph(*_wrap(bullet, width, zh), alignment="left", font=ctx.font,
                          font_size=TEXT_SIZE * ctx.layout.text_scale, color=WHITE,
                          line_spacing=0.6)
        dot.next_to(lines[0], LEFT, buff=0.25 * ctx.layout.text_scale)
        items.append(VGroup(dot, lines))
    body = VGroup(*items).arrange(DOWN, aligned_edge=LEFT, buff=0.35 * ctx.layout.text_scale)
    ctx.layout.fit(body, ctx.layout.content, buff=0.1 * ctx.layout.text_scale)
    ctx.beats([
        (FadeIn(heading), 1),
        (LaggedStart(*[FadeIn(item, shift=0.2 * RIGHT) for item in items], lag_ratio=0.6), 3),
        (None, 1),
    ])
