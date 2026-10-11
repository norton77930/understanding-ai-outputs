#!/usr/bin/env python3
"""Run the diagram-explainer eval: four topics, with-skill vs baseline, blind two-axis human rating.

Usage:
    python evals/diagram-explainer/run_eval.py [--topics 01,03] [--model MODEL]
                                               [--plugin-dir DIR] [--dry-run]
                                               [--workers N] [--seed S]
                                               [--timeout SECONDS]

For each topic in topics/ the harness asks an agent "Draw a diagram that
explains the following." plus the topic's Source, in two arms (same request):
    with-skill  claude -p ... --plugin-dir <plugin dir>   (default: repo root)
    baseline    claude -p ...   (no plugin)
Each arm runs in its own scratch folder outside the repo and outside ~/.claude.
The harness takes the Mermaid the agent saved (*.mmd files), else the first
```mermaid block of the reply, else the hand-written SVG the agent saved, and
measures it per arm: the checker pass and issue count, node count (participants
for sequence diagrams), label overruns, render success (render_diagram.py
through `uv run`) and diagram type against the topic's expected type (a Mermaid
header such as `flowchart TD`, or `svg`). Mermaid is checked with
diagram_check.py, hand-written SVG with svg_check.py (exit code, issue and
warning rules recorded; node, message and label metrics stay n/a for SVG).
All scripts come from <plugin dir>/skills/diagram-explainer/scripts/.
An .svg counts as hand-written only when no .mmd with the same stem sits in the
same folder: the Mermaid path also writes diagram.svg beside diagram.mmd, and
that is a render, not a drawing.
The with-skill checker gate is svg_check.py for SVG and diagram_check.py for
Mermaid; the baseline is reported, never gated.
Both arms are compared as PNG: render_diagram.py writes the PNG of a Mermaid
diagram; a hand-written SVG is rendered by `uv run render_diagram.py FILE.svg`,
else (uv, Playwright or the render failed) screenshotted with headless Chrome or
Edge (see svg_to_png); the method used is recorded.
There is no LLM judge. The harness writes runs/<timestamp>/review.html, a blind
review page: per topic the reader points, both images as 圖 A / 圖 B in a random
order (reproducible from --seed, recorded), two 1-5 axes (理解, 呈現) and the
better image. The key (which arm is A) is only in report.json (ab_key).
Outputs and report.md/report.json go to evals/diagram-explainer/runs/<timestamp>/
(git-ignored). The report gives cost and wall time per arm and in total.

See evals/diagram-explainer/README.md. Python standard library only.
Exit code: 0 = complete, 2 = some call or measurement failed (see errors).
"""

import argparse
import html
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
TOPICS_DIR = HERE / "topics"
RUNS_DIR = HERE / "runs"
# Scratch root outside the repo and outside ~/.claude (writes there count as sensitive).
SCRATCH_ROOT = Path(os.environ.get("DIAGRAM_EVAL_CWD") or "D:/diagram-explainer-eval")
SKILL_SCRIPTS = Path("skills") / "diagram-explainer" / "scripts"

REQUEST = "Draw a diagram that explains the following."
ARMS = ("with-skill", "baseline")

# Environment for the agent and the scripts: caches off the system drive, no
# Python download by uv, UTF-8 I/O, no __pycache__ in the skill folder.
# TMPDIR/TEMP/TMP are added per run (see agent_env).
AGENT_ENV = {
    "UV_CACHE_DIR": "D:/uv-cache",
    "UV_PYTHON_DOWNLOADS": "never",
    "PYTHONUTF8": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
}

ISOLATION_FLAGS = [
    "--setting-sources", "project,local",
    "--strict-mcp-config",
    "--no-session-persistence",
    "--output-format", "json",
]
ALLOWED_TOOLS = ["Bash", "Read", "Write", "Edit", "Skill", "Glob", "Grep"]
COPY_SUFFIXES = {".mmd", ".md", ".svg", ".png", ".json"}

# --------------------------------------------------------------------------
# Pure logic (unit-tested in test_run_eval.py)
# --------------------------------------------------------------------------

def parse_topic(topic_id, text):
    """Read language, expected type, Source and the reader points from a topic file."""
    lang = re.search(r"^- Language:\s*(\S+)", text, re.M)
    expected = re.search(r"^- Expected diagram type:\s*`([^`]+)`", text, re.M)
    source = _section(text, "Source")
    if not (lang and expected and source):
        raise ValueError(f"topic {topic_id}: missing Language, Expected diagram type or Source")
    points = [line[2:].strip() for line in (_section(text, "Reader should understand") or "").splitlines()
              if line.startswith("- ")]
    return {"id": topic_id, "lang": lang.group(1), "expected_type": expected.group(1).strip(),
            "source": source, "points": points}


