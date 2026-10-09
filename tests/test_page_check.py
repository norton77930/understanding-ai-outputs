"""CLI tests for skills/html-explainer/scripts/page_check.py.

All assertions use the JSON the checker prints. The checker is run as a
subprocess, the same way the agent and the evals run it. Per-rule cases mutate
the passing fixture into a temporary file.
"""

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "html-explainer" / "scripts" / "page_check.py"
PASS_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "html" / "pass.html"


def run(path, *args):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(path), *args], capture_output=True)
    out = proc.stdout.decode("utf-8")
    data = json.loads(out) if out.strip() else None
    return proc.returncode, data


class PageCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.base = PASS_FIXTURE.read_text(encoding="utf-8")

    def check(self, html, *args, name="page.html"):
        path = self.tmp / name
        path.write_bytes(html.encode("utf-8"))
        return run(path, *args)

    def mutate(self, old, new, *args):
        self.assertIn(old, self.base, "fixture no longer contains the mutated text")
        return self.check(self.base.replace(old, new, 1), *args)

    def rules(self, data):
        return [i["rule"] for i in data["issues"]]

    def assert_fails_only(self, code, data, rule):
        self.assertEqual(code, 1, data)
        self.assertEqual(self.rules(data), [rule], data["issues"])
        self.assertFalse(data["pass"])


class PassingFixtureTests(PageCase):
    def test_passing_fixture_exits_zero_with_shape_and_stats(self):
        code, data = run(PASS_FIXTURE)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["issues"], [])
        self.assertTrue(data["pass"])
        self.assertEqual(data["lang"], "en")
        self.assertEqual(data["title"], "Slider demo")
        self.assertEqual(data["file"], str(PASS_FIXTURE))
        self.assertGreater(data["size_kb"], 0)
        stats = data["stats"]
        self.assertEqual(stats["controls"], 2)
        self.assertEqual(stats["cjk_chars"], 9)
        self.assertEqual(
            stats["external"],
            ["https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"])
        self.assertGreater(stats["words"], 10)


