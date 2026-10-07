# Trigger eval results

Date: 2026-10-07. Model: `claude-opus-5-5`. Tool: skill-creator `run_eval.py` (patched scratch copy, see below). 3 runs per query, threshold 0.5.

## Final result

**20/20 passed (0 errors; limit is 2).** The description in `skills/ste-writing/SKILL.md` was not changed.

Description under test:

> Write or rewrite text in Simplified Technical English (STE) style. Use ONLY when the user explicitly asks for STE, Simplified Technical English, ASD-STE100, or "80% STE" writing, such as "explain X in STE" or "rewrite this in STE". Never use for ordinary answers.

| Result | Query (start) | Triggered |
| --- | --- | --- |
| PASS | can you explain how Kubernetes readiness probes work in STE? ... | 3/3 |
| PASS | Rewrite this in Simplified Technical English please: "Prior to the commencement ..." | 3/3 |
| PASS | ASD-STE100 style please. what does git rebase --onto actually do? ... | 3/3 |
| PASS | walk me through the OAuth 2.0 PKCE flow, 80% STE is fine ... | 3/3 |
| PASS | strict STE: describe how to rotate the TLS cert on our nginx box ... | 3/3 |
| PASS | 用 STE 解釋一下 Docker 的 volume 跟 bind mount 差在哪裡 ... | 3/3 |
| PASS | ste pls - explain what a mutex is ... | 3/3 |
| PASS | Going forward I want your answers in Simplified Technical English. ... | 3/3 |
| PASS | This paragraph from our README is a mess: "The utilization of the cache ..." (full STE) | 3/3 |
| PASS | explain the CAP theorem the way Karpathy suggested, like ASD-STE100 ... | 3/3 |
| PASS | my manager says my incident summary is too dense ... make this simpler? | 0/3 |
| PASS | give me a plain English summary of the attached 40 page GDPR ... | 0/3 |
| PASS | ELI5: how does a blockchain actually work? ... | 0/3 |
| PASS | write a technical spec for a token-bucket rate limiter service ... | 0/3 |
| PASS | we're hiring a new STE for the payments team (software test engineer ...) | 0/3 |
| PASS | simplify this python function, it has four nested for loops ... | 0/3 |
| PASS | translate this paragraph into simple Chinese so my mom can read it ... | 0/3 |
| PASS | write the maintenance procedure for replacing the hydraulic pump filter ... | 0/3 |
| PASS | change the passive voice in this paragraph to active voice ... | 0/3 |
| PASS | is ASD-STE100 still maintained? who publishes it ... | 0/3 |

## Iteration history

| Run | Description | Result | Valid? |
| --- | --- | --- | --- |
| 1 (stock script, user settings on) | original | 10/20 (all 10 positives failed) | No: harness artifact |
| 2 (stock script, `--setting-sources project,local`) | original | 10/20 | No: same artifact |
| 3 (draft description with "invoke at once, before any other tool" wording) | tuned draft | 10/20 | No: same artifact |
| 4 (isolated run directories) | original | **20/20** | Yes |

Cause of the invalid runs: the harness writes each parallel run's command file into one shared directory, so each `claude -p` call saw up to 8 skills with the same description and often called another run's copy; the harness then counted a miss. Single-query checks with one worker triggered correctly. Fix in the scratch copy: one directory per run. After the fix the original description passed, so the tuning draft from run 3 was dropped and the original description was restored. No iteration of description tuning was kept.

## Deviations from stock skill-creator usage

Installed skill-creator files were not modified. A scratch copy (outside the repo, `%TEMP%`) had four changes:

1. Reads output with a thread and queue instead of `select.select` (not supported for pipes on Windows).
2. One scratch project directory per run (see above).
3. Extra flags `--no-session-persistence`, `--setting-sources project,local` and `--disallowedTools PushNotification` so the nested sessions do not save transcripts, load user-level instructions or send phone notifications.
4. UTF-8 file encoding.

`run_loop.py` was not used: it opens a browser report and its improvement step was not needed.
