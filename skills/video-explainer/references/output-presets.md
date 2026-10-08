# Output presets

Set the preset with the storyboard `preset` field. The values come from `PRESETS` in `scripts/make_video.py`.

| Preset | Use for | Aspect | Final resolution | fps | Target length | Captions |
| --- | --- | --- | --- | --- | --- | --- |
| `explainer` (default) | Watching on a computer, sharing a file | 16:9 | 1280x720 | 30 | 30 to 120 s | `video.srt` only |
| `youtube` | A landscape YouTube upload | 16:9 | 1920x1080 | 30 | 30 to 120 s | `video.srt` only |
| `short` | YouTube Shorts, Reels, vertical video | 9:16 | 1080x1920 | 30 | 30 to 60 s | `video.srt`, and the narration burned into the picture |

- `preview` renders at 15 fps with the shorter side at 480 px (540 px for `short`).
- `short` keeps the bottom 16% of the frame clear for app controls. It draws each scene's whole narration in a band above that zone (`layout.narration`). Scene code must not draw there.
- `plan` adds a notice when the estimated length is outside the target. Shorten the storyboard when it is over the limit.
- `youtube` and `short` with edge-tts add a publishing notice. See "Before you publish" in `narration-engines.md`.
- Render time grows with resolution: `youtube` takes about twice as long as `explainer` for the final render. `plan` gives the estimate.
