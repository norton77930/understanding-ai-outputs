#!/usr/bin/env python3
"""Run the diagram-explainer eval: four topics, with-skill vs baseline, plus an LLM judge.

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
```mermaid block of the reply, and measures it per arm: diagram_check.py pass
and issue count, node count (participants for sequence diagrams), label
overruns, render success (render_diagram.py through `uv run`) and diagram type
against the topic's expected type. Both scripts come from
<plugin dir>/skills/diagram-explainer/scripts/.
One judge call per topic (claude -p --tools "") sees the source and both
diagrams in randomized A/B order (reproducible from --seed) and returns which
explains faster plus an accuracy score 1-5 for each; the harness maps A/B back
to arms. Outputs and report.md/report.json go to
evals/diagram-explainer/runs/<timestamp>/ (git-ignored).

See evals/diagram-explainer/README.md. Python standard library only.
Exit code: 0 = complete, 2 = some call or measurement failed (see errors).
"""

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
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

JUDGE_INSTRUCTIONS = """You are comparing two diagrams (Mermaid or SVG source code) that were \
made to explain the same source text to a reader. Imagine each one rendered. \
A side can hold more than one diagram; judge the side as a whole.

Score each side for ACCURACY against the source, from 1 to 5:
5 = every fact shown is correct and nothing is invented; 4 = minor imprecision only; \
3 = one fact wrong, missing or invented that matters for the key points; \
2 = several facts wrong or missing; 1 = misleading.
Then say which side lets a reader understand the key points FASTER \
("A", "B" or "tie"). Consider type choice, size, labels and clarity, not looks.

Answer with ONE JSON object and nothing else, in this form:
{"faster": "A" | "B" | "tie", "accuracy_a": <1-5>, "accuracy_b": <1-5>, "reason": "<one or two sentences>"}
"""


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
    """Pick what to measure and judge. Returns (codes, from, format).

    Saved .mmd files first, then the first ```mermaid block of the reply, then
    saved .svg files (an agent that drew the diagram by hand; judged, but no
    Mermaid metrics). ([], None, None) when there is nothing.
    """
    if saved_mmd:
        return list(saved_mmd), "file", "mermaid"
    code = extract_mermaid(reply)
    if code:
        return [code], "reply", "mermaid"
    if saved_svg:
        return list(saved_svg), "file", "svg"
    return [], None, None


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

    codes: Mermaid sources; checks: diagram_check.py JSON per diagram (None if
    the checker failed); renders: True (rendered) / False (Mermaid error) /
    None (rendering not available) per diagram. Counts are summed over the
    diagrams; pass needs every diagram to pass; the first diagram decides the type.
    fmt "svg": hand-drawn SVG, so every Mermaid metric is None and the type is "svg".
    """
    if not codes:
        return {"diagrams": 0, "checker_pass": False, "issues": None, "nodes": None, "messages": None,
                "label_overruns": None, "render_ok": False, "type": None, "type_ok": False}
    if fmt == "svg":
        return {"diagrams": len(codes), "checker_pass": None, "issues": None, "nodes": None, "messages": None,
                "label_overruns": None, "render_ok": None, "type": "svg", "type_ok": False}
    known = [c for c in checks if c is not None]
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
            "type": kind, "type_ok": bool(type_matches(expected, kind))}


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


def parse_judge(text):
    """Parse and validate the judge reply. Returns a dict or None if invalid."""
    obj = extract_json_object(text or "")
    if obj is None:
        return None
    try:
        acc_a, acc_b = int(obj["accuracy_a"]), int(obj["accuracy_b"])
    except (KeyError, TypeError, ValueError):
        return None
    faster = obj.get("faster")
    if isinstance(faster, str):
        faster = faster.strip()
        faster = "tie" if faster.lower() == "tie" else faster.upper()
    if not (1 <= acc_a <= 5 and 1 <= acc_b <= 5) or faster not in ("A", "B", "tie"):
        return None
    return {"faster": faster, "accuracy_a": acc_a, "accuracy_b": acc_b, "reason": str(obj.get("reason", ""))}


def map_judge_to_arms(judge, order):
    """order = (arm shown as A, arm shown as B). Returns {"accuracy": {arm: int}, "faster", "reason"}."""
    arm_a, arm_b = order
    return {"accuracy": {arm_a: judge["accuracy_a"], arm_b: judge["accuracy_b"]},
            "faster": {"A": arm_a, "B": arm_b, "tie": "tie"}[judge["faster"]],
            "reason": judge.get("reason", "")}


def judge_order(seed, topic_id):
    """Randomized but reproducible A/B order for one topic."""
    rng = random.Random(f"{seed}:{topic_id}")
    arms = list(ARMS)
    rng.shuffle(arms)
    return tuple(arms)


def aggregate(results):
    """Totals per arm over topics, plus the judge's faster counts."""
    arms = {}
    for arm in ARMS:
        entries = [r["arms"][arm] for r in results]
        metrics = [e.get("metrics") for e in entries]
        scores = [e.get("accuracy") for e in entries]
        known = [s for s in scores if s is not None]
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
            "accuracy_scores": scores,
            "mean_accuracy": sum(known) / len(known) if known else None,
            "turns": sum((e.get("meta") or {}).get("num_turns") or 0 for e in entries),
            "cost_usd": round(sum((e.get("meta") or {}).get("cost_usd") or 0 for e in entries), 4),
            "seconds": round(sum(e.get("seconds") or 0 for e in entries), 1),
        }
    faster = {"with-skill": 0, "baseline": 0, "tie": 0, "missing": 0}
    for r in results:
        faster[r.get("faster") or "missing"] += 1
    return {"topics": len(results), "arms": arms, "faster": faster,
            "judge_cost_usd": round(sum((r.get("judge_meta") or {}).get("cost_usd") or 0 for r in results), 4)}


