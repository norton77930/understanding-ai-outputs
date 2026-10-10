# Demo: one answer, four formats

Made on 2026-10-10 with the four skills in this repo (Claude Code 2.1.295, default model). Each skill ran in its own
isolated `claude -p` session with the plugin loaded, with one request followed by the same answer.

## The answer

An assistant-style answer to "Why do long Claude Code sessions get slow and expensive, and how do an automatic handoff
and keeping the cache warm help?" The facts come from the Claude Code and API documentation (read 2026-10-10):

- [How Claude Code uses prompt caching](https://code.claude.com/docs/en/prompt-caching)
- [Explore the context window](https://code.claude.com/docs/en/context-window)
- [Prompt caching (API), pricing](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)

The full answer is in [`prompt-cache-answer.md`](prompt-cache-answer.md).

## Requests, results and costs

| Skill | Request | Result | Time | Cost |
| --- | --- | --- | --- | --- |
| `ste-writing` | "Rewrite this answer in STE." | [`prompt-cache-ste.md`](prompt-cache-ste.md) | 1 min | $0.30 |
| `diagram-explainer` | "Draw a diagram of this answer, and render it to PNG." | [diagram 1](prompt-cache-diagram-1.png) ([source](prompt-cache-diagram-1.mmd)), [diagram 2](prompt-cache-diagram-2.png) ([source](prompt-cache-diagram-2.mmd)) | 2.5 min | $0.54 |
| `html-explainer` | "Make an interactive HTML page that explains this answer." | [`prompt-cache/index.html`](prompt-cache/index.html), [screenshot](prompt-cache-page.png) | 4 min | $0.81 |
| `video-explainer` | "Make a short explainer video of this answer, about 90 seconds, using the explainer output preset." (plus a line that pre-approves the storyboard, because `claude -p` cannot wait for approval) | [`prompt-cache.mp4`](prompt-cache.mp4), [captions](prompt-cache.srt), [script](prompt-cache-video-script.md) | 31 min | $0.92 |

## What we changed by hand

- **Web page:** one sentence. The page simulates automatic compaction at 85% of the window; the original text read as
  if 85% were Claude Code's real threshold. It now says "In this example, automatic compaction runs at 85%; the real
  point depends on the model and /autocompact."
- **README GIF:** three clips cut from the video (no other edits). The video, the diagrams and the STE text are as the
  skills produced them.
- **Video narration** was shortened by the skill to fit about 90 seconds (it reported each change); for example "breaks
  not much longer than the cache lifetime" became "breaks just past the cache lifetime".
