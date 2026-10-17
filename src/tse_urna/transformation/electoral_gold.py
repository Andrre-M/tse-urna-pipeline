from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, fields
from pathlib import Path
from uuid import uuid4

import polars as pl

from tse_urna.filesystem import promote_directory

ELECTORAL_GOLD_SCHEMA_VERSION = 2
ELECTORAL_TABLES = (
    "election_overview",
    "municipality_summary",
    "electorate_profile",
    "candidate_results",
    "section_summary",
    "section_results",
    "metadata",
)


@dataclass(frozen=True, slots=True)
class ElectoralSourceFiles:
    state_votes: Path
    presidential_votes: Path
    state_section_detail: Path
    presidential_section_detail: Path
    electorate_profile: Path
    state_candidates: Path
    presidential_candidates: Path


@dataclass(frozen=True, slots=True)
class ElectoralGoldResult:
    output_files: tuple[str, ...]
    row_counts: dict[str, int]
    municipalities: int
    sections: int
    registered_electors: int


def _scan_csv(path: Path) -> pl.LazyFrame:
    if not path.exists():
        raise FileNotFoundError(f"Fonte eleitoral não encontrada: {path}")
    return pl.scan_csv(
        path,
        separator=";",
        quote_char='"',
        encoding="utf8",
        infer_schema=False,
        null_values=["#NULO#", "#NE#", "-1"],
        truncate_ragged_lines=False,
    )


def _text_code(column: str, width: int) -> pl.Expr:
    return pl.col(column).str.strip_chars().str.zfill(width)


def _integer(column: str) -> pl.Expr:
    return pl.col(column).cast(pl.Int64, strict=False).fill_null(0)


def _base_dimensions() -> list[pl.Expr]:
    return [
        pl.lit(2026, dtype=pl.Int32).alias("election_year"),
        pl.lit(1, dtype=pl.Int8).alias("round"),
        pl.lit("CE").alias("uf"),
        _text_code("CD_MUNICIPIO", 5).alias("municipality_code"),
        pl.col("NM_MUNICIPIO").str.strip_chars().alias("municipality_name"),
        _text_code("NR_ZONA", 4).alias("zone"),
        _text_code("NR_SECAO", 4).alias("section"),
    ]


def _details(source: Path, *, office_filter: str | None = None) -> pl.LazyFrame:
    frame = _scan_csv(source).filter(
        (pl.col("NR_TURNO") == "1") & (pl.col("SG_UF") == "CE")
    )
    if office_filter is not None:
        frame = frame.filter(pl.col("DS_CARGO") == office_filter)
    return frame.select(
        *_base_dimensions(),
        pl.col("CD_ELEICAO").cast(pl.Int32, strict=False).alias("election_code"),
        pl.col("DS_ELEICAO").str.strip_chars().alias("election_name"),
        pl.col("DT_ELEICAO").str.strip_chars().alias("election_date"),
        pl.col("CD_CARGO").cast(pl.Int16, strict=False).alias("office_code"),
        pl.col("DS_CARGO").str.strip_chars().alias("office"),
        _text_code("NR_LOCAL_VOTACAO", 4).alias("voting_place_code"),
        pl.col("NM_LOCAL_VOTACAO").str.strip_chars().alias("voting_place_name"),
        pl.col("DS_LOCAL_VOTACAO_ENDERECO")
        .str.strip_chars()
        .alias("voting_place_address"),
        pl.col("ST_SECAO_INSTALADA").str.strip_chars().alias("section_installed"),
        pl.col("ST_SECAO_ANULADA").str.strip_chars().alias("section_annulled"),
        _integer("QT_APTOS").alias("eligible_voters"),
        _integer("QT_COMPARECIMENTO").alias("turnout"),
        _integer("QT_ABSTENCOES").alias("abstentions"),
        _integer("QT_VOTOS_NOMINAIS").alias("nominal_votes"),
        _integer("QT_VOTOS_LEGENDA").alias("party_votes"),
        _integer("QT_VOTOS_BRANCOS").alias("blank_votes"),
        _integer("QT_VOTOS_NULOS").alias("null_votes"),
        _integer("QT_VOTOS_ANULADOS_APU_SEP").alias("separately_annulled_votes"),
    ).with_columns(
        pl.concat_str(
            "uf", "municipality_code", "zone", "section", separator="-"
        ).alias("section_id"),
        (pl.col("nominal_votes") + pl.col("party_votes")).alias("valid_votes"),
        (
            pl.col("nominal_votes")
            + pl.col("party_votes")
            + pl.col("blank_votes")
            + pl.col("null_votes")
            + pl.col("separately_annulled_votes")
        ).alias("total_votes"),
        pl.when(pl.col("eligible_voters") > 0)
        .then(pl.col("turnout") / pl.col("eligible_voters"))
        .otherwise(None)
        .alias("turnout_rate"),
        pl.when(pl.col("eligible_voters") > 0)
        .then(pl.col("abstentions") / pl.col("eligible_voters"))
        .otherwise(None)
        .alias("abstention_rate"),
    ).with_columns(
        pl.when(pl.col("total_votes") > 0)
        .then(pl.col("blank_votes") / pl.col("total_votes"))
        .otherwise(None)
        .alias("blank_vote_rate"),
        pl.when(pl.col("total_votes") > 0)
        .then(pl.col("null_votes") / pl.col("total_votes"))
        .otherwise(None)
        .alias("null_vote_rate"),
    )


