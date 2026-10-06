from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from tse_urna.parsing.log_parser import parse_file


def build_bronze(
    *,
    log_path: Path,
    output_path: Path,
    quarantine_path: Path,
    metadata: dict[str, str | int],
) -> tuple[int, int]:
    records: list[dict] = []
    rejected: list[dict] = []

    for line_number, raw_line, event in parse_file(log_path):
        if event is None:
            if raw_line.strip():
                rejected.append(
                    {
                        **metadata,
                        "source_log": str(log_path),
                        "line_number": line_number,
                        "raw_content": raw_line,
                        "error_reason": "unparsed_line",
                    }
                )
            continue

        records.append(
            {
                **metadata,
                "source_log": str(log_path),
                "line_number": event.line_number,
                "event_timestamp": event.event_timestamp,
                "severity": event.severity,
                "ue_id": event.ue_id,
                "application": event.application,
                "message_raw": event.message_raw,
                "mac": event.mac,
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    quarantine_path.parent.mkdir(parents=True, exist_ok=True)

    if records:
        pl.DataFrame(records).write_parquet(output_path, compression="zstd")
    else:
        pl.DataFrame(
            schema={
                "source_log": pl.String,
                "line_number": pl.Int64,
                "event_timestamp": pl.Datetime,
                "severity": pl.String,
                "ue_id": pl.String,
                "application": pl.String,
                "message_raw": pl.String,
                "mac": pl.String,
            }
        ).write_parquet(output_path, compression="zstd")

    if rejected:
        with quarantine_path.open("a", encoding="utf-8") as fh:
            for row in rejected:
                fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    return len(records), len(rejected)
