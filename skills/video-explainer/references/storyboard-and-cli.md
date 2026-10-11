# Storyboard and CLI reference

`scripts/make_video.py` is the source of truth. Its module docstring holds the same facts.

## Storyboard (JSON, UTF-8)

```json
{
  "slug": "binary-search",
  "lang": "zh-TW",
  "preset": "explainer",
  "mode": "quick",
  "engine": null,
  "scenes": [
    {"id": "s1", "narration": "要在十六個排好的數字裡找三十七。先看正中間。"},
    {"id": "s2", "narration": "三十一太小，所以左邊一半全部丟掉。"},
    {"id": "s3", "narration": "每看一次，範圍就少一半。", "fallback": true, "title": "範圍減半"},
    {"id": "s4", "narration": "最多看五次就找到。", "flagged": "label still touches the caption"}
  ]
}
```

| Field | Required | Value |
| --- | --- | --- |
| `slug` | yes | Lower-case letters, digits and single hyphens. Names the output folder. |
| `lang` | yes | Narration language tag: `en`, `zh-TW`, or another tag (best effort, see `narration-engines.md`). |
| `preset` | no | `explainer` (default), `youtube` or `short`. See `output-presets.md`. |
| `mode` | no | `quick` (3 to 6 scenes, about 1 minute), `standard` (default; 6 to 15 scenes, 2 to 4 minutes) or `deep` (15 to 30 scenes, 5 to 10 minutes). `plan` fails when the scene count is outside the mode's range, and adds a notice when the estimated length is outside the mode's length or less than 5% above its lower end. `preview` and `final` do not check the scene count. |
| `engine` | no | `null` for automatic selection, an engine name (`"kokoro"`, `"edge-tts"`), or `{"name": "kokoro", "voice": "zf_001"}`. The object form needs `name`; a voice alone is an error. `elevenlabs` needs the object form with a voice ID: `{"name": "elevenlabs", "voice": "<voice_id>"}`. A field that looks like a credential (`key`, `token`, `secret`, `auth`) is an error; the ElevenLabs key comes only from `ELEVENLABS_API_KEY`. The `silent` engine is for tests only. |
| `scenes` | yes | Non-empty list, in play order. |
| `scenes[].id` | yes | Unique. Also the function name in the scenes module and the frame file name. Lower-case letters, digits and underscores, not starting with a digit (`s1`, `intro`). Not a Python keyword or a Windows device name (`con`, `nul`, `com1`). |
| `scenes[].narration` | yes | The spoken text of the scene. |
| `scenes[].fallback` | no | `true` replaces the scene with a title and 2 to 4 bullets from its narration. Set it after three failed fixes of a render error. The scenes module then needs no function for this id. |
| `scenes[].title` | no | Heading for the fallback scene. Default: the first clause of the narration. |
| `scenes[].flagged` | no | Short reason for a layout problem left after two fix rounds. `final` still renders and lists it. |

The scenes module can also map ids to functions with a module-level `SCENES = {"s1": fn, ...}` dict.

## Commands

| Command | Run with | Needs |
| --- | --- | --- |
| `doctor.py [--quick]` | `python` | Standard library. Without `--quick` it installs ManimCE into the uv cache. |
| `make_video.py plan STORYBOARD [--out DIR] [--offline]` | `python` | Standard library, no network |
| `make_video.py fetch-models SET [SET ...]` | `python` | Network. Sets: `kokoro-en`, `kokoro-zh` |
| `make_video.py preview STORYBOARD SCENES [--out DIR]` | `uv run` | uv, ffmpeg, ffprobe, ManimCE (installed by uv) |
| `make_video.py final STORYBOARD SCENES [--out DIR]` | `uv run` | Same as `preview` |

Each command prints one JSON object on stdout. Progress and library output go to stderr.

Exit codes:

- `0`: success.
- `1`: a check failed. Fix the input. Examples: invalid storyboard, a scene count outside the mode's range (`plan` only), missing scene function, no engine for the language, a scenes module that fails to import (also an `ImportError` such as `from manim import ShowCreation`), or scene code raised during `preview` or `final`.
- `2`: an environment or runtime problem. Examples: missing uv, ffmpeg or ffprobe (listed in `missing_tools` with install hints), ManimCE not installed (run with `uv run`), missing or wrong-size model files, an ffmpeg or ffprobe call that ran longer than 120 seconds, a render failure outside scene code, or an unexpected internal error (then also `error` and `type`). Stop and show it to the user.

On exit 1 or 2, `errors` is a list of messages.

