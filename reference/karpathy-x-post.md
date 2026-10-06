# Source: Andrej Karpathy on understanding LLM outputs

- Post: https://x.com/karpathy/status/2105819303471976479 (2026-10-02)
- The post text and its attached image belong to their author and are **not** stored in this repo.
  Maintainers keep a local copy in `reference/local/` (git-ignored).

## Summary (our words)

As agents do more of the work, more of our work becomes reading and checking what they produce.
The post suggests asking the model for formats that are easier to understand, in rising order:

1. **Controlled writing.** Ask for an explanation in ASD-STE100 (Simplified Technical English), a
   controlled language from aerospace maintenance documentation. A softer variant is to ask for
   "80% of the way to ASD-STE100".
2. **Diagrams.** Ask for a diagram instead of prose.
3. **Web pages.** Ask for the output "in HTML" to get an interactive page.
4. **Explainer videos.** Ask for a bespoke explainer video, for example in the style of 3Blue1Brown,
   with generated narration (a paid TTS API or a free local alternative).

The closing point: because code is now cheap, it makes sense to ask for large, custom, throwaway
artifacts (web apps, videos) just to understand one thing.

## Short quotes

> "We'll be spending a lot more time trying to understand the outputs of language models."

> "you can ask for large, custom, discardable software artifacts (e.g. web apps, video explainers)
> that would have never made sense to create before."

## Related external reference

- ASD-STE100 Simplified Technical English: https://www.asd-ste100.org/ (owned by ASD; free to
  download, not redistributed here). Skills in this repo are inspired by it and are not official or
  endorsed by ASD.
