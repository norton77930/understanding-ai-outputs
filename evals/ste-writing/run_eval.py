#!/usr/bin/env python3
"""Run the ste-writing eval: eight passages, with-skill vs baseline, plus an LLM judge.

Usage:
    python evals/ste-writing/run_eval.py [--passages 01,03,05] [--model MODEL]
                                         [--dry-run] [--workers N] [--seed S]
                                         [--timeout SECONDS]
                                         [--strictness relaxed|strict]
    python evals/ste-writing/run_eval.py --set explain [--topics 01,03] [--model MODEL]
                                         [--dry-run] [--workers N] [--seed S]
                                         [--timeout SECONDS]

For each passage the harness asks an agent "Rewrite the following text in STE."
(strict: "... in strict STE.") in two arms (same request in both):
    with-skill  claude -p ... --plugin-dir <repo root>
    baseline    claude -p ...   (no plugin)
Each output is measured with skills/ste-writing/scripts/ste_check.py (relaxed or
strict; strict also loads the replacement list, which gives the replacement hits).
One judge call per passage sees the original and both outputs in randomized A/B
order and returns meaning scores (1-5) and the more readable output.
Raw outputs and the report go to evals/ste-writing/runs/<timestamp>/.

--set explain runs the explain topics in explain/ instead: both arms get the
topic's request (for example "用 STE 解釋：..."), the answers are measured where
the checker applies, and runs/<timestamp>/review.html shows both answers per
topic in a random A/B order for a blind human rating. No judge. The A/B key is
only in report.json. Exit code: 0 = all answers present, 2 = a call failed.

See evals/ste-writing/README.md for the isolation flags and the thresholds.
Python standard library only. Exit code: 0 = PASS, 1 = FAIL, 2 = incomplete/error.
"""

import argparse
import html
import json
import random
import os
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
PASSAGES_DIR = HERE / "passages"
EXPLAIN_DIR = HERE / "explain"
RUNS_DIR = HERE / "runs"
CHECKER = REPO_ROOT / "skills" / "ste-writing" / "scripts" / "ste_check.py"
REPLACEMENTS = REPO_ROOT / "skills" / "ste-writing" / "references" / "replacements.md"
# Neutral cwd outside the repo, so this repo's CLAUDE.md and .claude/ settings do not apply.
SCRATCH_CWD = Path(os.environ.get("STE_EVAL_CWD") or Path(tempfile.gettempdir()) / "ste-writing-eval")

REQUESTS = {"relaxed": "Rewrite the following text in STE.",
            "strict": "Rewrite the following text in strict STE."}
STRICTNESS = tuple(REQUESTS)
ARMS = ("with-skill", "baseline")
SETS = ("rewrite", "explain")

# Relaxed acceptance thresholds (issue #3). Strict adds zero replacement-list
# hits in the with-skill arm.
MAX_REPLACEMENT_HITS = 0
MIN_WITHIN_LIMIT_RATIO = 0.90
MAX_PASSIVE_PROGRESSIVE_RATIO = 0.05
MIN_MEANING = 4

# Isolation flags (see README): drop user-level settings and memory so the
# user's global instructions (reply language, etc.) cannot leak into outputs.
ISOLATION_FLAGS = [
    "--setting-sources", "project,local",
    "--strict-mcp-config",
    "--no-session-persistence",
    "--output-format", "json",
]

JUDGE_INSTRUCTIONS = """You are comparing two rewrites of the same source text. \
Both rewrites were asked to put the text in Simplified Technical English style \
(short sentences, active voice, one instruction per sentence, one term per concept).

Score each rewrite for MEANING PRESERVED against the original, from 1 to 5:
5 = every fact kept, nothing added; 4 = minor loss or wording drift only; \
3 = one fact lost, changed or added; 2 = several facts lost or changed; 1 = the meaning is lost.
Code, identifiers and error strings should be kept exactly.
Then say which rewrite is MORE READABLE for a reader who must check or learn from it \
("A", "B" or "tie").

Answer with ONE JSON object and nothing else, in this form:
{"meaning_a": <1-5>, "meaning_b": <1-5>, "more_readable": "A" | "B" | "tie", "reason": "<one or two sentences>"}
"""


# --------------------------------------------------------------------------
# Pure logic (unit-tested in test_run_eval.py)
# --------------------------------------------------------------------------

def request_for(strictness):
    """The rewrite request for a strictness. Both arms get the same one."""
    return REQUESTS[strictness]


