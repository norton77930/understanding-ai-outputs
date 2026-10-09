#!/usr/bin/env python3
"""Run the video-explainer eval: four approved topics, with-skill arm only.

Usage:
    python evals/video-explainer/run_eval.py [--topics 01,03] [--model MODEL]
                                             [--dry-run] [--workers N]
                                             [--timeout SECONDS]

For each topic in topics/ the harness asks one agent (claude -p with
--plugin-dir <repo root>) to "Make an explainer video of the following, using
the <preset> output preset", with the storyboard pre-approved, from a scratch
folder outside the repo. It then measures what the agent produced:
render success (ffprobe + a full decode), resolution against the preset,
layout-check pass rate (scenes not flagged / total; fallback count),
audio/video length difference (pass at 0.3 s or less), captions match
narration (SRT cue text vs storyboard narration, normalized), turns and cost.
The deliverables and the report go to evals/video-explainer/runs/<timestamp>/.

See evals/video-explainer/README.md. Python standard library only.
Exit code: 0 = PASS, 1 = FAIL, 2 = incomplete/error.
"""

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
TOPICS_DIR = HERE / "topics"
RUNS_DIR = HERE / "runs"
# Scratch root outside the repo and outside ~/.claude (writes there count as sensitive).
SCRATCH_ROOT = Path(os.environ.get("VIDEO_EVAL_CWD") or "D:/video-explainer-eval")

# Environment for the agent and the scripts it runs: caches off the system
# drive, no Python download by uv, UTF-8 I/O, and no __pycache__ in the skill folder.
AGENT_ENV = {
    "UV_CACHE_DIR": "D:/uv-cache",
    "UV_PYTHON_DOWNLOADS": "never",
    "PYTHONUTF8": "1",
    "VIDEO_EXPLAINER_CACHE": "D:/video-explainer-cache",
    "PYTHONDONTWRITEBYTECODE": "1",
}

ISOLATION_FLAGS = [
    "--setting-sources", "project,local",
    "--strict-mcp-config",
    "--no-session-persistence",
    "--output-format", "json",
]
ALLOWED_TOOLS = ["Bash", "Read", "Write", "Edit", "Skill", "Glob", "Grep"]

PRESET_RESOLUTION = {"explainer": (1280, 720), "youtube": (1920, 1080), "short": (1080, 1920)}
MAX_AV_DIFFERENCE = 0.3
DELIVERABLES = ("video.mp4", "video.srt", "script.md", "storyboard.json", "scenes.py",
                "plan.json", "preview.json", "final.json")
CHECKS = ("render_ok", "resolution_ok", "av_ok", "captions_ok")


# --------------------------------------------------------------------------
# Pure logic (unit-tested in test_run_eval.py)
# --------------------------------------------------------------------------

