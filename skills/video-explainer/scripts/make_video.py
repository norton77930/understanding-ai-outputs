# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "manim>=0.21,<0.22",
# ]
# ///
"""Orchestrator for the video-explainer skill: storyboard -> video.

Usage:
    python make_video.py plan STORYBOARD.json [--out DIR]
    uv run make_video.py preview STORYBOARD.json SCENES.py [--out DIR]
    uv run make_video.py final STORYBOARD.json SCENES.py [--out DIR]

Each command prints one JSON object to stdout. Exit codes:
    0  success
    1  a check failed (invalid storyboard, missing scene function)
    2  environment or runtime error (missing tool, render failure)

`plan` needs only the Python standard library. `preview` and `final` need
ffmpeg/ffprobe on PATH and ManimCE, which `uv run` installs from the inline
dependency block above. Heavy imports happen only inside those commands.

Default output folder: out/video-explainer/<slug>/ relative to the current
working directory.
"""

import argparse
import contextlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import textwrap
import time
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Silence appended after each scene's speech. The scene length is
# speech + PAD_SECONDS, so the picture can settle before the next scene.
PAD_SECONDS = 0.35

# Speech rates measured in the prototype (natural explainer pace).
EN_WORDS_PER_SECOND = 168 / 60
ZH_HANZI_PER_SECOND = 3.05

# Output presets. Add a row to add a preset (#19: youtube, short).
#   preview_short_side: pixel size of the shorter frame side in `preview`.
PRESETS = {
    "explainer": {
        "width": 1280, "height": 720, "fps": 30, "aspect": "16:9",
        "target_seconds": [30, 120], "burn_captions": False,
        "preview_short_side": 480, "preview_fps": 15,
    },
}
DEFAULT_PRESET = "explainer"

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
HANZI_RE = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
LATIN_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['’.-][A-Za-z0-9]+)*")
SENTENCE_RE = re.compile(r"[^.!?。！？]+[.!?。！？]*")

CAPTION_MAX_CHARS = {"zh": 16, "default": 42}


class CheckFailed(Exception):
    """Input problem the agent must fix. Exit 1."""

    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = errors


class RuntimeFailure(Exception):
    """Environment or runtime problem. Exit 2."""


# ---------------------------------------------------------------- estimates

def text_units(text):
    """Count hanzi and Latin words (digits count as words)."""
    hanzi = len(HANZI_RE.findall(text))
    words = len(LATIN_WORD_RE.findall(HANZI_RE.sub(" ", text)))
    return {"hanzi": hanzi, "words": words}


def estimate_speech_seconds(text):
    units = text_units(text)
    return units["hanzi"] / ZH_HANZI_PER_SECOND + units["words"] / EN_WORDS_PER_SECOND


def estimate_render_seconds(total_seconds, preset):
    """Rough wall time for one render, measured on a 20-thread Windows CPU
    (16 s fixture: preview 15 s, final 26 s). Busy scenes take longer."""
    pixels = preset["width"] * preset["height"]
    short = preset["preview_short_side"]
    preview_pixels = pixels * (short / min(preset["width"], preset["height"])) ** 2
    preview_frames = total_seconds * preset["preview_fps"]
    final_frames = total_seconds * preset["fps"]
    # Startup plus per-frame cost scaled by pixel count (calibrated at 720p30).
    per_frame_720p = 0.04
    preview = 10 + preview_frames * per_frame_720p * preview_pixels / 921600
    final = 10 + final_frames * per_frame_720p * pixels / 921600
    return {"preview": round(preview, 1), "final": round(final, 1)}


def is_zh(lang):
    return lang.lower().startswith("zh")


def split_captions(text, lang):
    """Split narration into caption lines: sentences first, then wrap."""
    limit = CAPTION_MAX_CHARS["zh" if is_zh(lang) else "default"]
    lines = []
    for sentence in SENTENCE_RE.findall(text.strip()):
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) <= limit:
            lines.append(sentence)
        elif is_zh(lang):
            lines.extend(_wrap_zh(sentence, limit))
        else:
            lines.extend(textwrap.wrap(sentence, limit))
    return lines


def _wrap_zh(sentence, limit):
    parts = re.findall(r"[^，、；：,;:]+[，、；：,;:]?", sentence)
    lines, current = [], ""
    for part in parts:
        if len(current) + len(part) <= limit:
            current += part
            continue
        if current:
            lines.append(current)
        while len(part) > limit:
            lines.append(part[:limit])
            part = part[limit:]
        current = part
    if current:
        lines.append(current)
    return lines


# ---------------------------------------------------------------- engines

