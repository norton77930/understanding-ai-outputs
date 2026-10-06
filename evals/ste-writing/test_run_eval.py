"""Unit tests for the pure parts of run_eval.py (parsing, aggregation, thresholds).

Run: python -m unittest discover -s evals/ste-writing -p "test_run_eval.py"
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_eval  # noqa: E402


def totals(sentences, over, passive=0, progressive=0, perfect=0):
    return {"sentences": sentences, "over_limit": over, "passive": passive,
            "progressive": progressive, "perfect": perfect}


def passage(pid, skill_totals, base_totals, skill_meaning, base_meaning, readable, lang="en"):
    return {"id": pid, "lang": lang, "readable": readable, "arms": {
        "with-skill": {"totals": skill_totals, "meaning": skill_meaning},
        "baseline": {"totals": base_totals, "meaning": base_meaning}}}


class ParseJudgeTest(unittest.TestCase):
    def test_extracts_json_from_chatty_reply(self):
        reply = 'Here you go:\n{"meaning_a": 5, "meaning_b": "4", "more_readable": "b", "reason": "ok"}'
        self.assertEqual(run_eval.parse_judge(reply),
                         {"meaning_a": 5, "meaning_b": 4, "more_readable": "B", "reason": "ok"})

    def test_accepts_tie(self):
        reply = '{"meaning_a": 3, "meaning_b": 3, "more_readable": "Tie", "reason": ""}'
        self.assertEqual(run_eval.parse_judge(reply)["more_readable"], "tie")

    def test_rejects_invalid(self):
        self.assertIsNone(run_eval.parse_judge("no json here"))
        self.assertIsNone(run_eval.parse_judge('{"meaning_a": 6, "meaning_b": 3, "more_readable": "A"}'))
        self.assertIsNone(run_eval.parse_judge('{"meaning_a": 3, "meaning_b": 3, "more_readable": "C"}'))


class MapJudgeTest(unittest.TestCase):
    def test_maps_ab_back_to_arms(self):
        judge = {"meaning_a": 5, "meaning_b": 2, "more_readable": "A", "reason": "r"}
        mapped = run_eval.map_judge_to_arms(judge, ("baseline", "with-skill"))
        self.assertEqual(mapped["meaning"], {"baseline": 5, "with-skill": 2})
        self.assertEqual(mapped["readable"], "baseline")

    def test_tie_stays_tie(self):
        judge = {"meaning_a": 4, "meaning_b": 4, "more_readable": "tie", "reason": ""}
        self.assertEqual(run_eval.map_judge_to_arms(judge, ("with-skill", "baseline"))["readable"], "tie")

    def test_order_is_reproducible_and_complete(self):
        first = run_eval.judge_order("seed", "01-api-doc")
        self.assertEqual(first, run_eval.judge_order("seed", "01-api-doc"))
        self.assertEqual(sorted(first), sorted(run_eval.ARMS))


class AggregateTest(unittest.TestCase):
    def test_pools_sentences_and_skips_chinese(self):
        results = [
            passage("01-a", totals(10, 1, 1), totals(10, 6, 3, 1), 5, 5, "with-skill"),
            passage("02-b", totals(10, 0), totals(10, 4), 4, 5, "tie"),
            passage("07-zh-c", None, None, 5, 5, "baseline", lang="zh"),
        ]
        agg = run_eval.aggregate(results)
        self.assertEqual(agg["with-skill"]["sentences"], 20)
        self.assertAlmostEqual(agg["with-skill"]["over_limit_ratio"], 0.05)
        self.assertAlmostEqual(agg["with-skill"]["passive_progressive_ratio"], 0.05)
        self.assertAlmostEqual(agg["baseline"]["over_limit_ratio"], 0.5)
        self.assertEqual(agg["with-skill"]["min_meaning"], 4)
        self.assertEqual(agg["readability"], {"with-skill": 1, "baseline": 0, "tie": 1, "missing": 0})

    def test_missing_metrics_are_counted(self):
        agg = run_eval.aggregate([passage("01-a", None, totals(5, 1), None, 5, None)])
        self.assertEqual(agg["with-skill"]["missing_metrics"], 1)
        self.assertIsNone(agg["with-skill"]["min_meaning"])
        self.assertEqual(agg["readability"]["missing"], 1)


class EvaluateTest(unittest.TestCase):
    def verdict(self, results):
        return run_eval.evaluate(run_eval.aggregate(results))

    def good(self):
        return [passage("01-a", totals(20, 2, 1), totals(20, 10, 5), 5, 5, "with-skill"),
                passage("02-b", totals(20, 2), totals(20, 9, 4), 4, 5, "with-skill")]

    def test_pass_at_the_boundaries(self):
        # 4/40 over limit = 10% (exactly 90% within); 2/40 passive = 5%.
        results = [passage("01-a", totals(20, 2, 1), totals(20, 10), 4, 5, "with-skill"),
                   passage("02-b", totals(20, 2, 1), totals(20, 10), 4, 5, "with-skill")]
        self.assertEqual(self.verdict(results)["verdict"], "PASS")

    def test_pass(self):
        self.assertEqual(self.verdict(self.good())["verdict"], "PASS")

    def test_fail_on_over_limit(self):
        results = self.good()
        results[0]["arms"]["with-skill"]["totals"] = totals(20, 6)
        ev = self.verdict(results)
        self.assertEqual(ev["verdict"], "FAIL")
        self.assertFalse(ev["checks"]["within_limit"]["pass"])

    def test_fail_on_passive_progressive(self):
        results = self.good()
        results[0]["arms"]["with-skill"]["totals"] = totals(20, 0, 2, 1)
        self.assertFalse(self.verdict(results)["checks"]["passive_progressive"]["pass"])

    def test_fail_when_one_passage_meaning_is_low(self):
        results = self.good()
        results[1]["arms"]["with-skill"]["meaning"] = 3
        ev = self.verdict(results)
        self.assertEqual(ev["verdict"], "FAIL")
        self.assertFalse(ev["checks"]["meaning"]["pass"])

    def test_fail_when_baseline_wins_readability(self):
        results = self.good()
        results[0]["readable"] = "baseline"
        results[1]["readable"] = "tie"
        ev = self.verdict(results)
        self.assertFalse(ev["checks"]["readability"]["pass"])

    def test_incomplete_when_data_is_missing(self):
        results = self.good()
        results[0]["arms"]["with-skill"]["meaning"] = None
        results[0]["readable"] = None
        self.assertEqual(self.verdict(results)["verdict"], "INCOMPLETE")


if __name__ == "__main__":
    unittest.main()
