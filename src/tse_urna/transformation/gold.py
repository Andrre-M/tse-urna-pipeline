from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import polars as pl

from tse_urna.filesystem import promote_directory

GOLD_SCHEMA_VERSION = 1
PARTIAL_TABLES = (
    "section_events",
    "event_timeline",
    "applications",
    "temporal_outliers",
    "statistics",
)


@dataclass(frozen=True, slots=True)
class GoldBuildResult:
    output_files: tuple[str, ...]
    processed_parts: int
    reused_parts: int
    remaining_parts: int
    completed: bool
    total_events: int | None
    catalog_sections: int | None
    temporal_outlier_events: int | None


def municipality_names_from_state_config(
    payload: dict[str, Any], *, uf: str
) -> dict[str, str]:
    """Extrai a relação código/nome do mesmo catálogo usado no discovery."""
    target_uf = uf.lower()
    names: dict[str, str] = {}
    for block in payload.get("abr", []):
        if not isinstance(block, dict):
            continue
        block_uf = str(block.get("cd", "")).lower()
        if block_uf and block_uf != target_uf:
            continue
        for municipality in block.get("mu", []):
            if not isinstance(municipality, dict):
                continue
            raw_code = str(municipality.get("cd", "")).strip()
            code = raw_code.zfill(5)
            name = str(municipality.get("nm", "")).strip()
            if not raw_code or not name:
                continue
            previous = names.get(code)
            if previous is not None and previous != name:
                raise ValueError(f"nomes conflitantes para o município {code}")
            names[code] = name
    if not names:
        raise ValueError(f"catálogo não contém municípios para {uf.upper()}")
    return names


def load_municipality_names(path: Path, *, uf: str) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"Catálogo estadual não encontrado em {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return municipality_names_from_state_config(payload, uf=uf)


def _source_fingerprint(path: Path) -> dict[str, str | int]:
    stat = path.stat()
    return {"name": path.name, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{uuid4().hex}")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _partial_frames(events: pl.LazyFrame) -> dict[str, pl.LazyFrame]:
    base = ["election_year", "pleito", "uf", "municipality", "zone"]
    valid = events.filter(
        (pl.col("timestamp_status") == "valid")
        & pl.col("event_timestamp_validated").is_not_null()
    )
    outliers = events.filter(pl.col("timestamp_status") == "outside_election_year")
    return {
        "section_events": events.group_by("section_id").agg(
            pl.len().cast(pl.Int64).alias("event_count")
        ),
        "event_timeline": (
            valid.with_columns(
                pl.col("event_date_validated").alias("event_date"),
                pl.col("event_timestamp_validated").dt.hour().alias("event_hour"),
            )
            .group_by(*base, "event_date", "event_hour", "severity")
            .agg(pl.len().cast(pl.Int64).alias("event_count"))
        ),
        "applications": events.group_by(*base, "application", "severity").agg(
            pl.len().cast(pl.Int64).alias("event_count")
        ),
        "temporal_outliers": outliers.group_by(
            *base,
            "section",
            "section_id",
            "event_year_recorded",
            "application",
            "severity",
        ).agg(
            pl.len().cast(pl.Int64).alias("event_count"),
            pl.col("event_timestamp_recorded")
            .min()
            .alias("first_recorded_event_at"),
            pl.col("event_timestamp_recorded")
            .max()
            .alias("last_recorded_event_at"),
        ),
        "statistics": events.select(
            pl.len().cast(pl.Int64).alias("total_events"),
            (pl.col("timestamp_status") == "valid")
            .sum()
            .cast(pl.Int64)
            .alias("valid_timestamp_events"),
            (pl.col("timestamp_status") == "outside_election_year")
            .sum()
            .cast(pl.Int64)
            .alias("temporal_outlier_events"),
            pl.col("event_timestamp_validated").min().alias("first_valid_event_at"),
            pl.col("event_timestamp_validated").max().alias("last_valid_event_at"),
        ),
    }


def _write_partials(source: Path, *, work_dir: Path) -> None:
    frames = _partial_frames(pl.scan_parquet(source))
    temporary_files: list[tuple[Path, Path]] = []
    try:
        for table, frame in frames.items():
            destination = work_dir / "partials" / table / source.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(
                f".{destination.stem}.tmp-{uuid4().hex}.parquet"
            )
            frame.sink_parquet(
                temporary, compression="zstd", statistics=True, mkdir=True
            )
            temporary_files.append((temporary, destination))
        for temporary, destination in temporary_files:
            temporary.replace(destination)
    finally:
        for temporary, _ in temporary_files:
            temporary.unlink(missing_ok=True)


def _partial_paths(work_dir: Path, table: str, sources: list[Path]) -> list[Path]:
    return [work_dir / "partials" / table / source.name for source in sources]


def _municipality_frame(names: dict[str, str]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "municipality": list(names),
            "municipality_name": list(names.values()),
        },
        schema={"municipality": pl.String, "municipality_name": pl.String},
    )


