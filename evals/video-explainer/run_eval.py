#!/usr/bin/env python3
"""Run the video-explainer eval: four topics, with-skill arm plus a baseline arm on the zh-TW topics.

Usage:
    python evals/video-explainer/run_eval.py [--topics 01,03] [--model MODEL]
                                             [--dry-run] [--no-baseline]
                                             [--seed SEED] [--workers N]
                                             [--timeout SECONDS]

For each topic in topics/ the harness asks one agent (claude -p with
--plugin-dir <repo root>) for the topic's Request line, plus "Use the <preset>
output preset.", with the storyboard pre-approved, from a scratch folder
outside the repo. The zh-TW topics also get a baseline agent: the same prompt
and flags without --plugin-dir, from its own scratch folder.
It then measures what the agent produced:
render success (ffprobe + a full decode), resolution against the preset,
layout-check pass rate (scenes not flagged / total; fallback count),
audio/video length difference (pass at 0.3 s or less), captions match
narration (SRT cue text vs storyboard narration, normalized), the storyboard
mode with scene-count and video-length checks against the skill's MODES, turns,
cost and wall time. The baseline video is the newest .mp4 under its scratch
folder; metrics that need a storyboard or SRT are n/a for it. The verdict
covers the with-skill arm only.
The deliverables, the report and a blind review page (review.html) go to
evals/video-explainer/runs/<timestamp>/.

See evals/video-explainer/README.md. Python standard library only.
Exit code: 0 = PASS, 1 = FAIL, 2 = incomplete/error.
"""

import argparse
import difflib
import html
import importlib.util
import json
import os
import random
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

# Topics in these languages also run the baseline arm (the same request without the plugin).
BASELINE_LANGS = ("zh-TW",)
# The mode names a topic may state. The ranges are read from the skill (load_modes).
MODE_NAMES = ("quick", "standard", "deep")
ARMS = ("with-skill", "baseline")
DEFAULT_TIMEOUT = 3600  # seconds per arm; a deep-mode video can take 60+ minutes

PRESET_RESOLUTION = {"explainer": (1280, 720), "youtube": (1920, 1080), "short": (1080, 1920)}
MAX_AV_DIFFERENCE = 0.3
DELIVERABLES = ("video.mp4", "video.srt", "script.md", "storyboard.json", "scenes.py",
                "plan.json", "preview.json", "final.json")
CHECKS = ("render_ok", "resolution_ok", "av_ok", "captions_ok")


# --------------------------------------------------------------------------
# Pure logic (unit-tested in test_run_eval.py)
# --------------------------------------------------------------------------

