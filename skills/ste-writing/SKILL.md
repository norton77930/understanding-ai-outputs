---
name: ste-writing
description: Write or rewrite text in Simplified Technical English (STE) style. Use ONLY when the user explicitly asks for STE, Simplified Technical English, ASD-STE100, or "80% STE" writing, such as "explain X in STE" or "rewrite this in STE". Never use for ordinary answers.
---

# STE writing

Write in a controlled, easy-to-read style so the reader spends effort on the ideas, not on the sentences. This skill is inspired by ASD-STE100. It is not official and is not endorsed by ASD.

There are two strictness levels. **Relaxed** is the default: the core rules below, in natural wording. A request for "80% STE" or "soft STE" means relaxed. English relaxed output carries no label or note about the style. **Strict** is only for a user who asks for "strict STE" or "full STE". It adds the rules in "Strict strictness" below. Full rules with before/after examples are in `references/rules.md`. Read it when a case is unclear.

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
9. Keep articles ("the", "a", "an"). Do not drop them to save words. Write "Open the file", not "Open file".

Example of rule 3:

- Before: "Open the file, change the port, and save it."
- After: "1. Open the file. 2. Change the port. 3. Save the file."

Example of rule 7:

- CAUTION: Do not delete the `data/` folder. The app loses all saved records.

## Strict strictness

Use strict only when the user asks for "strict STE" or "full STE". Apply every core rule above, and also:

- Use no progressive form ("is running") and no perfect form ("has finished"). Use the simple form.
- Use no passive voice in procedures. Descriptions should stay active too.
- Keep noun clusters to 3 words or fewer. Write "the timeout of the connection pool", not "the connection pool timeout setting value".
- Use no word or phrase from `references/replacements.md`. Use the plain choice in its second column. The list covers inflections ("utilize" also bans "utilizes" and "utilized").

End strict English output with ONE short note line: "Written in strict STE (not official ASD-STE100)." Put nothing else about the style in the answer. Relaxed output has no note.

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

Do not translate English rules word for word. The strict-only rules and the replacement list do not apply. End the answer with one short note line, in the answer language, that says only STE principles were applied. See `references/rules.md` for an example.

## Before you answer (self-check)

Measure the draft, then fix it. The checker in `scripts/ste_check.py` is the source of truth for the length limits and the counts.

1. If Python is available and the draft is English, run the checker from this skill's `scripts/` folder. Send the draft on stdin: `python <skill folder>/scripts/ste_check.py --strictness relaxed --lang auto`. Use `python3` if `python` is missing. For strict, use `--strictness strict --replacements <skill folder>/references/replacements.md`.
2. Read the JSON. Fix each sentence with `over_limit` true or a `passive` or `progressive` count above 0. For strict, also fix each `perfect` count, each entry in `noun_clusters`, each entry in `replacement_hits`, and each passive in a procedure.
3. Run the checker one more time. Fix what it still flags, then answer. Do not loop further.
4. If Python is not available, the checker fails to run (permission denied, error), or the draft is not English, use this checklist on the draft. Fall back silently. Do not tell the user the checker failed:
   - Is every sentence within its limit (20 procedural, 25 descriptive)?
   - Does every instruction use active voice?
   - Does every sentence hold one instruction?
   - Does each concept use one term?
   - English only: are the articles ("the", "a", "an") kept?
   - Does each paragraph hold one topic, in 6 sentences or fewer?
   - Are procedures numbered, and are hazards marked WARNING or CAUTION?
   - Is exempt content unchanged?
   - Strict only: no progressive or perfect forms, no passive in procedures, no noun cluster over 3 words, no word from `references/replacements.md`, and one note line at the end?

Never mention the checker or the self-check in the answer. Show no check results, and report no failure to run the checker. The checker ignores exempt content.
