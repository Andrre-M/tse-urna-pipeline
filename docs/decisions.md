# Decisions

- Ceará 2026/3220 is the MVP. Small batches are validation only.
- SQLite stores operational state; Parquet stores analytical data.
- RAW inputs are immutable and excluded from Git.
- Physical paths use short stable IDs for Windows; full identity stays in the manifest and Bronze.
- Data and SQLite state may live on another local volume through `TSE_DATA_DIR` and
  `TSE_METADATA_DIR`; the repository remains portable and data stays unversioned.
- Discovery accepts official `tp: "log"`, `.logjez` and `-log.jez` names.
- Extraction supports ZIP and 7-Zip containers with safe member paths.
- Bronze is deterministic and batched; quarantine is per batch; compaction is separate.
- Dashboard starts only after full Ceará processing, quality validation and a stable analytical schema.
