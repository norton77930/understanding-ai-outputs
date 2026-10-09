# ste-writing eval results

Newest run first. Trigger-eval results are in `triggers/RESULTS.md`.

## Explain set (`--set explain`)

Topics in `explain/`, approved by the maintainer on 2026-10-09 (issue #48). Model: claude CLI default, `claude` 2.1.295. Skill state: `feat/ste-explain` (`cde11fd`, keep-articles rule and "80% STE means relaxed"). Runs and review pages are local (`runs/` is git-ignored).

### Run 20261009-100349 (both arms told to answer in Traditional Chinese)

Command: `python evals/ste-writing/run_eval.py --set explain --suffix "請用繁體中文回答。"` (seed `20261009-100349`). The suffix goes to both arms. Answers 4/4 in both arms, all in zh-TW, so the checker has no metrics ("metrics not available"). Cost: with-skill $0.72 (96 s), baseline $0.60 (93 s). The review page renders the Markdown answers (pinned marked + DOMPurify, `5cd1df9`); the maintainer rated the rendered page and counted layout (headings, numbered steps, tables) as part of readability.

| Topic | A understanding | A readability | B understanding | B readability | Better (A/B/tie) | Notes | With-skill was (from key) |
|---|---|---|---|---|---|---|---|
| 01-idempotency | 5 | 4 | 5 | 5 | B | | B |
| 02-python-venv | 5 | 5 | 5 | 4 | A | | A |
| 03-database-index | 5 | 5 | 5 | 5 | tie | about the same | A |
| 04-port-in-use | 5 | 4 | 5 | 5 | B | | A |

**Result: the skill won 2, tied 1 and lost 1.** Understanding 5 everywhere in both arms. Readability: with-skill 5, 5, 5, 4 (mean 4.75); baseline 4, 4, 5, 5 (mean 4.5). Better: the with-skill answer on 01 and 02, tie on 03, the baseline answer on 04.

### Run 20261009-092712 (request as written, no language line)

Command: `python evals/ste-writing/run_eval.py --set explain` (seed `20261009-092712`). Not rated: the arms answered in different languages, so a readability comparison would rate the language, not the writing.

- **Finding: without the skill, Claude answered all four zh-TW requests in English.** ASD-STE100 is an English specification, so a plain "用 STE 解釋：..." was read as "write STE English". The with-skill arm answered in zh-TW and applied the STE principles, as the skill says for non-English conversations. For a zh-TW user this is a real difference in favor of the skill.
- The baseline's English answers were good STE by the checker: 161 sentences, 0% over the length limit, 0% passive or progressive. Cost: with-skill $0.76 (120 s), baseline $0.66 (114 s).

The rewrite set's history (LLM judge, run `20261007-065154`: with-skill 0% over limit, 0% passive+progressive, meaning 5/5, readability 6-0) is in PR #13 and `README.md`.
