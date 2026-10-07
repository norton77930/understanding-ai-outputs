# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "manim>=0.21,<0.22",
#     "kokoro-onnx>=0.6,<0.7",
#     "misaki-fork[zh]>=0.9",
#     "soundfile",
#     "edge-tts>=7",
# ]
# ///
"""Orchestrator for the video-explainer skill: storyboard -> video.

Usage:
    python make_video.py plan STORYBOARD.json [--out DIR] [--offline]
    uv run make_video.py preview STORYBOARD.json SCENES.py [--out DIR]
    uv run make_video.py final STORYBOARD.json SCENES.py [--out DIR]
    python make_video.py fetch-models SET [SET ...]     (kokoro-en, kokoro-zh)

Each command prints one JSON object to stdout. Exit codes:
    0  success
    1  a check failed (invalid storyboard, missing scene function,
       no narration engine for the language), or scene code raised during
       preview/final: each scene in "scenes" then has "status" ("ok",
       "fallback" or "failed") and failed ones an "error" {type, message,
       traceback}. The other scenes still render; final writes no video.
    2  environment or runtime error (missing uv/ffmpeg/ffprobe, reported in
       "missing_tools" with the doctor's install hints; missing model;
       render failure outside scene code)

Stop rules, set per scene in the storyboard:
    "fallback": true    draw the helper's fallback (title plus 2-4 bullets from
                        the narration; optional "title") instead of the scene
                        function, e.g. after three failed fixes
    "flagged": "why"    a layout problem left after two fix rounds; final
                        still renders and lists it
final's JSON lists them in "replaced" (scene ids) and "flagged"
({id, reason, frame}, the frame being the last preview frame of the scene).

`plan` and `fetch-models` need only the Python standard library, and `plan`
never touches the network: it assumes edge-tts is reachable unless --offline
or VIDEO_EXPLAINER_OFFLINE=1 says otherwise. `preview` and `final` check
edge-tts reachability for real and fall back to Kokoro Chinese when it fails.
They need ffmpeg/ffprobe on PATH and the packages in the inline dependency
block above, which `uv run` installs. Heavy imports happen only inside them.

Narration engines (selection rules in select_engine()):
    kokoro    offline; en default (af_heart), zh-TW offline fallback (zf_001)
    edge-tts  network; zh-TW default (zh-TW-HsiaoChenNeural)
    silent    tests only; silence sized from the text-length estimate
Kokoro model files live in the doctor's cache dir (VIDEO_EXPLAINER_CACHE or
the user cache dir), never in the project. When they are missing, `plan`
lists them under "downloads"; `preview` and `final` stop with exit 2 and
never download. Narration audio is cached per text/engine/voice in the
output's work/audio/cache, so `final` reuses what `preview` synthesized.

Default output folder: out/video-explainer/<slug>/ relative to the current
working directory.
"""

import argparse
import contextlib
import importlib.util
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
import traceback
import urllib.request
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import doctor  # noqa: E402  (stdlib only; shares the model cache dir and network probe)

# Silence appended after each scene's speech. The scene length is
# speech + PAD_SECONDS, so the picture can settle before the next scene.
PAD_SECONDS = 0.35

# Speech rates measured in the prototype (natural explainer pace).
EN_WORDS_PER_SECOND = 168 / 60
ZH_HANZI_PER_SECOND = 3.05

