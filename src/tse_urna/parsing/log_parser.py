from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from tse_urna.models import LogEvent

FALLBACK_PATTERN = re.compile(
    r"^(?P<date>\d{2}/\d{2}/\d{4})\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<severity>\S+)\s+"
    r"(?P<ue_id>\S+)\s+"
    r"(?P<application>\S+)\s+"
    r"(?P<message>.*?)\s+"
    r"(?P<mac>[0-9A-Fa-f]{8,})$"
)


def _build_event(fields: list[str], line_number: int) -> LogEvent:
    date, time, severity, ue_id, application, message, mac = fields
    timestamp = datetime.strptime(f"{date} {time}", "%d/%m/%Y %H:%M:%S")
    return LogEvent(
        event_timestamp=timestamp,
        severity=severity.strip(),
        ue_id=ue_id.strip(),
        application=application.strip(),
        message_raw=message.strip(),
        mac=mac.strip(),
        line_number=line_number,
    )


def parse_line(line: str, line_number: int) -> LogEvent | None:
    raw = line.rstrip("\r\n")
    if not raw.strip():
        return None

    fields = raw.split("\t")
    if len(fields) == 7:
        try:
            return _build_event(fields, line_number)
        except ValueError:
            return None

    # Fallback útil para fixtures/copias de documentação onde TAB virou espaço.
    match = FALLBACK_PATTERN.match(raw)
    if not match:
        return None
    groups = match.groupdict()
    try:
        return _build_event(
            [
                groups["date"],
                groups["time"],
                groups["severity"],
                groups["ue_id"],
                groups["application"],
                groups["message"],
                groups["mac"],
            ],
            line_number,
        )
    except ValueError:
        return None


def parse_file(path: Path):
    # latin-1 preserva bytes sem interromper o pipeline; logs reais podem variar por versão.
    with path.open("r", encoding="latin-1", errors="replace") as fh:
        for line_number, line in enumerate(fh, start=1):
            yield line_number, line.rstrip("\r\n"), parse_line(line, line_number)