def _summary(frame: pl.LazyFrame, group_columns: list[str]) -> pl.LazyFrame:
    sums = [
        "eligible_voters",
        "turnout",
        "abstentions",
        "nominal_votes",
        "party_votes",
        "blank_votes",
        "null_votes",
        "separately_annulled_votes",
    ]
    return (
        frame.group_by(*group_columns)
        .agg(*(pl.col(column).sum().alias(column) for column in sums))
        .with_columns(
            (pl.col("nominal_votes") + pl.col("party_votes")).alias("valid_votes"),
            (
                pl.col("nominal_votes")
                + pl.col("party_votes")
                + pl.col("blank_votes")
                + pl.col("null_votes")
                + pl.col("separately_annulled_votes")
            ).alias("total_votes"),
            pl.when(pl.col("eligible_voters") > 0)
            .then(pl.col("turnout") / pl.col("eligible_voters"))
            .otherwise(None)
            .alias("turnout_rate"),
            pl.when(pl.col("eligible_voters") > 0)
            .then(pl.col("abstentions") / pl.col("eligible_voters"))
            .otherwise(None)
            .alias("abstention_rate"),
        )
        .with_columns(
            pl.when(pl.col("total_votes") > 0)
            .then(pl.col("blank_votes") / pl.col("total_votes"))
            .otherwise(None)
            .alias("blank_vote_rate"),
            pl.when(pl.col("total_votes") > 0)
            .then(pl.col("null_votes") / pl.col("total_votes"))
            .otherwise(None)
            .alias("null_vote_rate"),
        )
    )


def _candidates(source: Path, *, office_filter: str | None = None) -> pl.LazyFrame:
    frame = _scan_csv(source).filter(pl.col("SG_UF").is_in(["CE", "BR"]))
    if office_filter is not None:
        frame = frame.filter(
            pl.col("DS_CARGO").str.to_uppercase() == office_filter.upper()
        )
    return frame.select(
        pl.col("SQ_CANDIDATO").cast(pl.Int64, strict=False).alias("candidate_id"),
        pl.col("NR_CANDIDATO").cast(pl.Int32, strict=False).alias("candidate_number"),
        pl.col("NM_URNA_CANDIDATO").str.strip_chars().alias("candidate_name"),
        pl.col("NM_CANDIDATO").str.strip_chars().alias("candidate_full_name"),
        pl.col("SG_PARTIDO").str.strip_chars().alias("party_abbreviation"),
        pl.col("NM_PARTIDO").str.strip_chars().alias("party_name"),
        pl.col("DS_SITUACAO_CANDIDATURA")
        .str.strip_chars()
        .alias("candidacy_status"),
        pl.col("DS_SIT_TOT_TURNO").str.strip_chars().alias("round_result_status"),
    ).filter(pl.col("candidate_id").is_not_null())


def _result_type() -> pl.Expr:
    return (
        pl.when(pl.col("ballot_number") == 95)
        .then(pl.lit("blank"))
        .when(pl.col("ballot_number") == 96)
        .then(pl.lit("null"))
        .when(pl.col("candidate_id") > 0)
        .then(pl.lit("candidate"))
        .otherwise(pl.lit("party"))
        .alias("result_type")
    )


def _votes(source: Path, *, office_filter: str | None = None) -> pl.LazyFrame:
    frame = _scan_csv(source).filter(
        (pl.col("NR_TURNO") == "1") & (pl.col("SG_UF") == "CE")
    )
    if office_filter is not None:
        frame = frame.filter(pl.col("DS_CARGO") == office_filter)
    return frame.select(
        *_base_dimensions(),
        pl.col("CD_CARGO").cast(pl.Int16, strict=False).alias("office_code"),
        pl.col("DS_CARGO").str.strip_chars().alias("office"),
        pl.col("NR_VOTAVEL").cast(pl.Int32, strict=False).alias("ballot_number"),
        pl.col("NM_VOTAVEL").str.strip_chars().alias("ballot_name"),
        pl.col("SQ_CANDIDATO").cast(pl.Int64, strict=False).alias("candidate_id"),
        _integer("QT_VOTOS").alias("votes"),
    ).with_columns(
        pl.concat_str(
            "uf", "municipality_code", "zone", "section", separator="-"
        ).alias("section_id"),
        _result_type(),
    )


