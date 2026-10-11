# Eval topics

Status: APPROVED 2026-10-11 (round 3, issue #54). Earlier topics are kept in `round1/` and `round2/`; the harness reads only `topics/0*.md`.

Four topics for the diagram-explainer eval (issue #26, spec #23; round 3 for issue #54), all written for this repo (no copied text). Each file holds a short AI-style source explanation that the skill turns into a diagram, the expected output (`svg` for hand-written SVG, otherwise a Mermaid type), and the points a reader should get from the diagram. The harness gives each one to an agent with a request such as "Make a diagram of the following." and compares the with-skill and baseline outputs.

| File | Topic | Language | Expected output |
|---|---|---|---|
| `01-memory-hierarchy.md` | Memory hierarchy: capacity and access time from L1 to SSD | zh-TW | `svg` (proportion) |
| `02-http-cache-timeline.md` | HTTP cache over time: max-age and stale-while-revalidate | zh-TW | `svg` (timeline) |
| `03-btree-index.md` | How a B+ tree index narrows a search | zh-TW | `svg` (concept, spatial) |
| `04-password-reset.md` | Password reset by e-mail link | zh-TW | `sequenceDiagram` |

Round 3 tests the #54 change: three topics are concepts, proportions or timelines that boxes and arrows draw badly, and one (`04`) is a flow that must still come out as Mermaid. All are zh-TW, so the maintainer can rate every diagram, and new, so the maintainer has not seen diagrams of them before. The sources are sized in characters (about 250–350). The "Reader should understand" bullets are the checklist for the maintainer's blind rating of whether the diagram carries the points; they are written in the topic's language. The diagram hints are optional guidance for the reviewer, not a script for the agent, and are in English.

## Review checklist

When you review or change a topic, check it for:

- Realistic content: something a user would plausibly ask an agent to explain as a diagram.
- Suited to a diagram: the idea is a structure (order of messages, states, steps and decisions) or a picture (a proportion, a timeline, a spatial relation), not a story or a formula.
- Fits one readable diagram (about 12 key nodes or fewer), so size is not the test.
- No copied third-party text (ADR 0001): written originally, not taken from docs, Wikipedia or tutorials.
- zh-TW topics use Taiwan wording (程式, 資料, 伺服器, 預設, 快取).
- Facts are correct, and the understanding points match what the source actually says.

## Approval

Round 3: approved by the maintainer on 2026-10-11 (topic list in the session that opened PR #59).

Round 2 (`round2/`): approved by the maintainer on 2026-10-09, no changes; used in run `20261009-092505`.

Round 1 (`round1/`): used in runs `20261008-052951` and `20261008-053511`; never formally approved.
