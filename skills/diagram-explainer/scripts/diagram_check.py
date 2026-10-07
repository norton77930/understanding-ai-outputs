#!/usr/bin/env python3
"""Check Mermaid diagram source: size budgets, label length, fragile syntax.

Usage:
    python diagram_check.py [FILE|-] [--max-nodes N] [--max-participants N]
                            [--max-messages N] [--max-label-words N]
                            [--max-label-chars N]

Reads FILE (or stdin when FILE is omitted or "-") and prints one JSON object
on stdout (UTF-8). Exit code: 0 = pass, 1 = check failed, 2 = usage or input
error. Python standard library only.

Output shape:
    {"type": str | null,
     "counts": {...},
     "budgets": {"max_nodes", "max_participants", "max_messages",
                 "max_label_words", "max_label_chars"},
     "labels": [{"text", "words", "chars", "over"}],
     "issues": [{"rule", "line", "message"}],
     "pass": bool}

type is "flowchart" (flowchart and graph), "sequenceDiagram",
"stateDiagram-v2" (stateDiagram and stateDiagram-v2), or the first word of an
unsupported diagram (null when there is no diagram). counts depend on the type:
    flowchart:       nodes, edges, subgraphs
    sequenceDiagram: participants, messages
    stateDiagram-v2: states (without [*]), transitions
Unsupported types have an empty counts object.

Labels: node, edge, subgraph, participant alias, message, state and
transition texts. words counts Latin words, chars counts CJK characters
(ideographs, kana, hangul). A label is over when words or chars is above its
budget (exactly the budget is fine). HTML tags and entity codes are ignored
when measuring.

Rules (issue "rule" values):
    unsupported-type       no diagram, or a type other than the three above
    too-many-nodes         nodes (flowchart) or states (state) over --max-nodes
    too-many-participants  over --max-participants
    too-many-messages      over --max-messages
    label-too-long         a label is over the word or character budget
    html-in-label          an HTML tag in a label
    click-callback         a "click" line
    init-directive         a %%{init ...}%% directive, or config/theme in the
                           front matter
    style-url              a style, classDef or linkStyle line with url(
    unbalanced-block       subgraph/end, sequence alt/opt/loop/par/rect/
                           critical/break/box vs end, or state { } mismatch
    unquoted-label         a flowchart node label with any of ( ) [ ] { } " | ; #
                           that is not wrapped in double quotes

Method (line based and APPROXIMATE, not a Mermaid parser): one statement per
line (flowchart statements may also be split on ";"); full-line "%%"
comments and front matter are skipped; "A & B --> C" counts every edge.
"""

import argparse
import json
import re
import sys

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

DEFAULT_BUDGETS = {
    "max_nodes": 12,
    "max_participants": 6,
    "max_messages": 12,
    "max_label_words": 5,
    "max_label_chars": 10,
}

UNQUOTED_SPECIALS = "()[]{}\"|;#"

_WORD_RE = re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*")
_HTML_TAG_RE = re.compile(r"</?[A-Za-z][^<>]*>")
_ENTITY_RE = re.compile(r"#\w+;")
_HEADER_RE = re.compile(r"^(\S+)")
_INIT_RE = re.compile(r"^%%\{\s*init(?:ialize)?\b")
_FRONT_CONFIG_RE = re.compile(r"^\s*(?:config|theme|themeVariables|themeCSS)\s*:")
_STYLE_RE = re.compile(r"^(?:style|classDef|linkStyle)\b")
_CLICK_RE = re.compile(r"^click\b")
_ID = r"\w+(?:-\w+)*"

# Flowchart edges.
_EDGE_TEXT_RE = re.compile(
    r"[<xo]?(?:--|==|-\.)\s+(?P<t>.+?)\s+(?:-->|---|==>|===|\.->|\.-)")
_EDGE_RE = re.compile(r"[<xo]?(?:-{2,}[>xo-]?|={2,}[>xo=]?|-\.+-[>xo]?|~{3,})")
_EDGE_PIPE_RE = re.compile(r"\s*\|(?P<t>[^|]*)\|")
_NODE_ID_RE = re.compile(_ID)
_NODE_TRAIL_RE = re.compile(r"\s*(?:$|&|:::|[<xo]?(?:--|==|-\.|~~))")
_CLASS_SUFFIX_RE = re.compile(r":::\w+")

