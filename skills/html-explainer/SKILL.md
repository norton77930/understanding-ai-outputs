---
name: html-explainer
description: Build one self-contained HTML page that explains a topic or a piece of AI output as an interactive, designed page, with animation where it helps. Use ONLY when the user explicitly asks for an interactive page, a web explainer, an HTML demo, or an explanation or answer in HTML, such as "make an interactive page that explains X", "explain X in HTML", "做一個互動網頁說明 X" or "用 HTML 解釋 X". Never use for diagrams, videos, STE text, websites or landing pages, app components (React, Vue), fixing existing HTML or CSS, questions about HTML, or converting Markdown or other content to HTML.
---

# HTML explainer

Turn a topic, or an answer from this conversation, into one `index.html` file that the reader can open with a double-click. The reader learns by doing: the page lets them move through the idea, change it or uncover it. The user gets the file and a one-line summary of how to use it.

## Files

- `scripts/page_check.py`: static check of the file rules. Standard library only.
- `scripts/render_check.py`: loads the page in a headless browser and takes screenshots.
- `references/interaction-patterns.md`: six patterns with complete examples, and how to combine them. Read it before you write the page.
- `references/design-baseline.md`: the page rules, design guidance and a minimal skeleton.
- `references/checks.md`: both commands, their JSON, exit codes and environment variables.

Run every command from the user's project root. The default output folder is `out/html-explainer/<slug>/` under the current folder. Use another folder if the user names one. If git does not ignore `out/`, tell the user. Do not change `.gitignore` unasked. On Windows, set `PYTHONUTF8=1` so Chinese text stays intact.

## Workflow

1. **Plan.** List the key points of the topic. Let the topic decide how many: typically 3 to 6, more for a broad topic. If the user gives a list of points, use that list. The usual shape is a title, a lead that states the main conclusion, and one section per point that starts with its point. Use another shape if the topic calls for it, but explain every point. For each section, choose the pattern from `references/interaction-patterns.md` that makes the point clearer when the reader does something:
   - a process or algorithm: step-through
   - a number that changes a result: parameter slider
   - a structure of parts or layers: layer toggles
   - a definition or extra detail: reveal
   - a result the reader can guess first: predict-then-reveal
   - a behavior that depends on the input: preset scenarios

   Several patterns on one page are normal. Use motion where the point is about change.
2. **Page.** Write ONE file, `out/html-explainer/<slug>/index.html`. The skeleton in `references/design-baseline.md` is only the required minimum. Design the page for this topic, as "Design" in that file describes. The page must have:
   - `<html lang>` in the conversation's language, a `<title>` and a viewport meta.
   - Colors as CSS custom properties, with a `prefers-color-scheme: dark` override. Set the `body` background.
   - No horizontal scroll at 390 px.
   - Native controls (`button`, `input type="range"`, checkboxes, `details`) with labels and a visible focus ring.
   - `addEventListener` in the script. No `onclick=` or other inline handlers.
   - No external resources by default. If a library is necessary, load it only from cdnjs, jsDelivr or unpkg, at an exact version.
   - The key idea is readable before any interaction.
   - The render check clicks the first visible, enabled `<button>`. Make that button change the page.
3. **Text.** Write the page text with the rules in "Text" below.
4. **Static check.** Run `python <skill folder>/scripts/page_check.py <file>` (`python3` if `python` is missing). On exit 1, fix each entry in `issues` and run it again until it exits 0.
5. **Render check.** Run `uv run <skill folder>/scripts/render_check.py <file>`.
   - Exit 1: the page has a problem. Fix each entry in `console_errors` and `page_errors`, the overflow if `overflow_390.overflow` is true, the cause in `interaction_error` (for example an element that covers the button) and the cause in `load_error` (for example a resource that does not load). Then run the check again. Do not skip the render check or the layout check on exit 1.
   - Exit 2: read `error` and `hint`. If Playwright or a browser is missing, skip the render check and the layout check. Tell the user that the render check was skipped and why. If `error` starts with `render failed`, run the check once more. Never download a browser without asking. If the user wants one, state the size (about 300 MB download) and the command from the `hint`, and wait for a yes.
6. **Layout check.** Look at every PNG in `screenshots`. Look for overlapping elements, clipped text, text too small or too faint to read, a dark mode with light areas, an interaction screenshot with no change, and any drawn shape or number that does not match the math the page states (for example a stray curve). Then check the keyboard path in the page source: the controls are native elements in a logical order (no positive `tabindex`), so Tab reaches each one, and a `:focus-visible` rule gives them a visible outline (no `outline: none` without a replacement). Fix the page, then run steps 4 to 6 again. Do at most two fix rounds. Report any problem that is left.
7. **Deliver.** Give the user:
   - the path of `index.html` (and the screenshot folder, if the render check ran)
   - one line on how to use the page, for example "Press Next to step through each check."
   - the render check status: passed, or skipped with the reason
   - any problem left after two fix rounds

## Text

The text names each point. The interaction demonstrates it. Apply these rules to each sentence directly. Do not call another skill for them.

- Never cut a key point to save words. Keep the sentences short, not the page.
- English: relaxed STE. Use short sentences (20 words or fewer for steps, 25 for descriptions), active voice, one idea per sentence and one term per concept.
- Other languages: apply the STE principles: short sentences, active voice, one instruction per sentence, one term per concept.
- These rules are inspired by ASD-STE100. They are not official and are not endorsed by ASD. Put no note about the style on the page.
- zh-TW: use Taiwan wording (程式, 資料, 伺服器). Set `lang="zh-Hant-TW"`; `lang="zh-TW"` is also correct.
- Use one label for one thing. The button text, the caption and the paragraph use the same term.

When the source is AI output from the conversation, keep its facts. Do not add claims it does not make.
