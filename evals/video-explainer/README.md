# video-explainer eval

Evals live here, outside `skills/video-explainer/`, so installing the skill does not ship them. Spec: issue #14 (Testing Decisions, Eval). Harness: issue #22. Baseline arm, mode checks and blind review page: issue #41.

## Run it

```
python evals/video-explainer/run_eval.py                 # all four topics (+ baseline on the zh-TW ones), then the report
python evals/video-explainer/run_eval.py --topics 01,04  # a subset (id or number prefix)
python evals/video-explainer/run_eval.py --no-baseline   # with-skill arm only
python evals/video-explainer/run_eval.py --dry-run       # print both arms' commands and prompts, call nothing
python evals/video-explainer/run_eval.py --model sonnet  # pick a model (default: claude CLI default)
python -m unittest discover -s evals/video-explainer -p test_run_eval.py   # unit tests (pure logic only)
```

Needs the `claude` CLI, `ffmpeg` and `ffprobe` on `PATH`, Python 3.12 (standard library only), and what the skill itself needs (`uv`, network for edge-tts). A run is long: each arm of a topic is one agent that writes the storyboard and scenes (or, for the baseline, whatever it chooses), previews, checks layout and renders. Deep mode (topic 01) can take 60+ minutes per arm.

Options:

| Flag | Meaning |
| --- | --- |
| `--topics 01,03` | Run a subset (id or number prefix). |
| `--no-baseline` | Skip the baseline arm. |
| `--dry-run` | Print the commands and prompts for both arms; call nothing. |
| `--model NAME` | Passed to `claude --model` (both arms). |
| `--seed SEED` | Seed for the review page A/B order (default: the run timestamp). |
| `--workers N` | Parallel agent runs (default 1). |
| `--timeout SECONDS` | Per agent run, each arm (default 3600; it was 1800 before deep mode). A timed-out arm is measured on whatever it left behind. |