## Doctor JSON

- `ready`: `true` when uv, ffmpeg and ffprobe are present. Exit 0 when ready, 2 otherwise.
- `capabilities`: `uv`, `ffmpeg`, `ffprobe`, `manim`, `kokoro_models`, `edge_tts_network`, `elevenlabs_api_key` (only whether `ELEVENLABS_API_KEY` is set). Each is `{"available", "hint"}`. With `--quick`, the `manim` and network probes add `"skipped": true`, and the `manim` hint states the install size. The full `manim` probe uses the same Python and ManimCE pins as `make_video.py`.
- `font`, `font_path`, `font_hint`: the Traditional Chinese font that scenes use (Microsoft JhengHei, then PingFang TC, then Noto Sans CJK TC), or `null` with an install hint.
- `cache_dir`: where model files live.

## plan JSON

- `preset`: `name`, `width`, `height`, `fps`, `resolution`, `aspect`, `max_seconds` (the preset's length limit in every mode: `60` for `short`, otherwise `null`), `burn_captions`.
- `mode`: `name`, `scenes` (`[min, max]` scene count), `target_seconds` (`[min, max]` length). Show the mode with the length and render-time estimates.
- `zh_scene_chars` (Chinese storyboards only, `lang` starting with `zh`): `range` (`[min, max]` characters per scene in force: the mode's, or the quick range for the `short` preset), `average`, `per_scene` (hanzi plus Latin words of each scene). `plan` adds one notice when `average` is outside `range`. It never fails on it.
- `engine`: `name`, `voice`, `reason`, `fallback` (the offline engine for zh-TW, or `null`).
- `speech_rate`: `zh_hanzi_per_second` and `engine`, the Chinese speech rate behind the estimates (3.85 for edge-tts, measured; 3.05 for every other engine). English is 2.8 words per second. The rate follows the engine in `engine`, so a zh-TW plan made offline (Kokoro) estimates longer than the same plan with edge-tts.
- `narration_cost` (ElevenLabs only): `engine`, `model`, `characters` (all narration characters sent to ElevenLabs), `estimated_credits` (1 per character) and `note` (price per 1K characters, the date it was checked and its source). Show it before any call to ElevenLabs.
- `network`: `"offline"` or `"not checked"`. `plan` never connects. Use `--offline` (or `VIDEO_EXPLAINER_OFFLINE=1`) when the doctor reported no network.
- `notices`: messages for the user. Show every one.
- `downloads`: missing model files, each `{"name", "url", "size_mb", "set", "fallback"}`. `fallback` is `true` for files that only the run-time fallback engine needs (Kokoro Chinese when edge-tts is unreachable for zh-TW).
- `scenes[]`: `id`, `narration`, `units` (`hanzi`, `words`), `estimated_seconds`, `captions`, `fallback`, `flagged`.
- `estimated_total_seconds`; `estimated_render_seconds` (`preview`, `final`, wall-clock seconds).
- `cache_dir`, `out_dir`. `plan` also writes `plan.json` to `out_dir`.

## preview JSON

- `ok`: `false` when a scene failed. Exit code is then 1.
- `errors` (only when a scene failed), `engine`, `notices` (the engine can change at run time, for example to the offline fallback).
- `preview`: `width`, `height`, `fps` of the low-quality render.
- `scenes[]`: `id`, `start`, `end`, `duration`, `speech_seconds`, `audio_reused`, `words` (reserved, empty in v1), `status` (`ok`, `fallback` or `failed`), `error` (`type`, `message`, `traceback`; failed scenes only), `frame` (PNG path, or `null` for a failed scene).
- `audio_seconds`, `preview_video`, `render_seconds`, `out_dir`. Also written to `preview.json`.

## final JSON

- Same `engine`, `notices`, `preset` and `scenes[]` fields as above.
- On success: `video`, `srt`, `script` (paths), `replaced` (scene ids drawn as fallback), `flagged` (`{"id", "reason", "frame"}`), `audio_seconds`, `video_seconds`, `difference_seconds`, `render_seconds`, `out_dir`. Also written to `final.json`.
- When a scene failed: `ok` is `false`, exit code 1, `errors` lists the scene, and no video is written.

## Output folder

Default `out/video-explainer/<slug>/` under the current folder:

- `video.mp4`, `video.srt`, `script.md`: the deliverables.
- `frames/<id>.png`: one preview frame per scene, for the layout check.
- `plan.json`, `preview.json`, `final.json`: the last JSON of each command.
- `work/`: audio, the narration audio cache and render files.
