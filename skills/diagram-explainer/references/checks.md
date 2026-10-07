# Checks

Both scripts print one JSON object on stdout in UTF-8. On Windows, set `PYTHONUTF8=1` so Chinese labels stay intact in the terminal.

## diagram_check.py

Standard library only. Run it with `python` (`python3` if `python` is missing).

```
python <skill folder>/scripts/diagram_check.py [FILE|-] [--max-nodes N] [--max-participants N]
    [--max-messages N] [--max-label-words N] [--max-label-chars N]
```

- Input: FILE, or stdin when FILE is `-` or missing. UTF-8, a BOM is fine.
- Budgets (defaults): `--max-nodes 12`, `--max-participants 6`, `--max-messages 12`, `--max-label-words 5`, `--max-label-chars 10`. A value equal to the budget passes. Change a budget only when the user asks.

Exit codes:

| Code | Meaning |
| --- | --- |
| 0 | Pass: no issues |
| 1 | Check failed: fix every entry in `issues` |
| 2 | Usage or input error (bad flag, file not readable) |

JSON fields:

| Field | Content |
| --- | --- |
| `type` | `flowchart` (also for `graph`), `sequenceDiagram`, `stateDiagram-v2` (also for `stateDiagram`), the first word of an unsupported type, or `null` when there is no diagram |
| `counts` | Flowchart: `nodes`, `edges`, `subgraphs`. Sequence: `participants`, `messages`. State: `states` (without `[*]`), `transitions`. Empty for unsupported types |
| `budgets` | The budgets in use: `max_nodes`, `max_participants`, `max_messages`, `max_label_words`, `max_label_chars` |
| `labels` | One entry per label: `text`, `words` (Latin words), `chars` (CJK characters), `over` (true when over a budget) |
| `issues` | One entry per problem: `rule`, `line`, `message`. The rules are listed in `mermaid-syntax.md` |
| `pass` | true when `issues` is empty |

The checker is line based and approximate, not a Mermaid parser. It reads one statement per line, skips full-line `%%` comments and front matter, and counts `A & B --> C` as two edges. HTML tags are ignored when it measures a label.

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
| 1 | Mermaid reported a parse or render error. No files are written | Fix the source from `error`, check it and render again |
| 2 | Environment or input problem: no Playwright, no browser, no network, unreadable file | Read `hint`. Ask before any browser download. Otherwise deliver the source and say rendering was skipped |

JSON fields: `svg` and `png` (paths or `null`), `width` and `height` (PNG size in pixels or `null`), `mermaid_version`, `browser` (the browser used or `null`), `error` (message or `null`), and `hint` (only with exit 2).

## Environment variables

| Variable | Used by | Effect |
| --- | --- | --- |
| `PYTHONUTF8=1` | both | UTF-8 console output on Windows |
| `UV_CACHE_DIR` | `uv run` | Where uv keeps Python packages. Set it to keep the cache off the system drive |
| `PLAYWRIGHT_BROWSERS_PATH` | `render_diagram.py` | Where Playwright's Chromium is installed and looked for. Keep it set the same way for install and render |
| `DIAGRAM_RENDER_SIMULATE` | `render_diagram.py` | Tests only: `no-playwright` or `no-browser` acts as if that part is missing |

The Chromium download is about 300 MB (about 700 MB on disk). Install it only after the user agrees, with the command in `hint`.
