# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- README with both install routes, the skill list and the format ladder.
- CONTRIBUTING guide, issue forms (observed failure, idea) and this changelog.
- MIT license.
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
