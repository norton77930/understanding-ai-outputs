# Explain topics

Status: APPROVED by the maintainer on 2026-10-09, no changes (issue #48).

Four topics for the explain use of ste-writing ("Explain X in STE."), all written for this repo (no copied text). The harness reads `explain/0*.md` when it runs with `--set explain`. For each topic it sends the same request to both arms: the `## Request` line, then the `## Context` section when the file has one. The with-skill and baseline answers go to a blind review page, where the maintainer rates them.

| File | Type | Topic | Language |
|---|---|---|---|
| `01-idempotency.md` | Concept | What idempotency is and why API retries need it | zh-TW |
| `02-python-venv.md` | Procedure | Create a Python virtual environment and install the packages | zh-TW |
| `03-database-index.md` | Trade-off | What a database index gives and costs, and when to add one | zh-TW |
| `04-port-in-use.md` | Troubleshooting | Why a dev server fails with "address already in use", and the fix | zh-TW |

All four topics are in zh-TW, so the maintainer can rate every answer. Chinese answers have no checker metrics ("metrics not available"); English output stays covered by the rewrite set and the trigger eval. The "Reader should understand" bullets are the checklist for the rating. They are in zh-TW, so the rater can check them against the answer text directly.

## Review checklist

When you review or change a topic, check it for:

- Realistic content: something a developer would plausibly ask an agent to explain.
- Distinct from the other topics and from the topics of the other evals in this repo.
- No copied third-party text (ADR 0001): written originally, not taken from docs, Wikipedia or tutorials.
- Taiwan wording (程式, 資料, 伺服器, 預設, 連接埠).
- Facts and commands are correct, and the bullets cover what a good answer must explain.

## Approval

Not approved yet. Record the approval date and any changes from the review here.