class SilentEngine:
    """Test-only narration engine: silence sized from the text-length estimate.

    Engine interface (#18 adds Kokoro and edge-tts with the same shape):
        name: str            registry key used in the storyboard "engine" field
        default_voice: str | None
        extension: str       file type that synthesize() writes
        synthesize(text, lang, voice, path) -> None   write speech audio to path
    The orchestrator normalizes, pads and measures whatever the engine writes.
    """

    name = "silent"
    default_voice = None
    extension = "wav"
    sample_rate = 48000

    def synthesize(self, text, lang, voice, path):
        frames = int(round(estimate_speech_seconds(text) * self.sample_rate))
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.sample_rate)
            w.writeframes(b"\x00\x00" * frames)


ENGINES = {"silent": SilentEngine()}

# Default engine per language prefix when the storyboard has "engine": null.
# Empty in this version: only the silent engine exists (#18 fills this in).
DEFAULT_ENGINES = {}


def select_engine(board):
    """Return (engine, voice, notices). Assumes validate() already passed."""
    notices = []
    choice = board.get("engine")
    if isinstance(choice, dict):
        name, voice = choice.get("name"), choice.get("voice")
    else:
        name, voice = choice, None
    if name is None:
        prefix = board["lang"].lower().split("-")[0]
        name = DEFAULT_ENGINES.get(board["lang"].lower(), DEFAULT_ENGINES.get(prefix))
        if name is None:
            name = "silent"
            notices.append(f"No narration engine is available for '{board['lang']}' yet; "
                           "using the silent engine (no speech).")
    engine = ENGINES[name]
    return engine, voice or engine.default_voice, notices


# ---------------------------------------------------------------- storyboard

def load_storyboard(path):
    try:
        board = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise CheckFailed([f"cannot read storyboard: {exc}"])
    except json.JSONDecodeError as exc:
        raise CheckFailed([f"storyboard is not valid JSON: {exc}"])
    validate(board)
    return board


def validate(board):
    errors = []
    if not isinstance(board, dict):
        raise CheckFailed(["storyboard must be a JSON object"])
    slug = board.get("slug")
    if not isinstance(slug, str) or not SLUG_RE.match(slug):
        errors.append(f"slug {slug!r} must be lower-case letters, digits and single hyphens")
    lang = board.get("lang")
    if not isinstance(lang, str) or not lang.strip():
        errors.append("lang must be a non-empty language tag such as 'en' or 'zh-TW'")
    preset = board.get("preset", DEFAULT_PRESET)
    if preset not in PRESETS:
        errors.append(f"unknown preset {preset!r}; known presets: {', '.join(PRESETS)}")
    engine = board.get("engine")
    name = engine.get("name") if isinstance(engine, dict) else engine
    if name is not None and name not in ENGINES:
        errors.append(f"unknown engine {name!r}; known engines: {', '.join(ENGINES)}")
    scenes = board.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        errors.append("scenes must be a non-empty list")
        scenes = []
    seen = set()
    for i, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            errors.append(f"scene #{i + 1} must be an object with id and narration")
            continue
        sid = scene.get("id")
        if not isinstance(sid, str) or not sid.strip():
            errors.append(f"scene #{i + 1} has no id")
        elif sid in seen:
            errors.append(f"duplicate scene id {sid!r}")
        else:
            seen.add(sid)
        narration = scene.get("narration")
        if not isinstance(narration, str) or not narration.strip():
            errors.append(f"narration of scene {sid!r} is empty")
    if errors:
        raise CheckFailed(errors)
    board.setdefault("preset", DEFAULT_PRESET)


def preset_info(name):
    p = PRESETS[name]
    return {"name": name, "width": p["width"], "height": p["height"], "fps": p["fps"],
            "aspect": p["aspect"], "target_seconds": p["target_seconds"],
            "burn_captions": p["burn_captions"]}


def out_dir_for(board, out):
    path = Path(out) if out else Path.cwd() / "out" / "video-explainer" / board["slug"]
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- plan

def cmd_plan(args):
    board = load_storyboard(args.storyboard)
    engine, voice, notices = select_engine(board)
    preset = PRESETS[board["preset"]]
    scenes = []
    for s in board["scenes"]:
        seconds = estimate_speech_seconds(s["narration"]) + PAD_SECONDS
        scenes.append({"id": s["id"], "narration": s["narration"],
                       "units": text_units(s["narration"]),
                       "estimated_seconds": round(seconds, 2),
                       "captions": split_captions(s["narration"], board["lang"])})
    total = round(sum(s["estimated_seconds"] for s in scenes), 2)
    low, high = preset["target_seconds"]
    if not low <= total <= high:
        notices.append(f"Estimated length {total} s is outside the {board['preset']} "
                       f"target of {low}-{high} s.")
    out = out_dir_for(board, args.out)
    result = {"ok": True, "command": "plan", "slug": board["slug"], "lang": board["lang"],
              "preset": preset_info(board["preset"]),
              "engine": {"name": engine.name, "voice": voice},
              "notices": notices, "scenes": scenes,
              "estimated_total_seconds": total,
              "estimated_render_seconds": estimate_render_seconds(total, preset),
              "out_dir": str(out)}
    write_json(out / "plan.json", result)
    return result


