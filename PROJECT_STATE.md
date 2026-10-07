# Project state

Last updated: 2026-10-07

## Mission

Build a reproducible, resumable data pipeline that discovers, downloads, extracts, and converts
the public TSE electronic-voting-machine logs for the complete state of Ceará into traceable
Parquet datasets. Dashboard work is intentionally out of scope until the pipeline and dataset
quality are complete.

## Current milestone

Version line: v0.3 — real-data pilot validated; full Ceará execution not started.

Repository: `Andrre-M/tse-urna-pipeline`, branch `main`.

Latest validated commit at the time of this update: `bf91d98`.

## Verified evidence

- The official 2026/3220 Ceará catalog contained 25,650 sections on 2026-10-06.
- Five real sections completed discovery, download, extraction, Bronze, and compaction.
- The pilot produced 31,947 valid Bronze events and zero rejected lines.
- Current TSE log entries use `tp: "log"` and names ending in `-log.jez`.
- The observed 2026 `.jez` files are ZIP containers; legacy 7-Zip extraction remains supported.
- Local verification: 26 tests passing and Ruff clean.
- GitHub Actions passed on Python 3.12 and 3.13 in workflow run `37455881157`.

## Implemented capabilities

- Full-UF catalog parsing and section-level discovery checkpoints.
- SQLite manifest in WAL mode with idempotent section and file records.
- Concurrent discovery and ingestion with rate limiting, retry/backoff, and `Retry-After`.
- Atomic downloads with local SHA-256 and Windows-safe short physical paths.
- Atomic ZIP/7-Zip extraction, nested `.jez` support, and unsafe-member rejection.
- `logd.dat` parser with raw-message preservation.
- Deterministic Bronze batches, target row sizing, per-batch quarantine, and success markers.
- Streaming Bronze compaction by election/UF.
- Non-zero command exits after checkpointed partial failures.
- CI, lockfile, lint, tests, architecture, data dictionary, and operating documentation.

## Next recommended work

1. Add an explicit capacity/preflight command that estimates disk needs and confirms writable
   paths before a full run.
2. Run discovery for all pending Ceará sections in bounded batches and inspect failures.
3. Run ingestion in bounded batches while collecting throughput, retry, file-size, and disk-use
   measurements.
4. Extract and build Bronze in bounded batches; compact only after batch outputs are stable.
5. Produce a Ceará quality report before starting Silver.

Use `docs/runbook.md` for commands and stop conditions. Do not jump directly to an unbounded
full-state run merely because the pipeline supports it.

## Known limitations

- Only five real sections have completed the full pipeline so far.
- There is no capacity estimator or formal UF quality-report command yet.
- Compaction targets approximate compressed input size, not an exact output size.
- Silver, publication, and dashboard layers are not implemented.

## Handoff rule

Before ending material work, update this file only with verified facts: current milestone,
evidence, known limitations, and the next recommended action. Git history remains the detailed
record of implementation changes.
