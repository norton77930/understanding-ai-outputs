# diagram-explainer eval

Evals live here, outside `skills/diagram-explainer/`, so installing the skill does not ship them.

## Run it

```
python evals/diagram-explainer/run_eval.py                    # all four topics, both arms, judge, report
python evals/diagram-explainer/run_eval.py --topics 01,03     # a subset (id or number prefix)
python evals/diagram-explainer/run_eval.py --plugin-dir DIR   # plugin root to test (default: repo root)
python evals/diagram-explainer/run_eval.py --dry-run          # print the commands, call nothing
python evals/diagram-explainer/run_eval.py --model sonnet     # pick a model (default: claude CLI default)
python -m unittest discover -s evals/diagram-explainer -p test_run_eval.py   # unit tests (pure logic only)
```

Needs the `claude` CLI on `PATH` and Python 3.12 (standard library only). Rendering also needs `uv` and a browser that `render_diagram.py` can use (Playwright Chromium, Chrome or Edge) plus network access to the Mermaid CDN; without them the render column says "skipped". One full run is 8 agent calls plus 4 judge calls. Output goes to `evals/diagram-explainer/runs/<timestamp>/` (git-ignored): per topic and arm the agent reply (`reply.md`), the files the agent saved (`agent-files/`), the measured Mermaid (`eval-diagram-<n>.mmd`) and its render (`render/`); per topic the judge reply; and `report.md` and `report.json`.

`--plugin-dir` sets the plugin root for the with-skill arm and the location of `skills/diagram-explainer/scripts/diagram_check.py` and `render_diagram.py`. Use it to test a tree whose `.claude-plugin/plugin.json` lists diagram-explainer, for example an exported branch.

The topics are in `topics/` (see `topics/README.md` for their status).

## What one run does

1. Ask an agent "Draw a diagram that explains the following." plus the topic's Source (not its hints or reader points). The request is the same in both arms.
   - with-skill: `claude -p ... --plugin-dir <plugin dir>`
   - baseline: the same command without `--plugin-dir`
   - both: `--allowedTools Bash,Read,Write,Edit,Skill,Glob,Grep` (never a permission-bypass mode)
2. Take the Mermaid: every `*.mmd` file the agent saved under its scratch folder, in path order; if there is none, the first ```` ```mermaid ```` block of the reply. If there is no Mermaid at all but the agent saved `*.svg` files (the baseline often draws SVG by hand when asked for "a diagram"), the SVG source is judged, and the Mermaid metrics read n/a (counted as "Not Mermaid (SVG)").
3. Measure each diagram with the skill's scripts (CLI only):
   - `diagram_check.py`: pass (every diagram must pass), issue count, node count (flowchart nodes, state count, or sequence participants; summed over diagrams), sequence messages, label overruns (labels marked `over`).
   - `render_diagram.py` through `uv run`: ok (exit 0), FAIL (exit 1, Mermaid error), skipped (exit 2 or no `uv`).
   - Type: the header of the first diagram (`graph` and `flowchart` are the same, `TB` is `TD`, `stateDiagram` is `stateDiagram-v2`) against the topic's expected type.
4. One judge call per topic (`--tools ""`, no plugin) sees the Source, the topic's "Reader should understand" points and the Mermaid source of both arms in randomized A/B order (reproducible from `--seed`). It returns `{faster, accuracy_a, accuracy_b, reason}`. The harness maps A/B back to arms.
5. Write the report: totals per arm, a per-topic table, checker issues, render errors, judge reasons and all diagrams.

There are no pass/fail gates in this eval; the report gives the figures for the maintainer. Exit code 0 means every call and measurement completed; 2 means something failed (listed under errors).

## Isolation and environment

Every call uses the isolation flags of the ste-writing eval (`--setting-sources project,local --strict-mcp-config --no-session-persistence --output-format json`; see `evals/ste-writing/README.md` for why). Each arm runs in its own empty scratch folder outside the repo and outside `~/.claude`: `D:/diagram-explainer-eval/<timestamp>/<topic>/<arm>` (set `DIAGRAM_EVAL_CWD` to change the root). The judge runs in `<topic>/judge`.

The agents, the checker and the renderer get `UV_CACHE_DIR=D:/uv-cache`, `UV_PYTHON_DOWNLOADS=never`, `PYTHONUTF8=1`, `PYTHONDONTWRITEBYTECODE=1`, and `TMPDIR`/`TEMP`/`TMP` set to `<scratch run>/tmp`.

## Known limits

- The judge reads Mermaid (or SVG) source, not the rendered picture, and does not see the caption. "Faster" is the judge's estimate from the source. Hand-written SVG is harder to read as text than Mermaid, which may bias the judge against SVG answers.
- When the agent saves several diagrams, all of them are measured and judged; the first one decides the type.
- The baseline agent may also save `.mmd` files (it has the Write tool); then the files are measured, as for the skill.
- LLM judge scores are noisy. One run is a baseline, not proof.
