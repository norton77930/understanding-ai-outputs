# diagram-explainer eval results

Newest run first. The earlier run is kept below as history: it was scored by an LLM judge reading source text, which the next run does not use, so its figures are not comparable with the blind two-axis ratings.

## Run 20261009-092505 (round 2 topics, blind two-axis rating)

Run `20261009-092505` (2026-10-09). Model: claude CLI default. `claude` 2.1.295. Workers 4, timeout 900 s per call, A/B seed `20261009-092505`. Command: `python evals/diagram-explainer/run_eval.py` (plugin dir: the `feat/diagram-explainer` worktree after #46, `a53ca14`). Full report: `evals/diagram-explainer/runs/20261009-092505/report.md` (git-ignored, local only).

### Automated metrics

- with-skill: checker pass 4/4, rendered 4/4, label overruns 0, images 4/4, cost $1.57, 514 s agent time.
- baseline: checker pass 1/4 (3 answered in Mermaid, 1 hand-written SVG), label overruns 2, images 4/4, cost $0.76, 238 s agent time.
- Total: cost $2.33, agent time 752 s, wall time 276 s.

| Topic | Arm | Diagrams (from) | Type (expected) | Checker | Issues | Nodes | Messages | Label overruns | Render | Images | Turns | Cost | Time |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01-card-payment | with-skill | 1 (file) | sequenceDiagram (ok) | PASS | 0 | 4 | 11 | 0 | ok | 1 | 14 | $0.52 | 167 s |
| 01-card-payment | baseline | 1 (reply) | sequenceDiagram (ok) | FAIL | 1 | 4 | 12 | 1 | ok | 1 | 2 | $0.10 | 25 s |
| 02-delivery-order | with-skill | 1 (file) | stateDiagram-v2 (ok) | PASS | 0 | 6 | n/a | 0 | ok | 1 | 11 | $0.31 | 124 s |
| 02-delivery-order | baseline | 1 (reply) | stateDiagram-v2 (ok) | PASS | 0 | 6 | n/a | 0 | ok | 1 | 2 | $0.11 | 27 s |
| 03-video-processing | with-skill | 1 (file) | flowchart LR (ok) | PASS | 0 | 13 | n/a | 0 | ok | 1 | 11 | $0.42 | 106 s |
| 03-video-processing | baseline | 1 (reply) | flowchart TD (expected flowchart LR) | FAIL | 1 | 9 | n/a | 1 | ok | 1 | 2 | $0.22 | 58 s |
| 04-kubernetes-structure | with-skill | 1 (file) | flowchart LR (expected flowchart) | PASS | 0 | 11 | n/a | 0 | ok | 1 | 11 | $0.31 | 117 s |
| 04-kubernetes-structure | baseline | 1 (file) | svg (expected flowchart) | n/a | n/a | n/a | n/a | n/a | n/a | 1 | 4 | $0.33 | 127 s |

### Maintainer ratings (blind, two axes)

Open `evals/diagram-explainer/runs/20261009-092505/review.html` (local, git-ignored). Per topic it shows the "Reader should understand" points and image A and image B in a random order. Rate each image 1-5 on understanding (理解) and presentation (呈現), pick the better image (A / B / tie), and only then look up the key in `report.json` (`ab_key`) to fill the last column.

| Topic | A understanding | A presentation | B understanding | B presentation | Better (A/B/tie) | Notes | With-skill was (from key) |
|---|---|---|---|---|---|---|---|
| 01-card-payment | 5 | 4 | 5 | 5 | B |  | A |
| 02-delivery-order | 5 | 4 | 5 | 5 | B |  | B |
| 03-video-processing | 5 | 5 | 5 | 5 | tie | about the same | B |
| 04-kubernetes-structure | 5 | 5 | 5 | 4 | A |  | A |

**Result: the skill won 2, tied 1 and lost 1.** With-skill 5/4 (01), 5/5 (02), 5/5 (03), 5/5 (04); baseline 5/5, 5/4, 5/5, 5/4. Understanding 5 everywhere in both arms. Presentation mean: with-skill 4.75 (first run 3.75), baseline 4.5 (first run 4.75). Better: baseline on 01, the with-skill diagram on 02 and 04, tie on 03.

### Observations from this run

- The baseline answered in Mermaid on 3 of 4 topics this time (hand-written SVG only on 04); two of those failed the checker on label length, and 03 came out as `flowchart TD` for a pipeline.
- The with-skill arm used `flowchart LR` for 04 (a containment topic, expected a subgraph flowchart; it did use subgraphs) and stayed within the soft size limits except 03 (13 nodes, a warning only).
- The with-skill arm costs about twice the baseline ($1.57 vs $0.76): it saves files, checks, renders and runs a layout check.

- <fill after the run>

## Run 20261008-053511 (round 1 topics, LLM judge, history)

Run `20261008-053511` (2026-10-08). Model: claude CLI default (`claude` 2.1.293). Both arms per topic, workers 4, timeout 900 s per call, judge seed `20261008-053511`. Command: `python evals/diagram-explainer/run_eval.py --plugin-dir D:/tmp/export-feat-diagram-explainer` (an export of `feat/diagram-explainer` whose plugin manifest lists the skill). Full report: `evals/diagram-explainer/runs/20261008-053511/report.md` (git-ignored, local only).

**Topics:** the round-1 draft topics (now in `topics/round1/`; two of the four were in English). This run had an LLM judge that read the source text, not the pictures. The judge is gone from the harness (issue #47); the maintainer's blind rating of the rendered images is added below.

### Summary

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

### Maintainer ratings (blind, rendered images)

Added 2026-10-09. The maintainer rated the rendered images of this run blind. One axis per column: understanding (how well the "Reader should understand" points came across) and presentation (layout, colors, text size, visual quality), each 1-5.

| Topic | With-skill understanding | With-skill presentation | Baseline understanding | Baseline presentation | Better | Notes |
|---|---|---|---|---|---|---|
| 01-oauth-login | 5 | 4 | 5 | 4 | tie | |
| 02-pull-request-lifecycle | 5 | 4 | 5 | 5 | baseline | |
| 03-ci-pipeline | 5 | 3 | 5 | 5 | baseline | |
| 04-browser-cache | 5 | 4 | 5 | 5 | baseline | |

**Result: the baseline image was preferred on 3 of 4 topics, one tie.** Understanding was 5 for both arms on every topic, so the content was not the difference. Presentation: with-skill 4, 4, 3, 4 against baseline 4, 5, 5, 5. The LLM judge had picked with-skill as faster to understand in 3 of 4 topics; the human rating went the other way, because the judge compared source text and could not see how the pictures look. This is why the judge was dropped.

### Observations from this run

- **No skill bug found.** Every with-skill run saved `diagram.mmd` and `caption.md`, passed `diagram_check.py`, rendered with `render_diagram.py` and replied with the code, caption and paths. Topic 04 used a second layout fix round to remove crossing edges, as the workflow describes.
- **Type for topic 03 (topic vs skill rule, for the maintainer).** The topic expects `flowchart LR`; the skill chose `flowchart TD` in both runs (this run and the earlier one, see below). The pipeline has pass/fail decisions, and the skill's type list maps "steps and decisions" to `flowchart TD` and "data that moves through components" to `flowchart LR`. Either the topic's expected type or the skill's type guidance should change.
- **Simplification for the budget (topic 03).** With 12 nodes (the budget limit) the with-skill agent made staging a fixed step and put the health check after production only; the judge scored accuracy 4. The source says "many teams" use staging.
- **The baseline usually does not answer in Mermaid.** Asked to "draw a diagram", the baseline wrote a hand-made SVG file in 3 of 4 topics (both runs). The harness judges that SVG source but has no Mermaid metrics for it. The one Mermaid baseline (topic 02) used `<br/>` labels and long labels, so it failed the checker (it still rendered).
- **Judge reads source, not pictures.** The judge compared Mermaid with SVG source text, and did not see captions. Its "faster" choice was an estimate; the blind rating above is the real check, and it disagreed with the judge on 3 of 4 topics.
- **Earlier run `20261008-052951`.** The first run had no SVG fallback, so the judge was skipped for topics 01, 03 and 04 (the baseline had no Mermaid). Its with-skill figures were the same: 4/4 checker pass, 4/4 rendered, 0 overruns, `flowchart TD` for topic 03. Cost about $1.78. The harness was then changed to judge saved SVG files.
