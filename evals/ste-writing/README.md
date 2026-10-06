# ste-writing eval

Evals live here, outside `skills/ste-writing/`, so installing the skill does not ship them.

## Run it

```
python evals/ste-writing/run_eval.py                  # all eight passages, both arms, judge, report
python evals/ste-writing/run_eval.py --passages 01,03 # a subset (id or number prefix)
python evals/ste-writing/run_eval.py --strictness strict   # strict arm (default: relaxed)
python evals/ste-writing/run_eval.py --dry-run        # print the commands, call nothing
python evals/ste-writing/run_eval.py --model sonnet   # pick a model (default: claude CLI default)
python -m unittest discover -s evals/ste-writing -p test_run_eval.py   # unit tests (pure logic only)
```

Needs the `claude` CLI on `PATH` and Python 3.12 (standard library only). One full run is 16 rewrite calls plus 8 judge calls. Output goes to `evals/ste-writing/runs/<timestamp>/` (git-ignored): one `.txt` per passage and arm, the judge replies, `report.md` and `report.json`.

The passages are in `passages/` and are DRAFT until the maintainer approves them (see `passages/README.md`).

## What one run does

1. Ask an agent "Rewrite the following text in STE." for each passage (strict: "Rewrite the following text in strict STE."). The request is the same in both arms.
   - with-skill: `claude -p ... --plugin-dir <repo root>`
   - baseline: the same command without `--plugin-dir`
2. Measure each output with `skills/ste-writing/scripts/ste_check.py` (CLI only). Relaxed runs use `--strictness relaxed`. Strict runs use `--strictness strict --replacements skills/ste-writing/references/replacements.md`, so the report also shows replacement-list hits per arm. The Chinese passages report "metrics not available".
3. One judge call per passage sees the original and both outputs in randomized A/B order (reproducible from `--seed`). It returns `{meaning_a, meaning_b, more_readable, reason}`. The harness maps A/B back to arms.
4. Write the report. Verdict is for the with-skill arm against the relaxed thresholds from issue #3:
   - at least 90% of sentences within the length limit
   - passive plus progressive at most 5% of sentences
   - meaning at least 4/5 on every passage
   - readability preferred over baseline overall (with-skill wins greater than baseline wins; ties count for neither)
   - strict only: zero replacement-list hits in the with-skill arm (baseline hits are reported, not gated)

Sentence counts are pooled over all English passages. The Chinese passages are listed as manual review with their outputs shown; their judge scores are informational and do not count in the verdict. The verdict is `INCOMPLETE` (exit 2) when a call failed and data is missing.

## Trigger eval

`triggers/` holds a separate eval: 20 prompts (ten should trigger, ten should not) that check the skill description fires only on explicit STE requests. It uses skill-creator's `run_eval.py`, not `run_eval.py` in this folder. See `triggers/README.md` for the set and the decisions, and `triggers/RESULTS.md` for the latest results.

## Isolation: why these `claude` flags

The user-level `~/.claude/CLAUDE.md` and settings can force the reply language and style. That would contaminate both arms. Every call therefore uses:

- `--setting-sources project,local`: leaves out the user settings source. This also drops the user-level `CLAUDE.md`, rules and enabled plugins. Verified: without it, a plain English prompt got a zh-TW answer; with it, the answer was English.
- `--strict-mcp-config`: no MCP servers (no connector noise).
- `--no-session-persistence`: no saved sessions.
- `--output-format json`: gives the result text plus turns, cost and model.
- Run from a neutral scratch directory outside the repo (default: `<system temp>/ste-writing-eval`; set `STE_EVAL_CWD` to change it), so no project `CLAUDE.md` or `.claude/` settings from this repo apply.
- The judge also uses `--tools ""` and no plugin.

Options that were considered and not used:

- `--bare`: needs `ANTHROPIC_API_KEY` (it never reads OAuth), and it skips plugin sync. Not usable with a subscription login.
- `--safe-mode`: disables installed plugins and customizations, which risks disabling the `--plugin-dir` plugin too, and does not address user memory more cleanly than `--setting-sources`.
- `--system-prompt` / `--append-system-prompt`: would change the agent in both arms and would not remove the user `CLAUDE.md`.

## Known limits

- The baseline arm sometimes adds commentary ("Changes I made") to its rewrite. It is kept in the output and is measured and judged as is, because the request is the same in both arms.
- The checker is heuristic (see its docstring). Counts are approximate.
- LLM judge scores are noisy. One run is a baseline, not proof.
