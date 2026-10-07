# Architecture decision log

This file records durable choices and their rationale. Git history records implementation detail.

## ADR-001 — Ceará is the operational MVP

Status: accepted

The pipeline must reconstruct the complete state of Ceará. A single section or small batch is a
debugging and validation tool, not a reduced product scope. Brazil-wide execution remains
optional until Ceará is complete and measured.

## ADR-002 — SQLite is the operational manifest

Status: accepted

SQLite provides transactional, local, inspectable checkpoints without external infrastructure.
WAL mode and a busy timeout support the current concurrency. SQLite is not the analytical store;
Parquet is used for analytical layers.

## ADR-003 — RAW is immutable and rebuildable

Status: accepted

Downloaded TSE files are never modified. The manifest preserves source URL, published hash,
original filename, local SHA-256, and election coordinates. Heavy data remains unversioned and
can be reconstructed from the public source.

## ADR-004 — Physical paths may be shorter than logical identity

Status: accepted

Long TSE hashes plus partition names exceeded common Windows path limits. RAW and extracted
paths therefore use stable manifest IDs. Full logical identity remains in SQLite and Bronze
columns, preserving traceability without fragile filesystem paths.

## ADR-005 — Detect logs by official type and compatible suffixes

Status: accepted

Legacy data may use `.logjez`; observed 2026 data uses an `arq` entry with `tp: "log"` and a
`-log.jez` filename. Discovery accepts the official type and known log suffixes rather than
assuming one historical extension.

## ADR-006 — Support ZIP and 7-Zip containers

Status: accepted

Observed 2026 `.jez` files are ZIP containers, while legacy archives may be 7-Zip. Extraction
detects the container by content, validates member paths, and recursively handles nested `.jez`
files within a bounded depth.

## ADR-007 — Bronze is deterministic and batched

Status: accepted

Writing one Parquet per source creates excessive small files. Bronze groups a bounded number of
manifest records into a deterministic batch, writes row-bounded parts, and records completion
with `_SUCCESS.json`. Quarantine is batch-specific and idempotent. A separate streaming
compaction step produces fewer files without mutating RAW or Bronze batches.

## ADR-008 — Dashboard work waits for data quality

Status: accepted

The dashboard is a downstream consumer. It starts only after full Ceará processing, a quality
report, and a stable Silver/Gold contract. This prevents presentation work from hiding pipeline
and data-quality gaps.