def parse_topic(topic_id, text):
    """Read language, output preset and the Source section from a topic file."""
    lang = re.search(r"^- Language:\s*(\S+)", text, re.M)
    preset = re.search(r"^- Output preset:\s*`?([\w-]+)`?", text, re.M)
    source = re.search(r"^## Source\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not (lang and preset and source):
        raise ValueError(f"topic {topic_id}: missing Language, Output preset or Source")
    return {"id": topic_id, "lang": lang.group(1), "preset": preset.group(1),
            "source": source.group(1).strip()}


def build_prompt(topic):
    return (f"Make an explainer video of the following, using the {topic['preset']} output preset. "
            "The storyboard is pre-approved: do not wait for confirmation; render it. "
            "Any model download the plan lists is approved.\n\n"
            f"{topic['source'].strip()}\n")


def _stamp_seconds(stamp):
    h, m, rest = stamp.strip().split(":")
    s, ms = rest.replace(".", ",").split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse_srt(text):
    """Parse SRT text into [{"start", "end", "text"}] (cue text lines joined by \\n)."""
    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = block.split("\n")
        for i, line in enumerate(lines):
            if "-->" in line:
                start, end = line.split("-->")
                cues.append({"start": _stamp_seconds(start), "end": _stamp_seconds(end.split()[0]),
                             "text": "\n".join(lines[i + 1:]).strip()})
                break
    return cues


def normalize_caption(text):
    """Lower-case letters and digits only: drop punctuation, symbols, spaces, line breaks."""
    return "".join(ch for ch in unicodedata.normalize("NFKC", text).lower()
                   if unicodedata.category(ch)[0] in "LN")


def caption_match(cues, narrations):
    """Compare cue i with scene i's narration after normalization.

    Returns {"matched", "scenes", "cues", "similarity", "pass"}. similarity is
    the difflib ratio of all cue text vs all narration (normalized).
    """
    matched = sum(1 for cue, narration in zip(cues, narrations)
                  if normalize_caption(cue["text"]) == normalize_caption(narration))
    all_cues = normalize_caption("".join(c["text"] for c in cues))
    all_narration = normalize_caption("".join(narrations))
    similarity = difflib.SequenceMatcher(None, all_cues, all_narration).ratio()
    return {"matched": matched, "scenes": len(narrations), "cues": len(cues),
            "similarity": round(similarity, 4),
            "pass": len(cues) == len(narrations) and matched == len(narrations)}


def parse_probe(data):
    """Pick width, height and stream lengths from ffprobe JSON."""
    out = {"width": None, "height": None, "video_seconds": None, "audio_seconds": None}
    for stream in data.get("streams", []):
        duration = stream.get("duration")
        if stream.get("codec_type") == "video" and out["width"] is None:
            out["width"], out["height"] = stream.get("width"), stream.get("height")
            out["video_seconds"] = float(duration) if duration else None
        elif stream.get("codec_type") == "audio" and out["audio_seconds"] is None:
            out["audio_seconds"] = float(duration) if duration else None
    if out["width"] is not None and out["video_seconds"] is None:
        duration = (data.get("format") or {}).get("duration")
        out["video_seconds"] = float(duration) if duration else None
    return out


def choose_final(candidates):
    """candidates: [(path, mtime, data)]. Newest with ok true, else newest; None if empty."""
    if not candidates:
        return None
    ok = [c for c in candidates if c[2].get("ok")]
    return max(ok or candidates, key=lambda c: c[1])


def topic_metrics(preset, final, probe, plays, captions):
    """Per-topic metrics. A check is True, False, or None when its data is missing."""
    render_ok = bool(final and final.get("ok") and probe and probe.get("width") and plays)
    m = {"render_ok": render_ok, "resolution": None, "resolution_ok": None,
         "video_seconds": None, "audio_seconds": None, "av_difference_seconds": None, "av_ok": None,
         "scenes": None, "flagged": None, "fallbacks": None, "layout_pass_rate": None,
         "captions": captions, "captions_ok": captions["pass"] if captions else None}
    if final and final.get("scenes"):
        m["scenes"] = len(final["scenes"])
        m["flagged"] = len(final.get("flagged") or [])
        m["fallbacks"] = len(final.get("replaced") or [])
        m["layout_pass_rate"] = (m["scenes"] - m["flagged"]) / m["scenes"]
    if probe and probe.get("width"):
        m["resolution"] = f"{probe['width']}x{probe['height']}"
        m["resolution_ok"] = (probe["width"], probe["height"]) == PRESET_RESOLUTION.get(preset)
        video, audio = probe.get("video_seconds"), probe.get("audio_seconds")
        if audio is None and final:
            audio = final.get("audio_seconds")
        m["video_seconds"], m["audio_seconds"] = video, audio
        if video is not None and audio is not None:
            m["av_difference_seconds"] = round(abs(video - audio), 3)
            m["av_ok"] = m["av_difference_seconds"] <= MAX_AV_DIFFERENCE + 1e-9
    return m


def aggregate(results):
    """Totals over topics plus a verdict.

    Verdict: FAIL if any check is False on any topic (a topic without a video
    fails render_ok), else INCOMPLETE if any check has no data, else PASS.
    """
    metrics = [r["metrics"] for r in results]
    scenes = sum(m["scenes"] or 0 for m in metrics)
    flagged = sum(m["flagged"] or 0 for m in metrics)
    metas = [r.get("meta") or {} for r in results]
    outcomes = [m[c] for m in metrics for c in CHECKS]
    if False in outcomes:
        verdict = "FAIL"
    elif None in outcomes:
        verdict = "INCOMPLETE"
    else:
        verdict = "PASS"
    return {"topics": len(results),
            "rendered": sum(1 for m in metrics if m["render_ok"]),
            "scenes": scenes, "flagged": flagged,
            "fallbacks": sum(m["fallbacks"] or 0 for m in metrics),
            "layout_pass_rate": (scenes - flagged) / scenes if scenes else None,
            "turns": sum(meta.get("num_turns") or 0 for meta in metas),
            "cost_usd": round(sum(meta.get("cost_usd") or 0 for meta in metas), 4),
            "seconds": round(sum(r.get("seconds") or 0 for r in results), 1),
            "verdict": verdict}


def _yn(value):
    return {True: "PASS", False: "FAIL", None: "n/a"}[value]


def _num(value, fmt="{:.2f}"):
    return "n/a" if value is None else fmt.format(value)


def metrics_row(r):
    m, meta = r["metrics"], r.get("meta") or {}
    cap = m["captions"]
    captions = f"{_yn(m['captions_ok'])} ({cap['matched']}/{cap['scenes']})" if cap else "n/a"
    layout = ("n/a" if m["layout_pass_rate"] is None else
              f"{m['layout_pass_rate']:.0%} ({m['scenes'] - m['flagged']}/{m['scenes']}), "
              f"fallback {m['fallbacks']}")
    av = f"{_yn(m['av_ok'])} ({_num(m['av_difference_seconds'])} s)"
    return [r["id"], r["lang"], r["preset"], _yn(m["render_ok"]),
            f"{_yn(m['resolution_ok'])} ({m['resolution'] or 'n/a'})",
            _num(m["video_seconds"], "{:.1f} s"), layout, av, captions,
            str(meta.get("num_turns", "n/a")), _num(meta.get("cost_usd"), "${:.2f}"),
            _num(r.get("seconds"), "{:.0f} s")]


METRIC_HEADERS = ["Topic", "Lang", "Preset", "Render", "Resolution", "Video length", "Layout check",
                  "A/V diff (<= 0.3 s)", "Captions match", "Turns", "Cost", "Wall time"]


def render_report(meta, results, agg):
    out = [f"# video-explainer eval report ({meta['timestamp']})\n",
           f"- Model: {meta['model'] or 'claude CLI default'}",
           f"- claude version: {meta['claude_version']}",
           f"- Topics: {', '.join(r['id'] for r in results)}",
           f"- Scratch root: `{meta['scratch_root']}`\n",
           f"## Verdict (automated metrics): {agg['verdict']}\n",
           f"Rendered {agg['rendered']}/{agg['topics']}. Layout-check pass rate "
           f"{_num(agg['layout_pass_rate'], '{:.0%}')} ({agg['scenes'] - agg['flagged']}/{agg['scenes']} scenes "
           f"not flagged), {agg['fallbacks']} fallback scene(s). Turns {agg['turns']}, cost "
           f"${agg['cost_usd']:.2f}, wall time {agg['seconds']:.0f} s.\n",
           "## Per topic\n",
           "| " + " | ".join(METRIC_HEADERS) + " |",
           "|" + "---|" * len(METRIC_HEADERS)]
    for r in results:
        out.append("| " + " | ".join(metrics_row(r)) + " |")
    out.append("\n## Details\n")
    for r in results:
        out.append(f"### {r['id']}\n")
        out.append(f"- Copied files: `{r.get('copied_to') or 'none'}`")
        final = r.get("final") or {}
        for f in final.get("flagged") or []:
            out.append(f"- Flagged {f.get('id')}: {f.get('reason')}")
        if final.get("replaced"):
            out.append(f"- Fallback scenes: {', '.join(final['replaced'])}")
        for n in final.get("notices") or []:
            out.append(f"- Notice: {n}")
        cap = r["metrics"]["captions"]
        if cap:
            out.append(f"- Captions: {cap['matched']}/{cap['scenes']} scenes match, {cap['cues']} cues, "
                       f"similarity {cap['similarity']:.2%}")
        for e in r.get("errors") or []:
            out.append(f"- Error: {e}")
        if r.get("agent_reply"):
            out.append("\nAgent's final reply:\n")
            out.append("\n".join("> " + line for line in r["agent_reply"].strip().splitlines()))
        out.append("")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# Running claude and measuring the output
# --------------------------------------------------------------------------

def build_cmd(claude_exe, model):
    cmd = [claude_exe, "-p"] + ISOLATION_FLAGS + ["--plugin-dir", str(REPO_ROOT),
                                                   "--allowedTools", ",".join(ALLOWED_TOOLS)]
    if model:
        cmd += ["--model", model]
    return cmd


def agent_env():
    env = dict(os.environ)
    env.update(AGENT_ENV)
    return env


def run_claude(cmd, prompt, cwd, timeout):
    """Run claude with the prompt on stdin. Returns (reply, meta). Raises RuntimeError on failure."""
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                              cwd=cwd, timeout=timeout, env=agent_env())
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


