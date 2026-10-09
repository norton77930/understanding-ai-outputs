# Eval topics

Status: approved by the maintainer on 2026-10-08 (issue #17). Topic content is being revised for issue #41 (intent modes, baseline arm): status pending maintainer review. The header lines (Mode, Request) are set; the Sources will be expanded.

Four topics for the video-explainer eval (issue #17, spec #14), all written for this repo (no copied text). Each file holds a short AI-style source explanation that the skill turns into a video, the points a viewer should understand afterwards, and optional visual hints. The harness gives each one to an agent with the topic's `Request` line, " Use the <preset> output preset.", the pre-approval sentences and the Source. The `Mode` line (`quick`, `standard` or `deep`) is the intent mode the skill is expected to pick for that request; the mode decides the length (quick ~1 min, 3-6 scenes; standard 2-4 min, 6-15 scenes; deep 5-10 min, 15-30 scenes; the `short` preset is at most 60 s). The harness reports whether the storyboard's mode, scene count and video length fit; it does not gate on them. The zh-TW topics (01, 03) also run a baseline arm (the same request without the plugin).

| File | Topic | Language | Output preset | Mode | Baseline arm |
|---|---|---|---|---|---|
| `01-binary-search.md` | Binary search | zh-TW | `explainer` | `deep` | yes |
| `02-gradient-descent.md` | Gradient descent intuition | en | `explainer` | `quick` | no |
| `03-git-merge-vs-rebase.md` | git merge vs rebase | zh-TW | `youtube` | `standard` | yes |
| `04-http-request.md` | The life of an HTTP request | en | `short` | `quick` | no |

Each file's header also has a `- Request:` line: one sentence in the topic's language, the user request both arms receive.

The English sources are about 120–150 words. The Chinese sources are sized in characters (about 250–300). The "Viewer should understand" bullets are the checklist for the maintainer's 1–5 "did I understand it" rating; they are written in the topic's language so the rater can check them against the narration directly. The visual hints are optional guidance for the agent, not a storyboard, and are in English.

## Review checklist

When you review or change a topic, check it for:

- Realistic content: something a user would plausibly ask an agent to explain, at the right level for the target length.
- Suited to animation: the idea has something that moves, changes or travels, and does not rely on formulas (v1 has no LaTeX).
- No copied third-party text (ADR 0001): written originally, not taken from docs, Wikipedia or tutorials.
- zh-TW topics use Taiwan wording (程式, 資料, 伺服器, 預設).
- The understanding points match what the source actually says.

## Approval

Approved by the maintainer on 2026-10-08. Changes made during review: topic 01 now says at most five comparisons for sixteen items (the draft said four, which is wrong for the worst case), and the understanding points of the zh-TW topics are in Traditional Chinese.
