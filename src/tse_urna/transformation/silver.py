from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import polars as pl

SILVER_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class CoverageResult:
    output_file: str
    fingerprint: str
    rows: int
    published_sections: int
    unpublished_sections: int
    reused: bool


@dataclass(frozen=True, slots=True)
class SilverBuildResult:
    output_files: tuple[str, ...]
    processed_batches: int
    reused_batches: int
    remaining_batches: int
    event_rows: int | None
    temporal_outlier_rows: int | None
    distinct_sections: int | None


def _section_id() -> pl.Expr:
    return pl.concat_str(
        [
            pl.col("uf").str.to_uppercase(),
            pl.col("municipality"),
            pl.col("zone"),
            pl.col("section"),
        ],
        separator="-",
    )


def silver_events(frame: pl.LazyFrame, *, election_year: int) -> pl.LazyFrame:
    """Conforma eventos Bronze sem adivinhar timestamps inválidos."""
    recorded = pl.col("event_timestamp")
    timestamp_is_valid = recorded.dt.year() == pl.lit(int(election_year))
    validated = (
        pl.when(timestamp_is_valid)
        .then(recorded)
        .otherwise(pl.lit(None, dtype=pl.Datetime("us")))
    )
    source_log_member = pl.col("source_log").str.replace(
        r"^.*[\\/]f=\d{8}[\\/]", ""
    )
    return frame.select(
        pl.concat_str(
            [
                pl.col("source_hash"),
                pl.col("source_file"),
                source_log_member,
                pl.col("line_number").cast(pl.String),
            ],
            separator=":",
        ).alias("event_id"),
        _section_id().alias("section_id"),
        pl.col("election_year").cast(pl.Int32),
        pl.col("pleito"),
        pl.col("uf").str.to_uppercase(),
        pl.col("municipality"),
        pl.col("zone"),
        pl.col("section"),
        pl.col("source_hash"),
        pl.col("source_file"),
        source_log_member.alias("source_log_member"),
        pl.col("line_number"),
        recorded.alias("event_timestamp_recorded"),
        recorded.dt.year().cast(pl.Int32).alias("event_year_recorded"),
        pl.when(timestamp_is_valid)
        .then(pl.lit("valid"))
        .otherwise(pl.lit("outside_election_year"))
        .alias("timestamp_status"),
        validated.alias("event_timestamp_validated"),
        validated.dt.date().alias("event_date_validated"),
        pl.col("severity").str.strip_chars().str.to_uppercase(),
        pl.col("ue_id"),
        pl.col("application").str.strip_chars().str.to_uppercase(),
        pl.col("message_raw").alias("message"),
        pl.col("mac"),
    )


