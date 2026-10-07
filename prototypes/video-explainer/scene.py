"""PROTOTYPE: binary-search explainer. Audio-first: reads per-scene narration
durations from the JSON named by env VE_CONFIG and stretches each scene's
animations + waits to fill exactly that duration."""
import json
import os

from manim import (
    DOWN, GREEN, RIGHT, UP, WHITE, YELLOW, BLUE_E,
    Create, FadeIn, FadeOut, Indicate, Rectangle, Scene, Succession, Text, VGroup, Write,
)

CFG = json.load(open(os.environ["VE_CONFIG"], encoding="utf-8"))
SCRIPT = json.load(open(CFG["script"], encoding="utf-8"))
LBL = SCRIPT["labels"][CFG["lang"]]
FONT = CFG.get("font") or ""
DUR = CFG["durations"]  # seconds per scene, measured from narration audio


def T(s, size=30, color=WHITE):
    return Text(s, font=FONT, font_size=size, color=color) if FONT else Text(s, font_size=size, color=color)


class Explainer(Scene):
    def seg(self, total, steps):
        """steps: list of (animations or None, weight). Weights share `total` seconds."""
        wsum = sum(w for _, w in steps)
        for anims, w in steps:
            rt = total * w / wsum
            if anims:
                self.play(*anims, run_time=rt)
            else:
                self.wait(rt)

    def run_seg(self, total, steps):
        # compensate frame rounding drift so the scene ends exactly on its audio boundary
        self.seg(total, steps)
        self._target = getattr(self, "_target", 0.0) + total
        drift = self._target - self.renderer.time
        if drift > 1.0 / 30:
            self.wait(drift)

    def construct(self):
        nums = SCRIPT["numbers"]
        title = T(LBL["title"], 40).to_edge(UP, buff=0.4)
        target = T(LBL["target"], 30, YELLOW).next_to(title, DOWN, buff=0.3)
        boxes = VGroup(*[
            VGroup(Rectangle(width=0.72, height=0.72, color=BLUE_E, fill_opacity=0.35),
                   T(str(n), 24))
            for n in nums
        ]).arrange(RIGHT, buff=0.08)
        for b in boxes:
            b[1].move_to(b[0])
        boxes.move_to(DOWN * 0.2)
        caption = T(LBL["mid"], 28).next_to(boxes, DOWN, buff=0.6)

        def hl(i):
            return boxes[i][0].animate.set_stroke(YELLOW, width=6)

        def dim(rng):
            return [boxes[i].animate.set_opacity(0.15) for i in rng]

        def cap(key, color=WHITE):
            new = T(LBL[key], 28, color).next_to(boxes, DOWN, buff=0.6)
            return new

        def swap(old, new):
            # layout fix after preview check: captions share a position, so fade out fully before fading in
            return Succession(FadeOut(old), FadeIn(new))

        # Scene 1: boxes, target, middle highlighted (index 7 = 31)
        self.run_seg(DUR[0], [
            ([Write(title)], 1.0),
            ([Create(boxes)], 2.0),
            ([FadeIn(target)], 0.8),
            ([hl(7), FadeIn(caption)], 1.0),
            (None, 0.6),
        ])

        # Scene 2: drop left half, then 53 (idx 11) too big, 42 (idx 9) too big
        c1 = cap("small")
        c2 = cap("big1")
        c3 = cap("big2")
        self.run_seg(DUR[1], [
            ([*dim(range(0, 8)), swap(caption, c1)], 1.2),
            ([hl(11)], 0.6),
            ([*dim(range(11, 16)), swap(c1, c2)], 1.0),
            ([hl(9)], 0.6),
            ([*dim(range(9, 11)), swap(c2, c3)], 1.0),
            (None, 0.4),
        ])

        # Scene 3: found 37 (idx 8), counter
        found = cap("found", GREEN)
        counter = T(LBL["counter"], 34, YELLOW).next_to(found, DOWN, buff=0.4)
        self.run_seg(DUR[2], [
            ([boxes[8][0].animate.set_fill(GREEN, opacity=0.8).set_stroke(GREEN, width=6),
              swap(c3, found)], 1.0),
            ([Indicate(boxes[8], color=GREEN)], 0.8),
            ([Write(counter)], 1.6),
            (None, 0.8),
        ])
