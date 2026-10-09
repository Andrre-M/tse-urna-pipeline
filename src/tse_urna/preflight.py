from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True, slots=True)
class PreflightCheck:
    name: str
    status: Literal["ok", "warning", "error"]
    detail: str

    @property
    def ok(self) -> bool:
        return self.status != "error"


def _check_writable_directory(name: str, path: Path) -> PreflightCheck:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path, prefix=".preflight-", delete=True):
            pass
    except OSError as exc:
        return PreflightCheck(
            name=name, status="error", detail=f"{path.resolve()}: {exc}"
        )
    return PreflightCheck(name=name, status="ok", detail=str(path.resolve()))


def run_preflight(
    *,
    data_dir: Path,
    metadata_dir: Path,
    min_free_bytes: int,
    limit: int | None = None,
    full_workload_items: int = 25_650,
) -> list[PreflightCheck]:
    checks = [
        _check_writable_directory("data_path", data_dir),
        _check_writable_directory("metadata_path", metadata_dir),
    ]

    if checks[0].ok:
        try:
            free_bytes = shutil.disk_usage(data_dir).free
            required_bytes = min_free_bytes
            if limit is not None:
                required_bytes = min(
                    min_free_bytes,
                    max(1, min_free_bytes * limit // full_workload_items),
                )

            if free_bytes < required_bytes:
                status = "error"
            elif limit is not None and free_bytes < min_free_bytes:
                status = "warning"
            else:
                status = "ok"

            scope = (
                "carga completa"
                if limit is None
                else f"lote de até {limit} item(ns)"
            )
            checks.append(
                PreflightCheck(
                    name="disk_space",
                    status=status,
                    detail=(
                        f"{free_bytes / (1024**3):.1f} GiB livres em {data_dir.resolve()} "
                        f"(mínimo estimado para {scope}: "
                        f"{required_bytes / (1024**3):.1f} GiB; "
                        f"carga completa: {min_free_bytes / (1024**3):.1f} GiB)"
                    ),
                )
            )
        except OSError as exc:
            checks.append(
                PreflightCheck(name="disk_space", status="error", detail=str(exc))
            )
    else:
        checks.append(
            PreflightCheck(
                name="disk_space",
                status="error",
                detail="não foi possível medir o volume do diretório de dados",
            )
        )

    return checks
