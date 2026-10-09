from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

import polars as pl

from tse_urna.filesystem import promote_directory


def _groups_by_size(paths: list[Path], target_bytes: int) -> list[list[Path]]:
    groups: list[list[Path]] = []
    current: list[Path] = []
    current_size = 0
    for path in paths:
        size = path.stat().st_size
        if current and current_size + size > target_bytes:
            groups.append(current)
            current = []
            current_size = 0
        current.append(path)
        current_size += size
    if current:
        groups.append(current)
    return groups


def compact_bronze_partition(
    *, input_dir: Path, output_dir: Path, target_size_mb: int = 256
) -> list[Path]:
    if target_size_mb <= 0:
        raise ValueError("target_size_mb deve ser maior que zero")
    sources = sorted(input_dir.glob("batch=*/part-*.parquet"))
    if not sources:
        raise FileNotFoundError(f"Nenhum Parquet Bronze encontrado em {input_dir}")

    fingerprint = [[str(path.relative_to(input_dir)), path.stat().st_size] for path in sources]
    success_marker = output_dir / "_SUCCESS.json"
    if success_marker.exists():
        payload = json.loads(success_marker.read_text(encoding="utf-8"))
        if payload.get("sources") == fingerprint:
            return [output_dir / name for name in payload["outputs"]]

    staging = output_dir.with_name(f".{output_dir.name}.tmp-{uuid4().hex}")
    try:
        staging.mkdir(parents=True, exist_ok=False)
        groups = _groups_by_size(sources, target_size_mb * 1024 * 1024)
        names: list[str] = []
        for index, group in enumerate(groups):
            name = f"part-{index:05d}.parquet"
            pl.scan_parquet([str(path) for path in group]).sink_parquet(
                staging / name, compression="zstd", mkdir=True
            )
            names.append(name)
        (staging / "_SUCCESS.json").write_text(
            json.dumps({"sources": fingerprint, "outputs": names}, indent=2),
            encoding="utf-8",
        )
        if output_dir.exists():
            shutil.rmtree(output_dir)
        promote_directory(staging, output_dir)
        return [output_dir / name for name in names]
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
