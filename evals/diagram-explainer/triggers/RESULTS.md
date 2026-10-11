# Trigger eval results

Newest run first.

## 2026-10-11: description from issue #54 (hand-written SVG)

Date: 2026-10-11. Model: `claude-opus-5-5`. Claude Code `2.1.296`. Tool: skill-creator `run_eval.py` from the installed plugin version `a9fd21643fc1` (its `scripts/` folder is identical to `054417d0fc68`), in a new patched scratch copy with the same four changes as the 2026-10-08 run (see "Deviations" below). 3 runs per query, threshold 0.5, 6 workers with one scratch directory per run, timeout 60 s. The eval set `trigger-eval.json` was not changed. Wall time about 4.5 minutes.

**20/20 passed (0 errors; limit is 2).** The description was not tuned. Every should-trigger query triggered 3/3 and every should-not-trigger query triggered 0/3, the same rates as the 2026-10-08 run.

Description under test (issue #54 adds hand-written SVG and "logos or icons" as a negative):

> Explain a topic or a piece of AI output as a diagram with a one-line caption, checked and saved to files: Mermaid for flows, sequences and states, hand-written SVG for concepts, spatial relations, proportions and timelines. Use ONLY when the user explicitly asks for a diagram, chart, flowchart, sequence diagram or picture of how something works, such as "draw a diagram of this", "show this flow as a sequence diagram", "visualize this as a picture" or "畫一張圖說明". Never use for videos, web pages, STE text, data plots from numbers, artwork, logos or icons, fixing broken Mermaid code, or questions about diagram notation.

| Result | Query (start) | Triggered |
| --- | --- | --- |
| PASS | draw me a diagram of how the OAuth 2.0 authorization code flow works ... | 3/3 |
| PASS | can you show the TCP three-way handshake as a sequence diagram? ... | 3/3 |
| PASS | 請畫一張圖說明 git rebase 跟 git merge 的差別 ... | 3/3 |
| PASS | turn your explanation above into a flowchart please: "The CI job runs lint first ..." | 3/3 |
| PASS | visualize how a DNS lookup goes from my laptop to the authoritative server as a picture ... | 3/3 |
| PASS | make a state diagram of the lifecycle of a Kubernetes pod ... | 3/3 |
| PASS | 用流程圖畫出使用者下單之後，訂單從付款到出貨的流程 | 3/3 |
| PASS | give me a mermaid diagram of what runs inside a Docker host ... | 3/3 |
| PASS | I don't get this answer. can you draw it as a diagram instead? "A CDN edge server ..." | 3/3 |
| PASS | sketch a chart of how data moves through our pipeline: Kafka topic, Flink job ... | 3/3 |
| PASS | make a short explainer video with narration that shows how DNS caching works | 0/3 |
| PASS | build an interactive HTML page that explains how a B-tree splits a node ... | 0/3 |
| PASS | rewrite this paragraph in STE: "The configuration file should be edited ..." | 0/3 |
| PASS | my mermaid diagram won't render, GitHub says Parse error on line 3 ... | 0/3 |
| PASS | what is a sequence diagram, and when should I use one instead of a flowchart? | 0/3 |
| PASS | plot a bar chart of monthly revenue from sales.csv with matplotlib ... | 0/3 |
| PASS | draw a cute cat sitting on a laptop keyboard, as SVG | 0/3 |
| PASS | draw.io or Lucidchart for architecture diagrams? ... | 0/3 |
| PASS | explain in words what this diagram says, I inherited it from a colleague ... | 0/3 |
| PASS | explain step by step how garbage collection works in the JVM ... | 0/3 |

## 2026-10-08: description from issue #27 (Mermaid only)

Date: 2026-10-08. Model: `claude-opus-5-5`. Tool: skill-creator `run_eval.py` from the installed plugin version `054417d0fc68` (patched scratch copy, see below). 3 runs per query, threshold 0.5, 6 workers with one scratch directory per run, timeout 60 s.

### Final result

**20/20 passed (0 errors; limit is 2).** First run. The description was not tuned.

Description under test:

> Explain a topic or a piece of AI output as a Mermaid diagram (flowchart, sequence or state diagram) with a one-line caption, checked and saved to files. Use ONLY when the user explicitly asks for a diagram, chart, flowchart, sequence diagram or picture of how something works, such as "draw a diagram of this", "show this flow as a sequence diagram", "visualize this as a picture" or "畫一張圖說明". Never use for videos, web pages, STE text, data plots from numbers, artwork, fixing broken Mermaid code, or questions about diagram notation.

| Result | Query (start) | Triggered |
| --- | --- | --- |
| PASS | draw me a diagram of how the OAuth 2.0 authorization code flow works ... | 3/3 |
| PASS | can you show the TCP three-way handshake as a sequence diagram? ... | 3/3 |
| PASS | 請畫一張圖說明 git rebase 跟 git merge 的差別 ... | 3/3 |
| PASS | turn your explanation above into a flowchart please: "The CI job runs lint first ..." | 3/3 |
| PASS | visualize how a DNS lookup goes from my laptop to the authoritative server as a picture ... | 3/3 |
| PASS | make a state diagram of the lifecycle of a Kubernetes pod ... | 3/3 |
| PASS | 用流程圖畫出使用者下單之後，訂單從付款到出貨的流程 | 3/3 |
| PASS | give me a mermaid diagram of what runs inside a Docker host ... | 3/3 |
| PASS | I don't get this answer. can you draw it as a diagram instead? "A CDN edge server ..." | 3/3 |
| PASS | sketch a chart of how data moves through our pipeline: Kafka topic, Flink job ... | 3/3 |
| PASS | make a short explainer video with narration that shows how DNS caching works | 0/3 |
| PASS | build an interactive HTML page that explains how a B-tree splits a node ... | 0/3 |
| PASS | rewrite this paragraph in STE: "The configuration file should be edited ..." | 0/3 |
| PASS | my mermaid diagram won't render, GitHub says Parse error on line 3 ... | 0/3 |
| PASS | what is a sequence diagram, and when should I use one instead of a flowchart? | 0/3 |
| PASS | plot a bar chart of monthly revenue from sales.csv with matplotlib ... | 0/3 |
| PASS | draw a cute cat sitting on a laptop keyboard, as SVG | 0/3 |
| PASS | draw.io or Lucidchart for architecture diagrams? ... | 0/3 |
| PASS | explain in words what this diagram says, I inherited it from a colleague ... | 0/3 |
| PASS | explain step by step how garbage collection works in the JVM ... | 0/3 |

### Deviations from stock skill-creator usage

Installed skill-creator files were not modified. A scratch copy outside the repo had the same four changes as the ste-writing trigger eval (`evals/ste-writing/triggers/RESULTS.md`):

1. Reads output with a thread and queue instead of `select.select` (not supported for pipes on Windows).
2. One scratch project directory per run, under `%TEMP%`.
3. Extra flags `--no-session-persistence`, `--setting-sources project,local` and `--disallowedTools PushNotification`.
4. UTF-8 file encoding.

`--timeout 60` (default 30) was passed so that a slow first response is not counted as a miss. `run_loop.py` was not used.

The eval checks only that the skill fires. It does not check the workflow after the skill loads (checked Mermaid block, caption, saved files). That is checked in a fresh session (issue #27 acceptance).

### Fresh-session check (issue #27 acceptance)

2026-10-08, branch `feat/diagram-explainer` exported to a scratch folder and loaded with `--plugin-dir`, run from an empty folder with `--setting-sources project,local --strict-mcp-config --no-session-persistence`. Request: "Draw a diagram that explains how a DNS lookup finds the IP address for a website."

Result: pass. The skill loaded, picked `sequenceDiagram`, ran the checker, rendered and checked the PNG, and replied with the Mermaid block, a one-line caption and the saved paths (`diagram.mmd`, `caption.md`, `diagram.svg`, `diagram.png`). Re-running the checker on the saved file: pass, 5 participants, 9 messages. 12 turns, $0.23.