def _section(text, title):
    match = re.search(rf"^## {re.escape(title)}\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return match.group(1).strip() if match else None


def build_prompt(topic):
    """The request plus the Source only (no hints, no reader points). Same in both arms."""
    return f"{REQUEST}\n\n{topic['source'].strip()}\n"


_FENCE_RE = re.compile(r"^[ \t]*```[ \t]*mermaid[ \t]*\n(.*?)\n[ \t]*```", re.M | re.S | re.I)


def extract_mermaid(text):
    """Return the code of the first ```mermaid block in text, or None."""
    if not text:
        return None
    match = _FENCE_RE.search(text.replace("\r\n", "\n"))
    return match.group(1).strip("\n") if match else None


def choose_diagrams(saved_mmd, reply, saved_svg):
    """Pick what to measure and review. Returns (codes, from, format).

    Saved .mmd files first, then the first ```mermaid block of the reply, then
    saved .svg files (an agent that drew the diagram by hand; converted to PNG
    for the review, but no Mermaid metrics). ([], None, None) when there is nothing.
    """
    if saved_mmd:
        return list(saved_mmd), "file", "mermaid"
    code = extract_mermaid(reply)
    if code:
        return [code], "reply", "mermaid"
    if saved_svg:
        return list(saved_svg), "file", "svg"
    return [], None, None


def handwritten_svgs(svgs, mmds):
    """Split saved .svg paths into (hand-written, renders of a Mermaid file).

    The skill's Mermaid path writes diagram.svg (and diagram.png) next to
    diagram.mmd. An SVG is such a render when a .mmd with the same stem sits in
    the same folder (suffixes compare case-insensitively); every other SVG was
    drawn by the agent. choose_diagrams still prefers saved .mmd files.
    """
    mermaid = {(Path(p).parent, Path(p).stem) for p in mmds if Path(p).suffix.lower() == ".mmd"}
    hand, rendered = [], []
    for svg in svgs:
        svg = Path(svg)
        (rendered if (svg.parent, svg.stem) in mermaid else hand).append(svg)
    return hand, rendered


def diagram_header(code):
    """Normalized diagram type from the header line.

    flowchart/graph -> "flowchart <dir>" (TB is TD; no direction is TD),
    stateDiagram/stateDiagram-v2 -> "stateDiagram-v2", else the first word.
    Skips blank lines, %% comments and front matter. None when there is no header.
    """
    lines = code.replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and lines[i].strip() == "---":
        i += 1
        while i < len(lines) and lines[i].strip() != "---":
            i += 1
        i += 1
    for line in lines[i:]:
        line = line.strip()
        if not line or line.startswith("%%"):
            continue
        words = re.split(r"[\s;]+", line)
        first = words[0]
        if first in ("flowchart", "graph"):
            direction = words[1].upper() if len(words) > 1 and words[1].upper() in (
                "TB", "TD", "BT", "LR", "RL") else "TD"
            return f"flowchart {'TD' if direction == 'TB' else direction}"
        if first in ("stateDiagram", "stateDiagram-v2"):
            return "stateDiagram-v2"
        return first
    return None


def type_matches(expected, actual):
    """True/False, or None when the actual type is unknown."""
    if actual is None:
        return None
    return diagram_header(expected) == actual


def arm_metrics(codes, checks, renders, expected, fmt="mermaid"):
    """Metrics for one arm from its diagrams.

    codes: diagram sources; checks: diagram_check.py JSON per Mermaid diagram,
    svg_check.py JSON per hand-written SVG (None if the checker failed);
    renders: True (rendered) / False (render error) / None (rendering not
    available) per diagram. Counts are summed over the diagrams; pass needs
    every diagram to pass; the first diagram decides the type.
    fmt "svg": hand-written SVG. Node, message and label-overrun metrics are
    None, the type is "svg" (type_ok only when the topic expects svg) and the
    checker is svg_check.py. Both formats also record the checker exit codes and
    the issue and warning rule codes.
    """
    if not codes:
        return {"diagrams": 0, "checker_pass": False, "issues": None, "nodes": None, "messages": None,
                "label_overruns": None, "render_ok": False, "type": None, "type_ok": False,
                "checker_exit": [], "issue_rules": [], "warning_rules": []}
    known = [c for c in checks if c is not None]
    rules = {
        "checker_exit": [c.get("exit_code") for c in known],
        "issue_rules": [i.get("rule") for c in known for i in c.get("issues") or []],
        "warning_rules": [w.get("rule") for c in known for w in c.get("warnings") or []],
    }
    if fmt == "svg":
        if not known:
            checker_pass = None
        elif len(known) < len(checks):
            checker_pass = False if any(not c["pass"] for c in known) else None
        else:
            checker_pass = all(c["pass"] for c in known)
        if False in renders:
            render_ok = False
        elif None in renders or not renders:
            render_ok = None
        else:
            render_ok = True
        return {"diagrams": len(codes), "checker_pass": checker_pass,
                "issues": len(rules["issue_rules"]) if known else None, "nodes": None, "messages": None,
                "label_overruns": None, "render_ok": render_ok, "type": "svg",
                "type_ok": diagram_header(expected) == "svg", **rules}
    nodes = messages = overruns = issues = 0
    has_messages = False
    for c in known:
        counts = c.get("counts") or {}
        nodes += counts.get("nodes", counts.get("states", counts.get("participants", 0)))
        if "messages" in counts:
            has_messages = True
            messages += counts["messages"]
        overruns += sum(1 for label in c.get("labels") or [] if label.get("over"))
        issues += len(c.get("issues") or [])
    if len(known) < len(checks):
        checker_pass = False if any(not c["pass"] for c in known) else None
    else:
        checker_pass = all(c["pass"] for c in known)
    if False in renders:
        render_ok = False
    elif None in renders or not renders:
        render_ok = None
    else:
        render_ok = True
    kind = diagram_header(codes[0])
    return {"diagrams": len(codes), "checker_pass": checker_pass, "issues": issues if known else None,
            "nodes": nodes if known else None, "messages": messages if has_messages else None,
            "label_overruns": overruns if known else None, "render_ok": render_ok,
            "type": kind, "type_ok": bool(type_matches(expected, kind)), **rules}


def extract_json_object(text):
    """Return the first JSON object found in text, or None."""
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text[match.start():])
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def ab_order(seed, topic_id):
    """Randomized but reproducible A/B order for one topic: (arm shown as A, arm shown as B)."""
    rng = random.Random(f"{seed}:{topic_id}")
    arms = list(ARMS)
    rng.shuffle(arms)
    return tuple(arms)


