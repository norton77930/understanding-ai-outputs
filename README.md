# understanding-ai-outputs

Agent skills derived from Andrej Karpathy's X post on making LLM outputs easier to understand
([reference/karpathy-x-post.md](reference/karpathy-x-post.md)).

The post describes an escalating ladder of output formats:

1. **Writing** — explain in ASD-STE100 (Simplified Technical English), optionally "80% of the way".
2. **Diagrams / images** — ask for a diagram instead of prose.
3. **Web pages** — ask for output "in HTML" for an interactive page.
4. **Explainer videos** — bespoke 3b1b-style video explainers with narration.

## Layout

```
reference/   source links and our own summaries (third-party originals stay in reference/local/, git-ignored)
skills/      one directory per skill, each with a SKILL.md
```
