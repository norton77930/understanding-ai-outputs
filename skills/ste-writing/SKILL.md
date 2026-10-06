---
name: ste-writing
description: Write or rewrite text in Simplified Technical English (STE) style. Use ONLY when the user explicitly asks for STE, Simplified Technical English, ASD-STE100, or "80% STE" writing, such as "explain X in STE" or "rewrite this in STE". Never use for ordinary answers.
---

# STE writing (relaxed)

Write in a controlled, easy-to-read style so the reader spends effort on the ideas, not on the sentences. This skill is inspired by ASD-STE100. It is not official and is not endorsed by ASD.

This version uses relaxed strictness only: the core rules below, in natural wording. Do not add labels or notes about the style.

## Two uses

- **Explain** (main use): the user names a topic. Explain it with the rules below.
- **Rewrite**: the user gives text. Rewrite it with the rules below and keep every fact. Do not add or remove meaning.

Keep the style for later prose answers until the user says to stop. Answer code-only follow-ups normally.

## Core rules

1. Procedural sentences: 20 words or fewer. Descriptive sentences: 25 words or fewer.
2. Use active voice in instructions. Write "Restart the server", not "The server should be restarted".
3. Give one instruction per sentence.
4. Use one term for one concept. Do not switch between "folder" and "directory" for the same thing.
5. Give each paragraph one topic. Use 6 sentences or fewer.
6. Write procedures as numbered lists, one step per item.
7. Mark hazards with WARNING (risk of injury) or CAUTION (risk of damage). Put the command first, then the risk.

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

## Before you answer

Check the draft against the core rules. Split long sentences, switch passive instructions to active, and fix mixed terms. Then answer.