def ab_orders(topic_ids, seed):
    """{topic: [arm shown as A, arm shown as B]} for the review page; the key goes to report.json only."""
    return {tid: list(ab_order(seed, tid)) for tid in topic_ids}


def neutral_image_names(topic_id, label, count):
    """File names for the review page that reveal nothing about the arm: <topic>-A.png, <topic>-A-2.png, ..."""
    return [f"{topic_id}-{label}.png" if i == 1 else f"{topic_id}-{label}-{i}.png" for i in range(1, count + 1)]


def svg_dimensions(svg_text, default=(1400, 1100), max_side=4000):
    """Pixel size to screenshot an SVG at: width/height attributes, else the viewBox
    (width 1400 keeps the aspect), else default. Percent and other units are ignored."""
    head = re.search(r"<svg\b[^>]*>", svg_text, re.I | re.S)
    tag = head.group(0) if head else ""

    def number(attr):
        m = re.search(rf"\s{attr}\s*=\s*[\"']\s*([0-9.]+)\s*(?:px)?\s*[\"']", tag, re.I)
        return float(m.group(1)) if m else None

    width, height = number("width"), number("height")
    if not (width and height):
        box = re.search(r"viewBox\s*=\s*[\"']\s*[-0-9.]+[\s,]+[-0-9.]+[\s,]+([0-9.]+)[\s,]+([0-9.]+)", tag, re.I)
        if not box or float(box.group(1)) <= 0 or float(box.group(2)) <= 0:
            return default
        vw, vh = float(box.group(1)), float(box.group(2))
        if width:
            height = width * vh / vw
        elif height:
            width = height * vw / vh
        else:
            width, height = default[0], default[0] * vh / vw
    return min(max(int(round(width)), 100), max_side), min(max(int(round(height)), 100), max_side)


def browser_screenshot_cmd(browser, svg_path, png_path, size, profile_dir):
    """Headless Chrome/Edge command that screenshots an SVG file at device scale 2."""
    return [str(browser), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
            "--force-device-scale-factor=2", f"--user-data-dir={profile_dir}",
            f"--screenshot={png_path}", f"--window-size={size[0]},{size[1]}",
            Path(svg_path).resolve().as_uri()]


def svg_png(render, fallback, fallback_png, exists=lambda p: Path(p).is_file()):
    """PNG of a hand-written SVG: render_diagram.py first, headless Chrome/Edge second.

    render() -> (True/False/None, render_diagram.py JSON); fallback() -> error
    string or None (the browser screenshot, written to fallback_png). Returns
    {"png", "method", "fallback_reason", "error"}: method is "render_diagram.py",
    "browser" or None (both failed, error says why); fallback_reason is why
    render_diagram.py was not used (None when it was).
    """
    ok, data = render()
    data = data or {}
    png = data.get("png")
    if ok is True and png and exists(png):
        return {"png": png, "method": "render_diagram.py", "fallback_reason": None, "error": None}
    reason = (data.get("error") or data.get("hint") or "render_diagram.py wrote no PNG")[:300]
    error = fallback()
    if error:
        return {"png": None, "method": None, "fallback_reason": reason, "error": error}
    return {"png": str(fallback_png), "method": "browser", "fallback_reason": reason, "error": None}


CHECKER_SCRIPTS = {"mermaid": "diagram_check.py", "svg": "svg_check.py"}


def skill_gate(results):
    """The with-skill arm's checker-pass gate: per topic the checker of its format
    (svg_check.py for hand-written SVG, diagram_check.py for Mermaid), failed when
    that checker did not pass. The baseline is reported in the metrics, never gated.
    Returns {"checker": {topic: script or None}, "failed": [topic ids], "pass": bool}."""
    checker, failed = {}, []
    for r in results:
        entry = r["arms"]["with-skill"]
        checker[r["id"]] = CHECKER_SCRIPTS.get(entry.get("format"))
        if (entry.get("metrics") or {}).get("checker_pass") is False:
            failed.append(r["id"])
    return {"checker": checker, "failed": failed, "pass": not failed}


def aggregate(results):
    """Totals per arm over topics: checker, render, size, images, cost and agent time."""
    arms = {}
    for arm in ARMS:
        entries = [r["arms"][arm] for r in results]
        metrics = [e.get("metrics") for e in entries]
        arms[arm] = {
            "checker_pass": sum(1 for m in metrics if m and m["checker_pass"] is True),
            "rendered": sum(1 for m in metrics if m and m["render_ok"] is True),
            "render_unavailable": sum(1 for m in metrics if m and m["render_ok"] is None
                                      and m["type"] != "svg"),
            "not_mermaid": sum(1 for m in metrics if m and m["type"] == "svg"),
            "type_ok": sum(1 for m in metrics if m and m["type_ok"]),
            "issues": sum((m or {}).get("issues") or 0 for m in metrics),
            "label_overruns": sum((m or {}).get("label_overruns") or 0 for m in metrics),
            "nodes": [(m or {}).get("nodes") for m in metrics],
            "images": sum(1 for e in entries if e.get("images")),
            "turns": sum((e.get("meta") or {}).get("num_turns") or 0 for e in entries),
            "cost_usd": round(sum((e.get("meta") or {}).get("cost_usd") or 0 for e in entries), 4),
            "seconds": round(sum(e.get("seconds") or 0 for e in entries), 1),
        }
    return {"topics": len(results), "arms": arms,
            "cost_usd": round(sum(a["cost_usd"] for a in arms.values()), 4),
            "seconds": round(sum(a["seconds"] for a in arms.values()), 1)}


