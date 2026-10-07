# html-explainer trigger eval

Checks that the skill description fires only on explicit requests for an interactive page (issue #33, spec #29 stories 1, 3 and 4). The set is `trigger-eval.json`: 20 queries in skill-creator's format (`{"query", "should_trigger"}`), ten that should trigger and ten that should not. Acceptance: at most 2 errors out of 20. Latest results are in `RESULTS.md`.

## Decisions

- **Should trigger:** an explicit request to produce an interactive page that explains something: "interactive page", "web explainer", "HTML demo", "interactive webpage", "single-file interactive HTML page". The set covers a topic and a given passage of text as input, English and zh-TW phrasing (互動網頁, 可以互動的網頁, 互動式的網頁解說), and each interaction pattern (step-through, slider, layer toggles, a choose-and-see interaction).
- **Should not trigger:** requests for another explainer skill, and near-misses that share words with HTML or web pages:
  - another rung of the format ladder: a diagram, a video, STE text (ADR 0003: each explainer skill answers its own request)
  - a web page that is a product, not an explainer: a company landing page
  - work on existing web code: fixing CSS, a JavaScript error on load, converting Markdown to HTML
  - an app component (React), even though it is interactive
  - HTML as a topic: a question about HTML tags
  - an ordinary step-by-step explanation with no format request

## Run it

Tool: skill-creator's `scripts/run_eval.py` (do not modify the installed copy). It writes a temporary `.claude/commands/<name>-skill-<id>.md` file with the description, runs `claude -p <query>` and counts a hit when the model calls the `Skill` tool for that file. Each query runs 3 times. A query passes when the trigger rate is at least 0.5 (should trigger) or below 0.5 (should not trigger).

```
python -m scripts.run_eval --eval-set evals/html-explainer/triggers/trigger-eval.json \
  --skill-path skills/html-explainer --model <session model> --runs-per-query 3 \
  --timeout 60 --verbose
```

Use the same patched scratch copy as the ste-writing and video-explainer trigger evals (see `evals/ste-writing/triggers/README.md`):

- Put the copy and its scratch project directory outside this repo, so nothing is written into the repo or into `~/.claude`.
- Give each run its own scratch directory, or run with one worker. Parallel runs in one directory see each other's command files and give false failures.
- On Windows, read the output with a thread instead of `select.select`.
- Add `--setting-sources project,local` so user-level instructions and installed plugins do not change the model behavior.
