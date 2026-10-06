from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

import polars as pl

from tse_urna.parsing.log_parser import parse_file


@dataclass(frozen=True, slots=True)
class BronzeBatchResult:
    output_dir: str
    output_files: tuple[str, ...]
    valid_rows: int
    rejected_rows: int


def _write_part(records: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    pl.DataFrame(records).write_parquet(temporary, compression="zstd", statistics=True)
    temporary.replace(output_path)


def _empty_frame(metadata: dict[str, str | int]) -> pl.DataFrame:
    schema: dict[str, pl.DataType] = {
        key: pl.Int64 if isinstance(value, int) else pl.String for key, value in metadata.items()
    }
    schema.update(
        {
            "source_log": pl.String,
            "line_number": pl.Int64,
            "event_timestamp": pl.Datetime,
            "severity": pl.String,
            "ue_id": pl.String,
            "application": pl.String,
            "message_raw": pl.String,
            "mac": pl.String,
        }
    )
    return pl.DataFrame(schema=schema)


def build_bronze_batch(
    *,
    logs: list[tuple[Path, dict[str, str | int]]],
    output_dir: Path,
    quarantine_path: Path,
    target_rows: int,
) -> BronzeBatchResult:
    """Escreve um lote reiniciável em partes limitadas por quantidade de linhas."""
    if not logs:
        raise ValueError("o lote Bronze precisa de ao menos um log")
    if target_rows <= 0:
        raise ValueError("target_rows deve ser maior que zero")

    success_marker = output_dir / "_SUCCESS.json"
    if success_marker.exists():
        payload = json.loads(success_marker.read_text(encoding="utf-8"))
        payload["output_files"] = tuple(payload["output_files"])
        return BronzeBatchResult(**payload)

    staging = output_dir.with_name(f".{output_dir.name}.tmp-{uuid4().hex}")
    quarantine_path.parent.mkdir(parents=True, exist_ok=True)
    quarantine_temp = quarantine_path.with_suffix(quarantine_path.suffix + ".tmp")
    records: list[dict] = []
    output_names: list[str] = []
    valid_rows = 0
    rejected_rows = 0

    try:
        staging.mkdir(parents=True, exist_ok=False)
        with quarantine_temp.open("w", encoding="utf-8") as quarantine:
            for log_path, metadata in logs:
                for line_number, raw_line, event in parse_file(log_path):
                    if event is None:
                        if raw_line.strip():
                            rejected_rows += 1
                            quarantine.write(
                                json.dumps(
                                    {
                                        **metadata,
                                        "source_log": str(log_path),
                                        "line_number": line_number,
                                        "raw_content": raw_line,
                                        "error_reason": "unparsed_line",
                                    },
                                    ensure_ascii=False,
                                    default=str,
                                )
                                + "\n"
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
                    valid_rows += 1
                    if len(records) >= target_rows:
                        name = f"part-{len(output_names):05d}.parquet"
                        _write_part(records, staging / name)
                        output_names.append(name)
                        records = []

        if records:
            name = f"part-{len(output_names):05d}.parquet"
            _write_part(records, staging / name)
            output_names.append(name)
        elif not output_names:
            name = "part-00000.parquet"
            _empty_frame(logs[0][1]).write_parquet(staging / name, compression="zstd")
            output_names.append(name)

        result = BronzeBatchResult(
            output_dir=str(output_dir),
            output_files=tuple(str(output_dir / name) for name in output_names),
            valid_rows=valid_rows,
            rejected_rows=rejected_rows,
        )
        (staging / "_SUCCESS.json").write_text(
            json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        quarantine_temp.replace(quarantine_path)
        if output_dir.exists():
            shutil.rmtree(output_dir)
        staging.replace(output_dir)
        return result
    finally:
        quarantine_temp.unlink(missing_ok=True)
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def build_bronze(
    *,
    log_path: Path,
    output_path: Path,
    quarantine_path: Path,
    metadata: dict[str, str | int],
) -> tuple[int, int]:
    """Compatibilidade para a API por arquivo usada nas versões 0.1/0.2."""
    result = build_bronze_batch(
        logs=[(log_path, metadata)],
        output_dir=output_path.parent / f"batch={output_path.stem}",
        quarantine_path=quarantine_path,
        target_rows=250_000,
    )
    generated = Path(result.output_files[0])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(generated, output_path)
    return result.valid_rows, result.rejected_rows
