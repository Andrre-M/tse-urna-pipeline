import json
from datetime import date, datetime
from pathlib import Path

import polars as pl
import pytest

from tse_urna.dashboard import (
    BUILD_MARKER,
    DATASET_REVISION,
    build_dashboard_from_parquets,
    dataset_url,
)


def _write_gold(tmp_path: Path) -> dict[str, Path]:
    frames = {
        "overview": pl.DataFrame(
            {
                "catalog_sections": [2],
                "published_sections": [1],
                "unpublished_sections": [1],
                "sections_with_events": [1],
                "municipalities": [1],
                "zones": [1],
                "total_events": [3],
                "valid_timestamp_events": [2],
                "temporal_outlier_events": [1],
                "applications": [2],
                "severities": [2],
                "coverage_rate": [0.5],
                "first_valid_event_at": [datetime(2026, 10, 4, 8)],
                "last_valid_event_at": [datetime(2026, 10, 4, 9)],
            }
        ),
        "coverage": pl.DataFrame(
            {
                "section_id": ["CE-1-0001-0001", "CE-1-0001-0002"],
                "municipality": ["1", "1"],
                "municipality_name": ["TESTE", "TESTE"],
                "zone": ["0001", "0001"],
                "section": ["0001", "0002"],
                "publication_status": ["published", "not_published"],
                "has_published_file": [True, False],
                "event_count": [3, 0],
                "has_events": [True, False],
            }
        ),
        "event_timeline": pl.DataFrame(
            {
                "municipality": ["1"],
                "municipality_name": ["TESTE"],
                "zone": ["0001"],
                "event_date": [date(2026, 10, 4)],
                "event_hour": [8],
                "severity": ["INFO"],
                "event_count": [2],
            }
        ),
        "applications": pl.DataFrame(
            {
                "municipality": ["1", "1"],
                "municipality_name": ["TESTE", "TESTE"],
                "zone": ["0001", "0001"],
                "application": ["VOTA", "LOGD"],
                "severity": ["INFO", "ALERTA"],
                "event_count": [2, 1],
            }
        ),
        "temporal_outliers": pl.DataFrame(
            {
                "municipality_name": ["TESTE"],
                "zone": ["0001"],
                "section": ["0001"],
                "section_id": ["CE-1-0001-0001"],
                "event_year_recorded": [2029],
                "application": ["LOGD"],
                "severity": ["ALERTA"],
                "event_count": [1],
                "first_recorded_event_at": [datetime(2029, 1, 1, 12)],
                "last_recorded_event_at": [datetime(2029, 1, 1, 12)],
            }
        ),
    }
    paths = {}
    for name, frame in frames.items():
        path = tmp_path / f"{name}.parquet"
        frame.write_parquet(path)
        paths[name] = path
    return paths


def test_dashboard_build_reconciles_and_writes_static_artifact(tmp_path: Path):
    source = tmp_path / "source"
    (source / "assets").mkdir(parents=True)
    (source / "index.html").write_text("<h1>Painel</h1>", encoding="utf-8")
    (source / "assets" / "app.js").write_text("", encoding="utf-8")
    output = tmp_path / "dist"

    build_dashboard_from_parquets(
        _write_gold(tmp_path),
        output_dir=output,
        source_dir=source,
    )

    assert (output / BUILD_MARKER).read_text(encoding="utf-8") == "generated\n"
    assert json.loads((output / "data" / "coverage.json").read_text(encoding="utf-8"))[0][
        "municipality_name"
    ] == "TESTE"
    metadata = json.loads((output / "build.json").read_text(encoding="utf-8"))
    assert metadata["revision"] == DATASET_REVISION
    assert metadata["tables"]["event_timeline"] == 1


def test_dashboard_build_refuses_unmarked_output(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "dist"
    output.mkdir()
    (output / "keep.txt").write_text("user data", encoding="utf-8")

    with pytest.raises(ValueError, match="recusa em substituir"):
        build_dashboard_from_parquets(
            _write_gold(tmp_path),
            output_dir=output,
            source_dir=source,
        )
    assert (output / "keep.txt").read_text(encoding="utf-8") == "user data"


def test_dataset_url_is_revision_pinned():
    url = dataset_url("data/overview/part-00000.parquet")
    assert DATASET_REVISION in url
    assert "/resolve/" in url
