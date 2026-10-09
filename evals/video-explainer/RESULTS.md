# video-explainer eval results

The newest run is first (template, filled from the real run); run `20261008-035608` is kept below as history.

## Run `<timestamp>` (issue #41): with-skill vs baseline, two rating axes

Status: PENDING. Not run yet; the real run and the maintainer ratings are still to come. Replace every `<...>` below.

Model: `<claude CLI default | model>` (`claude` `<version>`). Command: `python evals/video-explainer/run_eval.py`. Workers `<n>`, timeout 3600 s per arm. A/B seed: `<seed, from report.json meta.seed>`. Full report: `evals/video-explainer/runs/<timestamp>/report.md`; review page: `evals/video-explainer/runs/<timestamp>/review.html` (both git-ignored, local only).

### Automated metrics (fill from report.md)

**With-skill verdict: `<PASS | FAIL | INCOMPLETE>`.** `<n>`/4 rendered. Layout-check pass rate `<..>`. With-skill arm: `<turns>` turns, `$<cost>`, `<minutes>` min wall time. Baseline arm: `<n>`/2 rendered, `<turns>` turns, `$<cost>`, `<minutes>` min wall time. The baseline does not gate the verdict.

With-skill arm (gated). Mode ranges come from the skill's `MODES` and are reported, not gated.

| Topic | Mode requested | Storyboard mode | Scenes (in mode range) | Video length (in mode range) | Render | Resolution | A/V diff (pass <= 0.3 s) | Layout check (not flagged; fallback) | Captions match narration | Turns | Cost | Wall time |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01-binary-search | deep | | | | | | | | | | | |
| 02-gradient-descent | quick | | | | | | | | | | | |
| 03-git-merge-vs-rebase | standard | | | | | | | | | | | |
| 04-http-request | quick | | | | | | | | | | | |

Baseline arm (reported, not gated; "n/a" for captions, layout check and mode checks):

| Topic | Render | Resolution | Video length | A/V diff | Captions | Layout check | Mode checks | Turns | Cost | Wall time |
|---|---|---|---|---|---|---|---|---|---|---|
| 01-binary-search | | | | | n/a | n/a | n/a | | | |
| 03-git-merge-vs-rebase | | | | | n/a | n/a | n/a | | | |

### Maintainer ratings (blind; leave empty until rated)

