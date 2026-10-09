# Runbook

## Setup

```powershell
uv sync --locked --extra dev
uv run ruff check .
uv run pytest -q
uv run urna-etl init
uv run urna-etl status
```

## Catalog

```powershell
uv run urna-etl discover-uf --year 2026 --pleito 3220 --uf CE --catalog-only
uv run urna-etl status
```

Expected baseline: 25,650 sections.

## Bounded processing

Run one stage at a time. Check status after each command. Repeat until its pending/failed count is zero.

```powershell
uv run urna-etl discover-uf --year 2026 --pleito 3220 --uf CE --limit 1000
uv run urna-etl ingest --limit 500
uv run urna-etl extract --limit 500
uv run urna-etl bronze --limit 500 --batch-files 100 --target-rows 250000
uv run urna-etl compact-bronze --year 2026 --pleito 3220 --uf CE
uv run urna-etl status
```

Refresh sections that previously had no logs:

```powershell
uv run urna-etl discover-uf --year 2026 --pleito 3220 --uf CE --refresh-empty --limit 1000
```

## Failure

1. Run `uv run urna-etl status`.
2. Inspect errors in `metadata/manifest.db`.
3. Add a small regression fixture and test.
4. Run Ruff and pytest.
5. Retry the failed bounded stage.

Completed checkpoints are reused. Extraction and Bronze require success markers; incomplete output is rebuilt.

Keep at least 30–40 GB free before full processing. Never commit `metadata/manifest.db*` or anything under `data/`.
