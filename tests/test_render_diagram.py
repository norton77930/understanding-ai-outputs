"""CLI tests for skills/diagram-explainer/scripts/render_diagram.py.

All assertions use the JSON the renderer prints and its exit code. The
renderer is run as a subprocess, the same way the agent runs it.

CI-safe tests simulate a missing environment with DIAGRAM_RENDER_SIMULATE and
run under the current Python (no Playwright, no browser, no network needed).

Local end-to-end tests render in a real browser through `uv run`. They are
skipped unless DIAGRAM_E2E=1. They need uv, a browser that is already
installed (Playwright's Chromium, Chrome or Edge) and network access to
cdn.jsdelivr.net.
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
SCRIPT = ROOT / "skills" / "diagram-explainer" / "scripts" / "render_diagram.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "diagram"
SVG_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "svg"

E2E = os.environ.get("DIAGRAM_E2E") == "1"


def parse(proc):
    out = proc.stdout.decode("utf-8")
    return json.loads(out) if out.strip() else None


def run_python(*args, env_extra=None):
    """Run the renderer with the current Python (no uv)."""
    env = dict(os.environ)
    env.update(env_extra or {})
    proc = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          capture_output=True, env=env)
    return proc.returncode, parse(proc), proc.stderr.decode("utf-8", "replace")


def run_uv(*args, env_extra=None):
    """Run the renderer with `uv run`, as the agent does."""
    env = dict(os.environ)
    env.update(env_extra or {})
    proc = subprocess.run(["uv", "run", "--quiet", str(SCRIPT), *map(str, args)],
                          capture_output=True, timeout=300, env=env)
    return proc.returncode, parse(proc), proc.stderr.decode("utf-8", "replace")


KEYS = {"svg", "png", "width", "height", "mermaid_version", "browser", "error"}


class EnvironmentTests(unittest.TestCase):
    """CI-safe: the renderer reports a missing environment with exit 2."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.src = self.tmp / "d.mmd"
        shutil.copy(FIXTURES / "pass_flowchart.mmd", self.src)

    def test_no_browser_exits_2_with_install_hint(self):
        code, data, err = run_python(
            self.src, env_extra={"DIAGRAM_RENDER_SIMULATE": "no-browser"})
        self.assertEqual(code, 2, err)
        self.assertEqual(set(data), KEYS | {"hint"})
        self.assertIsNone(data["svg"])
        self.assertIsNone(data["png"])
        self.assertIsNone(data["browser"])
        self.assertIn("playwright install chromium", data["hint"])
        self.assertIn("PLAYWRIGHT_BROWSERS_PATH", data["hint"])
        self.assertIn("MB", data["hint"])

    def test_no_playwright_exits_2_with_uv_hint(self):
        code, data, err = run_python(
            self.src, env_extra={"DIAGRAM_RENDER_SIMULATE": "no-playwright"})
        self.assertEqual(code, 2, err)
        self.assertIn("uv run", data["hint"])
        self.assertIn("playwright", data["error"].lower())

    def test_no_files_written_when_environment_is_missing(self):
        run_python(self.src, env_extra={"DIAGRAM_RENDER_SIMULATE": "no-browser"})
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ["d.mmd"])

    def test_unexpected_exception_exits_2_with_one_json_object(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(self.src)], capture_output=True,
            env={**os.environ, "DIAGRAM_RENDER_SIMULATE": "crash"})
        self.assertEqual(proc.returncode, 2, proc.stderr)
        data = json.loads(proc.stdout.decode("utf-8"))  # exactly one object
        self.assertEqual(set(data), KEYS | {"hint"})
        self.assertIn("RuntimeError", data["error"])
        self.assertTrue(data["hint"])
        self.assertIsNone(data["svg"])

    def test_lazy_chunk_fetch_failure_exits_2_with_network_hint(self):
        code, data, err = run_python(
            self.src, env_extra={"DIAGRAM_RENDER_SIMULATE": "chunk-fetch-failure"})
        self.assertEqual(code, 2, (data, err))
        self.assertIn("Failed to fetch dynamically imported module", data["error"])
        self.assertIn("network", data["hint"].lower())
        self.assertIn("cdn.jsdelivr.net", data["hint"])
        self.assertIsNone(data["svg"])
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ["d.mmd"])

    def test_missing_input_file_exits_2(self):
        code, data, err = run_python(self.tmp / "nope.mmd")
        self.assertEqual(code, 2, err)
        self.assertIn("nope.mmd", data["error"])


