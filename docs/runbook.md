# Operations runbook

This runbook is the operational path for local validation and staged Ceará processing. Commands
are safe to repeat because the manifest checkpoints completed work.

## 1. Prepare and verify

```powershell
uv sync --locked --extra dev
uv run ruff check .
uv run pytest -q
uv run urna-etl init
uv run urna-etl status
```

Expected code baseline: Ruff clean and 26 tests passing. A higher test count is fine; a lower
count requires investigation.

## 2. Catalog Ceará without downloading urn files

```powershell
uv run urna-etl discover-uf --year 2026 --pleito 3220 --uf CE --catalog-only
uv run urna-etl status
```

The catalog validation on 2026-10-06 returned 25,650 sections. A later total may legitimately
change if the TSE republishes the catalog; investigate large differences before continuing.

## 3. Pilot a bounded end-to-end batch

```powershell
uv run urna-etl discover-uf --year 2026 --pleito 3220 --uf CE --limit 100
uv run urna-etl ingest --limit 100
uv run urna-etl extract --limit 100
uv run urna-etl bronze --limit 100 --batch-files 100 --target-rows 250000
uv run urna-etl compact-bronze --year 2026 --pleito 3220 --uf CE
uv run urna-etl status
```

Stop and inspect the manifest if any command exits non-zero. Do not hide failures by chaining a
later stage before understanding the failed records.

## 4. Process Ceará in bounded runs

Repeat each stage with explicit limits. Finish and inspect one stage before moving to the next.

```powershell
uv run urna-etl discover-uf --year 2026 --pleito 3220 --uf CE --limit 1000
uv run urna-etl status

uv run urna-etl ingest --limit 500
uv run urna-etl status

uv run urna-etl extract --limit 500
uv run urna-etl status

uv run urna-etl bronze --limit 500 --batch-files 100 --target-rows 250000
uv run urna-etl status
```

The limits control work selected for one invocation, not the total project scope. Rerun the same
command until the relevant pending/failed count reaches zero.

After Bronze batches are stable:

```powershell
uv run urna-etl compact-bronze --year 2026 --pleito 3220 --uf CE
```

## 5. Refresh sections that previously had no logs

During gradual publication, a valid `aux.json` may initially contain no log. Recheck only those
completed-empty sections with:

```powershell
uv run urna-etl discover-uf --year 2026 --pleito 3220 --uf CE --refresh-empty --limit 1000
```

## Recovery behavior

- Discovery reruns `pending` and `failed` sections; `--refresh-empty` additionally selects
  completed sections with zero files.
- Ingestion reuses a non-empty file moved into its final RAW location before interruption.
- Extraction trusts only destinations containing `_SUCCESS` and reconstructs incomplete output.
- Bronze batch IDs derive from source manifest IDs and hashes. An incomplete batch is rebuilt;
  a completed `_SUCCESS.json` is reused.
- Compaction fingerprints its source files and rebuilds only when that input set changes.

## Failure triage

1. Run `uv run urna-etl status` and identify the failed stage.
2. Inspect the `error` and HTTP status columns in `metadata/manifest.db`.
3. Preserve the failing public source as a local, ignored fixture when reproduction requires it.
4. Add the smallest synthetic regression fixture that represents the format difference.
5. Fix, run Ruff and pytest, then retry the bounded stage.

## Data that must remain uncommitted

- `metadata/manifest.db*`
- cached discovery responses
- `data/raw`, `data/x`, and legacy `data/extracted`
- `data/bronze`, `data/bronze_compacted`, `data/quarantine`, `data/silver`, and `data/gold`

Only small synthetic test fixtures belong in Git.