def passage_language(passage_id):
    """Return "zh" for the Chinese passages (named ...-zh-...), else "en"."""
    return "zh" if "-zh-" in passage_id else "en"


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
        meaning_a = int(obj["meaning_a"])
        meaning_b = int(obj["meaning_b"])
    except (KeyError, TypeError, ValueError):
        return None
    readable = obj.get("more_readable")
    if isinstance(readable, str):
        readable = readable.strip()
        readable = readable.lower() if readable.lower() == "tie" else readable.upper()
    if not (1 <= meaning_a <= 5 and 1 <= meaning_b <= 5):
        return None
    if readable not in ("A", "B", "tie"):
        return None
    return {"meaning_a": meaning_a, "meaning_b": meaning_b,
            "more_readable": readable, "reason": str(obj.get("reason", ""))}


def map_judge_to_arms(judge, order):
    """Map A/B judge answers back to arms.

    order = (arm_shown_as_A, arm_shown_as_B). Returns
    {"meaning": {arm: int}, "readable": arm or "tie", "reason": str}.
    """
    arm_a, arm_b = order
    readable = {"A": arm_a, "B": arm_b, "tie": "tie"}[judge["more_readable"]]
    return {"meaning": {arm_a: judge["meaning_a"], arm_b: judge["meaning_b"]},
            "readable": readable, "reason": judge.get("reason", "")}


def aggregate(results):
    """Aggregate per-passage results into per-arm figures.

    results: list of {"id", "lang", "arms": {arm: {"totals": dict|None,
    "meaning": int|None}}, "readable": arm|"tie"|None}.
    Checker figures and the gates use English passages only; Chinese passages
    are manual review. Returns {arm: {...}} plus a "readability" entry.
    """
    english = [r for r in results if r["lang"] == "en"]
    agg = {}
    for arm in ARMS:
        sentences = over = passive = progressive = hits = 0
        meanings = []
        missing_metrics = 0
        for r in english:
            totals = r["arms"][arm].get("totals")
            if totals:
                sentences += totals["sentences"]
                over += totals["over_limit"]
                passive += totals["passive"]
                progressive += totals["progressive"]
                hits += totals.get("replacement_hits", 0)
            else:
                missing_metrics += 1
            meanings.append(r["arms"][arm].get("meaning"))
        agg[arm] = {
            "sentences": sentences,
            "over_limit": over,
            "passive": passive,
            "progressive": progressive,
            "replacement_hits": hits,
            "over_limit_ratio": over / sentences if sentences else None,
            "passive_progressive_ratio": (passive + progressive) / sentences if sentences else None,
            "meaning_scores": meanings,
            "min_meaning": min(meanings) if meanings and None not in meanings else None,
            "missing_metrics": missing_metrics,
        }
    wins = {"with-skill": 0, "baseline": 0, "tie": 0, "missing": 0}
    for r in english:
        wins[r.get("readable") or "missing"] += 1
    agg["readability"] = wins
    return agg


def evaluate(agg, strictness="relaxed"):
    """Check the with-skill arm against the thresholds for the strictness.

    Strict = the relaxed thresholds plus zero replacement-list hits in the
    with-skill arm (baseline hits are reported, not gated).

    Returns {"checks": {name: {"value", "threshold", "pass"}}, "verdict": ...}.
    A check's "pass" is True, False, or None when its data is missing.
    Verdict: FAIL if any check is False, else INCOMPLETE if any is None, else PASS.
    """
    arm = agg["with-skill"]
    wins = agg["readability"]
    complete = arm["missing_metrics"] == 0
    over = arm["over_limit_ratio"]
    pp = arm["passive_progressive_ratio"]
    within = None if over is None or not complete else 1 - over
    pp = pp if complete else None
    known = [m for m in arm["meaning_scores"] if m is not None]
    if known and min(known) < MIN_MEANING:
        meaning_pass = False
    elif not known or len(known) < len(arm["meaning_scores"]):
        meaning_pass = None
    else:
        meaning_pass = True
    readability_pass = None if wins["missing"] else wins["with-skill"] > wins["baseline"]
    checks = {
        "within_limit": {
            "value": within, "threshold": f">= {MIN_WITHIN_LIMIT_RATIO:.0%}",
            "pass": None if within is None else within >= MIN_WITHIN_LIMIT_RATIO - 1e-9},
        "passive_progressive": {
            "value": pp, "threshold": f"<= {MAX_PASSIVE_PROGRESSIVE_RATIO:.0%}",
            "pass": None if pp is None else pp <= MAX_PASSIVE_PROGRESSIVE_RATIO + 1e-9},
        "meaning": {
            "value": min(known) if known else None, "threshold": f">= {MIN_MEANING} on every passage",
            "pass": meaning_pass},
        "readability": {
            "value": f"with-skill {wins['with-skill']} / baseline {wins['baseline']} / tie {wins['tie']}",
            "threshold": "with-skill wins > baseline wins",
            "pass": readability_pass},
    }
    if strictness == "strict":
        hits = arm["replacement_hits"] if complete else None
        checks["replacement_hits"] = {
            "value": hits, "threshold": f"== {MAX_REPLACEMENT_HITS}",
            "pass": None if hits is None else hits <= MAX_REPLACEMENT_HITS}
    outcomes = [c["pass"] for c in checks.values()]
    if False in outcomes:
        verdict = "FAIL"
    elif None in outcomes:
        verdict = "INCOMPLETE"
    else:
        verdict = "PASS"
    return {"checks": checks, "verdict": verdict}