The topics are in `topics/` (see `topics/README.md`; content being revised for issue #41). Each has a `Mode` (`quick`, `standard`, `deep`) and a `Request` line in its header.

## What one run does

1. For each topic, run one with-skill agent from its own scratch folder (`<scratch root>/<timestamp>/<topic>/`, with `--plugin-dir <repo root>`) with this prompt:
   `<Request> Use the <preset> output preset. The storyboard is pre-approved: do not wait for confirmation; render it. Any model download the plan lists is approved.` followed by the topic's Source text. The pre-approval replaces the user's "go" that the skill waits for in a real conversation.
2. For the zh-TW topics (01 and 03; `BASELINE_LANGS` in `run_eval.py`), run a baseline agent with the same prompt and the same flags, env and `--allowedTools`, but without `--plugin-dir`, from `<scratch root>/<timestamp>/<topic>-baseline/`. The baseline has no skill, no storyboard and no SRT contract; it makes a video however it can.
3. With-skill: find the newest successful `final.json` under the scratch folder (any depth), read the output folder next to it, measure and copy `video.mp4`, `video.srt`, `script.md`, `storyboard.json`, `scenes.py`, the plan/preview/final JSON and `frames/` to `runs/<timestamp>/<topic>/`, plus the agent's final reply as `agent-reply.md`.
   Baseline: find the newest non-empty `*.mp4` anywhere under its scratch folder (Manim `partial_movie_files` are skipped), measure it, copy it to `runs/<timestamp>/<topic>/baseline/video.mp4`.
4. Write `runs/<timestamp>/report.md` and `report.json` (with `ab_key`, the only place that says which blind video is which).
5. Write the blind review page `runs/<timestamp>/review.html` and the videos it plays under neutral names, `runs/<timestamp>/review/<topic>-A.mp4` / `-B.mp4` (topics with a baseline, random order per topic, seeded from the timestamp or `--seed`) or `<topic>.mp4` (topics without one).

`runs/` is git-ignored (`.gitignore` in this folder; `*.mp4` is also ignored at the repo root).

## Metrics (per topic)

| Metric | With-skill arm | Baseline arm | Pass |
| --- | --- | --- | --- |
| Render success | `final.json` has `ok: true`, `video.mp4` exists, `ffprobe` finds a video stream, and `ffmpeg -f null` decodes it without an error | an `.mp4` exists, has a video stream and decodes | yes |
| Resolution | `ffprobe` width x height vs the preset (`explainer` 1280x720, `youtube` 1920x1080, `short` 1080x1920) | same | equal |
| Audio/video length difference | absolute difference of the video and audio stream lengths in `video.mp4` (`ffprobe`) | same when the file has an audio stream, else n/a | 0.3 s or less |
| Layout-check pass rate | scenes not `flagged` / total scenes, from `final.json`. Fallback scenes (`replaced`) are counted separately | n/a | reported, not gated |
| Captions match narration | SRT cue *i* vs scene *i* narration from `storyboard.json` (else `plan.json`), after removing punctuation, symbols, spaces and line breaks and lower-casing | n/a | every scene matches and cue count = scene count |
| Storyboard mode | `mode` from `storyboard.json` (else `plan.json`); also whether it equals the topic's `Mode` | n/a | reported, not gated |
| Scene count in mode range | scene count vs the mode's `scenes` range | n/a | reported, not gated |
| Video length in mode range | final `video_seconds` vs the mode's `target_seconds` range | n/a | reported, not gated |
| Turns, cost, wall time | `num_turns` and `total_cost_usd` from the `claude -p` JSON, and wall seconds of the agent run | same | reported |

The mode ranges are read from `MODES` in `skills/video-explainer/scripts/make_video.py` (loaded at run time, not copied). If that cannot be loaded the mode range checks are n/a.

Verdict (with-skill arm only): FAIL if any gated check fails on any topic (a topic with no video fails render success), INCOMPLETE if a check has no data, else PASS. Exit code 0 / 1 / 2. The baseline arm is reported in its own table and totals and never changes the verdict. For the baseline, a missing SRT or storyboard is n/a, not a failure.

## Blind review (manual)

Open `runs/<timestamp>/review.html` in a browser. It is self-contained (no external scripts) and in Traditional Chinese. Per topic it shows the "Viewer should understand" bullets and the video(s) with `<video controls>`. Topics with a baseline show two videos labeled A and B in a random order per topic; the key is only in `report.json` (`ab_key`, plus the seed in `meta.seed`). Per video, two 1-5 ratings:

- Understanding: did I understand it (check it against the bullets).
- Presentation: continuity, motion, narration naturalness, pacing.

Topics with a baseline also get "better: A / B / tie" and a notes field. The button at the bottom builds the filled table as Markdown text to copy into `RESULTS.md`; drafts are kept in `localStorage` (if the browser allows it). Then use `ab_key` to map A and B to the arms.

## Isolation

Same flags as the ste-writing eval (see `evals/ste-writing/README.md` for why), plus what a render needs:

- `--setting-sources project,local`, `--strict-mcp-config`, `--no-session-persistence`, `--output-format json`.
- `--plugin-dir <repo root>` loads the skill under test (with-skill arm only; the baseline arm has no plugin).
- `--allowedTools Bash,Read,Write,Edit,Skill,Glob,Grep`: the tools the workflow uses, for both arms. No permission-bypass mode.
- Scratch folder per arm: `D:/video-explainer-eval/<timestamp>/<topic>/` and `.../<topic>-baseline/` (set `VIDEO_EVAL_CWD` for another root). It is outside the repo, so no project `CLAUDE.md` or settings apply, and outside `~/.claude`, which Claude Code treats as sensitive and where writes are blocked.
- Environment for the agent: `UV_CACHE_DIR=D:/uv-cache`, `UV_PYTHON_DOWNLOADS=never`, `PYTHONUTF8=1`, `VIDEO_EXPLAINER_CACHE=D:/video-explainer-cache` (Kokoro models), `PYTHONDONTWRITEBYTECODE=1`. The paths are this maintainer machine's defaults; change `AGENT_ENV` in `run_eval.py` on another machine.

## Known limits

- One run per topic and arm. Agent behavior varies between runs; one run is a sample, not proof.
- The baseline may need tools or packages beyond the shared `--allowedTools` list; if it cannot make a video, that shows as "no .mp4" (render FAIL in the baseline table, not gated).
- Captions are compared with the storyboard the agent wrote, not with the topic Source. Whether the narration keeps the Source's facts is part of the maintainer's rating.
- The layout-check pass rate depends on the agent's own judgment of the frames (it sets `flagged`). The harness does not inspect frames itself. The maintainer can check `frames/`.
- The zh-TW topics use edge-tts, which needs network. Without it the skill falls back to Kokoro Chinese (mainland accent) and says so in `notices` (shown in the report).
- The blind page hides the arm in the page text and file names, not in the video content (a skill-made video may be recognizable by its style).
- Not covered here: the trigger eval (see `triggers/`).