Rate on `review.html`, press the Markdown button, paste the table here. Per video: **Understanding** (did I understand it, 1-5, against the topic's "Viewer should understand" bullets) and **Presentation** (continuity, motion, narration naturalness, pacing; 1-5). For topics with a baseline also pick the better video (A / B / tie). Then fill "With-skill was" from `report.json` `ab_key`; do this only after rating.

| Topic | Video | Understanding (1-5) | Presentation (1-5) | Better (A / B / tie) | With-skill was (from key) | Notes |
|---|---|---|---|---|---|---|
| 01-binary-search | A | | | | | |
| 01-binary-search | B | | | | | |
| 02-gradient-descent | - | | | n/a | n/a (no baseline) | |
| 03-git-merge-vs-rebase | A | | | | | |
| 03-git-merge-vs-rebase | B | | | | | |
| 04-http-request | - | | | n/a | n/a (no baseline) | |

"Better" and "With-skill was" are filled once per topic with a baseline (on the A row; the B row can stay empty or repeat it). The A/B order differs per topic.

### Observations from this run

`<to fill after the run>`

---

## History: run `20261008-035608`

Run `20261008-035608` (2026-10-08). Model: claude CLI default (`claude` 2.1.293). One with-skill run per topic, workers 1, timeout 1800 s per topic. Command: `python evals/video-explainer/run_eval.py`. Full report: `evals/video-explainer/runs/20261008-035608/report.md` (git-ignored, local only).

## Automated metrics

**Verdict: PASS.** 4/4 rendered. Layout-check pass rate 100% (30/30 scenes not flagged), 0 fallback scenes. Total 100 turns, $3.65, 59 min wall time.

| Topic | Lang | Preset | Render | Resolution | Video length (topic target) | Layout check (not flagged; fallback) | A/V diff (pass <= 0.3 s) | Captions match narration | Turns | Cost | Wall time |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 01-binary-search | zh-TW | explainer | PASS | PASS 1280x720 | 64.6 s (60–90 s) | 8/8; 0 | PASS 0.01 s | PASS 8/8 | 37 | $0.91 | 699 s |
| 02-gradient-descent | en | explainer | PASS | PASS 1280x720 | 48.5 s (60–90 s, below) | 7/7; 0 | PASS 0.01 s | PASS 7/7 | 3 | $1.03 | 1796 s |
| 03-git-merge-vs-rebase | zh-TW | youtube | PASS | PASS 1920x1080 | 58.8 s (90–120 s, below) | 8/8; 0 | PASS 0.00 s | PASS 8/8 | 27 | $0.93 | 528 s |
| 04-http-request | en | short | PASS | PASS 1080x1920 | 45.7 s (45–60 s) | 7/7; 0 | PASS 0.00 s | PASS 7/7 | 33 | $0.77 | 520 s |

Topic target length is not a gated metric. Topics 02 and 03 came out shorter than their targets; the videos are still inside the general 30–120 s range.

## Maintainer ratings

Watch each video and check it against the topic's "Viewer should understand" bullets in `topics/`. Videos (local, git-ignored): `evals/video-explainer/runs/20261008-035608/<topic>/video.mp4`, with `video.srt`, `script.md` and the preview `frames/` next to it.

| Topic | Video | Maintainer rating (1-5) | Notes |
|---|---|---|---|
| 01-binary-search | `runs/20261008-035608/01-binary-search/video.mp4` | 5 | |
| 02-gradient-descent | `runs/20261008-035608/02-gradient-descent/video.mp4` | 5 | |
| 03-git-merge-vs-rebase | `runs/20261008-035608/03-git-merge-vs-rebase/video.mp4` | 5 | |
| 04-http-request | `runs/20261008-035608/04-http-request/video.mp4` | 5 | |

Rated 2026-10-08: all four videos 5/5 (every "Viewer should understand" point came across).

## Observations from this run

- **Preview hang (skill issue, topic 02).** During the first `preview`, an `ffprobe -show_entries format=duration` call on a freshly written narration cache WAV (`work/audio/cache/42d12ada....wav`) hung with 0 s CPU from 04:13:26 for about 20 minutes. The same file probed in under a second when run by hand with stdin closed. `run_tool` in `skills/video-explainer/scripts/make_video.py` (lines 588–596) calls `subprocess.run` with no `timeout` and no `stdin=subprocess.DEVNULL`, so one stuck tool blocks the whole command. The agent's Bash call timed out, it blamed slow CPU, re-ran `preview` and finished (30 s). This is why topic 02 took 1796 s, just under the 1800 s limit. Root cause of the hang not confirmed.
- **Chinese caption wrap splits Latin words (skill issue, topic 03).** The agent reported that the zh caption split cut the word "feature" across two lines, and reworded scenes 2, 5 and 8 to avoid it. `_wrap_zh` (`make_video.py` around lines 197–212) hard-cuts a clause at the character limit without regard to ASCII words.
- **Scene objects left on screen (agent scene code, 3 of 4 topics).** In topics 01 and 02 the opening title never faded out and overlapped later scenes; in topic 04 objects from earlier scenes piled up. The layout check caught each case and one or two fix rounds fixed it. The repeat suggests `references/scenes.md` could say more clearly how a scene clears what it drew.
- **Notices.** Topic 03 (youtube + edge-tts) showed the publishing notice, as specified. No accent fallback occurred (edge-tts was reachable).
- **Turns.** Topic 02 reports 3 turns from the `claude -p` JSON although the agent ran a full workflow; the count seems to reset after the background-task wait. Treat turn counts as approximate.
