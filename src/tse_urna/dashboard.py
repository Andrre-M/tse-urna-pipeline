from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
import polars as pl

DATASET_REPOSITORY = "Andrre-M/tse-urna-ce-2026-gold"
DATASET_REVISION = "bb114e79239a8315eb8f069aaeeb120081bc54a9"
BUILD_MARKER = ".tse-dashboard-build"


@dataclass(frozen=True)
class GoldTable:
    path: str
    rows: int
    sha256: str


GOLD_TABLES: dict[str, GoldTable] = {
    "overview": GoldTable(
        path="data/overview/part-00000.parquet",
        rows=1,
        sha256="2b29c6e37c2f3e15ca4a50ffea6893093c0985b440fbd827987b552546a1614e",
    ),
    "coverage": GoldTable(
        path="data/coverage/part-00000.parquet",
        rows=25_650,
        sha256="ecf1a29501333d133f76f4be1023e92404acd4ddb2f1a1a67d0b3a4b8a616135",
    ),
    "event_timeline": GoldTable(
        path="data/event_timeline/part-00000.parquet",
        rows=12_307,
        sha256="b5d80a577f939b0a3282ab6cfa0c74f7c791e883641688cfce4f1c4f9e836c33",
    ),
    "applications": GoldTable(
        path="data/applications/part-00000.parquet",
        rows=2_780,
        sha256="7cd66abd0f84e97e5119cb8d42e155eee0d0ba7d050bbd4054f6741b1510b1bf",
    ),
    "temporal_outliers": GoldTable(
        path="data/temporal_outliers/part-00000.parquet",
        rows=11,
        sha256="c38dc7afc8be716fe0d42d4ed9697404ae05b01fa4111cc4f27a1dafc09ee202",
    ),
}

REQUIRED_COLUMNS: dict[str, set[str]] = {
    "overview": {
        "catalog_sections",
        "published_sections",
        "unpublished_sections",
        "sections_with_events",
        "municipalities",
        "zones",
        "total_events",
        "valid_timestamp_events",
        "temporal_outlier_events",
        "applications",
        "severities",
        "coverage_rate",
        "first_valid_event_at",
        "last_valid_event_at",
    },
    "coverage": {
        "section_id",
        "municipality",
        "municipality_name",
        "zone",
        "section",
        "publication_status",
        "has_published_file",
        "event_count",
        "has_events",
    },
    "event_timeline": {
        "municipality",
        "municipality_name",
        "zone",
        "event_date",
        "event_hour",
        "severity",
        "event_count",
    },
    "applications": {
        "municipality",
        "municipality_name",
        "zone",
        "application",
        "severity",
        "event_count",
    },
    "temporal_outliers": {
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
    },
}


def dataset_url(path: str) -> str:
    encoded_path = "/".join(quote(part) for part in path.split("/"))
    return (
        f"https://huggingface.co/datasets/{DATASET_REPOSITORY}/resolve/"
        f"{DATASET_REVISION}/{encoded_path}?download=true"
    )


def _download_gold(destination: Path) -> dict[str, Path]:
    destination.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    timeout = httpx.Timeout(60, connect=30)
    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        for name, table in GOLD_TABLES.items():
            target = destination / f"{name}.parquet"
            digest = hashlib.sha256()
            with client.stream("GET", dataset_url(table.path)) as response:
                response.raise_for_status()
                with target.open("wb") as output:
                    for chunk in response.iter_bytes():
                        output.write(chunk)
                        digest.update(chunk)
            if digest.hexdigest() != table.sha256:
                raise ValueError(f"hash inesperado para a tabela Gold {name}")
            paths[name] = target
    return paths


