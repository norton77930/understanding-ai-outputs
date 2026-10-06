# understanding-ai-outputs

Agent skills that turn LLM output into formats a human can understand faster, following the ideas in Andrej Karpathy's post.

## Language

**STE**:
Simplified Technical English as defined by the ASD-STE100 specification: a controlled English with writing rules and a restricted dictionary.
_Avoid_: Simple English, Plain English, simplified English

**Format ladder**:
The ordered set of output formats from the source post: STE writing, diagram, web page, explainer video. Each step trades more production effort for faster understanding.
_Avoid_: levels, tiers

**Explainer skill**:
One skill in this repo that produces one rung of the format ladder.
_Avoid_: mode, plugin

## STE writing

**Strictness**:
How closely STE output follows the rules. Two values: **strict** (all writing rules plus the replacement list) and **relaxed** (core rules only; the default, matching the source post's "80% of the way").
_Avoid_: level, percentage, 80% mode

**Replacement list**:
This repo's own table of wordy or ambiguous words and their plain substitutes (e.g. utilize → use). It is not the ASD-STE100 dictionary.
_Avoid_: dictionary, approved words, STE dictionary

**STE principles**:
The language-independent subset of the STE rules (short sentences, active voice, one instruction per sentence, one term per concept) applied when the output language is not English.
_Avoid_: Chinese STE, translated STE

**Self-check**:
The optional pass after writing STE where the agent measures its own output (by script when Python exists, by checklist otherwise) and fixes violations.
_Avoid_: lint, validation

**Exempt content**:
Text the skill never rewrites: code, identifiers, commands, quoted source text, proper and product names.
_Avoid_: protected text, skipped text
