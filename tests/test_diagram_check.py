"""CLI tests for skills/diagram-explainer/scripts/diagram_check.py.

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
SCRIPT = ROOT / "skills" / "diagram-explainer" / "scripts" / "diagram_check.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "diagram"


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


def rules(data):
    return [i["rule"] for i in data["issues"]]


def flow(n, label="Step"):
    """A chain of n nodes with short labels."""
    lines = ["flowchart TD"]
    for i in range(1, n):
        lines.append(f"    N{i}[{label} {i}] --> N{i + 1}[{label} {i + 1}]")
    return "\n".join(lines) + "\n"


def sequence(participants, messages):
    lines = ["sequenceDiagram"]
    lines += [f"    participant P{i}" for i in range(1, participants + 1)]
    for i in range(messages):
        lines.append(f"    P1->>P2: Msg {i}")
    return "\n".join(lines) + "\n"


class TypeTests(unittest.TestCase):
    def test_flowchart_and_graph_with_every_direction(self):
        for keyword in ("flowchart", "graph"):
            for direction in ("TD", "TB", "LR", "RL", "BT"):
                with self.subTest(keyword=keyword, direction=direction):
                    code, data = run(f"{keyword} {direction}\n    A --> B\n")
                    self.assertEqual(code, 0, data)
                    self.assertEqual(data["type"], "flowchart")

    def test_sequence_diagram(self):
        code, data = run("sequenceDiagram\n    A->>B: Hi\n")
        self.assertEqual(code, 0, data)
        self.assertEqual(data["type"], "sequenceDiagram")

    def test_state_diagram_v2_and_v1(self):
        for header in ("stateDiagram-v2", "stateDiagram"):
            with self.subTest(header=header):
                code, data = run(f"{header}\n    [*] --> A\n")
                self.assertEqual(code, 0, data)
                self.assertEqual(data["type"], "stateDiagram-v2")

    def test_unsupported_type_is_an_issue(self):
        code, data = run("classDiagram\n    class A\n")
        self.assertEqual(code, 1)
        self.assertEqual(data["type"], "classDiagram")
        self.assertIn("unsupported-type", rules(data))
        self.assertFalse(data["pass"])

    def test_empty_input_is_unsupported(self):
        code, data = run("\n%% only a comment\n")
        self.assertEqual(code, 1)
        self.assertIn("unsupported-type", rules(data))

    def test_header_after_comments_and_init_is_still_found(self):
        code, data = run("%% note\n\nflowchart LR\n    A --> B\n")
        self.assertEqual(code, 0, data)
        self.assertEqual(data["type"], "flowchart")


class FlowchartCountTests(unittest.TestCase):
    def test_nodes_edges_subgraphs_in_fixture(self):
        code, data = run(file_arg=FIXTURES / "pass_flowchart.mmd")
        self.assertEqual(code, 0, data)
        self.assertEqual(data["counts"], {"nodes": 5, "edges": 4, "subgraphs": 1})

    def test_edge_endpoints_without_definitions_are_nodes(self):
        code, data = run("flowchart LR\n    A --> B\n    B --> C\n    A --> C\n")
        self.assertEqual(data["counts"]["nodes"], 3)
        self.assertEqual(data["counts"]["edges"], 3)

    def test_chain_and_ampersand_edges(self):
        code, data = run("flowchart LR\n    A --> B --> C\n    D & E --> F\n")
        self.assertEqual(data["counts"]["nodes"], 6)
        self.assertEqual(data["counts"]["edges"], 4)

    def test_edge_styles_are_edges(self):
        text = "flowchart LR\n    A --- B\n    B -.-> C\n    C ==> D\n    D <--> E\n    E -- text --> F\n"
        code, data = run(text)
        self.assertEqual(data["counts"]["nodes"], 6)
        self.assertEqual(data["counts"]["edges"], 5)

    def test_subgraph_id_used_as_endpoint_is_not_a_node(self):
        text = "flowchart TD\n    subgraph S1\n        A\n    end\n    B --> S1\n"
        code, data = run(text)
        self.assertEqual(data["counts"]["nodes"], 2)
        self.assertEqual(data["counts"]["subgraphs"], 1)

    def test_shapes_do_not_change_node_count(self):
        text = ("flowchart TD\n    A((Round)) --> B([Pill])\n    B --> C[(DB)]\n"
                "    C --> D{{Hex}}\n    D --> E>Flag]\n")
        code, data = run(text)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["counts"]["nodes"], 5)
        self.assertEqual(data["counts"]["edges"], 4)

    def test_style_and_class_lines_add_no_nodes(self):
        text = "flowchart TD\n    A --> B\n    style A fill:#f9f\n    classDef hot fill:#f00\n    class B hot\n"
        code, data = run(text)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["counts"]["nodes"], 2)


class SequenceCountTests(unittest.TestCase):
    def test_fixture_counts(self):
        code, data = run(file_arg=FIXTURES / "pass_sequence.mmd")
        self.assertEqual(code, 0, data)
        self.assertEqual(data["counts"], {"participants": 3, "messages": 5})

    def test_implicit_participants_are_counted_once(self):
        code, data = run("sequenceDiagram\n    participant A\n    A->>B: One\n    B->>C: Two\n    C-->>A: Three\n")
        self.assertEqual(data["counts"], {"participants": 3, "messages": 3})

    def test_actor_and_arrow_variants(self):
        text = ("sequenceDiagram\n    actor U\n    U->>S: a\n    S-->>U: b\n    U-)S: c\n"
                "    U-xS: d\n    U->>+S: e\n    S-->>-U: f\n")
        code, data = run(text)
        self.assertEqual(data["counts"], {"participants": 2, "messages": 6})


class StateCountTests(unittest.TestCase):
    def test_fixture_counts_exclude_start_end(self):
        code, data = run(file_arg=FIXTURES / "pass_state.mmd")
        self.assertEqual(code, 0, data)
        self.assertEqual(data["counts"], {"states": 3, "transitions": 5})

    def test_declared_and_composite_states(self):
        text = ("stateDiagram-v2\n    state \"Waiting for input\" as Wait\n    state Busy {\n"
                "        [*] --> Inner\n    }\n    Idle : Does nothing\n    [*] --> Wait\n    Wait --> Busy\n")
        code, data = run(text)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["counts"], {"states": 4, "transitions": 3})


class BudgetTests(unittest.TestCase):
    def test_default_budgets_are_reported(self):
        code, data = run(file_arg=FIXTURES / "pass_flowchart.mmd")
        self.assertEqual(data["budgets"], {
            "max_nodes": 12, "max_participants": 6, "max_messages": 12,
            "max_label_words": 5, "max_label_chars": 10})

    def test_nodes_at_limit_pass_and_over_limit_fail(self):
        code, data = run(flow(12))
        self.assertEqual(code, 0, data)
        code, data = run(flow(13))
        self.assertEqual(code, 1)
        self.assertIn("too-many-nodes", rules(data))
        self.assertFalse(data["pass"])

    def test_max_nodes_flag(self):
        code, data = run(flow(4), "--max-nodes", "3")
        self.assertEqual(code, 1)
        self.assertEqual(data["budgets"]["max_nodes"], 3)
        self.assertIn("too-many-nodes", rules(data))
        code, data = run(flow(13), "--max-nodes", "13")
        self.assertEqual(code, 0, data)

    def test_state_diagram_uses_node_budget(self):
        text = "stateDiagram-v2\n" + "".join(f"    S{i} --> S{i + 1}\n" for i in range(4))
        code, data = run(text, "--max-nodes", "4")
        self.assertEqual(code, 1)
        self.assertIn("too-many-nodes", rules(data))

    def test_participants(self):
        code, data = run(sequence(6, 1))
        self.assertEqual(code, 0, data)
        code, data = run(sequence(7, 1))
        self.assertEqual(code, 1)
        self.assertIn("too-many-participants", rules(data))
        code, data = run(sequence(7, 1), "--max-participants", "7")
        self.assertEqual(code, 0, data)

    def test_messages(self):
        code, data = run(sequence(2, 12))
        self.assertEqual(code, 0, data)
        code, data = run(sequence(2, 13))
        self.assertEqual(code, 1)
        self.assertIn("too-many-messages", rules(data))
        code, data = run(sequence(2, 13), "--max-messages", "13")
        self.assertEqual(code, 0, data)

    def test_label_words(self):
        code, data = run("flowchart TD\n    A[one two three four five] --> B[ok]\n")
        self.assertEqual(code, 0, data)
        code, data = run("flowchart TD\n    A[one two three four five six] --> B[ok]\n")
        self.assertEqual(code, 1)
        self.assertIn("label-too-long", rules(data))
        code, data = run("flowchart TD\n    A[one two three] --> B[ok]\n", "--max-label-words", "2")
        self.assertEqual(code, 1)
        self.assertEqual(data["budgets"]["max_label_words"], 2)

    def test_label_chars_for_cjk(self):
        code, data = run("flowchart TD\n    A[一二三四五六七八九十] --> B[完成]\n")
        self.assertEqual(code, 0, data)
        code, data = run("flowchart TD\n    A[一二三四五六七八九十一] --> B[完成]\n")
        self.assertEqual(code, 1)
        self.assertIn("label-too-long", rules(data))
        code, data = run("flowchart TD\n    A[一二三] --> B[完成]\n", "--max-label-chars", "2")
        self.assertEqual(code, 1)
        self.assertEqual(data["budgets"]["max_label_chars"], 2)


class LabelTests(unittest.TestCase):
    def label(self, data, text):
        found = [lab for lab in data["labels"] if lab["text"] == text]
        self.assertEqual(len(found), 1, data["labels"])
        return found[0]

    def test_latin_words(self):
        code, data = run(file_arg=FIXTURES / "pass_flowchart.mmd")
        lab = self.label(data, "User clicks Buy")
        self.assertEqual((lab["words"], lab["chars"], lab["over"]), (3, 0, False))

    def test_edge_and_subgraph_labels_are_measured(self):
        code, data = run(file_arg=FIXTURES / "pass_flowchart.mmd")
        self.assertEqual(self.label(data, "Yes")["words"], 1)
        self.assertEqual(self.label(data, "Client side")["words"], 2)
        self.assertEqual(len(data["labels"]), 8)

    def test_cjk_chars_in_fixture(self):
        code, data = run(file_arg=FIXTURES / "cjk_flowchart.mmd")
        self.assertEqual(code, 0, data)
        lab = self.label(data, "使用者登入")
        self.assertEqual((lab["words"], lab["chars"], lab["over"]), (0, 5, False))
        self.assertEqual(self.label(data, "顯示錯誤訊息")["chars"], 6)

    def test_mixed_label_counts_both(self):
        code, data = run("flowchart TD\n    A[API 服務] --> B[ok]\n")
        lab = self.label(data, "API 服務")
        self.assertEqual((lab["words"], lab["chars"]), (1, 2))

    def test_over_flag_in_labels(self):
        code, data = run("flowchart TD\n    A[a b c d e f] --> B[ok]\n")
        self.assertTrue(self.label(data, "a b c d e f")["over"])
        self.assertFalse(self.label(data, "ok")["over"])

    def test_issue_carries_line_number(self):
        code, data = run("flowchart TD\n    A --> B\n    C[a b c d e f] --> D\n")
        issue = [i for i in data["issues"] if i["rule"] == "label-too-long"][0]
        self.assertEqual(issue["line"], 3)
        self.assertTrue(issue["message"])

    def test_sequence_and_state_labels(self):
        code, data = run("sequenceDiagram\n    participant W as Web app\n    W->>API: Send order now please ok thanks\n")
        self.assertEqual(code, 1)
        self.assertEqual(self.label(data, "Web app")["words"], 2)
        self.assertEqual(self.label(data, "Send order now please ok thanks")["words"], 6)
        code, data = run("stateDiagram-v2\n    A --> B : 這是一段非常非常長的轉換說明文字\n")
        self.assertEqual(code, 1)
        self.assertIn("label-too-long", rules(data))


class FragileSyntaxTests(unittest.TestCase):
    def assertFlags(self, text, rule):
        code, data = run(text)
        self.assertEqual(code, 1, data)
        self.assertIn(rule, rules(data))
        self.assertFalse(data["pass"])
        return data

    def test_html_in_node_label(self):
        data = self.assertFlags("flowchart TD\n    A[Line<br/>two] --> B\n", "html-in-label")
        self.assertEqual([i for i in data["issues"] if i["rule"] == "html-in-label"][0]["line"], 2)

    def test_html_in_quoted_label_and_sequence_message(self):
        self.assertFlags('flowchart TD\n    A["<b>Bold</b>"] --> B\n', "html-in-label")
        self.assertFlags("sequenceDiagram\n    A->>B: Hi<br/>there\n", "html-in-label")

    def test_click_callback(self):
        self.assertFlags("flowchart TD\n    A --> B\n    click A callback\n", "click-callback")
        self.assertFlags('flowchart TD\n    A --> B\n    click B href "https://example.com"\n', "click-callback")

    def test_init_directive(self):
        self.assertFlags("%%{init: {'theme': 'dark'}}%%\nflowchart TD\n    A --> B\n", "init-directive")

    def test_style_with_url(self):
        self.assertFlags("flowchart TD\n    A --> B\n    style A fill:url(#grad)\n", "style-url")
        self.assertFlags("flowchart TD\n    A --> B\n    classDef c fill:url(#grad)\n", "style-url")

    def test_style_without_url_is_fine(self):
        code, data = run("flowchart TD\n    A --> B\n    style A fill:#f9f\n")
        self.assertEqual(code, 0, data)

    def test_unbalanced_subgraph(self):
        data = self.assertFlags("flowchart TD\n    subgraph S\n        A --> B\n", "unbalanced-block")
        self.assertEqual(data["issues"][0]["line"], 2)
        self.assertFlags("flowchart TD\n    A --> B\n    end\n", "unbalanced-block")

    def test_balanced_nested_subgraphs_pass(self):
        code, data = run("flowchart TD\n    subgraph O\n        subgraph I\n            A\n        end\n    end\n")
        self.assertEqual(code, 0, data)
        self.assertEqual(data["counts"]["subgraphs"], 2)

    def test_unbalanced_sequence_blocks(self):
        for opener in ("alt", "opt", "loop", "par", "rect rgb(0,0,0)", "critical", "break"):
            with self.subTest(opener=opener):
                self.assertFlags(f"sequenceDiagram\n    {opener} Cond\n        A->>B: Hi\n", "unbalanced-block")
                code, data = run(f"sequenceDiagram\n    {opener} Cond\n        A->>B: Hi\n    end\n")
                self.assertEqual(code, 0, data)
        self.assertFlags("sequenceDiagram\n    A->>B: Hi\n    end\n", "unbalanced-block")

    def test_unbalanced_state_braces(self):
        self.assertFlags("stateDiagram-v2\n    state X {\n        [*] --> A\n", "unbalanced-block")

    def test_unquoted_label_with_special_characters(self):
        for ch in "()[]{}\"|;#":
            with self.subTest(ch=ch):
                self.assertFlags(f"flowchart TD\n    A[Start {ch} end] --> B\n", "unquoted-label")

    def test_unquoted_label_with_parentheses(self):
        data = self.assertFlags("flowchart TD\n    A[Call f(x)] --> B(Go (now))\n", "unquoted-label")
        self.assertEqual(len([i for i in data["issues"] if i["rule"] == "unquoted-label"]), 2)

    def test_quoted_label_with_special_characters_is_fine(self):
        code, data = run('flowchart TD\n    A["Call f(x) | #1"] --> B["Go {now}"]\n')
        self.assertNotIn("unquoted-label", rules(data))

    def test_edge_label_pipes_are_not_flagged(self):
        code, data = run("flowchart TD\n    A -->|Yes| B\n")
        self.assertEqual(code, 0, data)


class InputTests(unittest.TestCase):
    def test_stdin_and_dash_and_file_agree(self):
        text = (FIXTURES / "pass_state.mmd").read_text(encoding="utf-8")
        _, from_stdin = run(text)
        _, from_dash = run(text, file_arg="-")
        _, from_file = run(file_arg=FIXTURES / "pass_state.mmd")
        self.assertEqual(from_stdin, from_dash)
        self.assertEqual(from_stdin, from_file)

    def test_bom_and_crlf_are_accepted(self):
        raw = "﻿flowchart TD\r\n    A --> B\r\n".encode("utf-8")
        code, data = run(raw=raw)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["counts"]["nodes"], 2)

    def test_output_is_one_json_object_with_expected_keys(self):
        code, data = run(file_arg=FIXTURES / "pass_flowchart.mmd")
        self.assertEqual(set(data), {"type", "counts", "budgets", "labels", "issues", "pass"})
        self.assertIs(data["pass"], True)
        self.assertEqual(data["issues"], [])


class ExitCodeTests(unittest.TestCase):
    def test_passing_fixtures_exit_0(self):
        for name in ("pass_flowchart", "pass_sequence", "pass_state", "cjk_flowchart"):
            with self.subTest(name=name):
                code, data = run(file_arg=FIXTURES / f"{name}.mmd")
                self.assertEqual(code, 0, data)
                self.assertTrue(data["pass"])

    def test_failed_check_exits_1(self):
        code, data = run(flow(13))
        self.assertEqual(code, 1)

    def test_missing_file_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, data = run(file_arg=Path(tmp) / "nope.mmd")
        self.assertEqual(code, 2)
        self.assertIsNone(data)

    def test_invalid_utf8_exits_2(self):
        code, data = run(raw=b"flowchart TD\n    A[\xff\xfe] --> B\n")
        self.assertEqual(code, 2)

    def test_bad_flag_values_exit_2(self):
        for args in (["--max-nodes", "many"], ["--max-nodes", "-1"], ["--bogus"]):
            with self.subTest(args=args):
                code, data = run("flowchart TD\n    A --> B\n", *args)
                self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
