from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import polars as pl

from tse_urna.ingestion.manifest import Manifest

CRITICAL_COLUMNS = (
    "election_year",
    "pleito",
    "uf",
    "municipality",
    "zone",
    "section",
    "source_hash",
    "source_file",
    "event_timestamp",
    "severity",
    "ue_id",
    "application",
    "message_raw",
    "mac",
)


@dataclass(frozen=True, slots=True)
class QualitySummary:
    passed: bool
    has_warnings: bool
    total_sections: int
    discovered_sections: int
    sections_with_files: int
    empty_sections: int
    total_files: int
    completed_files: int
    valid_rows: int
    rejected_rows: int
    distinct_sources: int
    distinct_sections: int
    critical_nulls: int
    temporal_outlier_rows: int
    temporal_outlier_years: tuple[tuple[int, int], ...]
    parquet_parts: int
    parquet_bytes: int
    min_timestamp: str
    max_timestamp: str


def _count_quarantine_rows(paths: list[Path]) -> int:
    count = 0
    for path in paths:
        with path.open(encoding="utf-8") as stream:
            count += sum(1 for line in stream if line.strip())
    return count


def build_quality_summary(
    *,
    manifest: Manifest,
    compacted_dir: Path,
    quarantine_dir: Path,
    year: int,
    pleito: str | int,
    uf: str,
) -> QualitySummary:
    parts = sorted(compacted_dir.glob("part-*.parquet"))
    if not parts:
        raise FileNotFoundError(f"Nenhum Parquet compactado encontrado em {compacted_dir}")

    with manifest.connect() as conn:
        sections = conn.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(discovery_status='discovered') AS discovered,
                   SUM(discovery_status='discovered' AND files_found > 0) AS with_files,
                   SUM(discovery_status='discovered' AND files_found = 0) AS empty
            FROM sections
            WHERE election_year=? AND pleito=? AND uf=?
            """,
            (int(year), str(pleito), uf.lower()),
        ).fetchone()
        files = conn.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(status='downloaded' AND extract_status='extracted'
                       AND parse_status='parsed') AS completed
            FROM files
            WHERE election_year=? AND pleito=? AND uf=?
            """,
            (int(year), str(pleito), uf.lower()),
        ).fetchone()

    frame = pl.scan_parquet(parts)
    schema = frame.collect_schema()
    missing_columns = [column for column in CRITICAL_COLUMNS if column not in schema]
    if missing_columns:
        raise ValueError(f"Colunas críticas ausentes: {', '.join(missing_columns)}")

    metrics = frame.select(
        pl.len().alias("valid_rows"),
        pl.col("source_hash").n_unique().alias("distinct_sources"),
        pl.struct("municipality", "zone", "section")
        .n_unique()
        .alias("distinct_sections"),
        pl.col("event_timestamp").min().alias("min_timestamp"),
        pl.col("event_timestamp").max().alias("max_timestamp"),
        pl.sum_horizontal(
            [pl.col(column).null_count() for column in CRITICAL_COLUMNS]
        ).alias("critical_nulls"),
    ).collect(engine="streaming").row(named=True)
    temporal_rows = (
        frame.group_by(pl.col("event_timestamp").dt.year().alias("year"))
        .agg(pl.len().alias("rows"))
        .sort("year")
        .collect(engine="streaming")
    )
    temporal_outlier_years = tuple(
        (int(row["year"]), int(row["rows"]))
        for row in temporal_rows.iter_rows(named=True)
        if int(row["year"]) != int(year)
    )
    temporal_outlier_rows = sum(rows for _, rows in temporal_outlier_years)

    quarantine_paths = sorted(quarantine_dir.glob("*.jsonl"))
    rejected_rows = _count_quarantine_rows(quarantine_paths)
    total_sections = int(sections["total"] or 0)
    discovered_sections = int(sections["discovered"] or 0)
    sections_with_files = int(sections["with_files"] or 0)
    empty_sections = int(sections["empty"] or 0)
    total_files = int(files["total"] or 0)
    completed_files = int(files["completed"] or 0)
    valid_rows = int(metrics["valid_rows"])
    distinct_sources = int(metrics["distinct_sources"])
    distinct_sections = int(metrics["distinct_sections"])
    critical_nulls = int(metrics["critical_nulls"])
    passed = all(
        (
            total_sections > 0,
            total_sections == discovered_sections,
            total_files == completed_files,
            valid_rows > 0,
            rejected_rows == 0,
            distinct_sources == completed_files,
            distinct_sections == sections_with_files,
            critical_nulls == 0,
        )
    )
    return QualitySummary(
        passed=passed,
        has_warnings=empty_sections > 0 or temporal_outlier_rows > 0,
        total_sections=total_sections,
        discovered_sections=discovered_sections,
        sections_with_files=sections_with_files,
        empty_sections=empty_sections,
        total_files=total_files,
        completed_files=completed_files,
        valid_rows=valid_rows,
        rejected_rows=rejected_rows,
        distinct_sources=distinct_sources,
        distinct_sections=distinct_sections,
        critical_nulls=critical_nulls,
        temporal_outlier_rows=temporal_outlier_rows,
        temporal_outlier_years=temporal_outlier_years,
        parquet_parts=len(parts),
        parquet_bytes=sum(path.stat().st_size for path in parts),
        min_timestamp=str(metrics["min_timestamp"]),
        max_timestamp=str(metrics["max_timestamp"]),
    )