def _aggregate_electorate_profiles(base: pl.LazyFrame) -> pl.LazyFrame:
    dimensions = {
        "gender": "gender",
        "age_band": "age_band",
        "education": "education",
    }
    frames: list[pl.LazyFrame] = []
    for dimension, column in dimensions.items():
        frames.append(
            base.group_by(
                "election_year", "uf", "municipality_code", "municipality_name", column
            )
            .agg(
                pl.col("registered_electors").sum(),
                pl.col("biometric_electors").sum(),
                pl.col("electors_with_disability").sum(),
                pl.col("electors_with_social_name").sum(),
            )
            .rename({column: "category"})
            .with_columns(
                pl.lit(None, dtype=pl.String).alias("subcategory"),
                pl.lit(dimension).alias("dimension"),
            )
        )
    frames.append(
        base.group_by(
            "election_year",
            "uf",
            "municipality_code",
            "municipality_name",
            "age_band",
            "gender",
        )
        .agg(
            pl.col("registered_electors").sum(),
            pl.col("biometric_electors").sum(),
            pl.col("electors_with_disability").sum(),
            pl.col("electors_with_social_name").sum(),
        )
        .rename({"age_band": "category", "gender": "subcategory"})
        .with_columns(pl.lit("age_gender").alias("dimension"))
    )
    return pl.concat(frames, how="diagonal_relaxed").select(
        "election_year",
        "uf",
        "municipality_code",
        "municipality_name",
        "dimension",
        "category",
        "subcategory",
        "registered_electors",
        "biometric_electors",
        "electors_with_disability",
        "electors_with_social_name",
    )


def _electorate_profiles(source: Path) -> pl.LazyFrame:
    if not source.exists():
        raise FileNotFoundError(f"Fonte eleitoral não encontrada: {source}")
    columns = [
        "SG_UF",
        "CD_MUNICIPIO",
        "NM_MUNICIPIO",
        "DS_GENERO",
        "DS_FAIXA_ETARIA",
        "DS_GRAU_ESCOLARIDADE",
        "QT_ELEITORES",
        "QT_ELEITORES_BIOMETRIA",
        "QT_ELEITORES_DEFICIENCIA",
        "QT_ELEITORES_NOME_SOCIAL",
    ]
    source_frame = pl.read_csv(
        source,
        columns=columns,
        separator=";",
        quote_char='"',
        encoding="utf8",
        infer_schema=False,
        null_values=["#NULO#", "#NE#", "-1"],
        truncate_ragged_lines=False,
        low_memory=True,
    ).lazy()
    base = source_frame.filter(pl.col("SG_UF") == "CE").select(
        pl.lit(2026, dtype=pl.Int32).alias("election_year"),
        pl.lit("CE").alias("uf"),
        _text_code("CD_MUNICIPIO", 5).alias("municipality_code"),
        pl.col("NM_MUNICIPIO").str.strip_chars().alias("municipality_name"),
        pl.col("DS_GENERO").str.strip_chars().alias("gender"),
        pl.col("DS_FAIXA_ETARIA").str.strip_chars().alias("age_band"),
        pl.col("DS_GRAU_ESCOLARIDADE").str.strip_chars().alias("education"),
        _integer("QT_ELEITORES").alias("registered_electors"),
        _integer("QT_ELEITORES_BIOMETRIA").alias("biometric_electors"),
        _integer("QT_ELEITORES_DEFICIENCIA").alias("electors_with_disability"),
        _integer("QT_ELEITORES_NOME_SOCIAL").alias("electors_with_social_name"),
    )
    return _aggregate_electorate_profiles(base)


def _write_frame(frame: pl.LazyFrame, destination: Path) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.sink_parquet(destination, compression="zstd", statistics=True, mkdir=True)
    return int(pl.scan_parquet(destination).select(pl.len()).collect().item())


