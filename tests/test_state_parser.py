import pytest

from tse_urna.discovery.state_parser import StateConfigError, parse_state_config


def sample_payload():
    return {
        "abr": [
            {
                "cd": "ce",
                "mu": [
                    {
                        "cd": "13897",
                        "nm": "FORTALEZA",
                        "zon": [
                            {"cd": "0003", "sec": [{"ns": "0444"}, {"ns": "0445"}]},
                            {"cd": "0004", "sec": [{"ns": "0001"}]},
                        ],
                    },
                    {
                        "cd": "13730",
                        "nm": "MARACANAU",
                        "zon": [{"cd": "0104", "sec": [{"ns": "0002"}]}],
                    },
                ],
            }
        ]
    }


def test_parse_state_config_expands_full_hierarchy():
    sections = parse_state_config(sample_payload(), year=2026, pleito=3220, uf="CE")
    assert len(sections) == 4
    assert sections[0].municipality == "13897"
    assert sections[0].zone == "0003"
    assert sections[0].section == "0444"
    assert sections[-1].municipality == "13730"
    assert sections[-1].zone == "0104"


def test_parse_state_config_rejects_empty_payload():
    with pytest.raises(StateConfigError):
        parse_state_config({}, year=2026, pleito=3220, uf="CE")
