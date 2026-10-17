from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import unicodedata
from pathlib import Path
from typing import Any

import httpx
import polars as pl

PUBLISHED_GOLD_REPO = "Andrre-M/tse-urna-ce-2026-gold"
PUBLISHED_GOLD_REVISION = "f9d59eb4e924d3f554d2862d1e3ba1629633f7f9"
PUBLISHED_GOLD_MANIFEST = "electoral_manifest.json"
PUBLISHED_GOLD_MANIFEST_SHA256 = (
    "4a601143fabca9fba7174e764fe4c318d08e152f63d0aed42d57ee0d70216b2b"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(client: httpx.Client, url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.download")
    try:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            with temporary.open("wb") as output:
                for chunk in response.iter_bytes():
                    output.write(chunk)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def fetch_published_gold(cache_dir: Path) -> Path:
    """Baixa e valida a revisão imutável da Gold eleitoral publicada."""
    revision_dir = cache_dir / PUBLISHED_GOLD_REVISION
    manifest_path = revision_dir / PUBLISHED_GOLD_MANIFEST
    base_url = (
        f"https://huggingface.co/datasets/{PUBLISHED_GOLD_REPO}/resolve/"
        f"{PUBLISHED_GOLD_REVISION}"
    )
    with httpx.Client(follow_redirects=True, timeout=120.0) as client:
        if (
            not manifest_path.exists()
            or _sha256(manifest_path) != PUBLISHED_GOLD_MANIFEST_SHA256
        ):
            _download(client, f"{base_url}/{PUBLISHED_GOLD_MANIFEST}", manifest_path)
        if _sha256(manifest_path) != PUBLISHED_GOLD_MANIFEST_SHA256:
            raise ValueError("SHA-256 divergente no manifesto eleitoral publicado")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("extension") != "electoral":
            raise ValueError("Manifesto publicado não descreve a Gold eleitoral")
        for table, metadata in manifest["configurations"].items():
            remote_path = str(metadata["path"])
            prefix = "data/electoral/"
            if not remote_path.startswith(prefix):
                raise ValueError(f"Caminho eleitoral inválido no manifesto: {remote_path}")
            destination = revision_dir / remote_path.removeprefix(prefix)
            expected_hash = str(metadata["sha256"])
            if not destination.exists() or _sha256(destination) != expected_hash:
                _download(client, f"{base_url}/{remote_path}", destination)
            if destination.stat().st_size != int(metadata["bytes"]):
                raise ValueError(f"Tamanho divergente em {table}: {destination}")
            if _sha256(destination) != expected_hash:
                raise ValueError(f"SHA-256 divergente em {table}: {destination}")
    return revision_dir


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def _compact_frame(frame: pl.DataFrame) -> dict[str, Any]:
    return {"fields": frame.columns, "rows": frame.rows()}


def _rows(path: Path, columns: list[str] | None = None) -> list[dict[str, Any]]:
    frame = pl.read_parquet(path, columns=columns)
    return frame.to_dicts()


def _parquet(gold_dir: Path, table: str) -> Path:
    path = gold_dir / table / "part-00000.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Tabela Gold ausente: {path}")
    return path


def _normalized_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    characters = (
        character for character in normalized if not unicodedata.combining(character)
    )
    return "".join(characters).casefold()


def _prepare_geojson(
    geojson: dict[str, Any],
    municipalities: list[dict[str, Any]],
    ibge_municipalities_path: Path | None,
) -> dict[str, Any]:
    features = geojson.get("features", [])
    if not features:
        raise ValueError("GeoJSON municipal sem geometrias")

    tse_by_name = {
        _normalized_name(str(row["municipality_name"])): row for row in municipalities
    }
    ibge_by_code: dict[str, str] = {}
    if ibge_municipalities_path is not None:
        payload = json.loads(ibge_municipalities_path.read_text(encoding="utf-8"))
        rows = payload.get("municipalities", payload) if isinstance(payload, dict) else payload
        ibge_by_code = {
            str(row.get("id") or row.get("ibge_code") or row.get("codarea")): str(
                row.get("nome") or row.get("name") or row.get("municipality_name")
            )
            for row in rows
        }

    matched_codes: set[str] = set()
    for feature in features:
        properties = feature.setdefault("properties", {})
        ibge_code = str(
            properties.get("ibge_code")
            or properties.get("codarea")
            or properties.get("CD_MUN")
            or ""
        )
        municipality_name = str(
            properties.get("municipality_name")
            or properties.get("NM_MUN")
            or properties.get("nome")
            or properties.get("name")
            or ibge_by_code.get(ibge_code)
            or ""
        )
        municipality = tse_by_name.get(_normalized_name(municipality_name))
        if municipality is None:
            raise ValueError(
                f"Município do GeoJSON sem correspondência na Gold: "
                f"ibge={ibge_code or 'ausente'} nome={municipality_name or 'ausente'}"
            )
        municipality_code = str(municipality["municipality_code"])
        properties.clear()
        properties.update(
            {
                "ibge_code": ibge_code,
                "municipality_code": municipality_code,
                "municipality_name": municipality["municipality_name"],
            }
        )
        matched_codes.add(municipality_code)

    expected_codes = {str(row["municipality_code"]) for row in municipalities}
    missing = expected_codes - matched_codes
    if missing or len(features) != len(expected_codes):
        raise ValueError(
            "Cobertura geográfica incompleta: "
            f"{len(matched_codes)}/{len(expected_codes)} municípios; "
            f"ausentes={sorted(missing)}"
        )
    return geojson


def _profile_summary(frame: pl.DataFrame) -> list[dict[str, Any]]:
    return (
        frame.filter(pl.col("dimension") == "gender")
        .group_by("municipality_code", "municipality_name")
        .agg(
            pl.col("registered_electors").sum(),
            pl.col("biometric_electors").sum(),
            pl.col("electors_with_disability").sum(),
            pl.col("electors_with_social_name").sum(),
        )
        .with_columns(
            (pl.col("biometric_electors") / pl.col("registered_electors")).alias(
                "biometric_rate"
            ),
            (
                pl.col("electors_with_disability")
                / pl.col("registered_electors")
            ).alias("disability_rate"),
            (
                pl.col("electors_with_social_name")
                / pl.col("registered_electors")
            ).alias("social_name_rate"),
        )
        .sort("municipality_name")
        .to_dicts()
    )


def _zone_summary(frame: pl.DataFrame) -> list[dict[str, Any]]:
    sums = [
        "eligible_voters",
        "turnout",
        "abstentions",
        "valid_votes",
        "blank_votes",
        "null_votes",
        "separately_annulled_votes",
        "total_votes",
    ]
    return (
        frame.group_by(
            "municipality_code", "municipality_name", "zone", "office_code", "office"
        )
        .agg(*(pl.col(column).sum().alias(column) for column in sums))
        .with_columns(
            (pl.col("turnout") / pl.col("eligible_voters")).alias("turnout_rate"),
            (pl.col("abstentions") / pl.col("eligible_voters")).alias(
                "abstention_rate"
            ),
            (pl.col("blank_votes") / pl.col("total_votes")).alias("blank_vote_rate"),
            (pl.col("null_votes") / pl.col("total_votes")).alias("null_vote_rate"),
        )
        .sort("municipality_name", "zone", "office_code")
        .to_dicts()
    )


def build_dashboard(
    *,
    gold_dir: Path,
    source_dir: Path,
    output_dir: Path,
    geojson_path: Path | None,
    ibge_municipalities_path: Path | None = None,
) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(source_dir, output_dir)

    overview = _rows(_parquet(gold_dir, "election_overview"))
    municipality_summary = _rows(_parquet(gold_dir, "municipality_summary"))
    profile_frame = pl.read_parquet(_parquet(gold_dir, "electorate_profile"))
    profiles = profile_frame.to_dicts()
    metadata = _rows(_parquet(gold_dir, "metadata"))[0]
    section_summary_path = _parquet(gold_dir, "section_summary")
    section_results_path = _parquet(gold_dir, "section_results")

    municipalities = (
        pl.read_parquet(
            _parquet(gold_dir, "municipality_summary"),
            columns=["municipality_code", "municipality_name"],
        )
        .unique()
        .sort("municipality_name")
        .to_dicts()
    )
    section_count = (
        pl.scan_parquet(section_summary_path)
        .select(pl.col("section_id").n_unique())
        .collect()
        .item()
    )

    candidates = pl.read_parquet(
        _parquet(gold_dir, "candidate_results"),
        columns=[
            "office_code",
            "office",
            "municipality_code",
            "municipality_name",
            "ballot_number",
            "ballot_name",
            "candidate_id",
            "result_type",
            "candidate_name",
            "party_abbreviation",
            "candidacy_status",
            "round_result_status",
            "votes",
        ],
    )
    candidate_files: list[dict[str, Any]] = []
    for office in candidates.select("office_code", "office").unique().sort(
        "office_code"
    ).iter_rows(named=True):
        office_code = int(office["office_code"])
        file = f"assets/data/candidates/{office_code}.json"
        candidate_files.append({**office, "file": file})
        _write_json(
            output_dir / file,
            _compact_frame(candidates.filter(pl.col("office_code") == office_code)),
        )

    section_catalog = (
        pl.read_parquet(
            section_summary_path,
            columns=[
                "municipality_code",
                "municipality_name",
                "zone",
                "section",
                "voting_place_name",
            ],
        )
        .unique()
        .sort("municipality_name", "zone", "section")
    )
    section_index: list[dict[str, Any]] = []
    for municipality_key, municipality_frame in section_catalog.partition_by(
        "municipality_code", as_dict=True, maintain_order=True
    ).items():
        municipality_code = str(municipality_key[0])
        zones = []
        for zone_key, zone_frame in municipality_frame.partition_by(
            "zone", as_dict=True, maintain_order=True
        ).items():
            zones.append(
                {
                    "zone": str(zone_key[0]),
                    "sections": zone_frame.select(
                        "section", "voting_place_name"
                    ).to_dicts(),
                }
            )
        section_index.append(
            {
                "municipality_code": municipality_code,
                "municipality_name": municipality_frame["municipality_name"][0],
                "zones": zones,
            }
        )

    summary_columns = [
        "municipality_code",
        "municipality_name",
        "zone",
        "section",
        "office_code",
        "office",
        "voting_place_name",
        "voting_place_address",
        "section_installed",
        "section_annulled",
        "eligible_voters",
        "turnout",
        "abstentions",
        "valid_votes",
        "blank_votes",
        "null_votes",
        "separately_annulled_votes",
        "total_votes",
        "turnout_rate",
        "abstention_rate",
        "blank_vote_rate",
        "null_vote_rate",
    ]
    result_columns = [
        "municipality_code",
        "zone",
        "section",
        "office",
        "ballot_number",
        "ballot_name",
        "candidate_name",
        "party_abbreviation",
        "result_type",
        "votes",
    ]
    summaries = pl.read_parquet(section_summary_path, columns=summary_columns)
    results = pl.read_parquet(section_results_path, columns=result_columns)
    summary_partitions = summaries.partition_by(
        ["municipality_code", "zone"], as_dict=True
    )
    result_partitions = results.partition_by(
        ["municipality_code", "zone"], as_dict=True
    )
    for key, summary_frame in summary_partitions.items():
        municipality_code, zone = (str(value) for value in key)
        result_frame = result_partitions.get(key)
        if result_frame is None:
            raise ValueError(f"Resultados ausentes para {municipality_code}/{zone}")
        _write_json(
            output_dir
            / "assets"
            / "data"
            / "sections"
            / f"{municipality_code}-{zone}.json",
            {
                "municipality_name": section_catalog.filter(
                    pl.col("municipality_code") == municipality_code
                )["municipality_name"][0],
                "summaries": _compact_frame(
                    summary_frame.drop("municipality_code", "zone")
                ),
                "results": _compact_frame(
                    result_frame.drop("municipality_code", "zone")
                ),
            },
        )

    geojson: dict[str, Any] | None = None
    if geojson_path is not None and geojson_path.exists():
        geojson = json.loads(geojson_path.read_text(encoding="utf-8"))
        geojson = _prepare_geojson(
            geojson, municipalities, ibge_municipalities_path
        )
    atlas = {
        "metadata": metadata,
        "overview": overview,
        "municipalities": municipalities,
        "municipality_summary": municipality_summary,
        "electorate_profile": profiles,
        "electorate_municipality_summary": _profile_summary(profile_frame),
        "candidate_files": candidate_files,
        "section_index": section_index,
        "zone_summary": _zone_summary(summaries),
        "section_count": section_count,
        "geojson": geojson,
    }
    _write_json(output_dir / "assets" / "data" / "atlas.json", atlas)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gold-dir",
        type=Path,
        help="Override local para desenvolvimento; por padrão usa a Gold publicada.",
    )
    parser.add_argument(
        "--cache-dir", type=Path, default=Path(".dashboard-cache") / "gold"
    )
    parser.add_argument("--source-dir", type=Path, default=Path("dashboard"))
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    parser.add_argument("--geojson", type=Path)
    parser.add_argument("--ibge-municipalities", type=Path)
    args = parser.parse_args()
    gold_dir = args.gold_dir or fetch_published_gold(args.cache_dir)
    build_dashboard(
        gold_dir=gold_dir,
        source_dir=args.source_dir,
        output_dir=args.output_dir,
        geojson_path=args.geojson,
        ibge_municipalities_path=args.ibge_municipalities,
    )


if __name__ == "__main__":
    main()
