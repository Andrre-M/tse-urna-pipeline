from tse_urna.discovery.aux_parser import parse_aux_json
from tse_urna.models import SectionRef


def section():
    return SectionRef.build(
        year=2026, pleito=3220, uf="ce", municipality=13897, zone=3, section=444
    )


def test_parses_2024_plus_arq_shape():
    payload = {
        "hashes": [
            {
                "hash": "abc123",
                "arq": [
                    {"nm": "o03220-1389700030444.logjez"},
                    {"nm": "o03220-1389700030444.bu"},
                ],
            }
        ]
    }
    result = parse_aux_json(
        payload, base_url="https://resultados.tse.jus.br/oficial", section=section()
    )
    assert len(result) == 1
    assert result[0].filename.endswith(".logjez")
    assert "/abc123/" in result[0].source_url


def test_parses_legacy_nmarq_shape():
    payload = {
        "hashes": [
            {
                "hash": "legacyhash",
                "nmarq": [
                    {"nm": "o00406-0605000020824.logjez"},
                    {"nm": "o00406-0605000020824.bu"},
                ],
            }
        ]
    }
    result = parse_aux_json(
        payload, base_url="https://resultados.tse.jus.br/oficial", section=section()
    )
    assert [item.filename for item in result] == ["o00406-0605000020824.logjez"]


def test_parses_current_typed_log_jez_shape():
    payload = {
        "hashes": [
            {
                "hash": "currenthash",
                "arq": [
                    {"nm": "o03220ce1300500300082-bu.dat", "tp": "bu"},
                    {"nm": "o03220ce1300500300082-log.jez", "tp": "log"},
                ],
            }
        ]
    }
    result = parse_aux_json(
        payload, base_url="https://resultados.tse.jus.br/oficial", section=section()
    )
    assert [item.filename for item in result] == ["o03220ce1300500300082-log.jez"]


def test_skips_hash_zero():
    payload = {
        "hashes": [
            {"hash": "0", "arq": [{"nm": "ignored.logjez"}]},
        ]
    }
    assert parse_aux_json(
        payload, base_url="https://resultados.tse.jus.br/oficial", section=section()
    ) == []
