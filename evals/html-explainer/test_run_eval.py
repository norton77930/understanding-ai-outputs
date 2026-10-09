"""Unit tests for the pure parts of run_eval.py (topics, HTML choice, metrics, A/B order, review page).

Run: python -m unittest discover -s evals/html-explainer -p "test_run_eval.py"
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_eval  # noqa: E402

TOPIC = """- Language: zh-TW
- Intended interaction: slider

## Source

複利是利息再生利息。
第二行。

## Reader should understand

- 第一點。
- 第二點。

## Interaction hints

- Pattern: slider.
"""

PAGE_OK = {"pass": True, "size_kb": 12.5, "issues": [],
           "stats": {"words": 100, "cjk_chars": 0, "controls": 2, "external": []}}
RENDER_OK = {"pass": True, "console_errors": [], "page_errors": [],
             "overflow_390": {"scroll_width": 390, "client_width": 390, "overflow": False},
             "interaction": {"kind": "range", "selector": "#rate"}, "interaction_error": None,
             "load_error": None, "screenshots": ["a.png"]}


class TopicTest(unittest.TestCase):
    def test_reads_language_source_and_points(self):
        topic = run_eval.parse_topic("04-x", TOPIC)
        self.assertEqual(topic["lang"], "zh-TW")
        self.assertEqual(topic["source"], "複利是利息再生利息。\n第二行。")
        self.assertEqual(topic["points"], ["第一點。", "第二點。"])

    def test_missing_source_raises(self):
        with self.assertRaises(ValueError):
            run_eval.parse_topic("x", "- Language: en\n")

    def test_prompt_is_the_same_for_both_arms_and_ends_with_source(self):
        prompt = run_eval.build_prompt({"source": "Text."})
        self.assertTrue(prompt.startswith("Make an interactive web page that explains the following."))
        self.assertTrue(prompt.rstrip().endswith("Text."))


class ChooseHtmlTest(unittest.TestCase):
    def test_newest_wins_and_count_is_recorded(self):
        chosen = run_eval.choose_html([("a.html", 1.0), ("b.html", 3.0), ("c.html", 2.0)])
        self.assertEqual(chosen, {"path": "b.html", "count": 3, "all": ["a.html", "b.html", "c.html"]})

    def test_none_when_empty(self):
        self.assertEqual(run_eval.choose_html([]), {"path": None, "count": 0, "all": []})


class ArmMetricsTest(unittest.TestCase):
    def test_all_good(self):
        m = run_eval.arm_metrics(PAGE_OK, RENDER_OK)
        self.assertTrue(m["page_check_ok"])
        self.assertEqual(m["issue_rules"], [])
        self.assertTrue(m["render_ok"])
        self.assertEqual(m["console_errors"], 0)
        self.assertFalse(m["overflow_390"])
        self.assertEqual(m["interaction"], "range")
        self.assertTrue(m["single_file"])
        self.assertEqual(m["size_kb"], 12.5)

    def test_issue_rules_sorted_unique_and_single_file_false(self):
        page = dict(PAGE_OK, **{"pass": False, "issues": [
            {"rule": "local-resource", "line": 3, "message": ""},
            {"rule": "inline-handler", "line": 4, "message": ""},
            {"rule": "inline-handler", "line": 5, "message": ""}]})
        m = run_eval.arm_metrics(page, RENDER_OK)
        self.assertFalse(m["page_check_ok"])
        self.assertEqual(m["issue_rules"], ["inline-handler", "local-resource"])
        self.assertFalse(m["single_file"])

    def test_external_resource_is_not_single_file(self):
        page = dict(PAGE_OK, stats=dict(PAGE_OK["stats"], external=["https://unpkg.com/x@1.0.0/x.js"]))
        self.assertFalse(run_eval.arm_metrics(page, RENDER_OK)["single_file"])

    def test_render_problems(self):
        render = dict(RENDER_OK, **{"pass": False, "console_errors": ["e1"], "page_errors": ["p1", "p2"],
                                    "overflow_390": {"scroll_width": 500, "client_width": 390,
                                                     "overflow": True},
                                    "interaction": None})
        m = run_eval.arm_metrics(PAGE_OK, render)
        self.assertFalse(m["render_ok"])
        self.assertEqual((m["console_errors"], m["page_errors"]), (1, 2))
        self.assertTrue(m["overflow_390"])
        self.assertIsNone(m["interaction"])

    def test_interaction_error_means_not_found(self):
        render = dict(RENDER_OK, interaction_error="click timed out")
        self.assertIsNone(run_eval.arm_metrics(PAGE_OK, render)["interaction"])

    def test_missing_data_gives_none(self):
        m = run_eval.arm_metrics(None, None)
        self.assertIsNone(m["page_check_ok"])
        self.assertIsNone(m["render_ok"])
        self.assertIsNone(m["single_file"])

    def test_render_environment_error_is_none_not_fail(self):
        m = run_eval.arm_metrics(PAGE_OK, {"error": "no browser", "hint": "", "pass": False})
        self.assertIsNone(m["render_ok"])


class OrderTest(unittest.TestCase):
    def test_same_seed_same_order_and_both_arms_present(self):
        ids = ["01", "02", "03", "04"]
        first = run_eval.ab_orders(ids, 7)
        self.assertEqual(first, run_eval.ab_orders(ids, 7))
        for order in first.values():
            self.assertEqual(sorted(order), sorted(run_eval.ARMS))

    def test_seeds_give_both_orders(self):
        seen = set()
        for seed in range(20):
            seen.update(tuple(o) for o in run_eval.ab_orders(["01", "02", "03", "04"], seed).values())
        self.assertEqual(len(seen), 2)


class AggregateTest(unittest.TestCase):
    def _result(self, page_ok, render_ok):
        arms = {arm: {"metrics": {"page_check_ok": True, "render_ok": True}, "meta": {"cost_usd": 0.5},
                      "seconds": 10} for arm in run_eval.ARMS}
        arms["with-skill"]["metrics"] = {"page_check_ok": page_ok, "render_ok": render_ok}
        return {"id": "t", "arms": arms}

    def test_pass_fail_incomplete(self):
        self.assertEqual(run_eval.aggregate([self._result(True, True)])["verdict"], "PASS")
        self.assertEqual(run_eval.aggregate([self._result(True, None)])["verdict"], "INCOMPLETE")
        self.assertEqual(run_eval.aggregate([self._result(False, None)])["verdict"], "FAIL")

    def test_baseline_does_not_gate_and_cost_sums(self):
        r = self._result(True, True)
        r["arms"]["baseline"]["metrics"] = {"page_check_ok": False, "render_ok": False}
        agg = run_eval.aggregate([r])
        self.assertEqual(agg["verdict"], "PASS")
        self.assertEqual(agg["cost_usd"], 1.0)
        self.assertEqual(agg["arms"]["baseline"]["page_check_pass"], 0)


class ReportTest(unittest.TestCase):
    def test_summary_line_per_arm_has_cost_and_agent_time(self):
        arms = {arm: {"metrics": {"page_check_ok": True, "render_ok": True, "issue_rules": [],
                                  "console_errors": 0, "page_errors": 0, "overflow_390": False,
                                  "interaction": "button", "size_kb": 1.0, "single_file": True,
                                  "render_error": None},
                      "meta": {"cost_usd": 0.5, "num_turns": 3}, "seconds": 61.4, "errors": []}
                for arm in run_eval.ARMS}
        results = [{"id": "01-x", "lang": "zh-TW", "points": [], "arms": arms}]
        meta = {"timestamp": "t", "model": None, "claude_version": "v", "plugin_dir": "p",
                "scratch_root": "s", "review": "r", "seed": 1}
        report = run_eval.render_report(meta, results, run_eval.aggregate(results))
        for arm in run_eval.ARMS:
            self.assertIn(f"- {arm}: page_check 1/1, render_check 1/1, cost $0.50, 61 s", report)
        self.assertIn("Total cost $1.00, agent time 123 s", report)


class ReviewPageTest(unittest.TestCase):
    def test_labels_only_a_and_b_and_escapes(self):
        entries = [{"id": "01-x", "lang": "en", "points": ["a < b"],
                    "shots": {"A": {"390": "review/01-x-A-390.png", "1280": None},
                              "B": {"390": None, "1280": "review/01-x-B-1280.png"}},
                    "pages": {"A": "review/01-x-A.html", "B": None}}]
        html = run_eval.render_review(entries, "20260101-000000")
        self.assertIn("review/01-x-A-390.png", html)
        self.assertIn("a &lt; b", html)
        self.assertIn("頁面 A", html)
        self.assertNotIn("with-skill", html)
        self.assertNotIn("baseline", html)

    def _two_topics(self):
        return [{"id": tid, "lang": "zh-TW", "points": points,
                 "shots": {"A": {}, "B": {}}, "pages": {"A": None, "B": None}}
                for tid, points in (("01-x", ["重點甲", "重點乙"]), ("02-y", ["重點丙"]))]

    def test_page_is_zh_tw_and_states_both_axes_with_english_names(self):
        html = run_eval.render_review(self._two_topics(), "t")
        self.assertIn('lang="zh-TW"', html)
        self.assertIn("理解（Understanding）", html)
        self.assertIn("互動與呈現（Interaction and presentation）", html)
        self.assertIn("1 到 5", html)
        self.assertIn("平手（tie）", html)

    def test_each_topic_has_its_points_and_a_rating_table_for_a_and_b(self):
        html = run_eval.render_review(self._two_topics(), "t")
        for point in ("重點甲", "重點乙", "重點丙"):
            self.assertIn(point, html)
        self.assertEqual(html.count('<table class="rate">'), 2)
        self.assertEqual(html.count("較好的頁面（Better page）"), 2)
        self.assertEqual(html.count("<tr><th>頁面 A</th>"), 2)
        self.assertEqual(html.count("<tr><th>頁面 B</th>"), 2)


if __name__ == "__main__":
    unittest.main()
