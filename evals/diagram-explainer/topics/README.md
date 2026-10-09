# Eval topics

Status: APPROVED 2026-10-09 (round 2, issue #47, spec #23 revision 2026-10-09). The first-run topics are kept in `round1/`; the harness reads only `topics/0*.md`.

Four topics for the diagram-explainer eval (issue #26, spec #23), all written for this repo (no copied text). Each file holds a short AI-style source explanation that the skill turns into a diagram, the expected diagram type, and the points a reader should get from the diagram. The harness gives each one to an agent with a request such as "Make a diagram of the following." and compares the with-skill and baseline outputs.

| File | Topic | Language | Expected diagram type |
|---|---|---|---|
| `01-card-payment.md` | Online card payment: authorization and capture | zh-TW | `sequenceDiagram` |
| `02-delivery-order.md` | States of a food-delivery order | zh-TW | `stateDiagram-v2` |
| `03-video-processing.md` | Processing an uploaded video, stage by stage | zh-TW | `flowchart LR` |
| `04-kubernetes-structure.md` | What a Kubernetes cluster contains | zh-TW | `flowchart` with `subgraph` |

All round-2 topics are zh-TW, so the maintainer can rate every diagram; they are new, so the maintainer has not seen diagrams of them before. The sources are sized in characters (about 250–300). The "Reader should understand" bullets are the checklist for the maintainer's blind rating of whether the diagram carries the points; they are written in the topic's language. The diagram hints are optional guidance for the reviewer, not a script for the agent, and are in English.

## Review checklist

When you review or change a topic, check it for:

- Realistic content: something a user would plausibly ask an agent to explain as a diagram.
- Suited to a diagram: the idea is a structure (order of messages, states, steps and decisions), not a story or a formula.
- Fits one readable diagram (about 12 key nodes or fewer), so size is not the test.
- No copied third-party text (ADR 0001): written originally, not taken from docs, Wikipedia or tutorials.
- zh-TW topics use Taiwan wording (程式, 資料, 伺服器, 預設, 快取).
- Facts are correct, and the understanding points match what the source actually says.

## Approval

Round 2: approved by the maintainer on 2026-10-09, no changes.

Round 1 (`round1/`): used in runs `20261008-052951` and `20261008-053511`; never formally approved.
