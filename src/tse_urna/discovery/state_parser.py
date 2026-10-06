from __future__ import annotations

from typing import Any

from tse_urna.models import SectionRef


class StateConfigError(ValueError):
    pass


def parse_state_config(
    payload: dict[str, Any], *, year: int, pleito: str | int, uf: str
) -> list[SectionRef]:
    """Converte o catálogo de uma UF do TSE em referências de seções.

    O arquivo ``<uf>-pXXXXXX-cs.json`` contém a hierarquia
    município -> zona -> seção. A função tolera blocos de abrangência
    adicionais e considera apenas o bloco da UF solicitada quando o código
    estiver presente.
    """
    target_uf = uf.lower()
    sections: list[SectionRef] = []
    blocks = payload.get("abr", [])

    if not isinstance(blocks, list) or not blocks:
        raise StateConfigError("Configuração da UF não contém 'abr'.")

    matched_block = False
    for block in blocks:
        if not isinstance(block, dict):
            continue

        block_uf = str(block.get("cd", "")).lower()
        municipalities = block.get("mu", [])
        if block_uf and block_uf != target_uf:
            continue
        if not isinstance(municipalities, list):
            continue

        matched_block = True
        for municipality in municipalities:
            if not isinstance(municipality, dict) or "cd" not in municipality:
                continue
            municipality_code = municipality["cd"]

            for zone in municipality.get("zon", []):
                if not isinstance(zone, dict) or "cd" not in zone:
                    continue
                zone_code = zone["cd"]

                for section in zone.get("sec", []):
                    if isinstance(section, dict):
                        section_code = section.get("ns")
                    else:
                        section_code = section
                    if section_code is None:
                        continue

                    sections.append(
                        SectionRef.build(
                            year=year,
                            pleito=pleito,
                            uf=target_uf,
                            municipality=municipality_code,
                            zone=zone_code,
                            section=section_code,
                        )
                    )

    if not matched_block:
        raise StateConfigError(f"Nenhum bloco de abrangência encontrado para UF {uf.upper()}.")
    if not sections:
        raise StateConfigError(f"Nenhuma seção encontrada para UF {uf.upper()}.")

    # O catálogo não deveria duplicar seções, mas a deduplicação torna o
    # estágio determinístico caso o formato de origem traga repetições.
    unique: dict[tuple[str, str, str], SectionRef] = {}
    for ref in sections:
        unique[(ref.municipality, ref.zone, ref.section)] = ref
    return list(unique.values())
