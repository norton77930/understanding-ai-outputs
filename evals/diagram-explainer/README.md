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

Needs the `claude` CLI on `PATH` and Python 3.12 (standard library only). Rendering Mermaid also needs `uv` and a browser that `render_diagram.py` can use (Playwright Chromium, Chrome or Edge) plus network access to the Mermaid CDN; without them the render column says "skipped" and that arm has no image. Converting a hand-written SVG to PNG needs Chrome or Edge only (no `uv`, no Playwright): the harness looks for `DIAGRAM_EVAL_BROWSER`, then `chrome`, `msedge` and the usual install folders. One full run is 8 agent calls. Output goes to `evals/diagram-explainer/runs/<timestamp>/` (git-ignored): per topic and arm the agent reply (`reply.md`), the files the agent saved (`agent-files/`), the measured Mermaid (`eval-diagram-<n>.mmd`) and its render (`render/`); `review.html` and `review/` (the blind review page and its images); and `report.md` and `report.json`.

`--plugin-dir` sets the plugin root for the with-skill arm and the location of `skills/diagram-explainer/scripts/diagram_check.py` and `render_diagram.py`. Use it to test a tree whose `.claude-plugin/plugin.json` lists diagram-explainer, for example an exported branch.

The topics are in `topics/` (see `topics/README.md` for their status). All are zh-TW, so the maintainer can read and rate every diagram. The first-run topics are kept in `topics/round1/`; the harness reads only `topics/0*.md`.

## What one run does

1. Ask an agent "Draw a diagram that explains the following." plus the topic's Source (not its hints or reader points). The request is the same in both arms.
   - with-skill: `claude -p ... --plugin-dir <plugin dir>`
   - baseline: the same command without `--plugin-dir`
   - both: `--allowedTools Bash,Read,Write,Edit,Skill,Glob,Grep` (never a permission-bypass mode)
2. Take the Mermaid: every `*.mmd` file the agent saved under its scratch folder, in path order; if there is none, the first ```` ```mermaid ```` block of the reply. If there is no Mermaid at all but the agent saved `*.svg` files (the baseline often draws SVG by hand when asked for "a diagram"), the SVG is kept, and the Mermaid metrics read n/a (counted as "Not Mermaid (SVG)").
3. Measure each Mermaid diagram with the skill's scripts (CLI only):
   - `diagram_check.py`: pass (every diagram must pass), issue count, node count (flowchart nodes, state count, or sequence participants; summed over diagrams), sequence messages, label overruns (labels marked `over`).
   - `render_diagram.py` through `uv run`: ok (exit 0), FAIL (exit 1, Mermaid error), skipped (exit 2 or no `uv`). Its PNG is the image of that diagram.
   - Type: the header of the first diagram (`graph` and `flowchart` are the same, `TB` is `TD`, `stateDiagram` is `stateDiagram-v2`) against the topic's expected type.
4. Make a PNG of every diagram so both arms are compared as pictures. A Mermaid diagram uses the PNG from step 3. A hand-written SVG is screenshotted with headless Chrome or Edge (`--headless=new --screenshot`, window sized from the SVG's `width`/`height` or `viewBox`, device scale 2) into `<name>-render.png` beside the copied SVG in `agent-files/`. A conversion that fails is listed under errors and the topic shows "沒有圖片" for that arm.
5. Write the blind review page and the report (below).

There is no LLM judge and there are no pass/fail gates; the figures are for the maintainer. Exit code 0 means every call and measurement completed; 2 means something failed (listed under errors).

## Rating procedure (blind, two axes)

1. Open `runs/<timestamp>/review.html`. Per topic it shows the topic's "Reader should understand" points, then 圖 A and 圖 B side by side (click an image to open it full size). Which arm is A or B is random per topic, repeatable from the seed, and not stated anywhere on the page. The image files are copied to `review/<topic>-A.png` and `<topic>-B.png`, so neither the names nor the extensions show the arm.
2. Rate each image 1-5 on two axes:
   - 理解 (Understanding): after looking at the image, how many of the "Reader should understand" points did you get.
   - 呈現 (Presentation): is the layout, color, text size and overall look clear and easy to read.
3. Pick the better image: A, B or 平手 (tie).
4. Only then open `report.json` and read `ab_key` (for each topic, which arm was A and B) to fill the "With-skill was" column. The key is not in the review page or in `report.md`.
5. Put the ratings in `RESULTS.md` (template under "Next run").

`report.md` has, per arm and in total, the metrics (checker pass, render success, node count, label overruns), the cost and the agent time; the total also has the wall time of the whole run (arms of different topics run in parallel). The seed is recorded in `report.md` and `report.json`; rerun with `--seed` to get the same A/B order.

## Isolation and environment

Every call uses the isolation flags of the ste-writing eval (`--setting-sources project,local --strict-mcp-config --no-session-persistence --output-format json`; see `evals/ste-writing/README.md` for why). Each arm runs in its own empty scratch folder outside the repo and outside `~/.claude`: `D:/diagram-explainer-eval/<timestamp>/<topic>/<arm>` (set `DIAGRAM_EVAL_CWD` to change the root).

The agents, the checker and the renderer get `UV_CACHE_DIR=D:/uv-cache`, `UV_PYTHON_DOWNLOADS=never`, `PYTHONUTF8=1`, `PYTHONDONTWRITEBYTECODE=1`, and `TMPDIR`/`TEMP`/`TMP` set to `<scratch run>/tmp`. The browser for the SVG screenshot uses a throwaway profile folder under that `tmp`.

## Known limits

- The review is one person's rating of four topics; one run is a baseline, not proof.
- The Mermaid PNG and the SVG screenshot differ in size and style by nature, so an attentive reader may guess the arm. The page does not state it.
- When the agent saves several diagrams, all of them are measured and shown (image 1, 2, ... under the same label); the first one decides the type.
- The baseline agent may also save `.mmd` files (it has the Write tool); then the files are measured and rendered, as for the skill.
- The first run (`20261008-053511`) used an LLM judge that read source text; the judge was dropped because it did not agree with the human rating of the rendered images (see `RESULTS.md`).
