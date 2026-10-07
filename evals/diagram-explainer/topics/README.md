# Eval topics

Status: DRAFT — awaiting maintainer review (issue #26, spec #23)

Four topics for the diagram-explainer eval (issue #26, spec #23), all written for this repo (no copied text). Each file holds a short AI-style source explanation that the skill turns into a diagram, the expected diagram type, and the points a reader should get from the diagram. The harness gives each one to an agent with a request such as "Make a diagram of the following." and compares the with-skill and baseline outputs.

| File | Topic | Language | Expected diagram type |
|---|---|---|---|
| `01-oauth-login.md` | OAuth authorization-code login | en | `sequenceDiagram` |
| `02-pull-request-lifecycle.md` | Lifecycle of a pull request | zh-TW | `stateDiagram-v2` |
| `03-ci-pipeline.md` | CI pipeline from push to deploy | en | `flowchart LR` |
| `04-browser-cache.md` | How a browser decides to reuse a cached file | zh-TW | `flowchart TD` with decisions |

The English sources are about 120–180 words. The Chinese sources are sized in characters (about 200–280). The "Reader should understand" bullets are the checklist for the maintainer's and the judge's check of whether the diagram carries the points; they are written in the topic's language. The diagram hints are optional guidance for the reviewer, not a script for the agent, and are in English. Every topic fits the skill budget (at most 12 nodes; sequence: at most 6 participants and 12 messages).

## Review checklist

When you review or change a topic, check it for:

- Realistic content: something a user would plausibly ask an agent to explain as a diagram.
- Suited to a diagram: the idea is a structure (order of messages, states, steps and decisions), not a story or a formula.
- Fits the budget: the key nodes or participants stay within the limits above.
- No copied third-party text (ADR 0001): written originally, not taken from docs, Wikipedia or tutorials.
- zh-TW topics use Taiwan wording (程式, 資料, 伺服器, 預設, 快取).
- Facts are correct, and the understanding points match what the source actually says.

## Approval

Not yet approved. Record the approval date and any changes made during review here.
