# Project state

Updated: 2026-10-12

## Status

v0.3. Full Ceará Bronze and quality report completed.

## Verified

- Catalog: 25,650 CE sections for 2026/3220.
- Preflight blocks below 40 GiB only for an unbounded run; `--limit` uses a
  proportional estimate and warns when the full workload would not fit.
- Discovery completed for all 25,650 sections; 23,765 files were published and 1,885
  sections had no file available.
- All 23,765 files completed download, extraction and Bronze parsing.
- Bronze compacted result: 143,703,249 valid events in 8 Parquets
  (1,995,230,981 bytes), zero quarantine and zero critical nulls.
- Quality report: PASS WITH WARNINGS. It records 316 timestamps outside 2026
  (62 in 2009, 65 in 2028 and 189 in 2029) for explicit Silver treatment.
- Operational storage was copied and verified at `D:\tse-urna-pipeline`; the original
  `C:` copy remains intact. The `D:` volume has 392.6 GiB free.
- `TSE_DATA_DIR` and `TSE_METADATA_DIR` are supported and configured in the user
  environment to use the `D:` paths.
- Real-run regressions fixed for unpublished `aux.json` (404), gzip-encoded TSE
  downloads and transient Windows directory locks.
- Current generated data uses 18.92 GiB; 374 GiB remained free after completion.
- Local: 36 tests passing; Ruff clean.

## Ready

- Full-UF discovery with SQLite checkpoints.
- Idempotent download with rate limit, retry and atomic writes.
- ZIP/7-Zip `.jez` extraction and `logd.dat` parser.
- Batched Parquet Bronze, quarantine and compaction.
- Limits per CLI stage, tests, lockfile and CI.

## Missing

- Silver, publication and dashboard.

## Next

1. Define the Silver schema and timestamp policy, including the 316 out-of-year events.
2. Recheck the 1,885 empty sections with bounded `--refresh-empty` before publication.
3. Build and validate Silver, then publish the dataset before any dashboard work.

Quality report: `docs/quality_report_ce_2026_3220.md`.