# Opener -> accepted closers, longest opener first.
_SHAPES = (
    ("(((", (")))",)), ("((", ("))",)), ("([", ("])",)), ("[[", ("]]",)),
    ("[(", (")]",)), ("[/", ("/]", "\\]")), ("[\\", ("\\]", "/]")),
    ("{{", ("}}",)), ("(", (")",)), ("[", ("]",)), ("{", ("}",)), (">", ("]",)),
)

_SUBGRAPH_TITLE_RE = re.compile(rf"^({_ID})\s*\[(.*)\]\s*$")

# Sequence diagrams.
_SEQ_BLOCK_RE = re.compile(r"^(?:alt|opt|loop|par|rect|critical|break|box)(?:\s|$)")
_SEQ_SKIP_RE = re.compile(
    r"^(?:else|and|option|autonumber|title|note|activate|deactivate|destroy|"
    r"links?|properties|details)\b", re.IGNORECASE)
_SEQ_PARTICIPANT_RE = re.compile(
    r"^(?:create\s+)?(?:participant|actor)\s+([^\s@]+)(?:\s*@\{.*\})?(?:\s+as\s+(.+))?$")
_SEQ_ID = r"[\w.]+(?:-[\w.]+)*"
_SEQ_MESSAGE_RE = re.compile(
    rf"^({_SEQ_ID})\s*(<<-->>|<<->>|-->>|->>|--x|-x|--\)|-\)|-->|->)\s*[+-]?\s*"
    rf"({_SEQ_ID})\s*:\s*(.*)$")

# State diagrams.
_STATE_ID = r"\[\*\]|[\w.]+(?:-[\w.]+)*"
_STATE_TRANSITION_RE = re.compile(
    rf"^({_STATE_ID})\s*-->\s*({_STATE_ID})\s*(?::\s*(.*))?$")
_STATE_DECL_RE = re.compile(
    r'^state\s+(?:"([^"]*)"\s+as\s+)?([\w.]+(?:-[\w.]+)*)\s*(\{)?\s*(?:<<\w+>>)?\s*$')
_STATE_DESC_RE = re.compile(r"^([\w.]+(?:-[\w.]+)*)\s*:\s*(.+)$")
_STATE_NOTE_RE = re.compile(r"^note\b", re.IGNORECASE)


class InputError(Exception):
    pass


# --- label measuring --------------------------------------------------------

def _is_cjk(ch):
    cp = ord(ch)
    return (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF
            or 0x3040 <= cp <= 0x30FF or 0xAC00 <= cp <= 0xD7AF
            or 0xF900 <= cp <= 0xFAFF)


def measure(text):
    """Return (latin words, CJK characters) of a label."""
    plain = _ENTITY_RE.sub(" ", _HTML_TAG_RE.sub(" ", text)).replace("`", " ")
    chars = sum(1 for c in plain if _is_cjk(c))
    latin = "".join(" " if _is_cjk(c) else c for c in plain)
    return len(_WORD_RE.findall(latin)), chars


class Report:
    def __init__(self, budgets):
        self.budgets = budgets
        self.labels = []
        self.issues = []
        self._seen = set()

    def issue(self, rule, line, message):
        key = (rule, line, message)
        if key not in self._seen:
            self._seen.add(key)
            self.issues.append({"rule": rule, "line": line, "message": message})

    def label(self, text, line):
        text = text.strip()
        if not text:
            return
        words, chars = measure(text)
        over = (words > self.budgets["max_label_words"]
                or chars > self.budgets["max_label_chars"])
        self.labels.append({"text": text, "words": words, "chars": chars, "over": over})
        if _HTML_TAG_RE.search(text):
            self.issue("html-in-label", line,
                       f"HTML tag in label {text!r}; use plain text")
        if over:
            self.issue("label-too-long", line,
                       f"label {text!r} has {words} words and {chars} CJK characters "
                       f"(budget {self.budgets['max_label_words']} words, "
                       f"{self.budgets['max_label_chars']} characters)")


# --- shared line rules --------------------------------------------------------

