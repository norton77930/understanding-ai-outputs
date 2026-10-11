---
name: diagram-explainer
description: Explain a topic or a piece of AI output as a diagram with a one-line caption, checked and saved to files: Mermaid for flows, sequences and states, hand-written SVG for concepts, spatial relations, proportions and timelines, and a multi-panel SVG overview sheet when asked for one. Use ONLY when the user explicitly asks for a diagram, chart, flowchart, sequence diagram, picture of how something works, or one overview image of a whole topic, such as "draw a diagram of this", "show this flow as a sequence diagram", "visualize this as a picture", "one sheet that explains X", "畫一張圖說明" or "一張圖看懂 X". Never use for videos, web pages, STE text, text cheat sheets, data plots from numbers, artwork, logos or icons, fixing broken Mermaid code, or questions about diagram notation.
---

# Diagram explainer

Turn a topic, or an answer from this conversation, into one to three diagrams that are easy to read at a glance. Each diagram answers one question, has a title, two-line labels where a detail helps, colors with a fixed meaning and a legend, and one caption line that says what to look at. Flows, sequences and states are Mermaid; concepts, spatial relations, proportions and timelines are hand-written SVG. On an explicit request for a whole-topic overview, it draws one overview sheet instead (see "Overview sheet"). The user gets the files in `out/diagram-explainer/<slug>/`.

## Files

- `scripts/diagram_check.py`: checks a Mermaid file for type, label length and fragile syntax, and warns about size. Standard library only.
- `scripts/svg_check.py`: checks an SVG file for structure, outside content, a background, text contrast and text size, and warns about text outside the canvas. Standard library only.
- `scripts/render_diagram.py`: renders a Mermaid file to SVG and PNG, or an SVG file to PNG, in a headless browser. Run it with `uv run`.
- `references/diagram-types.md`: which output and type answers which question, with one passing example per Mermaid type. Read it before you pick.
- `references/mermaid-syntax.md`: the supported Mermaid syntax (title, two-line labels, color palette, legend), quoting rules and the fragile syntax to avoid.
- `references/svg-drawing.md`: when to draw SVG, the required structure, a passing example, the checker rules in plain words, and light and dark hosts. Read it before you draw SVG.
- `references/sheet-drawing.md`: the overview sheet: when to make one, panel kinds, grid layout, text sizes at the sheet display width, title block, legend, long text and a passing example. Read it before you draw a sheet.
- `references/checks.md`: flags, JSON fields, exit codes and environment variables of the scripts.

## Workflow

1. **Find the question.** Write down the one question the diagram answers, for example "What happens when a user logs in?". When the source is AI output from the conversation, keep its facts. Do not add steps or parts it does not mention.
2. **Pick the output** from the content (details in `references/diagram-types.md`):
   - the user explicitly asks for an overview of the whole topic on one image ("one sheet that explains X", "an overview poster of X", "一張圖看懂 X", "整理成一張總覽圖", "總覽圖"): an overview sheet; follow "Overview sheet" below instead of steps 3 to 10. "Cheat sheet" alone does not count; "cheat sheet" with a picture word ("畫成 cheat sheet", "cheat sheet 圖") does
   - steps and arrows (a flow, who talks to whom in order, the states of one thing): Mermaid
   - a concept, a spatial relation (what sits where, what is inside what), a proportion (how full, how much of the whole) or a timeline: hand-written SVG
   - the user names a tool (Mermaid, SVG, D2, Graphviz): that tool (D2 and Graphviz: see "Other tools")
3. **Pick the Mermaid type** from the question (Mermaid only):
   - who talks to whom, in order over time: `sequenceDiagram`
   - the states of one thing and what moves it between them: `stateDiagram-v2`
   - a chain of stages, with or without pass/fail checks (a pipeline, data that moves through components): `flowchart LR`
   - a process where the branching is the point: `flowchart TD`
   - what contains what: `flowchart` with `subgraph` blocks
4. **One concept per diagram, sized to the topic.** There is no fixed node budget: include every step or part the question needs, and leave out detail that does not help answer it. If the topic holds more than one concept, give each concept its own diagram (at most 3), each with its own question and caption. Split one concept only when the layout check (step 10) shows that the diagram is hard to read. The Mermaid checker warns above about 20 nodes, 8 participants or 20 messages; a warning is a reason to look carefully at the render, not a failure.
5. **Style the diagram.**
   - Mermaid (syntax and palette in `references/mermaid-syntax.md`): a title in the front matter (`title: ...`) that names the topic; colors with one fixed meaning, for example pass green, fail red, one color per kind of part: `classDef` and `class` in a flowchart or state diagram, `linkStyle` for edges whose path matters, `box` and `rect` in a sequence diagram; a legend for the colors: a small `legend` subgraph in a flowchart, the caption line in a sequence or state diagram; no `%%{init}` directive and no theme change.
   - SVG (structure and example in `references/svg-drawing.md`): design each SVG for its topic; there is no fixed template. Give it a `<title>`, a `viewBox`, a first `<rect>` that fills the viewBox with an opaque background, a font stack with CJK fallbacks, colors with one fixed meaning and a legend drawn in the image, and a visible title. Draw the idea itself: a bar that fills, parts placed where they are, a time axis. Plain boxes and arrows are Mermaid's job.
