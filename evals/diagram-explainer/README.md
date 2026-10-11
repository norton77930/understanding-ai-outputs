# diagram-explainer eval

Evals live here, outside `skills/diagram-explainer/`, so installing the skill does not ship them.

## Run it

```
python evals/diagram-explainer/run_eval.py                    # all four topics, both arms, report, review page
python evals/diagram-explainer/run_eval.py --topics 01,03     # a subset (id or number prefix)
python evals/diagram-explainer/run_eval.py --plugin-dir DIR   # plugin root to test (default: repo root)
python evals/diagram-explainer/run_eval.py --seed 7           # A/B order seed (default: the run timestamp)
python evals/diagram-explainer/run_eval.py --dry-run          # print the commands, call nothing
python evals/diagram-explainer/run_eval.py --model sonnet     # pick a model (default: claude CLI default)
python -m unittest discover -s evals/diagram-explainer -p test_run_eval.py   # unit tests (pure logic only)
```

Needs the `claude` CLI on `PATH` and Python 3.12 (standard library only). Rendering Mermaid also needs `uv` and a browser that `render_diagram.py` can use (Playwright Chromium, Chrome or Edge) plus network access to the Mermaid CDN; without them the render column says "skipped" and that arm has no image. A hand-written SVG is checked with `svg_check.py` (Python only) and converted to PNG by `render_diagram.py` through `uv run` when that works; if it does not (no `uv`, no Playwright browser, render error), the harness falls back to headless Chrome or Edge (no `uv`, no Playwright): it looks for `DIAGRAM_EVAL_BROWSER`, then `chrome`, `msedge` and the usual install folders. One full run is 8 agent calls. Output goes to `evals/diagram-explainer/runs/<timestamp>/` (git-ignored): per topic and arm the agent reply (`reply.md`), the files the agent saved (`agent-files/`), the measured Mermaid (`eval-diagram-<n>.mmd`) and its render (`render/`), the PNG of a hand-written SVG (`render/svg-<n>/` from `render_diagram.py`, or `<name>-render.png` beside the SVG from the browser fallback); `review.html` and `review/` (the blind review page and its images); and `report.md` and `report.json`.

`--plugin-dir` sets the plugin root for the with-skill arm and the location of `skills/diagram-explainer/scripts/diagram_check.py`, `svg_check.py` and `render_diagram.py`. Use it to test a tree whose `.claude-plugin/plugin.json` lists diagram-explainer, for example an exported branch.

The topics are in `topics/` (see `topics/README.md` for their status). All are zh-TW, so the maintainer can read and rate every diagram. Older rounds are kept in subfolders (`topics/round1/`, ...); the harness reads only `topics/0*.md`. A topic's `Expected diagram type` is a Mermaid header (`flowchart TD`, `sequenceDiagram`, ...) or `svg` for a diagram that must be drawn by hand (proportions, timelines, spatial ideas).

## What one run does

1. Ask an agent "Draw a diagram that explains the following." plus the topic's Source (not its hints or reader points). The request is the same in both arms.
   - with-skill: `claude -p ... --plugin-dir <plugin dir>`
   - baseline: the same command without `--plugin-dir`
   - both: `--allowedTools Bash,Read,Write,Edit,Skill,Glob,Grep` (never a permission-bypass mode)