def common_rules(stripped, line, report):
    """Rules that apply to any line. Returns True when the line is consumed."""
    if _INIT_RE.match(stripped):
        report.issue("init-directive", line,
                     "init directive; theme and config overrides do not render everywhere")
        return True
    if stripped.startswith("%%"):
        return True
    if _CLICK_RE.match(stripped):
        report.issue("click-callback", line,
                     "click line; callbacks and links are not supported everywhere")
        return True
    if _STYLE_RE.match(stripped):
        if "url(" in stripped.lower():
            report.issue("style-url", line, "url( in a style line; it may not render")
        return True
    return False


def split_lines(text):
    """Return ([(line number, stripped line)], front matter config line numbers).
    Front matter and blank lines are left out of the first list."""
    raw = text.splitlines()
    items = []
    front_issues = []
    i = 0
    if raw and raw[0].strip() == "---":
        j = 1
        while j < len(raw) and raw[j].strip() != "---":
            if _FRONT_CONFIG_RE.match(raw[j]):
                front_issues.append(j + 1)
            j += 1
        i = j + 1 if j < len(raw) else len(raw)
    for n in range(i, len(raw)):
        stripped = raw[n].strip()
        if stripped:
            items.append((n + 1, stripped))
    return items, front_issues


# --- flowchart ----------------------------------------------------------------

def split_statements(line):
    """Split on ";" outside quotes and brackets."""
    parts, buf, depth, quote = [], [], 0, False
    for ch in line:
        if ch == '"':
            quote = not quote
        elif not quote:
            if ch in "[({":
                depth += 1
            elif ch in "])}":
                depth = max(0, depth - 1)
            elif ch == ";" and depth == 0:
                parts.append("".join(buf))
                buf = []
                continue
        buf.append(ch)
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def parse_shape(stmt, pos):
    """Parse a node shape at stmt[pos]. Returns (label, quoted, end) or None."""
    for opener, closers in _SHAPES:
        if not stmt.startswith(opener, pos):
            continue
        start = pos + len(opener)
        body = stmt[start:].lstrip()
        if body.startswith('"'):
            close_quote = body.find('"', 1)
            if close_quote != -1:
                after = body[close_quote + 1:].lstrip()
                for closer in closers:
                    if after.startswith(closer):
                        end = len(stmt) - len(after) + len(closer)
                        return body[1:close_quote], True, end
        # Unquoted: first closer followed by end, "&", ":::" or an edge.
        best = None
        for closer in closers:
            idx = stmt.find(closer, start)
            while idx != -1:
                if _NODE_TRAIL_RE.match(stmt, idx + len(closer)):
                    if best is None or idx < best[0]:
                        best = (idx, closer)
                    break
                idx = stmt.find(closer, idx + 1)
        if best is None:
            return stmt[start:], False, len(stmt)
        return stmt[start:best[0]], False, best[0] + len(best[1])
    return None


def parse_flow_statement(stmt, line, state, report):
    pos, n = 0, len(stmt)
    groups, current = [], []
    expect_node = True
    while pos < n:
        while pos < n and stmt[pos].isspace():
            pos += 1
        if pos >= n:
            break
        if expect_node:
            m = _NODE_ID_RE.match(stmt, pos)
            if not m:
                break
            node_id = m.group(0)
            pos = m.end()
            if stmt.startswith("@{", pos):
                close = stmt.find("}", pos)
                pos = n if close == -1 else close + 1
            shape = parse_shape(stmt, pos) if pos < n else None
            if shape:
                label, quoted, pos = shape
                report.label(label, line)
                if not quoted and any(c in label for c in UNQUOTED_SPECIALS):
                    bad = sorted({c for c in label if c in UNQUOTED_SPECIALS})
                    report.issue("unquoted-label", line,
                                 f"label {label.strip()!r} has {' '.join(bad)} outside "
                                 "double quotes; wrap the label in double quotes")
            state["nodes"].add(node_id)
            current.append(node_id)
            cls = _CLASS_SUFFIX_RE.match(stmt, pos)
            if cls:
                pos = cls.end()
            while pos < n and stmt[pos].isspace():
                pos += 1
            if pos < n and stmt[pos] == "&":
                pos += 1
                continue
            groups.append(current)
            current = []
            expect_node = False
        else:
            m = _EDGE_TEXT_RE.match(stmt, pos)
            if m:
                report.label(m.group("t"), line)
                pos = m.end()
            else:
                m = _EDGE_RE.match(stmt, pos)
                if not m:
                    break
                pos = m.end()
                pipe = _EDGE_PIPE_RE.match(stmt, pos)
                if pipe:
                    report.label(pipe.group("t"), line)
                    pos = pipe.end()
            expect_node = True
    if current:
        groups.append(current)
    for left, right in zip(groups, groups[1:]):
        state["edges"] += len(left) * len(right)


