# video-explainer eval results

The newest run is first; run `20261008-035608` is kept below as history.

## Run `20261011-090459` (issue #53): zh-TW scene length, with-skill only

Status: automated metrics only (no baseline, no rating; this run checks the #53 length rule). Model: claude CLI default (`claude` 2.1.296). Command: `python evals/video-explainer/run_eval.py --topics 01,03 --no-baseline --workers 2 --timeout 5400` (plugin dir: branch `feat/v1.1-wave1`, PR #59, with 45-60 characters per scene in `standard` and `deep`). Full report: `evals/video-explainer/runs/20261011-090459/report.md` (git-ignored, local only).

**With-skill verdict: PASS** (rendered 2/2, layout check 100% (30/30), A/V diff 0.01 s, captions 30/30). Cost $4.05, wall time 6409 s (sum of both topics).

| Topic | Mode | Scenes | Average characters per scene (range) | Plan estimate | Video length (target) | In range |
|---|---|---|---|---|---|---|
| 01-binary-search | deep | 20 | 45.6 (45-60) | 306.0 s | 244.0 s (300-600 s) | no |
| 03-git-merge-vs-rebase | standard | 10 | 48.4 (45-60) | 163.4 s | 133.0 s (120-240 s) | yes |

- **standard now lands inside its range** (the #41 run: 15 scenes, 116 s).
- **deep is still short, because the estimate is too long, not because of the character rule.** The `plan` estimate uses `ZH_HANZI_PER_SECOND = 3.05` (measured in the prototype), but edge-tts `zh-TW-HsiaoChenNeural` speaks faster. Measured from `preview.json` `speech_seconds`: deep 912 hanzi in 237.0 s = **3.85 hanzi/s**; standard 442 hanzi + 42 Latin words in 129.5 s fits 3.85 hanzi/s plus the English word rate within 0.1 s. Both videos were about 80% of their estimate, so `plan` saw 306 s and gave no "below target" notice.
- The skill reported the shortfall to the user itself ("實際語速比估計快，所以檢查時沒有提出警告") and offered to lengthen the video.
- Follow-up in PR #59: a per-engine Chinese speech rate in `plan` (edge-tts 3.85, others 3.05), then a deep re-run.

## Run `20261009-132820` (issue #41): with-skill vs baseline, two rating axes

Status: complete. Automated metrics filled; maintainer rated the videos blind on 2026-10-10.

Model: claude CLI default (`claude` 2.1.295). Command: `python evals/video-explainer/run_eval.py --workers 3 --timeout 5400`. A/B seed: `20261009-132820`. Topics approved by the maintainer on 2026-10-09 (01 and 03 Sources expanded). Full report: `evals/video-explainer/runs/20261009-132820/report.md`; review page: `evals/video-explainer/runs/20261009-132820/review.html` (both git-ignored, local only).

### Automated metrics

**With-skill verdict: PASS.** 4/4 rendered. Layout-check pass rate 100% (57/57 scenes not flagged), 0 fallback scenes. With-skill arm: 71 turns, $6.18, 126 min wall time (sum over topics; 3 workers). Baseline arm: 2/2 rendered, 22 turns, $2.90, 82 min wall time. The baseline does not gate the verdict.

With-skill arm (gated). Mode ranges come from the skill's `MODES` and are reported, not gated.

| Topic | Mode requested | Storyboard mode | Scenes (in mode range) | Video length (in mode range) | Render | Resolution | A/V diff (pass <= 0.3 s) | Layout check (not flagged; fallback) | Captions match narration | Turns | Cost | Wall time |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01-binary-search | deep | deep | 30 (yes, 15-30) | 261.0 s (no, 300-600 s) | PASS | PASS (1280x720) | PASS (0.01 s) | 100% (30/30); 0 | PASS (30/30) | 2 | $2.88 | 3439 s |
| 02-gradient-descent | quick | quick | 6 (yes, 3-6) | 48.5 s (yes, 30-90 s) | PASS | PASS (1280x720) | PASS (0.00 s) | 100% (6/6); 0 | PASS (6/6) | 3 | $1.11 | 2406 s |
| 03-git-merge-vs-rebase | standard | standard | 15 (yes, 6-15) | 115.9 s (no, 120-240 s) | PASS | PASS (1920x1080) | PASS (0.01 s) | 100% (15/15); 0 | PASS (15/15) | 33 | $1.22 | 921 s |
| 04-http-request | quick | quick | 6 (yes, 3-6) | 43.5 s (yes, 30-90 s) | PASS | PASS (1080x1920) | PASS (0.01 s) | 100% (6/6); 0 | PASS (6/6) | 33 | $0.98 | 795 s |

Baseline arm (reported, not gated; "n/a" for captions, layout check and mode checks):

| Topic | Render | Resolution | Video length | A/V diff | Captions | Layout check | Mode checks | Turns | Cost | Wall time |
|---|---|---|---|---|---|---|---|---|---|---|
| 01-binary-search | PASS | FAIL (854x480) | 238.3 s | FAIL (2.72 s) | n/a | n/a | n/a | 17 | $1.44 | 3834 s |
| 03-git-merge-vs-rebase | PASS | PASS (1920x1080) | 90.5 s | PASS (0.01 s) | n/a | n/a | n/a | 5 | $1.46 | 1060 s |

### Maintainer ratings (blind)

Rate on `review.html`, press the Markdown button, paste the table here. Per video: **Understanding** (did I understand it, 1-5, against the topic's "Viewer should understand" bullets) and **Presentation** (continuity, motion, narration naturalness, pacing; 1-5). For topics with a baseline also pick the better video (A / B / tie). Then fill "With-skill was" from `report.json` `ab_key`; do this only after rating.

| Topic | Video | Understanding (1-5) | Presentation (1-5) | Better (A / B / tie) | With-skill was (from key) | Notes |
|---|---|---|---|---|---|---|
| 01-binary-search | A | 5 | 4 | B | B (A = baseline) | B's animation, presentation and voice are more comfortable to watch. |
| 01-binary-search | B | 5 | 5 | | | |
| 02-gradient-descent | - | 5 | 5 | n/a | n/a (no baseline) | |
| 03-git-merge-vs-rebase | A | 5 | 4 | B | B (A = baseline) | Same note as 01. |
| 03-git-merge-vs-rebase | B | 5 | 5 | | | |
| 04-http-request | - | 5 | 5 | n/a | n/a (no baseline) | |

"Better" and "With-skill was" are filled once per topic with a baseline (on the A row; the B row can stay empty or repeat it). The A/B order differs per topic.

**Result: the skill won both topics with a baseline (01, 03).** Understanding 5 for every video in both arms. Presentation: with-skill 5 on all four topics; baseline 4 on both. The maintainer's reason: the skill's animation, presentation and voice are more comfortable to watch.

On-screen text: both baseline videos burn the full narration in as subtitles. The skill's `explainer` and `youtube` presets show only key words on screen and deliver the full captions as `video.srt`; only `short` burns captions in (04). The maintainer noticed this difference while rating.

### Observations from this run

- **01 with-skill took deep mode without a depth question** (the request names 3Blue1Brown): the open acceptance item of issue #40. 30 scenes, but 4 min 21 s, under the deep target of 5 to 10 minutes: the narration ran faster than the plan's estimate. Chinese at about 30 characters per scene gives about 9 to 11 s per scene, so deep mode reaches 5 minutes only near its 30-scene maximum. 03 (standard, 15 scenes, 116 s) is also just under its range. The skill's own reply reported both shortfalls.
- **01 baseline did not finish.** Its last reply says the final 1080p render "is running in the background"; that process ended with the `claude -p` session, so the only video is Manim's 480p preview (854x480, audio 2.72 s off). The rating uses that video as the baseline's result.
- **03 baseline built its own pipeline** with Python/PIL frames, the Windows "Hanhan" voice and ffmpeg (no Manim, burned-in subtitles, also a thumbnail and a YouTube description). Its own reply calls the voice the weakest part.
- With-skill 01 added two derived numbers (2^20 = 1,048,576; about 21 and 22 comparisons for 2 and 4 million items) and said so. 03 with-skill added a short "what is a commit and a branch" scene for the Git-beginner audience the request names, and said so.
- The resolution and A/V differences make the 01 pair partly identifiable; the rating is blind to labels, not to quality.

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