# ---------------------------------------------------------------- media tools

def run_tool(cmd):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
    except FileNotFoundError:
        raise RuntimeFailure(f"{cmd[0]} not found on PATH; run the doctor script")
    if proc.returncode:
        raise RuntimeFailure(f"{cmd[0]} failed: {proc.stderr.strip()[-1500:]}")
    return proc.stdout


def probe_seconds(path, stream=None):
    cmd = ["ffprobe", "-v", "error"]
    if stream:
        cmd += ["-select_streams", stream, "-show_entries", "stream=duration"]
    else:
        cmd += ["-show_entries", "format=duration"]
    out = run_tool(cmd + ["-of", "csv=p=0", str(path)]).strip().splitlines()
    return float(out[0])


def make_narration(board, engine, voice, work):
    """Synthesize, pad and measure each scene. Returns timing records."""
    audio = work / "audio"
    audio.mkdir(parents=True, exist_ok=True)
    timing, start = [], 0.0
    for i, s in enumerate(board["scenes"]):
        raw = audio / f"{i + 1:02d}-raw.{engine.extension}"
        norm = audio / f"{i + 1:02d}.wav"
        try:
            engine.synthesize(s["narration"], board["lang"], voice, raw)
        except Exception as exc:  # engine failures are runtime errors
            raise RuntimeFailure(f"narration engine {engine.name} failed on {s['id']}: {exc}")
        speech = probe_seconds(raw)
        run_tool(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af",
                  f"apad=pad_dur={PAD_SECONDS}", "-ar", "48000", "-ac", "1", str(norm)])
        duration = probe_seconds(norm)
        timing.append({"id": s["id"], "start": round(start, 3),
                       "end": round(start + duration, 3), "duration": round(duration, 3),
                       "speech_seconds": round(speech, 3), "audio": str(norm),
                       # Reserved for word-level sync; v1 leaves it empty.
                       "words": []})
        start += duration
    listing = audio / "concat.txt"
    listing.write_text("".join(f"file '{Path(t['audio']).name}'\n" for t in timing),
                       encoding="utf-8")
    narration = work / "narration.wav"
    run_tool(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i",
              str(listing), "-c", "copy", str(narration)])
    return timing, narration


# ---------------------------------------------------------------- render