def check_flowchart(items, report):
    state = {"nodes": set(), "edges": 0}
    subgraph_ids = set()
    stack = []
    subgraphs = 0
    for line, stripped in items:
        if common_rules(stripped, line, report):
            continue
        word = stripped.split(None, 1)[0]
        if word == "subgraph":
            subgraphs += 1
            stack.append(line)
            rest = stripped[len("subgraph"):].strip()
            m = _SUBGRAPH_TITLE_RE.match(rest)
            if m:
                subgraph_ids.add(m.group(1))
                title = m.group(2).strip()
            else:
                title = rest
                subgraph_ids.add(rest.strip('"'))
            report.label(title.strip('"'), line)
            continue
        if word == "end":
            if stack:
                stack.pop()
            else:
                report.issue("unbalanced-block", line, "end without a matching subgraph")
            continue
        if word in ("direction", "class", "accTitle", "accDescr"):
            continue
        for stmt in split_statements(stripped):
            parse_flow_statement(stmt, line, state, report)
    for line in stack:
        report.issue("unbalanced-block", line, "subgraph without a matching end")
    nodes = state["nodes"] - subgraph_ids
    return {"nodes": len(nodes), "edges": state["edges"], "subgraphs": subgraphs}


# --- sequence diagram -----------------------------------------------------------

def check_sequence(items, report):
    participants = {}
    messages = 0
    stack = []

    def add(pid):
        participants.setdefault(pid, True)

    for line, stripped in items:
        if common_rules(stripped, line, report):
            continue
        if stripped == "end":
            if stack:
                stack.pop()
            else:
                report.issue("unbalanced-block", line, "end without a matching block")
            continue
        if _SEQ_BLOCK_RE.match(stripped):
            stack.append((line, stripped.split(None, 1)[0]))
            continue
        if _SEQ_SKIP_RE.match(stripped):
            continue
        m = _SEQ_PARTICIPANT_RE.match(stripped)
        if m:
            add(m.group(1))
            if m.group(2):
                report.label(m.group(2), line)
            continue
        m = _SEQ_MESSAGE_RE.match(stripped)
        if m:
            add(m.group(1))
            add(m.group(3))
            messages += 1
            report.label(m.group(4), line)
    for line, keyword in stack:
        report.issue("unbalanced-block", line, f"{keyword} without a matching end")
    return {"participants": len(participants), "messages": messages}


# --- state diagram --------------------------------------------------------------

def check_state(items, report):
    states = set()
    transitions = 0
    braces = []
    in_note = False
    for line, stripped in items:
        if in_note:
            if stripped.lower().startswith("end note"):
                in_note = False
            continue
        if common_rules(stripped, line, report):
            continue
        if _STATE_NOTE_RE.match(stripped):
            if ":" not in stripped:
                in_note = True
            continue
        if stripped == "}":
            if braces:
                braces.pop()
            else:
                report.issue("unbalanced-block", line, "} without a matching state {")
            continue
        m = _STATE_TRANSITION_RE.match(stripped)
        if m:
            transitions += 1
            for sid in (m.group(1), m.group(2)):
                if sid != "[*]":
                    states.add(sid)
            if m.group(3):
                report.label(m.group(3), line)
            continue
        m = _STATE_DECL_RE.match(stripped)
        if m:
            states.add(m.group(2))
            if m.group(1):
                report.label(m.group(1), line)
            if m.group(3):
                braces.append(line)
            continue
        m = _STATE_DESC_RE.match(stripped)
        if m:
            states.add(m.group(1))
            report.label(m.group(2), line)
    for line in braces:
        report.issue("unbalanced-block", line, "state { without a matching }")
    return {"states": len(states), "transitions": transitions}