def _section(text, title):
    m = re.search(rf"^## {re.escape(title)}[ \t]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else None


def parse_topic(topic_id, text):
    """Read language, output preset, mode, request, the Source section and the
    "Viewer should understand" bullets from a topic file. baseline is True for
    the languages in BASELINE_LANGS."""
    lang = re.search(r"^- Language:\s*(\S+)", text, re.M)
    preset = re.search(r"^- Output preset:\s*`?([\w-]+)`?", text, re.M)
    mode = re.search(r"^- Mode:\s*`?([\w-]+)`?", text, re.M)
    request = re.search(r"^- Request:[ \t]*(\S.*?)[ \t]*$", text, re.M)
    source = _section(text, "Source")
    if not (lang and preset and mode and request and source):
        raise ValueError(f"topic {topic_id}: missing Language, Output preset, Mode, Request or Source")
    if mode.group(1) not in MODE_NAMES:
        raise ValueError(f"topic {topic_id}: unknown mode {mode.group(1)!r}; known: {', '.join(MODE_NAMES)}")
    points = [line[2:].strip() for line in (_section(text, "Viewer should understand") or "").splitlines()
              if line.startswith("- ")]
    return {"id": topic_id, "lang": lang.group(1), "preset": preset.group(1), "mode": mode.group(1),
            "request": request.group(1), "source": source, "points": points,
            "baseline": lang.group(1) in BASELINE_LANGS}


def build_prompt(topic):
    """The same text goes to both arms: request, preset, pre-approval, Source."""
    return (f"{topic['request'].strip()} Use the {topic['preset']} output preset. "
            "The storyboard is pre-approved: do not wait for confirmation; render it. "
            "Any model download the plan lists is approved.\n\n"
            f"{topic['source'].strip()}\n")


def find_newest_mp4(root):
    """Newest non-empty *.mp4 anywhere under root, or None. Manim's partial movie
    files (partial_movie_files folders) are not deliverables and are skipped."""
    best = None
    for path in Path(root).rglob("*.mp4"):
        if "partial_movie_files" in path.parts:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        if stat.st_size > 0 and (best is None or stat.st_mtime > best[0]):
            best = (stat.st_mtime, path)
    return best[1] if best else None


def baseline_metrics(preset, probe, plays):
    """Metrics for the baseline arm, which has no final.json, storyboard or SRT.
    Render success, resolution and A/V difference apply; the rest stay None (n/a).
    A video file that exists is treated as the 'final' so topic_metrics measures it."""
    return topic_metrics(preset, {"ok": True} if probe else None, probe, plays, None)


def load_modes():
    """(MODES, DEFAULT_MODE) read from the skill's make_video.py, so the ranges are
    not copied here. ({}, "standard") when the module cannot be loaded."""
    path = REPO_ROOT / "skills" / "video-explainer" / "scripts" / "make_video.py"
    scripts = str(path.parent)
    keep_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    sys.path.insert(0, scripts)
    try:
        spec = importlib.util.spec_from_file_location("make_video_for_eval_modes", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return dict(module.MODES), module.DEFAULT_MODE
    except Exception:
        return {}, "standard"
    finally:
        sys.dont_write_bytecode = keep_bytecode
        if scripts in sys.path:
            sys.path.remove(scripts)


def read_board_mode(out_dir, default):
    """Mode the agent's storyboard asked for: storyboard.json's "mode" (default when a
    storyboard has none), else plan.json's mode name. None when neither file exists."""
    for name in ("storyboard.json", "plan.json"):
        try:
            data = json.loads((Path(out_dir) / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        mode = data.get("mode")
        if isinstance(mode, dict):
            mode = mode.get("name")
        if mode or name == "storyboard.json":
            return mode or default
    return None


def mode_metrics(requested, mode, scenes, video_seconds, modes):
    """Mode report for the with-skill arm (reported, not gated): the storyboard mode,
    whether it is the topic's mode, and whether the scene count and the final video
    length fall inside that mode's ranges. A check is None when its data is missing."""
    info = modes.get(mode) if mode else None
    m = {"requested": requested, "mode": mode,
         "matches_request": None if mode is None else mode == requested,
         "scenes": scenes, "scenes_range": info["scenes"] if info else None, "scenes_in_range": None,
         "video_seconds": video_seconds, "seconds_range": info["target_seconds"] if info else None,
         "seconds_in_range": None}
    if info and scenes is not None:
        m["scenes_in_range"] = info["scenes"][0] <= scenes <= info["scenes"][1]
    if info and video_seconds is not None:
        m["seconds_in_range"] = info["target_seconds"][0] <= video_seconds <= info["target_seconds"][1]
    return m


def mode_cells(m):
    """Report cells: storyboard mode, scene count check, length check."""
    if not m or m["mode"] is None:
        return ["n/a", "n/a", "n/a"]

    def cell(inside, text, rng, unit=""):
        if inside is None:
            return "n/a" if rng is None or text is None else text
        return f"{'yes' if inside else 'no'}: {text} ({rng[0]}-{rng[1]}{unit})"

    scenes = None if m["scenes"] is None else str(m["scenes"])
    seconds = None if m["video_seconds"] is None else f"{m['video_seconds']:.1f} s"
    return [m["mode"], cell(m["scenes_in_range"], scenes, m["scenes_range"]),
            cell(m["seconds_in_range"], seconds, m["seconds_range"], " s")]


def judge_order(seed, topic_id):
    """Random but repeatable arm order for one topic: (shown as A, shown as B)."""
    rng = random.Random(f"{seed}:{topic_id}")
    arms = list(ARMS)
    rng.shuffle(arms)
    return tuple(arms)


def ab_orders(topic_ids, seed):
    return {tid: judge_order(seed, tid) for tid in topic_ids}


def ab_key(results, orders):
    """{topic: {"A": arm, "B": arm}} for the topics that have a baseline. Only for report.json."""
    return {r["id"]: dict(zip(("A", "B"), orders[r["id"]])) for r in results if r.get("baseline")}


def review_plan(results, orders):
    """Per topic: the videos to show with their blind labels. A topic with a baseline gets
    A and B in the seeded order; one without gets a single unlabeled video. source is the
    copied video path (or None). No arm names in the result."""
    plan = []
    for r in results:
        base = r.get("baseline")
        if base:
            sources = {"with-skill": r.get("video"), "baseline": base.get("video")}
            videos = [{"label": label, "source": sources[arm]}
                      for label, arm in zip(("A", "B"), orders[r["id"]])]
        else:
            videos = [{"label": None, "source": r.get("video")}]
        plan.append({"id": r["id"], "lang": r["lang"], "points": r.get("points") or [],
                     "ab": bool(base), "videos": videos})
    return plan


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
    Only the with-skill results gate. The baseline arm (r["baseline"]) is summed
    separately under "baseline" and never changes the verdict.
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
            "baseline": baseline_totals([r["baseline"] for r in results if r.get("baseline")]),
            "verdict": verdict}


def baseline_totals(baselines):
    """Totals over the baseline arm's results; None when there is no baseline run."""
    if not baselines:
        return None
    metas = [b.get("meta") or {} for b in baselines]
    return {"topics": len(baselines),
            "rendered": sum(1 for b in baselines if b["metrics"]["render_ok"]),
            "turns": sum(meta.get("num_turns") or 0 for meta in metas),
            "cost_usd": round(sum(meta.get("cost_usd") or 0 for meta in metas), 4),
            "seconds": round(sum(b.get("seconds") or 0 for b in baselines), 1)}


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
    av = ("n/a" if m["av_ok"] is None else
          f"{_yn(m['av_ok'])} ({_num(m['av_difference_seconds'])} s)")
    return [r["id"], r["lang"], r["preset"], _yn(m["render_ok"]),
            f"{_yn(m['resolution_ok'])} ({m['resolution'] or 'n/a'})",
            _num(m["video_seconds"], "{:.1f} s")] + mode_cells(r.get("mode_metrics")) + [
            layout, av, captions,
            str(meta.get("num_turns", "n/a")), _num(meta.get("cost_usd"), "${:.2f}"),
            _num(r.get("seconds"), "{:.0f} s")]


METRIC_HEADERS = ["Topic", "Lang", "Preset", "Render", "Resolution", "Video length",
                  "Storyboard mode", "Scenes in mode range", "Length in mode range", "Layout check",
                  "A/V diff (<= 0.3 s)", "Captions match", "Turns", "Cost", "Wall time"]


def _table(rows):
    return (["| " + " | ".join(METRIC_HEADERS) + " |", "|" + "---|" * len(METRIC_HEADERS)]
            + ["| " + " | ".join(row) + " |" for row in rows])


def _arm_details(out, r):
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


def render_report(meta, results, agg):
    out = [f"# video-explainer eval report ({meta['timestamp']})\n",
           f"- Model: {meta['model'] or 'claude CLI default'}",
           f"- claude version: {meta['claude_version']}",
           f"- Topics: {', '.join(r['id'] for r in results)}",
           f"- Scratch root: `{meta['scratch_root']}`",
           f"- Review page: `{meta.get('review') or 'none'}` (A/B key in report.json only; "
           f"seed {meta.get('seed')})",
           "- Video-length and scene-count ranges come from the skill's MODES; they are reported, not gated.\n",
           f"## Verdict (automated metrics, with-skill arm): {agg['verdict']}\n",
           f"Rendered {agg['rendered']}/{agg['topics']}. Layout-check pass rate "
           f"{_num(agg['layout_pass_rate'], '{:.0%}')} ({agg['scenes'] - agg['flagged']}/{agg['scenes']} scenes "
           f"not flagged), {agg['fallbacks']} fallback scene(s). With-skill arm: turns {agg['turns']}, cost "
           f"${agg['cost_usd']:.2f}, wall time {agg['seconds']:.0f} s.\n",
           "## Per topic (with-skill arm, gated)\n"] + _table([metrics_row(r) for r in results])
    baselines = [dict(b, id=r["id"]) for r in results for b in [r.get("baseline")] if b]
    if baselines:
        base = agg["baseline"]
        out += ["\n## Baseline arm (reported, does not gate)\n",
                "Same request without the plugin. Captions, layout check and mode checks are n/a "
                "(no storyboard or SRT is expected); a missing one is not a failure.\n",
                f"Rendered {base['rendered']}/{base['topics']}. Turns {base['turns']}, cost "
                f"${base['cost_usd']:.2f}, wall time {base['seconds']:.0f} s.\n"]
        out += _table([metrics_row(b) for b in baselines])
    out.append("\n## Details\n")
    for r in results:
        out.append(f"### {r['id']}\n")
        out.append(f"- Mode requested by the topic: {r['mode_metrics']['requested']}"
                   if r.get("mode_metrics") else "- Mode: n/a")
        out.append("\n#### With-skill arm\n")
        _arm_details(out, r)
        if r.get("baseline"):
            out.append("\n#### Baseline arm\n")
            _arm_details(out, r["baseline"])
        out.append("")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# Blind review page (self-contained: no external scripts, ratings kept in localStorage)
# --------------------------------------------------------------------------

REVIEW_CSS = """
body{font-family:system-ui,sans-serif;margin:1rem;background:#f4f4f4;color:#111;line-height:1.6}
section{background:#fff;border:1px solid #ccc;border-radius:6px;padding:1rem;margin-bottom:2rem}
.pair{display:grid;grid-template-columns:repeat(auto-fit,minmax(24rem,1fr));gap:1rem;align-items:start}
.video{border:1px solid #bbb;border-radius:4px;padding:.6rem;background:#fafafa}
video{width:100%;max-height:70vh;background:#000}
h3{margin:.3rem 0}.missing{color:#a00}
.axis{margin:.4rem 0}.axis label{margin-right:.8rem;white-space:nowrap}
textarea{width:100%;box-sizing:border-box}
#md{height:14rem;font-family:ui-monospace,monospace}
"""

# Rating instructions, Traditional Chinese (Taiwan), English axis names in parentheses.
REVIEW_INTRO = (
    "<p>每個主題請看影片，再評分。有兩支影片的主題，A 和 B 的順序是隨機的，"
    "對照表只在 report.json。評分完成前，請不要打開 run 資料夾裡的其他檔案。</p>"
    "<p>每支影片各打兩個分數，各為 1 到 5 分（1 = 很差，5 = 很好）：</p>"
    "<ul><li><strong>理解（Understanding）</strong>：看完這支影片後，"
    "你理解了該主題「觀眾應該理解」的幾個重點。</li>"
    "<li><strong>呈現（Presentation）</strong>：畫面連貫性（continuity）、動態（motion）、"
    "旁白自然度（narration naturalness）、節奏（pacing）。</li></ul>"
    "<p>有兩支影片的主題，最後選出較好的一支（A、B 或平手 tie），可以寫備註。"
    "全部完成後按最下面的按鈕，產生 Markdown 表格，貼到 RESULTS.md。"
    "分數會暫存在這個瀏覽器（localStorage），重新整理不會消失。</p>"
)

# Plain script (no f-string): reads the form, keeps a draft in localStorage, builds the Markdown table.
REVIEW_JS = """
(function () {
  var KEY = 'video-eval-review-__STAMP__';
  var form = document.getElementById('review');
  function load() {
    try { return JSON.parse(window.localStorage.getItem(KEY) || '{}'); } catch (e) { return {}; }
  }
  function save() {
    var data = {};
    form.querySelectorAll('input[type=radio]:checked').forEach(function (el) { data[el.name] = el.value; });
    form.querySelectorAll('textarea[data-note]').forEach(function (el) { data[el.name] = el.value; });
    try { window.localStorage.setItem(KEY, JSON.stringify(data)); } catch (e) { /* storage unavailable */ }
  }
  function restore() {
    var data = load();
    form.querySelectorAll('input[type=radio]').forEach(function (el) { el.checked = data[el.name] === el.value; });
    form.querySelectorAll('textarea[data-note]').forEach(function (el) { el.value = data[el.name] || ''; });
  }
  function checked(name) {
    var el = form.querySelector('input[name="' + name + '"]:checked');
    return el ? el.value : '';
  }
  function cell(text) { return String(text).replace(/\\|/g, '\\\\|').replace(/\\s*\\n\\s*/g, ' '); }
  function build() {
    var rows = ['| 主題 | 影片 | 理解 (1-5) | 呈現 (1-5) | 較好 | 備註 |', '|---|---|---|---|---|---|'];
    form.querySelectorAll('section[data-topic]').forEach(function (sec) {
      var topic = sec.getAttribute('data-topic');
      var first = true;
      sec.querySelectorAll('.video').forEach(function (v) {
        var label = v.getAttribute('data-label');
        var base = topic + '-' + (label || 'V');
        var better = '', note = '';
        if (first) {
          better = checked(topic + '-better');
          var n = sec.querySelector('textarea[data-note]');
          note = n ? n.value : '';
        }
        first = false;
        rows.push('| ' + [topic, label || '-', checked(base + '-understanding'), checked(base + '-presentation'),
                          better, cell(note)].join(' | ') + ' |');
      });
    });
    return rows.join('\\n');
  }
  form.addEventListener('change', save);
  form.addEventListener('input', save);
  restore();
  document.getElementById('make-md').addEventListener('click', function () {
    var out = document.getElementById('md');
    out.value = build();
    out.select();
    try { if (navigator.clipboard) { navigator.clipboard.writeText(out.value); } } catch (e) { /* copy by hand */ }
  });
})();
"""


def _radios(name, axis, values):
    return "".join(f'<label><input type="radio" name="{html.escape(name)}" data-axis="{axis}" '
                   f'value="{html.escape(v)}">{html.escape(t)}</label>' for v, t in values)


def render_review(entries, timestamp):
    """Blind review page, Traditional Chinese (Taiwan). entries: [{"id", "lang", "points",
    "ab", "videos": [{"label": "A"|"B"|None, "src": relative path|None}]}]. Only A and B
    labels appear, never arm names or the key. Per video: a player and two 1-5 ratings
    (理解, 呈現). Per pair topic: better A/B/tie and a notes field. One button builds the
    Markdown table."""
    esc = html.escape
    scale = [(str(n), str(n)) for n in range(1, 6)]
    out = ["<!doctype html>", '<html lang="zh-TW"><head><meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width, initial-scale=1">',
           f"<title>video-explainer 影片評分 {esc(timestamp)}</title><style>{REVIEW_CSS}</style></head><body>",
           f"<h1>video-explainer 影片評分（{esc(timestamp)}）</h1>", REVIEW_INTRO, '<form id="review">']
    for e in entries:
        out.append(f'<section data-topic="{esc(e["id"])}"><h2>{esc(e["id"])}（{esc(e["lang"])}）</h2>')
        if e["points"]:
            out.append("<p>觀眾應該理解（Viewer should understand）：</p><ul>"
                       + "".join(f"<li>{esc(p)}</li>" for p in e["points"]) + "</ul>")
        out.append('<div class="pair">')
        for v in e["videos"]:
            label = v["label"]
            title = f"影片 {label}" if label else "影片"
            base = f"{e['id']}-{label or 'V'}"
            player = (f'<video controls preload="metadata" src="{esc(v["src"])}"></video>' if v["src"]
                      else '<p class="missing">沒有影片</p>')
            out.append(f'<div class="video" data-label="{esc(label or "")}"><h3>{title}</h3>{player}'
                       f'<div class="axis">理解（Understanding）：{_radios(base + "-understanding", "understanding", scale)}</div>'
                       f'<div class="axis">呈現（Presentation）：{_radios(base + "-presentation", "presentation", scale)}</div>'
                       "</div>")
        out.append("</div>")
        if e["ab"]:
            out.append('<div class="axis">較好的影片（Better）：'
                       + _radios(f"{e['id']}-better", "better", [("A", "A"), ("B", "B"), ("tie", "平手")])
                       + "</div>"
                       f'<p>備註（Notes）：<textarea data-note="1" name="{esc(e["id"])}-notes" rows="3"></textarea></p>')
        out.append("</section>")
    out.append('<p><button type="button" id="make-md">產生 Markdown 表格（Build Markdown table）</button></p>'
               '<textarea id="md" readonly placeholder="按上面的按鈕，表格會出現在這裡"></textarea>')
    out.append("</form>")
    out.append("<script>" + REVIEW_JS.replace("__STAMP__", re.sub(r"[^\w-]", "", timestamp)) + "</script>")
    out.append("</body></html>")
    return "\n".join(out) + "\n"


def build_review(results, orders, run_dir, timestamp):
    """Copy each video under a neutral name (review/<topic>-A.mp4, -B.mp4, or <topic>.mp4),
    write run_dir/review.html and return its path. Nothing in the page or the file names
    says which arm a video came from."""
    review_dir = Path(run_dir) / "review"
    entries = []
    for topic in review_plan(results, orders):
        videos = []
        for v in topic["videos"]:
            src = None
            if v["source"] and Path(v["source"]).is_file():
                review_dir.mkdir(exist_ok=True)
                name = f"{topic['id']}-{v['label']}.mp4" if v["label"] else f"{topic['id']}.mp4"
                shutil.copy2(v["source"], review_dir / name)
                src = f"review/{name}"
            videos.append({"label": v["label"], "src": src})
        entries.append({**topic, "videos": videos})
    page = Path(run_dir) / "review.html"
    page.write_text(render_review(entries, timestamp), encoding="utf-8")
    return page


# --------------------------------------------------------------------------
# Running claude and measuring the output
# --------------------------------------------------------------------------

def build_cmd(claude_exe, model, arm="with-skill"):
    """claude -p command. The baseline arm is the same without --plugin-dir."""
    cmd = [claude_exe, "-p"] + ISOLATION_FLAGS
    if arm == "with-skill":
        cmd += ["--plugin-dir", str(REPO_ROOT)]
    cmd += ["--allowedTools", ",".join(ALLOWED_TOOLS)]
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


def run_arm(topic, arm, args, claude_exe, cwd):
    """Run one arm's agent in cwd. Returns the result skeleton (reply, meta, seconds, errors)."""
    cwd.mkdir(parents=True, exist_ok=True)
    result = {"id": topic["id"], "arm": arm, "lang": topic["lang"], "preset": topic["preset"],
              "meta": None, "agent_reply": None, "final": None, "errors": [], "copied_to": None,
              "video": None}
    started = time.monotonic()
    try:
        result["agent_reply"], result["meta"] = run_claude(build_cmd(claude_exe, args.model, arm),
                                                           build_prompt(topic), cwd, args.timeout)
    except ClaudeError as exc:
        result["agent_reply"], result["meta"] = exc.reply or None, exc.meta
        result["errors"].append(str(exc))
    except Exception as exc:  # keep going; measure whatever the agent left behind
        result["errors"].append(str(exc))
    result["seconds"] = round(time.monotonic() - started, 1)
    return result


def process_baseline(topic, args, claude_exe, run_dir, scratch_run):
    """Baseline arm: the same request without the plugin, from <scratch>/<topic>-baseline/.
    Finds the newest .mp4 anywhere under that folder and measures what applies to a bare
    video. A missing SRT or storyboard is n/a, not an error."""
    result = run_arm(topic, "baseline", args, claude_exe, scratch_run / f"{topic['id']}-baseline")
    dest = run_dir / topic["id"] / "baseline"
    found = find_newest_mp4(scratch_run / f"{topic['id']}-baseline")
    probe, plays = None, False
    if found is None:
        result["errors"].append(f"no .mp4 under {scratch_run / (topic['id'] + '-baseline')}")
    else:
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(found, dest / "video.mp4")
        result["video"], result["copied_to"] = str(dest / "video.mp4"), str(dest)
        result["source_video"] = str(found)
        probe = probe_video(found)
        plays = decodes(found)
    if result["agent_reply"]:
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "agent-reply.md").write_text(result["agent_reply"] + "\n", encoding="utf-8")
    result["metrics"] = baseline_metrics(topic["preset"], probe, plays)
    return result


def process_topic(topic, args, claude_exe, run_dir, scratch_run, modes=({}, "standard")):
    """With-skill arm: copy the deliverables and measure them, including the mode report."""
    cwd = scratch_run / topic["id"]
    result = run_arm(topic, "with-skill", args, claude_exe, cwd)
    result.update({"mode": topic["mode"], "points": topic["points"], "baseline": None, "mode_metrics": None})

    found = find_final(cwd)
    final = probe = captions = board_mode = None
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
            result["video"] = str(dest / "video.mp4")
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
        board_mode = read_board_mode(out_dir, modes[1])
    if result["agent_reply"]:
        (run_dir / topic["id"]).mkdir(parents=True, exist_ok=True)
        (run_dir / topic["id"] / "agent-reply.md").write_text(result["agent_reply"] + "\n", encoding="utf-8")
    result["metrics"] = topic_metrics(topic["preset"], final, probe, plays, captions)
    m = result["metrics"]
    result["mode_metrics"] = mode_metrics(topic["mode"], board_mode, m["scenes"], m["video_seconds"], modes[0])
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
    parser.add_argument("--no-baseline", action="store_true",
                        help="skip the baseline arm (the zh-TW topics); with-skill arm only")
    parser.add_argument("--seed", default=None, help="seed for the review page A/B order (default: run timestamp)")
    parser.add_argument("--workers", type=int, default=1, help="parallel agent runs (default 1)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"seconds per agent run, each arm (default {DEFAULT_TIMEOUT}; deep mode can take 60+ min)")
    args = parser.parse_args(argv)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    seed = args.seed or timestamp
    topics = load_topics(args.topics)
    claude_exe = shutil.which("claude") or "claude"
    scratch_run = SCRATCH_ROOT / timestamp

    def has_baseline(t):
        return t["baseline"] and not args.no_baseline

    if args.dry_run:
        print(f"env: {AGENT_ENV}")
        print(f"timeout: {args.timeout} s per arm; review page A/B seed: {seed}")
        for t in topics:
            print(f"[{t['id']}] mode: {t['mode']}")
            print(f"[{t['id']}] with-skill cwd: {scratch_run / t['id']}")
            print(f"[{t['id']}] with-skill: {' '.join(build_cmd(claude_exe, args.model, 'with-skill'))}")
            print(f"[{t['id']}] with-skill stdin: {build_prompt(t)!r}")
            if has_baseline(t):
                print(f"[{t['id']}] baseline cwd: {scratch_run / (t['id'] + '-baseline')}")
                print(f"[{t['id']}] baseline: {' '.join(build_cmd(claude_exe, args.model, 'baseline'))}")
                print(f"[{t['id']}] baseline stdin: {build_prompt(t)!r}")
            else:
                print(f"[{t['id']}] baseline: none")
        return 0

    run_dir = RUNS_DIR / timestamp
    run_dir.mkdir(parents=True)
    print(f"Run folder: {run_dir}", flush=True)
    modes = load_modes()
    if not modes[0]:
        print("warning: could not read MODES from make_video.py; mode range checks will be n/a", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [(t, pool.submit(process_topic, t, args, claude_exe, run_dir, scratch_run, modes),
                    pool.submit(process_baseline, t, args, claude_exe, run_dir, scratch_run)
                    if has_baseline(t) else None) for t in topics]
        results = []
        for _, future, base_future in futures:
            r = future.result()
            r["baseline"] = base_future.result() if base_future else None
            results.append(r)
            print(f"done {r['id']} with-skill in {r['seconds']:.0f} s: render {_yn(r['metrics']['render_ok'])}"
                  + (f" (errors: {len(r['errors'])})" if r["errors"] else ""), flush=True)
            if r["baseline"]:
                b = r["baseline"]
                print(f"done {r['id']} baseline in {b['seconds']:.0f} s: render {_yn(b['metrics']['render_ok'])}"
                      + (f" (errors: {len(b['errors'])})" if b["errors"] else ""), flush=True)

    orders = ab_orders([r["id"] for r in results], seed)
    review = build_review(results, orders, run_dir, timestamp)
    agg = aggregate(results)
    meta = {"timestamp": timestamp, "model": args.model, "claude_version": claude_version(claude_exe),
            "isolation_flags": ISOLATION_FLAGS, "allowed_tools": ALLOWED_TOOLS, "env": AGENT_ENV,
            "scratch_root": str(scratch_run), "timeout_seconds": args.timeout, "seed": seed,
            "review": str(review), "modes": modes[0]}
    (run_dir / "report.md").write_text(render_report(meta, results, agg), encoding="utf-8")
    (run_dir / "report.json").write_text(
        json.dumps({"meta": meta, "aggregate": agg, "ab_key": ab_key(results, orders), "topics": results},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Verdict (with-skill arm): {agg['verdict']}")
    print(f"Report: {run_dir / 'report.md'}")
    print(f"Review: {review}")
    for r in results:
        for arm in (r, r["baseline"]):
            for e in (arm or {}).get("errors") or []:
                print(f"error [{r['id']} {arm['arm']}]: {e}", file=sys.stderr)
    return {"PASS": 0, "FAIL": 1, "INCOMPLETE": 2}[agg["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
