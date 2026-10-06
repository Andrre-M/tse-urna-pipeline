from __future__ import annotations

from tse_urna.models import SectionRef


def pleito_token(pleito: str | int) -> str:
    return f"p{int(pleito):06d}"


def election_slug(year: int) -> str:
    return f"ele{year}"


def state_config_filename(*, uf: str, pleito: str | int) -> str:
    uf = uf.lower()
    return f"{uf}-{pleito_token(pleito)}-cs.json"


def state_config_url(*, base_url: str, year: int, pleito: str | int, uf: str) -> str:
    uf = uf.lower()
    filename = state_config_filename(uf=uf, pleito=pleito)
    return (
        f"{base_url.rstrip('/')}/{election_slug(year)}/arquivo-urna/{pleito}/"
        f"config/{uf}/{filename}"
    )


def section_aux_filename(section: SectionRef) -> str:
    return (
        f"{pleito_token(section.pleito)}-{section.uf}-m{section.municipality}-"
        f"z{section.zone}-s{section.section}-aux.json"
    )


def section_base_url(*, base_url: str, section: SectionRef) -> str:
    return (
        f"{base_url.rstrip('/')}/{election_slug(section.year)}/arquivo-urna/"
        f"{section.pleito}/dados/{section.uf}/{section.municipality}/"
        f"{section.zone}/{section.section}"
    )


def section_aux_url(*, base_url: str, section: SectionRef) -> str:
    return f"{section_base_url(base_url=base_url, section=section)}/{section_aux_filename(section)}"


def urn_file_url(
    *, base_url: str, section: SectionRef, source_hash: str, filename: str
) -> str:
    return f"{section_base_url(base_url=base_url, section=section)}/{source_hash}/{filename}"
