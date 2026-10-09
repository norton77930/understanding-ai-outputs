# Diagram types

Pick the type from the question the diagram answers, not from the topic. One topic can need two types: "How does OAuth work?" is a sequence (who sends what to whom), but "What states does a token go through?" is a state diagram.

| The question is about | Type | Header |
| --- | --- | --- |
| Who talks to whom, in order over time ("What happens when ...?") | Sequence | `sequenceDiagram` |
| The states of one thing and what moves it between them ("What states does ... go through?") | State | `stateDiagram-v2` |
| A chain of stages, with or without pass/fail checks: a pipeline, data that moves through components ("What are the steps?", "Where does the data go?") | Flowchart, left to right | `flowchart LR` |
| A process where the branching is the point ("How does ... decide?", "What happens if ...?") | Flowchart, top down | `flowchart TD` |
| What contains what ("What runs where?", "What is inside ...?") | Flowchart with subgraphs | `flowchart LR` or `flowchart TD` plus `subgraph` |

A pipeline stays `flowchart LR` even when it has checks that can fail: the stages read as a line, and the failure exits go to the side. Use `flowchart TD` only when the decisions are what the reader must follow.

## Size

There is no fixed node budget. Put in every step or part that the question needs, and leave out detail that does not help answer it. The checker warns above about 20 nodes or states (sequence: about 8 participants or 20 messages). A warning does not fail the check. Split the topic into at most 3 diagrams, one concept each, only when the layout check of the rendered image shows that the diagram is hard to read.

## Style

Every example below has:

- **A title** in the front matter (`title:`). It names the topic.
- **Two-line labels** where a detail helps: a short name, `<br>`, then one detail ("Test<br>runs unit tests"). Name line: about 5 words or 10 CJK characters. Detail line: about 8 words or 16 CJK characters.
- **Colors with one fixed meaning** in each diagram, set with `classDef` and `class` (flowchart, state) or `box` and `rect` (sequence). Use the palette in `mermaid-syntax.md`. Give one color to each kind of part or result, for example pass green and fail red. Color edges with `linkStyle` when the path matters.
- **A legend** that explains each color: a small `legend` subgraph in a flowchart, or the caption line in a sequence or state diagram.

Each example below passes `scripts/diagram_check.py` and renders with `scripts/render_diagram.py`. Each one has the caption line that goes into `caption.md`.

## Sequence: who talks to whom over time

```mermaid
---
title: OAuth login with an authorization code
---
sequenceDiagram
    box rgb(227, 242, 253) Your side
        participant B as Browser
        participant A as App server
    end
    box rgb(255, 243, 205) Identity provider
        participant S as Auth server
    end
    B->>A: Click Log in
    A-->>B: Redirect<br>to the auth server
    B->>S: Sign in<br>with password
    S-->>B: Redirect<br>with a one-time code
    B->>A: Send code
    rect rgb(212, 237, 218)
        A->>S: Trade code for token<br>with the client secret
        S-->>A: Access token
    end
    A-->>B: Show account page
```

Caption: Follow the code: the browser carries it, but only the app server trades it for a token (green: the step that uses the client secret).

## State: the lifecycle of one thing

```mermaid
---
title: Life of an issue
---
stateDiagram-v2
    state "Open<br>waits for an owner" as Open
    state "In progress<br>owner writes the fix" as InProgress
    state "Review<br>a maintainer reads the PR" as Review
    state "Closed<br>merged or rejected" as Closed
    [*] --> Open
    Open --> InProgress : Assign
    InProgress --> Review : Open pull request
    Review --> InProgress : Request changes
    Review --> Closed : Merge
    Open --> Closed : Reject
    Closed --> [*]
    classDef wait fill:#fff3cd,stroke:#b8860b,color:#4a3800
    classDef work fill:#e3f2fd,stroke:#1565c0,color:#0d2a4a
    classDef done fill:#d4edda,stroke:#2e7d32,color:#1b3d1f
    class Open,Review wait
    class InProgress work
    class Closed done
```

Caption: Look at Review: an issue can go back to work many times before it closes (yellow: waits for a person, blue: work, green: done).

## Flowchart LR: a pipeline with pass/fail checks

