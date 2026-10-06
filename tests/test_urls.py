from tse_urna.discovery.urls import (
    pleito_token,
    section_aux_filename,
    section_aux_url,
    state_config_url,
)
from tse_urna.models import SectionRef


def test_pleito_token_zero_pads_to_six_digits():
    assert pleito_token(406) == "p000406"
    assert pleito_token(3220) == "p003220"


def test_section_ref_normalizes_codes():
    ref = SectionRef.build(
        year=2026, pleito=3220, uf="CE", municipality=13897, zone=3, section=444
    )
    assert ref.uf == "ce"
    assert ref.municipality == "13897"
    assert ref.zone == "0003"
    assert ref.section == "0444"


def test_2026_section_aux_url():
    ref = SectionRef.build(
        year=2026, pleito=3220, uf="CE", municipality=13897, zone=3, section=444
    )
    assert section_aux_filename(ref) == "p003220-ce-m13897-z0003-s0444-aux.json"
    assert section_aux_url(base_url="https://resultados.tse.jus.br/oficial", section=ref) == (
        "https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/"
        "dados/ce/13897/0003/0444/p003220-ce-m13897-z0003-s0444-aux.json"
    )


def test_state_config_url():
    assert state_config_url(
        base_url="https://resultados.tse.jus.br/oficial", year=2026, pleito=3220, uf="CE"
    ) == (
        "https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/"
        "config/ce/ce-p003220-cs.json"
    )