def _yn(value):
    return {True: "PASS", False: "FAIL", None: "n/a"}[value]


def _render_cell(value):
    return {True: "ok", False: "FAIL", None: "skipped"}[value]


def _num(value, fmt="{}"):
    return "n/a" if value is None else fmt.format(value)


def arm_summary_line(arm, a, topics):
    """One summary line per arm: the metrics, cost and agent time."""
    return (f"- {arm}: checker pass {a['checker_pass']}/{topics}, rendered {a['rendered']}/{topics}, "
            f"label overruns {a['label_overruns']}, images {a['images']}/{topics}, "
            f"cost ${a['cost_usd']:.2f}, {a['seconds']:.0f} s")


def gate_line(gate):
    """One report line for the with-skill checker gate, naming the checker used per topic."""
    used = ", ".join(f"{tid}: {script or 'n/a'}" for tid, script in gate["checker"].items())
    if gate["pass"]:
        return f"- With-skill checker gate: PASS ({used}); the baseline is reported, never gated"
    failed = ", ".join(f"{tid}: {gate['checker'][tid]}" for tid in gate["failed"])
    return f"- With-skill checker gate: FAIL ({failed}); the baseline is reported, never gated"


def checker_cell(entry, metrics):
    """Checker column: PASS/FAIL/n/a, with "(svg_check)" for a hand-written SVG."""
    cell = _yn(metrics["checker_pass"])
    return f"{cell} (svg_check)" if entry.get("format") == "svg" else cell


def render_cell(entry, metrics):
    """Render column. A hand-written SVG shows which tool made its PNG."""
    if metrics["type"] != "svg":
        return _render_cell(metrics["render_ok"])
    methods = sorted(set(entry.get("render_methods") or []))
    if methods:
        return "ok (" + ", ".join(methods) + ")"
    return "FAIL" if metrics["render_ok"] is False else "n/a"


def type_line(arm, expected, entry, metrics):
    """Details line: what the topic expected and what the arm drew."""
    got = metrics["type"] or "no diagram"
    kind = {"svg": " (hand-written SVG)", "mermaid": " (Mermaid)"}.get(entry.get("format"), "")
    verdict = "type ok" if metrics["type_ok"] else "type not as expected"
    return f"- {arm}: expected {expected}, got {got}{kind}: {verdict}"


