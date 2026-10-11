# Eval topics

Status: DRAFT 2026-10-11 (round 4, issue #55), waiting for maintainer review. Earlier topics are kept in `round1/` (rounds 1-2) and `round3/`; the harness reads only `topics/0*.md`.

Four topics for the html-explainer eval (issue #32, spec #29; round 4 for issue #55), all written for this repo (no copied text). Each file holds a short AI-style source explanation that the skill turns into an interactive page, the points a reader should understand afterwards, and hints for the intended interaction. The harness gives each one to an agent with the topic's `- Request:` line when it has one, else "Make an interactive web page that explains the following.", and compares the with-skill and baseline pages. Both arms get the same request.

| File | Topic | Language | Request | Checks |
|---|---|---|---|---|
| `01-db-migration-plan.md` | An AI-written plan to move orders from MySQL to PostgreSQL | zh-TW | blueprint style | blueprint on request; visible assumptions (2) and an open decision |
| `02-cache-proposal.md` | An AI proposal to put a Redis cache in front of a product API | zh-TW | blueprint style | blueprint on request; visible assumptions (2) and an open decision; hit-rate math |
| `03-hash-table-resize.md` | How a hash table resizes when the load factor passes 0.75 | zh-TW | default | default pages do not regress |
| `04-hosting-cost-estimate.md` | An AI estimate of a blog's monthly hosting cost | zh-TW | default | default pages do not regress; visible assumptions appear without a style |

Round 4 answers the two #55 acceptance questions: (a) a blueprint page on request against Claude without the skill given the same request (01, 02), and (b) default pages do not regress (03, 04). 01, 02 and 04 are AI output with stated assumptions, so the optional "make the assumptions visible" pattern fits them; 03 has none, so the pattern must not appear. All are zh-TW, so the maintainer can rate every page, and new, so the maintainer has not seen pages of them before. The sources are sized in characters (about 300–350). The "Reader should understand" bullets are the checklist for the blind rating; the interaction hints are optional guidance for the reviewer, not a script for the agent, and are in English. The check values were calculated by hand.

## Review checklist

When you review or change a topic, check it for:

- Realistic content: something a user would plausibly ask an agent to explain as an interactive page.
- Suited to interaction: the idea changes when the reader moves a slider, steps through, or toggles something, and the key point is still readable before any interaction.
- Fits one self-contained file: no external data, no heavy simulation.
- No copied third-party text (ADR 0001): written originally, not taken from docs, Wikipedia or tutorials.
- zh-TW topics use Taiwan wording (程式, 資料, 伺服器, 預設).
- Facts and numbers are correct, and the understanding points match what the source actually says.

## Approval

Round 4: draft, waiting for maintainer review.

Round 3 (`round3/`): approved by the maintainer on 2026-10-09, no changes; used in run `20261009-021002`.

Round 1-2 set (`round1/`): approved by the maintainer on 2026-10-09. Change during review: topics 01 and 03 rewritten from English to zh-TW (spec #29 revision 2026-10-09), with the same facts, numbers and understanding points.