# Output presets. Add a row to add a preset.
#   preview_short_side: pixel size of the shorter frame side in `preview`.
#   burn_captions: draw the narration into the picture, one scene-level caption
#       per scene (video.srt is written either way).
#   layout: extra video_helper.Layout arguments. `short` keeps the bottom 16% of
#       the frame clear for app controls and reserves a band above it for the
#       burned captions.
#   caption_chars: caption line width in characters (burned captions only).
PRESETS = {
    "explainer": {
        "width": 1280, "height": 720, "fps": 30, "aspect": "16:9",
        "target_seconds": [30, 120], "burn_captions": False, "layout": {},
        "preview_short_side": 480, "preview_fps": 15,
    },
    "youtube": {
        "width": 1920, "height": 1080, "fps": 30, "aspect": "16:9",
        "target_seconds": [30, 120], "burn_captions": False, "layout": {},
        "preview_short_side": 480, "preview_fps": 15,
    },
    "short": {
        "width": 1080, "height": 1920, "fps": 30, "aspect": "9:16",
        "target_seconds": [30, 60], "burn_captions": True,
        "layout": {"bottom_inset": 0.16, "narration_fraction": 0.3, "caption_fraction": 0.1},
        "caption_chars": {"zh": 11, "default": 24},
        "preview_short_side": 540, "preview_fps": 15,
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
    """Environment or runtime problem. Exit 2. extra: keys added to the JSON."""

    def __init__(self, message, extra=None):
        super().__init__(message)
        self.extra = extra or {}


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


def split_captions(text, lang, max_chars=None):
    """Split narration into caption lines: sentences first, then wrap.

    max_chars overrides CAPTION_MAX_CHARS ({"zh": n, "default": n}).
    """
    limit = (max_chars or CAPTION_MAX_CHARS)["zh" if is_zh(lang) else "default"]
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

    Engine interface (shared by every engine in ENGINES):
        name: str            registry key used in the storyboard "engine" field
        default_voice: str | None
        extension: str       file type that synthesize() writes
        voice_for(lang) -> str | None          default voice for a language
        missing_models(voice) -> [(set, name, url, bytes)]   files not yet cached
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


    def voice_for(self, lang):
        return None

    def missing_models(self, voice):
        return []


# Kokoro model files. They live in the doctor's cache dir (never in the
# project) and are fetched only by `make_video.py fetch-models`.
_KOKORO_RELEASES = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
MODEL_SETS = {
    "kokoro-en": [
        ("kokoro-v1.0.onnx", _KOKORO_RELEASES + "model-files-v1.0/kokoro-v1.0.onnx", 325532387),
        ("voices-v1.0.bin", _KOKORO_RELEASES + "model-files-v1.0/voices-v1.0.bin", 28214398),
    ],
    "kokoro-zh": [
        ("kokoro-v1.1-zh.onnx", _KOKORO_RELEASES + "model-files-v1.1/kokoro-v1.1-zh.onnx",
         325506167),
        ("voices-v1.1-zh.bin", _KOKORO_RELEASES + "model-files-v1.1/voices-v1.1-zh.bin", 53815880),
        ("config-v1.1-zh.json",
         "https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh/raw/main/config.json", 3228),
    ],
}


def size_mb(size):
    return round(size / 1e6, 1) or 0.1


def find_model(name):
    """Path of a model file anywhere under the cache dir, or None."""
    cache = doctor.cache_dir()
    if not cache.is_dir():
        return None
    return next((p for p in cache.rglob(name) if p.is_file()), None)


class KokoroEngine:
    """Kokoro via kokoro-onnx (offline, Apache-2.0 weights).

    Voices starting with "z" use the Kokoro v1.1-zh model with the misaki
    Chinese G2P; all other voices use Kokoro v1.0, with the language taken
    from the voice prefix (a = American English, b = British English, ...).
    """

    name = "kokoro"
    default_voice = "af_heart"
    extension = "wav"
    # Language tag (lower case; tried in full, then by primary subtag) -> voice.
    VOICES = {"en": "af_heart", "en-gb": "bf_emma", "zh": "zf_001", "es": "ef_dora",
              "fr": "ff_siwis", "hi": "hf_alpha", "it": "if_sara", "ja": "jf_alpha",
              "pt": "pf_dora"}
    PREFIX_LANG = {"a": "en-us", "b": "en-gb", "e": "es", "f": "fr-fr", "h": "hi",
                   "i": "it", "j": "ja", "p": "pt-br"}

    def __init__(self):
        self._models = {}

    def voice_for(self, lang):
        lang = lang.lower()
        return self.VOICES.get(lang, self.VOICES.get(lang.split("-")[0]))

    @staticmethod
    def model_set(voice):
        return "kokoro-zh" if voice.startswith("z") else "kokoro-en"

    def missing_models(self, voice):
        return [(set_name, name, url, size)
                for set_name in [self.model_set(voice)]
                for name, url, size in MODEL_SETS[set_name] if find_model(name) is None]

    def _load(self, set_name):
        if set_name not in self._models:
            from kokoro_onnx import Kokoro

            files = [find_model(name) for name, _, _ in MODEL_SETS[set_name]]
            if None in files:
                raise RuntimeFailure(f"Kokoro model files are missing from {doctor.cache_dir()}; "
                                     f"run `make_video.py fetch-models {set_name}` first")
            if set_name == "kokoro-zh":
                from misaki import zh

                model = Kokoro(str(files[0]), str(files[1]), vocab_config=str(files[2]))
                self._models[set_name] = (model, zh.ZHG2P(version="1.1"))
            else:
                self._models[set_name] = (Kokoro(str(files[0]), str(files[1])), None)
        return self._models[set_name]

    def synthesize(self, text, lang, voice, path):
        import soundfile

        model, g2p = self._load(self.model_set(voice))
        if g2p is not None:
            phonemes, _ = g2p(text)
            samples, rate = model.create(phonemes, voice=voice, speed=1.0, is_phonemes=True)
        else:
            samples, rate = model.create(text, voice=voice, speed=1.0,
                                         lang=self.PREFIX_LANG.get(voice[0], "en-us"))
        soundfile.write(str(path), samples, rate)


class EdgeTtsEngine:
    """edge-tts: Microsoft Edge read-aloud voices. Needs network access."""

    name = "edge-tts"
    default_voice = "zh-TW-HsiaoChenNeural"
    extension = "mp3"

    def voice_for(self, lang):
        return self.default_voice if is_zh_tw(lang) else None

    def missing_models(self, voice):
        return []

    def synthesize(self, text, lang, voice, path):
        import asyncio

        import edge_tts

        asyncio.run(edge_tts.Communicate(text, voice).save(str(path)))
        if not Path(path).is_file() or Path(path).stat().st_size == 0:
            raise RuntimeError("edge-tts returned no audio")


ENGINES = {"silent": SilentEngine(), "kokoro": KokoroEngine(), "edge-tts": EdgeTtsEngine()}

PUBLISHING_PRESETS = ("youtube", "short")

ACCENT_NOTICE = ("edge-tts is unreachable, so zh-TW narration uses Kokoro Chinese "
                 "(voice zf_001) with a mainland Mandarin accent, not a Taiwan accent.")
PUBLISHING_NOTICE = ("edge-tts uses an unofficial Microsoft endpoint with no service terms "
                     "for publishing; for a {preset} video consider Kokoro instead "
                     "(Apache-2.0, offline, mainland Mandarin accent for Chinese): "
                     "set \"engine\": \"kokoro\" in the storyboard.")


def is_zh_tw(lang):
    parts = lang.lower().split("-")
    return parts[0] == "zh" and ("tw" in parts or "hant" in parts)


def network_offline():
    """True when the environment states that the network is unavailable."""
    return os.environ.get("VIDEO_EXPLAINER_OFFLINE") == "1"


def edge_tts_reachable():
    """Real reachability check (used by preview and final, never by plan)."""
    return doctor.probe_network(quick=False)["available"]


def select_engine(board, offline=False):
    """Apply the selection rules. Assumes validate() already passed.

    Returns {"name", "voice", "reason", "fallback", "notices"}:
      1. A user-named engine and/or voice wins (no automatic fallback).
      2. zh-TW -> edge-tts; when offline -> Kokoro Chinese with an accent notice.
      3. Any other language -> Kokoro when it has a voice for it.
      4. Otherwise CheckFailed (exit 1).
    edge-tts with a publishing preset adds a notice that offers Kokoro.
    """
    lang = board["lang"]
    choice = board.get("engine")
    if isinstance(choice, dict):
        name, voice = choice.get("name"), choice.get("voice")
    else:
        name, voice = choice, None
    notices, fallback = [], None
    if name is not None:
        reason = "user override"
        voice = voice or ENGINES[name].voice_for(lang)
        if voice is None and name != "silent":
            raise CheckFailed([f"engine {name!r} has no default voice for {lang!r}; "
                               "name one in the storyboard: "
                               f"\"engine\": {{\"name\": \"{name}\", \"voice\": \"...\"}}"])
        if name == "edge-tts" and offline:
            notices.append("edge-tts was requested but the network is marked offline; "
                           "preview and final will fail until it is reachable.")
    elif is_zh_tw(lang):
        fallback = {"name": "kokoro", "voice": ENGINES["kokoro"].voice_for("zh")}
        if offline:
            name, voice = fallback["name"], fallback["voice"]
            reason, fallback = "edge-tts unreachable, offline fallback for zh-TW", None
            notices.append(ACCENT_NOTICE)
        else:
            name, voice, reason = "edge-tts", voice or ENGINES["edge-tts"].default_voice, \
                "default for zh-TW"
    elif ENGINES["kokoro"].voice_for(lang):
        name, voice = "kokoro", voice or ENGINES["kokoro"].voice_for(lang)
        reason = f"default for {lang}"
    else:
        known = ", ".join(["zh-TW"] + sorted(KokoroEngine.VOICES))
        raise CheckFailed([f"no narration engine has a voice for {lang!r}; supported "
                           f"languages: {known}. Or name an engine and voice in the "
                           "storyboard 'engine' field."])
    if name == "edge-tts" and board["preset"] in PUBLISHING_PRESETS:
        notices.append(PUBLISHING_NOTICE.format(preset=board["preset"]))
    return {"name": name, "voice": voice, "reason": reason, "fallback": fallback,
            "notices": notices}


def downloads_for(selection):
    """Model files the selected engine still needs, as plan reports them."""
    engine = ENGINES[selection["name"]]
    return [{"name": name, "url": url, "size_mb": size_mb(size), "set": set_name}
            for set_name, name, url, size in engine.missing_models(selection["voice"])]


def download_notice(downloads):
    total = round(sum(d["size_mb"] for d in downloads), 1)
    sets = " ".join(dict.fromkeys(d["set"] for d in downloads))
    return (f"Model files ({total} MB) are missing from {doctor.cache_dir()}. Ask the user "
            f"before downloading, then run `make_video.py fetch-models {sets}`.")


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
        if not isinstance(scene.get("fallback", False), bool):
            errors.append(f"fallback of scene {sid!r} must be true or false, "
                          f"not {scene['fallback']!r}")
        flagged = scene.get("flagged")
        if flagged is not None and (not isinstance(flagged, str) or not flagged.strip()):
            errors.append(f"flagged of scene {sid!r} must be a non-empty reason or null")
        title = scene.get("title")
        if title is not None and (not isinstance(title, str) or not title.strip()):
            errors.append(f"title of scene {sid!r} must be a non-empty string or null")
    if errors:
        raise CheckFailed(errors)
    board.setdefault("preset", DEFAULT_PRESET)


def preset_info(name):
    p = PRESETS[name]
    return {"name": name, "width": p["width"], "height": p["height"], "fps": p["fps"],
            "resolution": f"{p['width']}x{p['height']}",
            "aspect": p["aspect"], "target_seconds": p["target_seconds"],
            "burn_captions": p["burn_captions"]}


def out_dir_for(board, out):
    path = Path(out) if out else Path.cwd() / "out" / "video-explainer" / board["slug"]
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- plan

def engine_info(selection):
    return {k: selection[k] for k in ("name", "voice", "reason", "fallback")}


def cmd_plan(args):
    board = load_storyboard(args.storyboard)
    offline = args.offline or network_offline()
    selection = select_engine(board, offline=offline)
    notices = list(selection["notices"])
    downloads = downloads_for(selection)
    if downloads:
        notices.append(download_notice(downloads))
    preset = PRESETS[board["preset"]]
    scenes = []
    for s in board["scenes"]:
        seconds = estimate_speech_seconds(s["narration"]) + PAD_SECONDS
        scenes.append({"id": s["id"], "narration": s["narration"],
                       "units": text_units(s["narration"]),
                       "estimated_seconds": round(seconds, 2),
                       "captions": split_captions(s["narration"], board["lang"]),
                       "fallback": s.get("fallback", False), "flagged": s.get("flagged")})
    total = round(sum(s["estimated_seconds"] for s in scenes), 2)
    low, high = preset["target_seconds"]
    if total > high:
        notices.append(f"Estimated length {total} s exceeds the {high} s limit for the "
                       f"{board['preset']} preset (target {low}-{high} s); shorten the "
                       "storyboard.")
    elif total < low:
        notices.append(f"Estimated length {total} s is below the {board['preset']} "
                       f"target of {low}-{high} s.")
    out = out_dir_for(board, args.out)
    result = {"ok": True, "command": "plan", "slug": board["slug"], "lang": board["lang"],
              "preset": preset_info(board["preset"]),
              "engine": engine_info(selection),
              "network": "offline" if offline else "not checked",
              "notices": notices, "downloads": downloads,
              "cache_dir": str(doctor.cache_dir()), "scenes": scenes,
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


class EngineFailed(Exception):
    """A narration engine raised while synthesizing one scene."""


def synthesize_cached(engine, voice, text, lang, cache):
    """Speech audio for text, reused when the same text/engine/voice/lang was
    synthesized before (preview -> final). Returns (path, reused)."""
    key = hashlib.sha256(json.dumps([engine.name, voice, lang, text],
                                    ensure_ascii=False).encode("utf-8")).hexdigest()[:24]
    path = cache / f"{key}.{engine.extension}"
    if path.is_file() and path.stat().st_size > 0:
        return path, True
    partial = cache / f"{key}.part.{engine.extension}"
    try:
        engine.synthesize(text, lang, voice, partial)
    except RuntimeFailure:
        raise
    except Exception as exc:
        partial.unlink(missing_ok=True)
        raise EngineFailed(f"{type(exc).__name__}: {exc}") from exc
    partial.replace(path)
    return path, False


def make_narration(board, engine, voice, work):
    """Synthesize, pad and measure each scene. Returns timing records."""
    audio = work / "audio"
    cache = audio / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    timing, start = [], 0.0
    for i, s in enumerate(board["scenes"]):
        norm = audio / f"{i + 1:02d}.wav"
        try:
            raw, reused = synthesize_cached(engine, voice, s["narration"], board["lang"], cache)
        except EngineFailed as exc:
            raise EngineFailed(f"narration engine {engine.name} failed on {s['id']}: {exc}")
        speech = probe_seconds(raw)
        run_tool(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af",
                  f"apad=pad_dur={PAD_SECONDS}", "-ar", "48000", "-ac", "1", str(norm)])
        duration = probe_seconds(norm)
        timing.append({"id": s["id"], "start": round(start, 3),
                       "end": round(start + duration, 3), "duration": round(duration, 3),
                       "speech_seconds": round(speech, 3), "audio": str(norm),
                       "audio_reused": reused,
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
    except Exception as exc:
        error = scene_error(exc)
        raise CheckFailed([f"scenes module raised on import: {error['type']}: "
                           f"{error['message']}\n{error['traceback']}"])
    table = getattr(module, "SCENES", None) or {}
    functions, missing = {}, []
    for s in board["scenes"]:
        fn = table.get(s["id"]) or getattr(module, s["id"], None)
        if callable(fn):
            functions[s["id"]] = fn
        elif not s.get("fallback"):
            missing.append(f"scenes module has no function for scene {s['id']!r}")
    if missing:
        raise CheckFailed(missing)
    return functions


def scene_error(exc):
    """Short, JSON-ready record of an exception raised by scene code."""
    tail = "".join(traceback.format_exception(exc)).strip()
    return {"type": type(exc).__name__, "message": str(exc)[:300],
            "traceback": tail[-1500:]}


def recover_renderer(renderer):
    """Leave the ManimCE renderer ready for the next play() after scene code
    raised inside one: close a half-written partial movie, or drop the
    partial movie entry of a play that never started writing."""
    writer = renderer.file_writer
    if len(writer.partial_movie_files) <= renderer.num_plays:
        return
    if getattr(writer, "_current_encode_job", None) is not None:
        writer.close_partial_movie_stream()
        renderer.num_plays += 1
    else:
        writer.partial_movie_files.pop()
        if len(renderer.animations_hashes) > renderer.num_plays:
            renderer.animations_hashes.pop()


def render(board, functions, timing, preset, width, height, fps, media_dir, name):
    """Render all scenes in one ManimCE scene.

    Returns (video path, seconds, failures) where failures maps the id of each
    scene whose code raised to scene_error(). A failed scene is cleared from
    the screen and its time is filled with the screen as it was before it, so
    later scenes still render and keep their timing. Scenes marked
    "fallback": true are drawn by video_helper.fallback_scene() on a cleared
    screen instead of their function; the screen is restored after them.

    With preset["burn_captions"], each scene's narration is drawn as one
    scene-level caption (appears with the scene, leaves with it).
    """
    try:
        import manim
        import video_helper
    except ImportError as exc:
        raise RuntimeFailure(f"ManimCE is not importable ({exc}); run this command with "
                             "`uv run make_video.py ...`")

    lang = board["lang"]
    burn = preset["burn_captions"]
    char_limit = preset.get("caption_chars")
    failures = {}

    class Explainer(manim.Scene):
        def construct(self):
            layout = video_helper.Layout(manim.config.frame_width, manim.config.frame_height,
                                         **preset["layout"])
            font = video_helper.pick_font(lang)
            for record, s in zip(timing, board["scenes"]):
                ctx = video_helper.SceneContext(
                    scene=self, scene_id=s["id"], narration=s["narration"], lang=lang,
                    start=record["start"], duration=record["duration"],
                    speech_seconds=record["speech_seconds"], layout=layout, font=font,
                    fps=fps)
                before = list(self.mobjects)
                if s.get("fallback"):
                    self.clear()
                burned = None
                if burn:
                    burned = ctx.narration_caption(split_captions(s["narration"], lang,
                                                                  char_limit))
                    self.add(burned)
                try:
                    if s.get("fallback"):
                        video_helper.fallback_scene(ctx, s.get("title"))
                    else:
                        functions[s["id"]](ctx)
                except Exception as exc:
                    failures[s["id"]] = scene_error(exc)
                    recover_renderer(self.renderer)
                    self.clear()
                    self.add(*before, *([burned] if burned is not None else []))
                ctx.wait_until(record["end"])
                if burned is not None:
                    self.remove(burned)
                if s.get("fallback"):
                    self.clear()
                    self.add(*before)

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
    return video, time.perf_counter() - t0, failures


def scene_status(scene, failures):
    if scene["id"] in failures:
        return {"status": "failed", "error": failures[scene["id"]]}
    return {"status": "fallback" if scene.get("fallback") else "ok"}


def failure_errors(failures):
    return [f"scene {sid} failed to render: {e['type']}: {e['message']}. Fix its function, "
            "or after three failed fixes set \"fallback\": true on the scene in the storyboard."
            for sid, e in failures.items()]


def use_fallback(selection, why):
    """Switch an edge-tts selection to its Kokoro Chinese fallback."""
    fallback = selection["fallback"]
    return {"name": fallback["name"], "voice": fallback["voice"],
            "reason": f"{why}, offline fallback for zh-TW", "fallback": None,
            "notices": [ACCENT_NOTICE]}


def require_models(selection):
    downloads = downloads_for(selection)
    if downloads:
        raise RuntimeFailure(download_notice(downloads))


def narrate(board, selection, work):
    """Narration for the selection; edge-tts falls back to Kokoro on failure."""
    try:
        require_models(selection)
        return selection, *make_narration(board, ENGINES[selection["name"]],
                                          selection["voice"], work)
    except EngineFailed as exc:
        if not selection["fallback"]:
            raise RuntimeFailure(str(exc))
        print(f"{exc}; falling back to Kokoro Chinese", file=sys.stderr)
        selection = use_fallback(selection, "edge-tts failed")
    require_models(selection)
    try:
        return selection, *make_narration(board, ENGINES[selection["name"]],
                                          selection["voice"], work)
    except EngineFailed as exc:
        raise RuntimeFailure(str(exc))


REQUIRED_TOOLS = ("uv", "ffmpeg", "ffprobe")


def require_tools():
    """Stop (exit 2) when a tool from the doctor's minimum set is missing.

    Uses the doctor's probes, so VIDEO_EXPLAINER_DOCTOR_PATH applies here too.
    Runs before the scenes module (and so ManimCE) is imported.
    """
    missing = [{"tool": name, "hint": cap["hint"]}
               for name, cap in ((n, doctor.probe_tool(n)) for n in REQUIRED_TOOLS)
               if not cap["available"]]
    if missing:
        names = ", ".join(m["tool"] for m in missing)
        raise RuntimeFailure(
            f"required tool missing: {names}. Install it, then run "
            f"`python {HERE / 'doctor.py'}` to check the machine before rendering again.",
            {"missing_tools": missing})


def prepare(args):
    board = load_storyboard(args.storyboard)
    require_tools()
    selection = select_engine(board, offline=network_offline())
    functions = load_scenes_module(args.scenes, board)
    out = out_dir_for(board, args.out)
    work = out / "work"
    work.mkdir(exist_ok=True)
    if selection["fallback"] and not edge_tts_reachable():
        selection = use_fallback(selection, "edge-tts unreachable")
    selection, timing, narration = narrate(board, selection, work)
    return board, selection, functions, out, work, timing, narration


def public_timing(timing):
    return [{k: v for k, v in t.items() if k != "audio"} for t in timing]


def cmd_preview(args):
    board, selection, functions, out, work, timing, narration = prepare(args)
    preset = PRESETS[board["preset"]]
    scale = preset["preview_short_side"] / min(preset["width"], preset["height"])
    width = int(round(preset["width"] * scale / 2)) * 2
    height = int(round(preset["height"] * scale / 2)) * 2
    video, seconds, failures = render(board, functions, timing, preset, width, height,
                                      preset["preview_fps"],
                                      work / "media_preview", "preview.mp4")
    frames = out / "frames"
    frames.mkdir(exist_ok=True)
    scenes = []
    for t, s in zip(public_timing(timing), board["scenes"]):
        frame = frames / f"{t['id']}.png"
        frame.unlink(missing_ok=True)  # never leave a stale frame for a failed scene
        status = scene_status(s, failures)
        if status["status"] != "failed":
            at = max(t["start"], t["end"] - 0.2)  # inside the final hold of the scene
            run_tool(["ffmpeg", "-y", "-v", "error", "-ss", f"{at:.3f}", "-i", str(video),
                      "-frames:v", "1", str(frame)])
        scenes.append(dict(t, **status, frame=str(frame) if frame.is_file() else None))
    result = {"ok": not failures, "command": "preview", "slug": board["slug"],
              **({"errors": failure_errors(failures)} if failures else {}),
              "engine": engine_info(selection), "notices": selection["notices"],
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
    board, selection, functions, out, work, timing, narration = prepare(args)
    preset = PRESETS[board["preset"]]
    rendered, seconds, failures = render(board, functions, timing, preset, preset["width"],
                                         preset["height"], preset["fps"], work / "media_final",
                                         "final.mp4")
    scenes = [dict(t, **scene_status(s, failures))
              for t, s in zip(public_timing(timing), board["scenes"])]
    if failures:
        result = {"ok": False, "command": "final", "slug": board["slug"],
                  "errors": failure_errors(failures), "engine": engine_info(selection),
                  "notices": selection["notices"], "preset": preset_info(board["preset"]),
                  "scenes": scenes, "render_seconds": round(seconds, 1), "out_dir": str(out)}
        write_json(out / "final.json", result)
        return result
    replaced = [s["id"] for s in board["scenes"] if s.get("fallback")]
    flagged = []
    for s in board["scenes"]:
        if s.get("flagged"):
            frame = out / "frames" / f"{s['id']}.png"
            flagged.append({"id": s["id"], "reason": s["flagged"],
                            "frame": str(frame) if frame.is_file() else None})
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
              "engine": engine_info(selection), "notices": selection["notices"],
              "preset": preset_info(board["preset"]), "scenes": scenes,
              "replaced": replaced, "flagged": flagged, "video": str(video), "srt": str(srt), "script": str(script),
              "audio_seconds": round(audio_seconds, 3),
              "video_seconds": round(video_seconds, 3),
              "difference_seconds": round(video_seconds - audio_seconds, 3),
              "render_seconds": round(seconds, 1), "out_dir": str(out)}
    write_json(out / "final.json", result)
    return result


# ---------------------------------------------------------------- models

def cmd_fetch_models(args):
    """Download model sets into the cache dir. Files already present are kept."""
    unknown = [s for s in args.sets if s not in MODEL_SETS]
    if unknown:
        raise CheckFailed([f"unknown model set {s!r}; known sets: {', '.join(MODEL_SETS)}"
                           for s in unknown])
    target = doctor.cache_dir() / "kokoro"
    files = []
    for set_name in dict.fromkeys(args.sets):
        for name, url, size in MODEL_SETS[set_name]:
            path = find_model(name)
            downloaded = path is None
            if downloaded:
                target.mkdir(parents=True, exist_ok=True)
                path = target / name
                partial = target / f"{name}.part"
                print(f"downloading {name} ({size_mb(size)} MB) from {url}", file=sys.stderr)
                try:
                    with urllib.request.urlopen(url, timeout=60) as resp, \
                            open(partial, "wb") as fh:
                        shutil.copyfileobj(resp, fh, 1 << 20)
                except OSError as exc:
                    partial.unlink(missing_ok=True)
                    raise RuntimeFailure(f"download of {name} failed: {exc}")
                partial.replace(path)
            files.append({"name": name, "set": set_name, "path": str(path),
                          "size_mb": size_mb(path.stat().st_size), "downloaded": downloaded})
    return {"ok": True, "command": "fetch-models", "cache_dir": str(doctor.cache_dir()),
            "files": files}


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
    p.add_argument("--offline", action="store_true",
                   help="state that edge-tts is unreachable (same as VIDEO_EXPLAINER_OFFLINE=1)")
    for name in ("preview", "final"):
        p = sub.add_parser(name)
        p.add_argument("storyboard")
        p.add_argument("scenes")
        p.add_argument("--out")
    p = sub.add_parser("fetch-models", help="download model files into the user cache dir")
    p.add_argument("sets", nargs="+", metavar="SET", help=", ".join(MODEL_SETS))
    args = parser.parse_args(argv)
    handler = {"plan": cmd_plan, "preview": cmd_preview, "final": cmd_final,
               "fetch-models": cmd_fetch_models}[args.command]
    try:
        # Libraries (phonemizer, ManimCE logging) may print; stdout carries
        # only the final JSON object.
        with contextlib.redirect_stdout(sys.stderr):
            result = handler(args)
            code = 0 if result["ok"] else 1  # not ok: a scene failed to render
    except CheckFailed as exc:
        result, code = {"ok": False, "command": args.command, "errors": exc.errors}, 1
    except RuntimeFailure as exc:
        result, code = {"ok": False, "command": args.command, "errors": [str(exc)],
                        **exc.extra}, 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
