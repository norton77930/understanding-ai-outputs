"""CLI tests for skills/video-explainer/scripts/make_video.py.

All assertions use the JSON the orchestrator prints, its exit code and the
files it writes. The CLI runs as a subprocess, the same way the agent runs it.

`plan` tests need only the standard library and run in CI. The `preview` and
`final` tests render with ManimCE through `uv run` and are skipped unless the
environment variable VIDEO_E2E=1 is set.
"""

import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "video-explainer" / "scripts" / "make_video.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "video"
STORYBOARD = FIXTURES / "storyboard.json"
SCENES = FIXTURES / "scenes.py"


def load_storyboard():
    return json.loads(STORYBOARD.read_text(encoding="utf-8"))


def run(cmd, cwd=None):
    env = dict(os.environ, PYTHONUTF8="1")
    proc = subprocess.run(cmd, capture_output=True, cwd=cwd, env=env)
    out = proc.stdout.decode("utf-8")
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        raise AssertionError(
            f"stdout is not one JSON object (exit {proc.returncode}):\n{out}\n"
            f"stderr:\n{proc.stderr.decode('utf-8', 'replace')[-3000:]}")
    return proc.returncode, data


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def plan(self, storyboard):
        path = self.tmp / "storyboard.json"
        path.write_text(json.dumps(storyboard, ensure_ascii=False), encoding="utf-8")
        return run([sys.executable, str(SCRIPT), "plan", str(path),
                    "--out", str(self.tmp / "out")])

    def assert_invalid(self, storyboard, pattern):
        code, data = self.plan(storyboard)
        self.assertEqual(code, 1, data)
        self.assertFalse(data["ok"])
        self.assertTrue(any(re.search(pattern, e) for e in data["errors"]), data["errors"])

    def test_valid_storyboard_returns_estimates(self):
        code, data = self.plan(load_storyboard())
        self.assertEqual(code, 0, data)
        self.assertTrue(data["ok"])
        self.assertEqual(data["engine"]["name"], "silent")
        self.assertEqual(data["preset"]["name"], "explainer")
        self.assertEqual((data["preset"]["width"], data["preset"]["height"],
                          data["preset"]["fps"]), (1280, 720, 30))
        self.assertEqual([s["id"] for s in data["scenes"]], ["s1", "s2", "s3"])
        for scene in data["scenes"]:
            self.assertGreater(scene["estimated_seconds"], 0)
            self.assertTrue(scene["captions"])
        total = sum(s["estimated_seconds"] for s in data["scenes"])
        self.assertAlmostEqual(data["estimated_total_seconds"], total, places=2)
        self.assertGreater(data["estimated_render_seconds"]["preview"], 0)
        self.assertGreater(data["estimated_render_seconds"]["final"], 0)
        self.assertTrue((self.tmp / "out" / "plan.json").is_file())

    def test_english_estimate_follows_word_count(self):
        board = load_storyboard()
        board["scenes"] = [{"id": "a", "narration": " ".join(["word"] * 28)},
                           {"id": "b", "narration": " ".join(["word"] * 56)}]
        code, data = self.plan(board)
        self.assertEqual(code, 0, data)
        a, b = (s["estimated_seconds"] for s in data["scenes"])
        self.assertGreater(b, a)
        # About 168 words per minute: 28 words take about 10 s plus a short pad.
        self.assertTrue(9 < a < 12, a)

    def test_chinese_estimate_follows_hanzi_count(self):
        board = load_storyboard()
        board["lang"] = "zh-TW"
        board["scenes"] = [{"id": "a", "narration": "要在十六個由小到大排好的數字裡找三十七。先看正中間的那一個。"}]
        code, data = self.plan(board)
        self.assertEqual(code, 0, data)
        seconds = data["scenes"][0]["estimated_seconds"]
        # 28 hanzi at about 3 hanzi/s.
        self.assertTrue(8.5 < seconds < 11.5, seconds)
        self.assertTrue(all(len(line) <= 20 for line in data["scenes"][0]["captions"]))

    def test_long_english_narration_is_split_into_caption_lines(self):
        board = load_storyboard()
        board["scenes"] = [{"id": "a", "narration": "This is the first sentence of the scene. "
                            "This second sentence is a bit longer than the first one is."}]
        code, data = self.plan(board)
        self.assertEqual(code, 0, data)
        captions = data["scenes"][0]["captions"]
        self.assertGreaterEqual(len(captions), 2)
        self.assertTrue(all(len(line) <= 42 for line in captions), captions)

    def test_missing_scenes_is_invalid(self):
        board = load_storyboard()
        del board["scenes"]
        self.assert_invalid(board, "scenes")

    def test_empty_scenes_is_invalid(self):
        board = load_storyboard()
        board["scenes"] = []
        self.assert_invalid(board, "scenes")

    def test_duplicate_scene_ids_are_invalid(self):
        board = load_storyboard()
        board["scenes"][1]["id"] = "s1"
        self.assert_invalid(board, "duplicate.*s1")

    def test_unknown_preset_is_invalid(self):
        board = load_storyboard()
        board["preset"] = "cinema"
        self.assert_invalid(board, "preset.*cinema")

    def test_bad_slug_is_invalid(self):
        board = load_storyboard()
        board["slug"] = "Binary Search!"
        self.assert_invalid(board, "slug")

    def test_empty_narration_is_invalid(self):
        board = load_storyboard()
        board["scenes"][0]["narration"] = "   "
        self.assert_invalid(board, "narration.*s1")

    def test_unknown_engine_is_invalid(self):
        board = load_storyboard()
        board["engine"] = "nope-tts"
        self.assert_invalid(board, "engine.*nope-tts")

    def test_unreadable_storyboard_is_invalid(self):
        path = self.tmp / "broken.json"
        path.write_text("{not json", encoding="utf-8")
        code, data = run([sys.executable, str(SCRIPT), "plan", str(path),
                          "--out", str(self.tmp / "out")])
        self.assertEqual(code, 1, data)
        self.assertFalse(data["ok"])


