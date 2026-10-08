# video-explainer trigger eval

Checks that the skill description fires only on explicit video requests (issue #21, spec #14 stories 1, 3 and 4). The set is `trigger-eval.json`: 20 queries in skill-creator's format (`{"query", "should_trigger"}`), ten that should trigger and ten that should not. Acceptance: at most 2 errors out of 20. Latest results are in `RESULTS.md`.

## Decisions

- **Should trigger:** an explicit request to produce a video that explains something: "explainer video", "animated video", "narrated animation", "video with voice-over", a YouTube video or Short. The set covers a topic and a given passage of text as input, English and zh-TW phrasing (影片, 解說影片, Shorts 短片), and each output preset (default, 1080p landscape, vertical Short).
- **Should not trigger:** requests for another explainer skill, and near-misses that share words with video:
  - another rung of the format ladder: a diagram, an interactive HTML page, STE text (ADR 0003: each explainer skill answers its own request)
  - "video" as a topic: a video codec question, a YouTube channel recommendation, a summary of a video transcript
  - work on an existing video: trimming a recording and burning in subtitles
  - a script for a video the user records themselves (the user wants text, not a rendered video)
  - a ManimCE debugging question (the skill's renderer, but no video request)
  - an ordinary step-by-step explanation with no format request

## Run it

Tool: skill-creator's `scripts/run_eval.py` (do not modify the installed copy). It writes a temporary `.claude/commands/<name>-skill-<id>.md` file with the description, runs `claude -p <query>` and counts a hit when the model calls the `Skill` tool for that file. Each query runs 3 times. A query passes when the trigger rate is at least 0.5 (should trigger) or below 0.5 (should not trigger).

```
python -m scripts.run_eval --eval-set evals/video-explainer/triggers/trigger-eval.json \
  --skill-path skills/video-explainer --model <session model> --runs-per-query 3 \
  --timeout 60 --verbose
```

Use the same patched scratch copy as the ste-writing trigger eval (see `evals/ste-writing/triggers/README.md`):

- Put the copy and its scratch project directory outside this repo, so nothing is written into the repo or into `~/.claude`.
- Give each run its own scratch directory, or run with one worker. Parallel runs in one directory see each other's command files and give false failures.
- On Windows, read the output with a thread instead of `select.select`.
- Add `--setting-sources project,local` so user-level instructions and installed plugins do not change the model behavior.
