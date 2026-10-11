# Eval topics

Status: APPROVED 2026-10-11 (round 4, overview sheets, issue #42). Earlier topics are kept in `round1/`, `round2/` and `round3/`; the harness reads only `topics/0*.md`.

Topics for the diagram-explainer eval (issue #26, spec #23; round 3 for issue #54, round 4 for issue #42), all written for this repo (no copied text). Each file holds a short AI-style source explanation that the skill turns into a diagram, the expected output (`svg` for hand-written SVG, otherwise a Mermaid type), and the points a reader should get from the diagram. The harness gives each one to an agent with the topic's `- Request:` line when it has one, else "Draw a diagram that explains the following.", and compares the with-skill and baseline outputs. Both arms get the same request.

| File | Topic | Language | Request | Expected output |
|---|---|---|---|---|
| `01-https-overview.md` | HTTPS at a glance: handshake, certificate chain, what it protects | zh-TW | overview sheet | `svg` (sheet) |
| `02-docker-overview.md` | Docker images and containers at a glance: layers, cache, writable layer, volumes | zh-TW | overview sheet | `svg` (sheet) |
| `03-jwt-overview.md` | JWT at a glance: three parts, verification, expiry and refresh | zh-TW | overview sheet | `svg` (sheet) |

Round 4 tests the #42 change: each topic asks for "一張圖看懂 X" (an overview of the whole topic on one image), and holds several sub-questions, so a good answer is one multi-panel sheet (3-6 panels with letter tabs, a title block and one legend). Both arms get the same overview request; the baseline draws however it chooses. All are zh-TW, so the maintainer can rate every sheet, and new, so the maintainer has not seen sheets of them before. The sources are longer than single-diagram topics (about 350–450 characters), because a sheet covers a whole topic. The "Reader should understand" bullets are the checklist for the blind rating; the diagram hints are optional guidance for the reviewer, not a script for the agent, and are in English.

## Review checklist

When you review or change a topic, check it for:

- Realistic content: something a user would plausibly ask an agent to explain as a diagram.
- Suited to a diagram: the idea is a structure (order of messages, states, steps and decisions) or a picture (a proportion, a timeline, a spatial relation), not a story or a formula. An overview topic holds 3-6 such sub-questions.
- Fits one readable diagram or, for an overview, one readable sheet, so size is not the test.
- No copied third-party text (ADR 0001): written originally, not taken from docs, Wikipedia or tutorials.
- zh-TW topics use Taiwan wording (程式, 資料, 伺服器, 預設, 快取).
- Facts are correct, and the understanding points match what the source actually says.

## Approval

Round 4: approved by the maintainer on 2026-10-11, no changes.

Round 3 (`round3/`): approved by the maintainer on 2026-10-11; used in run `20261011-093008`.

Round 2 (`round2/`): approved by the maintainer on 2026-10-09, no changes; used in run `20261009-092505`.

Round 1 (`round1/`): used in runs `20261008-052951` and `20261008-053511`; never formally approved.
