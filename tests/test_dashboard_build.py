import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import polars as pl
import pytest

MODULE_SPEC = spec_from_file_location(
    "build_dashboard", Path(__file__).parents[1] / "scripts" / "build_dashboard.py"
)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
BUILD_DASHBOARD = module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(BUILD_DASHBOARD)

_prepare_geojson = BUILD_DASHBOARD._prepare_geojson
_profile_summary = BUILD_DASHBOARD._profile_summary
_sha256 = BUILD_DASHBOARD._sha256
_zone_summary = BUILD_DASHBOARD._zone_summary


def test_prepare_geojson_joins_ibge_geometry_to_tse_code(tmp_path):
    lookup = tmp_path / "ibge.json"
    lookup.write_text(
        json.dumps([{"id": 2300101, "nome": "Abaiara"}]), encoding="utf-8"
    )
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"codarea": "2300101"},
                "geometry": {"type": "Polygon", "coordinates": []},
            }
        ],
    }
    municipalities = [
        {"municipality_code": "13013", "municipality_name": "ABAIARA"}
    ]

    result = _prepare_geojson(geojson, municipalities, lookup)

    assert result["features"][0]["properties"] == {
        "ibge_code": "2300101",
        "municipality_code": "13013",
        "municipality_name": "ABAIARA",
    }


def test_prepare_geojson_rejects_incomplete_coverage():
    with pytest.raises(ValueError, match="sem correspondência"):
        _prepare_geojson(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "properties": {"municipality_name": "Outro"},
                        "geometry": {"type": "Polygon", "coordinates": []},
                    }
                ],
            },
            [{"municipality_code": "13013", "municipality_name": "ABAIARA"}],
            None,
        )


def test_dashboard_summaries_keep_one_electorate_universe_and_office_rates():
    profiles = pl.DataFrame(
        {
            "municipality_code": ["13013", "13013", "13013"],
            "municipality_name": ["ABAIARA"] * 3,
            "dimension": ["gender"] * 3,
            "registered_electors": [60, 40, 0],
            "biometric_electors": [55, 35, 0],
            "electors_with_disability": [2, 1, 0],
            "electors_with_social_name": [1, 0, 0],
        }
    )
    summary = _profile_summary(profiles)[0]

    assert summary["registered_electors"] == 100
    assert summary["biometric_rate"] == 0.9
    assert summary["disability_rate"] == 0.03

    sections = pl.DataFrame(
        {
            "municipality_code": ["13013", "13013"],
            "municipality_name": ["ABAIARA", "ABAIARA"],
            "zone": ["0026", "0026"],
            "office_code": [1, 1],
            "office": ["Presidente", "Presidente"],
            "eligible_voters": [100, 200],
            "turnout": [80, 150],
            "abstentions": [20, 50],
            "valid_votes": [70, 130],
            "blank_votes": [5, 10],
            "null_votes": [5, 10],
            "separately_annulled_votes": [0, 0],
            "total_votes": [80, 150],
        }
    )
    zone = _zone_summary(sections)[0]

    assert zone["eligible_voters"] == 300
    assert zone["turnout"] == 230
    assert zone["turnout_rate"] == 230 / 300
    assert zone["blank_vote_rate"] == 15 / 230


def test_published_gold_revision_and_hash_are_pinned(tmp_path):
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"gold-eleitoral")

    assert BUILD_DASHBOARD.PUBLISHED_GOLD_REPO == (
        "Andrre-M/tse-urna-ce-2026-gold"
    )
    assert BUILD_DASHBOARD.PUBLISHED_GOLD_REVISION == (
        "f9d59eb4e924d3f554d2862d1e3ba1629633f7f9"
    )
    assert BUILD_DASHBOARD.PUBLISHED_GOLD_MANIFEST_SHA256 == (
        "4a601143fabca9fba7174e764fe4c318d08e152f63d0aed42d57ee0d70216b2b"
    )
    assert _sha256(payload) == (
        "4778aa5ebf493e6d53dc692412b70ca9d58966fc70e44afa65a18de1f39ada82"
    )
