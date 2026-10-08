# html-explainer eval results

Newest run first. The earlier run is kept below as history; its single-axis ratings are not comparable with the two-axis ratings of the next run.

## Run <timestamp> (approved topics, two rating axes)

<date>. Model: <model>. `claude` <version>. One run per topic and arm, workers <n>, timeout <s> s per agent run, A/B seed <seed>. Command: `python evals/html-explainer/run_eval.py <options>`. Full report: `evals/html-explainer/runs/<timestamp>/report.md` (git-ignored, local only).

**Topics:** the approved set (issue #32), all zh-TW. English output is covered by the trigger eval and the automated checks, not by this rating.

### Automated metrics

**Verdict (with-skill arm): <PASS/FAIL/INCOMPLETE>.**

- with-skill: page_check <n>/4, render_check <n>/4, cost $<x>, <n> s agent time.
- baseline: page_check <n>/4, render_check <n>/4, cost $<x>, <n> s agent time.
- Total: $<x>, <n> s agent time; about <n> min wall time with <n> parallel runs.

| Topic | Lang | Arm | page_check (issue rules) | render_check | Console / page errors | No overflow at 390 | Interaction | Size | Single file | HTML files | Turns | Cost | Wall time |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (fill from report.md) | | | | | | | | | | | | | |

### Maintainer ratings (blind, two axes)

Open `evals/html-explainer/runs/<timestamp>/review.html` (local, git-ignored). Per topic it shows the "Reader should understand" points, links to page A and page B (try the interaction), and the 390 px and 1280 px light screenshots. Rate each page 1-5 on two axes, then pick the better page, and only then look up the key in `report.json` (`ab_key`) to fill the last column.

- **Understanding (理解):** how well you understood the topic's "Reader should understand" points after using the page.
- **Presentation (互動與呈現, interaction and presentation):** how good the interaction, layout and visual design are.

| Topic | A understanding | A presentation | B understanding | B presentation | Better (A/B/tie) | Notes | With-skill was (from key) |
|---|---|---|---|---|---|---|---|
| 01-learning-rate | | | | | | | |
| 02-bubble-sort | | | | | | | |
| 03-flexbox-space | | | | | | | |
| 04-compound-interest | | | | | | | |

**Result:** <fill after the maintainer rating>

### Observations from this run

- <fill after the run>

## Run 20261008-052926 (first drafts, one rating axis)

Run `20261008-052926` (2026-10-08). Model: claude CLI default (`claude` 2.1.293). One run per topic and arm, workers 4, timeout 1200 s per agent run, A/B seed 852557. Command: `python evals/html-explainer/run_eval.py --plugin-dir D:/tmp/export-feat-html-explainer --workers 4` (the plugin dir is an export of the `feat/html-explainer` branch tree, because the working tree's plugin manifest did not yet list html-explainer). Full report: `evals/html-explainer/runs/20261008-052926/report.md` (git-ignored, local only).

**Topics:** this run used the first drafts (01 and 03 in English). The approved topics (all zh-TW, issue #32) are used from the next run (#39).

### Automated metrics

**Verdict (with-skill arm): PASS.** with-skill: page_check 4/4, render_check 4/4, $1.95, 618 s agent time. baseline: page_check 2/4, render_check 4/4, $2.39, 608 s. Total $4.34; about 7 min wall time with 4 parallel runs.

| Topic | Lang | Arm | page_check (issue rules) | render_check | Console / page errors | No overflow at 390 | Interaction | Size | Single file | HTML files | Turns | Cost | Wall time |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01-learning-rate | en | with-skill | PASS | PASS | 0 / 0 | PASS | button | 12.9 KB | yes | 1 | 11 | $0.49 | 125 s |
| 01-learning-rate | en | baseline | PASS | PASS | 0 / 0 | PASS | button | 34.3 KB | yes | 1 | 12 | $0.84 | 215 s |
| 02-bubble-sort | zh-TW | with-skill | PASS | PASS | 0 / 0 | PASS | button | 10.9 KB | yes | 1 | 14 | $0.44 | 126 s |
| 02-bubble-sort | zh-TW | baseline | FAIL (missing-dark-mode) | PASS | 0 / 0 | PASS | button | 27.2 KB | yes | 1 | 3 | $0.48 | 119 s |
| 03-flexbox-space | en | with-skill | PASS | PASS | 0 / 0 | PASS | button | 8.7 KB | yes | 1 | 16 | $0.44 | 240 s |
| 03-flexbox-space | en | baseline | FAIL (missing-dark-mode) | PASS | 0 / 0 | PASS | button | 22.2 KB | yes | 1 | 4 | $0.41 | 102 s |
| 04-compound-interest | zh-TW | with-skill | PASS | PASS | 0 / 0 | PASS | button | 13.8 KB | yes | 1 | 15 | $0.58 | 127 s |
| 04-compound-interest | zh-TW | baseline | PASS | PASS | 0 / 0 | PASS | button | 26.1 KB | yes | 1 | 12 | $0.66 | 172 s |

The harness ran `page_check.py` and `render_check.py` itself on both arms' pages (the baseline agent does not know them). "Interaction" is the control the render check used; every page had a usable button.

### Maintainer ratings (blind)

Open `evals/html-explainer/runs/20261008-052926/review.html` (local, git-ignored). Per topic it shows page A and page B at 390 px and 1280 px (light mode) and links to both pages so you can try the interaction. Rate each page 1-5 on "did I understand the topic's Reader should understand points", pick the better page, and only then look up the key in `report.json` (`ab_key`) to fill the last column.

| Topic | Rating A (1-5) | Rating B (1-5) | Better page (A / B / tie) | Notes | With-skill was (A / B, from key) |
|---|---|---|---|---|---|
| 01-learning-rate | 5 | 3 | A |  | B |
| 02-bubble-sort | 5 | 3 | A |  | B |
| 03-flexbox-space | 5 | 3 | A |  | B |
| 04-compound-interest | 5 | 4 | A |  | B |

**Result: the baseline page was rated better on all four topics** (baseline 5/5 each; with-skill 3, 3, 3, 4). The key shows A = baseline for every topic; with seed 852557 the per-topic shuffle happened to give the same order four times (checked: `ab_orders` reproduces it; about a 1-in-16 chance, not a bug). The automated checks favor the skill (dark mode), but the human rating does not. One visible difference: the with-skill pages are 1.6x to 2.6x smaller, so they may carry less explanation.

### Observations from this run

- **No skill bug found.** All four with-skill agents followed the workflow: page in `out/html-explainer/<slug>/index.html`, static check and render check passed, layout check done, delivery with path, usage line and check status.
- **The layout check found real problems.** Each with-skill agent fixed one to three issues it saw in the screenshots: a formula cut off at phone width and an overlapping axis label (01), a wrong initial highlight and thin slider bars (02), invisible free-space stripes (03), an axis label on top of a value (04).
- **Remaining problem reported (01).** The agent said the chart labels on a phone are still small (about 10 px) and that loss values above 20 are drawn flat along the chart's top edge, with a note on the page. The skill asks it to report what is left after two fix rounds, and it did.
- **Baseline difference.** Two of four baseline pages had no `prefers-color-scheme: dark` style. All baseline pages were single files without overflow or errors, and 1.6x to 2.6x the size of the with-skill pages.
- **Turns.** Baseline topics 02 and 03 report 3 and 4 turns; treat turn counts as approximate (see the video-explainer RESULTS for the same effect).