def render_report(meta, results, agg):
    """Render report.md as a string. The A/B key is not in it (report.json only)."""
    n = agg["topics"]
    out = [f"# diagram-explainer eval report ({meta['timestamp']})\n",
           f"- Model: {meta['model'] or 'claude CLI default'}",
           f"- claude version: {meta['claude_version']}",
           f"- Request: `{REQUEST}` + the topic's Source",
           f"- Plugin dir (with-skill arm, checker, renderer): `{meta['plugin_dir']}`",
           f"- Topics: {', '.join(r['id'] for r in results)}",
           f"- Review page: `{meta.get('review')}` (A/B key in report.json only; seed {meta['seed']})",
           f"- Scratch root: `{meta['scratch_root']}`\n",
           "## Summary per arm\n"]
    out += [arm_summary_line(arm, agg["arms"][arm], n) for arm in ARMS]
    wall = meta.get("wall_seconds")
    out.append(f"- Total: cost ${agg['cost_usd']:.2f}, agent time {agg['seconds']:.0f} s"
               + (f", wall time {wall:.0f} s" if wall is not None else ""))
    out.append(gate_line(skill_gate(results)) + "\n")
    out += ["## Totals per arm\n",
            "| Arm | Checker pass | Issues | Label overruns | Rendered | Render skipped | Not Mermaid (SVG) | "
            "Type as expected | Nodes per topic | Images (PNG) | Turns | Cost | Agent time |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for arm in ARMS:
        a = agg["arms"][arm]
        out.append(f"| {arm} | {a['checker_pass']}/{n} | {a['issues']} | {a['label_overruns']} | "
                   f"{a['rendered']}/{n} | {a['render_unavailable']} | {a['not_mermaid']} | "
                   f"{a['type_ok']}/{n} | {a['nodes']} | {a['images']}/{n} | {a['turns']} | "
                   f"${a['cost_usd']:.2f} | {a['seconds']:.0f} s |")
    out.append("\n## Per topic\n")
    out.append("| Topic | Arm | Diagrams (from) | Type (expected) | Checker | Issues | Nodes | Messages | "
               "Label overruns | Render | Images | Turns | Cost | Time |")
    out.append("|" + "---|" * 14)
    for r in results:
        for arm in ARMS:
            e = r["arms"][arm]
            m = e.get("metrics") or arm_metrics([], [], [], r["expected_type"])
            meta_ = e.get("meta") or {}
            out.append(f"| {r['id']} | {arm} | {m['diagrams']} ({e.get('mermaid_from') or 'none'}) | "
                       f"{m['type'] or 'n/a'} ({'ok' if m['type_ok'] else 'expected ' + r['expected_type']}) | "
                       f"{checker_cell(e, m)} | {_num(m['issues'])} | {_num(m['nodes'])} | "
                       f"{_num(m['messages'])} | {_num(m['label_overruns'])} | "
                       f"{render_cell(e, m)} | "
                       f"{len(e.get('images') or [])} | {_num(meta_.get('num_turns'))} | "
                       f"{_num(meta_.get('cost_usd'), '${:.2f}')} | {_num(e.get('seconds'), '{:.0f} s')} |")
    out.append("\n## Details\n")
    for r in results:
        out.append(f"### {r['id']} ({r['lang']}, expected `{r['expected_type']}`)\n")
        for arm in ARMS:
            e = r["arms"][arm]
            m = e.get("metrics") or arm_metrics([], [], [], r["expected_type"])
            out.append(type_line(arm, r["expected_type"], e, m))
            if e.get("note"):
                out.append(f"- {arm}: {e['note']} ({', '.join(e.get('files') or [])})")
            for c in e.get("checks") or []:
                for issue in (c or {}).get("issues") or []:
                    out.append(f"- {arm} checker issue: {issue.get('rule')} (line {issue.get('line')}): "
                               f"{issue.get('message')}")
                for warning in (c or {}).get("warnings") or []:
                    out.append(f"- {arm} checker warning: {warning.get('rule')} (line {warning.get('line')}): "
                               f"{warning.get('message')}")
            for why in e.get("png_fallbacks") or []:
                out.append(f"- {arm} PNG fallback to the browser: {why}")
            for rd in e.get("renders") or []:
                if rd and rd.get("error"):
                    out.append(f"- {arm} render error: {rd['error'][:300]}")
                if rd and rd.get("hint"):
                    out.append(f"- {arm} render hint: {rd['hint'][:300]}")
        for err in r.get("errors") or []:
            out.append(f"- Error: {err}")
        for arm in ARMS:
            if r["arms"][arm].get("format") != "mermaid":
                continue
            codes = r["arms"][arm].get("codes") or []
            for i, code in enumerate(codes, 1):
                out.append(f"\n{arm} diagram {i}:\n\n```mermaid\n{code}\n```")
        out.append("")
    return "\n".join(out) + "\n"


REVIEW_CSS = """
body{font-family:system-ui,sans-serif;margin:1rem;background:#f4f4f4;color:#111}
section{background:#fff;border:1px solid #ccc;border-radius:6px;padding:1rem;margin-bottom:2rem}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:1rem;align-items:start}
.pair figure{margin:0}.pair img{width:100%;border:1px solid #999;margin-bottom:.5rem}
figcaption{font-weight:bold;margin:.5rem 0}
.missing{color:#a00}
table.rate{border-collapse:collapse;margin:.5rem 0}
table.rate th,table.rate td{border:1px solid #999;padding:.4rem .8rem;min-width:6rem;text-align:left}
"""

# Rating instructions, Traditional Chinese (Taiwan), English axis names in parentheses.
REVIEW_INTRO = (
    "<p>每個主題請比較圖 A 和圖 B。先看「讀者應該理解」的重點，再看圖。"
    "A/B 的順序在每個主題都是隨機的，對照表只在 report.json。點圖可以開啟原尺寸。</p>"
    "<p>每張圖各打兩個分數，各為 1 到 5 分（1 = 很差，5 = 很好）：</p>"
    "<ul><li><strong>理解（Understanding）</strong>：看完這張圖後，"
    "你對該主題「讀者應該理解」的各個重點理解了多少。</li>"
    "<li><strong>呈現（Presentation）</strong>：版面、配色、文字大小與整體視覺是否清楚好讀。</li></ul>"
    "<p>最後選出該主題中較好的圖：A、B 或平手。"
    "把分數填進 RESULTS.md 的表格，之後再用 report.json 的 ab_key 對照 A、B 各是哪一組。</p>"
)


def render_review(entries, timestamp):
    """Blind review page, in Traditional Chinese (Taiwan). entries: [{"id", "lang", "points",
    "images": {"A"|"B": [relative png path, ...]}}]. Only the labels 圖 A and 圖 B appear, never
    arm names. Per topic: the points, both images (each linked to the full-size file), a two-axis
    rating table (理解, 呈現) for A and B and the better-image line."""
    esc = html.escape
    out = ["<!doctype html>", '<html lang="zh-TW"><head><meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width, initial-scale=1">',
           f"<title>diagram-explainer 盲測評分 {esc(timestamp)}</title><style>{REVIEW_CSS}</style></head><body>",
           f"<h1>diagram-explainer 盲測評分（{esc(timestamp)}）</h1>", REVIEW_INTRO]
    for e in entries:
        out.append(f"<section><h2>{esc(e['id'])}（{esc(e['lang'])}）</h2>")
        if e["points"]:
            out.append("<p>讀者應該理解（Reader should understand）：</p><ul>"
                       + "".join(f"<li>{esc(p)}</li>" for p in e["points"]) + "</ul>")
        out.append('<div class="pair">')
        for label in ("A", "B"):
            images = (e.get("images") or {}).get(label) or []
            body = "".join(
                f'<a href="{esc(img)}" target="_blank"><img src="{esc(img)}" alt="圖 {label}"></a>'
                f'<div><a href="{esc(img)}" target="_blank">開啟原尺寸（圖 {label}'
                + (f"，第 {i} 張" if len(images) > 1 else "") + "）</a></div>"
                for i, img in enumerate(images, 1)) or '<p class="missing">沒有圖片</p>'
            out.append(f"<figure><figcaption>圖 {label}</figcaption>{body}</figure>")
        out.append("</div>")
        out.append('<table class="rate"><tr><th></th><th>理解（Understanding），1-5</th>'
                   "<th>呈現（Presentation），1-5</th></tr>"
                   + "".join(f"<tr><th>圖 {label}</th><td></td><td></td></tr>" for label in ("A", "B"))
                   + "</table>")
        out.append("<p>較好（A / B / 平手）：______</p>")
        out.append("</section>")
    out.append("</body></html>")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# Running claude, the checker and the renderer
# --------------------------------------------------------------------------

def build_cmd(claude_exe, arm, model, plugin_dir):
    cmd = [claude_exe, "-p"] + ISOLATION_FLAGS + ["--allowedTools", ",".join(ALLOWED_TOOLS)]
    if arm == "with-skill":
        cmd += ["--plugin-dir", str(plugin_dir)]
    if model:
        cmd += ["--model", model]
    return cmd


def agent_env(tmp_dir):
    env = dict(os.environ)
    env.update(AGENT_ENV)
    env.update({"TMPDIR": str(tmp_dir), "TEMP": str(tmp_dir), "TMP": str(tmp_dir)})
    return env


class ClaudeError(RuntimeError):
    """claude returned JSON but reported an error; keeps the reply and turns/cost."""

    def __init__(self, message, reply, meta):
        super().__init__(message)
        self.reply, self.meta = reply, meta


def run_claude(cmd, prompt, cwd, timeout, env):
    """Run claude with the prompt on stdin. Returns (reply, meta)."""
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                              cwd=cwd, timeout=timeout, env=env)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"claude timed out after {timeout} s") from exc
    try:
        data = json.loads(proc.stdout)
    except ValueError as exc:
        raise RuntimeError(f"claude exited {proc.returncode}, output is not JSON: "
                           f"{proc.stdout[:300]!r} {proc.stderr.strip()[:300]}") from exc
    meta = {"num_turns": data.get("num_turns"), "cost_usd": data.get("total_cost_usd"),
            "models": list((data.get("modelUsage") or {}).keys()), "subtype": data.get("subtype")}
    reply = (data.get("result") or "").strip()
    if proc.returncode != 0 or data.get("is_error"):
        raise ClaudeError(f"claude error (exit {proc.returncode}, {data.get('subtype')}): {reply[:300]}",
                          reply, meta)
    return reply, meta


