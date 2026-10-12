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
- Silver has separate event and section-coverage datasets so unpublished sections remain
  explicit without creating synthetic events.
- Silver preserves the timestamp recorded by the voting machine. Events outside the election
  year are flagged and receive a null validated timestamp; timestamps are never guessed.
- Each compacted Bronze part is a restartable Silver batch with an atomic output and a source
  fingerprint checkpoint. Partition success is recorded only after all batches complete.
- Empty-section refreshes have a persisted run ID in SQLite. Successful sections are marked per
  run, so bounded retries resume instead of querying the first empty sections again.
- Dashboard starts only after full Ceará processing, quality validation and a stable analytical schema.
