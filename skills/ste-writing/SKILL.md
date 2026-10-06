---
name: ste-writing
description: Write or rewrite text in Simplified Technical English (STE) style. Use ONLY when the user explicitly asks for STE, Simplified Technical English, ASD-STE100, or "80% STE" writing, such as "explain X in STE" or "rewrite this in STE". Never use for ordinary answers.
---

# STE writing (relaxed)

Write in a controlled, easy-to-read style so the reader spends effort on the ideas, not on the sentences. This skill is inspired by ASD-STE100. It is not official and is not endorsed by ASD.

This version uses relaxed strictness: the core rules below, in natural wording. English output carries no label or note about the style. Full rules with before/after examples are in `references/rules.md`. Read it when a case is unclear.

## Two uses

- **Explain** (main use): the user names a topic. Explain it with the rules below.
- **Rewrite**: the user gives text. Rewrite it with the rules below. Keep every fact. Do not add or remove meaning.

## Core rules

1. Procedural sentences: 20 words or fewer. Descriptive sentences: 25 words or fewer.
2. Use active voice in instructions and in descriptions. Write "Restart the server", not "The server should be restarted".
3. Give one instruction per sentence.
4. Use one term for one concept. Do not switch between "folder" and "directory".
5. Give each paragraph one topic. Use 6 sentences or fewer.
6. Write procedures as numbered lists, one step per item.
7. Mark hazards with WARNING (risk of injury) or CAUTION (risk of damage). Put the command first, then the risk.
8. Keep verb forms simple. Write "The server runs", not "The server is running". The checker counts both forms.

Example of rule 3:

- Before: "Open the file, change the port, and save it."
- After: "1. Open the file. 2. Change the port. 3. Save the file."

Example of rule 7:

- CAUTION: Do not delete the `data/` folder. The app loses all saved records.

## Exempt content

Leave these unchanged, exactly as written:

- code and code blocks
- identifiers, commands, and error messages
- quoted source text
- proper names and product names

Apply the rules only to the prose around them.

## Persistence

Keep the style for every later prose answer until the user says to stop. Answer a code-only follow-up normally. The style stays on for the next prose answer after it.

## Non-English output

When the answer is not in English, apply STE principles only:

- short sentences
- active voice
- one instruction per sentence
- one term per concept
- one topic per paragraph

Do not translate English rules word for word. End the answer with one short note line, in the answer language, that says only STE principles were applied. See `references/rules.md` for an example.

## Before you answer (self-check)

Measure the draft, then fix it. The checker in `scripts/ste_check.py` is the source of truth for the length limits and the counts.

1. If Python is available and the draft is English, run the checker from this skill's `scripts/` folder. Send the draft on stdin: `python <skill folder>/scripts/ste_check.py --strictness relaxed --lang auto`. Use `python3` if `python` is missing.
2. Read the JSON. Fix each sentence with `over_limit` true or a `passive` or `progressive` count above 0.
3. Run the checker one more time. Fix what it still flags, then answer. Do not loop further.
4. If Python is not available, or the draft is not English, use this checklist on the draft:
   - Is every sentence within its limit (20 procedural, 25 descriptive)?
   - Does every instruction use active voice?
   - Does every sentence hold one instruction?
   - Does each concept use one term?
   - Does each paragraph hold one topic, in 6 sentences or fewer?
   - Are procedures numbered, and are hazards marked WARNING or CAUTION?
   - Is exempt content unchanged?

Do not show the check to the user. The checker ignores exempt content.
