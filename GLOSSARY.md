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

## Explainer video

**Scene**:
One segment of an explainer video: one narration passage and the animation that plays while it is spoken. The narration audio sets the scene's length.
_Avoid_: shot, clip, slide

**Narration**:
The spoken text of an explainer video, one passage per scene. It follows relaxed STE in English and the STE principles in other languages.
_Avoid_: voice-over script, transcript

**Narration engine**:
The text-to-speech system that turns narration into audio. One engine offers one or more voices.
_Avoid_: TTS backend, voice (a voice is one speaker inside an engine)

**Layout check**:
The review of still frames from a low-quality preview render, before the final render, to find overlapping, clipped or unreadable elements.
_Avoid_: QA, visual lint, self-check (that term belongs to STE writing)

**Output preset**:
A named set of video output settings (aspect ratio, resolution, target length). Three values: **explainer** (the default), **youtube**, **short**.
_Avoid_: format (reserved for the format ladder), profile, mode
