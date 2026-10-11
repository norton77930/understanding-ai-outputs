"""CLI tests for skills/diagram-explainer/scripts/svg_check.py.

All assertions use the JSON the checker prints. The checker is run as a
subprocess, the same way the agent runs it. Standard library only.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "diagram-explainer" / "scripts" / "svg_check.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "svg"


def run(text=None, *args, file_arg=None, raw=None):
    cmd = [sys.executable, str(SCRIPT)]
    if file_arg is not None:
        cmd.append(str(file_arg))
    cmd.extend(args)
    data_in = raw if raw is not None else (None if text is None else text.encode("utf-8"))
    proc = subprocess.run(cmd, input=data_in, capture_output=True)
    out = proc.stdout.decode("utf-8")
    data = json.loads(out) if out.strip() else None
    return proc.returncode, data


def fixture(name):
    return run(file_arg=FIXTURES / name)


def rules(data):
    return [i["rule"] for i in data["issues"]]


def warning_rules(data):
    return [w["rule"] for w in data["warnings"]]


def svg(body, view_box="0 0 800 400", background=True):
    """A small SVG document around body, with a white background by default."""
    bg = '<rect width="100%" height="100%" fill="#ffffff"/>' if background else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_box}">'
            f"<title>T</title>{bg}{body}</svg>")


class PassTests(unittest.TestCase):
    def test_cjk_fixture_passes_with_no_warnings(self):
        code, data = fixture("pass_cjk.svg")
        self.assertEqual(code, 0, data)
        self.assertTrue(data["pass"])
        self.assertEqual(data["issues"], [])
        self.assertEqual(data["warnings"], [])
        self.assertEqual(data["viewbox"], [0, 0, 800, 340])
        self.assertEqual(set(data), {"viewbox", "limits", "counts", "texts",
                                     "issues", "warnings", "pass"})

    def test_cjk_text_is_listed_with_size_and_contrast(self):
        _code, data = fixture("pass_cjk.svg")
        entry = next(t for t in data["texts"] if t["text"] == "系統提示")
        self.assertEqual(entry["font_size"], 16)
        self.assertEqual(entry["color"], "#ffffff")
        self.assertEqual(entry["background"], "#1565c0")  # the box under it
        self.assertGreaterEqual(entry["contrast"], 4.5)


class StructureTests(unittest.TestCase):
    def test_doctype_with_entities_is_rejected_before_parsing(self):
        code, data = fixture("doctype_entity.svg")
        self.assertEqual(code, 1, data)
        self.assertEqual(rules(data), ["doctype"])
        self.assertEqual(data["issues"][0]["line"], 2)
        self.assertEqual(data["texts"], [])  # nothing was parsed or expanded

    def test_entity_declaration_alone_is_rejected(self):
        code, data = run('<!ENTITY x "y">' + svg(""))
        self.assertEqual(code, 1, data)
        self.assertIn("doctype", rules(data))

    def test_not_well_formed_xml(self):
        code, data = fixture("not_xml.svg")
        self.assertEqual(code, 1, data)
        self.assertEqual(rules(data), ["not-xml"])
        self.assertIsNone(data["viewbox"])

    def test_root_without_svg_namespace(self):
        code, data = fixture("not_svg.svg")
        self.assertEqual(code, 1, data)
        self.assertEqual(rules(data), ["not-svg"])
        self.assertIn("xmlns", data["issues"][0]["message"])

    def test_root_that_is_not_svg(self):
        code, data = run('<html xmlns="http://www.w3.org/1999/xhtml"><body/></html>')
        self.assertEqual(code, 1, data)
        self.assertEqual(rules(data), ["not-svg"])

    def test_missing_view_box(self):
        code, data = fixture("no_viewbox.svg")
        self.assertEqual(code, 1, data)
        self.assertEqual(rules(data), ["no-viewbox"])
        self.assertIsNone(data["viewbox"])
        self.assertIsNone(data["limits"]["min_font_size"])

    def test_malformed_view_box(self):
        for box in ("0 0 800", "0 0 0 400", "0 0 a b", "0 0 -800 400"):
            with self.subTest(view_box=box):
                code, data = run(svg("", view_box=box))
                self.assertEqual(code, 1, data)
                self.assertIn("no-viewbox", rules(data))

    def test_view_box_with_commas(self):
        code, data = run(svg("", view_box="0,0,640,360"))
        self.assertEqual(code, 0, data)
        self.assertEqual(data["viewbox"], [0, 0, 640, 360])


class ActiveContentTests(unittest.TestCase):
    def test_script_element(self):
        code, data = fixture("script.svg")
        self.assertEqual(code, 1, data)
        self.assertEqual(rules(data), ["script"])
        self.assertEqual(data["issues"][0]["line"], 4)

    def test_event_handler_attributes(self):
        code, data = fixture("event_handler.svg")
        self.assertEqual(code, 1, data)
        self.assertEqual(rules(data), ["event-handler", "event-handler"])
        self.assertIn("onload", data["issues"][0]["message"])
        self.assertIn("onclick", data["issues"][1]["message"])

    def test_attributes_that_only_start_with_o_are_fine(self):
        code, data = run(svg('<rect width="10" height="10" opacity="0.5"/>'))
        self.assertEqual(code, 0, data)

    def test_foreign_object(self):
        code, data = fixture("foreign_object.svg")
        self.assertEqual(code, 1, data)
        self.assertEqual(rules(data), ["foreign-object"])


class ExternalReferenceTests(unittest.TestCase):
    def test_href_to_a_url_or_another_file(self):
        code, data = fixture("external_href.svg")
        self.assertEqual(code, 1, data)
        self.assertEqual(rules(data), ["external-reference", "external-reference"])
        self.assertEqual([i["line"] for i in data["issues"]], [9, 10])
        self.assertIn("https://example.com/logo.png", data["issues"][0]["message"])
        self.assertIn("other.svg#shape", data["issues"][1]["message"])

    def test_css_import_and_url_to_outside(self):
        code, data = fixture("external_css.svg")
        self.assertEqual(code, 1, data)
        messages = " | ".join(i["message"] for i in data["issues"])
        self.assertEqual(rules(data), ["external-reference"] * 3, messages)
        self.assertIn("@import", messages)
        self.assertIn("https://example.com/texture.png", messages)
        self.assertIn("http://example.com/a.png", messages)
        self.assertNotIn("#fade", messages)

    def test_javascript_href(self):
        code, data = run(svg('<a href="javascript:alert(1)"><rect width="9" height="9"/></a>'))
        self.assertEqual(code, 1, data)
        self.assertEqual(rules(data), ["external-reference"])


class BackgroundTests(unittest.TestCase):
    def test_shape_that_does_not_cover_the_canvas(self):
        code, data = fixture("no_background.svg")
        self.assertEqual(code, 1, data)
        self.assertEqual(rules(data), ["no-background"])

    def test_semi_transparent_full_rect_is_not_a_background(self):
        body = '<rect width="800" height="400" fill="#ffffff" fill-opacity="0.5"/>'
        code, data = run(svg(body, background=False))
        self.assertEqual(code, 1, data)
        self.assertEqual(rules(data), ["no-background"])

    def test_full_rect_in_view_box_units_with_offset_origin(self):
        body = '<rect x="-10" y="-10" width="820" height="420" fill="#fafafa"/>'
        code, data = run(svg(body, view_box="-10 -10 820 420", background=False))
        self.assertEqual(code, 0, data)

    def test_css_background_on_the_root(self):
        doc = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200" '
               'style="background-color: #ffffff"><title>T</title>'
               '<text x="10" y="40" font-size="16">Hi</text></svg>')
        code, data = run(doc)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["texts"][0]["background"], "#ffffff")

    def test_gradient_background_counts(self):
        body = ('<defs><linearGradient id="g"><stop offset="0" stop-color="#fff"/>'
                '</linearGradient></defs><rect width="100%" height="100%" fill="url(#g)"/>')
        code, data = run(svg(body, background=False))
        self.assertEqual(code, 0, data)


class ContrastTests(unittest.TestCase):
    def test_low_contrast_on_canvas_and_on_a_box(self):
        code, data = fixture("low_contrast.svg")
        self.assertEqual(code, 1, data)
        self.assertEqual(rules(data), ["low-contrast", "low-contrast"])
        self.assertEqual([i["line"] for i in data["issues"]], [5, 7])
        self.assertIn("#b0b0b0", data["issues"][0]["message"])
        self.assertIn("#1565c0", data["issues"][1]["message"])

    def test_color_formats_resolve(self):
        for fill in ("#333", "#333333ff", "rgb(51, 51, 51)", "rgb(51 51 51)",
                     "rgba(0,0,0,1)", "black", "currentColor"):
            with self.subTest(fill=fill):
                body = f'<text x="10" y="40" font-size="16" color="#222" fill="{fill}">Hi</text>'
                code, data = run(svg(body))
                self.assertEqual(code, 0, data)
                self.assertGreater(data["texts"][0]["contrast"], 4.5)

    def test_transparent_text_is_blended_with_the_background(self):
        body = '<text x="10" y="40" font-size="16" fill="#000000" opacity="0.2">Faint</text>'
        code, data = run(svg(body))
        self.assertEqual(code, 1, data)
        self.assertEqual(rules(data), ["low-contrast"])

    def test_box_painted_after_the_text_is_not_its_background(self):
        body = ('<text x="10" y="40" font-size="16" fill="#ffffff">White</text>'
                '<rect x="0" y="0" width="200" height="100" fill="#000000" opacity="0"/>')
        code, data = run(svg(body))
        self.assertEqual(rules(data), ["low-contrast"])

    def test_large_text_uses_the_same_threshold(self):
        body = '<text x="10" y="60" font-size="40" fill="#949494">Big</text>'
        code, data = run(svg(body))
        self.assertEqual(rules(data), ["low-contrast"])


class FontSizeTests(unittest.TestCase):
    def test_hard_floor_scales_with_a_wide_view_box(self):
        code, data = fixture("small_text.svg")
        self.assertEqual(code, 1, data)
        self.assertEqual(data["limits"]["floor_font_size"], 14.67)  # 11 x 1600 / 1200
        self.assertEqual(data["limits"]["min_font_size"], 24)       # 12 x 1600 / 800
        self.assertEqual(rules(data), ["small-text"])
        self.assertEqual(data["issues"][0]["line"], 6)  # the CSS font shorthand
        self.assertIn("6 px", data["issues"][0]["message"])
        self.assertEqual(data["warnings"], [])  # no second report for the same text

    def test_between_floor_and_recommendation_is_a_warning_only(self):
        for box, size in (("0 0 800 400", 11.5), ("0 0 1600 400", 16)):
            with self.subTest(view_box=box, size=size):
                body = f'<text x="10" y="40" font-size="{size}" fill="#222">Small</text>'
                code, data = run(svg(body, view_box=box))
                self.assertEqual(code, 0, data)
                self.assertEqual(warning_rules(data), ["small-text-advisory"])
                self.assertIn("recommended", data["warnings"][0]["message"])

    def test_floor_stays_at_min_font_px_for_a_narrow_view_box(self):
        body = '<text x="10" y="40" font-size="12" fill="#222">Twelve</text>'
        code, data = run(svg(body, view_box="0 0 400 200"))
        self.assertEqual(code, 0, data)
        self.assertEqual(data["warnings"], [])
        self.assertEqual(data["limits"]["min_font_size"], 12)
        self.assertEqual(data["limits"]["floor_font_size"], 11)

    def test_text_below_the_floor(self):
        body = '<text x="10" y="40" font-size="10.5" fill="#222">Small</text>'
        code, data = run(svg(body))
        self.assertEqual(rules(data), ["small-text"])

    def test_floor_flags(self):
        body = '<text x="10" y="40" font-size="12" fill="#222">Hi</text>'
        code, data = run(svg(body, view_box="0 0 1200 400"), "--floor-width", "600",
                         "--floor-font-px", "8")
        self.assertEqual(data["limits"]["floor_font_size"], 16)
        self.assertEqual(rules(data), ["small-text"])

    def test_units_and_inheritance(self):
        cases = [('<g font-size="8pt"><text x="10" y="40" fill="#222">Hi</text></g>', 10.67),
                 ('<g font-size="20"><text x="10" y="40" font-size="0.5em" fill="#222">Hi</text></g>', 10),
                 ('<text x="10" y="40" style="font-size: 10px" fill="#222">Hi</text>', 10)]
        for body, size in cases:
            with self.subTest(body=body):
                code, data = run(svg(body))
                self.assertEqual(rules(data), ["small-text"])
                self.assertEqual(data["texts"][0]["font_size"], size)

    def test_default_font_size_is_16(self):
        code, data = run(svg('<text x="10" y="40" fill="#222">Hi</text>'))
        self.assertEqual(code, 0, data)
        self.assertEqual(data["texts"][0]["font_size"], 16)

    def test_display_width_and_min_font_px_flags(self):
        body = '<text x="10" y="40" font-size="16" fill="#222">Hi</text>'
        code, data = run(svg(body, view_box="0 0 1200 400"), "--display-width", "600",
                         "--min-font-px", "10")
        self.assertEqual(data["limits"]["min_font_size"], 20)
        self.assertEqual(rules(data), [])
        self.assertEqual(warning_rules(data), ["small-text-advisory"])

    def test_bad_flag_exits_2_without_json(self):
        code, data = run(svg(""), "--min-font-px", "0")
        self.assertEqual(code, 2)
        self.assertIsNone(data)


class WarningTests(unittest.TestCase):
    def test_text_outside_honors_anchor_translate_and_cjk_width(self):
        code, data = fixture("text_outside.svg")
        self.assertEqual(code, 0, data)  # warnings never fail
        self.assertEqual(warning_rules(data), ["text-outside"] * 3)
        self.assertEqual([w["line"] for w in data["warnings"]], [4, 5, 7])
        self.assertIn("right", data["warnings"][0]["message"])
        self.assertIn("left", data["warnings"][1]["message"])
        self.assertIn("bottom", data["warnings"][2]["message"])

    def test_wide_cjk_label_is_measured_at_one_em_per_character(self):
        # 20 CJK characters at 16 units is about 320 units: over a 300-wide canvas.
        body = '<text x="0" y="40" font-size="16" fill="#222">' + "中" * 20 + "</text>"
        code, data = run(svg(body, view_box="0 0 300 100"))
        self.assertEqual(warning_rules(data), ["text-outside"])
        # The same count of Latin letters is about 0.6 em each: 192 units, inside.
        body = '<text x="0" y="40" font-size="16" fill="#222">' + "a" * 20 + "</text>"
        code, data = run(svg(body, view_box="0 0 300 100"))
        self.assertEqual(data["warnings"], [])

    def test_tspan_lines_are_placed_one_by_one(self):
        body = ('<text x="10" y="30" font-size="16" fill="#222">'
                '<tspan x="10">Short</tspan>'
                '<tspan x="10" dy="1.2em">Second line</tspan>'
                '<tspan x="10" dy="200">Far below</tspan></text>')
        code, data = run(svg(body, view_box="0 0 300 100"))
        self.assertEqual(warning_rules(data), ["text-outside"])
        self.assertIn("Far below", data["warnings"][0]["message"])

    def test_other_transforms_cannot_be_placed(self):
        code, data = fixture("cannot_place.svg")
        self.assertEqual(code, 0, data)
        self.assertEqual(warning_rules(data), ["cannot-place", "cannot-place"])
        self.assertEqual([w["line"] for w in data["warnings"]], [5, 7])

    def test_unresolved_text_and_background_colors(self):
        code, data = fixture("unresolved_color.svg")
        self.assertEqual(code, 0, data)
        self.assertEqual(warning_rules(data), ["unresolved-color"] * 2)
        self.assertIn("hsl(", data["warnings"][0]["message"])
        self.assertIn("url(#band)", data["warnings"][1]["message"])
        self.assertIsNone(data["texts"][1]["contrast"])

    def test_large_file(self):
        padding = "<!-- " + "x" * (210 * 1024) + " -->"
        code, data = run(svg(padding))
        self.assertEqual(code, 0, data)
        self.assertEqual(warning_rules(data), ["large-file"])
        self.assertGreater(data["counts"]["bytes"], 200 * 1024)


class InputTests(unittest.TestCase):
    def test_stdin_and_dash(self):
        doc = svg('<text x="10" y="40" fill="#222">Hi</text>')
        for args in ((), ("-",)):
            with self.subTest(args=args):
                code, data = run(doc, *args)
                self.assertEqual(code, 0, data)

    def test_utf8_bom_is_ignored(self):
        code, data = run(raw=b"\xef\xbb\xbf" + svg("").encode("utf-8"))
        self.assertEqual(code, 0, data)

    def test_missing_file_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, data = run(file_arg=Path(tmp) / "nope.svg")
        self.assertEqual(code, 2)
        self.assertIsNone(data)

    def test_not_utf8_exits_2(self):
        code, data = run(raw=b"<svg>\xff\xfe</svg>")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
