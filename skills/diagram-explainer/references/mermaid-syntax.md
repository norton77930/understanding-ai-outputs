# Mermaid syntax

Use only this subset. It renders on GitHub, in common IDE previews and in `scripts/render_diagram.py` (Mermaid 11). The checker supports these three types only.

## Supported subset

### Title

Put the title in front matter at the very top of the file. Only `title` goes there:

```
---
title: CI pipeline for a pull request
---
flowchart LR
```

Do not add `config`, `theme` or other keys to the front matter.

### Two-line labels

Write a name line, then `<br>`, then one detail line: `B["Test<br>runs unit tests"]`. Use `<br>` only between the two lines. Use one `<br>` at most.

Why `<br>`: Mermaid documents `<br>` as its line break in labels (for example in sequence messages and notes), Mermaid renders it in flowchart and state labels too, and it is the form GitHub's Mermaid renders in all three types. `render_diagram.py` (pinned Mermaid 11) renders it in node, edge, participant, message and state labels. The alternative, a Markdown string with a newline inside the label (`` "`Test ``, new line, `` runs tests`" ``), works only in flowcharts, puts a line break inside one statement, and old renderers show it as text.

- Flowchart node: `B["Test<br>runs unit tests"]`. Double quotes are optional for `<br>`, but the quoting rules below still apply to the rest of the label.
- Edge: `A -->|pass<br>all checks green| B`.
- Sequence: `participant B as Browser<br>user tab` and `B->>A: Send code<br>in the URL`.
- State: `state "Review<br>a maintainer reads the PR" as Review`, and `A --> B : Reject<br>not a bug`.

Limits (checked): name line about 5 words or 10 CJK characters, detail line about 8 words or 16 CJK characters.

### Colors and legend

Give each color one meaning in the diagram, and explain the colors in a legend. Use this palette. Each class sets `fill`, `stroke` and the text `color`, so the label stays readable in light and dark mode:

| Meaning (examples) | Class line |
| --- | --- |
| Pass, done, allowed | `classDef ok fill:#d4edda,stroke:#2e7d32,color:#1b3d1f` |
| Fail, error, rejected | `classDef bad fill:#f8d7da,stroke:#c62828,color:#5a1414` |
| Check, wait, warning | `classDef check fill:#fff3cd,stroke:#b8860b,color:#4a3800` |
| Main part or step | `classDef main fill:#e3f2fd,stroke:#1565c0,color:#0d2a4a` |
| Data, external or managed part | `classDef data fill:#eeeeee,stroke:#616161,color:#212121` |

Rename a class to fit its meaning (`sync`, `async`, `inside`). Do not use more than about 4 colors in one diagram.

- Flowchart and state diagram: define classes with `classDef name fill:...,stroke:...,color:...`. Apply them with `class A,B name`, or with a `:::name` suffix on a node (`C[Deploy]:::ok`, `Open:::wait`).
- Flowchart edges: `linkStyle 2,3 stroke:#2e7d32,stroke-width:2px`. The numbers count edges from 0 in the order they appear in the file, invisible links (`~~~`) included. Write the legend subgraph after all real edges so the numbers stay the same.
- Sequence diagram: `classDef` does not work. Group participants with `box rgb(227, 242, 253) Your side` ... `end`, and mark a phase with `rect rgb(212, 237, 218)` ... `end`. Use the light fills of the palette as `rgb(...)`.
- Legend in a flowchart: a small subgraph after the real edges, one node per color, chained with invisible links so it stays on one row:

  ```
      subgraph legend [Legend]
          direction LR
          k1["Passed"]:::ok
          k2["Failed"]:::bad
          k1 ~~~ k2
      end
  ```

  Legend nodes count toward the node total.
- Legend in a sequence or state diagram: in the caption line, in parentheses: "(green: done, red: failed)".

### Flowchart

- Header: `flowchart TD` (top down) or `flowchart LR` (left to right). `graph` also works, but write `flowchart`.
- Node: `ID[Label]`. IDs are letters, digits and `_` with no spaces: `A`, `api`, `auth_server`.
- Shapes: `[box]` for a step or part, `{decision?}` for a question, `([start or end])`, `[(database)]`, `((circle))`. Keep to these.
- Edges: `-->` (arrow), `---` (line), `-.->` (dotted), `==>` (thick), `~~~` (invisible, only to place legend nodes).
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
| `label-too-long` | A name line over 5 words or 10 CJK characters, a detail line over 8 words or 16 CJK characters, or more than two lines | Shorten the name to a verb phrase or a noun. Keep one short detail line. Move other detail to the caption |
| `html-in-label` | `<b>`, `<i>` or another HTML tag other than `<br>` in a label | Use plain text. Some renderers show the tags as text |
| `click-callback` | A `click` line | Remove it. Links and callbacks do not work in most viewers |
| `init-directive` | `%%{init: ...}%%`, or `config` or `theme` in front matter | Remove it. Keep the default theme and set colors with `classDef` |
| `style-url` | `url(` in a `style`, `classDef` or `linkStyle` line | Remove it. External resources do not load everywhere |
| `unbalanced-block` | A `subgraph`, `alt`, `opt`, `loop` or `state {` without its `end` or `}` | Close every block |
| `unquoted-label` | A flowchart label with `( ) [ ] { } " \| ; #` outside double quotes | Wrap the label in double quotes |

The checker also gives warnings. A warning does not fail the check:

| Warning rule | What it means | Do this |
| --- | --- | --- |
| `too-many-nodes`, `too-many-participants`, `too-many-messages` | More than about 20 nodes or states, 8 participants or 20 messages | Render and do the layout check. Split into at most 3 diagrams only when the image is hard to read |

Also avoid these, which the checker does not catch:

- Markdown strings in labels (`` "`**bold**`" ``) and icons (`fa:fa-user`).
- New shape syntax (`A@{ shape: ... }`), which old renderers do not know.
- A `classDef` or `style` without a text `color`, or a fill that is not from the palette. The label can be hard to read in dark mode.
- Color as the only cue. Keep the meaning in the label or the edge text too ("pass", "fail").
- Comments at the end of a line. Put `%%` comments on their own line.

The checker is line based and approximate. A diagram that passes can still fail to render. When `render_diagram.py` exits 1, its `error` field has Mermaid's own message.
