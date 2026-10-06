#!/usr/bin/env python3
"""Run the ste-writing eval: eight passages, with-skill vs baseline, plus an LLM judge.

Usage:
    python evals/ste-writing/run_eval.py [--passages 01,03,05] [--model MODEL]
                                         [--dry-run] [--workers N] [--seed S]
                                         [--timeout SECONDS]

For each passage the harness asks an agent "Rewrite the following text in STE."
in two arms (same request in both):
    with-skill  claude -p ... --plugin-dir <repo root>
    baseline    claude -p ...   (no plugin)
Each output is measured with skills/ste-writing/scripts/ste_check.py (relaxed).
One judge call per passage sees the original and both outputs in randomized A/B
order and returns meaning scores (1-5) and the more readable output.
Raw outputs and the report go to evals/ste-writing/runs/<timestamp>/.

See evals/ste-writing/README.md for the isolation flags and the thresholds.
Python standard library only. Exit code: 0 = PASS, 1 = FAIL, 2 = incomplete/error.
"""

import argparse
import json
import random
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
PASSAGES_DIR = HERE / "passages"
RUNS_DIR = HERE / "runs"
CHECKER = REPO_ROOT / "skills" / "ste-writing" / "scripts" / "ste_check.py"
# Neutral cwd outside the repo, so this repo's CLAUDE.md and .claude/ settings do not apply.
SCRATCH_CWD = Path(os.environ.get("STE_EVAL_CWD") or Path(tempfile.gettempdir()) / "ste-writing-eval")

REQUEST = "Rewrite the following text in STE."
ARMS = ("with-skill", "baseline")

# Relaxed acceptance thresholds (issue #3).
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
        sentences = over = passive = progressive = 0
        meanings = []
        missing_metrics = 0
        for r in english:
            totals = r["arms"][arm].get("totals")
            if totals:
                sentences += totals["sentences"]
                over += totals["over_limit"]
                passive += totals["passive"]
                progressive += totals["progressive"]
            else:
                missing_metrics += 1
            meanings.append(r["arms"][arm].get("meaning"))
        agg[arm] = {
            "sentences": sentences,
            "over_limit": over,
            "passive": passive,
            "progressive": progressive,
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


def evaluate(agg):
    """Check the with-skill arm against the relaxed thresholds.

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
    out.append(f"- Request: `{REQUEST}`")
    out.append(f"- Passages: {', '.join(r['id'] for r in results)}")
    out.append(f"- Judge order seed: {meta['seed']}")
    out.append(f"- Strictness: relaxed. Gates use English passages only.\n")
    out.append(f"## Verdict (with-skill, relaxed thresholds): {evaluation['verdict']}\n")
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
               "Passive+progressive ratio | Meaning scores | Min meaning |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for arm in ARMS:
        a = agg[arm]
        out.append(f"| {arm} | {a['sentences']} | {a['over_limit']} | {fmt_ratio(a['over_limit_ratio'])} | "
                   f"{a['passive']} | {a['progressive']} | {fmt_ratio(a['passive_progressive_ratio'])} | "
                   f"{a['meaning_scores']} | {a['min_meaning']} |")
    w = agg["readability"]
    out.append(f"\nReadability wins (judge, English passages): with-skill {w['with-skill']}, "
               f"baseline {w['baseline']}, tie {w['tie']}.\n")
    out.append("## Per passage\n")
    out.append("| Passage | Arm | Sentences | Over limit | Passive | Progressive | Perfect | "
               "Over-limit ratio | Passive+prog ratio | Meaning | More readable |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in results:
        for arm in ARMS:
            d = r["arms"][arm]
            t = d.get("totals")
            readable = ""
            if r.get("readable"):
                readable = "yes" if r["readable"] == arm else ("tie" if r["readable"] == "tie" else "no")
            if t:
                cells = (t["sentences"], t["over_limit"], t["passive"], t["progressive"], t["perfect"],
                         fmt_ratio(t["over_limit_ratio"]), fmt_ratio(t["passive_progressive_ratio"]))
            else:
                cells = ("n/a",) * 7
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


def rewrite_prompt(passage):
    return f"{REQUEST}\n\n{passage.strip()}\n"


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


def measure(text):
    """Run ste_check.py (relaxed) on text through its CLI. Returns the parsed JSON."""
    proc = subprocess.run([sys.executable, "-I", str(CHECKER), "-", "--strictness", "relaxed"],
                          input=text, capture_output=True, text=True, encoding="utf-8")
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
            text, meta = run_claude(build_cmd(claude_exe, arm, args.model), rewrite_prompt(original), args.timeout)
            entry["output"], entry["meta"] = text, meta
            (run_dir / f"{passage_id}.{arm}.txt").write_text(text + "\n", encoding="utf-8")
            metrics = measure(text)
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


def claude_version(claude_exe):
    try:
        proc = subprocess.run([claude_exe, "--version"], capture_output=True, text=True, timeout=60)
        return proc.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the ste-writing eval.")
    parser.add_argument("--passages", help="comma-separated passage ids or number prefixes, e.g. 01,03")
    parser.add_argument("--model", help="model alias or name passed to claude --model (default: CLI default)")
    parser.add_argument("--dry-run", action="store_true", help="print the commands and exit; call nothing")
    parser.add_argument("--workers", type=int, default=4, help="parallel passages (default 4)")
    parser.add_argument("--seed", default=None, help="seed for the judge A/B order (default: timestamp)")
    parser.add_argument("--timeout", type=int, default=600, help="seconds per claude call (default 600)")
    args = parser.parse_args(argv)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    args.seed = args.seed or timestamp
    passages = load_passages(args.passages)
    claude_exe = shutil.which("claude") or "claude"

    if args.dry_run:
        print(f"cwd: {SCRATCH_CWD}")
        for passage_id, original in passages:
            for arm in ARMS:
                print(f"[{passage_id}] {arm}: {' '.join(build_cmd(claude_exe, arm, args.model))}")
            order = judge_order(args.seed, passage_id)
            print(f"[{passage_id}] judge (A={order[0]}, B={order[1]}): "
                  f"{' '.join(build_judge_cmd(claude_exe, args.model))}")
            print(f"[{passage_id}] stdin: {REQUEST!r} + passage ({len(original)} characters)")
        print(f"checker: {sys.executable} -I {CHECKER} - --strictness relaxed")
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
    evaluation = evaluate(agg)
    meta = {"timestamp": timestamp, "model": args.model, "seed": args.seed,
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
