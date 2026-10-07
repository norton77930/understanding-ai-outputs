# diagram-explainer eval results

Run `20261008-053511` (2026-10-08). Model: claude CLI default (`claude` 2.1.293). Both arms per topic, workers 4, timeout 900 s per call, judge seed `20261008-053511`. Command: `python evals/diagram-explainer/run_eval.py --plugin-dir D:/tmp/export-feat-diagram-explainer` (an export of `feat/diagram-explainer` whose plugin manifest lists the skill). Full report: `evals/diagram-explainer/runs/20261008-053511/report.md` (git-ignored, local only).

**The topics are a DRAFT.** `topics/README.md` says they still wait for maintainer review (issue #26). This run used them as they are; rerun after the review if a topic changes.

## Summary

With-skill: 4/4 diagrams pass the checker, 4/4 render, 0 label overruns, expected type 3/4. Baseline: 1/4 answered in Mermaid (it failed the checker with 12 issues and rendered); 3/4 drew a hand-written SVG instead. The judge picked with-skill as faster to understand in 3 of 4 topics (baseline 1, tie 0). Mean judge accuracy is 4.75 in both arms. Wall time 3 min 13 s (topics in parallel). Cost $2.22: with-skill $1.00 (49 turns), baseline $1.00 (19 turns), judge $0.22.

| Topic | Lang | Expected type | Arm | Format / type | Checker (issues) | Nodes | Label overruns | Render | Judge accuracy | Faster | Cost | Time |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01-oauth-login | en | sequenceDiagram | with-skill | sequenceDiagram | PASS (0) | 5 participants, 11 messages | 0 | ok | 5 | | $0.25 | 63 s |
| | | | baseline | hand-written SVG | n/a | n/a | n/a | n/a | 5 | yes | $0.34 | 111 s |
| 02-pull-request-lifecycle | zh-TW | stateDiagram-v2 | with-skill | stateDiagram-v2 | PASS (0) | 5 states | 0 | ok | 5 | yes | $0.24 | 70 s |
| | | | baseline | stateDiagram-v2 (in reply) | FAIL (12) | 7 states | 4 | ok | 4 | | $0.08 | 19 s |
| 03-ci-pipeline | en | flowchart LR | with-skill | flowchart TD (not as expected) | PASS (0) | 12 | 0 | ok | 4 | yes | $0.17 | 54 s |
| | | | baseline | hand-written SVG | n/a | n/a | n/a | n/a | 5 | | $0.29 | 85 s |
| 04-browser-cache | zh-TW | flowchart TD | with-skill | flowchart TD | PASS (0) | 12 | 0 | ok | 5 | yes | $0.34 | 97 s |
| | | | baseline | hand-written SVG | n/a | n/a | n/a | n/a | 5 | | $0.28 | 72 s |

Judge reasons, in short:

- 01: both correct; the baseline SVG's labeled front-channel and back-channel bands and numbered notes make the key points explicit, while the reader of the compact sequence diagram must infer them.
- 02: the baseline adds a "checks failed, back to Open" path that the source does not describe; the with-skill state diagram covers every point and is quicker to grasp.
- 03: the with-skill flowchart is quicker to scan, but it shows staging as a fixed step (the source says "many teams") and drops "nothing is deployed"; the baseline SVG is faithful but larger and denser.
- 04: both correct; the with-skill chart is compact, the baseline SVG has a large canvas, a legend and a long wrap-around arrow.

## Maintainer notes

Look at each diagram against the topic's "Reader should understand" bullets in `topics/`. Renders (local, git-ignored) are in `runs/20261008-053511/<topic>/<arm>/render/` (Mermaid) or `agent-files/` (the baseline's SVG files).

| Topic | Arm | Diagram | Maintainer notes |
|---|---|---|---|
| 01-oauth-login | with-skill | `runs/20261008-053511/01-oauth-login/with-skill/render/eval-diagram-1.png` | |
| 01-oauth-login | baseline | `runs/20261008-053511/01-oauth-login/baseline/agent-files/oauth-authorization-code-flow.svg` | |
| 02-pull-request-lifecycle | with-skill | `runs/20261008-053511/02-pull-request-lifecycle/with-skill/render/eval-diagram-1.png` | |
| 02-pull-request-lifecycle | baseline | `runs/20261008-053511/02-pull-request-lifecycle/baseline/render/eval-diagram-1.png` | |
| 03-ci-pipeline | with-skill | `runs/20261008-053511/03-ci-pipeline/with-skill/render/eval-diagram-1.png` | |
| 03-ci-pipeline | baseline | `runs/20261008-053511/03-ci-pipeline/baseline/agent-files/ci-cd-pipeline.svg` | |
| 04-browser-cache | with-skill | `runs/20261008-053511/04-browser-cache/with-skill/render/eval-diagram-1.png` | |
| 04-browser-cache | baseline | `runs/20261008-053511/04-browser-cache/baseline/agent-files/browser-cache.svg` | |

## Observations from this run

- **No skill bug found.** Every with-skill run saved `diagram.mmd` and `caption.md`, passed `diagram_check.py`, rendered with `render_diagram.py` and replied with the code, caption and paths. Topic 04 used a second layout fix round to remove crossing edges, as the workflow describes.
- **Type for topic 03 (topic vs skill rule, for the maintainer).** The topic expects `flowchart LR`; the skill chose `flowchart TD` in both runs (this run and the earlier one, see below). The pipeline has pass/fail decisions, and the skill's type list maps "steps and decisions" to `flowchart TD` and "data that moves through components" to `flowchart LR`. Either the topic's expected type or the skill's type guidance should change.
- **Simplification for the budget (topic 03).** With 12 nodes (the budget limit) the with-skill agent made staging a fixed step and put the health check after production only; the judge scored accuracy 4. The source says "many teams" use staging.
- **The baseline usually does not answer in Mermaid.** Asked to "draw a diagram", the baseline wrote a hand-made SVG file in 3 of 4 topics (both runs). The harness judges that SVG source but has no Mermaid metrics for it. The one Mermaid baseline (topic 02) used `<br/>` labels and long labels, so it failed the checker (it still rendered).
- **Judge reads source, not pictures.** The judge compares Mermaid with SVG source text, and does not see captions. Its "faster" choice is an estimate; the maintainer notes above are the real check.
- **Earlier run `20261008-052951`.** The first run had no SVG fallback, so the judge was skipped for topics 01, 03 and 04 (the baseline had no Mermaid). Its with-skill figures were the same: 4/4 checker pass, 4/4 rendered, 0 overruns, `flowchart TD` for topic 03. Cost about $1.78. The harness was then changed to judge saved SVG files.
