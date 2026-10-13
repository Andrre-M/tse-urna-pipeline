# Project rules

## Scope

- Target: all Ceará sections, election 2026, pleito 3220.
- Small batches are validation only.
- No dashboard before the Ceará dataset and quality report are complete.
- Never run the full Ceará workload without explicit approval.
- Never commit downloaded/generated data or SQLite state.

## Context

- At the start of every session, read this file and `PROJECT_STATE.md` before
  taking action.
- Current status, verified baseline and next task: `PROJECT_STATE.md`.
- Commands and recovery: `docs/runbook.md`.
- Dataset publication: `docs/publication.md`.
- Architecture changes: read/update `docs/decisions.md` and `docs/architecture.md`.
- Bronze or Silver schema changes: update `docs/data_dictionary.md`.
- Do not infer progress from chat history. Verify the repository, local outputs
  and remote destination named in `PROJECT_STATE.md`.

## Work

- Use `uv`; keep `uv.lock` committed.
- For code changes run `uv run ruff check .` and `uv run pytest -q`.
- Add regression tests for real bugs.
- Keep commits small.
- Update `PROJECT_STATE.md` after material progress.
- Record new architectural or publication choices in `docs/decisions.md`.
- Never put credentials, tokens or account identifiers in the repository.
- Report only verified results.