def _enrich_municipalities(
    frame: pl.LazyFrame, municipality_names: pl.DataFrame
) -> pl.LazyFrame:
    return frame.join(municipality_names.lazy(), on="municipality", how="left")


def _sum_column(frame: pl.DataFrame, column: str) -> int:
    value = frame[column].sum()
    return int(value or 0)


def _final_frames(
    *,
    sources: list[Path],
    work_dir: Path,
    coverage_file: Path,
    municipality_names: dict[str, str],
) -> dict[str, pl.DataFrame]:
    names = _municipality_frame(municipality_names)
    section_events = (
        pl.scan_parquet(_partial_paths(work_dir, "section_events", sources))
        .group_by("section_id")
        .agg(pl.col("event_count").sum())
    )
    coverage = (
        pl.scan_parquet(coverage_file)
        .select(
            "section_id",
            "election_year",
            "pleito",
            "uf",
            "municipality",
            "zone",
            "section",
            "publication_status",
            "has_published_file",
        )
        .join(section_events, on="section_id", how="left")
        .with_columns(
            pl.col("event_count").fill_null(0).cast(pl.Int64),
            pl.col("event_count").fill_null(0).gt(0).alias("has_events"),
        )
    )
    coverage = _enrich_municipalities(coverage, names).select(
        "section_id",
        "election_year",
        "pleito",
        "uf",
        "municipality",
        "municipality_name",
        "zone",
        "section",
        "publication_status",
        "has_published_file",
        "event_count",
        "has_events",
    )

    timeline_keys = [
        "election_year",
        "pleito",
        "uf",
        "municipality",
        "zone",
        "event_date",
        "event_hour",
        "severity",
    ]
    timeline = _enrich_municipalities(
        pl.scan_parquet(_partial_paths(work_dir, "event_timeline", sources))
        .group_by(*timeline_keys)
        .agg(pl.col("event_count").sum()),
        names,
    ).select(
        "election_year",
        "pleito",
        "uf",
        "municipality",
        "municipality_name",
        "zone",
        "event_date",
        "event_hour",
        "severity",
        "event_count",
    )

    application_keys = [
        "election_year",
        "pleito",
        "uf",
        "municipality",
        "zone",
        "application",
        "severity",
    ]
    applications = _enrich_municipalities(
        pl.scan_parquet(_partial_paths(work_dir, "applications", sources))
        .group_by(*application_keys)
        .agg(pl.col("event_count").sum()),
        names,
    ).select(
        "election_year",
        "pleito",
        "uf",
        "municipality",
        "municipality_name",
        "zone",
        "application",
        "severity",
        "event_count",
    )

    outlier_keys = [
        "election_year",
        "pleito",
        "uf",
        "municipality",
        "zone",
        "section",
        "section_id",
        "event_year_recorded",
        "application",
        "severity",
    ]
    outliers = _enrich_municipalities(
        pl.scan_parquet(_partial_paths(work_dir, "temporal_outliers", sources))
        .group_by(*outlier_keys)
        .agg(
            pl.col("event_count").sum(),
            pl.col("first_recorded_event_at").min(),
            pl.col("last_recorded_event_at").max(),
        ),
        names,
    ).select(
        "election_year",
        "pleito",
        "uf",
        "municipality",
        "municipality_name",
        "zone",
        "section",
        "section_id",
        "event_year_recorded",
        "application",
        "severity",
        "event_count",
        "first_recorded_event_at",
        "last_recorded_event_at",
    )

    collected = {
        "coverage": coverage.sort("municipality", "zone", "section").collect(
            engine="streaming"
        ),
        "event_timeline": timeline.sort(*timeline_keys).collect(engine="streaming"),
        "applications": applications.sort(*application_keys).collect(engine="streaming"),
        "temporal_outliers": outliers.sort(*outlier_keys).collect(engine="streaming"),
    }
    if collected["coverage"]["municipality_name"].null_count():
        missing = (
            collected["coverage"]
            .filter(pl.col("municipality_name").is_null())["municipality"]
            .unique()
            .sort()
            .to_list()
        )
        raise ValueError(f"municípios ausentes no catálogo estadual: {missing}")

    stats = (
        pl.scan_parquet(_partial_paths(work_dir, "statistics", sources))
        .select(
            pl.col("total_events").sum(),
            pl.col("valid_timestamp_events").sum(),
            pl.col("temporal_outlier_events").sum(),
            pl.col("first_valid_event_at").min(),
            pl.col("last_valid_event_at").max(),
        )
        .collect(engine="streaming")
        .row(named=True)
    )
    _validate_final_frames(collected, stats)

    coverage_frame = collected["coverage"]
    applications_frame = collected["applications"]
    catalog_sections = coverage_frame.height
    published_sections = coverage_frame.filter(
        pl.col("publication_status") == "published"
    ).height
    unpublished_sections = coverage_frame.filter(
        pl.col("publication_status") == "not_published"
    ).height
    if published_sections + unpublished_sections != catalog_sections:
        raise ValueError("Gold exige discovery concluído para todas as seções")
    first_row = coverage_frame.row(0, named=True)
    collected["overview"] = pl.DataFrame(
        {
            "election_year": [first_row["election_year"]],
            "pleito": [first_row["pleito"]],
            "uf": [first_row["uf"]],
            "catalog_sections": [catalog_sections],
            "published_sections": [published_sections],
            "unpublished_sections": [unpublished_sections],
            "sections_with_events": [int(coverage_frame["has_events"].sum())],
            "municipalities": [coverage_frame["municipality"].n_unique()],
            "zones": [
                coverage_frame.select(pl.struct("municipality", "zone").n_unique()).item()
            ],
            "total_events": [int(stats["total_events"])],
            "valid_timestamp_events": [int(stats["valid_timestamp_events"])],
            "temporal_outlier_events": [int(stats["temporal_outlier_events"])],
            "applications": [applications_frame["application"].n_unique()],
            "severities": [applications_frame["severity"].n_unique()],
            "coverage_rate": [published_sections / catalog_sections],
            "first_valid_event_at": [stats["first_valid_event_at"]],
            "last_valid_event_at": [stats["last_valid_event_at"]],
        }
    )
    return collected