def _source_fingerprint(path: Path) -> dict[str, str | int]:
    stat = path.stat()
    return {"name": path.name, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{uuid4().hex}")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _coverage_status(discovery_status: str, files_found: int) -> str:
    if discovery_status == "discovered":
        return "published" if files_found > 0 else "not_published"
    if discovery_status == "failed":
        return "discovery_failed"
    return "discovery_pending"


def build_section_coverage(
    *, rows: Iterable[Mapping[str, Any]], output_dir: Path
) -> CoverageResult:
    records: list[dict[str, Any]] = []
    for row in rows:
        files_found = int(row["files_found"] or 0)
        discovery_status = str(row["discovery_status"])
        records.append(
            {
                "election_year": int(row["election_year"]),
                "pleito": str(row["pleito"]),
                "uf": str(row["uf"]).upper(),
                "municipality": str(row["municipality"]),
                "zone": str(row["zone"]),
                "section": str(row["section"]),
                "discovery_status": discovery_status,
                "publication_status": _coverage_status(
                    discovery_status, files_found
                ),
                "files_found": files_found,
                "has_published_file": files_found > 0,
                "last_checked_at": row["discovered_at"],
            }
        )
    if not records:
        raise ValueError("a cobertura Silver precisa de ao menos uma seção")
    records.sort(
        key=lambda item: (item["municipality"], item["zone"], item["section"])
    )
    fingerprint = hashlib.sha256(
        json.dumps(records, sort_keys=True, default=str).encode()
    ).hexdigest()
    output_file = output_dir / "part-00000.parquet"
    success_marker = output_dir / "_SUCCESS.json"
    previous = _read_json(success_marker)
    if (
        previous
        and previous.get("schema_version") == SILVER_SCHEMA_VERSION
        and previous.get("fingerprint") == fingerprint
        and output_file.exists()
    ):
        return CoverageResult(
            output_file=str(output_file),
            fingerprint=fingerprint,
            rows=int(previous["rows"]),
            published_sections=int(previous["published_sections"]),
            unpublished_sections=int(previous["unpublished_sections"]),
            reused=True,
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    temporary = output_dir / f".part-00000.tmp-{uuid4().hex}.parquet"
    try:
        frame = (
            pl.DataFrame(records)
            .with_columns(
                _section_id().alias("section_id"),
                pl.col("election_year").cast(pl.Int32),
                pl.col("files_found").cast(pl.Int32),
                pl.col("last_checked_at")
                .cast(pl.String)
                .str.to_datetime(strict=False),
            )
            .select(
                "section_id",
                "election_year",
                "pleito",
                "uf",
                "municipality",
                "zone",
                "section",
                "discovery_status",
                "publication_status",
                "files_found",
                "has_published_file",
                "last_checked_at",
            )
        )
        frame.write_parquet(temporary, compression="zstd", statistics=True)
        temporary.replace(output_file)
    finally:
        temporary.unlink(missing_ok=True)

    published = sum(record["publication_status"] == "published" for record in records)
    unpublished = sum(
        record["publication_status"] == "not_published" for record in records
    )
    payload = {
        "schema_version": SILVER_SCHEMA_VERSION,
        "fingerprint": fingerprint,
        "output": output_file.name,
        "rows": len(records),
        "published_sections": published,
        "unpublished_sections": unpublished,
    }
    _write_json_atomic(success_marker, payload)
    return CoverageResult(
        output_file=str(output_file),
        fingerprint=fingerprint,
        rows=len(records),
        published_sections=published,
        unpublished_sections=unpublished,
        reused=False,
    )


def build_silver_events(
    *,
    input_dir: Path,
    output_dir: Path,
    election_year: int,
    coverage_fingerprint: str,
    expected_published_sections: int,
    limit: int | None = None,
) -> SilverBuildResult:
    if limit is not None and limit <= 0:
        raise ValueError("limit deve ser maior que zero")
    sources = sorted(input_dir.glob("part-*.parquet"))
    if not sources:
        raise FileNotFoundError(f"Nenhum Parquet Bronze encontrado em {input_dir}")
    fingerprints = [_source_fingerprint(path) for path in sources]
    output_dir.mkdir(parents=True, exist_ok=True)
    success_marker = output_dir / "_SUCCESS.json"
    previous_success = _read_json(success_marker)
    expected_outputs = [output_dir / path.name for path in sources]
    if (
        previous_success
        and previous_success.get("schema_version") == SILVER_SCHEMA_VERSION
        and previous_success.get("sources") == fingerprints
        and previous_success.get("coverage_fingerprint") == coverage_fingerprint
        and all(path.exists() for path in expected_outputs)
    ):
        return SilverBuildResult(
            output_files=tuple(str(path) for path in expected_outputs),
            processed_batches=0,
            reused_batches=len(sources),
            remaining_batches=0,
            event_rows=int(previous_success["event_rows"]),
            temporal_outlier_rows=int(previous_success["temporal_outlier_rows"]),
            distinct_sections=int(previous_success["distinct_sections"]),
        )

    success_marker.unlink(missing_ok=True)
    processed = 0
    reused = 0
    pending = 0
    for source, fingerprint in zip(sources, fingerprints, strict=True):
        output = output_dir / source.name
        checkpoint = output_dir / "_checkpoints" / f"{source.stem}.json"
        previous = _read_json(checkpoint)
        if (
            previous
            and previous.get("schema_version") == SILVER_SCHEMA_VERSION
            and previous.get("source") == fingerprint
            and output.exists()
        ):
            reused += 1
            continue
        if limit is not None and processed >= limit:
            pending += 1
            continue

        temporary = output_dir / f".{source.stem}.tmp-{uuid4().hex}.parquet"
        try:
            silver_events(
                pl.scan_parquet(source), election_year=election_year
            ).sink_parquet(temporary, compression="zstd", statistics=True, mkdir=True)
            temporary.replace(output)
        finally:
            temporary.unlink(missing_ok=True)
        _write_json_atomic(
            checkpoint,
            {
                "schema_version": SILVER_SCHEMA_VERSION,
                "source": fingerprint,
                "output": output.name,
                "bytes": output.stat().st_size,
            },
        )
        processed += 1

    if pending:
        return SilverBuildResult(
            output_files=tuple(
                str(path) for path in expected_outputs if path.exists()
            ),
            processed_batches=processed,
            reused_batches=reused,
            remaining_batches=pending,
            event_rows=None,
            temporal_outlier_rows=None,
            distinct_sections=None,
        )

    metrics = (
        pl.scan_parquet(expected_outputs)
        .select(
            pl.len().alias("event_rows"),
            (pl.col("timestamp_status") == "outside_election_year")
            .sum()
            .alias("temporal_outlier_rows"),
            pl.col("event_timestamp_recorded")
            .null_count()
            .alias("recorded_timestamp_nulls"),
            pl.col("event_timestamp_validated")
            .null_count()
            .alias("validated_timestamp_nulls"),
            pl.col("section_id").n_unique().alias("distinct_sections"),
        )
        .collect(engine="streaming")
        .row(named=True)
    )
    source_rows = int(
        pl.scan_parquet(sources)
        .select(pl.len().alias("rows"))
        .collect(engine="streaming")
        .item()
    )
    event_rows = int(metrics["event_rows"])
    temporal_outlier_rows = int(metrics["temporal_outlier_rows"])
    distinct_sections = int(metrics["distinct_sections"])
    if event_rows != source_rows:
        raise ValueError(
            f"Silver perdeu linhas: Bronze={source_rows}, Silver={event_rows}"
        )
    if int(metrics["recorded_timestamp_nulls"]) != 0:
        raise ValueError("Silver contém timestamp registrado nulo")
    if int(metrics["validated_timestamp_nulls"]) != temporal_outlier_rows:
        raise ValueError("política temporal Silver inconsistente")
    if distinct_sections != int(expected_published_sections):
        raise ValueError(
            "cobertura Silver inconsistente: "
            f"esperadas={expected_published_sections}, eventos={distinct_sections}"
        )
    payload = {
        "schema_version": SILVER_SCHEMA_VERSION,
        "sources": fingerprints,
        "coverage_fingerprint": coverage_fingerprint,
        "outputs": [path.name for path in expected_outputs],
        "event_rows": event_rows,
        "temporal_outlier_rows": temporal_outlier_rows,
        "distinct_sections": distinct_sections,
    }
    _write_json_atomic(success_marker, payload)
    return SilverBuildResult(
        output_files=tuple(str(path) for path in expected_outputs),
        processed_batches=processed,
        reused_batches=reused,
        remaining_batches=0,
        event_rows=event_rows,
        temporal_outlier_rows=temporal_outlier_rows,
        distinct_sections=distinct_sections,
    )
