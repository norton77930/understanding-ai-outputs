# diagram-explainer trigger eval

Checks that the skill description fires only on explicit diagram requests (issue #27, spec #23 stories 1, 3 and 4). The set is `trigger-eval.json`: 23 queries in skill-creator's format (`{"query", "should_trigger"}`), twelve that should trigger and eleven that should not. Acceptance: at most 2 errors out of 23. The overview sheet (spec #23 revision 2026-10-11, issue #42) added three queries: two should-trigger and one should-not. Latest results are in `RESULTS.md`.

## Decisions

- **Should trigger:** an explicit request to show how something works as a picture: "diagram", "flowchart", "sequence diagram", "state diagram", "mermaid diagram", "visualize as a picture", or "chart" of a flow. The set covers a topic and a given passage of text as input ("turn your explanation above into a flowchart"), English and zh-TW phrasing (畫一張圖, 流程圖), and each diagram type (sequence, state, flowchart TD, flowchart LR, containment). It also covers an explicit request for an overview of a whole topic on one image, in English ("an overview poster of ...") and zh-TW (一張圖看懂, 總覽圖); the skill answers those with an overview sheet.
- **Should not trigger:** requests for another explainer skill, and near-misses that share words with diagrams:
  - another rung of the format ladder: a video, an interactive HTML page, STE text (ADR 0003: each explainer skill answers its own request)
  - fixing a broken Mermaid diagram. The user wants a debugging answer for their own diagram, not a new diagram that explains a topic. The skill's workflow (pick a type, budgets, caption, saved files) does not fit. Decision: should not trigger.
  - a question about diagram notation ("what is a sequence diagram?"). The user asks for facts, not for a diagram.
  - a data plot from numbers (a bar chart from a CSV). "Chart" here means a plot, which is out of scope.
  - artwork (draw a cat as SVG)
  - a diagram tool recommendation (draw.io or Lucidchart)
  - explaining an existing diagram in words (the reverse direction)
  - an ordinary step-by-step explanation with no format request
  - a text cheat sheet ("給我一份 git 指令的 cheat sheet"). "Cheat sheet" alone usually means a text list, so it does not trigger; only "cheat sheet" with a picture word ("畫成 cheat sheet", "cheat sheet 圖") is an overview request (spec #23 decision 3).

This eval checks only whether the skill fires. Whether it draws a sheet or a single diagram is decided inside the skill: a single-question diagram request still triggers and still gets one diagram.

## Run it

Tool: skill-creator's `scripts/run_eval.py` (do not modify the installed copy). It writes a temporary `.claude/commands/<name>-skill-<id>.md` file with the description, runs `claude -p <query>` and counts a hit when the model calls the `Skill` tool for that file. Each query runs 3 times. A query passes when the trigger rate is at least 0.5 (should trigger) or below 0.5 (should not trigger).

```
python -m scripts.run_eval --eval-set evals/diagram-explainer/triggers/trigger-eval.json \
  --skill-path skills/diagram-explainer --model <session model> --runs-per-query 3 \
  --num-workers 6 --timeout 60 --verbose
```

Use the same patched scratch copy as the ste-writing and video-explainer trigger evals (see `evals/ste-writing/triggers/README.md`):

- Put the copy and its scratch project directory outside this repo, so nothing is written into the repo or into `~/.claude`.
- Give each run its own scratch directory, or run with one worker. Parallel runs in one directory see each other's command files and give false failures.
- On Windows, read the output with a thread instead of `select.select`.
- Add `--setting-sources project,local` so user-level instructions and installed plugins do not change the model behavior.
