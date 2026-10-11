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
       no narration engine for the language, scenes module fails to import),
       or scene code raised during preview/final: each scene in "scenes"
       then has "status" ("ok", "fallback" or "failed") and failed ones an
       "error" {type, message, traceback}. The other scenes still render;
       final writes no video.
    2  environment or runtime error (missing uv/ffmpeg/ffprobe, reported in
       "missing_tools" with the doctor's install hints; ManimCE not
       installed; missing or wrong-size model; an ffmpeg/ffprobe call over
       TOOL_TIMEOUT seconds; render failure outside scene code; any
       unexpected error, which adds "error" and "type")

Stop rules, set per scene in the storyboard:
    "fallback": true    draw the helper's fallback (title plus 2-4 bullets from
                        the narration; optional "title") instead of the scene
                        function, e.g. after three failed fixes
    "flagged": "why"    a layout problem left after two fix rounds; final
                        still renders and lists it
final's JSON lists them in "replaced" (scene ids) and "flagged"
({id, reason, frame}, the frame being the last preview frame of the scene).

Intent modes (storyboard "mode", see MODES): quick, standard (default) and
deep. `plan` fails (exit 1) when the scene count is outside the mode's range
and adds a notice when the estimated length is outside the mode's length (and
when a preset with max_seconds, i.e. short, is over its limit). `preview` and
`final` do not check the scene count.

`plan` and `fetch-models` need only the Python standard library, and `plan`
never touches the network: it assumes edge-tts is reachable unless --offline
or VIDEO_EXPLAINER_OFFLINE=1 says otherwise. `preview` and `final` check
edge-tts reachability for real and fall back to Kokoro Chinese when it fails.
They need ffmpeg/ffprobe on PATH and the packages in the inline dependency
block above, which `uv run` installs. Heavy imports happen only inside them.

Narration engines (selection rules in select_engine()):
    kokoro    offline; en default (af_heart), zh-TW offline fallback (zf_001)
    edge-tts  network; zh-TW default (zh-TW-HsiaoChenNeural)
    elevenlabs  network, paid; only when the storyboard names it with a voice
              ID: {"name": "elevenlabs", "voice": "<voice_id>"}. The key comes
              only from ELEVENLABS_API_KEY (read at synthesis, never stored,
              printed or cached); ELEVENLABS_API_BASE overrides the API URL.
              `plan` reports the characters and credits it will use.
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
import keyword
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
import traceback
import urllib.error
import urllib.parse
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
# Chinese rate per narration engine; an engine not listed speaks at
# ZH_HANZI_PER_SECOND. edge-tts measured 2026-10-11 with zh-TW-HsiaoChenNeural,
# run 20261011-090459, issue #53 (912 hanzi in 237.0 s).
ZH_HANZI_PER_SECOND_BY_ENGINE = {"edge-tts": 3.85}

# Output presets. Add a row to add a preset.
#   max_seconds: length limit of the preset in every mode (None: the mode alone
#       sets the length).
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
        "max_seconds": None, "burn_captions": False, "layout": {},
        "preview_short_side": 480, "preview_fps": 15,
    },
    "youtube": {
        "width": 1920, "height": 1080, "fps": 30, "aspect": "16:9",
        "max_seconds": None, "burn_captions": False, "layout": {},
        "preview_short_side": 480, "preview_fps": 15,
    },
    "short": {
        "width": 1080, "height": 1920, "fps": 30, "aspect": "9:16",
        "max_seconds": 60, "burn_captions": True,
        "layout": {"bottom_inset": 0.16, "narration_fraction": 0.3, "caption_fraction": 0.1},
        "caption_chars": {"zh": 11, "default": 24},
        "preview_short_side": 540, "preview_fps": 15,
    },
}
DEFAULT_PRESET = "explainer"

