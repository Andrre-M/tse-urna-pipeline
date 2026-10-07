# Agent guidance

This repository is the durable source of truth for the TSE urna pipeline. Do not rely on
chat history for project state.

## Project boundaries

- The operational target is the complete state of Ceará for election year 2026, pleito 3220.
- A small section batch is for validation only; do not redefine it as the product scope.
- Do not build a dashboard yet. Finish and validate the data pipeline first.
- Do not commit downloaded election data, SQLite manifests, extracted logs, quarantine, or
  generated Parquet datasets.
- Preserve RAW files as immutable inputs. Derived layers may be rebuilt from the manifest.
- Never run the full Ceará download or transformation unless the user explicitly requests it.

## Read only what the task needs

- Read `PROJECT_STATE.md` when resuming work or choosing the next task.
- Read `docs/architecture.md` before changing stage boundaries, paths, schemas, or idempotency.
- Read `docs/runbook.md` for real TSE runs, recovery, and staged Ceará execution.
- Read `docs/decisions.md` before reversing an established architectural choice.
- Read `docs/data_dictionary.md` when changing Bronze columns or types.

## Development contract

- Use `uv` and keep `uv.lock` committed.
- Run `uv run ruff check .` and `uv run pytest -q` for code changes.
- Add a regression test for every real format or operational bug.
- Keep commits small and scoped; do not mix generated data with code changes.
- A command that records partial stage failures must exit non-zero after saving checkpoints.
- Update `PROJECT_STATE.md` after a material validation, milestone, or change to the next action.
- Record durable architectural decisions in `docs/decisions.md`; do not log routine edits there.

## Definition of done

A change is complete when implementation, affected tests, documentation, and the operational
checkpoint are consistent. Report what was actually validated and distinguish it from what is
only planned.
