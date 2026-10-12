from datetime import datetime
from pathlib import Path

import polars as pl

from tse_urna.transformation.silver import (
    build_section_coverage,
    build_silver_events,
)


def _bronze_frame(timestamps: list[datetime]) -> pl.DataFrame:
    size = len(timestamps)
    return pl.DataFrame(
        {
            "election_year": [2026] * size,
            "pleito": ["3220"] * size,
            "uf": ["ce"] * size,
            "municipality": ["13897"] * size,
            "zone": ["0003"] * size,
            "section": ["0444"] * size,
            "source_hash": ["hash-a"] * size,
            "source_file": ["sample.logjez"] * size,
            "source_log": ["ignored/logd.dat"] * size,
            "line_number": list(range(1, size + 1)),
            "event_timestamp": timestamps,
            "severity": [" info "] * size,
            "ue_id": ["123"] * size,
            "application": [" scue "] * size,
            "message_raw": ["mensagem"] * size,
            "mac": ["ABC"] * size,
        }
    )


def _coverage_rows() -> list[dict]:
    return [
        {
            "election_year": 2026,
            "pleito": "3220",
            "uf": "ce",
            "municipality": "13897",
            "zone": "0003",
            "section": "0444",
            "discovery_status": "discovered",
            "files_found": 1,
            "discovered_at": "2026-10-12 10:00:00",
        },
        {
            "election_year": 2026,
            "pleito": "3220",
            "uf": "ce",
            "municipality": "13897",
            "zone": "0003",
            "section": "0445",
            "discovery_status": "discovered",
            "files_found": 0,
            "discovered_at": "2026-10-12 10:00:01",
        },
    ]


def test_section_coverage_preserves_unpublished_sections(tmp_path: Path):
    output = tmp_path / "coverage"

    first = build_section_coverage(rows=_coverage_rows(), output_dir=output)
    second = build_section_coverage(rows=_coverage_rows(), output_dir=output)
    frame = pl.read_parquet(first.output_file).sort("section")

    assert first.rows == 2
    assert first.published_sections == 1
    assert first.unpublished_sections == 1
    assert not first.reused
    assert second.reused
    assert frame["section_id"].to_list() == ["CE-13897-0003-0444", "CE-13897-0003-0445"]
    assert frame["publication_status"].to_list() == ["published", "not_published"]


def test_silver_flags_out_of_year_timestamp_without_changing_it(tmp_path: Path):
    bronze = tmp_path / "bronze"
    bronze.mkdir()
    _bronze_frame(
        [datetime(2026, 10, 4, 8), datetime(2029, 9, 29, 15, 53, 3)]
    ).write_parquet(bronze / "part-00000.parquet")

    result = build_silver_events(
        input_dir=bronze,
        output_dir=tmp_path / "silver",
        election_year=2026,
        coverage_fingerprint="coverage-a",
        expected_published_sections=1,
    )
    frame = pl.read_parquet(result.output_files[0]).sort("line_number")

    assert result.event_rows == 2
    assert result.temporal_outlier_rows == 1
    assert result.distinct_sections == 1
    assert frame["timestamp_status"].to_list() == ["valid", "outside_election_year"]
    assert frame["event_timestamp_recorded"][1] == datetime(2029, 9, 29, 15, 53, 3)
    assert frame["event_timestamp_validated"].null_count() == 1
    assert frame["event_date_validated"].null_count() == 1
    assert frame["severity"].to_list() == ["INFO", "INFO"]
    assert frame["application"].to_list() == ["SCUE", "SCUE"]


def test_silver_batches_are_restartable_and_limit_only_pending(tmp_path: Path):
    bronze = tmp_path / "bronze"
    bronze.mkdir()
    _bronze_frame([datetime(2026, 10, 4, 8)]).write_parquet(
        bronze / "part-00000.parquet"
    )
    _bronze_frame([datetime(2026, 10, 4, 9)]).write_parquet(
        bronze / "part-00001.parquet"
    )
    silver = tmp_path / "silver"

    first = build_silver_events(
        input_dir=bronze,
        output_dir=silver,
        election_year=2026,
        coverage_fingerprint="coverage-a",
        expected_published_sections=1,
        limit=1,
    )
    second = build_silver_events(
        input_dir=bronze,
        output_dir=silver,
        election_year=2026,
        coverage_fingerprint="coverage-a",
        expected_published_sections=1,
        limit=1,
    )
    third = build_silver_events(
        input_dir=bronze,
        output_dir=silver,
        election_year=2026,
        coverage_fingerprint="coverage-a",
        expected_published_sections=1,
        limit=1,
    )

    assert (first.processed_batches, first.remaining_batches) == (1, 1)
    assert (second.processed_batches, second.reused_batches) == (1, 1)
    assert second.remaining_batches == 0
    assert second.event_rows == 2
    assert (third.processed_batches, third.reused_batches) == (0, 2)
    assert (silver / "_SUCCESS.json").exists()
