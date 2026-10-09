#!/usr/bin/env python3
"""Run the html-explainer eval: four topics, with-skill vs baseline, plus a blind review page.

Usage:
    python evals/html-explainer/run_eval.py [--topics 01,03] [--model MODEL]
                                            [--plugin-dir DIR] [--seed S]
                                            [--dry-run] [--workers N]
                                            [--timeout SECONDS]

For each topic in topics/ the harness sends the same request ("Make an
interactive web page that explains the following." + the topic's Source) in
two arms, each from its own scratch folder outside the repo:
    with-skill  claude -p ... --plugin-dir <plugin dir>
    baseline    claude -p ...   (no plugin)
It then finds the newest .html the agent left under the scratch folder and
measures it with the skill's own scripts (taken from <plugin dir>):
page_check.py (pass, issue rules, size, single file) and render_check.py
(pass, console and page errors, overflow at 390 px, interaction found,
screenshots). It copies the page and screenshots to
evals/html-explainer/runs/<timestamp>/<topic>/<arm>/ and builds review.html:
per topic the "Reader should understand" points, a two-axis rating table
(understanding, interaction and presentation) and the 390 and 1280 light
screenshots of both arms side by side in a random A/B order (--seed). The A/B key is only in report.json.

See evals/html-explainer/README.md. Python standard library only.
Exit code: 0 = PASS, 1 = FAIL, 2 = incomplete/error (with-skill arm gates).
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
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
TOPICS_DIR = HERE / "topics"
RUNS_DIR = HERE / "runs"
# Scratch root outside the repo and outside ~/.claude (writes there count as sensitive).
SCRATCH_ROOT = Path(os.environ.get("HTML_EVAL_CWD") or "D:/html-explainer-eval")

# Environment for the agent and the check scripts: caches and temp files off
# the system drive, no Python download by uv, UTF-8 I/O, no __pycache__.
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
ARMS = ("with-skill", "baseline")
GATED = ("page_check_ok", "render_ok")
SCRIPT_TIMEOUT = 300


# --------------------------------------------------------------------------
# Pure logic (unit-tested in test_run_eval.py)
# --------------------------------------------------------------------------

def _section(text, title):
    m = re.search(rf"^## {re.escape(title)}\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else None


def parse_topic(topic_id, text):
    """Read the language, the Source and the "Reader should understand" bullets."""
    lang = re.search(r"^- Language:\s*(\S+)", text, re.M)
    source = _section(text, "Source")
    if not (lang and source):
        raise ValueError(f"topic {topic_id}: missing Language or Source")
    points = [line[2:].strip() for line in (_section(text, "Reader should understand") or "").splitlines()
              if line.startswith("- ")]
    return {"id": topic_id, "lang": lang.group(1), "source": source, "points": points}


def build_prompt(topic):
    """The request. Both arms get the same one."""
    return f"Make an interactive web page that explains the following.\n\n{topic['source'].strip()}\n"


def choose_html(candidates):
    """candidates: [(path, mtime)]. The newest is the page; count and list all."""
    if not candidates:
        return {"path": None, "count": 0, "all": []}
    newest = max(candidates, key=lambda c: c[1])
    return {"path": newest[0], "count": len(candidates), "all": sorted(c[0] for c in candidates)}


def arm_metrics(page, render):
    """Per-arm metrics from page_check and render_check JSON. None = no data."""
    m = {"page_check_ok": None, "issue_rules": None, "size_kb": None, "single_file": None,
         "external": None, "render_ok": None, "console_errors": None, "page_errors": None,
         "overflow_390": None, "interaction": None, "render_error": None}
    if page and "issues" in page:
        rules = sorted({i["rule"] for i in page["issues"]})
        external = (page.get("stats") or {}).get("external") or []
        m.update(page_check_ok=bool(page["pass"]), issue_rules=rules, size_kb=page.get("size_kb"),
                 external=len(external),
                 single_file="local-resource" not in rules and not external)
    if render and "error" in render:
        m["render_error"] = render["error"]
    elif render:
        overflow = render.get("overflow_390")
        interaction = render.get("interaction")
        m.update(render_ok=bool(render["pass"]),
                 console_errors=len(render.get("console_errors") or []),
                 page_errors=len(render.get("page_errors") or []),
                 overflow_390=overflow["overflow"] if overflow else None,
                 interaction=(interaction["kind"] if interaction and not render.get("interaction_error")
                              else None))
    return m


def ab_orders(topic_ids, seed):
    """{topic: [arm shown as A, arm shown as B]}, random per topic, repeatable by seed."""
    rng = random.Random(seed)
    orders = {}
    for tid in topic_ids:
        order = list(ARMS)
        rng.shuffle(order)
        orders[tid] = order
    return orders


def aggregate(results):
    """Per-arm totals and a verdict on the with-skill arm.

    Verdict: FAIL if page_check or render_check fails on any with-skill page,
    else INCOMPLETE if one has no data (no page, check could not run), else PASS.
    The baseline arm is reported, not gated.
    """
    arms = {}
    for arm in ARMS:
        ms = [r["arms"][arm]["metrics"] for r in results]
        arms[arm] = {"pages": sum(1 for m in ms if m.get("page_check_ok") is not None),
                     "page_check_pass": sum(1 for m in ms if m.get("page_check_ok")),
                     "render_pass": sum(1 for m in ms if m.get("render_ok")),
                     "cost_usd": round(sum((r["arms"][arm].get("meta") or {}).get("cost_usd") or 0
                                           for r in results), 4),
                     "seconds": round(sum(r["arms"][arm].get("seconds") or 0 for r in results), 1)}
    outcomes = [r["arms"]["with-skill"]["metrics"].get(c) for r in results for c in GATED]
    verdict = "FAIL" if False in outcomes else "INCOMPLETE" if None in outcomes else "PASS"
    return {"topics": len(results), "arms": arms,
            "cost_usd": round(sum(a["cost_usd"] for a in arms.values()), 4),
            "seconds": round(sum(a["seconds"] for a in arms.values()), 1), "verdict": verdict}


def _yn(value):
    return {True: "PASS", False: "FAIL", None: "n/a"}[value]


def _num(value, fmt="{:.2f}"):
    return "n/a" if value is None else fmt.format(value)


def metrics_row(r, arm):
    a = r["arms"][arm]
    m, meta = a["metrics"], a.get("meta") or {}
    rules = m["issue_rules"]
    page = "n/a" if m["page_check_ok"] is None else _yn(m["page_check_ok"]) + (
        f" ({', '.join(rules)})" if rules else "")
    errors = ("n/a" if m["console_errors"] is None else f"{m['console_errors']} / {m['page_errors']}")
    render = _yn(m["render_ok"]) if not m["render_error"] else "n/a (error)"
    html_count = (a.get("html") or {}).get("count", 0)
    return [r["id"], arm, page, render, errors, _yn(None if m["overflow_390"] is None else not m["overflow_390"]),
            m["interaction"] or ("none" if m["render_ok"] is not None else "n/a"),
            _num(m["size_kb"], "{:.1f} KB"), _yn(m["single_file"]), str(html_count),
            str(meta.get("num_turns", "n/a")), _num(meta.get("cost_usd"), "${:.2f}"),
            _num(a.get("seconds"), "{:.0f} s")]


METRIC_HEADERS = ["Topic", "Arm", "page_check (issue rules)", "render_check", "Console / page errors",
                  "No overflow at 390", "Interaction", "Size", "Single file", "HTML files",
                  "Turns", "Cost", "Wall time"]


def render_report(meta, results, agg):
    out = [f"# html-explainer eval report ({meta['timestamp']})\n",
           f"- Model: {meta['model'] or 'claude CLI default'}",
           f"- claude version: {meta['claude_version']}",
           f"- Plugin dir (with-skill arm, check scripts): `{meta['plugin_dir']}`",
           f"- Topics: {', '.join(r['id'] for r in results)}",
           f"- Scratch root: `{meta['scratch_root']}`",
           f"- Review page: `{meta['review']}` (A/B key in report.json only; seed {meta['seed']})\n",
           f"## Verdict (with-skill arm, automated checks): {agg['verdict']}\n"]
    for arm in ARMS:
        a = agg["arms"][arm]
        out.append(f"- {arm}: page_check {a['page_check_pass']}/{agg['topics']}, render_check "
                   f"{a['render_pass']}/{agg['topics']}, cost ${a['cost_usd']:.2f}, {a['seconds']:.0f} s")
    out += [f"- Total cost ${agg['cost_usd']:.2f}, agent time {agg['seconds']:.0f} s\n",
            "## Per topic and arm\n",
            "| " + " | ".join(METRIC_HEADERS) + " |",
            "|" + "---|" * len(METRIC_HEADERS)]
    for r in results:
        for arm in ARMS:
            out.append("| " + " | ".join(metrics_row(r, arm)) + " |")
    out.append("\n## Details\n")
    for r in results:
        for arm in ARMS:
            a = r["arms"][arm]
            out.append(f"### {r['id']} / {arm}\n")
            found = a.get("html") or {}
            out.append(f"- Page: `{found.get('path') or 'none'}`"
                       + (f" (newest of {found['count']}: {', '.join(found['all'])})"
                          if found.get("count", 0) > 1 else ""))
            out.append(f"- Copied to: `{a.get('copied_to') or 'none'}`")
            for issue in (a.get("page_check") or {}).get("issues") or []:
                out.append(f"- page_check {issue['rule']} (line {issue.get('line')}): {issue.get('message')}")
            render = a.get("render_check") or {}
            for key in ("console_errors", "page_errors"):
                for e in render.get(key) or []:
                    out.append(f"- {key[:-1].replace('_', ' ')}: {e}")
            for key in ("interaction_error", "load_error", "error", "hint"):
                if render.get(key):
                    out.append(f"- render {key}: {render[key]}")
            for e in a.get("errors") or []:
                out.append(f"- Error: {e}")
            if a.get("agent_reply"):
                out.append("\nAgent's final reply:\n")
                out.append("\n".join("> " + line for line in a["agent_reply"].strip().splitlines()))
            out.append("")
    return "\n".join(out) + "\n"


REVIEW_CSS = """
body{font-family:system-ui,sans-serif;margin:1rem;background:#f4f4f4;color:#111}
section{background:#fff;border:1px solid #ccc;border-radius:6px;padding:1rem;margin-bottom:2rem}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:1rem;align-items:start}
.pair figure{margin:0}.pair img{width:100%;border:1px solid #999}
.w390 img{max-width:390px}figcaption{font-weight:bold;margin:.5rem 0}
.missing{color:#a00}
table.rate{border-collapse:collapse;margin:.5rem 0}
table.rate th,table.rate td{border:1px solid #999;padding:.4rem .8rem;min-width:6rem;text-align:left}
"""

# Rating instructions, Traditional Chinese (Taiwan), English axis names in parentheses.
REVIEW_INTRO = (
    "<p>每個主題請比較頁面 A 和頁面 B。請打開每個頁面，實際操作它的互動。"
    "A/B 的順序在每個主題都是隨機的，對照表只在 report.json。</p>"
    "<p>每個頁面各打兩個分數，各為 1 到 5 分（1 = 很差，5 = 很好）：</p>"
    "<ul><li><strong>理解（Understanding）</strong>：看完這個頁面後，"
    "你對該主題「讀者應該理解」的各個重點理解了多少。</li>"
    "<li><strong>互動與呈現（Interaction and presentation）</strong>：互動是否好用、"
    "版面與視覺是否清楚好讀（手機與桌面都看）。</li></ul>"
    "<p>最後選出該主題中較好的頁面：A、B 或平手（tie）。"
    "把分數填進 RESULTS.md 的表格，之後再用 report.json 的 ab_key 對照 A、B 各是哪一組。</p>"
)


def render_review(entries, timestamp):
    """Blind review page, in Traditional Chinese (Taiwan). entries: [{"id", "lang", "points",
    "shots": {"A"|"B": {"390"|"1280": path|None}}, "pages": {"A"|"B": path|None}}].
    Only A and B labels appear, never arm names. Per topic: the points, the links, a two-axis
    rating table (理解, 互動與呈現) for A and B, the better-page line, then the screenshots."""
    esc = html.escape
    out = ["<!doctype html>", '<html lang="zh-TW"><head><meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width, initial-scale=1">',
           f"<title>html-explainer 盲測評分 {esc(timestamp)}</title><style>{REVIEW_CSS}</style></head><body>",
           f"<h1>html-explainer 盲測評分（{esc(timestamp)}）</h1>", REVIEW_INTRO]
    for e in entries:
        out.append(f"<section><h2>{esc(e['id'])}（{esc(e['lang'])}）</h2>")
        if e["points"]:
            out.append("<p>讀者應該理解（Reader should understand）：</p><ul>"
                       + "".join(f"<li>{esc(p)}</li>" for p in e["points"]) + "</ul>")
        links = []
        for label in ("A", "B"):
            page = e["pages"].get(label)
            links.append(f'<a href="{esc(page)}">開啟頁面 {label}</a>' if page
                         else f'<span class="missing">頁面 {label}：沒有頁面</span>')
        out.append("<p>" + " · ".join(links) + "</p>")
        out.append('<table class="rate"><tr><th></th><th>理解（Understanding），1-5</th>'
                   "<th>互動與呈現（Interaction and presentation），1-5</th></tr>"
                   + "".join(f"<tr><th>頁面 {label}</th><td></td><td></td></tr>" for label in ("A", "B"))
                   + "</table>")
        out.append("<p>較好的頁面（Better page）：A / B / 平手（tie）：______</p>")
        for width in ("390", "1280"):
            out.append(f'<h3>{width} px，淺色模式</h3><div class="pair w{width}">')
            for label in ("A", "B"):
                shot = e["shots"][label].get(width)
                body = (f'<img src="{esc(shot)}" alt="頁面 {label}，{width} px">' if shot
                        else '<p class="missing">沒有截圖</p>')
                out.append(f"<figure><figcaption>頁面 {label}</figcaption>{body}</figure>")
            out.append("</div>")
        out.append("</section>")
    out.append("</body></html>")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# Running claude and the checks
# --------------------------------------------------------------------------

def build_cmd(claude_exe, model, arm, plugin_dir):
    cmd = [claude_exe, "-p"] + ISOLATION_FLAGS
    if arm == "with-skill":
        cmd += ["--plugin-dir", str(plugin_dir)]
    cmd += ["--allowedTools", ",".join(ALLOWED_TOOLS)]
    if model:
        cmd += ["--model", model]
    return cmd


def agent_env(tmp):
    env = dict(os.environ)
    env.update(AGENT_ENV)
    env.update({"TMPDIR": str(tmp), "TEMP": str(tmp), "TMP": str(tmp)})
    return env


class ClaudeError(RuntimeError):
    """claude returned JSON but reported an error; keeps the reply and turns/cost."""

    def __init__(self, message, reply, meta):
        super().__init__(message)
        self.reply, self.meta = reply, meta


def run_claude(cmd, prompt, cwd, timeout, env):
    """Run claude with the prompt on stdin. Returns (reply, meta). Raises RuntimeError on failure."""
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
            "models": list((data.get("modelUsage") or {}).keys()),
            "is_error": data.get("is_error"), "subtype": data.get("subtype")}
    reply = (data.get("result") or "").strip()
    if proc.returncode != 0 or data.get("is_error"):
        raise ClaudeError(f"claude error (exit {proc.returncode}, {data.get('subtype')}): {reply[:300]}",
                          reply, meta)
    return reply, meta


def find_html(cwd):
    candidates = []
    for path in Path(cwd).rglob("*.html"):
        try:
            candidates.append((str(path), path.stat().st_mtime))
        except OSError:
            continue
    return choose_html(candidates)


def run_json(cmd, env, cwd):
    """Run a check script; return (exit code, parsed JSON or None, stderr)."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              env=env, cwd=cwd, timeout=SCRIPT_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None, None, f"timed out after {SCRIPT_TIMEOUT} s"
    try:
        return proc.returncode, json.loads(proc.stdout), proc.stderr.strip()
    except ValueError:
        return proc.returncode, None, (proc.stderr.strip() or proc.stdout.strip())[:500]


def load_topics(selected):
    topics = [parse_topic(p.stem, p.read_text(encoding="utf-8")) for p in sorted(TOPICS_DIR.glob("0*.md"))]
    if selected:
        wanted = [s.strip() for s in selected.split(",") if s.strip()]
        topics = [t for t in topics if any(t["id"] == w or t["id"].startswith(w) for w in wanted)]
        if not topics:
            raise SystemExit(f"no topic matches --topics {selected!r}")
    return topics


def process_arm(topic, arm, args, claude_exe, run_dir, scratch_run):
    cwd = scratch_run / topic["id"] / arm
    tmp = scratch_run / "_tmp" / f"{topic['id']}-{arm}"
    cwd.mkdir(parents=True, exist_ok=True)
    tmp.mkdir(parents=True, exist_ok=True)
    env = agent_env(tmp)
    a = {"meta": None, "agent_reply": None, "errors": [], "html": None, "copied_to": None,
         "page_check": None, "render_check": None, "screenshots": {}}
    started = time.monotonic()
    try:
        a["agent_reply"], a["meta"] = run_claude(build_cmd(claude_exe, args.model, arm, args.plugin_dir),
                                                 build_prompt(topic), cwd, args.timeout, env)
    except ClaudeError as exc:
        a["agent_reply"], a["meta"] = exc.reply or None, exc.meta
        a["errors"].append(str(exc))
    except Exception as exc:  # keep going; measure whatever the agent left behind
        a["errors"].append(str(exc))
    a["seconds"] = round(time.monotonic() - started, 1)

    dest = run_dir / topic["id"] / arm
    dest.mkdir(parents=True, exist_ok=True)
    if a["agent_reply"]:
        (dest / "agent-reply.md").write_text(a["agent_reply"] + "\n", encoding="utf-8")
    a["html"] = find_html(cwd)
    if a["html"]["count"] > 1:
        a["errors"].append(f"{a['html']['count']} .html files; measured the newest")
    page_path = a["html"]["path"]
    if page_path is None:
        a["errors"].append(f"no .html under {cwd}")
    else:
        shutil.copy2(page_path, dest / Path(page_path).name)
        a["copied_to"] = str(dest)
        scripts = Path(args.plugin_dir) / "skills" / "html-explainer" / "scripts"
        code, a["page_check"], err = run_json([sys.executable, str(scripts / "page_check.py"), page_path],
                                              env, cwd)
        if a["page_check"] is None:
            a["errors"].append(f"page_check exit {code}: {err}")
        shots = dest / "screenshots"
        code, a["render_check"], err = run_json(["uv", "run", str(scripts / "render_check.py"), page_path,
                                                 "--out", str(shots)], env, cwd)
        if a["render_check"] is None:
            a["errors"].append(f"render_check exit {code}: {err}")
        for width, name in (("390", "390x844-light.png"), ("1280", "1280x800-light.png")):
            if (shots / name).is_file():
                a["screenshots"][width] = str(shots / name)
    a["metrics"] = arm_metrics(a["page_check"], a["render_check"])
    return a


def build_review(results, orders, run_dir, timestamp):
    """Copy the light screenshots and pages under neutral A/B names and write review.html."""
    review = run_dir / "review"
    review.mkdir(exist_ok=True)
    entries = []
    for r in results:
        e = {"id": r["id"], "lang": r["lang"], "points": r["points"], "shots": {}, "pages": {}}
        for label, arm in zip(("A", "B"), orders[r["id"]]):
            a = r["arms"][arm]
            e["shots"][label] = {}
            for width in ("390", "1280"):
                src = a["screenshots"].get(width)
                if src:
                    name = f"{r['id']}-{label}-{width}.png"
                    shutil.copy2(src, review / name)
                    e["shots"][label][width] = f"review/{name}"
            page = (a.get("html") or {}).get("path")
            if page:
                name = f"{r['id']}-{label}.html"
                shutil.copy2(page, review / name)
                e["pages"][label] = f"review/{name}"
        entries.append(e)
    path = run_dir / "review.html"
    path.write_text(render_review(entries, timestamp), encoding="utf-8")
    return path


def claude_version(claude_exe):
    try:
        proc = subprocess.run([claude_exe, "--version"], capture_output=True, text=True, timeout=60)
        return proc.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the html-explainer eval.")
    parser.add_argument("--topics", help="comma-separated topic ids or number prefixes, e.g. 01,03")
    parser.add_argument("--model", help="model alias or name passed to claude --model (default: CLI default)")
    parser.add_argument("--plugin-dir", default=str(REPO_ROOT),
                        help="plugin folder for the with-skill arm and the check scripts (default: repo root)")
    parser.add_argument("--seed", type=int, help="A/B order seed (default: random, recorded in report.json)")
    parser.add_argument("--dry-run", action="store_true", help="print the commands and exit; call nothing")
    parser.add_argument("--workers", type=int, default=2, help="parallel topic/arm runs (default 2)")
    parser.add_argument("--timeout", type=int, default=1200, help="seconds per agent run (default 1200)")
    args = parser.parse_args(argv)
    args.plugin_dir = str(Path(args.plugin_dir).resolve())
    if not (Path(args.plugin_dir) / "skills" / "html-explainer" / "SKILL.md").is_file():
        raise SystemExit(f"no skills/html-explainer/SKILL.md under --plugin-dir {args.plugin_dir}")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    topics = load_topics(args.topics)
    claude_exe = shutil.which("claude") or "claude"
    scratch_run = SCRATCH_ROOT / timestamp
    seed = args.seed if args.seed is not None else random.randrange(1_000_000)

    if args.dry_run:
        print(f"env: {AGENT_ENV} + TMPDIR/TEMP/TMP under {scratch_run / '_tmp'}")
        for t in topics:
            for arm in ARMS:
                print(f"[{t['id']}/{arm}] cwd: {scratch_run / t['id'] / arm}")
                print(f"[{t['id']}/{arm}] {' '.join(build_cmd(claude_exe, args.model, arm, args.plugin_dir))}")
            print(f"[{t['id']}] stdin: {build_prompt(t)!r}")
        return 0

    run_dir = RUNS_DIR / timestamp
    run_dir.mkdir(parents=True)
    print(f"Run folder: {run_dir}", flush=True)
    jobs = [(t, arm) for t in topics for arm in ARMS]
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {(t["id"], arm): pool.submit(process_arm, t, arm, args, claude_exe, run_dir, scratch_run)
                   for t, arm in jobs}
        results = []
        for t in topics:
            r = {"id": t["id"], "lang": t["lang"], "points": t["points"], "arms": {}}
            for arm in ARMS:
                a = futures[(t["id"], arm)].result()
                r["arms"][arm] = a
                m = a["metrics"]
                print(f"done {t['id']}/{arm} in {a['seconds']:.0f} s: page_check {_yn(m['page_check_ok'])}, "
                      f"render {_yn(m['render_ok'])}" + (f" (errors: {len(a['errors'])})" if a["errors"] else ""),
                      flush=True)
            results.append(r)

    orders = ab_orders([r["id"] for r in results], seed)
    review = build_review(results, orders, run_dir, timestamp)
    agg = aggregate(results)
    meta = {"timestamp": timestamp, "model": args.model, "claude_version": claude_version(claude_exe),
            "plugin_dir": args.plugin_dir, "isolation_flags": ISOLATION_FLAGS, "allowed_tools": ALLOWED_TOOLS,
            "env": AGENT_ENV, "scratch_root": str(scratch_run), "review": str(review), "seed": seed,
            "workers": args.workers, "timeout": args.timeout}
    (run_dir / "report.md").write_text(render_report(meta, results, agg), encoding="utf-8")
    (run_dir / "report.json").write_text(
        json.dumps({"meta": meta, "aggregate": agg,
                    "ab_key": {tid: {"A": o[0], "B": o[1]} for tid, o in orders.items()},
                    "topics": results}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(f"Verdict: {agg['verdict']}")
    print(f"Report: {run_dir / 'report.md'}")
    print(f"Review: {review}")
    for r in results:
        for arm in ARMS:
            for e in r["arms"][arm]["errors"]:
                print(f"error [{r['id']}/{arm}]: {e}", file=sys.stderr)
    return {"PASS": 0, "FAIL": 1, "INCOMPLETE": 2}[agg["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
