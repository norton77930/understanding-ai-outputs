# Checks

Both scripts print one JSON object on stdout in UTF-8. On Windows, set `PYTHONUTF8=1` so Chinese labels stay intact in the terminal.

## diagram_check.py

Standard library only. Run it with `python` (`python3` if `python` is missing). The checker is required: without Python, do not show an unchecked diagram.

```
python <skill folder>/scripts/diagram_check.py [FILE|-] [--max-nodes N] [--max-participants N]
    [--max-messages N] [--max-label-words N] [--max-label-chars N]
    [--max-detail-words N] [--max-detail-chars N]
```

- Input: FILE, or stdin when FILE is `-` or missing. UTF-8, a BOM is fine.
- Soft size limits (defaults): `--max-nodes 20`, `--max-participants 8`, `--max-messages 20`. Above a limit, the checker adds a warning. A warning does not fail the check.
- Label limits (defaults): name line `--max-label-words 5` and `--max-label-chars 10`; detail line (after `<br>`) `--max-detail-words 8` and `--max-detail-chars 16`. A label over a limit fails the check. A value equal to the limit passes.
- Change a limit only when the user asks.

Exit codes:

| Code | Meaning |
| --- | --- |
| 0 | Pass: no issues (there can be warnings) |
| 1 | Check failed: fix every entry in `issues` |
| 2 | Usage or input error (bad flag, file not readable) |

JSON fields:

| Field | Content |
| --- | --- |
| `type` | `flowchart` (also for `graph`), `sequenceDiagram`, `stateDiagram-v2` (also for `stateDiagram`), the first word of an unsupported type, or `null` when there is no diagram |
| `counts` | Flowchart: `nodes`, `edges`, `subgraphs`. Sequence: `participants`, `messages`. State: `states` (without `[*]`), `transitions`. Empty for unsupported types |
| `budgets` | The limits in use: `max_nodes`, `max_participants`, `max_messages` (soft), `max_label_words`, `max_label_chars` (name line), `max_detail_words`, `max_detail_chars` (detail line) |
| `labels` | One entry per label: `text` (with `<br>`), `words` and `chars` (Latin words and CJK characters of the name line), `detail_words` and `detail_chars` (of the detail line, `null` without one), `over` (true when a line is over its limit or the label has more than two lines) |
| `issues` | One entry per problem: `rule`, `line`, `message`. The rules are listed in `mermaid-syntax.md` |
| `warnings` | One entry per soft limit passed: `rule` (`too-many-nodes`, `too-many-participants`, `too-many-messages`), `line`, `message`. Warnings do not change `pass` |
| `pass` | true when `issues` is empty |

The checker is line based and approximate, not a Mermaid parser. It reads one statement per line, skips full-line `%%` comments and front matter (a `title` is fine), and counts `A & B --> C` as two edges. It accepts `classDef`, `class`, `style`, `linkStyle` and `:::name` suffixes, and does not count them as nodes. Invisible links (`~~~`) count as edges. HTML tags are ignored when it measures a label.

## render_diagram.py

Needs `uv`. The inline (PEP 723) block installs Playwright on first use.

```
uv run <skill folder>/scripts/render_diagram.py FILE.mmd [--out DIR]
```

- Writes `DIR/<name>.svg` and `DIR/<name>.png`. DIR defaults to the folder of FILE. The PNG is at device scale 2 with a small white margin.
- Loads Mermaid 11 (a pinned version) from `cdn.jsdelivr.net`, so it needs network.
- Never downloads a browser. It tries Playwright's Chromium (if already installed), then Google Chrome, then Microsoft Edge.

Exit codes:

| Code | Meaning | What to do |
| --- | --- | --- |
| 0 | Rendered | Open `png` and do the layout check |
| 1 | Mermaid reported a parse or render error, or the render timed out (`error` says "Render timed out"). No files are written | Fix the source from `error`, check it and render again. After a second timeout, simplify the diagram or skip rendering |
| 2 | Environment or input problem: no Playwright, no browser, no network (Mermaid, or one of its diagram chunks that loads on demand, did not load), unreadable file, unexpected crash | Read `hint`. Ask before any browser download. Otherwise deliver the source and say rendering was skipped |

The render has a 30 second limit. The input file is read as UTF-8, and a BOM is ignored.

JSON fields: `svg` and `png` (paths or `null`), `width` and `height` (PNG size in pixels or `null`), `mermaid_version`, `browser` (the browser used or `null`), `error` (message or `null`), and `hint` (only with exit 2).

## Environment variables

| Variable | Used by | Effect |
| --- | --- | --- |
| `PYTHONUTF8=1` | both | UTF-8 console output on Windows |
| `UV_CACHE_DIR` | `uv run` | Where uv keeps Python packages. Set it to keep the cache off the system drive |
| `PLAYWRIGHT_BROWSERS_PATH` | `render_diagram.py` | Where Playwright's Chromium is installed and looked for. Keep it set the same way for install and render |
| `DIAGRAM_RENDER_SIMULATE` | `render_diagram.py` | Tests only: `no-playwright` or `no-browser` acts as if that part is missing. `chunk-fetch-failure` acts as if a Mermaid chunk could not load (exit 2). `crash` raises an unexpected error (exit 2) |
| `DIAGRAM_RENDER_TIMEOUT_MS` | `render_diagram.py` | Tests only: render time limit in milliseconds (default 30000) |

The Chromium download is about 300 MB (about 700 MB on disk). Install it only after the user agrees, with the command in `hint`.
