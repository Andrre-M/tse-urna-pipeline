# Project state

Updated: 2026-10-12

## Status

v0.4 in progress. Silver architecture and restartable implementation completed;
full Ceará Silver generation awaits explicit workload approval.

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
- A real bounded Silver batch completed with 19,157,920 events. Its versioned
  checkpoint is reusable; seven compacted Bronze parts remain pending.
- Silver coverage completed with 25,650 rows: 23,765 `published` and 1,885
  `not_published`.
- The bounded Silver output uses 0.33 GiB; the `D:` volume currently has 357.3 GiB free.
- Local: 39 tests passing; Ruff clean.

## Ready

- Full-UF discovery with SQLite checkpoints.
- Idempotent download with rate limit, retry and atomic writes.
- ZIP/7-Zip `.jez` extraction and `logd.dat` parser.
- Batched Parquet Bronze, quarantine and compaction.
- Batched, atomic and restartable Silver events plus full section coverage.
- Limits per CLI stage, tests, lockfile and CI.

## Missing

- Full Ceará Silver generation, publication and dashboard.

## Next

1. Obtain explicit approval and complete the seven pending Ceará Silver batches.
2. Verify the completed Silver invariants: 143,703,249 events, 23,765 event
   sections, 25,650 coverage rows, 1,885 unpublished sections and 316 flagged/null
   validated timestamps.
3. Recheck the 1,885 empty sections with bounded `--refresh-empty` before publication.
4. Publish the dataset before any dashboard work.

Quality report: `docs/quality_report_ce_2026_3220.md`.
