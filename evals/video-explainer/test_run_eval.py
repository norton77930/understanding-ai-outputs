"""Unit tests for the pure parts of run_eval.py (topic parsing, SRT, captions, metrics).

Run: python -m unittest discover -s evals/video-explainer -p "test_run_eval.py"
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_eval  # noqa: E402

TOPIC = """# Binary search

- Language: zh-TW
- Output preset: `explainer` (16:9, 720p)
- Target length: 60–90 s, 4–6 scenes

## Source

二分搜尋是在已排序的資料裡找目標值的方法。
第二行。

## Viewer should understand

- 一點。
"""

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

    def test_prompt_names_preset_and_preapproval(self):
        prompt = run_eval.build_prompt({"preset": "short", "source": "Text."})
        self.assertIn("using the short output preset", prompt)
        self.assertIn("do not wait for confirmation", prompt)
        self.assertTrue(prompt.rstrip().endswith("Text."))


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


if __name__ == "__main__":
    unittest.main()
