---
name: diagram-explainer
description: Explain a topic or a piece of AI output as a Mermaid diagram (flowchart, sequence or state diagram) with a one-line caption, checked and saved to files. Use ONLY when the user explicitly asks for a diagram, chart, flowchart, sequence diagram or picture of how something works, such as "draw a diagram of this", "show this flow as a sequence diagram", "visualize this as a picture" or "畫一張圖說明". Never use for videos, web pages, STE text, data plots from numbers, artwork, fixing broken Mermaid code, or questions about diagram notation.
---

# Diagram explainer

Turn a topic, or an answer from this conversation, into one to three small Mermaid diagrams. Each diagram answers one question and has one caption line that says what to look at. The user gets the Mermaid code in the reply and the files in `out/diagram-explainer/<slug>/`.

## Files

- `scripts/diagram_check.py`: checks a Mermaid file for type, budgets, label length and fragile syntax. Standard library only.
- `scripts/render_diagram.py`: renders a Mermaid file to SVG and PNG in a headless browser. Run it with `uv run`.
- `references/diagram-types.md`: which type answers which question, with one passing example per type. Read it before you pick a type.
- `references/mermaid-syntax.md`: the supported syntax, quoting rules and the fragile syntax to avoid.
- `references/checks.md`: flags, JSON fields, exit codes and environment variables of both scripts.

## Workflow

1. **Find the question.** Write down the one question the diagram answers, for example "What happens when a user logs in?". When the source is AI output from the conversation, keep its facts. Do not add steps or parts it does not mention.
2. **Pick the type** from the question (details in `references/diagram-types.md`):
   - who talks to whom, in order over time: `sequenceDiagram`
   - the states of one thing and what moves it between them: `stateDiagram-v2`
   - steps and decisions: `flowchart TD`
   - data that moves through components: `flowchart LR`
   - what contains what: `flowchart` with `subgraph` blocks
3. **One concept per diagram.** If the topic holds more than one concept, or does not fit the budgets, split it into at most 3 diagrams. Give each diagram its own question and caption. Leave out detail that does not help answer the question.
4. **Keep the budgets.** Flowchart and state diagram: 12 nodes or fewer. Sequence diagram: 6 participants or fewer and 12 messages or fewer. Each label: 5 words or fewer, or 10 CJK characters or fewer.
5. **Write the labels** in the conversation's language. Use Taiwan wording for zh-TW (程式, 資料, 伺服器). Apply the STE principles (inspired by ASD-STE100; not official and not endorsed by ASD):
   - Use a short verb phrase for a step ("Check token"), a noun for a part ("Auth server").
   - Use one term for one concept in all labels and in the caption.
   - Use active voice. Give one action per label.
   In a flowchart, wrap a node label in double quotes when it has any of `( ) [ ] { } " | ; #`: `A["Charge card (Stripe)"]`. Other punctuation needs no quotes: `B{Token present?}`. Use only the syntax in `references/mermaid-syntax.md`.
6. **Write the caption.** One sentence, STE principles, same language. Say what to look at, not what the diagram is: "Follow the token: the browser never sees the client secret.", not "This diagram shows OAuth."
7. **Save.** Pick a short kebab-case slug from the topic. Write `out/diagram-explainer/<slug>/diagram.mmd` and `caption.md` under the current folder. For more than one diagram, write `diagram-1.mmd`, `diagram-2.mmd` and so on, and put one caption line per diagram in `caption.md`. Use another folder if the user names one. If git does not ignore `out/`, tell the user. Do not change `.gitignore` unasked.
8. **Check.** Run `python <skill folder>/scripts/diagram_check.py <file>` (`python3` if `python` is missing) on each file. On exit 1, fix every entry in `issues` and run the check again. Do not show a diagram that fails the check. The checker is required (Python standard library only). If Python is not available, say so and stop. Do not show an unchecked diagram.
9. **Render and look.** If `uv` is available, run `uv run <skill folder>/scripts/render_diagram.py <file>`. It writes `diagram.svg` and `diagram.png` next to the source.
   - Exit 0: open the PNG and do a layout check. Look for overlapping or clipped labels, labels too small to read, and crossing edges that hide the flow. Fix the source, check it again and render again. Do at most two layout fix rounds. Report a problem left after round two.
   - Exit 1: Mermaid could not parse the diagram, or the render timed out (`error` says "Render timed out"). Fix the source from `error`, then check and render again. This does not count as a layout fix round. If the render times out again, simplify the diagram, or deliver the checked source and say that rendering was skipped.
   - Exit 2: rendering is not available. Read `hint`. Never download a browser without asking the user first, and give the download size from `hint` when you ask. Without a browser or network, deliver the checked source and say that rendering was skipped and why.
   - On Windows, set `PYTHONUTF8=1`. To keep the uv cache off the system drive, set `UV_CACHE_DIR`.
10. **Reply** with, for each diagram:
    - the Mermaid code in a ```` ```mermaid ```` block
    - the caption line
    - the saved paths (source, caption, and SVG and PNG when rendered)

    Add one line when rendering was skipped, with the reason. Add any layout problem left after two layout fix rounds.

## Other tools

Use D2 or Graphviz only when the user asks for it and the tool is installed (`d2 --version`, `dot -V`). Keep the same workflow: one question, budgets, STE-principle labels, caption, saved source. The checker does not support them. Do not install either tool unasked.
