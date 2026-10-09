"""Unit tests for the pure parts of run_eval.py (topic parsing, SRT, captions, metrics).

Run: python -m unittest discover -s evals/video-explainer -p "test_run_eval.py"
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_eval  # noqa: E402

TOPIC = """# Binary search

- Language: zh-TW
- Output preset: `explainer` (16:9, 720p)
- Mode: `deep`
- Request: 用 3Blue1Brown 風格，把下面這段說明做成一支深入的解說影片。

## Source

二分搜尋是在已排序的資料裡找目標值的方法。
第二行。

## Viewer should understand

- 一點。
- 兩點，有逗號。

## Visual hints

- A row of boxes.
"""

MODES = {"quick": {"scenes": [3, 6], "target_seconds": [30, 90]},
         "standard": {"scenes": [6, 15], "target_seconds": [120, 240]},
         "deep": {"scenes": [15, 30], "target_seconds": [300, 600]}}

SRT = """1
00:00:00,000 --> 00:00:04,500
要在十六個數字裡找三十七。
先看正中間。

2
00:00:04,500 --> 00:00:07,250
三十一太小，左邊丟掉。
"""


class ParseTopicTest(unittest.TestCase):
    def test_reads_language_preset_and_source(self):
        topic = run_eval.parse_topic("01-binary-search", TOPIC)
        self.assertEqual(topic["lang"], "zh-TW")
        self.assertEqual(topic["preset"], "explainer")
        self.assertEqual(topic["source"], "二分搜尋是在已排序的資料裡找目標值的方法。\n第二行。")

    def test_reads_mode_request_and_points(self):
        topic = run_eval.parse_topic("01-binary-search", TOPIC)
        self.assertEqual(topic["mode"], "deep")
        self.assertEqual(topic["request"], "用 3Blue1Brown 風格，把下面這段說明做成一支深入的解說影片。")
        self.assertEqual(topic["points"], ["一點。", "兩點，有逗號。"])

    def test_mode_and_request_are_required(self):
        no_mode = TOPIC.replace("- Mode: `deep`\n", "")
        no_request = "\n".join(line for line in TOPIC.splitlines() if not line.startswith("- Request:"))
        with self.assertRaises(ValueError):
            run_eval.parse_topic("01", no_mode)
        with self.assertRaises(ValueError):
            run_eval.parse_topic("01", no_request)

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            run_eval.parse_topic("01", TOPIC.replace("`deep`", "`epic`"))

    def test_baseline_arm_only_for_zh_tw(self):
        self.assertTrue(run_eval.parse_topic("01", TOPIC)["baseline"])
        self.assertFalse(run_eval.parse_topic("02", TOPIC.replace("zh-TW", "en"))["baseline"])

    def test_real_topic_files_parse(self):
        topics = run_eval.load_topics(None)
        self.assertEqual([t["mode"] for t in topics], ["deep", "quick", "standard", "quick"])
        self.assertEqual([t["baseline"] for t in topics], [True, False, True, False])
        self.assertTrue(all(t["request"] and t["points"] for t in topics))


class PromptTest(unittest.TestCase):
    TOPIC = {"request": "Make a Short.", "preset": "short", "source": "Text."}

    def test_request_preset_preapproval_then_source(self):
        prompt = run_eval.build_prompt(self.TOPIC)
        self.assertTrue(prompt.startswith("Make a Short. Use the short output preset. "))
        self.assertIn("The storyboard is pre-approved: do not wait for confirmation; render it. "
                      "Any model download the plan lists is approved.", prompt)
        self.assertTrue(prompt.rstrip().endswith("\n\nText."))

    def test_prompt_does_not_depend_on_the_arm(self):
        self.assertEqual(run_eval.build_prompt(self.TOPIC), run_eval.build_prompt(dict(self.TOPIC, baseline=True)))


class BuildCmdTest(unittest.TestCase):
    def test_baseline_has_no_plugin_dir_but_same_other_flags(self):
        skill = run_eval.build_cmd("claude", "sonnet", "with-skill")
        base = run_eval.build_cmd("claude", "sonnet", "baseline")
        self.assertIn("--plugin-dir", skill)
        self.assertNotIn("--plugin-dir", base)
        i = skill.index("--plugin-dir")
        self.assertEqual(skill[:i] + skill[i + 2:], base)
        self.assertIn("Bash,Read,Write,Edit,Skill,Glob,Grep", base)

    def test_default_arm_is_with_skill(self):
        self.assertIn("--plugin-dir", run_eval.build_cmd("claude", None))


class SrtTest(unittest.TestCase):
    def test_parses_multiline_cues(self):
        cues = run_eval.parse_srt(SRT)
        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[0]["start"], 0.0)
        self.assertAlmostEqual(cues[1]["end"], 7.25)
        self.assertEqual(cues[0]["text"], "要在十六個數字裡找三十七。\n先看正中間。")

    def test_tolerates_bom_and_crlf(self):
        cues = run_eval.parse_srt("﻿" + SRT.replace("\n", "\r\n"))
        self.assertEqual(len(cues), 2)


class CaptionMatchTest(unittest.TestCase):
    def test_match_ignores_punctuation_space_and_line_breaks(self):
        cues = run_eval.parse_srt(SRT)
        result = run_eval.caption_match(cues, ["要在十六個數字裡找三十七，先看正中間", "三十一太小 左邊丟掉!"])
        self.assertEqual(result["matched"], 2)
        self.assertTrue(result["pass"])

    def test_mismatch_and_count_difference(self):
        cues = run_eval.parse_srt(SRT)
        result = run_eval.caption_match(cues, ["別的內容", "三十一太小，左邊丟掉。", "多一個"])
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["scenes"], 3)
        self.assertFalse(result["pass"])

    def test_english_case_insensitive(self):
        cues = [{"text": "You type a web\naddress."}]
        self.assertTrue(run_eval.caption_match(cues, ["you type a Web address"])["pass"])


class ProbeTest(unittest.TestCase):
    def test_parse_probe(self):
        data = {"streams": [
            {"codec_type": "video", "width": 1080, "height": 1920, "duration": "41.2"},
            {"codec_type": "audio", "duration": "41.05"}], "format": {"duration": "41.2"}}
        self.assertEqual(run_eval.parse_probe(data),
                         {"width": 1080, "height": 1920, "video_seconds": 41.2, "audio_seconds": 41.05})

    def test_parse_probe_without_audio(self):
        data = {"streams": [{"codec_type": "video", "width": 1280, "height": 720}],
                "format": {"duration": "10.0"}}
        probe = run_eval.parse_probe(data)
        self.assertEqual(probe["video_seconds"], 10.0)
        self.assertIsNone(probe["audio_seconds"])


class ChooseFinalTest(unittest.TestCase):
    def test_prefers_newest_successful(self):
        candidates = [("a/final.json", 30, {"ok": False}),
                      ("b/final.json", 10, {"ok": True}),
                      ("c/final.json", 20, {"ok": True})]
        self.assertEqual(run_eval.choose_final(candidates)[0], "c/final.json")

    def test_falls_back_to_newest_failed(self):
        candidates = [("a/final.json", 1, {"ok": False}), ("b/final.json", 2, {"ok": False})]
        self.assertEqual(run_eval.choose_final(candidates)[0], "b/final.json")
        self.assertIsNone(run_eval.choose_final([]))


class TopicMetricsTest(unittest.TestCase):
    def final(self, **extra):
        data = {"ok": True, "scenes": [{"id": f"s{i}"} for i in range(1, 5)],
                "replaced": ["s3"], "flagged": [{"id": "s4", "reason": "x", "frame": None}],
                "audio_seconds": 60.0, "video_seconds": 60.1, "difference_seconds": 0.1}
        data.update(extra)
        return data

    def test_metrics_and_checks(self):
        probe = {"width": 1280, "height": 720, "video_seconds": 60.1, "audio_seconds": 60.0}
        captions = {"matched": 4, "scenes": 4, "pass": True}
        m = run_eval.topic_metrics("explainer", self.final(), probe, True, captions)
        self.assertTrue(m["render_ok"])
        self.assertTrue(m["resolution_ok"])
        self.assertEqual(m["scenes"], 4)
        self.assertEqual(m["flagged"], 1)
        self.assertEqual(m["fallbacks"], 1)
        self.assertAlmostEqual(m["layout_pass_rate"], 0.75)
        self.assertAlmostEqual(m["av_difference_seconds"], 0.1)
        self.assertTrue(m["av_ok"])
        self.assertTrue(m["captions_ok"])

    def test_wrong_resolution_and_long_tail_fail(self):
        probe = {"width": 1280, "height": 720, "video_seconds": 61.0, "audio_seconds": 60.0}
        m = run_eval.topic_metrics("youtube", self.final(), probe, True, {"matched": 4, "scenes": 4, "pass": True})
        self.assertFalse(m["resolution_ok"])
        self.assertFalse(m["av_ok"])

    def test_no_video(self):
        m = run_eval.topic_metrics("short", None, None, False, None)
        self.assertFalse(m["render_ok"])
        self.assertIsNone(m["av_ok"])
        self.assertIsNone(m["layout_pass_rate"])


class AggregateTest(unittest.TestCase):
    def test_totals_and_verdict(self):
        ok = {"render_ok": True, "resolution_ok": True, "av_ok": True, "captions_ok": True,
              "scenes": 4, "flagged": 1, "fallbacks": 0}
        bad = dict(ok, av_ok=False, flagged=0, fallbacks=1)
        results = [{"id": "01", "metrics": ok, "meta": {"num_turns": 10, "cost_usd": 1.5}, "seconds": 100},
                   {"id": "02", "metrics": bad, "meta": {"num_turns": 20, "cost_usd": 2.0}, "seconds": 200}]
        agg = run_eval.aggregate(results)
        self.assertEqual(agg["rendered"], 2)
        self.assertAlmostEqual(agg["layout_pass_rate"], 7 / 8)
        self.assertEqual(agg["fallbacks"], 1)
        self.assertAlmostEqual(agg["cost_usd"], 3.5)
        self.assertEqual(agg["turns"], 30)
        self.assertEqual(agg["verdict"], "FAIL")
        self.assertEqual(run_eval.aggregate(results[:1])["verdict"], "PASS")

    def test_fail_when_a_topic_did_not_render(self):
        results = [{"id": "01", "metrics": run_eval.topic_metrics("short", None, None, False, None),
                    "meta": None, "seconds": 5}]
        agg = run_eval.aggregate(results)
        self.assertEqual(agg["rendered"], 0)
        self.assertEqual(agg["verdict"], "FAIL")

    def test_incomplete_when_a_check_has_no_data(self):
        m = {"render_ok": True, "resolution_ok": True, "av_ok": None, "captions_ok": True,
             "scenes": 4, "flagged": 0, "fallbacks": 0}
        results = [{"id": "01", "metrics": m, "meta": None, "seconds": 5}]
        self.assertEqual(run_eval.aggregate(results)["verdict"], "INCOMPLETE")


def touch(path, mtime, data=b"x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    os.utime(path, (mtime, mtime))


class FindNewestMp4Test(unittest.TestCase):
    def test_newest_mp4_at_any_depth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            touch(root / "old.mp4", 100)
            touch(root / "a" / "b" / "new.mp4", 300)
            touch(root / "notes.txt", 900)
            self.assertEqual(run_eval.find_newest_mp4(root), root / "a" / "b" / "new.mp4")

    def test_skips_empty_files_and_manim_partial_movies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            touch(root / "final.mp4", 100)
            touch(root / "empty.mp4", 500, b"")
            touch(root / "media" / "videos" / "partial_movie_files" / "Scene" / "0001.mp4", 600)
            self.assertEqual(run_eval.find_newest_mp4(root), root / "final.mp4")

    def test_none_when_no_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(run_eval.find_newest_mp4(Path(tmp)))
            self.assertIsNone(run_eval.find_newest_mp4(Path(tmp) / "missing"))


class BaselineMetricsTest(unittest.TestCase):
    def test_video_and_audio_metrics_apply_and_the_rest_is_na(self):
        probe = {"width": 1920, "height": 1080, "video_seconds": 100.2, "audio_seconds": 100.0}
        m = run_eval.baseline_metrics("youtube", probe, True)
        self.assertTrue(m["render_ok"])
        self.assertTrue(m["resolution_ok"])
        self.assertAlmostEqual(m["av_difference_seconds"], 0.2)
        self.assertTrue(m["av_ok"])
        for key in ("captions", "captions_ok", "scenes", "flagged", "fallbacks", "layout_pass_rate"):
            self.assertIsNone(m[key])

    def test_wrong_resolution_is_reported(self):
        probe = {"width": 1280, "height": 720, "video_seconds": 10.0, "audio_seconds": None}
        m = run_eval.baseline_metrics("youtube", probe, True)
        self.assertFalse(m["resolution_ok"])
        self.assertIsNone(m["av_ok"])

    def test_no_video_or_undecodable_video(self):
        self.assertFalse(run_eval.baseline_metrics("youtube", None, False)["render_ok"])
        probe = {"width": 1920, "height": 1080, "video_seconds": 10.0, "audio_seconds": 10.0}
        self.assertFalse(run_eval.baseline_metrics("youtube", probe, False)["render_ok"])

    def test_row_shows_na_not_failure(self):
        probe = {"width": 1920, "height": 1080, "video_seconds": 100.0, "audio_seconds": 100.0}
        r = {"id": "03", "lang": "zh-TW", "preset": "youtube", "meta": {"num_turns": 5, "cost_usd": 1.0},
             "seconds": 60.0, "metrics": run_eval.baseline_metrics("youtube", probe, True)}
        row = run_eval.metrics_row(r)
        self.assertIn("n/a", row)
        self.assertNotIn("FAIL", " ".join(row))


class ModeMetricsTest(unittest.TestCase):
    def test_inside_ranges(self):
        m = run_eval.mode_metrics("deep", "deep", 20, 400.0, MODES)
        self.assertEqual(m["mode"], "deep")
        self.assertTrue(m["matches_request"])
        self.assertTrue(m["scenes_in_range"])
        self.assertTrue(m["seconds_in_range"])
        self.assertEqual(m["scenes_range"], [15, 30])
        self.assertEqual(m["seconds_range"], [300, 600])

    def test_outside_ranges_and_other_mode(self):
        m = run_eval.mode_metrics("deep", "standard", 5, 65.0, MODES)
        self.assertFalse(m["matches_request"])
        self.assertFalse(m["scenes_in_range"])
        self.assertFalse(m["seconds_in_range"])

    def test_range_edges_are_inside(self):
        m = run_eval.mode_metrics("quick", "quick", 6, 30.0, MODES)
        self.assertTrue(m["scenes_in_range"])
        self.assertTrue(m["seconds_in_range"])

    def test_missing_data_is_none(self):
        m = run_eval.mode_metrics("quick", None, None, None, MODES)
        self.assertIsNone(m["matches_request"])
        self.assertIsNone(m["scenes_in_range"])
        self.assertIsNone(m["seconds_in_range"])
        m = run_eval.mode_metrics("quick", "quick", 4, None, MODES)
        self.assertTrue(m["scenes_in_range"])
        self.assertIsNone(m["seconds_in_range"])

    def test_unknown_mode_or_no_ranges(self):
        self.assertIsNone(run_eval.mode_metrics("quick", "weird", 4, 60.0, MODES)["scenes_in_range"])
        self.assertIsNone(run_eval.mode_metrics("quick", "quick", 4, 60.0, {})["scenes_in_range"])

    def test_load_modes_reads_the_skill(self):
        modes, default = run_eval.load_modes()
        self.assertEqual(sorted(modes), sorted(run_eval.MODE_NAMES))
        self.assertIn(default, modes)

    def test_read_board_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            self.assertIsNone(run_eval.read_board_mode(out, "standard"))
            (out / "plan.json").write_text(json.dumps({"mode": {"name": "deep"}}), encoding="utf-8")
            self.assertEqual(run_eval.read_board_mode(out, "standard"), "deep")
            (out / "storyboard.json").write_text(json.dumps({"mode": "quick", "scenes": []}), encoding="utf-8")
            self.assertEqual(run_eval.read_board_mode(out, "standard"), "quick")
            (out / "storyboard.json").write_text(json.dumps({"scenes": []}), encoding="utf-8")
            self.assertEqual(run_eval.read_board_mode(out, "standard"), "standard")


TOPIC_IDS = [f"{n:02d}-t" for n in range(1, 9)]


class AbOrderTest(unittest.TestCase):
    def test_repeatable_by_seed_and_a_permutation(self):
        first = run_eval.ab_orders(TOPIC_IDS, "20261009-120000")
        self.assertEqual(first, run_eval.ab_orders(TOPIC_IDS, "20261009-120000"))
        for order in first.values():
            self.assertEqual(sorted(order), sorted(run_eval.ARMS))

    def test_both_orders_occur_and_seed_matters(self):
        orders = run_eval.ab_orders(TOPIC_IDS, "s1")
        self.assertEqual({o[0] for o in orders.values()}, set(run_eval.ARMS))
        self.assertNotEqual(orders, run_eval.ab_orders(TOPIC_IDS, "s2"))


def fake_result(tid, baseline, order=("with-skill", "baseline")):
    result = {"id": tid, "lang": "zh-TW", "preset": "explainer", "mode": "deep",
              "points": ["要點一。", "要點二。"], "video": f"{tid}/video.mp4", "baseline": None}
    if baseline:
        result["baseline"] = {"video": f"{tid}/baseline/video.mp4"}
    return result


class ReviewTest(unittest.TestCase):
    def setUp(self):
        self.results = [fake_result("01-binary-search", True), fake_result("02-gradient-descent", False)]
        self.orders = {"01-binary-search": ("baseline", "with-skill")}

    def test_ab_key_lists_only_baseline_topics(self):
        key = run_eval.ab_key(self.results, self.orders)
        self.assertEqual(key, {"01-binary-search": {"A": "baseline", "B": "with-skill"}})

    def test_plan_assigns_labels_by_order(self):
        plan = run_eval.review_plan(self.results, self.orders)
        both, single = plan
        self.assertEqual([(v["label"], v["source"]) for v in both["videos"]],
                         [("A", "01-binary-search/baseline/video.mp4"), ("B", "01-binary-search/video.mp4")])
        self.assertEqual([v["label"] for v in single["videos"]], [None])
        self.assertEqual(single["videos"][0]["source"], "02-gradient-descent/video.mp4")
        self.assertTrue(both["ab"])
        self.assertFalse(single["ab"])

    def test_build_review_copies_neutral_names_and_page_has_no_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            for rel in ("01-binary-search/baseline/video.mp4", "01-binary-search/video.mp4",
                        "02-gradient-descent/video.mp4"):
                touch(run_dir / rel, 1, rel.encode())
            self.results[0]["video"] = str(run_dir / "01-binary-search/video.mp4")
            self.results[0]["baseline"]["video"] = str(run_dir / "01-binary-search/baseline/video.mp4")
            self.results[1]["video"] = str(run_dir / "02-gradient-descent/video.mp4")
            page = run_eval.build_review(self.results, self.orders, run_dir, "20261009-120000")
            html = page.read_text(encoding="utf-8")
            self.assertEqual(page, run_dir / "review.html")
            # A is the baseline video here; the copy is under a neutral name.
            self.assertEqual((run_dir / "review" / "01-binary-search-A.mp4").read_bytes(),
                             b"01-binary-search/baseline/video.mp4")
            self.assertEqual((run_dir / "review" / "01-binary-search-B.mp4").read_bytes(),
                             b"01-binary-search/video.mp4")
            self.assertTrue((run_dir / "review" / "02-gradient-descent.mp4").is_file())
            self.assertIn('src="review/01-binary-search-A.mp4"', html)
            self.assertIn('src="review/02-gradient-descent.mp4"', html)
            for secret in ("with-skill", "baseline", "ab_key", "skill", "Skill"):
                self.assertNotIn(secret, html)

    def test_missing_video_is_shown_not_dropped(self):
        results = [dict(fake_result("01-binary-search", True), video=None)]
        with tempfile.TemporaryDirectory() as tmp:
            page = run_eval.build_review(results, {"01-binary-search": ("with-skill", "baseline")},
                                         Path(tmp), "t")
            html = page.read_text(encoding="utf-8")
        self.assertIn("沒有影片", html)

    def render(self):
        entries = [{"id": "01-binary-search", "lang": "zh-TW", "points": ["要點 <一>。"], "ab": True,
                    "videos": [{"label": "A", "src": "review/01-binary-search-A.mp4"},
                               {"label": "B", "src": "review/01-binary-search-B.mp4"}]},
                   {"id": "02-gradient-descent", "lang": "en", "points": [], "ab": False,
                    "videos": [{"label": None, "src": "review/02-gradient-descent.mp4"}]}]
        return run_eval.render_review(entries, "20261009-120000")

    def test_page_is_self_contained_with_video_players(self):
        html = self.render()
        self.assertEqual(html.count("<video controls"), 3)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("<script src", html)
        self.assertIn("&lt;一&gt;", html)

    def test_page_has_both_rating_axes_and_better_only_for_pairs(self):
        html = self.render()
        self.assertEqual(html.count('data-axis="understanding"'), 3 * 5)
        self.assertEqual(html.count('data-axis="presentation"'), 3 * 5)
        self.assertEqual(html.count('data-axis="better"'), 3)
        self.assertIn("影片 A", html)
        self.assertIn("影片 B", html)
        self.assertIn("要點", html)
        self.assertIn("localStorage", html)
        self.assertIn("Markdown", html)
        self.assertEqual(html.count("<textarea"), 2)  # notes for the one pair, and the Markdown output

    def test_ratings_script_is_valid_javascript(self):
        import shutil
        import subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        script = self.render().split("<script>")[1].split("</script>")[0]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "page.js"
            path.write_text(script, encoding="utf-8")
            proc = subprocess.run([node, "--check", str(path)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)


class ArmReportTest(unittest.TestCase):
    def results(self):
        ok = {"render_ok": True, "resolution_ok": True, "av_ok": True, "captions_ok": True,
              "resolution": "1280x720", "video_seconds": 400.0, "audio_seconds": 400.0,
              "av_difference_seconds": 0.0, "scenes": 20, "flagged": 0, "fallbacks": 0,
              "layout_pass_rate": 1.0, "captions": {"matched": 20, "scenes": 20, "cues": 20,
                                                    "similarity": 1.0, "pass": True}}
        base_probe = {"width": 1280, "height": 720, "video_seconds": 90.0, "audio_seconds": None}
        baseline = {"id": "01", "lang": "zh-TW", "preset": "explainer", "meta": {"num_turns": 7, "cost_usd": 0.5},
                    "seconds": 120.0, "errors": [], "copied_to": "x", "agent_reply": None, "final": None,
                    "metrics": run_eval.baseline_metrics("explainer", base_probe, True)}
        failed_baseline = dict(baseline, metrics=run_eval.baseline_metrics("explainer", None, False))
        skill = {"id": "01", "lang": "zh-TW", "preset": "explainer", "meta": {"num_turns": 30, "cost_usd": 2.0},
                 "seconds": 900.0, "errors": [], "copied_to": "x", "agent_reply": None, "final": {},
                 "metrics": ok, "baseline": baseline,
                 "mode_metrics": run_eval.mode_metrics("deep", "deep", 20, 400.0, MODES)}
        return skill, failed_baseline

    def test_aggregate_reports_baseline_totals_without_gating(self):
        skill, failed_baseline = self.results()
        agg = run_eval.aggregate([skill])
        self.assertEqual(agg["baseline"], {"topics": 1, "rendered": 1, "turns": 7, "cost_usd": 0.5, "seconds": 120.0})
        self.assertEqual(agg["verdict"], "PASS")
        self.assertEqual(agg["cost_usd"], 2.0)
        failing = dict(skill, baseline=failed_baseline)
        agg = run_eval.aggregate([failing])
        self.assertEqual(agg["baseline"]["rendered"], 0)
        self.assertEqual(agg["verdict"], "PASS")

    def test_aggregate_without_baseline(self):
        skill, _ = self.results()
        self.assertIsNone(run_eval.aggregate([dict(skill, baseline=None)])["baseline"])

    def test_report_has_both_arms_mode_cost_and_time(self):
        skill, _ = self.results()
        meta = {"timestamp": "20261009-120000", "model": None, "claude_version": "x", "scratch_root": "D:/s",
                "seed": "20261009-120000", "review": "review.html"}
        report = run_eval.render_report(meta, [skill], run_eval.aggregate([skill]))
        self.assertIn("Verdict (automated metrics, with-skill arm): PASS", report)
        self.assertIn("Baseline arm", report)
        self.assertIn("deep", report)
        self.assertIn("20 (15-30", report)
        self.assertIn("$2.00", report)
        self.assertIn("900 s", report)
        self.assertIn("$0.50", report)
        self.assertIn("120 s", report)
        self.assertIn("n/a", report)
        self.assertNotIn('"A"', report)


class ModeCellTest(unittest.TestCase):
    def test_cells(self):
        m = run_eval.mode_metrics("deep", "deep", 20, 700.0, MODES)
        cells = run_eval.mode_cells(m)
        self.assertEqual(cells[0], "deep")
        self.assertEqual(cells[1], "yes: 20 (15-30)")
        self.assertEqual(cells[2], "no: 700.0 s (300-600 s)")
        self.assertEqual(run_eval.mode_cells(None), ["n/a", "n/a", "n/a"])


if __name__ == "__main__":
    unittest.main()
