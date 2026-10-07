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

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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
        self.assertIn("playwright install chromium", data["hint"])
        self.assertIn("MB", data["hint"])
        self.assertIn("PLAYWRIGHT_BROWSERS_PATH", data["hint"])
        self.assertFalse((tmp / "shots").exists())

    def test_missing_file_exits_two(self):
        code, data = run([sys.executable, str(SCRIPT), str(FIXTURES / "nope.html")])
        self.assertEqual(code, 2, data)
        self.assertFalse(data["pass"])


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


if __name__ == "__main__":
    unittest.main()