def _yn(value):
    return {True: "PASS", False: "FAIL", None: "n/a"}[value]


def _render_cell(value):
    return {True: "ok", False: "FAIL", None: "skipped"}[value]


def _num(value, fmt="{}"):
    return "n/a" if value is None else fmt.format(value)


def render_report(meta, results, agg):
    """Render report.md as a string."""
    out = [f"# diagram-explainer eval report ({meta['timestamp']})\n",
           f"- Model: {meta['model'] or 'claude CLI default'}",
           f"- claude version: {meta['claude_version']}",
           f"- Request: `{REQUEST}` + the topic's Source",
           f"- Plugin dir (with-skill arm, checker, renderer): `{meta['plugin_dir']}`",
           f"- Topics: {', '.join(r['id'] for r in results)}",
           f"- Judge order seed: {meta['seed']}",
           f"- Scratch root: `{meta['scratch_root']}`\n",
           "## Totals per arm\n",
           "| Arm | Checker pass | Issues | Label overruns | Rendered | Render skipped | Not Mermaid (SVG) | "
           "Type as expected | Nodes per topic | Accuracy (judge) | Mean accuracy | Turns | Cost | Time |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    n = agg["topics"]
    for arm in ARMS:
        a = agg["arms"][arm]
        out.append(f"| {arm} | {a['checker_pass']}/{n} | {a['issues']} | {a['label_overruns']} | "
                   f"{a['rendered']}/{n} | {a['render_unavailable']} | {a['not_mermaid']} | "
                   f"{a['type_ok']}/{n} | {a['nodes']} | "
                   f"{a['accuracy_scores']} | {_num(a['mean_accuracy'], '{:.2f}')} | {a['turns']} | "
                   f"${a['cost_usd']:.2f} | {a['seconds']:.0f} s |")
    f = agg["faster"]
    out.append(f"\nExplains faster (judge): with-skill {f['with-skill']}, baseline {f['baseline']}, "
               f"tie {f['tie']}, missing {f['missing']}. Judge cost ${agg['judge_cost_usd']:.2f}.\n")
    out.append("## Per topic\n")
    out.append("| Topic | Arm | Diagrams (from) | Type (expected) | Checker | Issues | Nodes | Messages | "
               "Label overruns | Render | Accuracy | Faster | Turns | Cost | Time |")
    out.append("|" + "---|" * 15)
    for r in results:
        for arm in ARMS:
            e = r["arms"][arm]
            m = e.get("metrics") or arm_metrics([], [], [], r["expected_type"])
            meta_ = e.get("meta") or {}
            faster = "" if not r.get("faster") else ("yes" if r["faster"] == arm else
                                                     "tie" if r["faster"] == "tie" else "no")
            out.append(f"| {r['id']} | {arm} | {m['diagrams']} ({e.get('mermaid_from') or 'none'}) | "
                       f"{m['type'] or 'n/a'} ({'ok' if m['type_ok'] else 'expected ' + r['expected_type']}) | "
                       f"{_yn(m['checker_pass'])} | {_num(m['issues'])} | {_num(m['nodes'])} | "
                       f"{_num(m['messages'])} | {_num(m['label_overruns'])} | "
                       f"{'n/a' if m['type'] == 'svg' else _render_cell(m['render_ok'])} | "
                       f"{_num(e.get('accuracy'))} | {faster} | {_num(meta_.get('num_turns'))} | "
                       f"{_num(meta_.get('cost_usd'), '${:.2f}')} | {_num(e.get('seconds'), '{:.0f} s')} |")
    out.append("\n## Details\n")
    for r in results:
        order = r.get("order") or ["?", "?"]
        out.append(f"### {r['id']} ({r['lang']}, expected `{r['expected_type']}`)\n")
        out.append(f"- Judge (A = {order[0]}, B = {order[1]}): {r.get('reason') or 'no judge result'}")
        for arm in ARMS:
            e = r["arms"][arm]
            if e.get("note"):
                out.append(f"- {arm}: {e['note']} ({', '.join(e.get('files') or [])})")
            for c in e.get("checks") or []:
                for issue in (c or {}).get("issues") or []:
                    out.append(f"- {arm} checker issue: {issue.get('rule')} (line {issue.get('line')}): "
                               f"{issue.get('message')}")
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


def build_judge_cmd(claude_exe, model):
    """Judge: same isolation, no plugin, no tools."""
    cmd = [claude_exe, "-p"] + ISOLATION_FLAGS + ["--tools", ""]
    if model:
        cmd += ["--model", model]
    return cmd


def judge_prompt(topic, codes_a, codes_b, fmt_a="mermaid", fmt_b="mermaid"):
    def side(codes):
        if len(codes) == 1:
            return codes[0].strip()
        return "\n\n".join(f"--- diagram {i} ---\n{c.strip()}" for i, c in enumerate(codes, 1))
    names = {"mermaid": "Mermaid source", "svg": "hand-written SVG source"}
    points = "\n".join(f"- {p}" for p in topic["points"])
    return (f"{JUDGE_INSTRUCTIONS}\n=== SOURCE ===\n{topic['source'].strip()}\n\n"
            f"=== KEY POINTS A READER SHOULD GET ===\n{points}\n\n"
            f"=== DIAGRAM A ({names[fmt_a]}) ===\n{side(codes_a)}\n\n"
            f"=== DIAGRAM B ({names[fmt_b]}) ===\n{side(codes_b)}\n")


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


def run_checker(plugin_dir, path):
    """diagram_check.py through its CLI. Returns the JSON, or None on a usage/input error."""
    script = Path(plugin_dir) / SKILL_SCRIPTS / "diagram_check.py"
    proc = subprocess.run([sys.executable, "-I", str(script), str(path)], capture_output=True, text=True,
                          encoding="utf-8")
    if proc.returncode not in (0, 1):
        return None
    return json.loads(proc.stdout)


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
             "metrics": None, "accuracy": None, "seconds": None}
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
    saved_svg = [] if saved_mmd else find_saved_diagrams(cwd, "*.svg")
    read = [p.read_text(encoding="utf-8", errors="replace").strip("\n") for p in saved_mmd or saved_svg]
    entry["codes"], entry["mermaid_from"], entry["format"] = choose_diagrams(
        read if saved_mmd else [], entry["reply"], read if saved_svg else [])
    if entry["mermaid_from"] == "file":
        entry["files"] = [str(p.relative_to(cwd)) for p in saved_mmd or saved_svg]
    if entry["format"] == "svg":
        entry["note"] = "no Mermaid: the agent drew SVG by hand; judged as SVG source, no Mermaid metrics"
    elif not entry["codes"]:
        errors.append(f"{arm}: no .mmd file, no ```mermaid block in the reply and no .svg file")
    renders = []
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
    return entry, errors


