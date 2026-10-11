# html-explainer eval

Evals live here, outside `skills/html-explainer/`, so installing the skill does not ship them. Spec: issue #29 (Testing Decisions, Eval). Harness: issue #34.

## Run it

```
python evals/html-explainer/run_eval.py                    # all four topics, both arms, then the report
python evals/html-explainer/run_eval.py --topics 01,04     # a subset (id or number prefix)
python evals/html-explainer/run_eval.py --dry-run          # print the commands and prompts, call nothing
python evals/html-explainer/run_eval.py --plugin-dir DIR   # plugin folder to test (default: repo root)
python evals/html-explainer/run_eval.py --model sonnet     # pick a model (default: claude CLI default)
python -m unittest discover -s evals/html-explainer -p test_run_eval.py   # unit tests (pure logic only)
```

Needs the `claude` CLI, Python 3.12 (standard library only), `uv`, and a browser for the render check (Playwright's Chromium 1234, Chrome or Edge; see `skills/html-explainer/references/checks.md`). Options: `--workers N` (default 2, parallel agent runs), `--timeout SECONDS` (default 1200 per agent run), `--seed S` (A/B order; default random, recorded in `report.json`).

`--plugin-dir` is both the plugin the with-skill arm loads and the source of `page_check.py` and `render_check.py`. It must contain `skills/html-explainer/SKILL.md`, and its `.claude-plugin/` manifest must expose the skill.

The topics are in `topics/` (see `topics/README.md` for their review status). All four are zh-TW. English output is not rated here; the trigger eval (`triggers/`) and the automated checks cover it.

## What one run does

1. For each topic and each arm, run one agent from its own scratch folder with the same request followed by the topic's Source text. The request is the topic's `- Request:` line when it has one (for example a named style such as blueprint), else `Make an interactive web page that explains the following.`
   - `with-skill`: `claude -p ... --plugin-dir <plugin dir>`
   - `baseline`: `claude -p ...` with no plugin
2. Find the newest `.html` file the agent left under its scratch folder (any depth). If there are several, the report lists them all and measures the newest.
3. Run `page_check.py` and `render_check.py` from the plugin dir on that page, for both arms. Screenshots go to `runs/<timestamp>/<topic>/<arm>/screenshots/`. The page and the agent's final reply (`agent-reply.md`) are copied next to them.
4. Build `runs/<timestamp>/review.html` for the blind rating, written in Traditional Chinese (Taiwan): per topic, the "Reader should understand" points, links to both pages, a rating table with the two axes for A and B, and the 390 px and 1280 px light screenshots of both arms side by side, labeled only A and B in a random order per topic. The screenshots and pages are copied to `runs/<timestamp>/review/` under neutral names (`<topic>-A-390.png`, `<topic>-A.html`). The A/B key is only in `report.json` (`ab_key`).
5. Write `runs/<timestamp>/report.md` and `report.json`.

`runs/` is git-ignored (`.gitignore` in this folder).

## Metrics (per topic and arm)

| Metric | How |
| --- | --- |
| page_check | `pass` of `page_check.py`, and the sorted unique `rule` values of its `issues` |
| render_check | `pass` of `render_check.py`. An exit-2 environment error (no browser) is "n/a", not a failure |
| Console / page errors | number of `console_errors` and `page_errors` |
| No overflow at 390 | `overflow_390.overflow` is false |
| Interaction | the `interaction.kind` the render check used (`button`, `range`, `checkbox`, `details`); none if it found no usable control or `interaction_error` is set |
| Size | `size_kb` from `page_check.py` |
| Single file | the page loads nothing else: no `local-resource` issue and no external resources (`stats.external` empty, so a pinned CDN library also counts as not single-file) |
| HTML files | number of `.html` files the agent left |
| Turns, cost, wall time | `num_turns` and `total_cost_usd` from the `claude -p` JSON, and the agent run time |

Verdict (with-skill arm only; the baseline is reported, not gated): FAIL if `page_check` or `render_check` fails on any with-skill page, INCOMPLETE if one has no data (no page, or a check could not run), else PASS. Exit code 0 / 1 / 2.

The maintainer's rating is manual and blind: open `review.html`, open each page A and B to try the interaction, and rate each page 1-5 on two axes: (a) understanding (理解), how well the topic's "Reader should understand" points came across, and (b) interaction and presentation (互動與呈現). Then pick the better page per topic (A, B or tie). Fill the rating columns in `RESULTS.md`, then look up the key in `report.json`. `report.md` also gives cost and agent time per arm, which `RESULTS.md` carries into its summary.

## Isolation

Same flags as the ste-writing and video-explainer evals:

- `--setting-sources project,local`, `--strict-mcp-config`, `--no-session-persistence`, `--output-format json`.
- `--plugin-dir <plugin dir>` only in the with-skill arm.
- `--allowedTools Bash,Read,Write,Edit,Skill,Glob,Grep` in both arms. No permission-bypass mode.
- Scratch folder per topic and arm: `D:/html-explainer-eval/<timestamp>/<topic>/<arm>/` (set `HTML_EVAL_CWD` for another root). It is outside the repo, so no project `CLAUDE.md` or settings apply, and outside `~/.claude`.
- Environment for the agent and the checks: `UV_CACHE_DIR=D:/uv-cache`, `UV_PYTHON_DOWNLOADS=never`, `PYTHONUTF8=1`, `PYTHONDONTWRITEBYTECODE=1`, and `TMPDIR`/`TEMP`/`TMP` in `<scratch root>/<timestamp>/_tmp/<topic>-<arm>/`. The paths are this maintainer machine's defaults; change `AGENT_ENV` in `run_eval.py` on another machine.

## Known limits

- One run per topic and arm. Agent behavior varies between runs; one run is a sample, not proof.
- The automated checks measure the file rules and the render, not whether the page explains well or looks good. That is the two-axis blind rating.
- All rated topics are zh-TW. English output is covered by the trigger eval and the automated checks only.
- Full-page screenshots of long pages are tall; the review page scales the 1280 px shots to the column width.
- The baseline agent may not know the 390 px or single-file rules. Its failures on them show what the skill adds; they do not gate the verdict.
- Not covered here: the trigger eval (see `triggers/`).