def run_checker(plugin_dir, path, script_name="diagram_check.py", env=None):
    """diagram_check.py (Mermaid) or svg_check.py (hand-written SVG) through its CLI.

    Returns the JSON plus "exit_code", or None on a usage/input error (exit 2)."""
    script = Path(plugin_dir) / SKILL_SCRIPTS / script_name
    proc = subprocess.run([sys.executable, "-I", str(script), str(path)], capture_output=True, text=True,
                          encoding="utf-8", env=env)
    if proc.returncode not in (0, 1):
        return None
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        return None
    data["exit_code"] = proc.returncode
    return data


def run_render(plugin_dir, path, out_dir, env):
    """render_diagram.py through `uv run`. Returns (True/False/None, JSON or note)."""
    uv = shutil.which("uv")
    if not uv:
        return None, {"hint": "uv not found on PATH; render skipped"}
    script = Path(plugin_dir) / SKILL_SCRIPTS / "render_diagram.py"
    try:
        proc = subprocess.run([uv, "run", "--quiet", str(script), str(path), "--out", str(out_dir)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=300, env=env)
    except subprocess.TimeoutExpired:
        return None, {"hint": "render_diagram.py did not finish in 300 s"}
    data = extract_json_object(proc.stdout) or {"hint": f"no JSON output: {proc.stderr.strip()[:300]}"}
    return {0: True, 1: False}.get(proc.returncode), data


def find_browser():
    """Chrome or Edge for the SVG screenshot: DIAGRAM_EVAL_BROWSER, then PATH, then the usual install paths."""
    override = os.environ.get("DIAGRAM_EVAL_BROWSER")
    if override and Path(override).is_file():
        return override
    for name in ("chrome", "google-chrome", "msedge", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    roots = [os.environ.get(k) for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
    for root in filter(None, roots):
        for rel in ("Google/Chrome/Application/chrome.exe", "Microsoft/Edge/Application/msedge.exe"):
            if (Path(root) / rel).is_file():
                return str(Path(root) / rel)
    for path in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                 "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"):
        if Path(path).is_file():
            return path
    return None


def svg_to_png(svg_path, png_path, tmp_dir):
    """Screenshot a hand-written SVG to PNG with headless Chrome/Edge. Returns an error string or None."""
    browser = find_browser()
    if not browser:
        return "no Chrome or Edge found (set DIAGRAM_EVAL_BROWSER); SVG not converted to PNG"
    size = svg_dimensions(Path(svg_path).read_text(encoding="utf-8", errors="replace"))
    Path(tmp_dir).mkdir(parents=True, exist_ok=True)
    profile = tempfile.mkdtemp(prefix="svg-profile-", dir=tmp_dir)
    Path(png_path).unlink(missing_ok=True)
    try:
        subprocess.run(browser_screenshot_cmd(browser, svg_path, png_path, size, profile),
                       capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return f"browser did not finish within 120 s for {Path(svg_path).name}"
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    if not (Path(png_path).is_file() and Path(png_path).stat().st_size > 0):
        return f"browser wrote no PNG for {Path(svg_path).name}"
    return None


def find_saved_diagrams(cwd, pattern="*.mmd"):
    """Files the agent saved under cwd (default *.mmd), in path order."""
    return sorted(p for p in Path(cwd).rglob(pattern) if p.is_file() and ".venv" not in p.parts)


def copy_agent_files(cwd, dest):
    for path in Path(cwd).rglob("*"):
        if path.is_file() and path.suffix.lower() in COPY_SUFFIXES and ".venv" not in path.parts:
            target = dest / path.relative_to(cwd)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def run_arm(topic, arm, args, claude_exe, run_dir, scratch_run, env):
    cwd = scratch_run / topic["id"] / arm
    cwd.mkdir(parents=True, exist_ok=True)
    out = run_dir / topic["id"] / arm
    out.mkdir(parents=True, exist_ok=True)
    entry = {"reply": None, "meta": None, "mermaid_from": None, "codes": [], "checks": [], "renders": [],
             "metrics": None, "images": [], "seconds": None}
    errors = []
    started = time.monotonic()
    try:
        entry["reply"], entry["meta"] = run_claude(build_cmd(claude_exe, arm, args.model, args.plugin_dir),
                                                   build_prompt(topic), cwd, args.timeout, env)
    except ClaudeError as exc:
        entry["reply"], entry["meta"] = exc.reply or None, exc.meta
        errors.append(f"{arm}: {exc}")
    except Exception as exc:  # keep going; measure whatever the agent left behind
        errors.append(f"{arm}: {exc}")
    entry["seconds"] = round(time.monotonic() - started, 1)
    if entry["reply"]:
        (out / "reply.md").write_text(entry["reply"] + "\n", encoding="utf-8")
    copy_agent_files(cwd, out / "agent-files")

    saved_mmd = find_saved_diagrams(cwd)
    # An .svg beside an .mmd with the same stem is the skill's Mermaid render, not a drawing.
    saved_svg, mermaid_renders = handwritten_svgs(find_saved_diagrams(cwd, "*.svg"), saved_mmd)
    if saved_mmd and mermaid_renders:
        entry["mermaid_renders_ignored"] = [str(p.relative_to(cwd)) for p in mermaid_renders]
    read_mmd = [p.read_text(encoding="utf-8", errors="replace").strip("\n") for p in saved_mmd]
    read_svg = [p.read_text(encoding="utf-8", errors="replace").strip("\n") for p in saved_svg]
    entry["codes"], entry["mermaid_from"], entry["format"] = choose_diagrams(read_mmd, entry["reply"], read_svg)
    entry["checker"] = CHECKER_SCRIPTS.get(entry["format"])
    if entry["mermaid_from"] == "file":
        entry["files"] = [str(p.relative_to(cwd)) for p in (saved_mmd if entry["format"] == "mermaid" else saved_svg)]
    if entry["format"] == "svg":
        entry["note"] = ("no Mermaid: the agent drew SVG by hand; checked with svg_check.py, "
                         "converted to PNG for the review, no Mermaid metrics")
    elif not entry["codes"]:
        errors.append(f"{arm}: no .mmd file, no ```mermaid block in the reply and no hand-written .svg file")
    renders = []
    entry["render_methods"] = []
    entry["png_fallbacks"] = []
    if entry["format"] == "svg":
        for i, rel in enumerate(entry.get("files") or [], 1):
            svg = out / "agent-files" / rel
            check = run_checker(args.plugin_dir, svg, "svg_check.py", env)
            if check is None:
                errors.append(f"{arm}: svg_check.py failed on {rel}")
            entry["checks"].append(check)
            png = svg.with_name(svg.stem + "-render.png")
            got = svg_png(lambda: run_render(args.plugin_dir, svg, out / "render" / f"svg-{i}", env),
                          lambda: svg_to_png(svg, png, scratch_run / "tmp"), png)
            entry["renders"].append(got)
            if got["method"]:
                renders.append(True)
                entry["render_methods"].append(got["method"])
                entry["images"].append(got["png"])
                if got["fallback_reason"]:
                    entry["png_fallbacks"].append(f"{rel}: {got['fallback_reason']}")
            else:
                renders.append(False)
                errors.append(f"{arm}: {got['error']}")
    for i, code in enumerate(entry["codes"] if entry["format"] == "mermaid" else [], 1):
        path = out / f"eval-diagram-{i}.mmd"
        path.write_text(code + "\n", encoding="utf-8")
        check = run_checker(args.plugin_dir, path)
        if check is None:
            errors.append(f"{arm}: diagram_check.py failed on diagram {i}")
        entry["checks"].append(check)
        ok, data = run_render(args.plugin_dir, path, out / "render", env)
        renders.append(ok)
        entry["renders"].append(data)
    entry["metrics"] = arm_metrics(entry["codes"], entry["checks"], renders, topic["expected_type"],
                                   entry["format"] or "mermaid")
    if entry["format"] != "svg":
        entry["images"] = [rd["png"] for rd in entry["renders"]
                           if rd and rd.get("png") and Path(rd["png"]).is_file()]
    return entry, errors


def process_topic(topic, args, claude_exe, run_dir, scratch_run):
    env = agent_env(scratch_run / "tmp")
    result = {"id": topic["id"], "lang": topic["lang"], "expected_type": topic["expected_type"],
              "points": topic["points"], "arms": {}, "errors": []}
    for arm in ARMS:
        entry, errors = run_arm(topic, arm, args, claude_exe, run_dir, scratch_run, env)
        result["arms"][arm] = entry
        result["errors"] += errors
    return result


def build_review(results, orders, run_dir, timestamp):
    """Copy the PNGs under neutral names (<topic>-A.png) into review/ and write review.html."""
    review = run_dir / "review"
    review.mkdir(exist_ok=True)
    entries = []
    for r in results:
        e = {"id": r["id"], "lang": r["lang"], "points": r["points"], "images": {}}
        for label, arm in zip(("A", "B"), orders[r["id"]]):
            sources = r["arms"][arm].get("images") or []
            names = neutral_image_names(r["id"], label, len(sources))
            for src, name in zip(sources, names):
                shutil.copy2(src, review / name)
            e["images"][label] = [f"review/{name}" for name in names]
        entries.append(e)
    path = run_dir / "review.html"
    path.write_text(render_review(entries, timestamp), encoding="utf-8")
    return path


def load_topics(selected):
    topics = [parse_topic(p.stem, p.read_text(encoding="utf-8")) for p in sorted(TOPICS_DIR.glob("0*.md"))]
    if selected:
        wanted = [s.strip() for s in selected.split(",") if s.strip()]
        topics = [t for t in topics if any(t["id"] == w or t["id"].startswith(w) for w in wanted)]
        if not topics:
            raise SystemExit(f"no topic matches --topics {selected!r}")
    return topics


def claude_version(claude_exe):
    try:
        proc = subprocess.run([claude_exe, "--version"], capture_output=True, text=True, timeout=60)
        return proc.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the diagram-explainer eval.")
    parser.add_argument("--topics", help="comma-separated topic ids or number prefixes, e.g. 01,03")
    parser.add_argument("--model", help="model alias or name passed to claude --model (default: CLI default)")
    parser.add_argument("--plugin-dir", type=Path, default=REPO_ROOT,
                        help="plugin root for the with-skill arm and the scripts (default: repo root)")
    parser.add_argument("--dry-run", action="store_true", help="print the commands and exit; call nothing")
    parser.add_argument("--workers", type=int, default=4, help="parallel topics (default 4)")
    parser.add_argument("--seed", default=None, help="seed for the review A/B order (default: timestamp)")
    parser.add_argument("--timeout", type=int, default=900, help="seconds per claude call (default 900)")
    args = parser.parse_args(argv)
    args.plugin_dir = args.plugin_dir.resolve()
    for script in ("diagram_check.py", "svg_check.py"):
        if not (args.plugin_dir / SKILL_SCRIPTS / script).is_file():
            raise SystemExit(f"no {SKILL_SCRIPTS / script} under --plugin-dir {args.plugin_dir}")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    args.seed = args.seed or timestamp
    topics = load_topics(args.topics)
    claude_exe = shutil.which("claude") or "claude"
    scratch_run = SCRATCH_ROOT / timestamp

    if args.dry_run:
        print(f"env: {AGENT_ENV} + TMPDIR/TEMP/TMP={scratch_run / 'tmp'}")
        print("hand-written SVG (an .svg with no .mmd of the same stem beside it) -> "
              f"{SKILL_SCRIPTS / 'svg_check.py'}; Mermaid -> {SKILL_SCRIPTS / 'diagram_check.py'}")
        print("hand-written SVG -> PNG with: uv run render_diagram.py FILE.svg, "
              f"else headless {find_browser() or 'Chrome/Edge (none found; set DIAGRAM_EVAL_BROWSER)'}")
        for t in topics:
            print(f"[{t['id']}] expected diagram type: {t['expected_type']}")
            for arm in ARMS:
                print(f"[{t['id']}] {arm} cwd: {scratch_run / t['id'] / arm}")
                print(f"[{t['id']}] {arm}: {' '.join(build_cmd(claude_exe, arm, args.model, args.plugin_dir))}")
            print(f"[{t['id']}] stdin: {build_prompt(t)!r}")
        return 0

    run_dir = RUNS_DIR / timestamp
    run_dir.mkdir(parents=True)
    (scratch_run / "tmp").mkdir(parents=True, exist_ok=True)
    print(f"Run folder: {run_dir}", flush=True)
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(process_topic, t, args, claude_exe, run_dir, scratch_run) for t in topics]
        results = []
        for future in futures:
            r = future.result()
            results.append(r)
            print(f"done {r['id']}" + (f" (errors: {len(r['errors'])})" if r["errors"] else ""), flush=True)

    orders = ab_orders([r["id"] for r in results], args.seed)
    review = build_review(results, orders, run_dir, timestamp)
    agg = aggregate(results)
    meta = {"timestamp": timestamp, "model": args.model, "seed": args.seed,
            "claude_version": claude_version(claude_exe), "plugin_dir": str(args.plugin_dir),
            "isolation_flags": ISOLATION_FLAGS, "allowed_tools": ALLOWED_TOOLS, "env": AGENT_ENV,
            "scratch_root": str(scratch_run), "review": str(review),
            "wall_seconds": round(time.monotonic() - started, 1)}
    (run_dir / "report.md").write_text(render_report(meta, results, agg), encoding="utf-8")
    (run_dir / "report.json").write_text(
        json.dumps({"meta": meta, "aggregate": agg, "skill_gate": skill_gate(results),
                    "ab_key": {tid: {"A": o[0], "B": o[1]} for tid, o in orders.items()},
                    "topics": results}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(f"Report: {run_dir / 'report.md'}")
    print(f"Review: {review}")
    errors = [(r["id"], e) for r in results for e in r["errors"]]
    for tid, e in errors:
        print(f"error [{tid}]: {e}", file=sys.stderr)
    return 2 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
