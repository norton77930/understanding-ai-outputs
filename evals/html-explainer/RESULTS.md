# html-explainer eval results

Newest run first. The earlier run is kept below as history; its single-axis ratings are not comparable with the two-axis ratings of the next run.

## Run 20261013-041820 (round 5: Explore stage, issue #63)

2026-10-13. Model: claude CLI default (`claude` 2.1.296). One run per topic and arm, workers 2, timeout 1200 s per agent run. Command: `python evals/html-explainer/run_eval.py` (plugin dir: branch `feat/63-explore-stage`, PR #66). A/B seed 41915. Full report: `evals/html-explainer/runs/20261013-041820/report.md` (git-ignored, local only).

**Topics:** round 5 (draft 2026-10-13, run before maintainer approval). All three send the default request. 01 and 02 have numbers and a process the reader can run; 03 is meant as the structural control.

### Automated metrics

**Verdict (with-skill arm): PASS.**

- with-skill: page_check 3/3, render_check 3/3, cost $3.16, 1092 s agent time.
- baseline: page_check 2/3 (missing-dark-mode on 03), render_check 3/3, cost $2.64, 984 s agent time.
- Total: $5.79, 2075 s agent time.

| Topic | Request | Arm | page_check (issue rules) | render_check | No overflow at 390 | Size | Turns | Cost | Wall time |
|---|---|---|---|---|---|---|---|---|---|
| 01-token-bucket | default | with-skill | PASS | PASS | PASS | 32.6 KB | 18 | $1.07 | 345 s |
| 01-token-bucket | default | baseline | PASS | PASS | PASS | 40.7 KB | 17 | $1.18 | 419 s |
| 02-retry-backoff | default | with-skill | PASS | PASS | PASS | 28.9 KB | 23 | $1.04 | 406 s |
| 02-retry-backoff | default | baseline | PASS | PASS | PASS | 28.0 KB | 22 | $0.92 | 352 s |
| 03-jwt-structure | default | with-skill | PASS | PASS | PASS | 31.4 KB | 22 | $1.04 | 341 s |
| 03-jwt-structure | default | baseline | FAIL (missing-dark-mode) | PASS | PASS | 25.1 KB | 6 | $0.54 | 213 s |

### Explore stage (from the with-skill replies)

- 01, 02: an Explore stage at the end, as expected (01: four sliders, presets, "播放 20 秒"; 02: first wait, cap, retry count, jitter, presets, "執行" with an animated chart).
- 03: the page also ends with a 「動手試」 stage (change `sub` or re-sign, then send to the server), and the reply gives no skip reason. The control did not hold: changing the payload and watching the check fail is a process the reader can run, so the skill treated the topic as runnable. A purer structural control would be needed to test the skip rule.

### Control re-run: 04-dns-record-types (run 20261013-052151)

Added after this run because 03 did not hold as a control. Command: `python evals/html-explainer/run_eval.py --topics 04`. A/B seed 443708. Full report: `evals/html-explainer/runs/20261013-052151/report.md` (git-ignored, local only).

| Topic | Request | Arm | page_check (issue rules) | render_check | No overflow at 390 | Size | Turns | Cost | Wall time |
|---|---|---|---|---|---|---|---|---|---|
| 04-dns-record-types | default | with-skill | PASS | PASS | PASS | 31.1 KB | 17 | $0.89 | 322 s |
| 04-dns-record-types | default | baseline | PASS | PASS | PASS | 22.1 KB | 3 | $0.39 | 116 s |

- Verdict (with-skill): PASS. Total $1.28, 438 s agent time.
- The skip rule did not fire here either: the with-skill page ends with an Explore stage (add and delete records, run queries, a "CNAME 衝突" preset), and the reply gives no skip reason. The page also adds lookup steps the source does not describe (CNAME to an IP, an MX "播放", an NS query).
- Reading: the rule "skip only for a purely definitional or structural topic" does not stop the agent, because almost any topic can be turned into something to run. Whether that hurts understanding is for the blind rating to show; if it does, the skip rule needs a sharper test (for example: skip when the source states no number and no process).

### Maintainer ratings (blind, two axes)

Pending. Rate 01-03 on `runs/20261013-041820/review.html` and 04 on `runs/20261013-052151/review.html`, same procedure and axes as round 4.

| Topic | A understanding | A presentation | B understanding | B presentation | Better (A/B/tie) | Notes | With-skill was (from key) |
|---|---|---|---|---|---|---|---|
| 01-token-bucket | | | | | | | |
| 02-retry-backoff | | | | | | | |
| 03-jwt-structure | | | | | | | |
| 04-dns-record-types | | | | | | | |

## Run 20261011-103229 (round 4: blueprint on request, visible assumptions, issue #55)

2026-10-11. Model: claude CLI default (`claude` 2.1.296). One run per topic and arm, workers 4, timeout 1200 s per agent run. Command: `python evals/html-explainer/run_eval.py --workers 4` (plugin dir: branch `feat/55-html-styles`, PR #60). A/B seed 331874. Full report: `evals/html-explainer/runs/20261011-103229/report.md` (git-ignored, local only).

**Topics:** round 4 (approved 2026-10-11). 01 and 02 send a blueprint request ("用工程圖紙（blueprint）風格做一個互動網頁…") to both arms; 03 and 04 send the default request. 01, 02 and 04 are AI output with stated assumptions; 03 has none.

### Automated metrics

**Verdict (with-skill arm): PASS.**

- with-skill: page_check 4/4, render_check 4/4, cost $3.33, 1019 s agent time.
- baseline: page_check 2/4 (missing-dark-mode on both blueprint pages, 01 and 02), render_check 3/4 (01 overflows at 390 px), cost $2.45, 1337 s agent time.
- Total: $5.78, 2356 s agent time.

| Topic | Request | Arm | page_check (issue rules) | render_check | No overflow at 390 | Size | Turns | Cost | Wall time |
|---|---|---|---|---|---|---|---|---|---|
| 01-db-migration-plan | blueprint | with-skill | PASS | PASS | PASS | 24.0 KB | 19 | $0.94 | 338 s |
| 01-db-migration-plan | blueprint | baseline | FAIL (missing-dark-mode) | FAIL | FAIL | 24.1 KB | 3 | $0.46 | 140 s |
| 02-cache-proposal | blueprint | with-skill | PASS | PASS | PASS | 27.6 KB | 20 | $0.92 | 266 s |
| 02-cache-proposal | blueprint | baseline | FAIL (missing-dark-mode) | PASS | PASS | 32.7 KB | 16 | $0.80 | 256 s |
| 03-hash-table-resize | default | with-skill | PASS | PASS | PASS | 26.3 KB | 18 | $0.90 | 250 s |
| 03-hash-table-resize | default | baseline | PASS | PASS | PASS | 29.8 KB | 1 | $0.73 | 836 s |
| 04-hosting-cost-estimate | default | with-skill | PASS | PASS | PASS | 18.1 KB | 13 | $0.57 | 166 s |
| 04-hosting-cost-estimate | default | baseline | PASS | PASS | PASS | 20.7 KB | 7 | $0.46 | 105 s |

### Maintainer ratings (blind, two axes)

Rated by the maintainer on 2026-10-11 on the published review page (each page opened and used in an in-page viewer). Same procedure and axes as the run below; for 01 and 02 also judge how well the page carries the blueprint look that the request names, and for every topic whether assumptions are shown as assumptions (and none invented).

| Topic | A understanding | A presentation | B understanding | B presentation | Better (A/B/tie) | Notes | With-skill was (from key) |
|---|---|---|---|---|---|---|---|
| 01-db-migration-plan | 5 | 5 | 5 | 5 | tie | A more interactive, B easier to understand (A互動性好，B比較易懂) | B |
| 02-cache-proposal | 5 | 5 | 5 | 5 | tie | A more interactive, B easier to understand (A互動性好，B比較易懂) | B |
| 03-hash-table-resize | 5 | 5 | 5 | 4 | A | | A |
| 04-hosting-cost-estimate | 5 | 5 | 5 | 4 | A | A more interactive (A互動性較好) | B |

Result: with-skill better on 1 topic (03), tie on 2 (01, 02), worse on 1 (04). Understanding is 5 in every page.

- (a) Blueprint on request (01, 02): ties. Both times the maintainer found the with-skill page easier to understand and the baseline page more interactive. The baseline pages here are larger dashboards (an animated request simulator, a live chart, check-off cards); the with-skill pages are step-through panels with a summary.
- (b) Default pages (03, 04): one better and one worse, so no clear regression and no clear gain. On 04 the with-skill page (a receipt step-through, a quiz and three sliders) was rated less interactive than the baseline (sliders, a scenario chart and a sensitivity table): presentation 4 vs 5.
- Follow-up signal for html-explainer: the skill's pages explain well but can come out less interactive than the baseline. This is a design note for a later round, not a blocker for #55.

## Run 20261009-021002 (round 3: new topics, bespoke design guidance)

2026-10-09. Model: claude CLI default. One run per topic and arm, workers 4, timeout 1200 s per agent run. Command: `python evals/html-explainer/run_eval.py --workers 4`. Skill state: `e854aff` (bare skeleton, "Design" section, math-consistency layout check). Full report: `evals/html-explainer/runs/20261009-021002/report.md` (git-ignored, local only).

**Topics:** a new round-3 set (Monty Hall, LRU cache, base rate, pendulum), all zh-TW, approved 2026-10-09, chosen so the maintainer rates topics not seen in earlier rounds. Round 1-2 topics are in `topics/round1/`.

### Automated metrics

**Verdict (with-skill arm): PASS.**

- with-skill: page_check 4/4, render_check 4/4, cost $2.79, 809 s agent time.
- baseline: page_check 3/4 (missing-dark-mode on 02), render_check 4/4, cost $2.50, 782 s agent time.
- Total: $5.28, 1591 s agent time; about 7 min wall time with 4 parallel runs.

| Topic | Lang | Arm | page_check (issue rules) | render_check | Console / page errors | No overflow at 390 | Interaction | Size | Single file | HTML files | Turns | Cost | Wall time |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01-monty-hall | zh-TW | with-skill | PASS | PASS | 0 / 0 | PASS | button | 23.5 KB | yes | 1 | 17 | $0.69 | 214 s |
| 01-monty-hall | zh-TW | baseline | PASS | PASS | 0 / 0 | PASS | button | 29.4 KB | yes | 1 | 18 | $0.80 | 288 s |
| 02-lru-cache | zh-TW | with-skill | PASS | PASS | 0 / 0 | PASS | button | 21.0 KB | yes | 1 | 14 | $0.63 | 162 s |
| 02-lru-cache | zh-TW | baseline | FAIL (missing-dark-mode) | PASS | 0 / 0 | PASS | button | 21.0 KB | yes | 1 | 2 | $0.35 | 92 s |
| 03-base-rate | zh-TW | with-skill | PASS | PASS | 0 / 0 | PASS | button | 21.8 KB | yes | 1 | 16 | $0.68 | 194 s |
| 03-base-rate | zh-TW | baseline | PASS | PASS | 0 / 0 | PASS | button | 22.9 KB | yes | 1 | 9 | $0.55 | 174 s |
| 04-pendulum | zh-TW | with-skill | PASS | PASS | 0 / 0 | PASS | button | 27.7 KB | yes | 1 | 16 | $0.79 | 239 s |
| 04-pendulum | zh-TW | baseline | PASS | PASS | 0 / 0 | PASS | button | 31.5 KB | yes | 1 | 12 | $0.79 | 229 s |

### Maintainer ratings (blind, two axes)

Open `evals/html-explainer/runs/20261009-021002/review.html`. Same procedure and axes as the run below.

| Topic | A understanding | A presentation | B understanding | B presentation | Better (A/B/tie) | Notes | With-skill was (from key) |
|---|---|---|---|---|---|---|---|
| 01-monty-hall | 5 | 5 | 5 | 5 | tie | about the same | A |
| 02-lru-cache | 5 | 5 | 5 | 5 | tie | about the same | B |
| 03-base-rate | 5 | 4 | 5 | 5 | B | content about the same; B has better animation | B |
| 04-pendulum | 5 | 5 | 5 | 5 | tie | about the same | A |

**Result: parity, with one win for the skill.** With-skill 5/5 on both axes for all four topics. Baseline 5/5 on 01, 02 and 04 and 5/4 on 03. Better page: tie on 01, 02 and 04; the with-skill page on 03 (the maintainer: the content was about the same, the difference was the animation). The baseline page for 02 had no dark mode (page_check). Compared with rounds 1 and 2 (baseline preferred 4/4 both times), removing the styled skeleton and asking for a bespoke design closed the presentation gap. The topics are new in this round, so part of the change may come from the topics.

## Run 20261009-011139 (approved topics, two rating axes)

2026-10-09. Model: claude CLI default. `claude` 2.1.294. One run per topic and arm, workers 4, timeout 1200 s per agent run, A/B seed 261113. Command: `python evals/html-explainer/run_eval.py --workers 4` (plugin dir: the `feat/html-explainer` worktree after #38). Full report: `evals/html-explainer/runs/20261009-011139/report.md` (git-ignored, local only).

**Topics:** the approved set (issue #32), all zh-TW. English output is covered by the trigger eval and the automated checks, not by this rating.

### Automated metrics

**Verdict (with-skill arm): PASS.**

- with-skill: page_check 4/4, render_check 4/4, cost $2.77, 745 s agent time.
- baseline: page_check 2/4 (missing-dark-mode on 02 and 03), render_check 4/4, cost $2.60, 862 s agent time.
- Total: $5.36, 1607 s agent time; about 7 min wall time with 4 parallel runs.

| Topic | Lang | Arm | page_check (issue rules) | render_check | Console / page errors | No overflow at 390 | Interaction | Size | Single file | HTML files | Turns | Cost | Wall time |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01-learning-rate | zh-TW | with-skill | PASS | PASS | 0 / 0 | PASS | button | 21.2 KB | yes | 1 | 24 | $0.85 | 233 s |
| 01-learning-rate | zh-TW | baseline | PASS | PASS | 0 / 0 | PASS | button | 40.0 KB | yes | 1 | 21 | $1.13 | 403 s |
| 02-bubble-sort | zh-TW | with-skill | PASS | PASS | 0 / 0 | PASS | button | 17.3 KB | yes | 1 | 20 | $0.63 | 146 s |
| 02-bubble-sort | zh-TW | baseline | FAIL (missing-dark-mode) | PASS | 0 / 0 | PASS | button | 22.2 KB | yes | 1 | 3 | $0.41 | 139 s |
| 03-flexbox-space | zh-TW | with-skill | PASS | PASS | 0 / 0 | PASS | button | 16.9 KB | yes | 1 | 18 | $0.66 | 188 s |
| 03-flexbox-space | zh-TW | baseline | FAIL (missing-dark-mode) | PASS | 0 / 0 | PASS | button | 24.9 KB | yes | 1 | 2 | $0.48 | 129 s |
| 04-compound-interest | zh-TW | with-skill | PASS | PASS | 0 / 0 | PASS | button | 17.2 KB | yes | 1 | 19 | $0.63 | 177 s |
| 04-compound-interest | zh-TW | baseline | PASS | PASS | 0 / 0 | PASS | button | 22.1 KB | yes | 1 | 12 | $0.58 | 191 s |

### Maintainer ratings (blind, two axes)

Open `evals/html-explainer/runs/20261009-011139/review.html` (local, git-ignored). Per topic it shows the "Reader should understand" points, links to page A and page B (try the interaction), and the 390 px and 1280 px light screenshots. Rate each page 1-5 on two axes, then pick the better page, and only then look up the key in `report.json` (`ab_key`) to fill the last column.

- **Understanding (理解):** how well you understood the topic's "Reader should understand" points after using the page.
- **Presentation (互動與呈現, interaction and presentation):** how good the interaction, layout and visual design are.

| Topic | A understanding | A presentation | B understanding | B presentation | Better (A/B/tie) | Notes | With-skill was (from key) |
|---|---|---|---|---|---|---|---|
| 01-learning-rate | 5 | 5 | 3 | 3 | A |  | B |
| 02-bubble-sort | 5 | 4 | 5 | 5 | B |  | A |
| 03-flexbox-space | 5 | 4 | 5 | 5 | B |  | A |
| 04-compound-interest | 4 | 3 | 5 | 4 | B |  | A |

**Result: the baseline page was preferred on all four topics again, but the gap narrowed.** With-skill understanding 3, 5, 5, 4 (baseline 5, 5, 5, 5): a tie on 02 and 03. With-skill presentation 3, 4, 4, 3 (baseline 5, 5, 5, 4). The remaining gap is mostly presentation. In 01 the baseline page ran the three learning rates side by side at once, showed a live step calculation and ended with a summary; the with-skill page used the same plain card look as the design-baseline skeleton on every topic and drew a stray arc in section 2. The with-skill pages grew from 9-14 KB (first run) to 17-21 KB.

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
