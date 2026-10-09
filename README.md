# understanding-ai-outputs

Agent skills that turn LLM output into formats a human can understand faster, following Andrej Karpathy's X post
([our summary](reference/karpathy-x-post.md)).

As agents do more of the work, we spend more time reading and checking what they produce. The post suggests a
**format ladder**. Each step costs more to produce and is faster to understand:

1. **STE writing**: explain in Simplified Technical English.
2. **Diagram**: ask for a diagram instead of prose.
3. **Web page**: ask for the output as an interactive HTML page.
4. **Explainer video**: ask for a narrated, 3Blue1Brown-style video.

Each step is its own skill. Install only the ones you need.

## Skills

| Skill | What it does | Status |
| --- | --- | --- |
| `ste-writing` | Writes or rewrites text in a relaxed Simplified Technical English style | Available in the next release |
| `diagram-explainer` | Turns a topic or an answer into one to three small Mermaid diagrams (flowchart, sequence, state) with a caption | Available in the next release |
| `html-explainer` | Turns a topic or an answer into one self-contained interactive web page | Available in the next release |
| `video-explainer` | Turns a topic or an answer into a short narrated video (MP4, captions, script) | Available in the next release |

`ste-writing` is inspired by ASD-STE100. It is not official and is not endorsed by ASD. The skill uses its own
rules and its own replacement list, not the ASD-STE100 dictionary ([ADR 0001](docs/adr/0001-third-party-reference-material-stays-local.md)).

## Using video-explainer

Ask for a video explicitly, for example "make an explainer video of this answer" or "做一支解釋 TCP 握手的短影片". The
skill writes a storyboard and shows you the scene count, the full narration, the estimated length and render time, and
any model download with its size. It renders only after you approve. You get `video.mp4`, `video.srt` and `script.md`
in `out/video-explainer/<slug>/`.

- Needs [uv](https://docs.astral.sh/uv/) and ffmpeg. The plugin installs nothing. ManimCE and the narration engines
  arrive through `uv run` on first use, and the skill's doctor script reports what your machine can do.
- Narration: English uses Kokoro (offline, Apache-2.0). Traditional Chinese uses edge-tts with a Taiwan voice, and
  falls back to Kokoro (mainland accent) without network.
- Output presets: `explainer` (16:9, 720p, default), `youtube` (16:9, 1080p) and `short` (9:16, captions burned in).
- Before you upload a video, read "Before you publish" in
  [`narration-engines.md`](skills/video-explainer/references/narration-engines.md): edge-tts uses an unofficial
  endpoint.
- To keep caches off your system drive, set `UV_CACHE_DIR` and `VIDEO_EXPLAINER_CACHE`.

## Using diagram-explainer

Ask for a diagram explicitly, for example "draw a diagram of this answer", "show this as a sequence diagram" or
"畫一張圖說明 git rebase". The skill picks the diagram type from your question (a pipeline reads left to right), sizes
the diagram to the topic and splits it only when the rendered image is hard to read. Each diagram has a title, labels
with a short name and one detail line, colors with a fixed meaning (for example pass green, fail red) explained by a
legend, and one caption line that says what to look at. You get the Mermaid code in the reply, and `diagram.mmd` and
`caption.md` in `out/diagram-explainer/<slug>/`.

- Only `flowchart`, `sequenceDiagram` and `stateDiagram-v2`, in syntax that renders on GitHub and in common tools. A
  stdlib checker script checks every diagram before you see it.
- Optional rendering to `diagram.svg` and `diagram.png` needs [uv](https://docs.astral.sh/uv/), network access, and
  Google Chrome, Microsoft Edge or Playwright's Chromium. The skill never downloads a browser without asking you. Without
  a browser, you still get the checked Mermaid source.
- Labels follow the STE principles. They are inspired by ASD-STE100, are not official and are not endorsed by ASD.
- D2 or Graphviz only when you ask for them and have them installed.

## Using html-explainer

Ask for an interactive page explicitly, for example "make an interactive page that explains binary search" or
"做一個互動網頁說明 TCP 三次握手". The skill picks an interaction that fits the idea (step-through, slider, layer toggles
or reveal) and writes one `index.html` in `out/html-explainer/<slug>/`. Open it with a double-click: no build, no
server, no install.

- The page has no external resources by default. A library, if necessary, comes only from cdnjs, jsDelivr or unpkg at a
  pinned version.
- The page fits a 390 px phone screen, follows your light or dark system setting and works with the keyboard.
- A static check (Python standard library) runs on every page. A render check then loads the page in a headless
  browser, fails on console errors or horizontal scroll, and saves phone and desktop screenshots in light and dark mode
  for a layout check.
- The render check needs [uv](https://docs.astral.sh/uv/) and a Chromium browser: Playwright's Chromium, Google Chrome
  or Microsoft Edge. It never downloads a browser. Without one, the skill skips the render check and tells you why.
  Set `PLAYWRIGHT_BROWSERS_PATH` to choose where Playwright's browsers go.

## Installation

Pick one route. Installing both gives you every skill twice.

<details>
<summary><strong>Claude Code</strong></summary>

```bash
claude plugin marketplace add norton77930/understanding-ai-outputs
claude plugin install understanding-ai-outputs@norton77930
```

Or, from inside a session:

```
/plugin marketplace add norton77930/understanding-ai-outputs
/plugin install understanding-ai-outputs@norton77930
```

</details>

<details>
<summary><strong>Codex, Cursor, and other agents</strong></summary>

```bash
npx skills@latest add norton77930/understanding-ai-outputs
```

To install one skill only:

```bash
npx skills@latest add norton77930/understanding-ai-outputs --skill=ste-writing
```

</details>

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Release notes are in [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE). Copyright (c) 2026 Norton Deng.
