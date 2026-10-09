# Project rules

## Scope

- Target: all Ceará sections, election 2026, pleito 3220.
- Small batches are validation only.
- No dashboard before the Ceará dataset and quality report are complete.
- Never run the full Ceará workload without explicit approval.
- Never commit downloaded/generated data or SQLite state.

## Context

- Current status and next task: `PROJECT_STATE.md`.
- Commands and recovery: `docs/runbook.md`.
- Architecture changes: read/update `docs/decisions.md` and `docs/architecture.md`.
- Bronze schema changes: update `docs/data_dictionary.md`.

## Work

- Use `uv`; keep `uv.lock` committed.
- For code changes run `uv run ruff check .` and `uv run pytest -q`.
- Add regression tests for real bugs.
- Keep commits small.
- Update `PROJECT_STATE.md` after material progress.
- Report only verified results.
