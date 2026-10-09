# ste-writing eval results

Newest run first. Trigger-eval results are in `triggers/RESULTS.md`.

## Explain set (`--set explain`): not run yet

The topics in `explain/` are a DRAFT for maintainer review (issue #48). Run the set after the maintainer approves them:

```
python evals/ste-writing/run_eval.py --set explain
```

Then record here: the date, model, `claude` version, seed, command and skill commit; the answers and the cost and agent time per arm from `report.md`; and the path of `review.html`. The rating procedure is in `README.md` ("Explain set").

### Maintainer ratings (blind, two axes)

Scores 1-5. 理解（Understanding）: how well the reader understands the topic's bullets after reading. 好讀（Readability）: how easy the text is to read. Fill "With-skill was" from `ab_key` in `report.json` after the ratings.

| Topic | A understanding | A readability | B understanding | B readability | Better (A/B/tie) | Notes | With-skill was (from key) |
|---|---|---|---|---|---|---|---|
| 01-idempotency | | | | | | | |
| 02-python-venv | | | | | | | |
| 03-database-index | | | | | | | |
| 04-port-in-use | | | | | | | |
