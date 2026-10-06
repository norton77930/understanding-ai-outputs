# Skill folders use the Agent Skills standard layout, not the upstream flat layout

This repo copies its workflow from mattpocock/skills, which puts extra files flat beside `SKILL.md` with upper-case names (e.g. `tdd/MOCKING.md`). We instead use the Agent Skills standard subfolders `references/`, `scripts/` and `assets/`, because we target several agents (Claude Code plugin plus `npx skills`) and the standard layout is what those tools and `skill-creator` expect. The `skills/` folder is flat, without upstream's bucket folders, because the repo has only four skills on one theme.
