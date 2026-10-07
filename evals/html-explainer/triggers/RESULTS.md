# Trigger eval results

Date: 2026-10-08. Model: `claude-opus-5-5`. Tool: skill-creator `run_eval.py` from the installed plugin version `054417d0fc68` (patched scratch copy, see below). 3 runs per query, threshold 0.5, 6 workers with one scratch directory per run, timeout 60 s.

## Final result

**20/20 passed (0 errors; limit is 2).** First run. The description was not tuned.

Description under test:

> Build one self-contained interactive HTML page that explains a topic or a piece of AI output, with a step-through, slider, layer toggle or reveal the reader can use. Use ONLY when the user explicitly asks for an interactive page, a web explainer or an HTML demo, such as "make an interactive page that explains X", "turn this answer into an interactive web explainer" or "做一個互動網頁說明 X". Never use for diagrams, videos, STE text, websites or landing pages, app components (React, Vue), fixing existing HTML or CSS, or questions about HTML.

| Result | Query (start) | Triggered |
| --- | --- | --- |
| PASS | make an interactive page that explains how binary search works, with buttons ... | 3/3 |
| PASS | Can you build me a small web explainer for compound interest? I want a slider ... | 3/3 |
| PASS | 做一個互動網頁說明 TCP 三次握手，讓我可以一步一步按下一步看封包怎麼跑 | 3/3 |
| PASS | 請把下面這段回答做成可以互動的網頁，給新同事玩玩看：「快取命中時 ...」 | 3/3 |
| PASS | turn this answer into an interactive web explainer: "A Bloom filter sets k bits ..." | 3/3 |
| PASS | I'd like an HTML demo that lets me toggle the layers of the OSI model ... | 3/3 |
| PASS | build a single-file interactive HTML page explaining how softmax temperature ... | 3/3 |
| PASS | make me a little interactive explainer page about the Monty Hall problem ... | 3/3 |
| PASS | can you create an interactive webpage that walks through how a hash table ... | 3/3 |
| PASS | 幫我做一個互動式的網頁解說 Git rebase 跟 merge 的差別，可以切換看兩種歷史 | 3/3 |
| PASS | draw me a diagram of the OAuth 2.0 authorization code flow with PKCE ... | 0/3 |
| PASS | make a short narrated explainer video of how DNS caching works ... | 0/3 |
| PASS | explain how HTTPS certificate validation works in STE | 0/3 |
| PASS | fix my CSS: the sidebar overlaps the main content on mobile ... | 0/3 |
| PASS | build me a landing page for my company, a small bakery in Taipei ... | 0/3 |
| PASS | explain the difference between the &lt;section&gt;, &lt;article&gt; and &lt;div&gt; HTML tags ... | 0/3 |
| PASS | write a React component that shows a paginated table of users ... | 0/3 |
| PASS | my page throws 'Uncaught TypeError: Cannot read properties of null ...' | 0/3 |
| PASS | explain step by step how the attention mechanism in a transformer works ... | 0/3 |
| PASS | convert this markdown README to HTML so I can paste it into our wiki | 0/3 |

## Deviations from stock skill-creator usage

Installed skill-creator files were not modified. A scratch copy outside the repo had the same four changes as the ste-writing trigger eval (`evals/ste-writing/triggers/RESULTS.md`):

1. Reads output with a thread and queue instead of `select.select` (not supported for pipes on Windows).
2. One scratch project directory per run, under `%TEMP%`.
3. Extra flags `--no-session-persistence`, `--setting-sources project,local` and `--disallowedTools PushNotification`.
4. UTF-8 file encoding.

`--timeout 60` (default 30) was passed so that a slow first response is not counted as a miss. `run_loop.py` was not used.

The eval checks only that the skill fires. It does not check the page that the workflow makes. That is checked in a fresh session (issue #33 acceptance) and by the eval topics (issue #34).

## Fresh-session check (issue #33 acceptance)

2026-10-08, branch `feat/html-explainer` exported to a scratch folder and loaded with `--plugin-dir`, run from an empty folder with `--setting-sources project,local --strict-mcp-config --no-session-persistence`. Request: "Make an interactive web page that explains how binary search halves the search range."

Result: pass. The skill loaded and wrote one `index.html` (step-through with a target menu, range bars and two reveal questions), ran the static and render checks, fixed one layout issue after looking at the screenshots, and replied with the path and how to use the page. Re-running page_check on the saved file: pass, 0 issues, 9.2 KB, 6 controls. The 390 px dark screenshot shows no overflow or clipping. 19 turns, $0.49.