2. Take the diagram: every `*.mmd` file the agent saved under its scratch folder, in path order; if there is none, the first ```` ```mermaid ```` block of the reply; if there is no Mermaid at all, the `*.svg` files the agent drew by hand (the baseline often does when asked for "a diagram"). The Mermaid metrics read n/a for SVG (counted as "Not Mermaid (SVG)").
   - **Which `.svg` is hand-written:** the skill's Mermaid path also writes `diagram.svg` (and `diagram-N.svg`) beside `diagram.mmd`. An `.svg` counts as hand-written only when no `.mmd` with the same stem sits in the same folder; one that has a sibling `.mmd` is a render and is ignored (the `.mmd` wins, as before; the ignored renders are listed in `report.json` as `mermaid_renders_ignored`).
3. Measure each diagram with the skill's scripts (CLI only):
   - Mermaid, `diagram_check.py`: pass (every diagram must pass), issue count, node count (flowchart nodes, state count, or sequence participants; summed over diagrams), sequence messages, label overruns (labels marked `over`).
   - Hand-written SVG, `svg_check.py`: pass (every SVG must pass), issue count; the exit code, issue rules and warning rules are recorded (`checker_exit`, `issue_rules`, `warning_rules` in the metrics, the full JSON in `checks`). Nodes, messages and label overruns stay n/a.
   - `render_diagram.py` through `uv run` for Mermaid: ok (exit 0), FAIL (exit 1, Mermaid error), skipped (exit 2 or no `uv`). Its PNG is the image of that diagram.
   - Type: for Mermaid, the header of the first diagram (`graph` and `flowchart` are the same, `TB` is `TD`, `stateDiagram` is `stateDiagram-v2`) against the topic's expected type. A hand-written SVG has type `svg`: type as expected only when the topic expects `svg`. A Mermaid diagram on an `svg` topic, or an SVG on a Mermaid topic, is "not as expected".
4. Make a PNG of every diagram so both arms are compared as pictures. A Mermaid diagram uses the PNG from step 3. A hand-written SVG goes through `uv run render_diagram.py FILE.svg` first (`render/svg-<n>/`); if that fails or `uv` is missing, it is screenshotted with headless Chrome or Edge (`--headless=new --screenshot`, window sized from the SVG's `width`/`height` or `viewBox`, device scale 2) into `<name>-render.png` beside the copied SVG in `agent-files/`. The method used per SVG is in the report (Render column, `render_methods` in `report.json`) and the reason for a fallback is listed in the details. A conversion that fails in both ways is listed under errors and the topic shows "沒有圖片" for that arm.
5. Write the blind review page and the report (below).

The with-skill arm has one checker gate, reported in `report.md` and `report.json` (`skill_gate`): each topic is checked with `svg_check.py` when the arm drew SVG and `diagram_check.py` when it drew Mermaid, and the gate fails if one of them does not pass. The baseline is reported in the same columns and never gated. The gate does not change the exit code. There is no LLM judge; the figures are for the maintainer. Exit code 0 means every call and measurement completed; 2 means something failed (listed under errors).

## Rating procedure (blind, two axes)

1. Open `runs/<timestamp>/review.html`. Per topic it shows the topic's "Reader should understand" points, then 圖 A and 圖 B side by side (click an image to open it full size). Which arm is A or B is random per topic, repeatable from the seed, and not stated anywhere on the page. The image files are copied to `review/<topic>-A.png` and `<topic>-B.png`, so neither the names nor the extensions show the arm.
2. Rate each image 1-5 on two axes:
   - 理解 (Understanding): after looking at the image, how many of the "Reader should understand" points did you get.
   - 呈現 (Presentation): is the layout, color, text size and overall look clear and easy to read.
3. Pick the better image: A, B or 平手 (tie).
4. Only then open `report.json` and read `ab_key` (for each topic, which arm was A and B) to fill the "With-skill was" column. The key is not in the review page or in `report.md`.
5. Put the ratings in `RESULTS.md` (template under "Next run").

`report.md` has, per arm and in total, the metrics (checker pass, render success, node count, label overruns; the Checker column reads `PASS (svg_check)` or `FAIL (svg_check)` for a hand-written SVG, and the details say per arm "expected svg, got svg (hand-written SVG)" or the Mermaid type that was drawn instead), the cost and the agent time; the total also has the wall time of the whole run (arms of different topics run in parallel). The seed is recorded in `report.md` and `report.json`; rerun with `--seed` to get the same A/B order.

## Isolation and environment

Every call uses the isolation flags of the ste-writing eval (`--setting-sources project,local --strict-mcp-config --no-session-persistence --output-format json`; see `evals/ste-writing/README.md` for why). Each arm runs in its own empty scratch folder outside the repo and outside `~/.claude`: `D:/diagram-explainer-eval/<timestamp>/<topic>/<arm>` (set `DIAGRAM_EVAL_CWD` to change the root).

The agents, the checker and the renderer get `UV_CACHE_DIR=D:/uv-cache`, `UV_PYTHON_DOWNLOADS=never`, `PYTHONUTF8=1`, `PYTHONDONTWRITEBYTECODE=1`, and `TMPDIR`/`TEMP`/`TMP` set to `<scratch run>/tmp`. The browser for the SVG screenshot uses a throwaway profile folder under that `tmp`.

## Known limits

- The review is one person's rating of four topics; one run is a baseline, not proof.
- The Mermaid PNG and the SVG screenshot differ in size and style by nature, so an attentive reader may guess the arm. The page does not state it.
- When the agent saves several diagrams, all of them are measured and shown (image 1, 2, ... under the same label); the first one decides the type.
- The baseline agent may also save `.mmd` files (it has the Write tool); then the files are measured and rendered, as for the skill.
- The first run (`20261008-053511`) used an LLM judge that read source text; the judge was dropped because it did not agree with the human rating of the rendered images (see `RESULTS.md`).
