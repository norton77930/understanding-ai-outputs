# ste-writing trigger eval

Checks that the skill description fires only on explicit STE requests (issue #3, story 31). The set is `trigger-eval.json`: 20 queries in skill-creator's format (`{"query", "should_trigger"}`), ten that should trigger and ten that should not. Acceptance: at most 2 errors out of 20. Latest results are in `RESULTS.md`.

## Decisions

- **Should trigger:** an explicit request for STE, Simplified Technical English, ASD-STE100, "strict STE", "80% STE" or clearly equivalent wording, in any language, for explaining a topic or rewriting a given text.
- **Should not trigger:** ordinary answers, and near-misses that share words or ideas with STE:
  - "make this simpler", "plain English summary", "ELI5", "simplify this code", "translate to simple Chinese"
  - "use active voice" as a single edit (one rule, not the style)
  - technical writing (a spec, maintenance procedures for aircraft) with no STE request
  - "STE" as another abbreviation (software test engineer)
  - a question ABOUT the standard ("is ASD-STE100 still maintained?"). The user asks for facts, not for text written in STE, so the skill stays off.

## Run it

Tool: skill-creator's `scripts/run_eval.py` (do not modify the installed copy). It writes a temporary `.claude/commands/<name>-skill-<id>.md` file with the description, runs `claude -p <query>` and counts a hit when the model calls the `Skill` tool for that file. Each query runs 3 times. A query passes when the trigger rate is at least 0.5 (should trigger) or below 0.5 (should not trigger).

```
python -m scripts.run_eval --eval-set evals/ste-writing/triggers/trigger-eval.json \
  --skill-path skills/ste-writing --model <session model> --runs-per-query 3 --verbose
```

Notes from the recorded run (see `RESULTS.md`):

- Use a scratch project directory outside this repo for the temporary command files, so nothing is written into the repo or into `~/.claude`.
- The upstream script puts every parallel run's command file in the same directory. Parallel runs then see several skills with the same description, and the model may pick another run's copy. This gave false failures. Give each run its own scratch directory, or run with one worker.
- On Windows the script needs a patched copy: `select.select` does not work on pipes there.
- Add `--setting-sources project,local` so user-level instructions do not change the model behavior.
