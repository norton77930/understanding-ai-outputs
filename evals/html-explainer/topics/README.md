# Eval topics

Status: DRAFT 2026-10-13 (round 5, issue #63), pending maintainer approval. Earlier topics are kept in `round1/` (rounds 1-2), `round3/` and `round4/`; the harness reads only `topics/0*.md`.

Four topics for the html-explainer eval (issue #32, spec #29; round 5 for issue #63), all written for this repo (no copied text). Each file holds a short AI-style source explanation that the skill turns into an interactive page, the points a reader should understand afterwards, and hints for the intended interaction. The harness gives each one to an agent with the topic's `- Request:` line when it has one, else "Make an interactive web page that explains the following.", and compares the with-skill and baseline pages. Both arms get the same request.

| File | Topic | Language | Request | Checks |
|---|---|---|---|---|
| `01-token-bucket.md` | How a token bucket limits API requests | zh-TW | default | numbers and a runnable process: Explore stage expected; burst and steady-rate math |
| `02-retry-backoff.md` | An AI recommendation for exponential backoff with a cap and jitter | zh-TW | default | numbers and a runnable process: Explore stage expected; wait-time math |
| `03-jwt-structure.md` | The three parts of a JWT and why a changed payload fails | zh-TW | default | meant as a structural control; the tamper check turned out to be a runnable process, so 04 was added |
| `04-dns-record-types.md` | What each DNS record type answers, and the CNAME rule | zh-TW | default | control: purely definitional, no number and no process; Explore stage expected to be skipped with the reason stated |

Round 5 answers the #63 acceptance question: with the Explore stage, is the with-skill page at least as easy to understand as the baseline, and not less interactive? 01 and 02 have numbers and a process the reader can run, so the skill should add an Explore stage. 03 is the control: no number changes a result, so the skill should skip the Explore stage and say why, and understanding must not drop. All are zh-TW, so the maintainer can rate every page, and new, so the maintainer has not seen pages of them before. The sources are sized in characters (about 300–350). The "Reader should understand" bullets are the checklist for the blind rating; the interaction hints are optional guidance for the reviewer, not a script for the agent, and are in English. The check values were calculated by hand.

## Review checklist

When you review or change a topic, check it for:

- Realistic content: something a user would plausibly ask an agent to explain as an interactive page.
- Suited to interaction: the idea changes when the reader moves a slider, steps through, or toggles something, and the key point is still readable before any interaction.
- Fits one self-contained file: no external data, no heavy simulation.
- No copied third-party text (ADR 0001): written originally, not taken from docs, Wikipedia or tutorials.
- zh-TW topics use Taiwan wording (程式, 資料, 伺服器, 預設).
- Facts and numbers are correct, and the understanding points match what the source actually says.

## Approval

Round 5: pending.

Round 4 (`round4/`): approved by the maintainer on 2026-10-11, no changes; used in run `20261011-103229`.

Round 3 (`round3/`): approved by the maintainer on 2026-10-09, no changes; used in run `20261009-021002`.

Round 1-2 set (`round1/`): approved by the maintainer on 2026-10-09. Change during review: topics 01 and 03 rewritten from English to zh-TW (spec #29 revision 2026-10-09), with the same facts, numbers and understanding points.