class ExternalResourceTests(PageCase):
    def test_script_from_unlisted_host_is_external_host(self):
        code, data = self.mutate(
            "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js",
            "https://example.com/chart.js@4.4.1/chart.js")
        self.assert_fails_only(code, data, "external-host")
        self.assertEqual(data["issues"][0]["line"], 7)
        self.assertIn("example.com", data["issues"][0]["message"])

    def test_jsdelivr_outside_npm_is_external_host(self):
        code, data = self.mutate(
            "cdn.jsdelivr.net/npm/chart.js@4.4.1",
            "cdn.jsdelivr.net/gh/user/repo@1.2.3")
        self.assert_fails_only(code, data, "external-host")

    def test_lookalike_host_is_external_host(self):
        code, data = self.mutate(
            "https://cdn.jsdelivr.net/npm/", "https://cdn.jsdelivr.net.evil.com/npm/")
        self.assert_fails_only(code, data, "external-host")

    def test_protocol_relative_url_is_checked(self):
        code, data = self.mutate("https://cdn.jsdelivr.net", "//other.example")
        self.assert_fails_only(code, data, "external-host")

    def test_unpinned_versions(self):
        cases = {
            "no version": "https://unpkg.com/chart.js/dist/chart.js",
            "tag": "https://cdn.jsdelivr.net/npm/chart.js@latest/dist/chart.js",
            "range": "https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.js",
            "partial": "https://unpkg.com/chart.js@4.4/dist/chart.js",
        }
        for label, url in cases.items():
            with self.subTest(label):
                code, data = self.mutate(
                    "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js",
                    url)
                self.assert_fails_only(code, data, "unpinned-version")

    def test_exact_versions_pass_on_each_allowed_host(self):
        urls = [
            "https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js",
            "https://cdn.jsdelivr.net/npm/d3@7.8.5/dist/d3.min.js",
            "https://unpkg.com/d3@7.8.5/dist/d3.min.js",
            "https://unpkg.com/@scope/pkg@1.2.3-beta.1/dist/x.js",
        ]
        for url in urls:
            with self.subTest(url):
                code, data = self.mutate(
                    "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js",
                    url)
                self.assertEqual(code, 0, data["issues"])

    def test_relative_paths_are_local_resource(self):
        for tag in ('<script src="app.js"></script>',
                    '<link rel="stylesheet" href="./style.css">',
                    '<img src="img/a.png" alt="">',
                    '<iframe src="other.html"></iframe>',
                    '<video><source src="clip.mp4"></video>'):
            with self.subTest(tag):
                code, data = self.mutate("<h1>", tag + "\n<h1>")
                self.assert_fails_only(code, data, "local-resource")
                self.assertEqual(data["issues"][0]["line"], 17)

    def test_data_and_fragment_urls_are_allowed(self):
        code, data = self.mutate(
            "<h1>", '<img src="data:image/png;base64,AAAA" alt="">'
            '<iframe src="#frag"></iframe>\n<h1>')
        self.assertEqual(code, 0, data["issues"])

    def test_link_rel_kinds_are_checked_others_are_not(self):
        for rel in ("preload", "icon", "modulepreload", "shortcut icon"):
            with self.subTest(rel):
                code, data = self.mutate(
                    "</head>", f'<link rel="{rel}" href="https://example.com/x">\n</head>')
                self.assert_fails_only(code, data, "external-host")
        code, data = self.mutate(
            "</head>", '<link rel="canonical" href="https://example.com/x">\n</head>')
        self.assertEqual(code, 0, data["issues"])

    def test_anchor_links_are_not_resources(self):
        code, data = self.mutate("<h1>", '<a href="https://example.com">x</a>\n<h1>')
        self.assertEqual(code, 0, data["issues"])

    def test_css_import_and_url_in_inline_style(self):
        cases = {
            "import string": ('@import "https://example.com/a.css";', "external-host"),
            "import url": ("@import url(https://example.com/a.css);", "external-host"),
            "url host": ("p { background: url('https://example.com/a.png'); }",
                         "external-host"),
            "local url": ("p { background: url(img/a.png); }", "local-resource"),
            "unpinned": ("@import url(https://unpkg.com/x/a.css);", "unpinned-version"),
        }
        for label, (css, rule) in cases.items():
            with self.subTest(label):
                code, data = self.mutate("body {", css + "\nbody {")
                self.assert_fails_only(code, data, rule)
                self.assertEqual(data["issues"][0]["line"], 13)

    def test_url_in_style_attribute(self):
        code, data = self.mutate(
            "<h1>", '<div style="background:url(https://example.com/a.png)">x</div>\n<h1>')
        self.assert_fails_only(code, data, "external-host")
        self.assertEqual(data["issues"][0]["line"], 17)

    def test_host_aware_version_pins(self):
        bad = [
            "https://unpkg.com/foo/1.2.3/x.js",
            "https://cdn.jsdelivr.net/npm/chart.js@4/dist/1.0.0/x.js",
            "https://cdn.jsdelivr.net/npm/1.2.3/x.js",
            "https://cdnjs.cloudflare.com/ajax/libs/d3@7.8.5/d3.min.js",
            "https://cdnjs.cloudflare.com/d3/7.8.5/d3.min.js",
            "https://unpkg.com/@scope/pkg/1.2.3/x.js",
        ]
        for url in bad:
            with self.subTest(url):
                code, data = self.mutate(
                    "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js",
                    url)
                self.assert_fails_only(code, data, "unpinned-version")
        good = [
            "https://cdn.jsdelivr.net/npm/@scope/pkg@1.2.3/x.js",
            "https://cdn.jsdelivr.net/npm/d3@7.8.5",
            "https://unpkg.com/d3@7.8.5",
        ]
        for url in good:
            with self.subTest(url):
                code, data = self.mutate(
                    "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js",
                    url)
                self.assertEqual(code, 0, data["issues"])

    def test_malformed_url_is_bad_url(self):
        code, data = self.mutate(
            "<h1>", '<img src="http://[::1/x" alt="">\n<h1>')
        self.assert_fails_only(code, data, "bad-url")
        self.assertEqual(data["issues"][0]["line"], 17)

    def test_inline_script_imports_and_fetches(self):
        cases = {
            "module import": ('<script type="module">\nimport * as d3 from '
                              '"https://example.com/d3.js";\n</script>', "external-host", 18),
            "side-effect import": ('<script type="module">import "https://unpkg.com/x/a.js";'
                                   '</script>', "unpinned-version", 17),
            "dynamic import": ("<script>\n\nconst m = await import('https://example.com/m.js');"
                               "</script>", "external-host", 19),
            "relative import": ('<script type="module">import {a} from "./a.js";</script>',
                                "local-resource", 17),
            "fetch": ('<script>fetch("https://example.com/data.json")</script>',
                      "external-host", 17),
            "new URL": ("<script>new URL('https://example.com/w.js')</script>",
                        "external-host", 17),
            "importmap": ('<script type="importmap">{"imports": {"d3": '
                          '"https://example.com/d3.js"}}</script>', "external-host", 17),
        }
        for label, (tag, rule, line) in cases.items():
            with self.subTest(label):
                code, data = self.mutate("<h1>", tag + "\n<h1>")
                self.assert_fails_only(code, data, rule)
                self.assertEqual(data["issues"][0]["line"], line)

    def test_inline_script_without_resources_passes(self):
        code, data = self.mutate(
            "<h1>", '<script type="module">import {a} from "d3"; fetch("data.json");'
            ' const s = "import x from y";</script>\n<h1>')
        self.assertEqual(code, 0, data["issues"])

    def test_more_resource_attributes(self):
        cases = [
            '<img srcset="a.png 1x, https://cdn.jsdelivr.net/npm/x@1.0.0/b.png 2x" alt="">',
            '<picture><source srcset="https://example.com/a.webp"></picture>',
            '<video poster="https://example.com/p.png"></video>',
            '<object data="https://example.com/x.pdf"></object>',
            '<embed src="https://example.com/x.swf">',
            '<link rel="preconnect" href="https://fonts.example.com">',
            '<link rel="manifest" href="https://example.com/m.json">',
            '<svg><image href="https://example.com/a.png"/></svg>',
            '<svg><use xlink:href="https://example.com/s.svg#i"/></svg>',
        ]
        for tag in cases:
            with self.subTest(tag):
                code, data = self.mutate("<h1>", tag + "\n<h1>")
                self.assertEqual(code, 1, data)
                self.assertEqual(len(data["issues"]), 1, data["issues"])
                self.assertIn(data["issues"][0]["rule"],
                              ("external-host", "local-resource"))

    def test_srcset_with_allowed_urls_and_data_passes(self):
        code, data = self.mutate(
            "<h1>", '<img srcset="data:image/gif;base64,R0lG,AA 1x, '
            'https://unpkg.com/x@1.0.0/b.png 2x" alt="">'
            '<svg><use href="#icon"/></svg>'
            '<link rel="preconnect" href="https://cdn.jsdelivr.net">\n<h1>')
        self.assertEqual(code, 0, data["issues"])

    def test_external_stat_lists_every_external_url(self):
        code, data = self.mutate(
            "<h1>", '<img src="https://example.com/a.png" alt="">\n<h1>')
        self.assertEqual(code, 1)
        self.assertEqual(
            data["stats"]["external"],
            ["https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js",
             "https://example.com/a.png"])