class ClaudeError(RuntimeError):
    """claude returned JSON but reported an error; keeps the reply and turns/cost."""

    def __init__(self, message, reply, meta):
        super().__init__(message)
        self.reply, self.meta = reply, meta


def find_final(cwd):
    candidates = []
    for path in Path(cwd).rglob("final.json"):
        try:
            candidates.append((path, path.stat().st_mtime, json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            continue
    return choose_final(candidates)


def load_narrations(out_dir, slug):
    """Storyboard narration: storyboard.json in the output folder, else plan.json."""
    for name in ("storyboard.json", "plan.json"):
        path = out_dir / name
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        scenes = data.get("scenes") or []
        if scenes and all("narration" in s for s in scenes) and data.get("slug", slug) == slug:
            return [s["narration"] for s in scenes], name
    return None, None


def probe_video(video):
    proc = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                           "stream=codec_type,width,height,duration:format=duration", "-of", "json",
                           str(video)], capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        return None
    return parse_probe(json.loads(proc.stdout))


def decodes(video):
    """True when ffmpeg decodes every frame without an error message."""
    proc = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-f", "null", "-"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.returncode == 0 and not proc.stderr.strip()


def load_topics(selected):
    topics = [parse_topic(p.stem, p.read_text(encoding="utf-8")) for p in sorted(TOPICS_DIR.glob("0*.md"))]
    if selected:
        wanted = [s.strip() for s in selected.split(",") if s.strip()]
        topics = [t for t in topics if any(t["id"] == w or t["id"].startswith(w) for w in wanted)]
        if not topics:
            raise SystemExit(f"no topic matches --topics {selected!r}")
    return topics


def process_topic(topic, args, claude_exe, run_dir, scratch_run):
    cwd = scratch_run / topic["id"]
    cwd.mkdir(parents=True, exist_ok=True)
    result = {"id": topic["id"], "lang": topic["lang"], "preset": topic["preset"], "meta": None,
              "agent_reply": None, "final": None, "errors": [], "copied_to": None}
    started = time.monotonic()
    try:
        result["agent_reply"], result["meta"] = run_claude(build_cmd(claude_exe, args.model),
                                                           build_prompt(topic), cwd, args.timeout)
    except ClaudeError as exc:
        result["agent_reply"], result["meta"] = exc.reply or None, exc.meta
        result["errors"].append(str(exc))
    except Exception as exc:  # keep going; measure whatever the agent left behind
        result["errors"].append(str(exc))
    result["seconds"] = round(time.monotonic() - started, 1)

    found = find_final(cwd)
    final = probe = captions = None
    plays = False
    if found is None:
        result["errors"].append(f"no final.json under {cwd}")
    else:
        final_path, _, final = found
        result["final"] = final
        out_dir = final_path.parent
        dest = run_dir / topic["id"]
        dest.mkdir(parents=True, exist_ok=True)
        for name in DELIVERABLES:
            if (out_dir / name).is_file():
                shutil.copy2(out_dir / name, dest / name)
        if (out_dir / "frames").is_dir():
            shutil.copytree(out_dir / "frames", dest / "frames", dirs_exist_ok=True)
        result["copied_to"] = str(dest)
        video, srt = out_dir / "video.mp4", out_dir / "video.srt"
        if video.is_file():
            probe = probe_video(video)
            plays = decodes(video)
        else:
            result["errors"].append("video.mp4 missing")
        narrations, source = load_narrations(out_dir, final.get("slug"))
        if srt.is_file() and narrations:
            captions = caption_match(parse_srt(srt.read_text(encoding="utf-8")), narrations)
            captions["narration_source"] = source
        else:
            result["errors"].append("video.srt or storyboard narration missing")
    if result["agent_reply"]:
        (run_dir / topic["id"]).mkdir(parents=True, exist_ok=True)
        (run_dir / topic["id"] / "agent-reply.md").write_text(result["agent_reply"] + "\n", encoding="utf-8")
    result["metrics"] = topic_metrics(topic["preset"], final, probe, plays, captions)
    return result


def claude_version(claude_exe):
    try:
        proc = subprocess.run([claude_exe, "--version"], capture_output=True, text=True, timeout=60)
        return proc.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the video-explainer eval.")
    parser.add_argument("--topics", help="comma-separated topic ids or number prefixes, e.g. 01,03")
    parser.add_argument("--model", help="model alias or name passed to claude --model (default: CLI default)")
    parser.add_argument("--dry-run", action="store_true", help="print the commands and exit; call nothing")
    parser.add_argument("--workers", type=int, default=1, help="parallel topics (default 1)")
    parser.add_argument("--timeout", type=int, default=1800, help="seconds per topic (default 1800)")
    args = parser.parse_args(argv)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    topics = load_topics(args.topics)
    claude_exe = shutil.which("claude") or "claude"
    scratch_run = SCRATCH_ROOT / timestamp

    if args.dry_run:
        print(f"env: {AGENT_ENV}")
        for t in topics:
            print(f"[{t['id']}] cwd: {scratch_run / t['id']}")
            print(f"[{t['id']}] {' '.join(build_cmd(claude_exe, args.model))}")
            print(f"[{t['id']}] stdin: {build_prompt(t)!r}")
        return 0

    run_dir = RUNS_DIR / timestamp
    run_dir.mkdir(parents=True)
    print(f"Run folder: {run_dir}", flush=True)
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(process_topic, t, args, claude_exe, run_dir, scratch_run) for t in topics]
        results = []
        for future in futures:
            r = future.result()
            results.append(r)
            print(f"done {r['id']} in {r['seconds']:.0f} s: render {_yn(r['metrics']['render_ok'])}"
                  + (f" (errors: {len(r['errors'])})" if r["errors"] else ""), flush=True)

    agg = aggregate(results)
    meta = {"timestamp": timestamp, "model": args.model, "claude_version": claude_version(claude_exe),
            "isolation_flags": ISOLATION_FLAGS, "allowed_tools": ALLOWED_TOOLS, "env": AGENT_ENV,
            "scratch_root": str(scratch_run)}
    (run_dir / "report.md").write_text(render_report(meta, results, agg), encoding="utf-8")
    (run_dir / "report.json").write_text(
        json.dumps({"meta": meta, "aggregate": agg, "topics": results}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(f"Verdict: {agg['verdict']}")
    print(f"Report: {run_dir / 'report.md'}")
    for r in results:
        for e in r["errors"]:
            print(f"error [{r['id']}]: {e}", file=sys.stderr)
    return {"PASS": 0, "FAIL": 1, "INCOMPLETE": 2}[agg["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
