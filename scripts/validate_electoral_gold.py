from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import polars as pl

from tse_urna.transformation.electoral_gold import (
    ELECTORAL_GOLD_SCHEMA_VERSION,
    ELECTORAL_TABLES,
)


def _table_path(gold_dir: Path, table: str) -> Path:
    path = gold_dir / table / "part-00000.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Tabela Gold ausente: {path}")
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_equal(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise ValueError(f"{label}: esperado={expected!r}, obtido={actual!r}")


def validate_electoral_gold(gold_dir: Path) -> dict[str, Any]:
    paths = {table: _table_path(gold_dir, table) for table in ELECTORAL_TABLES}
    frames = {table: pl.read_parquet(path) for table, path in paths.items()}

    metadata = frames["metadata"].row(0, named=True)
    _assert_equal(
        "metadata.schema_version",
        metadata["schema_version"],
        ELECTORAL_GOLD_SCHEMA_VERSION,
    )

    overview = frames["election_overview"]
    municipalities = frames["municipality_summary"]
    sections = frames["section_summary"]
    section_results = frames["section_results"]
    candidates = frames["candidate_results"]
    electorate = frames["electorate_profile"]

    offices = overview["office_code"].n_unique()
    municipality_count = municipalities["municipality_code"].n_unique()
    section_count = sections["section_id"].n_unique()
    _assert_equal("election_overview por cargo", overview.height, offices)
    _assert_equal(
        "municipality_summary por município/cargo",
        municipalities.height,
        municipality_count * offices,
    )
    _assert_equal(
        "section_summary por seção/cargo",
        sections.height,
        section_count * offices,
    )

    profile_totals = {
        dimension: int(
            electorate.filter(pl.col("dimension") == dimension)[
                "registered_electors"
            ].sum()
        )
        for dimension in ("gender", "age_band", "age_gender")
    }
    _assert_equal(
        "perfil faixa etária",
        profile_totals["age_band"],
        profile_totals["gender"],
    )
    _assert_equal(
        "perfil faixa etária/gênero",
        profile_totals["age_gender"],
        profile_totals["gender"],
    )
    _assert_equal(
        "metadata.registered_electors_profile",
        metadata["registered_electors_profile"],
        profile_totals["gender"],
    )

    candidate_keys = [
        "election_year",
        "round",
        "uf",
        "municipality_code",
        "municipality_name",
        "office_code",
        "office",
        "ballot_number",
        "ballot_name",
        "candidate_id",
        "result_type",
    ]
    section_candidate_totals = (
        section_results.filter(pl.col("result_type").is_in(["candidate", "party"]))
        .group_by(candidate_keys)
        .agg(pl.col("votes").sum())
        .sort(candidate_keys)
    )
    candidate_totals = candidates.select(*candidate_keys, "votes").sort(
        candidate_keys
    )
    if not candidate_totals.equals(section_candidate_totals, null_equal=True):
        raise ValueError("candidate_results não reconcilia com section_results")

    missing_candidate_parties = candidates.filter(
        (pl.col("result_type") == "candidate")
        & pl.col("party_abbreviation").is_null()
    ).height
    _assert_equal("candidatos sem partido", missing_candidate_parties, 0)

    table_stats = {
        table: {
            "rows": frame.height,
            "bytes": paths[table].stat().st_size,
            "sha256": _sha256(paths[table]),
        }
        for table, frame in frames.items()
    }
    return {
        "status": "PASS",
        "schema_version": metadata["schema_version"],
        "municipalities": municipality_count,
        "sections": section_count,
        "offices": offices,
        "registered_electors": profile_totals["gender"],
        "missing_candidate_parties": missing_candidate_parties,
        "tables": table_stats,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("gold_dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate_electoral_gold(args.gold_dir)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{payload}\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
