from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SectionRef:
    year: int
    pleito: str
    uf: str
    municipality: str
    zone: str
    section: str

    @classmethod
    def build(
        cls,
        *,
        year: int,
        pleito: str | int,
        uf: str,
        municipality: str | int,
        zone: str | int,
        section: str | int,
    ) -> "SectionRef":
        return cls(
            year=int(year),
            pleito=str(pleito),
            uf=uf.lower(),
            municipality=str(municipality).zfill(5),
            zone=str(zone).zfill(4),
            section=str(section).zfill(4),
        )


@dataclass(frozen=True, slots=True)
class DiscoveredFile:
    section: SectionRef
    source_hash: str
    filename: str
    source_url: str


@dataclass(frozen=True, slots=True)
class LogEvent:
    event_timestamp: datetime
    severity: str
    ue_id: str
    application: str
    message_raw: str
    mac: str
    line_number: int