# Intent modes: the scene count range (outside it `plan` fails), the target
# length in seconds (outside it `plan` adds a notice) and the characters per
# Chinese scene (an average outside it makes `plan` add a notice). Add a row to
# add a mode. The `short` preset uses the quick range of characters in every mode.
MODES = {
    "quick": {"scenes": [3, 6], "target_seconds": [30, 90], "zh_scene_chars": [25, 35]},
    "standard": {"scenes": [6, 15], "target_seconds": [120, 240], "zh_scene_chars": [45, 60]},
    "deep": {"scenes": [15, 30], "target_seconds": [300, 600], "zh_scene_chars": [45, 60]},
}
SHORT_PRESET = "short"
# `plan` adds a notice when the estimate is less than this fraction above the
# mode's lower length bound: the measured speech can run a few percent shorter
# than the estimate (run 20261011-103432: 305 s estimated, 298.6 s rendered).
LOWER_BOUND_MARGIN = 0.05
DEFAULT_MODE = "standard"

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Scene ids name frames/<id>.png and the scene function: lower-case Python
# names that are not keywords or Windows device names.
SCENE_ID_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
WINDOWS_DEVICE_NAMES = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                        *(f"lpt{i}" for i in range(1, 10))}
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


# ElevenLabs key values that drop_key() removed from os.environ. Only redact()
# reads this, so output written after narration is still masked.
_dropped_keys = []


def drop_key():
    """Remove the ElevenLabs key from os.environ once narration is done.

    Processes started later (ManimCE's LaTeX, dvisvgm, ffmpeg) inherit
    os.environ, so the key must not stay there. The name is compared in upper
    case, as doctor.child_env() does.
    """
    for name in [k for k in os.environ if k.upper() == doctor.ELEVENLABS_KEY_VAR]:
        value = os.environ.pop(name).strip()
        if value and value not in _dropped_keys:
            _dropped_keys.append(value)


def redact(text):
    """text with the ElevenLabs key (set now or dropped) replaced by [redacted]."""
    keys = (os.environ.get(doctor.ELEVENLABS_KEY_VAR, ""), *_dropped_keys)
    if isinstance(text, str):
        # The stripped key is a substring of the raw one, so masking it is
        # enough; a whitespace-only key strips to "" and masks nothing.
        for value in dict.fromkeys(key.strip() for key in keys):
            if value:
                text = text.replace(value, "[redacted]")
    return text


