from __future__ import annotations

from typing import Any

from tse_urna.discovery.urls import urn_file_url
from tse_urna.models import DiscoveredFile, SectionRef


def _filenames(hash_entry: dict[str, Any]) -> list[str]:
    # Até 2022 e alguns espelhos: nmarq. Há dumps com strings e com {"nm": ...}.
    source = hash_entry.get("nmarq") if "nmarq" in hash_entry else hash_entry.get("arq", [])

    result: list[str] = []
    for item in source or []:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict) and item.get("nm"):
            result.append(str(item["nm"]))
    return result


def parse_aux_json(
    payload: dict[str, Any], *, base_url: str, section: SectionRef
) -> list[DiscoveredFile]:
    discovered: list[DiscoveredFile] = []

    for entry in payload.get("hashes", []):
        source_hash = str(entry.get("hash", ""))
        if not source_hash or source_hash == "0":
            continue

        for filename in _filenames(entry):
            if not filename.lower().endswith(".logjez"):
                continue
            discovered.append(
                DiscoveredFile(
                    section=section,
                    source_hash=source_hash,
                    filename=filename,
                    source_url=urn_file_url(
                        base_url=base_url,
                        section=section,
                        source_hash=source_hash,
                        filename=filename,
                    ),
                )
            )

    return discovered