def _validate_final_frames(
    frames: dict[str, pl.DataFrame], stats: dict[str, Any]
) -> None:
    coverage = frames["coverage"]
    timeline = frames["event_timeline"]
    applications = frames["applications"]
    outliers = frames["temporal_outliers"]
    total = int(stats["total_events"])
    valid = int(stats["valid_timestamp_events"])
    atypical = int(stats["temporal_outlier_events"])
    if total != valid + atypical:
        raise ValueError("status temporal não cobre todos os eventos Silver")
    if coverage["section_id"].n_unique() != coverage.height:
        raise ValueError("coverage Gold contém section_id duplicado")
    if _sum_column(coverage, "event_count") != total:
        raise ValueError("contagem de eventos por seção não fecha com a Silver")
    if _sum_column(applications, "event_count") != total:
        raise ValueError("contagem por aplicação não fecha com a Silver")
    if _sum_column(timeline, "event_count") != valid:
        raise ValueError("linha do tempo não fecha com timestamps válidos")
    if _sum_column(outliers, "event_count") != atypical:
        raise ValueError("outliers temporais não fecham com a Silver")
    if coverage.filter(
        (pl.col("publication_status") == "not_published")
        & (pl.col("event_count") != 0)
    ).height:
        raise ValueError("seção sem arquivo publicado contém eventos")
    if coverage.filter(
        (pl.col("publication_status") == "published")
        & (pl.col("event_count") == 0)
    ).height:
        raise ValueError("seção publicada não contém eventos")


