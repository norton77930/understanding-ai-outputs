"""CLI tests for skills/html-explainer/scripts/render_check.py.

All assertions use the JSON the render check prints and its exit code. The CLI
runs as a subprocess, the same way the agent runs it.

The missing-browser test needs only the standard library and runs in CI: it
points PLAYWRIGHT_BROWSERS_PATH at an empty folder and limits the candidates to
the bundled Chromium, so the check stops before it imports Playwright. The
render tests open a real headless browser through `uv run` and are skipped
unless the environment variable HTML_E2E=1 is set. They never download a
browser.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "html-explainer" / "scripts" / "render_check.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "html"


def run(cmd, env=None):
    env = dict(os.environ if env is None else env, PYTHONUTF8="1")
    proc = subprocess.run(cmd, capture_output=True, env=env)
    out = proc.stdout.decode("utf-8")
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        raise AssertionError(
            f"no JSON on stdout (exit {proc.returncode}): {out!r}\n"
            f"stderr: {proc.stderr.decode('utf-8', 'replace')}")
    return proc.returncode, data


class MissingBrowserTests(unittest.TestCase):
    def test_no_browser_exits_two_with_install_hint(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        env = dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=str(tmp / "empty"),
                   RENDER_CHECK_BROWSERS="bundled")
        code, data = run([sys.executable, str(SCRIPT), str(FIXTURES / "pass.html"),
                          "--out", str(tmp / "shots")], env)
        self.assertEqual(code, 2, data)
        self.assertFalse(data["pass"])
        self.assertIn("uv run --with playwright==1.62.* playwright install chromium",
                      data["hint"])
        self.assertIn("about 300 MB download", data["hint"])
        self.assertIn("PLAYWRIGHT_BROWSERS_PATH", data["hint"])
        self.assertFalse((tmp / "shots").exists())

    def test_missing_file_exits_two(self):
        code, data = run([sys.executable, str(SCRIPT), str(FIXTURES / "nope.html")])
        self.assertEqual(code, 2, data)
        self.assertFalse(data["pass"])

    def test_unknown_candidate_names_leave_no_browser(self):
        env = dict(os.environ, RENDER_CHECK_BROWSERS="firefox")
        code, data = run([sys.executable, str(SCRIPT), str(FIXTURES / "pass.html")], env)
        self.assertEqual(code, 2, data)
        self.assertIn("firefox", data["error"])


def load_render_check():
    spec = importlib.util.spec_from_file_location("render_check", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    with mock.patch.object(sys, "dont_write_bytecode", True):  # keep the skill folder clean
        spec.loader.exec_module(mod)
    return mod


def fake_chromium(root, build):
    """A Playwright Chromium folder with an executable for every platform."""
    folder = root / build
    for exe in ("chrome-win64/chrome.exe", "chrome-linux64/chrome"):
        (folder / exe).parent.mkdir(parents=True, exist_ok=True)
        (folder / exe).write_bytes(b"")
    (folder / "INSTALLATION_COMPLETE").write_bytes(b"")


class CandidateTests(unittest.TestCase):
    """Browser discovery, in-process: no Playwright and no browser needed."""

    def setUp(self):
        self.mod = load_render_check()
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        self.tmp = tmp

    def labels(self, env):
        with mock.patch.dict(os.environ, env):
            return [label for _, label in self.mod.candidate_list()]

    def test_render_check_browsers_sets_the_order(self):
        fake_chromium(self.tmp, "chromium-1234")
        labels = self.labels({"PLAYWRIGHT_BROWSERS_PATH": str(self.tmp),
                              "RENDER_CHECK_BROWSERS": "msedge, bundled,chrome"})
        self.assertEqual(labels[0], "msedge")
        self.assertEqual(labels[1], "playwright-chromium (default)")
        self.assertTrue(labels[2].startswith("playwright-chromium (chromium-1234"), labels)
        self.assertEqual(labels[-1], "chrome")

    def test_default_order_and_empty_bundled_folder(self):
        labels = self.labels({"PLAYWRIGHT_BROWSERS_PATH": str(self.tmp / "none"),
                              "RENDER_CHECK_BROWSERS": ""})
        self.assertEqual(labels, ["chrome", "msedge"])

    def test_newest_build_first(self):
        fake_chromium(self.tmp, "chromium-1100")
        fake_chromium(self.tmp, "chromium-1234")
        labels = self.labels({"PLAYWRIGHT_BROWSERS_PATH": str(self.tmp),
                              "RENDER_CHECK_BROWSERS": "bundled"})
        builds = [l for l in labels if "chromium-1" in l]
        self.assertIn("chromium-1234", builds[0])
        self.assertIn("chromium-1100", builds[-1])

    def test_browsers_path_zero_uses_package_local_browsers(self):
        package = self.tmp / "playwright"
        fake_chromium(package / "driver" / "package" / ".local-browsers", "chromium-1234")
        with mock.patch.object(self.mod, "playwright_package_dir", return_value=package):
            labels = self.labels({"PLAYWRIGHT_BROWSERS_PATH": "0",
                                  "RENDER_CHECK_BROWSERS": "bundled"})
        self.assertEqual(labels[0], "playwright-chromium (default)")
        self.assertIn("chromium-1234", labels[1])

    def test_browsers_path_zero_without_playwright_has_no_bundled(self):
        with mock.patch.object(self.mod, "playwright_package_dir", return_value=None):
            labels = self.labels({"PLAYWRIGHT_BROWSERS_PATH": "0",
                                  "RENDER_CHECK_BROWSERS": "bundled"})
        self.assertEqual(labels, [])


@unittest.skipUnless(os.environ.get("HTML_E2E") == "1",
                     "set HTML_E2E=1 to render in a local headless browser through uv")
class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def render(self, name):
        out = self.tmp / name
        return run(["uv", "run", "--script", str(SCRIPT), str(FIXTURES / name),
                    "--out", str(out)])

    def test_passing_fixture_gives_five_screenshots(self):
        code, data = self.render("pass.html")
        self.assertEqual(code, 0, data)
        self.assertTrue(data["pass"])
        self.assertEqual(data["console_errors"], [])
        self.assertEqual(data["page_errors"], [])
        self.assertFalse(data["overflow_390"]["overflow"])
        self.assertTrue(data["browser"])
        self.assertEqual(data["interaction"]["kind"], "button")
        self.assertEqual(len(data["screenshots"]), 5)
        for shot in data["screenshots"]:
            path = Path(shot)
            self.assertTrue(path.is_file(), shot)
            self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_throwing_fixture_exits_one_with_message(self):
        code, data = self.render("throws.html")
        self.assertEqual(code, 1, data)
        self.assertFalse(data["pass"])
        self.assertTrue(any("render-check fixture error" in e
                            for e in data["page_errors"]), data["page_errors"])

    def test_overflowing_fixture_exits_one(self):
        code, data = self.render("overflow.html")
        self.assertEqual(code, 1, data)
        self.assertFalse(data["pass"])
        o = data["overflow_390"]
        self.assertTrue(o["overflow"], o)
        self.assertGreater(o["scroll_width"], o["client_width"] + 1)
        self.assertEqual(data["interaction"]["kind"], "details")

    def test_disabled_and_inert_buttons_are_skipped(self):
        code, data = self.render("disabled-first.html")
        self.assertEqual(code, 0, data)
        self.assertEqual(data["interaction"]["kind"], "button")
        self.assertIn("next", data["interaction"]["selector"])
        self.assertIsNone(data["interaction_error"])
        self.assertEqual(len(data["screenshots"]), 5)

    def test_blocked_click_is_a_page_problem(self):
        code, data = self.render("covered.html")
        self.assertEqual(code, 1, data)
        self.assertFalse(data["pass"])
        self.assertEqual(data["interaction"]["kind"], "button")
        self.assertTrue(data["interaction_error"])
        self.assertEqual(len(data["screenshots"]), 4)
        self.assertFalse(data["overflow_390"]["overflow"])

    def test_checkbox_only_page_clicks_the_checkbox(self):
        code, data = self.render("checkbox.html")
        self.assertEqual(code, 0, data)
        self.assertEqual(data["interaction"]["kind"], "checkbox")
        self.assertEqual(len(data["screenshots"]), 5)


if __name__ == "__main__":
    unittest.main()
