# Mermaid syntax

Use only this subset. It renders on GitHub, in common IDE previews and in `scripts/render_diagram.py` (Mermaid 11). The checker supports these three types only.

## Supported subset

### Flowchart

- Header: `flowchart TD` (top down) or `flowchart LR` (left to right). `graph` also works, but write `flowchart`.
- Node: `ID[Label]`. IDs are letters, digits and `_` with no spaces: `A`, `api`, `auth_server`.
- Shapes: `[box]` for a step or part, `{decision?}` for a question, `([start or end])`, `[(database)]`, `((circle))`. Keep to these.
- Edges: `-->` (arrow), `---` (line), `-.->` (dotted), `==>` (thick).
- Edge label: `A -->|Yes| B`. Also valid, but less clear: `A -- Yes --> B`.
- Several edges at once: `A & B --> C` counts as two edges.
- Containment: `subgraph id [Title]` ... `end`. Every `subgraph` needs its own `end`. Subgraphs can nest.

### Sequence diagram

- Header: `sequenceDiagram`.
- Participants: `participant A as Auth server`, or `actor U as User` for a person. Declare them in the order you want them from left to right.
- Messages: `A->>B: Label` (request), `B-->>A: Label` (reply). One message per line.
- Blocks: `alt Condition` ... `else Other` ... `end`, `opt Condition` ... `end`, `loop Every minute` ... `end`. Every block needs its own `end`.
- Notes: `Note over A,B: Short text`.

### State diagram

- Header: `stateDiagram-v2`.
- Start and end: `[*] --> First` and `Last --> [*]`.
- Transition: `From --> To : Event`.
- State IDs have no spaces. For a label with spaces, write `state "Waiting for payment" as Waiting`, then use `Waiting` in transitions.
- Composite state: `state Parent {` ... `}`. Every `{` needs its `}`.

## Quoting rules

- Wrap a flowchart label in double quotes when it has any of `( ) [ ] { } " | ; #`: `C["Charge card (Stripe)"]`.
- A quoted label cannot hold a double quote. Rephrase, or use single quotes inside: `A["Run 'npm test'"]`.
- Do not start a node ID with a reserved word such as `end`. Write `done` or `finish` instead.
- Keep `:` out of sequence participant names. In a message, everything after the first `:` is the label.
- CJK labels need no quotes unless they have one of the characters above. Full-width punctuation (，？：) is safe.

## Fragile syntax the checker flags

| Checker rule | What it catches | Do this instead |
| --- | --- | --- |
| `unsupported-type` | No diagram, or a type such as `classDiagram`, `erDiagram`, `gantt` or `mindmap` | Use `flowchart`, `sequenceDiagram` or `stateDiagram-v2` |
| `too-many-nodes`, `too-many-participants`, `too-many-messages` | A diagram over its budget | Split into at most 3 diagrams, or remove detail that does not answer the question |
| `label-too-long` | A label over 5 words or 10 CJK characters | Shorten to a verb phrase or a noun. Move detail to the caption |
| `html-in-label` | `<br>`, `<b>` or another HTML tag in a label | Use a shorter label. Some renderers show the tags as text |
| `click-callback` | A `click` line | Remove it. Links and callbacks do not work in most viewers |
| `init-directive` | `%%{init: ...}%%`, or `config` or `theme` in front matter | Remove it. Use the default theme |
| `style-url` | `url(` in a `style`, `classDef` or `linkStyle` line | Remove it. External resources do not load everywhere |
| `unbalanced-block` | A `subgraph`, `alt`, `opt`, `loop` or `state {` without its `end` or `}` | Close every block |
| `unquoted-label` | A flowchart label with `( ) [ ] { } " \| ; #` outside double quotes | Wrap the label in double quotes |

Also avoid these, which the checker does not catch:

- Markdown strings in labels (`` "`**bold**`" ``) and icons (`fa:fa-user`).
- New shape syntax (`A@{ shape: ... }`), which old renderers do not know.
- `style` and `classDef` color changes. They can make labels hard to read in dark mode.
- Comments at the end of a line. Put `%%` comments on their own line.

The checker is line based and approximate. A diagram that passes can still fail to render. When `render_diagram.py` exits 1, its `error` field has Mermaid's own message.
