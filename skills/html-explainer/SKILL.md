---
name: html-explainer
description: Build one self-contained interactive HTML page that explains a topic or a piece of AI output, with a step-through, slider, layer toggle or reveal the reader can use. Use ONLY when the user explicitly asks for an interactive page, a web explainer or an HTML demo, such as "make an interactive page that explains X", "turn this answer into an interactive web explainer" or "做一個互動網頁說明 X". Never use for diagrams, videos, STE text, websites or landing pages, app components (React, Vue), fixing existing HTML or CSS, or questions about HTML.
---

# HTML explainer

Turn a topic, or an answer from this conversation, into one `index.html` file that the reader can open with a double-click. The reader learns by doing: the page lets them move through the idea, change it or uncover it. The user gets the file and a one-line summary of how to use it.

## Files

- `scripts/page_check.py`: static check of the file rules. Standard library only.
- `scripts/render_check.py`: loads the page in a headless browser and takes screenshots.
- `references/interaction-patterns.md`: four patterns with complete examples. Read it before you write the page.
- `references/design-baseline.md`: the page rules and a minimal skeleton.
- `references/checks.md`: both commands, their JSON, exit codes and environment variables.

Run every command from the user's project root. The default output folder is `out/html-explainer/<slug>/` under the current folder. Use another folder if the user names one. If git does not ignore `out/`, tell the user. Do not change `.gitignore` unasked. On Windows, set `PYTHONUTF8=1` so Chinese text stays intact.

## Workflow

1. **Pattern.** Find the one thing the reader should do to understand the concept. Pick the pattern from `references/interaction-patterns.md`:
   - a process or algorithm: step-through
   - a number that changes a result: parameter slider
   - a structure of parts or layers: layer toggles
   - a question or extra detail: reveal

   Use a second pattern only when the concept has a second part.
2. **Page.** Write ONE file, `out/html-explainer/<slug>/index.html`, from the skeleton in `references/design-baseline.md`:
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
6. **Layout check.** Look at every PNG in `screenshots`. Look for overlapping elements, clipped text, text too small or too faint to read, a dark mode with light areas, and an interaction screenshot with no change. Then check the keyboard path in the page source: the controls are native elements in a logical order (no positive `tabindex`), so Tab reaches each one, and a `:focus-visible` rule gives them a visible outline (no `outline: none` without a replacement). Fix the page, then run steps 4 to 6 again. Do at most two fix rounds. Report any problem that is left.
7. **Deliver.** Give the user:
   - the path of `index.html` (and the screenshot folder, if the render check ran)
   - one line on how to use the page, for example "Press Next to step through each check."
   - the render check status: passed, or skipped with the reason
   - any problem left after two fix rounds

## Text

Keep the text short. The interaction does the explaining. Apply these rules directly. Do not call another skill for them.

- English: relaxed STE. Use short sentences (20 words or fewer for steps, 25 for descriptions), active voice, one idea per sentence and one term per concept.
- Other languages: apply the STE principles: short sentences, active voice, one instruction per sentence, one term per concept.
- These rules are inspired by ASD-STE100. They are not official and are not endorsed by ASD. Put no note about the style on the page.
- zh-TW: use Taiwan wording (程式, 資料, 伺服器). Set `lang="zh-Hant-TW"`; `lang="zh-TW"` is also correct.
- Use one label for one thing. The button text, the caption and the paragraph use the same term.

When the source is AI output from the conversation, keep its facts. Do not add claims it does not make.
