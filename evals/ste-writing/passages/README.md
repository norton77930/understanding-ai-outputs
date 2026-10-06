# Eval passages

Status: DRAFT — pending maintainer review (issue #8)

Eight passages, all written for this repo (no copied text). They are deliberately wordy: passive voice, long sentences, wordy phrases ("utilize", "prior to", "in order to") and stacked noun phrases. The harness gives each one to an agent with the request "Rewrite the following text in STE."

| File | Type | Language | Size | Exempt content |
|---|---|---|---|---|
| `01-api-doc.md` | API documentation | en | 134 words | inline code |
| `02-procedure.md` | Procedure | en | 136 words | none |
| `03-procedure-safety.md` | Procedure with a safety hazard | en | 137 words | none |
| `04-architecture.md` | Architecture description | en | 130 words | none |
| `05-error-message.md` | Error-message explanation | en | 140 words | inline code (error string) |
| `06-configuration.md` | Configuration explanation | en | 133 words | fenced code block, inline code |
| `07-zh-procedure.md` | Procedure | zh-TW | about 235 characters | none |
| `08-zh-concept.md` | Concept explanation | zh-TW | about 235 characters | none |

The Chinese passages are sized in characters, not words. They have no numeric metrics; the maintainer reviews them by hand.

Please check each passage for: realistic content, enough wordiness to give the skill room to help, and no accidental copy of third-party text.
