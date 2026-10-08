# Eval topics

Status: DRAFT (round 3) — awaiting maintainer review (spec #29). Round 1-2 topics (approved 2026-10-09, issue #32) are kept in `round1/`; the harness reads only `topics/0*.md`.

Four topics for the html-explainer eval (issue #32, spec #29), all written for this repo (no copied text). Each file holds a short AI-style source explanation that the skill turns into an interactive page, the points a reader should understand afterwards, and hints for the intended interaction. The harness gives each one to an agent with a request such as "Make an interactive page for the following." and compares the with-skill and baseline pages.

| File | Topic | Language | Intended interaction |
|---|---|---|---|
| `01-monty-hall.md` | Why switching doors wins two times in three | zh-TW | predict-then-reveal, simulation |
| `02-lru-cache.md` | How an LRU cache picks what to evict | zh-TW | step-through, preset scenarios |
| `03-base-rate.md` | Why a positive test can still mean "probably not sick" | zh-TW | sliders, population grid |
| `04-pendulum.md` | What sets a pendulum's period | zh-TW | sliders, side-by-side animation |

All four topics are in zh-TW (spec #29 revision 2026-10-09), so the maintainer can rate every page; English output is covered by the trigger eval and the automated checks. Round 3 uses new topics so the maintainer rates topics they have not seen in earlier rounds; the round-1 topics stay in `round1/` for the earlier runs. The sources are sized in characters (about 200–330). The "Reader should understand" bullets are the checklist for the maintainer's blind rating of which page explains better; they are written in the topic's language so the rater can check them against the page text directly. The interaction hints are optional guidance for the reviewer, not a script for the agent, and are in English. The suggested numbers in the hints were calculated by hand and are there so the reviewer can check a page's values.

## Review checklist

When you review or change a topic, check it for:

- Realistic content: something a user would plausibly ask an agent to explain as an interactive page.
- Suited to interaction: the idea changes when the reader moves a slider, steps through, or toggles something, and the key point is still readable before any interaction.
- Fits one self-contained file: no external data, no heavy simulation.
- No copied third-party text (ADR 0001): written originally, not taken from docs, Wikipedia or tutorials.
- zh-TW topics use Taiwan wording (程式, 資料, 伺服器, 預設).
- Facts and numbers are correct, and the understanding points match what the source actually says.

## Approval

Round 3 set: not yet approved. Record the approval date and any changes here.

Round 1-2 set (`round1/`): approved by the maintainer on 2026-10-09. Change during review: topics 01 and 03 rewritten from English to zh-TW (spec #29 revision 2026-10-09), with the same facts, numbers and understanding points.
