<p align="center">
  <img src="docs/logo.svg" width="64" height="64" alt="understanding-ai-outputs logo">
</p>

<h1 align="center">understanding-ai-outputs</h1>

<p align="center">
  <b>STE writing&nbsp;&nbsp;|&nbsp;&nbsp;Diagrams&nbsp;&nbsp;|&nbsp;&nbsp;Interactive pages&nbsp;&nbsp;|&nbsp;&nbsp;Narrated videos&nbsp;&nbsp;|&nbsp;&nbsp;Blind-tested</b>
</p>

<p align="center">
  <img src="docs/demo/text-vs-four-formats.png" width="100%"
    alt="Left: a long plain answer about prompt caching in a terminal. Right: the same answer as STE text, a diagram, an interactive page and a narrated video">
</p>

<p align="center">
  <b>Ask your agent for a diagram, a web page or a narrated video instead of another wall of text.</b><br>
  Four agent skills that follow the format ladder from Andrej Karpathy's
  <a href="https://x.com/karpathy/status/2105819303471976479">post</a> on understanding LLM output.
</p>

<p align="center">
  <a href="https://github.com/norton77930/understanding-ai-outputs/releases"><img src="https://img.shields.io/github/v/release/norton77930/understanding-ai-outputs?style=flat-square&labelColor=16181d&color=2ea44f" alt="Release"></a>
  <a href="https://github.com/norton77930/understanding-ai-outputs/actions/workflows/validate.yml"><img src="https://img.shields.io/github/actions/workflow/status/norton77930/understanding-ai-outputs/validate.yml?branch=main&style=flat-square&labelColor=16181d&label=CI" alt="CI"></a>
  <img src="https://img.shields.io/badge/works%20with-Claude%20Code%20%C2%B7%20Codex%20%C2%B7%20Cursor-2ea44f?style=flat-square&labelColor=16181d" alt="Works with Claude Code, Codex, Cursor">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-2ea44f?style=flat-square&labelColor=16181d" alt="MIT license"></a>
</p>

<p align="center">
  <a href="#install"><b>Install</b></a> · <a href="#one-answer-four-formats">Demo</a> · <a href="#why-not-just-ask-claude">Why</a> · <a href="#the-four-skills">Skills</a> · <a href="docs/demo/README.md">How the demo was made</a> · <a href="README.zh-TW.md">繁體中文</a>
</p>

Once installed, ask the way you always do, and name the format you want:

```
> Explain the answer above in STE
> Draw a diagram of how this request flows through the services
> Make an interactive page that explains binary search
> Make a 3b1b-style explainer video of the TCP handshake
```

Each format is its own skill, and each one starts only when you ask for it. Here is the video one at work:

https://github.com/user-attachments/assets/36cdba42-4a24-4bba-a807-0db2ac08b58c

<p align="center"><sub>92 seconds, made by <code>video-explainer</code> from one answer, no edits. Turn the sound on. Can't play it here? <a href="https://norton77930.github.io/understanding-ai-outputs/demo/prompt-cache.mp4">Open the video</a>.</sub></p>

## Why not just ask Claude?

You can. Claude without these skills writes good diagrams, pages and even videos. We checked how often the skills
do better, in blind ratings: the maintainer rates the rendered output (the image, the page, the video) without
knowing which one the skill made, on new topics each round.

| Skill | Latest blind round against Claude without the skill | Result |
| :--- | :--- | :--- |
| `ste-writing` | 4 explain topics, asked in Traditional Chinese | **2 wins, 1 tie, 1 loss.** Without the skill, Claude answered all four in English. |
| `diagram-explainer` | 4 topics | **2 wins, 1 tie, 1 loss.** Presentation 4.75 vs 4.5 |
| `html-explainer` | 4 topics, round 3 | **1 win, 3 ties.** The baseline won rounds 1 and 2, until we removed the fixed page style |
| `video-explainer` | 2 topics | **2 wins.** Presentation 5 vs 4 |

What the skills add is the part that is easy to skip when you ask by hand:

| When… | Asking by hand | With the skill |
| :--- | :--- | :--- |
| a diagram has long labels | Labels can overflow their boxes, and a pipeline can come out top to bottom (both seen in our tests) | A checker rejects long labels and broken syntax before you see it |
| a page looks fine on your laptop | It can scroll sideways on a phone or skip dark mode (one baseline page had no dark mode) | A render check loads it at 390 px and 1280 px, light and dark, and fails on console errors |
| you ask for a video | The agent picks the length and renders without asking (one baseline run ended before its final render) | You approve a storyboard with the length and render time first; captions are checked against the narration |
| you ask in Chinese for STE | Claude answered in English 4 times out of 4 in our test | You get the STE principles applied in your language |

