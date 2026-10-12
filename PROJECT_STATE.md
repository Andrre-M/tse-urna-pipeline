# Project state

Updated: 2026-10-12

## Status

v0.3. Bounded processing validated beyond the pilot. Full Ceará run not started.

## Verified

- Catalog: 25,650 CE sections for 2026/3220.
- Preflight blocks below 40 GiB only for an unbounded run; `--limit` uses a
  proportional estimate and warns when the full workload would not fit.
- Bounded discovery checkpoint: 1,934 sections completed, 1,816 logs found and
  23,716 sections pending.
- Bounded file checkpoint: 720 files completed through Bronze; 1,096 discovered
  files remain before Bronze (426 downloaded and 670 pending download).
- Bounded result: 4,185,149 valid events, zero quarantined lines and one compacted
  Parquet (58,097,587 bytes).
- Operational storage was copied and verified at `D:\tse-urna-pipeline`; the original
  `C:` copy remains intact. The `D:` volume has 392.6 GiB free.
- `TSE_DATA_DIR` and `TSE_METADATA_DIR` are supported and configured in the user
  environment to use the `D:` paths.
- Real-run regressions fixed for unpublished `aux.json` (404), gzip-encoded TSE
  downloads and transient Windows directory locks.
- Local: 34 tests passing; Ruff clean.

## Ready

- Full-UF discovery with SQLite checkpoints.
- Idempotent download with rate limit, retry and atomic writes.
- ZIP/7-Zip `.jez` extraction and `logd.dat` parser.
- Batched Parquet Bronze, quarantine and compaction.
- Limits per CLI stage, tests, lockfile and CI.

## Missing

- Full Ceará processing and operational metrics.
- Ceará quality report.
- Silver, publication and dashboard.

## Next

1. Continue Ceará in bounded batches using `docs/runbook.md` and record operational
   metrics after each batch.
2. Keep the unbounded run blocked until 40 GiB is available and the user explicitly
   authorizes it.
3. Produce the Ceará quality report after the full dataset, before Silver.

Do not start an unbounded run.