def load_scenes_module(path, board):
    path = Path(path).resolve()
    if not path.is_file():
        raise CheckFailed([f"scenes module not found: {path}"])
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    spec = importlib.util.spec_from_file_location("video_explainer_scenes", path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ImportError as exc:
        raise RuntimeFailure(f"cannot import scenes module: {exc}")
    table = getattr(module, "SCENES", None) or {}
    functions, missing = {}, []
    for s in board["scenes"]:
        fn = table.get(s["id"]) or getattr(module, s["id"], None)
        if callable(fn):
            functions[s["id"]] = fn
        else:
            missing.append(f"scenes module has no function for scene {s['id']!r}")
    if missing:
        raise CheckFailed(missing)
    return functions


def render(board, functions, timing, width, height, fps, media_dir, name):
    """Render all scenes in one ManimCE scene. Returns (video path, seconds)."""
    try:
        import manim
        import video_helper
    except ImportError as exc:
        raise RuntimeFailure(f"ManimCE is not importable ({exc}); run this command with "
                             "`uv run make_video.py ...`")

    lang = board["lang"]

    class Explainer(manim.Scene):
        def construct(self):
            layout = video_helper.Layout(manim.config.frame_width, manim.config.frame_height)
            font = video_helper.pick_font(lang)
            for record, s in zip(timing, board["scenes"]):
                ctx = video_helper.SceneContext(
                    scene=self, scene_id=s["id"], narration=s["narration"], lang=lang,
                    start=record["start"], duration=record["duration"],
                    speech_seconds=record["speech_seconds"], layout=layout, font=font,
                    fps=fps)
                functions[s["id"]](ctx)
                ctx.wait_until(record["end"])

    settings = {"pixel_width": width, "pixel_height": height, "frame_rate": fps,
                "frame_height": 8.0, "frame_width": 8.0 * width / height,
                "media_dir": str(media_dir), "output_file": name,
                "disable_caching": True, "progress_bar": "none", "verbosity": "ERROR",
                "write_to_movie": True}
    t0 = time.perf_counter()
    try:
        with manim.tempconfig(settings), contextlib.redirect_stdout(sys.stderr):
            scene = Explainer()
            scene.render()
            video = Path(scene.renderer.file_writer.movie_file_path)
    except CheckFailed:
        raise
    except Exception as exc:
        raise RuntimeFailure(f"render failed: {type(exc).__name__}: {exc}")
    return video, time.perf_counter() - t0


def prepare(args):
    board = load_storyboard(args.storyboard)
    engine, voice, notices = select_engine(board)
    functions = load_scenes_module(args.scenes, board)
    out = out_dir_for(board, args.out)
    work = out / "work"
    work.mkdir(exist_ok=True)
    timing, narration = make_narration(board, engine, voice, work)
    return board, engine, voice, notices, functions, out, work, timing, narration


def public_timing(timing):
    return [{k: v for k, v in t.items() if k != "audio"} for t in timing]


def cmd_preview(args):
    board, engine, voice, notices, functions, out, work, timing, narration = prepare(args)
    preset = PRESETS[board["preset"]]
    scale = preset["preview_short_side"] / min(preset["width"], preset["height"])
    width = int(round(preset["width"] * scale / 2)) * 2
    height = int(round(preset["height"] * scale / 2)) * 2
    video, seconds = render(board, functions, timing, width, height, preset["preview_fps"],
                            work / "media_preview", "preview.mp4")
    frames = out / "frames"
    frames.mkdir(exist_ok=True)
    scenes = []
    for t in public_timing(timing):
        frame = frames / f"{t['id']}.png"
        at = max(t["start"], t["end"] - 0.2)  # inside the final hold of the scene
        run_tool(["ffmpeg", "-y", "-v", "error", "-ss", f"{at:.3f}", "-i", str(video),
                  "-frames:v", "1", str(frame)])
        scenes.append(dict(t, frame=str(frame)))
    result = {"ok": True, "command": "preview", "slug": board["slug"],
              "engine": {"name": engine.name, "voice": voice}, "notices": notices,
              "preview": {"width": width, "height": height, "fps": preset["preview_fps"]},
              "scenes": scenes,
              "audio_seconds": round(sum(t["duration"] for t in timing), 3),
              "preview_video": str(video), "render_seconds": round(seconds, 1),
              "out_dir": str(out)}
    write_json(out / "preview.json", result)
    return result


def srt_stamp(seconds):
    ms = int(round(seconds * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def write_srt(path, board, timing):
    cues = []
    for i, (t, s) in enumerate(zip(timing, board["scenes"])):
        text = "\n".join(split_captions(s["narration"], board["lang"]))
        cues.append(f"{i + 1}\n{srt_stamp(t['start'])} --> {srt_stamp(t['end'])}\n{text}\n")
    path.write_text("\n".join(cues), encoding="utf-8")


def write_script(path, board):
    parts = [f"# {board['slug']}\n"]
    for s in board["scenes"]:
        parts.append(f"## {s['id']}\n\n{s['narration'].strip()}\n")
    path.write_text("\n".join(parts), encoding="utf-8")


def cmd_final(args):
    board, engine, voice, notices, functions, out, work, timing, narration = prepare(args)
    preset = PRESETS[board["preset"]]
    rendered, seconds = render(board, functions, timing, preset["width"], preset["height"],
                               preset["fps"], work / "media_final", "final.mp4")
    video = out / "video.mp4"
    run_tool(["ffmpeg", "-y", "-v", "error", "-i", str(rendered), "-i", str(narration),
              "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
              str(video)])
    srt, script = out / "video.srt", out / "script.md"
    write_srt(srt, board, timing)
    write_script(script, board)
    audio_seconds = probe_seconds(narration)
    video_seconds = probe_seconds(video, "v:0")
    result = {"ok": True, "command": "final", "slug": board["slug"],
              "engine": {"name": engine.name, "voice": voice}, "notices": notices,
              "preset": preset_info(board["preset"]), "scenes": public_timing(timing),
              "video": str(video), "srt": str(srt), "script": str(script),
              "audio_seconds": round(audio_seconds, 3),
              "video_seconds": round(video_seconds, 3),
              "difference_seconds": round(video_seconds - audio_seconds, 3),
              "render_seconds": round(seconds, 1), "out_dir": str(out)}
    write_json(out / "final.json", result)
    return result


# ---------------------------------------------------------------- CLI

def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan", help="validate and estimate (stdlib only)")
    p.add_argument("storyboard")
    p.add_argument("--out")
    for name in ("preview", "final"):
        p = sub.add_parser(name)
        p.add_argument("storyboard")
        p.add_argument("scenes")
        p.add_argument("--out")
    args = parser.parse_args(argv)
    handler = {"plan": cmd_plan, "preview": cmd_preview, "final": cmd_final}[args.command]
    try:
        result, code = handler(args), 0
    except CheckFailed as exc:
        result, code = {"ok": False, "command": args.command, "errors": exc.errors}, 1
    except RuntimeFailure as exc:
        result, code = {"ok": False, "command": args.command, "errors": [str(exc)]}, 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
