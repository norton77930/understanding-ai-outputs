---
name: video-explainer
description: Make a short narrated explainer video (MP4 with captions and a script) of a topic or a piece of AI output, animated with ManimCE. Use ONLY when the user explicitly asks for a video, such as "make an explainer video of this", "turn this answer into an animated video", or "make a YouTube Short that explains X". Never use for diagrams, web pages, STE text, editing an existing video, or questions about video technology.
---

# Video explainer

Turn a topic, or an answer from this conversation, into a short narrated video. Each **Scene** has one **Narration** passage and the animation that plays while it is spoken. The narration audio sets the scene length. The user gets `video.mp4`, `video.srt` and `script.md`.

Rendering takes minutes. Never render before the user approves the storyboard.

## Files

- `scripts/doctor.py`: what this machine can do. Standard library only.
- `scripts/make_video.py`: `plan`, `preview`, `final` and `fetch-models`. Each prints one JSON object.
- `scripts/video_helper.py`: the helper that scene code uses. It owns layout, captions and timing.
- `references/scenes.md`: helper API, scene rules and example scenes. Read it before you write scenes.
- `references/storyboard-and-cli.md`: storyboard fields, command JSON and exit codes.
- `references/narration-engines.md`: engines, voices and "Before you publish".
- `references/output-presets.md`: the three output presets.

## How to run the scripts

- Run `doctor.py`, `plan` and `fetch-models` with `python` (`python3` if `python` is missing). They need only the standard library.
- Run `preview` and `final` with `uv run <skill folder>/scripts/make_video.py ...`. `uv` reads the inline (PEP 723) dependency block and installs ManimCE, kokoro-onnx and edge-tts on first use. The first run takes a few minutes.
- Run every command from the user's project root. The default output folder is `out/video-explainer/<slug>/` under the current folder. Use `--out DIR` for another folder. If git does not ignore `out/`, tell the user. Do not change `.gitignore` unasked.
- To keep large caches off the system drive, set `UV_CACHE_DIR` (Python packages) and `VIDEO_EXPLAINER_CACHE` (narration models) before you run the scripts.
- On Windows, set `PYTHONUTF8=1` so Chinese text stays intact.

## Workflow

1. **Doctor.** Run `python <skill folder>/scripts/doctor.py --quick`. It installs nothing. On exit 2, stop. Show the user the missing capabilities and their `hint` lines. Do not continue with a half-working setup. For Chinese narration with `font` null, show `font_hint` and stop. The `manim` hint states the package install size. You show it to the user in step 4.
2. **Storyboard.** Write `out/video-explainer/<slug>/storyboard.json` (fields in `references/storyboard-and-cli.md`):
   - 3 to 8 scenes, one idea per scene.
   - Pick `lang` from the user's language (`en`, `zh-TW`).
   - Pick the output preset: `explainer` by default, `youtube` for a YouTube upload, `short` for Shorts, Reels or vertical video.
   - Respect an engine or voice that the user names.
   - Write the narration with the rules in "Narration" below.
3. **Plan.** Run `python <skill folder>/scripts/make_video.py plan <storyboard>`. On exit 1, fix the storyboard from `errors` and run `plan` again.
4. **Show the storyboard and wait.** Show the user:
   - the scene count and the full narration of each scene
   - `estimated_total_seconds` and `estimated_render_seconds` (preview and final)
   - the output preset and the narration engine and voice
   - every entry in `notices`: accent fallback, publishing risk, length outside the target
   - each model in `downloads`, with its size in MB. Say which ones are only for the offline fallback (`"fallback": true`).
   - the first-run package install and its size, from the doctor's `manim` hint

   Then stop and wait. The user approves or asks for changes in plain words. Apply the changes to the storyboard, run `plan` again and show the result again. Do not render until the user approves.
5. **Install check and models.** Do these steps only after the user agrees to the stated sizes:
   - Run `python <skill folder>/scripts/doctor.py` without `--quick`. This installs ManimCE into the uv cache and checks the network. If `manim` is not available, show its `hint` and stop. If `edge_tts_network` is not available for zh-TW, run `plan` again with `--offline` and show the new notices.
   - Download the models: `python <skill folder>/scripts/make_video.py fetch-models <set> ...` with the sets from the `plan` notice (`kokoro-en`, `kokoro-zh`). Models go to the user cache folder, never the project.
6. **Scenes.** Write `out/video-explainer/<slug>/scenes.py` with one function per scene id. Use the helper as `references/scenes.md` shows: ManimCE only, `Text` only, layout areas only, timing through `ctx.beats()`. Each scene starts on a clean screen. Call `ctx.carry(...)` for objects the next scene reuses.
7. **Preview.** Run `uv run <skill folder>/scripts/make_video.py preview <storyboard> <scenes.py>`.
   - Exit 2: an environment problem. Show `errors` and any `missing_tools` hints, then stop.
   - Exit 1 with a scene `status` of `failed`: fix that function from its `error` and run `preview` again. After three failed fixes of one scene, set `"fallback": true` on it in the storyboard. The helper then draws a title and bullets from its narration. Add `"title"` to set the heading.
8. **Layout check.** Look at every frame in `scenes[].frame` (one PNG per scene). Look for overlapping elements, text clipped by the frame edge, and text too small or too faint to read. Fix the scenes module and run `preview` again. Do at most two fix rounds. For a problem left after round two, set `"flagged": "<short reason>"` on the scene.
9. **Final.** Run `uv run <skill folder>/scripts/make_video.py final <storyboard> <scenes.py>`. It reuses the narration audio from the preview.
10. **Deliver.** Give the user:
    - the paths from `video`, `srt` and `script`
    - the video length (`video_seconds`)
    - each scene id in `replaced`, with the reason it was replaced
    - each entry in `flagged`, with its reason and frame path
    - each entry in `notices`

    Offer another fix round for flagged scenes. Do not start it unasked.

## Narration

The narration is heard, not read. Apply these rules directly. Do not call another skill for them. The STE rules are inspired by ASD-STE100. They are not official and are not endorsed by ASD.

- English: relaxed STE. Use short sentences (20 words or fewer), active voice, one idea per sentence and one term per concept.
- Other languages: apply the STE principles: short sentences, active voice, one idea per sentence, one term per concept.
- Chinese: keep each scene to about 30 characters. Use Taiwan wording for zh-TW (程式, 資料, 伺服器).
- Write numbers and symbols the way a speaker says them. Avoid parentheses, slashes, abbreviations and code in narration. Show code on screen instead.
- Target 30 to 120 seconds in total. Keep `short` videos at 60 seconds or less.
- Each scene's narration must describe what its animation shows at the same time.

When the source is AI output from the conversation, keep its facts. Do not add claims it does not make.