def build_electoral_gold(
    *,
    sources: ElectoralSourceFiles,
    output_dir: Path,
) -> ElectoralGoldResult:
    """Constrói a Gold eleitoral oficial do primeiro turno do Ceará em 2026."""
    state_details = _details(sources.state_section_detail)
    presidential_details = _details(
        sources.presidential_section_detail, office_filter="Presidente"
    )
    details = pl.concat([state_details, presidential_details], how="diagonal_relaxed")

    state_votes = _votes(sources.state_votes)
    presidential_votes = _votes(sources.presidential_votes, office_filter="Presidente")
    votes = pl.concat([state_votes, presidential_votes], how="diagonal_relaxed")

    candidates = pl.concat(
        [
            _candidates(sources.state_candidates),
            _candidates(sources.presidential_candidates, office_filter="Presidente"),
        ],
        how="diagonal_relaxed",
    ).unique("candidate_id", keep="first")

    overview_keys = [
        "election_year",
        "round",
        "uf",
        "election_code",
        "election_name",
        "election_date",
        "office_code",
        "office",
    ]
    municipality_keys = overview_keys + ["municipality_code", "municipality_name"]
    election_overview = _summary(details, overview_keys).sort("office_code")
    municipality_summary = _summary(details, municipality_keys).sort(
        "municipality_name", "office_code"
    )

    result_dimensions = [
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
    candidate_results = (
        votes.filter(pl.col("result_type").is_in(["candidate", "party"]))
        .group_by(*result_dimensions)
        .agg(pl.col("votes").sum())
        .join(candidates, on="candidate_id", how="left")
        .sort(
            "office_code",
            "municipality_name",
            "votes",
            descending=[False, False, True],
        )
    )
    section_results = votes.join(candidates, on="candidate_id", how="left").sort(
        "municipality_name", "zone", "section", "office_code", "votes",
        descending=[False, False, False, False, True],
    )
    section_summary = details.sort(
        "municipality_name", "zone", "section", "office_code"
    )
    electorate_profile = _electorate_profiles(sources.electorate_profile).sort(
        "municipality_name", "dimension", "category"
    )

    temporary = output_dir.with_name(f".{output_dir.name}.tmp-{uuid4().hex}")
    shutil.rmtree(temporary, ignore_errors=True)
    row_counts: dict[str, int] = {}
    try:
        frames = {
            "election_overview": election_overview,
            "municipality_summary": municipality_summary,
            "electorate_profile": electorate_profile,
            "candidate_results": candidate_results,
            "section_summary": section_summary,
            "section_results": section_results,
        }
        for table, frame in frames.items():
            row_counts[table] = _write_frame(
                frame, temporary / table / "part-00000.parquet"
            )

        overview = pl.read_parquet(
            temporary / "election_overview" / "part-00000.parquet"
        )
        municipality_frame = pl.scan_parquet(
            temporary / "municipality_summary" / "part-00000.parquet"
        )
        section_frame = pl.scan_parquet(
            temporary / "section_summary" / "part-00000.parquet"
        )
        electorate = pl.scan_parquet(
            temporary / "electorate_profile" / "part-00000.parquet"
        )
        municipalities = int(
            municipality_frame.select(pl.col("municipality_code").n_unique())
            .collect()
            .item()
        )
        sections = int(
            section_frame.select(pl.col("section_id").n_unique()).collect().item()
        )
        registered_electors = int(
            electorate.filter(pl.col("dimension") == "gender")
            .select(pl.col("registered_electors").sum())
            .collect()
            .item()
            or 0
        )
        metadata = pl.DataFrame(
            {
                "schema_version": [ELECTORAL_GOLD_SCHEMA_VERSION],
                "election_year": [2026],
                "round": [1],
                "uf": ["CE"],
                "scope": ["Resultados e eleitorado oficiais do primeiro turno"],
                "source_authority": ["Tribunal Superior Eleitoral"],
                "registered_electors_profile": [registered_electors],
                "presidential_eligible_voters": [
                    int(
                        overview.filter(pl.col("office") == "Presidente")[
                            "eligible_voters"
                        ].item()
                    )
                ],
                "limitations": [
                    "O perfil cadastral e os aptos por cargo têm universos oficiais "
                    "distintos. Logs de urna não são votos e não alimentam estes resultados."
                ],
                "source_files": [
                    json.dumps(
                        [getattr(sources, field.name).name for field in fields(sources)],
                        ensure_ascii=False,
                    )
                ],
            }
        )
        metadata_path = temporary / "metadata" / "part-00000.parquet"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata.write_parquet(metadata_path, compression="zstd", statistics=True)
        row_counts["metadata"] = 1

        backup = output_dir.with_name(f".{output_dir.name}.backup-{uuid4().hex}")
        if output_dir.exists():
            output_dir.replace(backup)
        try:
            promote_directory(temporary, output_dir)
        except Exception:
            if backup.exists() and not output_dir.exists():
                backup.replace(output_dir)
            raise
        finally:
            shutil.rmtree(backup, ignore_errors=True)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)

    output_files = tuple(
        str(output_dir / table / "part-00000.parquet") for table in ELECTORAL_TABLES
    )
    return ElectoralGoldResult(
        output_files=output_files,
        row_counts=row_counts,
        municipalities=municipalities,
        sections=sections,
        registered_electors=registered_electors,
    )