6. **Write the labels** in the conversation's language. Use Taiwan wording for zh-TW (程式, 資料, 伺服器). Give a label a short name, and add a second line with one detail where it helps: `B["Test<br>runs unit tests"]` in Mermaid, a second `<tspan>` in a smaller size in SVG. Name line: about 5 words or 10 CJK characters. Detail line: about 8 words or 16 CJK characters. Apply the STE principles (inspired by ASD-STE100; not official and not endorsed by ASD):
   - Use a short verb phrase for a step ("Check token"), a noun for a part ("Auth server").
   - Use one term for one concept in all labels and in the caption.
   - Use active voice. Give one action per label.
   In a Mermaid flowchart, wrap a node label in double quotes when it has any of `( ) [ ] { } " | ; #`: `A["Charge card (Stripe)"]`. Other punctuation needs no quotes: `B{Token present?}`. Use only the syntax in `references/mermaid-syntax.md`. In SVG text, write `&amp;` for `&` and `&lt;` for `<`.
7. **Write the caption.** One sentence, STE principles, same language. Say what to look at, not what the diagram is: "Follow the token: the browser never sees the client secret.", not "This diagram shows OAuth."
8. **Save.** Pick a short kebab-case slug from the topic. Write `out/diagram-explainer/<slug>/diagram.mmd` (Mermaid) or `diagram.svg` (SVG) and `caption.md` under the current folder. For more than one diagram, write `diagram-1.mmd` or `diagram-1.svg`, `diagram-2...` and so on, and put one caption line per diagram in `caption.md`. Use another folder if the user names one. If git does not ignore `out/`, tell the user. Do not change `.gitignore` unasked.
9. **Check.** Run `python <skill folder>/scripts/diagram_check.py <file>` on each Mermaid file and `python <skill folder>/scripts/svg_check.py <file>` on each SVG file (`python3` if `python` is missing). On exit 1, fix every entry in `issues` and run the check again. Do not show a diagram that fails the check. Entries in `warnings` do not fail the check; keep them in mind for the layout check. The checker is required (Python standard library only). If Python is not available, say so and stop. Do not show an unchecked diagram.
10. **Render and look.** If `uv` is available, run `uv run <skill folder>/scripts/render_diagram.py <file>`. For Mermaid it writes `diagram.svg` and `diagram.png` next to the source; for SVG it writes `diagram.png` and leaves the SVG as it is.
    - Exit 0: open the PNG and do a layout check. Look for overlapping or clipped labels, labels too small to read, crossing edges that hide the flow, a pipeline drawn as a tall column, and colors the legend does not explain. Fix the source (or split the diagram if it is too dense to read), check it again and render again. Do at most two layout fix rounds. Report a problem left after round two.
    - Exit 1: Mermaid could not parse the diagram, the browser could not load the SVG, or the render timed out (`error` says "Render timed out"). Fix the source from `error`, then check and render again. This does not count as a layout fix round. If the render times out again, simplify the diagram, or deliver the checked source and say that rendering was skipped.
    - Exit 2: rendering is not available. Read `hint`. Never download a browser without asking the user first, and give the download size from `hint` when you ask. Without a browser or network, deliver the checked source and say that rendering was skipped and why.
    - On Windows, set `PYTHONUTF8=1`. To keep the uv cache off the system drive, set `UV_CACHE_DIR`.
11. **Reply** with, for each diagram:
    - Mermaid: the code in a ```` ```mermaid ```` block
    - the caption line
    - the saved paths (source, caption, and the SVG and PNG when rendered)

    Do not paste SVG source into the reply; the paths are enough. Add one line when rendering was skipped, with the reason. Add any layout problem left after two layout fix rounds.

## Overview sheet

Only on an explicit overview request (step 2). Without one, nothing here applies. Details and a passing example are in `references/sheet-drawing.md`.

1. **Panels.** Write 3 to 6 sub-questions that together give the overview. Each one becomes a panel with a letter tab (A, B, C ...) in reading order and a one-line heading. Pick each panel kind from its content: a tree or hierarchy, an annotated sentence or code line, a status table, value bars, a timeline, or a small flow.
2. **Draw one SVG.** A landscape canvas (1600 units wide is the simplest), panels on a grid, a title block (topic, source, date) and one legend for the whole sheet. Each color keeps one meaning in every panel. Labels, wording and language follow steps 6 and 7; break long text into lines by hand.
3. **Save** `sheet.svg` and `caption.md` (one caption line: where to start and what the colors mean) in `out/diagram-explainer/<slug>/`, as in step 8.
4. **Check** with `python <skill folder>/scripts/svg_check.py sheet.svg --sheet`. `--sheet` judges text at the 1600 px display width a sheet is viewed at; the hard floor stays. Fix every issue, as in step 9.
5. **Render and look** as in step 10, at most two layout fix rounds. Also look for text clipped by a panel border and colors used against the legend.
6. **Reply** with the caption line and the saved paths, as in step 11.

## Other tools

Use D2 or Graphviz only when the user asks for it and the tool is installed (`d2 --version`, `dot -V`). Keep the same workflow: one question, sized to the topic, title, colors with a legend, STE-principle labels, caption, saved source. The checkers do not support them. Do not install either tool unasked.
