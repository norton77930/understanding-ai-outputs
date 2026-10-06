# STE writing rules (relaxed)

These rules are inspired by ASD-STE100. They are written in our own words. They are not official, and ASD does not endorse them. They do not include the ASD-STE100 dictionary.

This file holds the full relaxed rule set. `SKILL.md` holds the short version.

## Measurement

The checker `scripts/ste_check.py` is the source of truth for the limits and the counts. The numbers below match its constants. The checker is a heuristic tool, not a grammar parser. It can miss a case or flag a wrong one. Use your own judgment when a flag looks wrong.

## Relaxed rules

### 1. Keep sentences short

- Procedural sentences (instructions, numbered steps): 20 words or fewer.
- Descriptive sentences: 25 words or fewer.
- Split a long sentence at its second idea.

Before: "The scheduler reads the queue, picks the job with the highest priority, and starts a worker, which then reports its status back to the scheduler."

After: "The scheduler reads the queue. It picks the job with the highest priority. Then it starts a worker. The worker reports its status to the scheduler."

### 2. Use active voice

Put the actor first. Say who does the action. This rule covers instructions and descriptions.

Before: "The cache should be cleared by the user before the build is started."

After: "Clear the cache before you start the build."

Before: "The request is rejected by the gateway."

After: "The gateway rejects the request."

### 3. Give one instruction per sentence

Each sentence tells the reader to do one thing. A reader can then track which step they are on.

Before: "Stop the service, back up the data folder, and then restart the service."

After: "1. Stop the service. 2. Back up the data folder. 3. Start the service."

### 4. Use one term for one concept

Pick one word for each thing and keep it. A second word makes the reader ask if there is a second thing.

Before: "Save the file in the folder. The directory must exist first."

After: "Save the file in the folder. The folder must exist first."

### 5. Give each paragraph one topic

- One topic per paragraph.
- 6 sentences or fewer.
- Start a new paragraph when the topic changes.

Before: one paragraph that explains what a cache is, how to clear it, and why a build can fail.

After: three short paragraphs: what a cache is, how to clear it, why a build can fail.

### 6. Write procedures as numbered lists

Use one numbered item for each step. Put the steps in the order the reader does them. Put a condition before the action.

Before: "You need to check that the port is free and, if it is not, change the port in the config and run the server."

After:

1. Check that the port is free.
2. If the port is in use, change the port in the config file.
3. Start the server.

### 7. Verb forms

Use simple verb forms where they work. The checker counts passive, progressive ("is running") and perfect ("has finished") forms. Passive and progressive forms together should stay under 5% of the sentences.

Before: "The job is running and the report has been generated."

After: "The job runs. The system generates the report."

A negation does not change this. "The file was not deleted" is still passive. Write "The script did not delete the file".

### 8. WARNING and CAUTION

Use WARNING when the risk is injury or loss of life. Use CAUTION when the risk is damage to equipment, data, or the product. Put the command first, then the risk. Put the note before the step that causes the risk.

WARNING: Disconnect the power cable before you open the case. Live parts can cause an electric shock.

CAUTION: Do not delete the `data/` folder. The app loses all saved records.

Keep the note short. Use WARNING and CAUTION only for real risk, not for general advice.

## Exempt content

Do not change exempt content. Copy it exactly, because the reader may paste it somewhere.

- code and code blocks
- identifiers (names of functions, files, variables, flags)
- commands
- error messages
- quoted source text
- proper names and product names

Apply the rules to the prose around these items. If a sentence is long only because of an exempt item, rewrite the prose and leave the item as it is.

Before: "Run `docker compose up -d` and the services will be started in the background."

After: "Run `docker compose up -d`. The services start in the background."

Quoted text keeps its original wording, even if it breaks a rule: The log says "Connection was refused by the host". Explain it in your own sentence next to it.

The checker removes fenced code blocks, inline code, and blockquote lines before it measures. It does not measure Markdown heading lines.

## Non-English output

When the answer is not in English, apply STE principles only. The English word limits, the verb-form counts, and the checker do not apply, because they depend on English grammar.

STE principles:

- short sentences
- active voice
- one instruction per sentence
- one term for one concept
- one topic per paragraph

End the answer with one short note line in the answer language. The note says that only STE principles were applied. Relaxed English output has no note.

Example in Traditional Chinese (zh-TW).

Before: 「在執行部署之前，必須先確認設定檔已經被正確修改，並且備份資料庫，然後才能啟動服務。」

After:

1. 修改設定檔。
2. 確認設定檔的內容正確。
3. 備份資料庫。
4. 啟動服務。

註：本回答只套用 STE 原則，不是完整的 STE。

Notes on the example: each step has one action in active voice. The text uses one term ("設定檔") for one thing. The last line is the note.

## Persistence

- Keep the style for every later prose answer until the user says to stop (for example "stop STE" or "back to normal").
- A code-only answer is written normally. The style stays on, and the next prose answer uses it again.
- Do not start the style for a user who did not ask for it.

## Self-check

1. Python available and English draft: run `python scripts/ste_check.py --strictness relaxed --lang auto` with the draft on stdin. Fix each flagged sentence. Run it one more time, then answer.
2. Python not available, or non-English draft: use the checklist in `SKILL.md`.
3. Do not show the check to the user.
