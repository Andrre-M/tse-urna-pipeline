# Project state

Updated: 2026-10-12

## Status

v0.4. Full Ceará Silver completed and validated.

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
- Silver schema has separate `events` and `section_coverage` datasets. Unpublished
  sections remain explicit and never create synthetic events.
- Timestamp policy was verified against all 316 real out-of-year events: recorded
  values were preserved, all 316 were flagged and all 316 validated timestamps are
  null.
- Silver coverage completed with 25,650 rows: 23,765 `published` and 1,885
  `not_published`.
- Silver events completed with 143,703,249 rows across 23,765 sections. All 8
  compacted Bronze parts have versioned checkpoints and a partition success marker.
- The Silver temporal invariant passed: 316 out-of-year recorded timestamps, 316
  null validated timestamps and no loss of recorded values.
- Silver events contain 8 Parquets totaling 2,630,037,414 bytes. The `D:` volume
  currently has 354.5 GiB free.
- Local: 39 tests passing; Ruff clean.

## Ready

- Full-UF discovery with SQLite checkpoints.
- Idempotent download with rate limit, retry and atomic writes.
- ZIP/7-Zip `.jez` extraction and `logd.dat` parser.
- Batched Parquet Bronze, quarantine and compaction.
- Batched, atomic and restartable Silver events plus full section coverage.
- Limits per CLI stage, tests, lockfile and CI.

## Missing

- Publication and dashboard.

## Next

1. Recheck the 1,885 empty sections with bounded `--refresh-empty` before publication.
2. If the refresh discovers files, process only that delta and rebuild the affected
   downstream checkpoints.
3. Publish the dataset before any dashboard work.

Quality report: `docs/quality_report_ce_2026_3220.md`.