class HeadTests(PageCase):
    def test_missing_lang(self):
        for old, new in (('<html lang="en">', "<html>"),
                         ('<html lang="en">', '<html lang="  ">')):
            with self.subTest(new):
                code, data = self.mutate(old, new)
                self.assert_fails_only(code, data, "missing-lang")
                self.assertEqual(data["issues"][0]["line"], 2)
                self.assertIsNone(data["lang"])

    def test_lang_is_reported(self):
        code, data = self.mutate('lang="en"', 'lang="zh-Hant"')
        self.assertEqual(code, 0)
        self.assertEqual(data["lang"], "zh-Hant")

    def test_missing_or_blank_title(self):
        for old, new in (("<title>Slider demo</title>", ""),
                         ("<title>Slider demo</title>", "<title>   </title>")):
            with self.subTest(new):
                code, data = self.mutate(old, new)
                self.assert_fails_only(code, data, "missing-title")

    def test_missing_viewport(self):
        for old, new in (
                ('<meta name="viewport" content="width=device-width, initial-scale=1">', ""),
                ('width=device-width', 'width=800')):
            with self.subTest(new):
                code, data = self.mutate(old, new)
                self.assert_fails_only(code, data, "missing-viewport")


class StyleAndControlTests(PageCase):
    def test_missing_dark_mode_query(self):
        code, data = self.mutate("prefers-color-scheme: dark", "prefers-reduced-motion: reduce")
        self.assert_fails_only(code, data, "missing-dark-mode")

    def test_light_query_does_not_count_as_dark_mode(self):
        code, data = self.mutate("prefers-color-scheme: dark", "prefers-color-scheme: light")
        self.assert_fails_only(code, data, "missing-dark-mode")

    def test_dark_mode_query_outside_style_does_not_count(self):
        text = self.base.replace("prefers-color-scheme: dark", "x")
        text = text.replace("<h1>", "<p>prefers-color-scheme: dark</p><h1>")
        code, data = self.check(text)
        self.assert_fails_only(code, data, "missing-dark-mode")

    def test_no_interactive_control(self):
        text = self.base.replace('<input id="v" type="range" min="0" max="10" value="3">', "")
        text = text.replace('<button id="reset" type="button">Reset</button>', "")
        code, data = self.check(text)
        self.assert_fails_only(code, data, "no-interaction")
        self.assertEqual(data["stats"]["controls"], 0)

    def test_each_control_kind_counts(self):
        text = self.base.replace('<input id="v" type="range" min="0" max="10" value="3">', "")
        text = text.replace('<button id="reset" type="button">Reset</button>', "{}")
        for ctrl in ('<button>x</button>', '<input type="range">',
                     '<input type="CHECKBOX">', '<input type="radio">',
                     '<input type="number">', '<select><option>a</option></select>',
                     '<details><summary>s</summary>t</details>'):
            with self.subTest(ctrl):
                code, data = self.check(text.replace("{}", ctrl))
                self.assertEqual(code, 0, data["issues"])
                self.assertEqual(data["stats"]["controls"], 1)

    def test_text_input_is_not_a_control(self):
        text = self.base.replace('<input id="v" type="range" min="0" max="10" value="3">',
                                 '<input type="text">')
        text = text.replace('<button id="reset" type="button">Reset</button>', "")
        code, data = self.check(text)
        self.assert_fails_only(code, data, "no-interaction")