def redact_data(data):
    """redact() applied to every string in JSON-ready data."""
    if isinstance(data, str):
        return redact(data)
    if isinstance(data, dict):
        return {redact_data(k): redact_data(v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [redact_data(v) for v in data]
    return data


# ---------------------------------------------------------------- estimates

def text_units(text):
    """Count hanzi and Latin words (digits count as words)."""
    hanzi = len(HANZI_RE.findall(text))
    words = len(LATIN_WORD_RE.findall(HANZI_RE.sub(" ", text)))
    return {"hanzi": hanzi, "words": words}


def zh_rate_for(engine_name):
    """Hanzi per second the named engine speaks (see ZH_HANZI_PER_SECOND_BY_ENGINE)."""
    return ZH_HANZI_PER_SECOND_BY_ENGINE.get(engine_name, ZH_HANZI_PER_SECOND)


def estimate_speech_seconds(text, zh_rate=ZH_HANZI_PER_SECOND):
    units = text_units(text)
    return units["hanzi"] / zh_rate + units["words"] / EN_WORDS_PER_SECOND


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
    """Wrap at clause marks first, then between characters, never inside a run
    of Latin letters and digits (unless the run alone exceeds the limit)."""
    parts = re.findall(r"[^，、；：,;:]+[，、；：,;:]?", sentence)
    lines, current = [], ""
    for part in parts:
        if len(current) + len(part) <= limit:
            current += part
            continue
        if current:
            lines.append(current)
        current = ""
        for token in re.findall(LATIN_WORD_RE.pattern + r"|.", part, re.S):
            if len(current) + len(token) > limit and current:
                lines.append(current)
                current = ""
            while len(token) > limit:
                lines.append(token[:limit])
                token = token[limit:]
            current += token
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


# ElevenLabs (issue #45). The price was checked on the date below; update both together.
ELEVENLABS_API_BASE = "https://api.elevenlabs.io"
ELEVENLABS_MODEL = "eleven_multilingual_v2"
ELEVENLABS_OUTPUT_FORMAT = "mp3_44100_128"
ELEVENLABS_CREDITS_PER_CHARACTER = 1  # eleven_multilingual_v2
ELEVENLABS_USD_PER_1K_CHARACTERS = 0.08
ELEVENLABS_PRICE_CHECKED = "2026-10-11"
ELEVENLABS_PRICING_URL = "https://elevenlabs.io/pricing/api"
ELEVENLABS_COST_NOTE = (f"about ${ELEVENLABS_USD_PER_1K_CHARACTERS:.2f} per 1K characters for "
                        f"{ELEVENLABS_MODEL} (checked {ELEVENLABS_PRICE_CHECKED}, "
                        f"{ELEVENLABS_PRICING_URL}); cached audio is reused, so preview and "
                        "final pay once")
ELEVENLABS_TIMEOUT = 60  # seconds for one request
ELEVENLABS_VOICE_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
ELEVENLABS_DETAIL_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
ELEVENLABS_STATUS_HINTS = {
    400: "check the voice ID and the narration",
    401: f"check {doctor.ELEVENLABS_KEY_VAR} and the credits of the account",
    403: f"check {doctor.ELEVENLABS_KEY_VAR} and the plan of the account",
    404: "check the voice ID",
    422: "check the voice ID and the narration",
    429: "too many requests or no credits left; wait, then run again",
}
# Engine object fields that look like a credential (validate() rejects them).
CREDENTIAL_FIELD_RE = re.compile(r"key|token|secret|auth|passw|credential", re.I)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow a redirect: it would send the key header to another URL."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def elevenlabs_detail(body):
    """ElevenLabs' detail.status or detail.code from an error body, or None.
    Only a short plain token is kept, with the key masked."""
    try:
        detail = json.loads(body.decode("utf-8")).get("detail")
    except (ValueError, AttributeError, UnicodeDecodeError):
        return None
    if not isinstance(detail, dict):
        return None
    for field in ("status", "code"):
        value = detail.get(field)
        if isinstance(value, str) and ELEVENLABS_DETAIL_RE.match(value):
            return redact(value)
    return None


class ElevenLabsEngine:
    """ElevenLabs text to speech over HTTPS (paid, needs network).

    Runs only when the storyboard names it with a voice ID. The key is read
    from ELEVENLABS_API_KEY inside synthesize() at call time and sent only in
    the xi-api-key header: it is never stored on this object, written to a
    file, part of the cache key or passed to a child process. Every request
    error becomes a RuntimeError built from the status code and ElevenLabs'
    detail status or code only.
    """

    name = "elevenlabs"
    default_voice = None
    extension = "mp3"

    def voice_for(self, lang):
        return None

    def missing_models(self, voice):
        return []

    def synthesize(self, text, lang, voice, path):
        key = os.environ.get(doctor.ELEVENLABS_KEY_VAR, "").strip()
        if not key:
            raise RuntimeFailure(f"{doctor.ELEVENLABS_KEY_VAR} is not set. Set it in the "
                                 "environment to use the elevenlabs engine.")
        base = (os.environ.get("ELEVENLABS_API_BASE") or ELEVENLABS_API_BASE).rstrip("/")
        url = (f"{base}/v1/text-to-speech/{urllib.parse.quote(voice, safe='')}"
               f"?output_format={ELEVENLABS_OUTPUT_FORMAT}")
        payload = json.dumps({"text": text, "model_id": ELEVENLABS_MODEL}).encode("utf-8")
        status = failure = audio = None
        try:
            request = urllib.request.Request(
                url, data=payload, method="POST",
                headers={"xi-api-key": key, "Content-Type": "application/json",
                         "Accept": "audio/mpeg"})
            opener = urllib.request.build_opener(_NoRedirect)
            with opener.open(request, timeout=ELEVENLABS_TIMEOUT) as response:
                audio = response.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            try:
                body = exc.read(4096)
            except Exception:
                body = b""
            failure = elevenlabs_detail(body)
        except Exception as exc:  # URLError, socket errors, timeouts, anything
            failure = type(exc).__name__
        finally:
            key = request = None
        # Raised outside the except blocks, so no original exception (with its
        # request, headers or message) is chained to the error.
        if status is not None:
            hint = ELEVENLABS_STATUS_HINTS.get(
                status, "ElevenLabs server error; try again later" if status >= 500 else None)
            detail = "".join(f"; {part}" for part in (failure, hint) if part)
            raise RuntimeError(f"ElevenLabs request failed: HTTP {status}{detail}")
        if failure is not None:
            raise RuntimeError(f"ElevenLabs request failed: {failure} (no HTTP reply); "
                               "check the network")
        if not audio:
            raise RuntimeError("ElevenLabs returned no audio")
        Path(path).write_bytes(audio)


ENGINES = {"silent": SilentEngine(), "kokoro": KokoroEngine(), "edge-tts": EdgeTtsEngine(),
           "elevenlabs": ElevenLabsEngine()}

PUBLISHING_PRESETS = ("youtube", "short")

ACCENT_NOTICE = ("edge-tts is unreachable, so zh-TW narration uses Kokoro Chinese "
                 "(voice zf_001) with a mainland Mandarin accent, not a Taiwan accent.")
PUBLISHING_NOTICE = ("edge-tts uses an unofficial Microsoft endpoint with no service terms "
                     "for publishing; for a {preset} video consider Kokoro instead "
                     "(Apache-2.0, offline, mainland Mandarin accent for Chinese): "
                     "set \"engine\": \"kokoro\" in the storyboard.")
ELEVENLABS_PUBLISHING_NOTICE = (
    "ElevenLabs for a {preset} video: the free plan has no commercial licence and needs "
    "\"elevenlabs.io\" in the title of each published video; paid plans include a "
    "commercial licence.")
ELEVENLABS_KEY_NOTICE = (f"{doctor.ELEVENLABS_KEY_VAR} is not set. preview and final need it "
                         "for the elevenlabs engine; set it in the environment, never in the "
                         "storyboard.")


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
    if name == "elevenlabs" and board["preset"] in PUBLISHING_PRESETS:
        notices.append(ELEVENLABS_PUBLISHING_NOTICE.format(preset=board["preset"]))
    return {"name": name, "voice": voice, "reason": reason, "fallback": fallback,
            "notices": notices}


def downloads_for(selection, fallback=False):
    """Model files the selected engine still needs, as plan reports them.
    fallback marks files that only the run-time fallback engine needs."""
    engine = ENGINES[selection["name"]]
    return [{"name": name, "url": url, "size_mb": size_mb(size), "set": set_name,
             "fallback": fallback}
            for set_name, name, url, size in engine.missing_models(selection["voice"])]


def plan_downloads(selection):
    """Downloads for the selected engine, then for its fallback engine (if any),
    so the user approves both before the first render."""
    downloads = downloads_for(selection)
    if selection["fallback"]:
        listed = {d["name"] for d in downloads}
        downloads += [d for d in downloads_for(selection["fallback"], fallback=True)
                      if d["name"] not in listed]
    return downloads


def download_notice(downloads):
    total = round(sum(d["size_mb"] for d in downloads), 1)
    sets = " ".join(dict.fromkeys(d["set"] for d in downloads))
    notice = (f"Model files ({total} MB) are missing from {doctor.cache_dir()}. Ask the user "
              f"before downloading, then run `make_video.py fetch-models {sets}`.")
    spare = [d for d in downloads if d["fallback"]]
    if spare:
        spare_sets = ", ".join(dict.fromkeys(d["set"] for d in spare))
        notice += (f" {spare_sets} ({round(sum(d['size_mb'] for d in spare), 1)} MB) is only "
                   "for the offline fallback, used when edge-tts is unreachable at render time.")
    return notice


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
    mode = board.get("mode", DEFAULT_MODE)
    if mode not in MODES:
        errors.append(f"unknown mode {mode!r}; known modes: {', '.join(MODES)}")
    engine = board.get("engine")
    name = engine.get("name") if isinstance(engine, dict) else engine
    if isinstance(engine, dict) and name is None:
        errors.append("engine object needs a name, for example "
                      "{\"name\": \"kokoro\", \"voice\": \"zf_001\"}")
    elif name is not None and name not in ENGINES:
        errors.append(f"unknown engine {name!r}; known engines: {', '.join(ENGINES)}")
    if isinstance(engine, dict):
        for field in engine:
            if CREDENTIAL_FIELD_RE.search(str(field)):
                errors.append(f"engine field {str(field)[:40]!r} looks like a credential; remove "
                              "it. The ElevenLabs key comes only from the "
                              f"{doctor.ELEVENLABS_KEY_VAR} environment variable.")
    if name == "elevenlabs":
        voice = engine.get("voice") if isinstance(engine, dict) else None
        if not isinstance(voice, str) or not ELEVENLABS_VOICE_RE.match(voice):
            errors.append("the elevenlabs engine needs an ElevenLabs voice ID (letters and "
                          "digits, from your ElevenLabs voice library). Ask the user to choose "
                          "one, then set \"engine\": {\"name\": \"elevenlabs\", "
                          "\"voice\": \"<voice_id>\"}.")
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
        elif (not SCENE_ID_RE.match(sid) or keyword.iskeyword(sid)
              or sid in WINDOWS_DEVICE_NAMES):
            errors.append(f"scene id {sid!r} must be a lower-case Python name (letters, digits "
                          "and underscores, not starting with a digit), not a keyword and not "
                          "a Windows device name such as con")
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
    board.setdefault("mode", DEFAULT_MODE)


def preset_info(name):
    p = PRESETS[name]
    return {"name": name, "width": p["width"], "height": p["height"], "fps": p["fps"],
            "resolution": f"{p['width']}x{p['height']}",
            "aspect": p["aspect"], "max_seconds": p["max_seconds"],
            "burn_captions": p["burn_captions"]}


def mode_info(name):
    m = MODES[name]
    return {"name": name, "scenes": m["scenes"], "target_seconds": m["target_seconds"]}


def zh_scene_chars_info(board, scenes):
    """Characters (hanzi plus Latin words) per Chinese scene against the range in
    force: the quick range for the `short` preset, else the range of the mode.
    Returns (info, notice); notice is None when the average is inside the range."""
    if board["preset"] == SHORT_PRESET:
        label, rng = "short preset", MODES["quick"]["zh_scene_chars"]
    else:
        label, rng = f"{board['mode']} mode", MODES[board["mode"]]["zh_scene_chars"]
    counts = [s["units"]["hanzi"] + s["units"]["words"] for s in scenes]
    average = round(sum(counts) / len(counts), 1)
    info = {"range": list(rng), "average": average, "per_scene": counts}
    low, high = rng
    if low <= average <= high:
        return info, None
    if average < low:
        side, fix = "below", "write fuller scenes, not more scenes"
    else:
        side, fix = "above", "write shorter scenes, not fewer scenes"
    return info, (f"Chinese narration: average {average:g} characters per scene is {side} "
                  f"the {label}'s {low}-{high}; {fix}.")


def check_scene_count(board):
    """The scene count must fit the mode. Only `plan` checks it, so a storyboard
    that the user approved still previews and renders."""
    mode = board["mode"]
    low, high = MODES[mode]["scenes"]
    count = len(board["scenes"])
    if not low <= count <= high:
        ranges = ", ".join(f"{n} {m['scenes'][0]}-{m['scenes'][1]}" for n, m in MODES.items())
        raise CheckFailed([f"the storyboard has {count} scenes, but the {mode} mode needs "
                           f"{low}-{high} scenes; change the scene count or set another mode "
                           f"({ranges})"])


def out_dir_for(board, out):
    path = Path(out) if out else Path.cwd() / "out" / "video-explainer" / board["slug"]
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def write_json(path, data):
    path.write_text(json.dumps(redact_data(data), indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


# ---------------------------------------------------------------- plan

def engine_info(selection):
    return {k: selection[k] for k in ("name", "voice", "reason", "fallback")}


def cmd_plan(args):
    board = load_storyboard(args.storyboard)
    check_scene_count(board)
    offline = args.offline or network_offline()
    selection = select_engine(board, offline=offline)
    notices = list(selection["notices"])
    downloads = plan_downloads(selection)
    if downloads:
        notices.append(download_notice(downloads))
    preset = PRESETS[board["preset"]]
    zh_rate = zh_rate_for(selection["name"])
    scenes = []
    for s in board["scenes"]:
        seconds = estimate_speech_seconds(s["narration"], zh_rate) + PAD_SECONDS
        scenes.append({"id": s["id"], "narration": s["narration"],
                       "units": text_units(s["narration"]),
                       "estimated_seconds": round(seconds, 2),
                       "captions": split_captions(s["narration"], board["lang"]),
                       "fallback": s.get("fallback", False), "flagged": s.get("flagged")})
    total = round(sum(s["estimated_seconds"] for s in scenes), 2)
    mode = board["mode"]
    low, high = MODES[mode]["target_seconds"]
    zh_chars, zh_notice = (zh_scene_chars_info(board, scenes) if is_zh(board["lang"])
                           else (None, None))
    # Chinese scenes below their character range: fuller scenes are the fix, so
    # one notice carries the short length and "add scenes" is not advised.
    zh_too_short = zh_chars is not None and zh_chars["average"] < zh_chars["range"][0]
    if total > high:
        notices.append(f"Estimated length {total} s is above the {mode} mode target of "
                       f"{low}-{high} s; shorten the scenes or switch to a deeper mode.")
    elif total < low:
        if zh_too_short:
            zh_notice += (f" Estimated length {total} s is below the {mode} mode target of "
                          f"{low}-{high} s.")
        else:
            notices.append(f"Estimated length {total} s is below the {mode} mode target of "
                           f"{low}-{high} s; add scenes or switch to a quicker mode.")
    elif total < low * (1 + LOWER_BOUND_MARGIN):
        notices.append(f"Estimated length {total} s is close to the lower end of the {mode} mode "
                       f"target of {low}-{high} s; the real video can be a few percent shorter, "
                       f"so add a little narration.")
    limit = preset["max_seconds"]
    if limit is not None and total > limit:
        notices.append(f"Estimated length {total} s exceeds the {limit} s limit for the "
                       f"{board['preset']} preset; shorten the storyboard.")
    if zh_notice:
        notices.append(zh_notice)
    out = out_dir_for(board, args.out)
    result = {"ok": True, "command": "plan", "slug": board["slug"], "lang": board["lang"],
              "preset": preset_info(board["preset"]), "mode": mode_info(mode),
              "engine": engine_info(selection),
              "speech_rate": {"zh_hanzi_per_second": zh_rate, "engine": selection["name"]},
              "network": "offline" if offline else "not checked",
              "notices": notices, "downloads": downloads,
              "cache_dir": str(doctor.cache_dir()), "scenes": scenes,
              "estimated_total_seconds": total,
              "estimated_render_seconds": estimate_render_seconds(total, preset),
              "out_dir": str(out)}
    if zh_chars is not None:
        result["zh_scene_chars"] = zh_chars
    if selection["name"] == "elevenlabs":
        characters = sum(len(s["narration"]) for s in board["scenes"])
        result["narration_cost"] = {
            "engine": "elevenlabs", "model": ELEVENLABS_MODEL, "characters": characters,
            "estimated_credits": characters * ELEVENLABS_CREDITS_PER_CHARACTER,
            "note": ELEVENLABS_COST_NOTE}
        if not os.environ.get(doctor.ELEVENLABS_KEY_VAR, "").strip():
            notices.append(ELEVENLABS_KEY_NOTICE)
    write_json(out / "plan.json", result)
    return result


# ---------------------------------------------------------------- media tools

# Seconds one ffmpeg/ffprobe call may take before it counts as hung.
# VIDEO_EXPLAINER_TOOL_TIMEOUT overrides it (used by the tests).
TOOL_TIMEOUT = 120


def tool_timeout():
    return float(os.environ.get("VIDEO_EXPLAINER_TOOL_TIMEOUT") or TOOL_TIMEOUT)


def run_tool(cmd):
    """Run a media tool found through the doctor's PATH lookup. Never reads
    stdin; a call that runs longer than tool_timeout() stops with exit 2."""
    exe = doctor.find_tool(cmd[0])
    if exe is None:
        raise RuntimeFailure(f"{cmd[0]} not found on PATH; run the doctor script")
    timeout = tool_timeout()
    try:
        proc = subprocess.run([exe, *cmd[1:]], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
                              timeout=timeout, env=doctor.child_env())
    except FileNotFoundError:
        raise RuntimeFailure(f"{cmd[0]} not found on PATH; run the doctor script")
    except subprocess.TimeoutExpired:
        raise RuntimeFailure(f"{cmd[0]} timed out after {timeout:g} s and was stopped: "
                             f"{' '.join(cmd[1:])[:300]}")
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

# Top-level modules that `uv run` installs for the scenes module and the
# helper. A scenes module that cannot import one of these is an environment
# problem (exit 2); any other import error is a bug in scene code (exit 1).
ENVIRONMENT_MODULES = {"manim", "manimpango", "numpy", "cairo", "video_helper", "doctor"}


def scenes_import_error(exc):
    error = scene_error(exc)
    return (f"scenes module raised on import: {error['type']}: {error['message']}\n"
            f"{error['traceback']}")


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
    except ModuleNotFoundError as exc:
        if exc.name not in ENVIRONMENT_MODULES:
            raise CheckFailed([scenes_import_error(exc)])
        raise RuntimeFailure(f"cannot import scenes module: {exc}. {exc.name} is installed by "
                             "`uv run`: run this command with `uv run make_video.py ...`")
    except Exception as exc:
        raise CheckFailed([scenes_import_error(exc)])
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
    # Private ManimCE 0.21 attribute; a missing one means another ManimCE
    # version, where guessing could corrupt the video.
    if not hasattr(writer, "_current_encode_job"):
        raise RuntimeFailure(
            "cannot recover from the failed scene: this ManimCE version has no "
            "SceneFileWriter._current_encode_job (ManimCE 0.21 internals). Run with "
            "`uv run make_video.py ...` so the pinned manim>=0.21,<0.22 is used.")
    if writer._current_encode_job is not None:
        writer.close_partial_movie_stream()
        renderer.num_plays += 1
    else:
        writer.partial_movie_files.pop()
        if len(renderer.animations_hashes) > renderer.num_plays:
            renderer.animations_hashes.pop()


def render(board, functions, timing, preset, width, height, fps, media_dir, name):
    """Render all scenes in one ManimCE scene.

    Returns (video path, seconds, failures) where failures maps the id of each
    scene whose code raised to scene_error(). Each scene starts with
    video_helper.clear_previous(): the previous scene's objects fade out,
    except those it passed to ctx.carry(). A failed scene is cleared from the
    screen and its time is filled with the objects carried into it, so later
    scenes still render and keep their timing. Scenes marked "fallback": true
    are drawn by video_helper.fallback_scene() on a cleared screen instead of
    their function. After a failed or fallback scene, the objects carried
    into it are carried on to the next scene.

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
            keep = []  # objects the previous scene passed to ctx.carry()
            for record, s in zip(timing, board["scenes"]):
                ctx = video_helper.SceneContext(
                    scene=self, scene_id=s["id"], narration=s["narration"], lang=lang,
                    start=record["start"], duration=record["duration"],
                    speech_seconds=record["speech_seconds"], layout=layout, font=font,
                    fps=fps)
                if s.get("fallback"):
                    survivors = video_helper.carried_on_screen(self, keep)
                    self.clear()
                else:
                    video_helper.clear_previous(ctx, keep)
                    survivors = list(self.mobjects)
                before = list(self.mobjects)
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
                if s.get("fallback") or s["id"] in failures:
                    # Pass what was carried into this scene on to the next one.
                    self.clear()
                    self.add(*survivors)
                    keep = survivors
                else:
                    keep = ctx.carried()

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
    except (CheckFailed, RuntimeFailure):
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
        print(redact(f"{exc}; falling back to Kokoro Chinese"), file=sys.stderr)
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
    try:
        selection, timing, narration = narrate(board, selection, work)
    finally:
        drop_key()  # render's child processes must not inherit the key
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
                got = partial.stat().st_size
                if got != size:
                    partial.unlink(missing_ok=True)
                    raise RuntimeFailure(f"download of {name} is incomplete or changed: got "
                                         f"{got} bytes, expected {size}; nothing was kept. "
                                         "Run fetch-models again.")
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
    except Exception as exc:  # keep the one-JSON-object contract for any bug
        sys.stderr.write(redact(traceback.format_exc()))
        message = f"unexpected {type(exc).__name__}: {exc}"
        result, code = {"ok": False, "command": args.command, "errors": [message],
                        "error": str(exc), "type": type(exc).__name__}, 2
    print(json.dumps(redact_data(result), indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