def ffprobe_seconds(path, stream):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries",
         "stream=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True).stdout.strip()
    return float(out.splitlines()[0])


def ffprobe_size(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True).stdout.strip()
    return tuple(int(x) for x in out.split(","))


def srt_seconds(stamp):
    h, m, rest = stamp.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


@unittest.skipUnless(os.environ.get("VIDEO_E2E") == "1",
                     "set VIDEO_E2E=1 to render with ManimCE through uv")
class EndToEndTests(unittest.TestCase):
    """Preview and final with the silent engine. Needs uv, ffmpeg and ManimCE."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.out = cls.tmp / "out"
        base = ["uv", "run", "--script", str(SCRIPT)]
        args = [str(STORYBOARD), str(SCENES), "--out", str(cls.out)]
        cls.preview_code, cls.preview = run(base + ["preview"] + args)
        cls.final_code, cls.final = run(base + ["final"] + args)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_preview_writes_one_frame_per_scene(self):
        self.assertEqual(self.preview_code, 0, self.preview)
        scenes = self.preview["scenes"]
        self.assertEqual([s["id"] for s in scenes], ["s1", "s2", "s3"])
        for scene in scenes:
            self.assertTrue(Path(scene["frame"]).is_file(), scene["frame"])
            self.assertGreater(scene["duration"], 0)
            self.assertEqual(scene["words"], [])

    def test_final_writes_video_srt_and_script(self):
        self.assertEqual(self.final_code, 0, self.final)
        video = Path(self.final["video"])
        self.assertEqual(ffprobe_size(video), (1280, 720))
        self.assertTrue(Path(self.final["srt"]).is_file())
        script = Path(self.final["script"]).read_text(encoding="utf-8")
        for scene in load_storyboard()["scenes"]:
            self.assertIn(scene["narration"], script)

    def test_video_length_matches_audio(self):
        self.assertEqual(self.final_code, 0, self.final)
        video = Path(self.final["video"])
        v = ffprobe_seconds(video, "v:0")
        a = sum(s["duration"] for s in self.final["scenes"])
        self.assertLessEqual(abs(v - a), 0.3, (v, a))
        self.assertLessEqual(abs(self.final["video_seconds"] - self.final["audio_seconds"]), 0.3)

    def test_srt_cues_match_scene_timing(self):
        self.assertEqual(self.final_code, 0, self.final)
        text = Path(self.final["srt"]).read_text(encoding="utf-8")
        cues = re.findall(r"(\d\d:\d\d:\d\d,\d\d\d) --> (\d\d:\d\d:\d\d,\d\d\d)", text)
        scenes = self.final["scenes"]
        self.assertEqual(len(cues), len(scenes))
        for (start, end), scene in zip(cues, scenes):
            self.assertAlmostEqual(srt_seconds(start), scene["start"], delta=0.002)
            self.assertAlmostEqual(srt_seconds(end), scene["end"], delta=0.002)
            self.assertAlmostEqual(scene["end"] - scene["start"], scene["duration"], delta=0.002)


if __name__ == "__main__":
    unittest.main()