def fmt_ratio(value):
    return "n/a" if value is None else f"{value:.1%}"


def render_report(meta, results, agg, evaluation):
    """Render report.md as a string."""
    out = []
    out.append(f"# ste-writing eval report ({meta['timestamp']})\n")
    out.append(f"- Model: {meta['model'] or 'claude CLI default'}")
    out.append(f"- claude version: {meta['claude_version']}")
    out.append(f"- Request: `{request_for(meta['strictness'])}`")
    out.append(f"- Passages: {', '.join(r['id'] for r in results)}")
    out.append(f"- Judge order seed: {meta['seed']}")
    gates = ("relaxed thresholds" if meta["strictness"] == "relaxed"
             else "relaxed thresholds plus zero replacement-list hits")
    out.append(f"- Strictness: {meta['strictness']}. Gates use English passages only.\n")
    out.append(f"## Verdict (with-skill, {gates}): {evaluation['verdict']}\n")
    out.append("| Check | Value | Threshold | Result |")
    out.append("|---|---|---|---|")
    for name, c in evaluation["checks"].items():
        value = c["value"]
        if isinstance(value, float):
            value = f"{value:.1%}"
        out.append(f"| {name} | {value if value is not None else 'n/a'} | {c['threshold']} | "
                   f"{ {True: 'PASS', False: 'FAIL', None: 'n/a'}[c['pass']] } |")
    out.append("\n## Totals per arm (English passages)\n")
    out.append("| Arm | Sentences | Over limit | Over-limit ratio | Passive | Progressive | "
               "Passive+progressive ratio | Replacement hits | Meaning scores | Min meaning |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    for arm in ARMS:
        a = agg[arm]
        out.append(f"| {arm} | {a['sentences']} | {a['over_limit']} | {fmt_ratio(a['over_limit_ratio'])} | "
                   f"{a['passive']} | {a['progressive']} | {fmt_ratio(a['passive_progressive_ratio'])} | "
                   f"{a['replacement_hits']} | {a['meaning_scores']} | {a['min_meaning']} |")
    w = agg["readability"]
    out.append(f"\nReadability wins (judge, English passages): with-skill {w['with-skill']}, "
               f"baseline {w['baseline']}, tie {w['tie']}.\n")
    out.append("## Per passage\n")
    out.append("| Passage | Arm | Sentences | Over limit | Passive | Progressive | Perfect | "
               "Over-limit ratio | Passive+prog ratio | Replacement hits | Meaning | More readable |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in results:
        for arm in ARMS:
            d = r["arms"][arm]
            t = d.get("totals")
            readable = ""
            if r.get("readable"):
                readable = "yes" if r["readable"] == arm else ("tie" if r["readable"] == "tie" else "no")
            if t:
                cells = (t["sentences"], t["over_limit"], t["passive"], t["progressive"], t["perfect"],
                         fmt_ratio(t["over_limit_ratio"]), fmt_ratio(t["passive_progressive_ratio"]),
                         t.get("replacement_hits", 0))
            else:
                cells = ("n/a",) * 8
            out.append(f"| {r['id']} | {arm} | " + " | ".join(str(c) for c in cells)
                       + f" | {d.get('meaning')} | {readable} |")
    out.append("\n## Judge reasons\n")
    for r in results:
        out.append(f"- {r['id']} (A = {r.get('order', ['?', '?'])[0]}, B = {r.get('order', ['?', '?'])[1]}): "
                   f"{r.get('reason') or 'no judge result'}")
    zh = [r for r in results if r["lang"] == "zh"]
    if zh:
        out.append("\n## Manual review (Chinese passages)\n")
        out.append("No numeric metrics. Judge scores are informational. The maintainer reviews STE principles "
                   "and meaning by hand.\n")
        for r in zh:
            out.append(f"### {r['id']}\n")
            out.append("Original:\n")
            out.append(_blockquote(r["original"]))
            for arm in ARMS:
                d = r["arms"][arm]
                out.append(f"\n{arm} (judge meaning {d.get('meaning')}, "
                           f"more readable: {'yes' if r.get('readable') == arm else ('tie' if r.get('readable') == 'tie' else 'no')}):\n")
                out.append(_blockquote(d.get("output") or "(no output)"))
            out.append("")
    return "\n".join(out) + "\n"


def _blockquote(text):
    return "\n".join("> " + line for line in text.strip().splitlines())


# --------------------------------------------------------------------------
# Explain set: pure logic (unit-tested in test_run_eval.py)
# --------------------------------------------------------------------------

def _section(text, title):
    m = re.search(rf"^## {re.escape(title)}[ \t]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else None


def parse_explain_topic(topic_id, text):
    """Read the language, the request, the optional context and the "Reader should understand" bullets."""
    lang = re.search(r"^- Language:\s*(\S+)", text, re.M)
    request = _section(text, "Request")
    if not (lang and request):
        raise ValueError(f"explain topic {topic_id}: missing Language or Request")
    points = [line[2:].strip() for line in (_section(text, "Reader should understand") or "").splitlines()
              if line.startswith("- ")]
    return {"id": topic_id, "lang": lang.group(1), "request": request,
            "context": _section(text, "Context") or None, "points": points}


def explain_prompt(topic, suffix=None):
    """The explain request, then the context if any, then the optional suffix. Both arms get the same one."""
    parts = [topic["request"].strip()] + ([topic["context"].strip()] if topic.get("context") else [])
    if suffix:
        parts.append(suffix.strip())
    return "\n\n".join(parts) + "\n"


def ab_orders(topic_ids, seed):
    """{topic: [arm shown as A, arm shown as B]}, random per topic, repeatable by seed."""
    return {tid: list(judge_order(seed, tid)) for tid in topic_ids}


def explain_aggregate(results):
    """Per-arm figures for the explain set: answers, cost, agent time, and the
    checker totals pooled over the answers that have metrics (English only)."""
    agg = {}
    for arm in ARMS:
        entries = [r["arms"][arm] for r in results]
        measured = [e["totals"] for e in entries if e.get("totals")]
        sentences = sum(t["sentences"] for t in measured)
        over = sum(t["over_limit"] for t in measured)
        passive = sum(t["passive"] for t in measured)
        progressive = sum(t["progressive"] for t in measured)
        agg[arm] = {
            "answers": sum(1 for e in entries if e.get("output")),
            "measured": len(measured),
            "sentences": sentences, "over_limit": over, "passive": passive, "progressive": progressive,
            "over_limit_ratio": over / sentences if sentences else None,
            "passive_progressive_ratio": (passive + progressive) / sentences if sentences else None,
            "cost_usd": round(sum((e.get("meta") or {}).get("cost_usd") or 0 for e in entries), 4),
            "seconds": round(sum(e.get("seconds") or 0 for e in entries), 1),
        }
    return agg


def review_entries(results, orders):
    """Blind entries for the review page: the answers under A/B labels, no arm names."""
    return [{"id": r["id"], "lang": r["lang"], "points": r["points"],
             "answers": {label: r["arms"][arm].get("output")
                         for label, arm in zip(("A", "B"), orders[r["id"]])}}
            for r in results]


REVIEW_CSS = """
body{font-family:system-ui,sans-serif;margin:1rem;background:#f4f4f4;color:#111;line-height:1.6}
section{background:#fff;border:1px solid #ccc;border-radius:6px;padding:1rem;margin-bottom:2rem}
.pair{display:grid;grid-template-columns:repeat(auto-fit,minmax(20rem,1fr));gap:1rem;align-items:start}
.answer{white-space:pre-wrap;border:1px solid #999;border-radius:4px;padding:.8rem;background:#fafafa}
.answer.rendered{white-space:normal}
.answer.rendered pre{white-space:pre-wrap;background:#eee;padding:.5rem;border-radius:4px}
.answer.rendered code{background:#eee;padding:0 .2rem;border-radius:3px}
.answer.rendered table{border-collapse:collapse}
.answer.rendered th,.answer.rendered td{border:1px solid #999;padding:.2rem .5rem}
h3{margin:.5rem 0}.missing{color:#a00}
table.rate{border-collapse:collapse;margin:.5rem 0}
table.rate th,table.rate td{border:1px solid #999;padding:.4rem .8rem;min-width:6rem;text-align:left}
"""

# The answers are Markdown. The page keeps the escaped text as the fallback and, when the
# pinned libraries load, renders it the way a chat client would, sanitized.
REVIEW_MARKDOWN_JS = (
    '<script src="https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js"></script>'
    '<script src="https://cdn.jsdelivr.net/npm/dompurify@3.1.6/dist/purify.min.js"></script>'
    "<script>document.addEventListener('DOMContentLoaded',function(){"
    "if(!window.marked||!window.DOMPurify)return;"
    "document.querySelectorAll('.answer').forEach(function(el){"
    "el.innerHTML=DOMPurify.sanitize(marked.parse(el.textContent));el.classList.add('rendered');});});</script>"
)

# Rating instructions, Traditional Chinese (Taiwan), English axis names in parentheses.
REVIEW_INTRO = (
    "<p>每個主題請比較回答 A 和回答 B。兩個回答收到的要求相同（「用 STE 解釋：……」）。"
    "A/B 的順序在每個主題都是隨機的，對照表只在 report.json。評分完成前，請不要打開 run 資料夾裡的其他檔案。</p>"
    "<p>每個回答各打兩個分數，各為 1 到 5 分（1 = 很差，5 = 很好）：</p>"
    "<ul><li><strong>理解（Understanding）</strong>：讀完這個回答後，"
    "你對該主題「讀者應該理解」的各個重點理解了多少。</li>"
    "<li><strong>好讀（Readability）</strong>：句子是否簡短、清楚，用詞是否一致，"
    "讀起來是否不費力。</li></ul>"
    "<p>最後選出該主題中較好的回答：A、B 或平手（tie）。"
    "把分數填進 RESULTS.md 的表格，之後再用 report.json 的 ab_key 對照 A、B 各是哪一組。</p>"
)


def render_review(entries, timestamp):
    """Blind review page, in Traditional Chinese (Taiwan). entries: review_entries() output.
    Per topic: the points, a two-axis rating table (理解, 好讀) for A and B, the better-answer
    line, then answers A and B as plain text. Only A and B labels appear, never arm names."""
    esc = html.escape
    out = ["<!doctype html>", '<html lang="zh-TW"><head><meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width, initial-scale=1">',
           f"<title>ste-writing 解釋盲測評分 {esc(timestamp)}</title><style>{REVIEW_CSS}</style></head><body>",
           f"<h1>ste-writing 解釋盲測評分（{esc(timestamp)}）</h1>", REVIEW_INTRO]
    for e in entries:
        out.append(f"<section><h2>{esc(e['id'])}（{esc(e['lang'])}）</h2>")
        if e["points"]:
            out.append("<p>讀者應該理解（Reader should understand）：</p><ul>"
                       + "".join(f"<li>{esc(p)}</li>" for p in e["points"]) + "</ul>")
        out.append('<table class="rate"><tr><th></th><th>理解（Understanding），1-5</th>'
                   "<th>好讀（Readability），1-5</th></tr>"
                   + "".join(f"<tr><th>回答 {label}</th><td></td><td></td></tr>" for label in ("A", "B"))
                   + "</table>")
        out.append("<p>較好的回答（Better answer）：A / B / 平手（tie）：______</p>")
        out.append('<div class="pair">')
        for label in ("A", "B"):
            text = e["answers"].get(label)
            body = (f'<div class="answer">{esc(text.strip())}</div>' if text
                    else '<p class="missing">沒有回答</p>')
            out.append(f"<div><h3>回答 {label}</h3>{body}</div>")
        out.append("</div></section>")
    out.append(REVIEW_MARKDOWN_JS)
    out.append("</body></html>")
    return "\n".join(out) + "\n"


def render_explain_report(meta, results, agg):
    """Render report.md for the explain set: per-arm figures, not the answers or the A/B key."""
    out = [f"# ste-writing explain eval report ({meta['timestamp']})\n",
           f"- Model: {meta['model'] or 'claude CLI default'}",
           f"- claude version: {meta['claude_version']}",
           f"- Topics: {', '.join(r['id'] for r in results)}",
           f"- Review page: `{meta['review']}` (A/B key in report.json only; seed {meta['seed']})",
           "- No verdict: the maintainer rates the answers on the review page.\n",
           "## Per arm\n",
           "| Arm | Answers | Measured (English) | Sentences | Over-limit ratio | Passive+progressive ratio "
           "| Cost | Agent time |",
           "|---|---|---|---|---|---|---|---|"]
    for arm in ARMS:
        a = agg[arm]
        out.append(f"| {arm} | {a['answers']}/{len(results)} | {a['measured']} | {a['sentences']} | "
                   f"{fmt_ratio(a['over_limit_ratio'])} | {fmt_ratio(a['passive_progressive_ratio'])} | "
                   f"${a['cost_usd']:.2f} | {a['seconds']:.0f} s |")
    out += ["\n## Per topic and arm\n",
            "| Topic | Arm | Metrics | Sentences | Over limit | Passive | Progressive | Turns | Cost | Wall time |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        for arm in ARMS:
            a = r["arms"][arm]
            t, m = a.get("totals"), a.get("meta") or {}
            if t:
                cells = ["available", t["sentences"], t["over_limit"], t["passive"], t["progressive"]]
            else:
                cells = ["metrics not available" if a.get("output") else "no answer"] + ["n/a"] * 4
            cost = m.get("cost_usd")
            cells += [m.get("num_turns", "n/a"), "n/a" if cost is None else f"${cost:.2f}",
                      "n/a" if a.get("seconds") is None else f"{a['seconds']:.0f} s"]
            out.append(f"| {r['id']} | {arm} | " + " | ".join(str(c) for c in cells) + " |")
    errors = [(r["id"], arm, e) for r in results for arm in ARMS for e in r["arms"][arm].get("errors") or []]
    if errors:
        out.append("\n## Errors\n")
        out += [f"- {tid} / {arm}: {e}" for tid, arm, e in errors]
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# Running claude and the checker
# --------------------------------------------------------------------------

def build_cmd(claude_exe, arm, model):
    """Return the claude argv for one arm. The prompt is passed on stdin."""
    cmd = [claude_exe, "-p"] + ISOLATION_FLAGS
    if arm == "with-skill":
        cmd += ["--plugin-dir", str(REPO_ROOT)]
    if model:
        cmd += ["--model", model]
    return cmd


def build_judge_cmd(claude_exe, model):
    """Judge: same isolation, no plugin, no tools."""
    cmd = [claude_exe, "-p"] + ISOLATION_FLAGS + ["--tools", ""]
    if model:
        cmd += ["--model", model]
    return cmd


def rewrite_prompt(passage, strictness="relaxed"):
    return f"{request_for(strictness)}\n\n{passage.strip()}\n"


def judge_prompt(original, text_a, text_b):
    return (f"{JUDGE_INSTRUCTIONS}\n=== ORIGINAL ===\n{original.strip()}\n\n"
            f"=== REWRITE A ===\n{text_a.strip()}\n\n=== REWRITE B ===\n{text_b.strip()}\n")


def run_claude(cmd, prompt, timeout):
    """Run claude with the prompt on stdin. Returns (text, meta). Raises RuntimeError on failure."""
    SCRATCH_CWD.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                          cwd=SCRATCH_CWD, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr.strip()[:500]}")
    try:
        data = json.loads(proc.stdout)
    except ValueError as exc:
        raise RuntimeError(f"claude output is not JSON: {proc.stdout[:300]!r}") from exc
    if data.get("is_error"):
        raise RuntimeError(f"claude reported an error: {str(data.get('result'))[:500]}")
    meta = {"num_turns": data.get("num_turns"), "cost_usd": data.get("total_cost_usd"),
            "models": list((data.get("modelUsage") or {}).keys())}
    return (data.get("result") or "").strip(), meta


def checker_cmd(strictness):
    """The ste_check.py argv for a strictness. Strict also loads the replacement list."""
    cmd = [sys.executable, "-I", str(CHECKER), "-", "--strictness", strictness]
    if strictness == "strict":
        cmd += ["--replacements", str(REPLACEMENTS)]
    return cmd


def measure(text, strictness="relaxed"):
    """Run ste_check.py on text through its CLI. Returns the parsed JSON."""
    proc = subprocess.run(checker_cmd(strictness), input=text, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"ste_check.py failed ({proc.returncode}): {proc.stderr.strip()[:300]}")
    return json.loads(proc.stdout)


def load_passages(selected):
    files = sorted(p for p in PASSAGES_DIR.glob("0*.md"))
    passages = [(p.stem, p.read_text(encoding="utf-8")) for p in files]
    if selected:
        wanted = [s.strip() for s in selected.split(",") if s.strip()]
        passages = [(i, t) for i, t in passages if any(i == w or i.startswith(w) for w in wanted)]
        if not passages:
            raise SystemExit(f"no passage matches --passages {selected!r}")
    return passages


def judge_order(seed, passage_id):
    """Randomized but reproducible A/B order for one passage."""
    rng = random.Random(f"{seed}:{passage_id}")
    arms = list(ARMS)
    rng.shuffle(arms)
    return tuple(arms)


def process_passage(passage_id, original, args, claude_exe, run_dir):
    """Run both arms, measure, judge. Returns the per-passage result dict."""
    lang = passage_language(passage_id)
    result = {"id": passage_id, "lang": lang, "original": original, "arms": {}, "readable": None,
              "reason": "", "errors": []}
    for arm in ARMS:
        entry = {"output": None, "totals": None, "metrics": None, "meaning": None, "meta": None}
        result["arms"][arm] = entry
        try:
            text, meta = run_claude(build_cmd(claude_exe, arm, args.model), rewrite_prompt(original, args.strictness), args.timeout)
            entry["output"], entry["meta"] = text, meta
            (run_dir / f"{passage_id}.{arm}.txt").write_text(text + "\n", encoding="utf-8")
            metrics = measure(text, args.strictness)
            entry["metrics"] = metrics
            entry["totals"] = metrics["totals"] if metrics.get("metrics_available") else None
        except Exception as exc:  # keep going; the report marks the gap
            result["errors"].append(f"{arm}: {exc}")
    order = judge_order(args.seed, passage_id)
    result["order"] = list(order)
    outputs = [result["arms"][arm]["output"] for arm in order]
    if all(outputs):
        prompt = judge_prompt(original, outputs[0], outputs[1])
        for attempt in (1, 2):
            try:
                reply, _ = run_claude(build_judge_cmd(claude_exe, args.model), prompt, args.timeout)
                (run_dir / f"{passage_id}.judge.txt").write_text(reply + "\n", encoding="utf-8")
                judge = parse_judge(reply)
                if judge is None:
                    raise RuntimeError(f"judge reply is not valid JSON: {reply[:200]!r}")
                mapped = map_judge_to_arms(judge, order)
                for arm in ARMS:
                    result["arms"][arm]["meaning"] = mapped["meaning"][arm]
                result["readable"], result["reason"] = mapped["readable"], mapped["reason"]
                break
            except Exception as exc:
                result["errors"].append(f"judge attempt {attempt}: {exc}")
    return result


def load_explain_topics(selected):
    files = sorted(EXPLAIN_DIR.glob("0*.md"))
    topics = [parse_explain_topic(p.stem, p.read_text(encoding="utf-8")) for p in files]
    if selected:
        wanted = [s.strip() for s in selected.split(",") if s.strip()]
        topics = [t for t in topics if any(t["id"] == w or t["id"].startswith(w) for w in wanted)]
        if not topics:
            raise SystemExit(f"no explain topic matches --topics {selected!r}")
    return topics


def process_explain_arm(topic, arm, args, claude_exe, run_dir):
    """One explain answer: run the arm, save it, measure it. Returns the arm entry."""
    entry = {"output": None, "totals": None, "metrics": None, "meta": None, "seconds": None, "errors": []}
    start = time.monotonic()
    try:
        text, meta = run_claude(build_cmd(claude_exe, arm, args.model), explain_prompt(topic, args.suffix), args.timeout)
        entry["seconds"] = round(time.monotonic() - start, 1)
        entry["output"], entry["meta"] = text, meta
        (run_dir / f"{topic['id']}.{arm}.txt").write_text(text + "\n", encoding="utf-8")
        metrics = measure(text, "relaxed")
        entry["metrics"] = metrics
        entry["totals"] = metrics["totals"] if metrics.get("metrics_available") else None
    except Exception as exc:  # keep going; the report marks the gap
        if entry["seconds"] is None:
            entry["seconds"] = round(time.monotonic() - start, 1)
        entry["errors"].append(str(exc))
    return entry


def run_explain(args, claude_exe, timestamp):
    """The explain set: both arms per topic, blind review page, report. Returns the exit code."""
    topics = load_explain_topics(args.topics)
    if args.dry_run:
        print(f"cwd: {SCRATCH_CWD}")
        for t in topics:
            for arm in ARMS:
                print(f"[{t['id']}] {arm}: {' '.join(build_cmd(claude_exe, arm, args.model))}")
            print(f"[{t['id']}] stdin: {explain_prompt(t, args.suffix)!r}")
        print(f"checker: {' '.join(checker_cmd('relaxed'))}")
        print(f"review: runs/<timestamp>/review.html (A/B order seed {args.seed})")
        return 0

    run_dir = RUNS_DIR / timestamp
    run_dir.mkdir(parents=True)
    print(f"Run folder: {run_dir}", flush=True)
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {(t["id"], arm): pool.submit(process_explain_arm, t, arm, args, claude_exe, run_dir)
                   for t in topics for arm in ARMS}
        results = []
        for t in topics:
            r = {"id": t["id"], "lang": t["lang"], "request": t["request"], "context": t["context"],
                 "points": t["points"], "arms": {}}
            for arm in ARMS:
                a = futures[(t["id"], arm)].result()
                r["arms"][arm] = a
                print(f"done {t['id']}/{arm} in {a['seconds']:.0f} s"
                      + (f" (errors: {len(a['errors'])})" if a["errors"] else ""), flush=True)
            results.append(r)

    orders = ab_orders([r["id"] for r in results], args.seed)
    review = run_dir / "review.html"
    review.write_text(render_review(review_entries(results, orders), timestamp), encoding="utf-8")
    agg = explain_aggregate(results)
    meta = {"timestamp": timestamp, "set": "explain", "model": args.model, "seed": args.seed,
            "claude_version": claude_version(claude_exe), "isolation_flags": ISOLATION_FLAGS,
            "review": str(review)}
    (run_dir / "report.md").write_text(render_explain_report(meta, results, agg), encoding="utf-8")
    (run_dir / "report.json").write_text(
        json.dumps({"meta": meta, "aggregate": agg,
                    "ab_key": {tid: {"A": o[0], "B": o[1]} for tid, o in orders.items()},
                    "topics": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for arm in ARMS:
        a = agg[arm]
        print(f"{arm}: {a['answers']}/{len(results)} answers, cost ${a['cost_usd']:.2f}, {a['seconds']:.0f} s")
    print(f"Report: {run_dir / 'report.md'}")
    print(f"Review: {review}")
    errors = [(r["id"], arm, e) for r in results for arm in ARMS for e in r["arms"][arm]["errors"]]
    for tid, arm, e in errors:
        print(f"error [{tid}/{arm}]: {e}", file=sys.stderr)
    return 2 if errors else 0


def claude_version(claude_exe):
    try:
        proc = subprocess.run([claude_exe, "--version"], capture_output=True, text=True, timeout=60)
        return proc.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the ste-writing eval.")
    parser.add_argument("--set", choices=SETS, default="rewrite", dest="eval_set",
                        help="rewrite (default): passages, LLM judge, verdict; "
                             "explain: explain topics, blind review page for a human rating")
    parser.add_argument("--passages", help="rewrite set: comma-separated passage ids or number prefixes, e.g. 01,03")
    parser.add_argument("--topics", help="explain set: comma-separated topic ids or number prefixes, e.g. 01,03")
    parser.add_argument("--model", help="model alias or name passed to claude --model (default: CLI default)")
    parser.add_argument("--dry-run", action="store_true", help="print the commands and exit; call nothing")
    parser.add_argument("--workers", type=int, default=4, help="parallel passages (default 4)")
    parser.add_argument("--seed", default=None, help="seed for the judge or review A/B order (default: timestamp)")
    parser.add_argument("--timeout", type=int, default=600, help="seconds per claude call (default 600)")
    parser.add_argument("--suffix", default=None,
                        help="explain set: a line added to the request of both arms, e.g. a language instruction")
    parser.add_argument("--strictness", choices=STRICTNESS, default="relaxed",
                        help="relaxed (default) or strict: changes the request, the checker call and the gates")
    args = parser.parse_args(argv)
    if args.eval_set == "explain" and (args.passages or args.strictness != "relaxed"):
        parser.error("--set explain takes --topics; --passages and --strictness apply to the rewrite set only")
    if args.eval_set == "rewrite" and args.topics:
        parser.error("--topics applies to --set explain only")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    args.seed = args.seed or timestamp
    claude_exe = shutil.which("claude") or "claude"
    if args.eval_set == "explain":
        return run_explain(args, claude_exe, timestamp)
    passages = load_passages(args.passages)

    if args.dry_run:
        print(f"cwd: {SCRATCH_CWD}")
        for passage_id, original in passages:
            for arm in ARMS:
                print(f"[{passage_id}] {arm}: {' '.join(build_cmd(claude_exe, arm, args.model))}")
            order = judge_order(args.seed, passage_id)
            print(f"[{passage_id}] judge (A={order[0]}, B={order[1]}): "
                  f"{' '.join(build_judge_cmd(claude_exe, args.model))}")
            print(f"[{passage_id}] stdin: {request_for(args.strictness)!r} + passage ({len(original)} characters)")
        print(f"checker: {' '.join(checker_cmd(args.strictness))}")
        return 0

    run_dir = RUNS_DIR / timestamp
    run_dir.mkdir(parents=True)
    print(f"Run folder: {run_dir}")
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(process_passage, i, t, args, claude_exe, run_dir) for i, t in passages]
        results = []
        for future in futures:
            r = future.result()
            results.append(r)
            print(f"done {r['id']}" + (f" (errors: {len(r['errors'])})" if r["errors"] else ""))

    agg = aggregate(results)
    evaluation = evaluate(agg, args.strictness)
    meta = {"timestamp": timestamp, "model": args.model, "seed": args.seed, "strictness": args.strictness,
            "claude_version": claude_version(claude_exe), "isolation_flags": ISOLATION_FLAGS}
    (run_dir / "report.md").write_text(render_report(meta, results, agg, evaluation), encoding="utf-8")
    (run_dir / "report.json").write_text(
        json.dumps({"meta": meta, "aggregate": agg, "evaluation": evaluation, "passages": results},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Verdict: {evaluation['verdict']}")
    print(f"Report: {run_dir / 'report.md'}")
    errors = [e for r in results for e in r["errors"]]
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    return {"PASS": 0, "FAIL": 1, "INCOMPLETE": 2}[evaluation["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
