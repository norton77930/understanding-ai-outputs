# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `diagram-explainer` skill: hand-written SVG for concepts, spatial relations, proportions and timelines; Mermaid stays
  for flows, sequences and states, and a tool the user names (D2, Graphviz) still wins (#54). New stdlib
  `svg_check.py` checker with unit tests: well-formed XML, a `viewBox`, an opaque background, no scripts, event
  handlers, `foreignObject` or outside references, text contrast of at least 4.5:1, and a font-size floor (fails below
  11 units per 1200 units of width; warns below 12 px at an 800 px display width); warnings for text that may fall
  outside the canvas, colors it cannot resolve and files over 200 KB. `render_diagram.py` also turns an SVG into a PNG
  for the layout check. New `references/svg-drawing.md`.
- `diagram-explainer` skill: overview sheets (#42). On an explicit request for a whole-topic overview ("one sheet that
  explains X", "一張圖看懂 X", "總覽圖"; "cheat sheet" alone does not count), the skill draws one hand-written SVG
  sheet with 3 to 6 lettered panels, a title block and one legend. `svg_check.py --sheet` checks text size for a
  1600 px display width. New `references/sheet-drawing.md`. Trigger eval: 23/23.
- `video-explainer` skill: ElevenLabs narration engine (#45), used only when the storyboard names it with a voice ID
  (`"engine": {"name": "elevenlabs", "voice": "<voice_id>"}`, model `eleven_multilingual_v2`); a set key never
  changes the default engine. The key comes only from `ELEVENLABS_API_KEY`: it is read at synthesis time, sent only in
  the `xi-api-key` header, and never stored, cached, passed to child processes or printed (errors keep only the HTTP
  status and ElevenLabs' error code; output and tracebacks are redacted). `plan` stays offline and reports
  `narration_cost` (characters, estimated credits, a dated price note), with a notice when the key is not set. A
  storyboard engine field that looks like a credential fails validation. The doctor reports only whether the key is
  set (`elevenlabs_api_key`). `youtube` and `short` get a licence notice for the free plan.
- `html-explainer` skill: opt-in named page styles, `blueprint` first (#55). Only a style the user names loads
  `references/styles/<name>.md` (engineering-drawing look: light and dark tokens, panels with letter tabs, a title
  block, numbered pins, status strokes); without a named style nothing changes. A new optional content pattern,
  "Make the assumptions visible", for AI output with assumptions or open decisions: a done / assumed / future legend
  that never relies on color alone, and an open-questions panel (our assumption, the question, who to ask, what it
  affects). The skill never invents an assumption the source does not contain.
- `video-explainer` skill: optional LaTeX formulas (#43). `doctor.py` reports `capabilities.latex` (`latex` and
  `dvisvgm` on PATH; never installed by the skill). Only when it is available may scene code use `MathTex`, `Tex` and
  `DecimalNumber`; without it the `Text`-only rule is unchanged. New Example 6 with a `Text`-only fallback.
- `video-explainer` skill: camera moves (#44). `ctx.camera.zoom`, `pan` and `restore` zoom in on a detail or pan along
  a long object as timed beats; titles, captions and the burned narration stay fixed in every preset, and each scene
  ends with the camera at home. The helper moves the content, not the scene camera. New Example 7.

### Changed

- `video-explainer` skill: Chinese narration is about 45 to 60 characters per scene in `standard` and `deep` mode, and
  about 30 (25 to 35) in `quick` mode and the `short` preset, so zh-TW videos reach their mode's length (#53). `plan`
  reports `zh_scene_chars` (range, average, per scene) for a Chinese storyboard and adds one notice when the average is
  outside the range; when short Chinese scenes also make the video too short, that notice says to write fuller scenes,
  not to add scenes. The length estimate uses the Chinese speech rate of the engine that will speak: edge-tts 3.85
  characters per second (measured), other engines 3.05; `plan` reports it as `speech_rate`. Before, edge-tts videos
  came out about 20% shorter than estimated, so a too-short deep video got no notice. `plan` also adds a notice when
  the estimate is less than 5% above the mode's lower length bound.
- `diagram-explainer` description and plugin description: Mermaid or SVG.

## [1.0.0] - 2026-10-10

First public release: four skills (`ste-writing`, `diagram-explainer`, `html-explainer`, `video-explainer`), each with
checker scripts, a 20-query trigger eval and a blind-rated eval.

### Added

- Claude Code plugin manifest (`.claude-plugin/plugin.json`) and marketplace entry (`.claude-plugin/marketplace.json`).
- `ste-writing` skill: relaxed Simplified Technical English writing and rewriting.
- `ste_check.py`: a script for the optional self-check, with unit tests.
- `video-explainer` skill: turns a topic or AI output into a short narrated explainer video (`video.mp4`, `video.srt`,
  `script.md`) with ManimCE. Includes the `doctor.py` and `make_video.py` scripts (plan, preview, final,
  fetch-models), the scene helper, Kokoro and edge-tts narration engines, the `explainer`, `youtube` and `short`
  output presets, fallback scenes for render failures, references with a "Before you publish" section, and a
  20-query trigger eval.
- GitHub Actions workflow that runs strict plugin validation and the unit tests on pull requests and on pushes to `main`.
- README with both install routes, the skill list and the format ladder, and a "How this project works" section
  (one format per skill, checker scripts as a floor, the latest blind rating per skill, related projects).
- `docs/demo/`: one answer (prompt caching and long Claude Code sessions) in all four formats, made by the skills,
  with the request, time and cost of each and the one sentence changed by hand. The README opens with it.
- Traditional Chinese README (`README.zh-TW.md`), a logo, and a README first screen with a plain-text versus
  four-formats image, badges, example requests and a "Why not just ask Claude?" section with the blind ratings.
- CONTRIBUTING guide, issue forms (observed failure, idea) and this changelog.
- MIT license.
- `diagram-explainer` skill: explains a topic or AI output as one to three Mermaid diagrams (flowchart,
  sequence, state) with a one-line caption, saved to `out/diagram-explainer/<slug>/`. Includes the stdlib
  `diagram_check.py` checker (size warnings, label length, fragile syntax) with unit tests, the `render_diagram.py` SVG/PNG
  renderer (Playwright, pinned Mermaid 11, no silent browser download), references with a type-selection table, and a
  20-query trigger eval.
- `html-explainer` skill: turns a topic or AI output into one self-contained interactive HTML page
  (`out/html-explainer/<slug>/index.html`) with six interaction patterns (step-through, slider, layer toggles, reveal, predict-then-reveal, preset scenarios). Includes the
  `page_check.py` static checker (standard library, with unit tests), the `render_check.py` headless-browser check
  (screenshots for a layout check, no browser download), references for interaction patterns, the design baseline and
  both checks, and a 20-query trigger eval.

### Changed

- `html-explainer` skill: the page now has one section per key point (usually 3 to 6), each with a pattern chosen for that point.
  The text names every point and no longer stays short at the cost of a point. Two new interaction patterns
  (predict-then-reveal, preset scenarios) and autoplay for the step-through. The design baseline adds visual
  hierarchy, state colors that are never the only cue, transitions and `prefers-reduced-motion` support, and replaces
  the styled skeleton with a bare one so that the agent designs each page for its topic; the page structure and
  state color names are now recommendations, the topic decides the number of key points, and the description also
  triggers on a request for an explanation "in HTML".
- `diagram-explainer` skill: no fixed node budget; the diagram is sized to the topic and split (at most three) only
  when the layout check shows it is hard to read. Each diagram has a title (front matter), two-line labels (a name,
  `<br>`, one detail), colors with a fixed meaning (`classDef`/`class`/`linkStyle`, a palette readable in dark mode)
  and a legend. A chain of stages, also with pass/fail checks, is now `flowchart LR`; `flowchart TD` is for branching.
  `diagram_check.py` reports size limits (about 20 nodes, 8 participants, 20 messages) as `warnings` that do not fail,
  checks the name line (5 words / 10 CJK characters) and the detail line (8 words / 16 CJK characters) of each label,
  and accepts `<br>`, title front matter, `classDef`, `class`, `linkStyle` and `:::` classes. `%%{init}` stays rejected.
- `ste-writing` skill: new core rule "keep articles (the, a, an)", and "80% STE" or "soft STE" now means relaxed.
  The eval adds an explain set of four zh-TW topics (`--set explain`) with a blind review page for a two-axis human rating.
- `video-explainer` skill: intent modes replace the fixed 3 to 8 scenes and 30 to 120 seconds. Before the storyboard
  the agent asks at most two questions (depth, audience), each with a recommended default, only for what the request
  does not say; words such as "3b1b" or "deep dive" (deep), "quick" (quick) and "Short" or "Reels" (`short` with
  quick) set the mode without a question; the default is standard for a general audience. Modes: quick (about
  1 minute, 3 to 6 scenes), standard (2 to 4 minutes, 6 to 15 scenes) and deep (5 to 10 minutes, 15 to 30 scenes).
  The storyboard has an optional `mode` field; `plan` fails on a scene count outside the mode's range, adds a notice
  when the estimate is outside the mode's length, keeps `short` at 60 s or less, and reports `mode` in its JSON
  (the preset's `target_seconds` becomes `max_seconds`). The storyboard confirmation shows the mode. A 3b1b-like style
  in every mode: carried objects that `Transform` when the idea continues, one color per concept, and counting numbers
  with `Text` and an updater, with two new scene examples. The description no longer says "short".

[Unreleased]: https://github.com/norton77930/understanding-ai-outputs/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/norton77930/understanding-ai-outputs/releases/tag/v1.0.0
