# video-explainer eval

Evals live here, outside `skills/video-explainer/`, so installing the skill does not ship them. Spec: issue #14 (Testing Decisions, Eval). Harness: issue #22.

## Run it

```
python evals/video-explainer/run_eval.py                 # all four topics, then the report
python evals/video-explainer/run_eval.py --topics 01,04  # a subset (id or number prefix)
python evals/video-explainer/run_eval.py --dry-run       # print the commands and prompts, call nothing
python evals/video-explainer/run_eval.py --model sonnet  # pick a model (default: claude CLI default)
python -m unittest discover -s evals/video-explainer -p test_run_eval.py   # unit tests (pure logic only)
```

Needs the `claude` CLI, `ffmpeg` and `ffprobe` on `PATH`, Python 3.12 (standard library only), and what the skill itself needs (`uv`, network for edge-tts). One topic takes several minutes (one agent writes the storyboard and scenes, previews, does the layout check and renders). Options: `--workers N` (default 1, parallel topics), `--timeout SECONDS` (default 1800 per topic).

The topics are in `topics/` (approved by the maintainer; see `topics/README.md`). The with-skill arm is the only arm (the spec has no baseline).

## What one run does

1. For each topic, run one agent from its own scratch folder with:
   `Make an explainer video of the following, using the <preset> output preset. The storyboard is pre-approved: do not wait for confirmation; render it. Any model download the plan lists is approved.` followed by the topic's Source text. The pre-approval replaces the user's "go" that the skill waits for in a real conversation.
2. Find the newest successful `final.json` the agent left under the scratch folder (any depth), and read the output folder next to it.
3. Measure and copy `video.mp4`, `video.srt`, `script.md`, `storyboard.json`, `scenes.py`, the plan/preview/final JSON and `frames/` to `runs/<timestamp>/<topic>/`, plus the agent's final reply as `agent-reply.md`.
4. Write `runs/<timestamp>/report.md` and `report.json`.

`runs/` is git-ignored (`.gitignore` in this folder; `*.mp4` is also ignored at the repo root).

## Metrics (per topic)

| Metric | How | Pass |
| --- | --- | --- |
| Render success | `final.json` has `ok: true`, `video.mp4` exists, `ffprobe` finds a video stream, and `ffmpeg -f null` decodes it without an error | yes |
| Resolution | `ffprobe` width x height vs the preset (`explainer` 1280x720, `youtube` 1920x1080, `short` 1080x1920) | equal |
| Layout-check pass rate | scenes not `flagged` / total scenes, from `final.json`. Fallback scenes (`replaced`) are counted separately | reported, not gated |
| Audio/video length difference | absolute difference of the video and audio stream lengths in `video.mp4` (`ffprobe`) | 0.3 s or less |
| Captions match narration | SRT cue *i* vs scene *i* narration from `storyboard.json` (else `plan.json`), after removing punctuation, symbols, spaces and line breaks and lower-casing | every scene matches and cue count = scene count |
| Turns, cost | `num_turns` and `total_cost_usd` from the `claude -p` JSON | reported |

Verdict: FAIL if any gated check fails on any topic (a topic with no video fails render success), INCOMPLETE if a check has no data, else PASS. Exit code 0 / 1 / 2.

The maintainer's 1-5 "did I understand it" rating is manual: watch each copied `video.mp4`, check it against the topic's "Viewer should understand" bullets, and fill the rating column in `RESULTS.md`.

## Isolation

Same flags as the ste-writing eval (see `evals/ste-writing/README.md` for why), plus what a render needs:

- `--setting-sources project,local`, `--strict-mcp-config`, `--no-session-persistence`, `--output-format json`.
- `--plugin-dir <repo root>` loads the skill under test.
- `--allowedTools Bash,Read,Write,Edit,Skill,Glob,Grep`: the tools the workflow uses. No permission-bypass mode.
- Scratch folder per topic: `D:/video-explainer-eval/<timestamp>/<topic>/` (set `VIDEO_EVAL_CWD` for another root). It is outside the repo, so no project `CLAUDE.md` or settings apply, and outside `~/.claude`, which Claude Code treats as sensitive and where writes are blocked.
- Environment for the agent: `UV_CACHE_DIR=D:/uv-cache`, `UV_PYTHON_DOWNLOADS=never`, `PYTHONUTF8=1`, `VIDEO_EXPLAINER_CACHE=D:/video-explainer-cache` (Kokoro models), `PYTHONDONTWRITEBYTECODE=1`. The paths are this maintainer machine's defaults; change `AGENT_ENV` in `run_eval.py` on another machine.

## Known limits

- One run per topic. Agent behavior varies between runs; one run is a sample, not proof.
- Captions are compared with the storyboard the agent wrote, not with the topic Source. Whether the narration keeps the Source's facts is part of the maintainer's rating.
- The layout-check pass rate depends on the agent's own judgment of the frames (it sets `flagged`). The harness does not inspect frames itself. The maintainer can check `frames/`.
- The zh-TW topics use edge-tts, which needs network. Without it the skill falls back to Kokoro Chinese (mainland accent) and says so in `notices` (shown in the report).
- Not covered here: the trigger eval (see `triggers/`).