class SvgEnvironmentTests(unittest.TestCase):
    """CI-safe: an .svg input follows the same environment rules."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.src = self.tmp / "d.svg"
        shutil.copy(SVG_FIXTURES / "pass_cjk.svg", self.src)

    def test_no_browser_exits_2_and_leaves_the_svg_alone(self):
        before = self.src.read_bytes()
        code, data, err = run_python(
            self.src, env_extra={"DIAGRAM_RENDER_SIMULATE": "no-browser"})
        self.assertEqual(code, 2, err)
        self.assertEqual(set(data), KEYS | {"hint"})
        self.assertIsNone(data["png"])
        self.assertIsNone(data["mermaid_version"])
        self.assertIn("playwright install chromium", data["hint"])
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ["d.svg"])
        self.assertEqual(self.src.read_bytes(), before)

    def test_no_playwright_exits_2_with_uv_hint(self):
        code, data, err = run_python(
            self.src, env_extra={"DIAGRAM_RENDER_SIMULATE": "no-playwright"})
        self.assertEqual(code, 2, err)
        self.assertIn("uv run", data["hint"])

    def test_missing_svg_exits_2(self):
        code, data, err = run_python(self.tmp / "nope.svg")
        self.assertEqual(code, 2, err)
        self.assertIn("nope.svg", data["error"])
        self.assertIsNone(data["mermaid_version"])


@unittest.skipUnless(E2E, "set DIAGRAM_E2E=1 to render in a real browser")
class RenderTests(unittest.TestCase):
    """Local only: render every fixture type in a real browser."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_each_fixture_type_renders_svg_and_png(self):
        for name in ("pass_flowchart", "pass_sequence", "pass_state", "cjk_flowchart"):
            with self.subTest(fixture=name):
                out = self.tmp / name
                code, data, err = run_uv(FIXTURES / f"{name}.mmd", "--out", out)
                self.assertEqual(code, 0, (data, err))
                self.assertEqual(set(data), KEYS)
                self.assertIsNone(data["error"])
                self.assertTrue(data["browser"])
                self.assertTrue(data["mermaid_version"].startswith("11."))
                svg, png = Path(data["svg"]), Path(data["png"])
                self.assertEqual(svg, out / f"{name}.svg")
                self.assertEqual(png, out / f"{name}.png")
                self.assertIn("<svg", svg.read_text(encoding="utf-8"))
                self.assertEqual(png.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
                self.assertGreater(png.stat().st_size, 5000)
                self.assertGreater(data["width"], 50)
                self.assertGreater(data["height"], 50)

    def test_default_out_is_next_to_input(self):
        src = self.tmp / "state.mmd"
        shutil.copy(FIXTURES / "pass_state.mmd", src)
        code, data, err = run_uv(src)
        self.assertEqual(code, 0, (data, err))
        self.assertEqual(Path(data["svg"]), self.tmp / "state.svg")
        self.assertTrue((self.tmp / "state.png").is_file())

    def test_broken_diagram_exits_1_with_mermaid_message(self):
        out = self.tmp / "broken"
        code, data, err = run_uv(FIXTURES / "broken_flowchart.mmd", "--out", out)
        self.assertEqual(code, 1, (data, err))
        self.assertIn("Parse error", data["error"])
        self.assertIsNone(data["svg"])
        self.assertIsNone(data["png"])
        self.assertFalse(out.exists() and any(out.iterdir()))

    def test_utf8_bom_in_input_is_ignored(self):
        src = self.tmp / "bom.mmd"
        src.write_bytes(b"\xef\xbb\xbf" + (FIXTURES / "pass_state.mmd").read_bytes())
        code, data, err = run_uv(src)
        self.assertEqual(code, 0, (data, err))
        self.assertTrue(Path(data["png"]).is_file())

    def test_render_timeout_exits_1_and_writes_nothing(self):
        out = self.tmp / "slow"
        code, data, err = run_uv(FIXTURES / "pass_flowchart.mmd", "--out", out,
                                 env_extra={"DIAGRAM_RENDER_TIMEOUT_MS": "1"})
        self.assertEqual(code, 1, (data, err))
        self.assertIn("render timed out", data["error"].lower())
        self.assertIsNone(data["svg"])
        self.assertIsNone(data["png"])
        self.assertFalse(out.exists() and any(out.iterdir()))


@unittest.skipUnless(E2E, "set DIAGRAM_E2E=1 to render in a real browser")
class SvgRenderTests(unittest.TestCase):
    """Local only: render a hand-written SVG to PNG in a real browser."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_svg_renders_png_next_to_it_and_is_not_rewritten(self):
        src = self.tmp / "diagram.svg"
        shutil.copy(SVG_FIXTURES / "pass_cjk.svg", src)
        before = src.read_bytes()
        code, data, err = run_uv(src)
        self.assertEqual(code, 0, (data, err))
        self.assertEqual(set(data), KEYS)
        self.assertIsNone(data["mermaid_version"])
        self.assertEqual(Path(data["svg"]), src)
        self.assertEqual(Path(data["png"]), self.tmp / "diagram.png")
        self.assertEqual(src.read_bytes(), before)
        png = Path(data["png"]).read_bytes()
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        # viewBox 800 x 340 at device scale 2.
        self.assertEqual((data["width"], data["height"]), (1600, 680))

    def test_out_folder_gets_only_the_png(self):
        out = self.tmp / "out"
        code, data, err = run_uv(SVG_FIXTURES / "pass_cjk.svg", "--out", out)
        self.assertEqual(code, 0, (data, err))
        self.assertEqual(sorted(p.name for p in out.iterdir()), ["pass_cjk.png"])

    def test_broken_svg_exits_1_and_writes_nothing(self):
        out = self.tmp / "broken"
        code, data, err = run_uv(SVG_FIXTURES / "not_xml.svg", "--out", out)
        self.assertEqual(code, 1, (data, err))
        self.assertTrue(data["error"])
        self.assertIsNone(data["png"])
        self.assertFalse(out.exists() and any(out.iterdir()))


if __name__ == "__main__":
    unittest.main()
