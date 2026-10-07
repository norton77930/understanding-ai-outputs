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


def run(cmd, cwd=None, env=None):
    env = dict(os.environ if env is None else env, PYTHONUTF8="1")
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


KOKORO_EN_FILES = ("kokoro-v1.0.onnx", "voices-v1.0.bin")
KOKORO_ZH_FILES = ("kokoro-v1.1-zh.onnx", "voices-v1.1-zh.bin", "config-v1.1-zh.json")


class EngineSelectionTests(unittest.TestCase):
    """`plan` engine selection. No network: VIDEO_EXPLAINER_OFFLINE states it."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.cache = self.tmp / "cache"
        self.cache.mkdir()

    def install_models(self, names):
        folder = self.cache / "kokoro"
        folder.mkdir(exist_ok=True)
        for name in names:
            (folder / name).write_bytes(b"stub")

    def plan(self, lang, engine=None, preset="explainer", offline=False):
        board = load_storyboard()
        board.update(lang=lang, engine=engine, preset=preset)
        if lang.startswith("zh"):
            board["scenes"] = [{"id": "s1", "narration": "先看正中間的那一個數字。"}]
        path = self.tmp / "storyboard.json"
        path.write_text(json.dumps(board, ensure_ascii=False), encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if k != "VIDEO_EXPLAINER_OFFLINE"}
        env["VIDEO_EXPLAINER_CACHE"] = str(self.cache)
        if offline:
            env["VIDEO_EXPLAINER_OFFLINE"] = "1"
        return run([sys.executable, str(SCRIPT), "plan", str(path),
                    "--out", str(self.tmp / "out")], env=env)

    def plan_with_preset(self, preset, **kwargs):
        code, data = self.plan(preset=preset, **kwargs)
        if code == 1 and any(f"unknown preset {preset!r}" in e for e in data["errors"]):
            self.skipTest(f"preset {preset!r} is not defined yet (#19)")
        return code, data

    def test_english_uses_kokoro(self):
        self.install_models(KOKORO_EN_FILES)
        code, data = self.plan("en")
        self.assertEqual(code, 0, data)
        self.assertEqual((data["engine"]["name"], data["engine"]["voice"]), ("kokoro", "af_heart"))
        self.assertEqual(data["downloads"], [])
        self.assertFalse(any(re.search("edge-tts|fetch-models", n) for n in data["notices"]),
                         data["notices"])

    def test_zh_tw_uses_edge_tts_when_network_is_not_ruled_out(self):
        code, data = self.plan("zh-TW")
        self.assertEqual(code, 0, data)
        self.assertEqual((data["engine"]["name"], data["engine"]["voice"]),
                         ("edge-tts", "zh-TW-HsiaoChenNeural"))
        self.assertEqual(data["engine"]["fallback"], {"name": "kokoro", "voice": "zf_001"})
        self.assertFalse(any("mainland" in n for n in data["notices"]), data["notices"])

    def test_zh_tw_offline_falls_back_to_kokoro_chinese_with_notice(self):
        self.install_models(KOKORO_ZH_FILES)
        code, data = self.plan("zh-TW", offline=True)
        self.assertEqual(code, 0, data)
        self.assertEqual((data["engine"]["name"], data["engine"]["voice"]), ("kokoro", "zf_001"))
        self.assertTrue(any("mainland Mandarin accent" in n for n in data["notices"]),
                        data["notices"])
        self.assertEqual(data["downloads"], [])

    def test_user_engine_and_voice_override_wins(self):
        code, data = self.plan("zh-TW", engine={"name": "kokoro", "voice": "zm_010"})
        self.assertEqual(code, 0, data)
        self.assertEqual((data["engine"]["name"], data["engine"]["voice"]), ("kokoro", "zm_010"))
        self.assertFalse(any("mainland" in n for n in data["notices"]), data["notices"])

    def test_user_engine_name_override_wins_with_language_voice(self):
        code, data = self.plan("en", engine="silent")
        self.assertEqual(code, 0, data)
        self.assertEqual(data["engine"]["name"], "silent")
        code, data = self.plan("zh-TW", engine="kokoro", offline=True)
        self.assertEqual(code, 0, data)
        self.assertEqual((data["engine"]["name"], data["engine"]["voice"]), ("kokoro", "zf_001"))

    def test_youtube_preset_with_edge_tts_adds_publishing_notice(self):
        code, data = self.plan_with_preset("youtube", lang="zh-TW")
        self.assertEqual(code, 0, data)
        self.assertEqual(data["engine"]["name"], "edge-tts")
        self.assertTrue(any("unofficial" in n and "Kokoro" in n for n in data["notices"]),
                        data["notices"])

    def test_short_preset_with_edge_tts_adds_publishing_notice(self):
        code, data = self.plan_with_preset("short", lang="zh-TW")
        self.assertEqual(code, 0, data)
        self.assertTrue(any("unofficial" in n and "Kokoro" in n for n in data["notices"]),
                        data["notices"])

    def test_explainer_preset_with_edge_tts_has_no_publishing_notice(self):
        code, data = self.plan("zh-TW")
        self.assertEqual(code, 0, data)
        self.assertFalse(any("unofficial" in n for n in data["notices"]), data["notices"])

    def test_other_language_uses_kokoro_when_it_has_a_voice(self):
        self.install_models(KOKORO_EN_FILES)
        code, data = self.plan("fr")
        self.assertEqual(code, 0, data)
        self.assertEqual((data["engine"]["name"], data["engine"]["voice"]), ("kokoro", "ff_siwis"))

    def test_unsupported_language_is_a_check_failure(self):
        code, data = self.plan("de")
        self.assertEqual(code, 1, data)
        self.assertFalse(data["ok"])
        self.assertTrue(any("'de'" in e for e in data["errors"]), data["errors"])

    def test_missing_models_are_listed_as_downloads(self):
        code, data = self.plan("en")
        self.assertEqual(code, 0, data)
        names = [d["name"] for d in data["downloads"]]
        self.assertEqual(names, list(KOKORO_EN_FILES))
        for d in data["downloads"]:
            self.assertTrue(d["url"].startswith("https://"), d)
            self.assertGreater(d["size_mb"], 0)
        self.assertEqual(Path(data["cache_dir"]), self.cache)
        self.assertTrue(any("fetch-models" in n for n in data["notices"]), data["notices"])

    def test_offline_zh_tw_lists_chinese_model_downloads(self):
        code, data = self.plan("zh-TW", offline=True)
        self.assertEqual(code, 0, data)
        self.assertEqual([d["name"] for d in data["downloads"]], list(KOKORO_ZH_FILES))

    def test_fetch_models_keeps_files_already_in_the_cache(self):
        self.install_models(KOKORO_EN_FILES)
        env = dict(os.environ, VIDEO_EXPLAINER_CACHE=str(self.cache))
        code, data = run([sys.executable, str(SCRIPT), "fetch-models", "kokoro-en"], env=env)
        self.assertEqual(code, 0, data)
        self.assertEqual([f["name"] for f in data["files"]], list(KOKORO_EN_FILES))
        self.assertFalse(any(f["downloaded"] for f in data["files"]))


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


STORYBOARD_ZH = FIXTURES / "storyboard_zh.json"
SCENES_ZH = FIXTURES / "scenes_zh.py"


@unittest.skipUnless(os.environ.get("VIDEO_E2E") == "1",
                     "set VIDEO_E2E=1 to render with real narration engines")
class NarrationEngineEndToEndTests(unittest.TestCase):
    """Kokoro (en), edge-tts (zh-TW) and the offline zh-TW fallback.

    Needs uv, ffmpeg, network for edge-tts, and the Kokoro models in the cache
    dir (VIDEO_EXPLAINER_CACHE or the user cache dir; see `fetch-models`).
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        base = ["uv", "run", "--script", str(SCRIPT)]
        online = {k: v for k, v in os.environ.items() if k != "VIDEO_EXPLAINER_OFFLINE"}
        en = load_storyboard()
        en.update(slug="tiny-halving-kokoro", engine=None)
        en_path = cls.tmp / "storyboard_en.json"
        en_path.write_text(json.dumps(en), encoding="utf-8")
        cls.runs = {}
        for key, board, scenes, commands, env in [
                ("en", en_path, SCENES, ("preview", "final"), online),
                ("zh", STORYBOARD_ZH, SCENES_ZH, ("preview", "final"), online),
                ("zh-offline", STORYBOARD_ZH, SCENES_ZH, ("preview",),
                 dict(online, VIDEO_EXPLAINER_OFFLINE="1"))]:
            out = cls.tmp / key
            for command in commands:
                cls.runs[key, command] = run(base + [command, str(board), str(scenes),
                                                     "--out", str(out)], env=env)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def result(self, key, command):
        code, data = self.runs[key, command]
        self.assertEqual(code, 0, data)
        return data

    def assert_video_matches_audio(self, final):
        v = ffprobe_seconds(Path(final["video"]), "v:0")
        a = ffprobe_seconds(Path(final["video"]), "a:0")
        self.assertLessEqual(abs(v - a), 0.3, (v, a))
        self.assertLessEqual(abs(final["difference_seconds"]), 0.3, final)

    def test_english_renders_with_kokoro(self):
        final = self.result("en", "final")
        self.assertEqual((final["engine"]["name"], final["engine"]["voice"]),
                         ("kokoro", "af_heart"))
        self.assert_video_matches_audio(final)

    def test_zh_tw_renders_with_edge_tts(self):
        final = self.result("zh", "final")
        self.assertEqual((final["engine"]["name"], final["engine"]["voice"]),
                         ("edge-tts", "zh-TW-HsiaoChenNeural"))
        self.assert_video_matches_audio(final)

    def test_final_reuses_preview_narration(self):
        for key in ("en", "zh"):
            preview, final = self.result(key, "preview"), self.result(key, "final")
            self.assertFalse(any(s["audio_reused"] for s in preview["scenes"]), preview)
            self.assertTrue(all(s["audio_reused"] for s in final["scenes"]), final)
            self.assertEqual([s["duration"] for s in preview["scenes"]],
                             [s["duration"] for s in final["scenes"]])

    def test_offline_zh_tw_falls_back_to_kokoro_chinese(self):
        preview = self.result("zh-offline", "preview")
        self.assertEqual((preview["engine"]["name"], preview["engine"]["voice"]),
                         ("kokoro", "zf_001"))
        self.assertTrue(any("mainland Mandarin accent" in n for n in preview["notices"]),
                        preview["notices"])
        self.assertTrue(all(Path(s["frame"]).is_file() for s in preview["scenes"]))

    def test_no_model_files_inside_the_project(self):
        # prototypes/ holds untracked throwaway prototype files, not skill output.
        roots = [p for p in ROOT.iterdir() if p.name not in (".git", "prototypes")]
        roots.append(self.tmp)
        found = [p for root in roots if root.is_dir()
                 for pattern in ("kokoro*.onnx", "voices*.bin") for p in root.rglob(pattern)]
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