def _publish_frames(frames: dict[str, pl.DataFrame], *, output_dir: Path) -> None:
    staging = output_dir.with_name(f".{output_dir.name}.tmp-{uuid4().hex}")
    backup = output_dir.with_name(f".{output_dir.name}.backup-{uuid4().hex}")
    try:
        for table in (
            "overview",
            "coverage",
            "event_timeline",
            "applications",
            "temporal_outliers",
        ):
            destination = staging / table / "part-00000.parquet"
            destination.parent.mkdir(parents=True, exist_ok=True)
            frames[table].write_parquet(
                destination, compression="zstd", statistics=True
            )
        if output_dir.exists():
            output_dir.replace(backup)
        try:
            promote_directory(staging, output_dir)
        except Exception:
            if backup.exists() and not output_dir.exists():
                backup.replace(output_dir)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def build_gold_partition(
    *,
    events_dir: Path,
    coverage_file: Path,
    state_config_path: Path,
    output_dir: Path,
    uf: str,
    limit: int | None = None,
) -> GoldBuildResult:
    """Constrói a Gold em partes reiniciáveis e só publica uma partição completa."""
    if limit is not None and limit <= 0:
        raise ValueError("limit deve ser maior que zero")
    sources = sorted(events_dir.glob("part-*.parquet"))
    if not sources:
        raise FileNotFoundError(f"Nenhum Parquet Silver encontrado em {events_dir}")
    if not coverage_file.exists():
        raise FileNotFoundError(f"Cobertura Silver não encontrada em {coverage_file}")
    fingerprints = [_source_fingerprint(path) for path in sources]
    coverage_fingerprint = _source_fingerprint(coverage_file)
    catalog_fingerprint = _file_sha256(state_config_path)
    success_marker = output_dir / "_SUCCESS.json"
    previous_success = _read_json(success_marker)
    output_paths = tuple(
        str(output_dir / table / "part-00000.parquet")
        for table in (
            "overview",
            "coverage",
            "event_timeline",
            "applications",
            "temporal_outliers",
        )
    )
    if (
        previous_success
        and previous_success.get("schema_version") == GOLD_SCHEMA_VERSION
        and previous_success.get("sources") == fingerprints
        and previous_success.get("coverage") == coverage_fingerprint
        and previous_success.get("state_config_sha256") == catalog_fingerprint
        and all(Path(path).exists() for path in output_paths)
    ):
        return GoldBuildResult(
            output_files=output_paths,
            processed_parts=0,
            reused_parts=len(sources),
            remaining_parts=0,
            completed=True,
            total_events=int(previous_success["total_events"]),
            catalog_sections=int(previous_success["catalog_sections"]),
            temporal_outlier_events=int(
                previous_success["temporal_outlier_events"]
            ),
        )

    work_dir = output_dir.with_name(f".{output_dir.name}.work")
    processed = 0
    reused = 0
    remaining = 0
    for source, fingerprint in zip(sources, fingerprints, strict=True):
        checkpoint = work_dir / "checkpoints" / f"{source.stem}.json"
        previous = _read_json(checkpoint)
        expected = [
            work_dir / "partials" / table / source.name for table in PARTIAL_TABLES
        ]
        if (
            previous
            and previous.get("schema_version") == GOLD_SCHEMA_VERSION
            and previous.get("source") == fingerprint
            and all(path.exists() for path in expected)
        ):
            reused += 1
            continue
        if limit is not None and processed >= limit:
            remaining += 1
            continue
        _write_partials(source, work_dir=work_dir)
        _write_json_atomic(
            checkpoint,
            {"schema_version": GOLD_SCHEMA_VERSION, "source": fingerprint},
        )
        processed += 1

    if remaining:
        return GoldBuildResult(
            output_files=(),
            processed_parts=processed,
            reused_parts=reused,
            remaining_parts=remaining,
            completed=False,
            total_events=None,
            catalog_sections=None,
            temporal_outlier_events=None,
        )

    municipality_names = load_municipality_names(state_config_path, uf=uf)
    frames = _final_frames(
        sources=sources,
        work_dir=work_dir,
        coverage_file=coverage_file,
        municipality_names=municipality_names,
    )
    overview = frames["overview"].row(0, named=True)
    _publish_frames(frames, output_dir=output_dir)
    payload = {
        "schema_version": GOLD_SCHEMA_VERSION,
        "sources": fingerprints,
        "coverage": coverage_fingerprint,
        "state_config_sha256": catalog_fingerprint,
        "outputs": list(output_paths),
        "total_events": int(overview["total_events"]),
        "catalog_sections": int(overview["catalog_sections"]),
        "temporal_outlier_events": int(overview["temporal_outlier_events"]),
    }
    _write_json_atomic(output_dir / "_SUCCESS.json", payload)
    return GoldBuildResult(
        output_files=output_paths,
        processed_parts=processed,
        reused_parts=reused,
        remaining_parts=0,
        completed=True,
        total_events=int(overview["total_events"]),
        catalog_sections=int(overview["catalog_sections"]),
        temporal_outlier_events=int(overview["temporal_outlier_events"]),
    )
