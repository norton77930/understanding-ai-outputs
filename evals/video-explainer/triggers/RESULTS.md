# Trigger eval results

Date: 2026-10-08. Model: `claude-opus-5-5`. Tool: skill-creator `run_eval.py` from the installed plugin version `054417d0fc68` (patched scratch copy, see below). 3 runs per query, threshold 0.5, 6 workers with one scratch directory per run, timeout 60 s.

## Final result

**20/20 passed (0 errors; limit is 2).** First run. The description was not tuned.

Description under test:

> Make a short narrated explainer video (MP4 with captions and a script) of a topic or a piece of AI output, animated with ManimCE. Use ONLY when the user explicitly asks for a video, such as "make an explainer video of this", "turn this answer into an animated video", or "make a YouTube Short that explains X". Never use for diagrams, web pages, STE text, editing an existing video, or questions about video technology.

| Result | Query (start) | Triggered |
| --- | --- | --- |
| PASS | can you make a short explainer video of how DNS caching works? ... | 3/3 |
| PASS | Make a 3Blue1Brown-style animated video that explains how a hash table ... | 3/3 |
| PASS | 請幫我做一支影片解釋 TCP 三次握手，要有旁白跟字幕 ... | 3/3 |
| PASS | 我想把下面這段說明做成解說影片給新同事看：「git rebase ...」 | 3/3 |
| PASS | make a YouTube Short (vertical, under 60 seconds) that explains why the sky is blue | 3/3 |
| PASS | I need a narrated explainer video for my YouTube channel on how public-key encryption works ... | 3/3 |
| PASS | turn this answer into a video with voice-over and subtitles: "A Kubernetes rolling update ..." | 3/3 |
| PASS | explain the Monty Hall problem as an animated video with narration ... | 3/3 |
| PASS | render me a 1 minute narrated animation (mp4 + srt) that explains how JWT signatures work | 3/3 |
| PASS | 幫我做一支 Shorts 直式短片，用動畫講解什麼是複利 | 3/3 |
| PASS | draw me a diagram of the OAuth 2.0 authorization code flow with PKCE ... | 0/3 |
| PASS | make an interactive HTML page that explains how quicksort works ... | 0/3 |
| PASS | explain how HTTPS certificate validation works in STE | 0/3 |
| PASS | what's the difference between H.264 and H.265 for live streaming? ... | 0/3 |
| PASS | trim the first 10 seconds off my screen recording demo.mp4 and burn in the subtitles ... | 0/3 |
| PASS | recommend a few YouTube channels that explain machine learning visually ... | 0/3 |
| PASS | write a script for a 5 minute YouTube video about our startup's product launch ... | 0/3 |
| PASS | my manim scene fails with NameError: name 'ShowCreation' is not defined ... | 0/3 |
| PASS | summarize this YouTube video transcript in five bullet points ... | 0/3 |
| PASS | explain step by step how the attention mechanism in a transformer works ... | 0/3 |

## Deviations from stock skill-creator usage

Installed skill-creator files were not modified. A scratch copy outside the repo had the same four changes as the ste-writing trigger eval (`evals/ste-writing/triggers/RESULTS.md`):

1. Reads output with a thread and queue instead of `select.select` (not supported for pipes on Windows).
2. One scratch project directory per run, under `%TEMP%`.
3. Extra flags `--no-session-persistence`, `--setting-sources project,local` and `--disallowedTools PushNotification`.
4. UTF-8 file encoding.

`--timeout 60` (default 30) was passed so that a slow first response is not counted as a miss. `run_loop.py` was not used.

The eval checks only that the skill fires. It does not check the workflow after the skill loads (storyboard shown, wait for approval). That is checked in a fresh session (issue #21 acceptance) and by the eval topics in `evals/video-explainer/topics/`.