def _read_tables(paths: Mapping[str, Path]) -> dict[str, pl.DataFrame]:
    if set(paths) != set(GOLD_TABLES):
        missing = sorted(set(GOLD_TABLES) - set(paths))
        extra = sorted(set(paths) - set(GOLD_TABLES))
        raise ValueError(f"conjunto de tabelas Gold inválido: ausentes={missing}, extras={extra}")

    tables: dict[str, pl.DataFrame] = {}
    for name, path in paths.items():
        frame = pl.read_parquet(path)
        missing_columns = REQUIRED_COLUMNS[name] - set(frame.columns)
        if missing_columns:
            raise ValueError(f"colunas ausentes em {name}: {sorted(missing_columns)}")
        tables[name] = frame
    return tables


def _reconcile(tables: Mapping[str, pl.DataFrame]) -> None:
    overview = tables["overview"]
    if overview.height != 1:
        raise ValueError("overview deve ter exatamente uma linha")
    totals = overview.row(0, named=True)

    checks = {
        "coverage": int(tables["coverage"]["event_count"].sum()),
        "event_timeline": int(tables["event_timeline"]["event_count"].sum()),
        "applications": int(tables["applications"]["event_count"].sum()),
        "temporal_outliers": int(tables["temporal_outliers"]["event_count"].sum()),
    }
    expected = {
        "coverage": totals["total_events"],
        "event_timeline": totals["valid_timestamp_events"],
        "applications": totals["total_events"],
        "temporal_outliers": totals["temporal_outlier_events"],
    }
    for name, actual in checks.items():
        if actual != expected[name]:
            raise ValueError(f"reconciliação falhou em {name}: {actual} != {expected[name]}")


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"tipo não serializável: {type(value).__name__}")


def _write_data(tables: Mapping[str, pl.DataFrame], destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        payload = json.dumps(
            frame.to_dicts(),
            ensure_ascii=False,
            separators=(",", ":"),
            default=_json_default,
        )
        (destination / f"{name}.json").write_text(payload, encoding="utf-8")


def build_dashboard_from_parquets(
    paths: Mapping[str, Path],
    *,
    output_dir: Path,
    source_dir: Path,
) -> Path:
    tables = _read_tables(paths)
    _reconcile(tables)

    output_dir = output_dir.resolve()
    source_dir = source_dir.resolve()
    if output_dir == source_dir or output_dir in source_dir.parents:
        raise ValueError("o diretório de saída não pode conter nem substituir a fonte")
    if output_dir.exists():
        if not (output_dir / BUILD_MARKER).is_file():
            raise ValueError(f"recusa em substituir diretório sem marcador: {output_dir}")
        shutil.rmtree(output_dir)

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_dir.parent) as staging_name:
        staging = Path(staging_name) / "site"
        shutil.copytree(source_dir, staging)
        _write_data(tables, staging / "data")
        metadata = {
            "dataset": DATASET_REPOSITORY,
            "revision": DATASET_REVISION,
            "tables": {name: frame.height for name, frame in tables.items()},
        }
        (staging / "build.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (staging / BUILD_MARKER).write_text("generated\n", encoding="utf-8")
        staging.replace(output_dir)
    return output_dir


def build_dashboard(*, output_dir: Path, source_dir: Path) -> Path:
    with tempfile.TemporaryDirectory() as download_dir:
        paths = _download_gold(Path(download_dir))
        for name, path in paths.items():
            expected_rows = GOLD_TABLES[name].rows
            actual_rows = pl.scan_parquet(path).select(pl.len()).collect().item()
            if actual_rows != expected_rows:
                raise ValueError(
                    f"contagem inesperada para {name}: {actual_rows} != {expected_rows}"
                )
        return build_dashboard_from_parquets(
            paths,
            output_dir=output_dir,
            source_dir=source_dir,
        )


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Gera o dashboard estático a partir da Gold")
    parser.add_argument("--output", type=Path, default=project_root / "dist")
    parser.add_argument("--source", type=Path, default=project_root / "dashboard")
    args = parser.parse_args()
    output = build_dashboard(output_dir=args.output, source_dir=args.source)
    print(f"Dashboard gerado em {output}")


if __name__ == "__main__":
    main()
