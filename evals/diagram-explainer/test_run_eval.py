"""Unit tests for the pure parts of run_eval.py (topic parsing, Mermaid
extraction, diagram type, A/B order, SVG size, aggregation, report and review page).

Run: python -m unittest discover -s evals/diagram-explainer -p "test_run_eval.py"
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_eval  # noqa: E402

TOPIC = """- Language: zh-TW
- Expected diagram type: `flowchart TD` with decisions

## Source

瀏覽器先檢查快取。

## Reader should understand

- 第一點。
- 第二點。

## Diagram hints

- Key nodes (about 9).
"""


def check(passed=True, kind="flowchart", nodes=5, over=0, issues=0, **counts):
    if kind == "flowchart":
        counts = {"nodes": nodes, "edges": nodes - 1, "subgraphs": 0, **counts}
    elif kind == "sequenceDiagram":
        counts = {"participants": nodes, "messages": counts.get("messages", 8)}
    else:
        counts = {"states": nodes, "transitions": nodes}
    labels = [{"text": "x", "over": i < over} for i in range(max(over, 3))]
    return {"type": kind, "counts": counts, "labels": labels,
            "issues": [{"rule": "label-too-long"}] * issues, "pass": passed}


class ParseTopicTest(unittest.TestCase):
    def test_reads_fields(self):
        topic = run_eval.parse_topic("04-browser-cache", TOPIC)
        self.assertEqual(topic["lang"], "zh-TW")
        self.assertEqual(topic["expected_type"], "flowchart TD")
        self.assertEqual(topic["source"], "瀏覽器先檢查快取。")
        self.assertEqual(topic["points"], ["第一點。", "第二點。"])

    def test_missing_source_is_an_error(self):
        with self.assertRaises(ValueError):
            run_eval.parse_topic("x", "- Language: en\n")

    def test_prompt_holds_request_and_source_only(self):
        topic = run_eval.parse_topic("04", TOPIC)
        prompt = run_eval.build_prompt(topic)
        self.assertTrue(prompt.startswith(run_eval.REQUEST))
        self.assertIn("瀏覽器先檢查快取。", prompt)
        self.assertNotIn("第一點", prompt)


class ExtractMermaidTest(unittest.TestCase):
    def test_first_mermaid_block(self):
        reply = ("Here:\n```text\nnot this\n```\n```mermaid\nflowchart LR\n  A --> B\n```\n"
                 "and\n```mermaid\nsequenceDiagram\n```\n")
        self.assertEqual(run_eval.extract_mermaid(reply), "flowchart LR\n  A --> B")

    def test_crlf_and_indented_fence(self):
        reply = "  ```Mermaid\r\nstateDiagram-v2\r\n  [*] --> A\r\n  ```\r\n"
        self.assertEqual(run_eval.extract_mermaid(reply), "stateDiagram-v2\n  [*] --> A")

    def test_none_without_block(self):
        self.assertIsNone(run_eval.extract_mermaid("no diagram\n```\nflowchart LR\n```"))
        self.assertIsNone(run_eval.extract_mermaid(None))


class ChooseDiagramsTest(unittest.TestCase):
    REPLY = "```mermaid\nflowchart LR\nA-->B\n```"

    def test_saved_files_first(self):
        self.assertEqual(run_eval.choose_diagrams(["graph TD\nX"], self.REPLY, ["<svg/>"]),
                         (["graph TD\nX"], "file", "mermaid"))

    def test_then_reply_block(self):
        self.assertEqual(run_eval.choose_diagrams([], self.REPLY, ["<svg/>"]),
                         (["flowchart LR\nA-->B"], "reply", "mermaid"))

    def test_then_saved_svg(self):
        self.assertEqual(run_eval.choose_diagrams([], "drew it", ["<svg/>"]), (["<svg/>"], "file", "svg"))

    def test_nothing(self):
        self.assertEqual(run_eval.choose_diagrams([], None, []), ([], None, None))


class DiagramTypeTest(unittest.TestCase):
    def test_header_normalization(self):
        h = run_eval.diagram_header
        self.assertEqual(h("%% comment\n\nflowchart LR\n A-->B"), "flowchart LR")
        self.assertEqual(h("graph TB\n A-->B"), "flowchart TD")
        self.assertEqual(h("flowchart\n A-->B"), "flowchart TD")
        self.assertEqual(h("flowchart RL; A-->B"), "flowchart RL")
        self.assertEqual(h("---\ntitle: x\n---\nstateDiagram\n"), "stateDiagram-v2")
        self.assertEqual(h("sequenceDiagram\n"), "sequenceDiagram")
        self.assertIsNone(h(""))

    def test_type_matches(self):
        self.assertTrue(run_eval.type_matches("flowchart TD", "flowchart TD"))
        self.assertFalse(run_eval.type_matches("flowchart TD", "flowchart LR"))
        self.assertTrue(run_eval.type_matches("stateDiagram-v2", "stateDiagram-v2"))
        self.assertIsNone(run_eval.type_matches("sequenceDiagram", None))


class ArmMetricsTest(unittest.TestCase):
    def test_single_flowchart(self):
        m = run_eval.arm_metrics(["flowchart LR\nA-->B"], [check(nodes=8, over=1, issues=1, passed=False)],
                                 [True], "flowchart LR")
        self.assertEqual(m["diagrams"], 1)
        self.assertFalse(m["checker_pass"])
        self.assertEqual(m["issues"], 1)
        self.assertEqual(m["nodes"], 8)
        self.assertEqual(m["label_overruns"], 1)
        self.assertTrue(m["render_ok"])
        self.assertEqual(m["type"], "flowchart LR")
        self.assertTrue(m["type_ok"])

    def test_sequence_counts_participants_and_messages(self):
        m = run_eval.arm_metrics(["sequenceDiagram\n"], [check(kind="sequenceDiagram", nodes=4, messages=9)],
                                 [True], "sequenceDiagram")
        self.assertEqual((m["nodes"], m["messages"]), (4, 9))

    def test_several_diagrams_sum_and_all(self):
        m = run_eval.arm_metrics(["flowchart TD\n", "flowchart LR\n"],
                                 [check(nodes=5), check(nodes=6, passed=False, issues=2)],
                                 [True, None], "flowchart TD")
        self.assertEqual(m["nodes"], 11)
        self.assertFalse(m["checker_pass"])
        self.assertEqual(m["issues"], 2)
        self.assertIsNone(m["render_ok"])  # one render unavailable, none failed
        self.assertTrue(m["type_ok"])  # the first diagram decides the type

    def test_render_failure_wins_over_unavailable(self):
        m = run_eval.arm_metrics(["a", "b"], [check(), check()], [None, False], "flowchart TD")
        self.assertFalse(m["render_ok"])

    def test_svg_has_no_mermaid_metrics(self):
        m = run_eval.arm_metrics(["<svg/>"], [], [], "flowchart TD", fmt="svg")
        self.assertEqual((m["diagrams"], m["type"], m["type_ok"]), (1, "svg", False))
        self.assertIsNone(m["checker_pass"])
        self.assertIsNone(m["render_ok"])
        self.assertIsNone(m["nodes"])

    def test_no_diagram(self):
        m = run_eval.arm_metrics([], [], [], "flowchart TD")
        self.assertEqual(m["diagrams"], 0)
        self.assertFalse(m["checker_pass"])
        self.assertFalse(m["render_ok"])
        self.assertFalse(m["type_ok"])


class OrderTest(unittest.TestCase):
    def test_order_reproducible_and_complete(self):
        first = run_eval.ab_order("seed", "01-card-payment")
        self.assertEqual(first, run_eval.ab_order("seed", "01-card-payment"))
        self.assertEqual(sorted(first), sorted(run_eval.ARMS))
        orders = {run_eval.ab_order(str(s), "01") for s in range(20)}
        self.assertEqual(len(orders), 2)

    def test_orders_per_topic_are_stable_when_topics_are_a_subset(self):
        ids = ["01", "02", "03", "04"]
        full = run_eval.ab_orders(ids, "s1")
        self.assertEqual(full, run_eval.ab_orders(ids, "s1"))
        self.assertEqual(run_eval.ab_orders(["03"], "s1")["03"], full["03"])
        self.assertTrue(all(sorted(o) == sorted(run_eval.ARMS) for o in full.values()))

    def test_neutral_image_names_hide_the_arm(self):
        self.assertEqual(run_eval.neutral_image_names("01-x", "A", 1), ["01-x-A.png"])
        self.assertEqual(run_eval.neutral_image_names("01-x", "B", 2), ["01-x-B.png", "01-x-B-2.png"])
        self.assertEqual(run_eval.neutral_image_names("01-x", "A", 0), [])


class SvgDimensionsTest(unittest.TestCase):
    def test_width_and_height_attributes(self):
        self.assertEqual(run_eval.svg_dimensions('<svg width="1240px" height="790" viewBox="0 0 10 10">'),
                         (1240, 790))

    def test_viewbox_only_uses_default_width_and_keeps_aspect(self):
        self.assertEqual(run_eval.svg_dimensions('<svg viewBox="0 0 700 350">'), (1400, 700))

    def test_one_attribute_and_viewbox(self):
        self.assertEqual(run_eval.svg_dimensions('<svg width="500" viewBox="0 0 100 200">'), (500, 1000))

    def test_fallback_and_clamp(self):
        self.assertEqual(run_eval.svg_dimensions("<svg>"), (1400, 1100))
        self.assertEqual(run_eval.svg_dimensions('<svg width="100%" height="50%">'), (1400, 1100))
        self.assertEqual(run_eval.svg_dimensions('<svg width="9000" height="20">'), (4000, 100))

    def test_screenshot_command_points_at_the_svg_file(self):
        cmd = run_eval.browser_screenshot_cmd("chrome", Path("a.svg"), Path("a.png"), (1000, 800), "prof")
        self.assertIn("--headless=new", cmd)
        self.assertIn("--window-size=1000,800", cmd)
        self.assertIn("--screenshot=a.png", cmd)
        self.assertTrue(cmd[-1].startswith("file:///") and cmd[-1].endswith("a.svg"))


class AggregateTest(unittest.TestCase):
    def topic(self, tid, skill, base, images=(1, 1)):
        return {"id": tid, "arms": {
            "with-skill": {"metrics": skill, "images": ["a.png"] * images[0],
                           "meta": {"cost_usd": 0.5, "num_turns": 9}, "seconds": 100},
            "baseline": {"metrics": base, "images": ["b.png"] * images[1],
                         "meta": {"cost_usd": 0.1, "num_turns": 2}, "seconds": 20}}}

    def test_totals(self):
        ok = run_eval.arm_metrics(["flowchart LR"], [check(nodes=8)], [True], "flowchart LR")
        bad = run_eval.arm_metrics(["flowchart TD"], [check(nodes=14, over=2, issues=3, passed=False)],
                                   [False], "flowchart LR")
        agg = run_eval.aggregate([self.topic("01", ok, bad), self.topic("02", ok, ok, images=(1, 0))])
        skill, base = agg["arms"]["with-skill"], agg["arms"]["baseline"]
        self.assertEqual((skill["checker_pass"], skill["rendered"], skill["type_ok"]), (2, 2, 2))
        self.assertEqual((base["checker_pass"], base["rendered"], base["type_ok"]), (1, 1, 1))
        self.assertEqual(base["label_overruns"], 2)
        self.assertEqual((skill["images"], base["images"]), (2, 1))
        self.assertAlmostEqual(skill["cost_usd"], 1.0)
        self.assertAlmostEqual(base["cost_usd"], 0.2)
        self.assertAlmostEqual(agg["cost_usd"], 1.2)
        self.assertEqual((skill["seconds"], agg["seconds"]), (200, 240))
        self.assertEqual(skill["turns"], 18)
        self.assertEqual(agg["topics"], 2)
        self.assertEqual(base["not_mermaid"], 0)
        self.assertNotIn("faster", agg)

    def test_counts_svg_answers(self):
        svg = run_eval.arm_metrics(["<svg/>"], [], [], "flowchart LR", fmt="svg")
        ok = run_eval.arm_metrics(["flowchart LR"], [check()], [True], "flowchart LR")
        agg = run_eval.aggregate([self.topic("01", ok, svg)])
        self.assertEqual(agg["arms"]["baseline"]["not_mermaid"], 1)
        self.assertEqual(agg["arms"]["baseline"]["checker_pass"], 0)

    def test_missing_metrics(self):
        agg = run_eval.aggregate([self.topic("01", None, None, images=(0, 0))])
        self.assertEqual(agg["arms"]["with-skill"]["checker_pass"], 0)
        self.assertEqual(agg["arms"]["with-skill"]["images"], 0)


class ReportTest(unittest.TestCase):
    def test_summary_line_per_arm_and_total(self):
        ok = run_eval.arm_metrics(["flowchart LR"], [check(nodes=8, over=1)], [True], "flowchart LR")
        arms = {arm: {"metrics": ok, "images": ["x.png"], "meta": {"cost_usd": 0.5, "num_turns": 3},
                      "seconds": 61.4, "mermaid_from": "file", "format": "mermaid", "codes": ["flowchart LR"]}
                for arm in run_eval.ARMS}
        results = [{"id": "01-x", "lang": "zh-TW", "expected_type": "flowchart LR", "points": [],
                    "arms": arms, "errors": []}]
        meta = {"timestamp": "t", "model": None, "claude_version": "v", "plugin_dir": "p",
                "scratch_root": "s", "review": "r", "seed": "sd", "wall_seconds": 75.2}
        report = run_eval.render_report(meta, results, run_eval.aggregate(results))
        for arm in run_eval.ARMS:
            self.assertIn(f"- {arm}: checker pass 1/1, rendered 1/1, label overruns 1, images 1/1, "
                          "cost $0.50, 61 s", report)
        self.assertIn("- Total: cost $1.00, agent time 123 s, wall time 75 s", report)
        self.assertNotIn("judge", report.lower())
        self.assertNotIn("ab_key", report)


class ReviewPageTest(unittest.TestCase):
    def entries(self):
        return [{"id": tid, "lang": "zh-TW", "points": points,
                 "images": {"A": [f"review/{tid}-A.png"], "B": [f"review/{tid}-B.png", f"review/{tid}-B-2.png"]}}
                for tid, points in (("01-x", ["重點甲", "a < b"]), ("02-y", ["重點丙"]))]

    def test_page_is_zh_tw_and_states_both_axes(self):
        page = run_eval.render_review(self.entries(), "t")
        self.assertIn('lang="zh-TW"', page)
        self.assertIn("理解（Understanding）", page)
        self.assertIn("呈現（Presentation）", page)
        self.assertIn("1 到 5", page)
        self.assertIn("較好（A / B / 平手）", page)

    def test_each_topic_has_its_points_and_a_rating_table_for_a_and_b(self):
        page = run_eval.render_review(self.entries(), "t")
        for point in ("重點甲", "a &lt; b", "重點丙"):
            self.assertIn(point, page)
        self.assertEqual(page.count('<table class="rate">'), 2)
        self.assertEqual(page.count("較好（A / B / 平手）：______"), 2)
        self.assertEqual(page.count("<tr><th>圖 A</th>"), 2)
        self.assertEqual(page.count("<tr><th>圖 B</th>"), 2)

    def test_images_are_shown_and_linked_full_size(self):
        page = run_eval.render_review(self.entries(), "t")
        self.assertIn('<a href="review/01-x-A.png" target="_blank"><img src="review/01-x-A.png"', page)
        self.assertIn("review/02-y-B-2.png", page)
        self.assertIn("開啟原尺寸（圖 B，第 2 張）", page)

    def test_missing_image_is_marked_and_no_arm_names(self):
        entries = self.entries()
        entries[0]["images"]["A"] = []
        page = run_eval.render_review(entries, "t")
        self.assertIn("沒有圖片", page)
        for name in run_eval.ARMS:
            self.assertNotIn(name, page)
        self.assertNotIn(".svg", page)
        self.assertNotIn(".mmd", page)


if __name__ == "__main__":
    unittest.main()
