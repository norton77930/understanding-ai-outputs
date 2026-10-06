# Contributing

Thanks for helping. This repo is a small, curated set of explainer skills, one for each step of the format ladder.
The contribution policy is semi-open.

## What to open

- **A fix to an existing skill**: open a pull request. Small, focused fixes are welcome.
- **A new skill or a new format**: open an [idea issue](https://github.com/norton77930/understanding-ai-outputs/issues/new?template=idea.yml) first.
  Please do not send a pull request for a new skill before a maintainer agrees to the idea.
- **A skill that gave a bad output**: open an [observed failure issue](https://github.com/norton77930/understanding-ai-outputs/issues/new?template=failure.yml).
  Give the prompt, the skill, the agent and platform, the actual output, the expected output and the version.
  A report from a real session is easier to act on than a general suggestion.

Blank issues are disabled. Use one of the two forms.

## Project language and decisions

- Use the terms in [GLOSSARY.md](GLOSSARY.md) (for example **format ladder**, **explainer skill**, **replacement list**), and avoid the words it lists under _Avoid_.
- Respect the decisions in [docs/adr/](docs/adr/). If you disagree with one, open an issue to discuss it before you change anything it covers.
- Write all repo files in English.

## Third-party material

The source post, its image and the ASD-STE100 specification belong to other people
([ADR 0001](docs/adr/0001-third-party-reference-material-stays-local.md)).

- Keep originals only in `reference/local/`. Git ignores that folder. Never commit it or copy it into a skill.
- Commit a link, your own summary and short attributed quotes.
- Write every rule, example and word list in your own words. Do not paste the ASD-STE100 dictionary or text from the specification.
- Keep the "not official, not endorsed by ASD" note wherever a skill mentions STE.

## Skill layout

- One folder per skill under `skills/`, each with a `SKILL.md`. Extra files go in the Agent Skills standard subfolders
  `references/`, `scripts/` and `assets/` ([ADR 0002](docs/adr/0002-agent-skills-standard-layout.md)).
- Each format is its own skill. There is no router skill ([ADR 0003](docs/adr/0003-one-skill-per-format-no-router.md)).
- `.claude-plugin/plugin.json` lists skills explicitly in its `skills` array. A skill folder that is not in the list
  is not published, so list a skill only when it is finished.
- The plugin version lives only in `plugin.json`.

## Local checks

Run both before you open a pull request. CI runs the same checks.

```bash
claude plugin validate . --strict
python -m unittest discover -s tests
```

`--strict` makes warnings fail. It needs no login and no API key.

Do not add a `CLAUDE.md` file at the repo root. It makes strict validation fail. The project's instructions live in
`.claude/CLAUDE.md` instead.

## Release checklist

Releases are manual. A maintainer does the following:

1. Bump `version` in `.claude-plugin/plugin.json`.
2. Move the `[Unreleased]` entries in `CHANGELOG.md` under a new `[X.Y.Z]` heading with the date, and leave an empty `[Unreleased]` section.
3. Run the local checks above.
4. Merge to `main` and wait for CI to pass.
5. Tag the merge commit `vX.Y.Z` and push the tag.
6. Create a GitHub Release for the tag. Use the changelog entry as the release notes.
