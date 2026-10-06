"""CLI tests for skills/ste-writing/scripts/ste_check.py.

All assertions use the JSON the checker prints. The checker is run as a
subprocess, the same way the agent and the evals run it.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "ste-writing" / "scripts" / "ste_check.py"
REPLACEMENTS = Path(__file__).resolve().parent / "fixtures" / "replacements.md"

FILLER = ["small", "dogs", "sleep", "under", "the", "old", "tree", "and",
          "cats", "watch", "from", "the", "wall"]


def filler(n):
    """Return n plain words that trigger no passive, progressive or perfect hit."""
    return [FILLER[i % len(FILLER)] for i in range(n)]


def descriptive(n):
    return " ".join(["The"] + filler(n - 1)) + "."


def numbered_step(n, number=1):
    return f"{number}. " + " ".join(["Open"] + filler(n - 1)) + "."


def run(text=None, *args, file_arg=None):
    cmd = [sys.executable, str(SCRIPT)]
    if file_arg is not None:
        cmd.append(str(file_arg))
    cmd.extend(args)
    proc = subprocess.run(
        cmd,
        input=None if text is None else text.encode("utf-8"),
        capture_output=True,
    )
    out = proc.stdout.decode("utf-8")
    data = json.loads(out) if out.strip() else None
    return proc.returncode, data


def only_sentence(text, *args):
    code, data = run(text, *args)
    assert code in (0, 1), (code, data)
    assert len(data["sentences"]) == 1, data["sentences"]
    return data["sentences"][0]


class SentenceLengthTests(unittest.TestCase):
    def test_26_word_descriptive_sentence_is_flagged(self):
        s = only_sentence(descriptive(26))
        self.assertEqual(s["words"], 26)
        self.assertEqual(s["kind"], "descriptive")
        self.assertEqual(s["limit"], 25)
        self.assertTrue(s["over_limit"])

    def test_24_word_descriptive_sentence_is_not_flagged(self):
        s = only_sentence(descriptive(24))
        self.assertEqual(s["words"], 24)
        self.assertFalse(s["over_limit"])

    def test_descriptive_sentence_at_exact_limit_is_not_flagged(self):
        self.assertFalse(only_sentence(descriptive(25))["over_limit"])

    def test_21_word_numbered_step_is_flagged(self):
        s = only_sentence(numbered_step(21))
        self.assertEqual(s["words"], 21)
        self.assertEqual(s["kind"], "procedural")
        self.assertEqual(s["limit"], 20)
        self.assertTrue(s["over_limit"])

    def test_20_word_numbered_step_is_not_flagged(self):
        s = only_sentence(numbered_step(20))
        self.assertEqual(s["words"], 20)
        self.assertFalse(s["over_limit"])

    def test_imperative_verb_makes_sentence_procedural(self):
        self.assertEqual(only_sentence("Close the valve.")["kind"], "procedural")

    def test_numbered_item_without_verb_is_procedural(self):
        self.assertEqual(only_sentence("1. The valve closes.")["kind"], "procedural")

    def test_bullet_item_is_its_own_unit(self):
        _, data = run("Steps:\n- The valve closes.\n- The pump stops.\n")
        self.assertEqual(data["totals"]["sentences"], 3)

    def test_star_bullet_item_is_its_own_unit(self):
        _, data = run("Steps:\n* The valve closes.\n* The pump stops.\n")
        self.assertEqual(data["totals"]["sentences"], 3)

    def test_emphasis_asterisks_are_not_list_markers(self):
        _, data = run("The **valve** closes.\n*Then* the pump stops.\n")
        self.assertEqual(data["totals"]["sentences"], 2)
        self.assertEqual(data["sentences"][0]["words"], 3)

    def test_abbreviation_does_not_split_sentence(self):
        _, data = run("Use a tool, e.g. a hammer, to fix it. Then rest.")
        self.assertEqual(data["totals"]["sentences"], 2)


class VoiceTests(unittest.TestCase):
    def test_passive_detected(self):
        s = only_sentence("The file is deleted by the script.")
        self.assertEqual(s["passive"], 1)
        self.assertEqual(s["progressive"], 0)

    def test_passive_with_adverb_and_irregular_participle(self):
        self.assertEqual(only_sentence("The door was quickly closed.")["passive"], 1)
        self.assertEqual(only_sentence("The data is sent to the host.")["passive"], 1)

    def test_negated_passive_detected(self):
        self.assertEqual(only_sentence("The file was not deleted.")["passive"], 1)
        self.assertEqual(only_sentence("The file was never quickly deleted.")["passive"], 1)

    def test_negated_perfect_detected(self):
        self.assertEqual(only_sentence("The team has not finished the work.")["perfect"], 1)

    def test_negated_progressive_detected(self):
        self.assertEqual(only_sentence("The server is not running the job.")["progressive"], 1)

    def test_active_sentence_has_no_hits(self):
        s = only_sentence("The script deletes the file.")
        self.assertEqual((s["passive"], s["progressive"], s["perfect"]), (0, 0, 0))

    def test_progressive_detected(self):
        s = only_sentence("The server is running the job.")
        self.assertEqual(s["progressive"], 1)
        self.assertEqual(s["passive"], 0)

    def test_perfect_detected(self):
        self.assertEqual(only_sentence("The team has finished the work.")["perfect"], 1)

    def test_perfect_with_irregular_participle(self):
        self.assertEqual(only_sentence("We have written the report.")["perfect"], 1)


class ExemptContentTests(unittest.TestCase):
    def test_passive_in_fenced_code_block_not_counted(self):
        text = "Run the tool.\n\n```\nThe file is deleted by the script.\n```\n"
        _, data = run(text)
        self.assertEqual(data["totals"]["passive"], 0)
        self.assertEqual(data["totals"]["sentences"], 1)

    def test_passive_in_inline_code_not_counted(self):
        _, data = run("Read the log `the file is deleted` first.")
        self.assertEqual(data["totals"]["passive"], 0)

    def test_blockquote_and_heading_not_measured(self):
        text = ("# The file is deleted by the script\n\n"
                "> The file is deleted by the script.\n\nRun the tool.\n")
        _, data = run(text)
        self.assertEqual(data["totals"]["passive"], 0)
        self.assertEqual(data["totals"]["sentences"], 1)

    def test_hash_without_space_is_prose_not_heading(self):
        _, data = run("#1 cause is the old pump.\n")
        self.assertEqual(data["totals"]["sentences"], 1)

    def test_seven_hashes_is_prose_not_heading(self):
        _, data = run("####### The pump stops.\n")
        self.assertEqual(data["totals"]["sentences"], 1)

    def test_deep_heading_is_not_measured(self):
        _, data = run("###### The file is deleted by the script\n\nRun the tool.\n")
        self.assertEqual(data["totals"]["sentences"], 1)

    def test_text_outside_code_block_still_measured(self):
        _, data = run("```\nx = 1\n```\n\nThe file is deleted by the script.\n")
        self.assertEqual(data["totals"]["passive"], 1)


class NounClusterTests(unittest.TestCase):
    def test_long_noun_cluster_flagged(self):
        s = only_sentence("The database connection pool timeout setting is low.")
        self.assertEqual(s["noun_clusters"], ["database connection pool timeout setting"])

    def test_three_word_cluster_not_flagged(self):
        s = only_sentence("The connection pool timeout is low.")
        self.assertEqual(s["noun_clusters"], [])


class ReplacementListTests(unittest.TestCase):
    def test_hits_reported_with_list_file(self):
        text = "Utilize the tool. Check the pump prior to the test."
        _, data = run(text, "--replacements", str(REPLACEMENTS))
        hits = [h.lower() for s in data["sentences"] for h in s["replacement_hits"]]
        self.assertEqual(sorted(hits), ["prior to", "utilize"])
        self.assertEqual(data["totals"]["replacement_hits"], 2)

    def test_multi_word_term_matches_case_insensitively(self):
        s = only_sentence("Prior to the test, wait.", "--replacements", str(REPLACEMENTS))
        self.assertEqual(len(s["replacement_hits"]), 1)

    def test_header_and_separator_rows_are_not_terms(self):
        s = only_sentence("The term replacement is plain.", "--replacements", str(REPLACEMENTS))
        self.assertEqual(s["replacement_hits"], [])

    def test_no_hits_without_list_file(self):
        _, data = run("Utilize the tool. Check the pump prior to the test.")
        self.assertEqual(data["totals"]["replacement_hits"], 0)

    def test_missing_replacement_file_is_usage_error(self):
        code, _ = run("Run it.", "--replacements", str(REPLACEMENTS) + ".missing")
        self.assertEqual(code, 2)


class LanguageTests(unittest.TestCase):
    def test_chinese_input_reports_metrics_not_available(self):
        code, data = run("請先關閉電源，然後打開蓋子。這個步驟很重要。")
        self.assertEqual(code, 0)
        self.assertEqual(data["language"], "other")
        self.assertFalse(data["metrics_available"])
        self.assertEqual(data["sentences"], [])
        self.assertEqual(data["totals"], {})
        self.assertIsNone(data["pass"])
        self.assertIsInstance(data["note"], str)

    def test_english_auto_is_available(self):
        _, data = run("Close the valve.")
        self.assertEqual(data["language"], "en")
        self.assertTrue(data["metrics_available"])

    def test_lang_other_forces_not_available(self):
        code, data = run("Close the valve.", "--lang", "other")
        self.assertEqual(code, 0)
        self.assertFalse(data["metrics_available"])

    def test_lang_en_forces_metrics_on_cjk_text(self):
        _, data = run("請先關閉電源。", "--lang", "en")
        self.assertEqual(data["language"], "en")
        self.assertTrue(data["metrics_available"])

    def test_cjk_in_code_block_does_not_change_language(self):
        text = "Run the tool.\n\n```\n請先關閉電源，然後打開蓋子。這個步驟很重要。\n```\n"
        _, data = run(text)
        self.assertEqual(data["language"], "en")


class PassFailTests(unittest.TestCase):
    PERFECT_TEXT = "The team has finished the work."

    def test_relaxed_passes_perfect_form(self):
        code, data = run(self.PERFECT_TEXT)
        self.assertEqual(code, 0)
        self.assertTrue(data["pass"])
        self.assertEqual(data["strictness"], "relaxed")

    def test_strict_fails_on_perfect_form(self):
        code, data = run(self.PERFECT_TEXT, "--strictness", "strict")
        self.assertEqual(code, 1)
        self.assertFalse(data["pass"])
        self.assertEqual(data["strictness"], "strict")

    def test_strict_fails_on_progressive_form(self):
        # 1 progressive in 20 sentences is exactly 5%: relaxed passes.
        text = "The server is running the job. " + "The pump stops. " * 19
        self.assertTrue(run(text)[1]["pass"])
        self.assertFalse(run(text, "--strictness", "strict")[1]["pass"])

    def test_strict_fails_on_replacement_hit_relaxed_passes(self):
        text = "Utilize the tool."
        code_r, data_r = run(text, "--replacements", str(REPLACEMENTS))
        code_s, data_s = run(text, "--strictness", "strict", "--replacements", str(REPLACEMENTS))
        self.assertEqual((code_r, data_r["pass"]), (0, True))
        self.assertEqual((code_s, data_s["pass"]), (1, False))

    def test_strict_fails_on_noun_cluster(self):
        text = "The database connection pool timeout setting is low."
        self.assertTrue(run(text)[1]["pass"])
        self.assertFalse(run(text, "--strictness", "strict")[1]["pass"])

    def test_strict_fails_on_passive_in_procedure(self):
        # 1 passive in 20 sentences is exactly 5%: relaxed passes.
        text = "1. The pump is stopped.\n" + "The pump stops. " * 19
        self.assertTrue(run(text)[1]["pass"])
        self.assertFalse(run(text, "--strictness", "strict")[1]["pass"])

    def test_strict_allows_passive_in_descriptive_sentence(self):
        text = "The pump is stopped. " + "The pump stops. " * 19
        self.assertTrue(run(text, "--strictness", "strict")[1]["pass"])

    def test_strict_passes_clean_text(self):
        code, data = run("Close the valve. Wait for the pump.", "--strictness", "strict")
        self.assertEqual(code, 0)
        self.assertTrue(data["pass"])

    def test_relaxed_fails_when_too_many_sentences_over_limit(self):
        code, data = run(descriptive(26) + " " + "The pump stops. " * 4)
        self.assertEqual(code, 1)
        self.assertEqual(data["totals"]["over_limit"], 1)
        self.assertAlmostEqual(data["totals"]["over_limit_ratio"], 0.2)
        self.assertFalse(data["pass"])

    def test_relaxed_fails_when_passive_progressive_ratio_high(self):
        code, data = run("The file is deleted. The pump stops. The valve closes. The fan starts.")
        self.assertEqual(code, 1)
        self.assertAlmostEqual(data["totals"]["passive_progressive_ratio"], 0.25)

    def test_output_has_the_settled_keys(self):
        _, data = run("Close the valve.")
        self.assertEqual(
            set(data),
            {"language", "metrics_available", "strictness", "sentences", "totals", "pass"},
        )
        self.assertEqual(
            set(data["totals"]),
            {"sentences", "over_limit", "passive", "progressive", "perfect",
             "noun_clusters", "replacement_hits", "over_limit_ratio",
             "passive_progressive_ratio"},
        )
        self.assertEqual(
            set(data["sentences"][0]),
            {"text", "kind", "words", "limit", "over_limit", "passive",
             "progressive", "perfect", "noun_clusters", "replacement_hits"},
        )


class InputTests(unittest.TestCase):
    def test_reads_file_argument(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "in.md"
            p.write_text("Close the valve.", encoding="utf-8")
            code, data = run(None, file_arg=p)
        self.assertEqual(code, 0)
        self.assertEqual(data["totals"]["sentences"], 1)

    def test_dash_reads_stdin(self):
        code, data = run("Close the valve.", file_arg="-")
        self.assertEqual(code, 0)
        self.assertEqual(data["totals"]["sentences"], 1)

    def test_missing_file_exits_2(self):
        code, _ = run(None, file_arg=ROOT / "tests" / "does-not-exist.md")
        self.assertEqual(code, 2)

    def test_invalid_strictness_exits_2(self):
        code, _ = run("Close the valve.", "--strictness", "loose")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
