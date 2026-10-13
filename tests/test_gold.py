import json
from datetime import date, datetime
from pathlib import Path

import polars as pl
import pytest

from tse_urna.transformation.gold import (
    build_gold_partition,
    municipality_names_from_state_config,
)


def _event(
    *,
    section: str,
    recorded: datetime,
    valid: bool,
    application: str,
    severity: str,
) -> dict:
    municipality = "13897"
    zone = "0003"
    return {
        "section_id": f"CE-{municipality}-{zone}-{section}",
        "election_year": 2026,
        "pleito": "3220",
        "uf": "CE",
        "municipality": municipality,
        "zone": zone,
        "section": section,
        "event_timestamp_recorded": recorded,
        "event_year_recorded": recorded.year,
        "timestamp_status": "valid" if valid else "outside_election_year",
        "event_timestamp_validated": recorded if valid else None,
        "event_date_validated": recorded.date() if valid else None,
        "severity": severity,
        "application": application,
    }


def _coverage() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "section_id": [
                "CE-13897-0003-0444",
                "CE-13897-0003-0445",
                "CE-13897-0003-0446",
            ],
            "election_year": [2026, 2026, 2026],
            "pleito": ["3220", "3220", "3220"],
            "uf": ["CE", "CE", "CE"],
            "municipality": ["13897", "13897", "13897"],
            "zone": ["0003", "0003", "0003"],
            "section": ["0444", "0445", "0446"],
            "publication_status": ["published", "published", "not_published"],
            "has_published_file": [True, True, False],
        }
    )


def _state_config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "abr": [
                    {
                        "cd": "ce",
                        "mu": [{"cd": "13897", "nm": "FORTALEZA"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def test_gold_is_restartable_and_reconciles_all_tables(tmp_path: Path):
    events = tmp_path / "silver-events"
    events.mkdir()
    pl.DataFrame(
        [
            _event(
                section="0444",
                recorded=datetime(2026, 10, 4, 8, 15),
                valid=True,
                application="VOTA",
                severity="INFO",
            ),
            _event(
                section="0444",
                recorded=datetime(2029, 9, 29, 15, 53, 3),
                valid=False,
                application="LOGD",
                severity="ALERTA",
            ),
        ]
    ).write_parquet(events / "part-00000.parquet")
    pl.DataFrame(
        [
            _event(
                section="0445",
                recorded=datetime(2026, 10, 4, 9, 30),
                valid=True,
                application="VOTA",
                severity="INFO",
            )
        ]
    ).write_parquet(events / "part-00001.parquet")
    coverage = tmp_path / "coverage.parquet"
    _coverage().write_parquet(coverage)
    catalog = tmp_path / "state-config.json"
    _state_config(catalog)
    output = tmp_path / "gold"

    first = build_gold_partition(
        events_dir=events,
        coverage_file=coverage,
        state_config_path=catalog,
        output_dir=output,
        uf="CE",
        limit=1,
    )
    assert not first.completed
    assert (first.processed_parts, first.remaining_parts) == (1, 1)
    assert not output.exists()

    second = build_gold_partition(
        events_dir=events,
        coverage_file=coverage,
        state_config_path=catalog,
        output_dir=output,
        uf="CE",
        limit=1,
    )
    third = build_gold_partition(
        events_dir=events,
        coverage_file=coverage,
        state_config_path=catalog,
        output_dir=output,
        uf="CE",
    )

    assert second.completed
    assert (second.processed_parts, second.reused_parts) == (1, 1)
    assert (third.processed_parts, third.reused_parts) == (0, 2)

    overview = pl.read_parquet(output / "overview" / "part-00000.parquet").row(
        0, named=True
    )
    assert overview["catalog_sections"] == 3
    assert overview["published_sections"] == 2
    assert overview["unpublished_sections"] == 1
    assert overview["sections_with_events"] == 2
    assert overview["total_events"] == 3
    assert overview["valid_timestamp_events"] == 2
    assert overview["temporal_outlier_events"] == 1
    assert overview["applications"] == 2
    assert overview["severities"] == 2
    assert overview["coverage_rate"] == pytest.approx(2 / 3)

    gold_coverage = pl.read_parquet(
        output / "coverage" / "part-00000.parquet"
    ).sort("section")
    assert gold_coverage["municipality_name"].to_list() == [
        "FORTALEZA",
        "FORTALEZA",
        "FORTALEZA",
    ]
    assert gold_coverage["event_count"].to_list() == [2, 1, 0]
    assert gold_coverage["has_events"].to_list() == [True, True, False]

    timeline = pl.read_parquet(
        output / "event_timeline" / "part-00000.parquet"
    )
    assert timeline["event_count"].sum() == 2
    assert timeline["event_date"].unique().to_list() == [date(2026, 10, 4)]
    assert sorted(timeline["event_hour"].to_list()) == [8, 9]

    applications = pl.read_parquet(
        output / "applications" / "part-00000.parquet"
    )
    assert applications["event_count"].sum() == 3

    outliers = pl.read_parquet(
        output / "temporal_outliers" / "part-00000.parquet"
    )
    assert outliers["event_count"].sum() == 1
    assert outliers["event_year_recorded"].to_list() == [2029]
    assert outliers["section_id"].to_list() == ["CE-13897-0003-0444"]


def test_municipality_names_reject_conflicting_catalog_entries():
    payload = {
        "abr": [
            {
                "cd": "ce",
                "mu": [
                    {"cd": "13897", "nm": "FORTALEZA"},
                    {"cd": "13897", "nm": "OUTRO NOME"},
                ],
            }
        ]
    }

    with pytest.raises(ValueError, match="nomes conflitantes"):
        municipality_names_from_state_config(payload, uf="CE")