Every run, cost and loss is in `evals/<skill>/RESULTS.md`. Each skill also passes a 20-query trigger test: it starts
on requests for its format, and stays quiet on the rest.

## Install

**Claude Code** (all four skills):

```bash
claude plugin marketplace add norton77930/understanding-ai-outputs
claude plugin install understanding-ai-outputs@norton77930
```

Or inside a session: `/plugin marketplace add norton77930/understanding-ai-outputs`, then
`/plugin install understanding-ai-outputs@norton77930`.

**Codex, Cursor and other agents**, through [vercel-labs/skills](https://github.com/vercel-labs/skills):

```bash
npx skills@latest add norton77930/understanding-ai-outputs                       # all four
npx skills@latest add norton77930/understanding-ai-outputs --skill=ste-writing   # just one
```

Pick one route; installing both gives you every skill twice. `ste-writing` needs nothing else. The others need extra
tools only for some steps, listed in [the four skills](#the-four-skills).

## One answer, four formats

We gave the same answer to each skill: *why long Claude Code sessions get slow and expensive, and how an automatic
handoff and keeping the cache warm help* ([the answer, the four requests and the costs](docs/demo/README.md)).

| You ask | You get |
| :--- | :--- |
| **"Rewrite this answer in STE."**<br>`ste-writing` | Before: *"Because the model does not remember anything between requests, Claude Code re-sends the entire context on every turn, including the system prompt, your project context and every prior message and tool result, and it relies on prompt caching so that …"* (one 86-word sentence)<br>After: *"The model does not remember anything between requests. Thus, Claude Code sends the full context again on every turn."* ([full text](docs/demo/prompt-cache-ste.md)) |
| **"Draw a diagram of this answer."**<br>`diagram-explainer` | <img src="docs/demo/prompt-cache-diagram-2.png" width="520" alt="Two flows: keep the cache warm (step away, tiny request before expiry, timer resets) and automatic handoff (threshold, break, structured summary, clear, continue)"><br>Mermaid source included ([second diagram](docs/demo/prompt-cache-diagram-1.png)) |
| **"Make an interactive HTML page that explains this answer."**<br>`html-explainer` | <a href="https://norton77930.github.io/understanding-ai-outputs/demo/prompt-cache/"><img src="docs/demo/prompt-cache-page-slider.png" width="520" alt="Section 2 of the page: a slider for the conversation size, and bars comparing the input cost of a warm and a cold cache"></a><br>Six sections with sliders, a guess-first question and step-through animations. **[Try it live](https://norton77930.github.io/understanding-ai-outputs/demo/prompt-cache/)** |
| **"Make a short explainer video of this answer."**<br>`video-explainer` | 92 seconds, 6 scenes, English narration (Kokoro, offline), captions as `.srt`. **[Watch it](https://norton77930.github.io/understanding-ai-outputs/demo/prompt-cache.mp4)** |

## The four skills

The post describes a **format ladder**: each step costs more to produce and is faster to understand. Each step is
one skill. Install only the ones you need.

| Skill | Ask for | You get | Needs |
| :--- | :--- | :--- | :--- |
| `ste-writing` | "explain in STE", "rewrite this in STE" | Text in a relaxed Simplified Technical English style | Nothing |
| `diagram-explainer` | "draw a diagram of this" | One to three diagrams with a legend and a caption: Mermaid for flows, sequences and states, hand-written SVG for concepts, proportions and timelines | Nothing; uv and a Chromium browser for PNG |
| `html-explainer` | "make an interactive page of this" | One self-contained `index.html` with step-through, sliders, toggles or reveals | Nothing; uv and a Chromium browser for the render check |
| `video-explainer` | "make an explainer video of this" | MP4, captions and script: quick (about 1 min), standard (2 to 4 min) or deep (5 to 10 min) | uv and ffmpeg |

`ste-writing` is inspired by ASD-STE100. It is not official and is not endorsed by ASD. The skill uses its own
rules and its own replacement list, not the ASD-STE100 dictionary ([ADR 0001](docs/adr/0001-third-party-reference-material-stays-local.md)).

<details>
<summary><b>video-explainer details</b></summary>

Ask for a video explicitly, for example "make an explainer video of this answer" or "做一支解釋 TCP 握手的短影片". The
skill asks at most two short questions (depth and audience) and skips what your request already says ("3b1b" or
"deep dive" means deep). It writes a storyboard and shows you the mode, the scene count, the full narration, the
estimated length and render time, and any model download with its size. It renders only after you approve. You get
`video.mp4`, `video.srt` and `script.md` in `out/video-explainer/<slug>/`.

- Needs [uv](https://docs.astral.sh/uv/) and ffmpeg. The plugin installs nothing. ManimCE and the narration engines
  arrive through `uv run` on first use, and the skill's doctor script reports what your machine can do.
- Narration: English uses Kokoro (offline, Apache-2.0). Traditional Chinese uses edge-tts with a Taiwan voice, and
  falls back to Kokoro (mainland accent) without network.
- Output presets: `explainer` (16:9, 720p, default), `youtube` (16:9, 1080p) and `short` (9:16, captions burned in).
- Before you upload a video, read "Before you publish" in
  [`narration-engines.md`](skills/video-explainer/references/narration-engines.md): edge-tts uses an unofficial
  endpoint.
- To keep caches off your system drive, set `UV_CACHE_DIR` and `VIDEO_EXPLAINER_CACHE`.

</details>

<details>
<summary><b>diagram-explainer details</b></summary>

Ask for a diagram explicitly, for example "draw a diagram of this answer", "show this as a sequence diagram" or
"畫一張圖說明 git rebase". The skill picks the format from the content: Mermaid for steps and arrows (a flow, a sequence
of messages, the states of one thing), hand-written SVG for a concept, a spatial relation, a proportion or a timeline,
which boxes and arrows cannot show. It picks the diagram type from your question (a pipeline reads left to right), sizes
the diagram to the topic and splits it only when the rendered image is hard to read. Each diagram has a title, labels
with a short name and one detail line, colors with a fixed meaning (for example pass green, fail red) explained by a
legend, and one caption line that says what to look at. For Mermaid you get the code in the reply, and `diagram.mmd`
and `caption.md` in `out/diagram-explainer/<slug>/`; for SVG you get `diagram.svg` and `caption.md` there, and the
saved paths in the reply.

- Mermaid: only `flowchart`, `sequenceDiagram` and `stateDiagram-v2`, in syntax that renders on GitHub and in common
  tools. SVG: designed for each topic, with its own background so it reads the same on light and dark pages. A stdlib
  checker script checks every diagram before you see it (for SVG: no scripts or outside files, readable text size and
  contrast).
- Optional rendering to `diagram.svg` and `diagram.png` needs [uv](https://docs.astral.sh/uv/), network access, and
  Google Chrome, Microsoft Edge or Playwright's Chromium. The skill never downloads a browser without asking you. Without
  a browser, you still get the checked Mermaid source.
- Labels follow the STE principles. They are inspired by ASD-STE100, are not official and are not endorsed by ASD.
- D2 or Graphviz only when you ask for them and have them installed.

</details>

<details>
<summary><b>html-explainer details</b></summary>

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

</details>

## How this project works

- **One format, one skill.** A skill starts only when you name its format. It never picks a format for you.
- **The model designs, scripts check.** Early versions with strict layout rules lost to Claude without the skill in
  blind tests. The skills now leave the design to the model and keep checker scripts as a floor.
- **Evidence over claims.** Every change to a skill is rated blind on the rendered output, and the losses stay in the
  results.

## Background

Andrej Karpathy [posted](https://x.com/karpathy/status/2105819303471976479) that as agents do more of the work, more of
our time goes to understanding what they produce. He suggested a ladder of formats that are easier to take in than
prose: STE writing, diagrams, interactive web pages and explainer videos ([our summary](reference/karpathy-x-post.md)).
This project turns each step into a skill you can install, test and improve.

Related projects: [ELI5](https://github.com/anthropics/claude-plugins-community) (Anthropic's community plugins),
[answer-me-with-html](https://github.com/QingYunA/answer-me-with-html).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Release notes are in [CHANGELOG.md](CHANGELOG.md). Ideas and bug reports go in
[issues](https://github.com/norton77930/understanding-ai-outputs/issues/new/choose).

## Star History

<a href="https://star-history.com/#norton77930/understanding-ai-outputs&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=norton77930/understanding-ai-outputs&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=norton77930/understanding-ai-outputs&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=norton77930/understanding-ai-outputs&type=Date" />
  </picture>
</a>

## License

[MIT](LICENSE). Copyright (c) 2026 Norton Deng.