def process_topic(topic, args, claude_exe, run_dir, scratch_run):
    env = agent_env(scratch_run / "tmp")
    result = {"id": topic["id"], "lang": topic["lang"], "expected_type": topic["expected_type"],
              "arms": {}, "faster": None, "reason": "", "order": None, "judge_meta": None, "errors": []}
    for arm in ARMS:
        entry, errors = run_arm(topic, arm, args, claude_exe, run_dir, scratch_run, env)
        result["arms"][arm] = entry
        result["errors"] += errors
    order = judge_order(args.seed, topic["id"])
    result["order"] = list(order)
    codes = [result["arms"][arm]["codes"] for arm in order]
    if not all(codes):
        result["errors"].append("judge skipped: an arm has no diagram")
        return result
    judge_cwd = scratch_run / topic["id"] / "judge"
    judge_cwd.mkdir(parents=True, exist_ok=True)
    prompt = judge_prompt(topic, codes[0], codes[1], *(result["arms"][arm]["format"] for arm in order))
    for attempt in (1, 2):
        try:
            reply, result["judge_meta"] = run_claude(build_judge_cmd(claude_exe, args.model), prompt,
                                                     judge_cwd, args.timeout, env)
            (run_dir / topic["id"] / "judge.txt").write_text(reply + "\n", encoding="utf-8")
            judge = parse_judge(reply)
            if judge is None:
                raise RuntimeError(f"judge reply is not valid JSON: {reply[:200]!r}")
            mapped = map_judge_to_arms(judge, order)
            for arm in ARMS:
                result["arms"][arm]["accuracy"] = mapped["accuracy"][arm]
            result["faster"], result["reason"] = mapped["faster"], mapped["reason"]
            break
        except Exception as exc:
            result["errors"].append(f"judge attempt {attempt}: {exc}")
    return result


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
    parser.add_argument("--seed", default=None, help="seed for the judge A/B order (default: timestamp)")
    parser.add_argument("--timeout", type=int, default=900, help="seconds per claude call (default 900)")
    args = parser.parse_args(argv)
    args.plugin_dir = args.plugin_dir.resolve()
    if not (args.plugin_dir / SKILL_SCRIPTS / "diagram_check.py").is_file():
        raise SystemExit(f"no {SKILL_SCRIPTS / 'diagram_check.py'} under --plugin-dir {args.plugin_dir}")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    args.seed = args.seed or timestamp
    topics = load_topics(args.topics)
    claude_exe = shutil.which("claude") or "claude"
    scratch_run = SCRATCH_ROOT / timestamp

    if args.dry_run:
        print(f"env: {AGENT_ENV} + TMPDIR/TEMP/TMP={scratch_run / 'tmp'}")
        for t in topics:
            for arm in ARMS:
                print(f"[{t['id']}] {arm} cwd: {scratch_run / t['id'] / arm}")
                print(f"[{t['id']}] {arm}: {' '.join(build_cmd(claude_exe, arm, args.model, args.plugin_dir))}")
            order = judge_order(args.seed, t["id"])
            print(f"[{t['id']}] judge (A={order[0]}, B={order[1]}): "
                  f"{' '.join(build_judge_cmd(claude_exe, args.model))}")
            print(f"[{t['id']}] stdin: {build_prompt(t)!r}")
        return 0

    run_dir = RUNS_DIR / timestamp
    run_dir.mkdir(parents=True)
    (scratch_run / "tmp").mkdir(parents=True, exist_ok=True)
    print(f"Run folder: {run_dir}", flush=True)
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(process_topic, t, args, claude_exe, run_dir, scratch_run) for t in topics]
        results = []
        for future in futures:
            r = future.result()
            results.append(r)
            print(f"done {r['id']}: faster {r['faster']}"
                  + (f" (errors: {len(r['errors'])})" if r["errors"] else ""), flush=True)

    agg = aggregate(results)
    meta = {"timestamp": timestamp, "model": args.model, "seed": args.seed,
            "claude_version": claude_version(claude_exe), "plugin_dir": str(args.plugin_dir),
            "isolation_flags": ISOLATION_FLAGS, "allowed_tools": ALLOWED_TOOLS, "env": AGENT_ENV,
            "scratch_root": str(scratch_run)}
    (run_dir / "report.md").write_text(render_report(meta, results, agg), encoding="utf-8")
    (run_dir / "report.json").write_text(
        json.dumps({"meta": meta, "aggregate": agg, "topics": results}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(f"Report: {run_dir / 'report.md'}")
    errors = [(r["id"], e) for r in results for e in r["errors"]]
    for tid, e in errors:
        print(f"error [{tid}]: {e}", file=sys.stderr)
    return 2 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
