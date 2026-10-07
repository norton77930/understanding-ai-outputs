"""CLI tests for skills/video-explainer/scripts/doctor.py.

The doctor is run as a subprocess, the same way the agent runs it. The tests
simulate the machine through the doctor's environment overrides: fake
executables in a temp dir, fake font files in temp dirs, and a temp cache
dir. Nothing here touches the real system or the network.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "video-explainer" / "scripts" / "doctor.py"

WINDOWS = os.name == "nt"
ALL_TOOLS = ("uv", "ffmpeg", "ffprobe")


def make_tool(directory, name):
    """Create a fake executable that exits with $FAKE_TOOL_EXIT (default 0)."""
    if WINDOWS:
        path = Path(directory) / f"{name}.cmd"
        path.write_text(
            '@if "%FAKE_TOOL_EXIT%"=="" (exit /b 0) else (exit /b %FAKE_TOOL_EXIT%)\r\n',
            encoding="utf-8",
        )
    else:
        path = Path(directory) / name
        path.write_text('#!/bin/sh\nexit "${FAKE_TOOL_EXIT:-0}"\n', encoding="utf-8")
        path.chmod(0o755)
    return path


def touch(directory, name):
    path = Path(directory) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


class DoctorCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.bin = self.tmp / "bin"
        self.cache = self.tmp / "cache"
        self.fonts = self.tmp / "fonts"
        for d in (self.bin, self.cache, self.fonts):
            d.mkdir()

    def tools(self, names=ALL_TOOLS):
        for name in names:
            make_tool(self.bin, name)

    def run_doctor(self, *args, fonts=None, **env_extra):
        env = dict(os.environ)
        env["VIDEO_EXPLAINER_DOCTOR_PATH"] = str(self.bin)
        env["VIDEO_EXPLAINER_CACHE"] = str(self.cache)
        env["VIDEO_EXPLAINER_FONT_DIRS"] = os.pathsep.join(
            str(d) for d in (fonts if fonts is not None else [self.fonts])
        )
        env["VIDEO_EXPLAINER_OFFLINE"] = "1"
        env.pop("FAKE_TOOL_EXIT", None)
        env.update(env_extra)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True,
            env=env,
            cwd=self.tmp,
        )
        out = proc.stdout.decode("utf-8")
        data = json.loads(out) if out.strip() else None
        return proc.returncode, data


class CapabilityTests(DoctorCase):
    def test_all_present_reports_each_capability(self):
        self.tools()
        for model in ("kokoro-v1.0.onnx", "voices-v1.0.bin"):
            touch(self.cache / "kokoro", model)
        code, data = self.run_doctor()
        self.assertEqual(code, 0)
        self.assertTrue(data["ready"])
        caps = data["capabilities"]
        self.assertEqual(
            set(caps), {"uv", "ffmpeg", "ffprobe", "manim", "kokoro_models", "edge_tts_network"}
        )
        for name in ("uv", "ffmpeg", "ffprobe", "manim", "kokoro_models"):
            self.assertTrue(caps[name]["available"], name)
            self.assertIsNone(caps[name]["hint"], name)
        for cap in caps.values():
            self.assertEqual(set(cap) - {"skipped"}, {"available", "hint"})

    def test_missing_ffmpeg_exits_2_with_hint(self):
        self.tools(("uv", "ffprobe"))
        code, data = self.run_doctor()
        self.assertEqual(code, 2)
        self.assertFalse(data["ready"])
        cap = data["capabilities"]["ffmpeg"]
        self.assertFalse(cap["available"])
        self.assertIn("ffmpeg", cap["hint"])
        self.assertTrue(data["capabilities"]["uv"]["available"])

    def test_missing_uv_exits_2_and_manim_is_unavailable(self):
        self.tools(("ffmpeg", "ffprobe"))
        code, data = self.run_doctor()
        self.assertEqual(code, 2)
        self.assertFalse(data["capabilities"]["uv"]["available"])
        self.assertIn("uv", data["capabilities"]["uv"]["hint"])
        self.assertFalse(data["capabilities"]["manim"]["available"])
        self.assertIsInstance(data["capabilities"]["manim"]["hint"], str)

    def test_missing_ffprobe_exits_2(self):
        self.tools(("uv", "ffmpeg"))
        code, data = self.run_doctor()
        self.assertEqual(code, 2)
        self.assertFalse(data["capabilities"]["ffprobe"]["available"])
        self.assertIsInstance(data["capabilities"]["ffprobe"]["hint"], str)

    def test_nothing_on_path_exits_2(self):
        code, data = self.run_doctor()
        self.assertEqual(code, 2)
        for name in ALL_TOOLS:
            self.assertFalse(data["capabilities"][name]["available"], name)

    def test_failing_manim_import_is_unavailable_but_not_fatal(self):
        self.tools()
        code, data = self.run_doctor(FAKE_TOOL_EXIT="1")
        self.assertEqual(code, 0)
        manim = data["capabilities"]["manim"]
        self.assertFalse(manim["available"])
        self.assertIn("manim", manim["hint"])

    def test_quick_skips_manim_probe(self):
        self.tools()
        code, data = self.run_doctor("--quick", FAKE_TOOL_EXIT="1")
        self.assertEqual(code, 0)
        manim = data["capabilities"]["manim"]
        self.assertFalse(manim["available"])
        self.assertTrue(manim["skipped"])

    def test_quick_skips_network_probe(self):
        self.tools()
        _, data = self.run_doctor("--quick", VIDEO_EXPLAINER_OFFLINE="")
        net = data["capabilities"]["edge_tts_network"]
        self.assertFalse(net["available"])
        self.assertTrue(net["skipped"])


class KokoroModelTests(DoctorCase):
    def test_missing_models_report_hint_with_cache_dir(self):
        self.tools()
        code, data = self.run_doctor()
        self.assertEqual(code, 0)
        cap = data["capabilities"]["kokoro_models"]
        self.assertFalse(cap["available"])
        self.assertIn(str(self.cache), cap["hint"])

    def test_partial_models_are_unavailable(self):
        self.tools()
        touch(self.cache / "kokoro", "kokoro-v1.0.onnx")
        _, data = self.run_doctor()
        self.assertFalse(data["capabilities"]["kokoro_models"]["available"])

    def test_cache_dir_is_reported_and_follows_env(self):
        self.tools()
        _, data = self.run_doctor()
        self.assertEqual(data["cache_dir"], str(self.cache))

    def test_default_cache_dir_ends_with_skill_path(self):
        self.tools()
        env = dict(os.environ)
        env["VIDEO_EXPLAINER_DOCTOR_PATH"] = str(self.bin)
        env["VIDEO_EXPLAINER_FONT_DIRS"] = str(self.fonts)
        env["VIDEO_EXPLAINER_OFFLINE"] = "1"
        env.pop("VIDEO_EXPLAINER_CACHE", None)
        proc = subprocess.run([sys.executable, str(SCRIPT), "--quick"],
                              capture_output=True, env=env, cwd=self.tmp)
        data = json.loads(proc.stdout.decode("utf-8"))
        parts = Path(data["cache_dir"]).parts
        self.assertEqual(parts[-2:], ("understanding-ai-outputs", "video-explainer"))


class NetworkTests(DoctorCase):
    def test_offline_override_reports_unavailable_with_hint(self):
        self.tools()
        code, data = self.run_doctor()
        self.assertEqual(code, 0)
        net = data["capabilities"]["edge_tts_network"]
        self.assertFalse(net["available"])
        self.assertIsInstance(net["hint"], str)
        self.assertNotIn("skipped", net)


class FontTests(DoctorCase):
    def setUp(self):
        super().setUp()
        self.tools()
        self.noto_dir = self.tmp / "noto"
        self.mac_dir = self.tmp / "mac"
        self.win_dir = self.tmp / "win"
        for d in (self.noto_dir, self.mac_dir, self.win_dir):
            d.mkdir()

    def font(self, *dirs):
        code, data = self.run_doctor(fonts=dirs)
        self.assertEqual(code, 0)
        return data

    def test_jhenghei_wins_over_the_others(self):
        touch(self.noto_dir, "NotoSansCJK-Regular.ttc")
        touch(self.mac_dir, "PingFang.ttc")
        touch(self.win_dir, "msjh.ttc")
        data = self.font(self.noto_dir, self.mac_dir, self.win_dir)
        self.assertEqual(data["font"], "Microsoft JhengHei")
        self.assertTrue(data["font_path"].lower().endswith("msjh.ttc"))
        self.assertIsNone(data["font_hint"])

    def test_pingfang_wins_over_noto(self):
        touch(self.noto_dir, "NotoSansCJK-Regular.ttc")
        touch(self.mac_dir, "PingFang.ttc")
        data = self.font(self.noto_dir, self.mac_dir)
        self.assertEqual(data["font"], "PingFang TC")

    def test_noto_is_last_choice(self):
        touch(self.noto_dir, "NotoSansCJK-Regular.ttc")
        data = self.font(self.noto_dir)
        self.assertEqual(data["font"], "Noto Sans CJK TC")

    def test_font_files_are_found_in_subdirectories_and_any_case(self):
        touch(self.win_dir / "deep" / "er", "MSJH.TTC")
        self.assertEqual(self.font(self.win_dir)["font"], "Microsoft JhengHei")

    def test_unrelated_fonts_do_not_count(self):
        touch(self.noto_dir, "NotoSansJP-Regular.otf")
        touch(self.noto_dir, "arial.ttf")
        data = self.font(self.noto_dir)
        self.assertIsNone(data["font"])

    def test_no_font_reports_null_and_hint_but_exit_0(self):
        data = self.font(self.noto_dir)
        self.assertIsNone(data["font"])
        self.assertIsNone(data["font_path"])
        self.assertIsInstance(data["font_hint"], str)

    def test_missing_font_dir_is_ignored(self):
        data = self.font(self.tmp / "nope")
        self.assertIsNone(data["font"])


class OutputTests(DoctorCase):
    def test_output_has_the_settled_keys(self):
        self.tools()
        _, data = self.run_doctor()
        self.assertEqual(
            set(data),
            {"ready", "capabilities", "font", "font_path", "font_hint", "cache_dir"},
        )

    def test_output_is_utf8_json_even_with_non_ascii_paths(self):
        self.tools()
        cache = self.tmp / "快取"
        cache.mkdir()
        code, data = self.run_doctor(VIDEO_EXPLAINER_CACHE=str(cache))
        self.assertEqual(code, 0)
        self.assertEqual(data["cache_dir"], str(cache))


if __name__ == "__main__":
    unittest.main()