# --- driver ---------------------------------------------------------------------

def detect_type(items):
    """Return (kind, index of the header item) for the first statement."""
    if not items:
        return None, None, -1
    for idx, (line, stripped) in enumerate(items):
        if stripped.startswith("%%"):
            continue
        word = _HEADER_RE.match(stripped).group(1)
        base = word.split(";")[0]
        if base in ("flowchart", "graph"):
            return "flowchart", base, idx
        if base == "sequenceDiagram":
            return "sequenceDiagram", base, idx
        if base in ("stateDiagram", "stateDiagram-v2"):
            return "stateDiagram-v2", base, idx
        return None, base, idx
    return None, None, -1


def analyze(text, budgets):
    report = Report(budgets)
    items, front_lines = split_lines(text)
    for line in front_lines:
        report.issue("init-directive", line,
                     "config or theme in the front matter; overrides do not render everywhere")
    # Directives before the header are still checked.
    kind, first_word, idx = detect_type(items)
    for line, stripped in items[:max(idx, 0)]:
        common_rules(stripped, line, report)
    counts = {}
    if kind is None:
        message = ("no diagram found" if first_word is None
                   else f"unsupported diagram type {first_word!r}; "
                        "use flowchart, sequenceDiagram or stateDiagram-v2")
        line = items[idx][0] if idx >= 0 else 1
        report.issue("unsupported-type", line, message)
        type_name = first_word
    else:
        type_name = kind
        body = items[idx + 1:]
        if kind == "flowchart":
            counts = check_flowchart(body, report)
            if counts["nodes"] > budgets["max_nodes"]:
                report.issue("too-many-nodes", items[idx][0],
                             f"{counts['nodes']} nodes (budget {budgets['max_nodes']}); "
                             "split the diagram")
        elif kind == "sequenceDiagram":
            counts = check_sequence(body, report)
            if counts["participants"] > budgets["max_participants"]:
                report.issue("too-many-participants", items[idx][0],
                             f"{counts['participants']} participants "
                             f"(budget {budgets['max_participants']}); split the diagram")
            if counts["messages"] > budgets["max_messages"]:
                report.issue("too-many-messages", items[idx][0],
                             f"{counts['messages']} messages "
                             f"(budget {budgets['max_messages']}); split the diagram")
        else:
            counts = check_state(body, report)
            if counts["states"] > budgets["max_nodes"]:
                report.issue("too-many-nodes", items[idx][0],
                             f"{counts['states']} states (budget {budgets['max_nodes']}); "
                             "split the diagram")
    return {
        "type": type_name,
        "counts": counts,
        "budgets": dict(budgets),
        "labels": report.labels,
        "issues": sorted(report.issues, key=lambda i: i["line"]),
        "pass": not report.issues,
    }


def read_input(path):
    try:
        if path is None or path == "-":
            raw = sys.stdin.buffer.read()
        else:
            with open(path, "rb") as fh:
                raw = fh.read()
        return raw.decode("utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError(f"cannot read input {path or '-'}: {exc}")


def _non_negative(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an integer: {value!r}")
    if number < 0:
        raise argparse.ArgumentTypeError(f"must be 0 or more: {value!r}")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Check Mermaid source (budgets, labels, fragile syntax) and print JSON.")
    parser.add_argument("file", nargs="?", default=None,
                        help="Mermaid file, or - for stdin (default: stdin)")
    for key, default in DEFAULT_BUDGETS.items():
        parser.add_argument("--" + key.replace("_", "-"), dest=key, type=_non_negative,
                            default=default, metavar="N",
                            help=f"default {default}")
    args = parser.parse_args(argv)  # argparse exits with 2 on usage errors
    budgets = {key: getattr(args, key) for key in DEFAULT_BUDGETS}

    try:
        text = read_input(args.file)
    except InputError as exc:
        print(f"diagram_check: {exc}", file=sys.stderr)
        return EXIT_USAGE

    result = analyze(text, budgets)
    out = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    sys.stdout.buffer.write(out.encode("utf-8"))
    sys.stdout.buffer.flush()
    return EXIT_PASS if result["pass"] else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