class HandlerTests(PageCase):
    def test_inline_handler_attribute(self):
        code, data = self.mutate(
            '<button id="reset"', '<button onclick="go()" id="reset"')
        self.assert_fails_only(code, data, "inline-handler")
        self.assertEqual(data["issues"][0]["line"], 22)
        self.assertIn("onclick", data["issues"][0]["message"])

    def test_each_handler_attribute_is_reported(self):
        code, data = self.mutate(
            "<h1>", '<p onmouseover="a()" ONFOCUS="b()">x</p>\n<h1>')
        self.assertEqual(code, 1)
        self.assertEqual(self.rules(data), ["inline-handler", "inline-handler"])

    def test_on_text_in_script_or_values_is_not_a_handler(self):
        code, data = self.mutate(
            "<h1>", '<p title="onclick=1" data-one="x">onclick="y"</p>\n<h1>')
        self.assertEqual(code, 0, data["issues"])

    def test_on_words_that_are_not_handlers(self):
        # Rule: "on" + 3 or more letters is a handler (the shortest real one is
        # oncut), except a short allow-list of plain words.
        code, data = self.mutate(
            "<h1>", '<p one="1" only="1" on="1" onset="1" online="1">x</p>\n<h1>')
        self.assertEqual(code, 0, data["issues"])
        code, data = self.mutate(
            "<h1>", '<p oncut="a()" onend="b()" onpointerdown="c()">x</p>\n<h1>')
        self.assertEqual(self.rules(data), ["inline-handler"] * 3)


