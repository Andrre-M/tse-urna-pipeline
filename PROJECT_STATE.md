# Project state

Updated: 2026-10-09

## Status

v0.3. Pilot passed. Full Ceará run not started.

## Verified

- Catalog: 25,650 CE sections for 2026/3220.
- Five real sections completed discovery through Bronze compaction.
- Result: 31,947 valid events; zero quarantined lines.
- Local: 26 tests passing; Ruff clean.
- GitHub Actions: Python 3.12 and 3.13 passing (run `37455881157`).

## Ready

- Full-UF discovery with SQLite checkpoints.
- Idempotent download with rate limit, retry and atomic writes.
- ZIP/7-Zip `.jez` extraction and `logd.dat` parser.
- Batched Parquet Bronze, quarantine and compaction.
- Limits per CLI stage, tests, lockfile and CI.

## Missing

- Preflight for paths and disk capacity.
- Full Ceará processing and operational metrics.
- Ceará quality report.
- Silver, publication and dashboard.

## Next

1. Implement `preflight`.
2. Process Ceará in bounded batches using `docs/runbook.md`.
3. Measure failures, throughput and disk use.
4. Produce the quality report before Silver.

Do not start an unbounded run.
