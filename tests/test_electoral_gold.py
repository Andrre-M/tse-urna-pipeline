import polars as pl

from tse_urna.transformation.electoral_gold import (
    _aggregate_electorate_profiles,
    _candidates,
    _electorate_profiles,
    _result_type,
    _summary,
)


def test_summary_keeps_turnout_separate_from_vote_total():
    source = pl.DataFrame(
        {
            "office": ["Senador"],
            "eligible_voters": [100],
            "turnout": [80],
            "abstentions": [20],
            "nominal_votes": [120],
            "party_votes": [0],
            "blank_votes": [20],
            "null_votes": [20],
            "separately_annulled_votes": [0],
        }
    ).lazy()

    result = _summary(source, ["office"]).collect().row(0, named=True)

    assert result["turnout_rate"] == 0.8
    assert result["total_votes"] == 160
    assert result["valid_votes"] == 120
    assert result["blank_vote_rate"] == 0.125


def test_electorate_profile_preserves_age_gender_cross_tab():
    source = pl.DataFrame(
        {
            "election_year": [2026, 2026, 2026],
            "uf": ["CE", "CE", "CE"],
            "municipality_code": ["13897", "13897", "13897"],
            "municipality_name": ["FORTALEZA", "FORTALEZA", "FORTALEZA"],
            "gender": ["FEMININO", "MASCULINO", "FEMININO"],
            "age_band": ["16 anos", "16 anos", "17 anos"],
            "education": ["ENSINO MÉDIO", "ENSINO MÉDIO", "ENSINO MÉDIO"],
            "registered_electors": [10, 8, 5],
            "biometric_electors": [9, 7, 5],
            "electors_with_disability": [0, 1, 0],
            "electors_with_social_name": [1, 0, 0],
        }
    ).lazy()

    result = _aggregate_electorate_profiles(source).collect()
    joint = result.filter(pl.col("dimension") == "age_gender")

    assert set(result["dimension"]) == {
        "age_band",
        "age_gender",
        "education",
        "gender",
    }
    assert joint["registered_electors"].sum() == 23
    assert set(joint["subcategory"]) == {"FEMININO", "MASCULINO"}

    by_age = (
        joint.group_by("category")
        .agg(pl.col("registered_electors").sum())
        .sort("category")
    )
    expected_age = (
        result.filter(pl.col("dimension") == "age_band")
        .select("category", "registered_electors")
        .sort("category")
    )
    assert by_age.equals(expected_age)

    by_gender = (
        joint.group_by("subcategory")
        .agg(pl.col("registered_electors").sum())
        .rename({"subcategory": "category"})
        .sort("category")
    )
    expected_gender = (
        result.filter(pl.col("dimension") == "gender")
        .select("category", "registered_electors")
        .sort("category")
    )
    assert by_gender.equals(expected_gender)


def test_candidates_matches_office_without_case_sensitivity(tmp_path):
    source = tmp_path / "candidates.csv"
    pl.DataFrame(
        {
            "SG_UF": ["BR", "BR"],
            "DS_CARGO": ["PRESIDENTE", "VICE-PRESIDENTE"],
            "SQ_CANDIDATO": [1, 2],
            "NR_CANDIDATO": [10, 10],
            "NM_URNA_CANDIDATO": ["CANDIDATA", "VICE"],
            "NM_CANDIDATO": ["CANDIDATA COMPLETA", "VICE COMPLETO"],
            "SG_PARTIDO": ["ABC", "ABC"],
            "NM_PARTIDO": ["PARTIDO ABC", "PARTIDO ABC"],
            "DS_SITUACAO_CANDIDATURA": ["APTO", "APTO"],
            "DS_SIT_TOT_TURNO": ["NÃO ELEITO", "NÃO ELEITO"],
        }
    ).write_csv(source, separator=";")

    result = _candidates(source, office_filter="Presidente").collect()

    assert result.height == 1
    assert result["candidate_id"].item() == 1
    assert result["party_abbreviation"].item() == "ABC"


def test_electorate_profile_reads_utf8_source(tmp_path):
    source = tmp_path / "electorate.csv"
    pl.DataFrame(
        {
            "SG_UF": ["CE"],
            "CD_MUNICIPIO": ["13897"],
            "NM_MUNICIPIO": ["SÃO GONÇALO DO AMARANTE"],
            "DS_GENERO": ["FEMININO"],
            "DS_FAIXA_ETARIA": ["100 anos ou mais"],
            "DS_GRAU_ESCOLARIDADE": ["SUPERIOR COMPLETO"],
            "QT_ELEITORES": ["1"],
            "QT_ELEITORES_BIOMETRIA": ["1"],
            "QT_ELEITORES_DEFICIENCIA": ["0"],
            "QT_ELEITORES_NOME_SOCIAL": ["0"],
        }
    ).write_csv(source, separator=";")

    result = _electorate_profiles(source).collect()

    assert result.filter(pl.col("dimension") == "age_band")["category"].item() == (
        "100 anos ou mais"
    )
    assert result["municipality_name"].first() == "SÃO GONÇALO DO AMARANTE"


def test_result_type_separates_party_votes_from_candidates():
    result = (
        pl.DataFrame(
            {
                "ballot_number": [13, 13, 95, 96],
                "candidate_id": [123, -3, None, None],
            }
        )
        .with_columns(_result_type())
        .get_column("result_type")
        .to_list()
    )

    assert result == ["candidate", "party", "blank", "null"]