def write_quality_report(
    summary: QualitySummary,
    *,
    output_path: Path,
    year: int,
    pleito: str | int,
    uf: str,
) -> None:
    status = (
        "PASS WITH WARNINGS"
        if summary.passed and summary.has_warnings
        else "PASS"
        if summary.passed
        else "FAIL"
    )
    outlier_years = ", ".join(
        f"{year}: {rows:,}" for year, rows in summary.temporal_outlier_years
    ) or "nenhum"
    report = f"""# Relatório de qualidade — {uf.upper()} {year}/{pleito}

Gerado em: {datetime.now().astimezone().isoformat(timespec="seconds")}

Status: **{status}**

## Cobertura

- Seções no catálogo: {summary.total_sections:,}
- Seções com discovery concluído: {summary.discovered_sections:,}
- Seções com arquivo de urna: {summary.sections_with_files:,}
- Seções sem arquivo publicado: {summary.empty_sections:,}
- Arquivos no manifest: {summary.total_files:,}
- Arquivos concluídos até Bronze: {summary.completed_files:,}

## Bronze compactado

- Eventos válidos: {summary.valid_rows:,}
- Linhas em quarantine: {summary.rejected_rows:,}
- Fontes distintas: {summary.distinct_sources:,}
- Seções distintas com eventos: {summary.distinct_sections:,}
- Nulos em colunas críticas: {summary.critical_nulls:,}
- Timestamps fora de {year}: {summary.temporal_outlier_rows:,}
- Distribuição dos anos atípicos: {outlier_years}
- Partes Parquet: {summary.parquet_parts:,}
- Tamanho Parquet: {summary.parquet_bytes:,} bytes
- Primeiro timestamp: {summary.min_timestamp}
- Último timestamp: {summary.max_timestamp}

## Critérios

- Discovery concluído para todo o catálogo.
- Todos os arquivos encontrados concluídos até Bronze.
- Uma fonte Bronze distinta por arquivo concluído.
- Cobertura de seções consistente entre manifest e Bronze.
- Zero linhas rejeitadas e zero nulos em colunas críticas.

## Avisos

- Seções sem arquivo publicado são mantidas como cobertura ausente e podem ser
  reconsultadas com `discover-uf --refresh-empty`.
- Timestamps fora do ano eleitoral são preservados como registrados pela urna e devem
  ser tratados explicitamente na camada Silver.
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