class SizeTests(PageCase):
    def test_too_large_with_default_budget(self):
        padding = "<!-- " + "x" * (500 * 1024) + " -->\n"
        code, data = self.mutate("<h1>", padding + "<h1>")
        self.assert_fails_only(code, data, "too-large")
        self.assertGreater(data["size_kb"], 500)

    def test_max_kb_flag(self):
        code, data = self.mutate("<h1>", "<h1>", "--max-kb", "0.1")
        self.assert_fails_only(code, data, "too-large")
        code, data = self.mutate("<h1>", "<h1>", "--max-kb", "5")
        self.assertEqual(code, 0, data["issues"])


class StatsTests(PageCase):
    def test_word_and_cjk_counts_use_visible_text_only(self):
        html = ("<!doctype html><html lang='en'><head><title>One two three</title>"
                "<meta name='viewport' content='width=device-width'>"
                "<style>@media (prefers-color-scheme: dark){p{color:red}}</style>"
                "<script>var hidden = 'a b c d e';</script></head>"
                "<body><p>Alpha beta gamma 你好世界</p><button>Go now</button></body></html>")
        code, data = self.check(html)
        self.assertEqual(code, 0, data["issues"])
        self.assertEqual(data["stats"]["words"], 5)
        self.assertEqual(data["stats"]["cjk_chars"], 4)
        self.assertEqual(data["title"], "One two three")


class UsageErrorTests(PageCase):
    def test_missing_file_exits_two(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(self.tmp / "nope.html")],
            capture_output=True)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, b"")
        self.assertIn(b"page_check", proc.stderr)

    def test_directory_exits_two(self):
        code, _ = run(self.tmp)
        self.assertEqual(code, 2)

    def test_non_utf8_input_exits_two(self):
        path = self.tmp / "latin1.html"
        path.write_bytes(self.base.encode("utf-8") + b"<p>caf\xe9</p>")
        code, data = run(path)
        self.assertEqual(code, 2)
        self.assertIsNone(data)

    def test_bad_flag_exits_two(self):
        for args in (("--bogus",), ("--max-kb", "abc")):
            with self.subTest(args):
                code, _ = run(PASS_FIXTURE, *args)
                self.assertEqual(code, 2)

    def test_no_file_argument_exits_two(self):
        proc = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True)
        self.assertEqual(proc.returncode, 2)

    def test_unexpected_error_prints_one_json_and_exits_two(self):
        # No input reaches this path through the CLI, so force it in-process.
        spec = importlib.util.spec_from_file_location("page_check", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        with mock.patch.object(sys, "dont_write_bytecode", True):  # keep the skill folder clean
            spec.loader.exec_module(mod)
        buf = io.BytesIO()
        fake_out = io.TextIOWrapper(buf, encoding="utf-8")
        with mock.patch.object(mod, "analyze", side_effect=RuntimeError("boom")), \
                mock.patch.object(sys, "stdout", fake_out):
            code = mod.main([str(PASS_FIXTURE)])
            fake_out.flush()
        self.assertEqual(code, 2)
        data = json.loads(buf.getvalue().decode("utf-8"))
        self.assertFalse(data["pass"])
        self.assertIn("boom", data["error"])


if __name__ == "__main__":
    unittest.main()
