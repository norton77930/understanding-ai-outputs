"""Unit tests for the pure parts of run_eval.py (topic parsing, Mermaid
extraction, diagram type, judge A/B mapping, aggregation).

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


class JudgeTest(unittest.TestCase):
    def test_parse_chatty_reply(self):
        reply = 'Sure.\n{"faster": "b", "accuracy_a": "4", "accuracy_b": 5, "reason": "ok"}'
        self.assertEqual(run_eval.parse_judge(reply),
                         {"faster": "B", "accuracy_a": 4, "accuracy_b": 5, "reason": "ok"})

    def test_parse_tie_and_invalid(self):
        self.assertEqual(run_eval.parse_judge('{"faster": "Tie", "accuracy_a": 3, "accuracy_b": 3}')["faster"],
                         "tie")
        self.assertIsNone(run_eval.parse_judge("nothing"))
        self.assertIsNone(run_eval.parse_judge('{"faster": "A", "accuracy_a": 0, "accuracy_b": 3}'))
        self.assertIsNone(run_eval.parse_judge('{"faster": "C", "accuracy_a": 3, "accuracy_b": 3}'))

    def test_map_back_to_arms(self):
        judge = {"faster": "A", "accuracy_a": 5, "accuracy_b": 2, "reason": "r"}
        mapped = run_eval.map_judge_to_arms(judge, ("baseline", "with-skill"))
        self.assertEqual(mapped["accuracy"], {"baseline": 5, "with-skill": 2})
        self.assertEqual(mapped["faster"], "baseline")
        judge["faster"] = "tie"
        self.assertEqual(run_eval.map_judge_to_arms(judge, ("with-skill", "baseline"))["faster"], "tie")

    def test_order_reproducible_and_complete(self):
        first = run_eval.judge_order("seed", "01-oauth-login")
        self.assertEqual(first, run_eval.judge_order("seed", "01-oauth-login"))
        self.assertEqual(sorted(first), sorted(run_eval.ARMS))
        orders = {run_eval.judge_order(str(s), "01") for s in range(20)}
        self.assertEqual(len(orders), 2)


class AggregateTest(unittest.TestCase):
    def topic(self, tid, skill, base, faster, acc=(5, 4)):
        return {"id": tid, "faster": faster, "arms": {
            "with-skill": {"metrics": skill, "accuracy": acc[0], "meta": {"cost_usd": 0.5, "num_turns": 9},
                           "seconds": 100},
            "baseline": {"metrics": base, "accuracy": acc[1], "meta": {"cost_usd": 0.1, "num_turns": 2},
                         "seconds": 20}},
                "judge_meta": {"cost_usd": 0.05}}

    def test_totals(self):
        ok = run_eval.arm_metrics(["flowchart LR"], [check(nodes=8)], [True], "flowchart LR")
        bad = run_eval.arm_metrics(["flowchart TD"], [check(nodes=14, over=2, issues=3, passed=False)],
                                   [False], "flowchart LR")
        results = [self.topic("01", ok, bad, "with-skill"),
                   self.topic("02", ok, ok, "tie", acc=(4, None))]
        agg = run_eval.aggregate(results)
        skill, base = agg["arms"]["with-skill"], agg["arms"]["baseline"]
        self.assertEqual((skill["checker_pass"], skill["rendered"], skill["type_ok"]), (2, 2, 2))
        self.assertEqual((base["checker_pass"], base["rendered"], base["type_ok"]), (1, 1, 1))
        self.assertEqual(base["label_overruns"], 2)
        self.assertEqual(skill["accuracy_scores"], [5, 4])
        self.assertEqual(base["accuracy_scores"], [4, None])
        self.assertAlmostEqual(skill["mean_accuracy"], 4.5)
        self.assertEqual(base["mean_accuracy"], 4.0)
        self.assertEqual(agg["faster"], {"with-skill": 1, "baseline": 0, "tie": 1, "missing": 0})
        self.assertAlmostEqual(skill["cost_usd"], 1.0)
        self.assertAlmostEqual(agg["judge_cost_usd"], 0.1)
        self.assertEqual(skill["turns"], 18)
        self.assertEqual(agg["topics"], 2)
        self.assertEqual(base["not_mermaid"], 0)

    def test_counts_svg_answers(self):
        svg = run_eval.arm_metrics(["<svg/>"], [], [], "flowchart LR", fmt="svg")
        ok = run_eval.arm_metrics(["flowchart LR"], [check()], [True], "flowchart LR")
        agg = run_eval.aggregate([self.topic("01", ok, svg, "baseline")])
        self.assertEqual(agg["arms"]["baseline"]["not_mermaid"], 1)
        self.assertEqual(agg["arms"]["baseline"]["checker_pass"], 0)

    def test_missing_judge_and_metrics(self):
        results = [self.topic("01", None, None, None, acc=(None, None))]
        agg = run_eval.aggregate(results)
        self.assertEqual(agg["faster"]["missing"], 1)
        self.assertIsNone(agg["arms"]["with-skill"]["mean_accuracy"])
        self.assertEqual(agg["arms"]["with-skill"]["checker_pass"], 0)


if __name__ == "__main__":
    unittest.main()