```mermaid
---
title: CI pipeline for a pull request
---
flowchart LR
    push(["Push<br>new commit"]) --> build["Build<br>compiles the code"]
    build --> lint{"Lint<br>style rules"}
    lint -->|pass| test{"Test<br>runs unit tests"}
    test -->|pass| deploy["Deploy<br>to staging"]
    lint -->|fail| stop["Stop<br>report on the PR"]
    test -->|fail| stop
    subgraph legend [Legend]
        direction LR
        k1["Check"]:::check
        k2["Passed"]:::ok
        k3["Failed"]:::bad
        k1 ~~~ k2 ~~~ k3
    end
    classDef check fill:#fff3cd,stroke:#b8860b,color:#4a3800
    classDef ok fill:#d4edda,stroke:#2e7d32,color:#1b3d1f
    classDef bad fill:#f8d7da,stroke:#c62828,color:#5a1414
    class lint,test check
    class deploy ok
    class stop bad
    linkStyle 2,3 stroke:#2e7d32,stroke-width:2px
    linkStyle 4,5 stroke:#c62828,stroke-width:2px
```

Caption: Follow the green path: a commit reaches staging only after both checks pass; any failed check stops the run.

## Flowchart TD: branching is the point

```mermaid
---
title: How the API checks a request
---
flowchart TD
    A(["Request arrives<br>with headers"]) --> B{"Token present?<br>Authorization header"}
    B -->|No| C["Return 401<br>asks the client to log in"]
    B -->|Yes| D{"Token expired?<br>compares the exp time"}
    D -->|Yes| C
    D -->|No| E["Run handler<br>reads or writes data"]
    E --> F(["Return response<br>status 200"])
    subgraph legend [Legend]
        direction LR
        k1["Check"]:::check
        k2["Allowed"]:::ok
        k3["Rejected"]:::bad
        k1 ~~~ k2 ~~~ k3
    end
    classDef check fill:#fff3cd,stroke:#b8860b,color:#4a3800
    classDef ok fill:#d4edda,stroke:#2e7d32,color:#1b3d1f
    classDef bad fill:#f8d7da,stroke:#c62828,color:#5a1414
    class B,D check
    class E,F ok
    class C bad
    linkStyle 1,3 stroke:#c62828,stroke-width:2px
```

Caption: Two checks stand before the handler; each red path returns 401.

## Flowchart LR: data through components (zh-TW)

```mermaid
---
title: 照片上傳與縮圖
---
flowchart LR
    A["手機 App<br>使用者拍照"] -->|上傳照片| B["API 伺服器<br>立刻回應"]
    B -->|存檔| C[("物件儲存<br>原圖與縮圖")]
    B -->|送出工作| D["工作佇列<br>排隊等待"]
    D --> E["縮圖程式<br>背景執行"]
    E -->|讀取原圖| C
    E -->|寫入縮圖| C
    subgraph legend [圖例]
        direction LR
        k1["同步步驟"]:::sync
        k2["非同步步驟"]:::async
        k3[("資料")]:::data
        k1 ~~~ k2 ~~~ k3
    end
    classDef sync fill:#e3f2fd,stroke:#1565c0,color:#0d2a4a
    classDef async fill:#fff3cd,stroke:#b8860b,color:#4a3800
    classDef data fill:#eeeeee,stroke:#616161,color:#212121
    class A,B sync
    class D,E async
    class C data
```

Caption: 看佇列：API 伺服器不等縮圖完成就回應。

## Flowchart with subgraphs: what contains what

```mermaid
---
title: What runs inside the cluster
---
flowchart LR
    subgraph cluster [Kubernetes cluster]
        subgraph pod [Pod]
            APP["App container<br>serves the API"]
            SIDE["Log sidecar<br>ships log lines"]
        end
        SVC["Service<br>stable address"]
    end
    DB[("Managed database<br>outside the cluster")]
    LOGS["Log store<br>outside the cluster"]
    SVC --> APP
    APP --> DB
    SIDE --> LOGS
    subgraph legend [Legend]
        direction LR
        k1["Inside the cluster"]:::inside
        k2["Managed service"]:::outside
        k1 ~~~ k2
    end
    classDef inside fill:#e3f2fd,stroke:#1565c0,color:#0d2a4a
    classDef outside fill:#eeeeee,stroke:#616161,color:#212121
    class APP,SIDE,SVC inside
    class DB,LOGS outside
```

Caption: The database and the log store sit outside the cluster; only the pod reaches them.
