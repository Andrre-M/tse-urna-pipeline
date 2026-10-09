from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PreflightCheck:
    name: str
    ok: bool
    detail: str


def _check_writable_directory(name: str, path: Path) -> PreflightCheck:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path, prefix=".preflight-", delete=True):
            pass
    except OSError as exc:
        return PreflightCheck(name=name, ok=False, detail=f"{path.resolve()}: {exc}")
    return PreflightCheck(name=name, ok=True, detail=str(path.resolve()))


def run_preflight(
    *, data_dir: Path, metadata_dir: Path, min_free_bytes: int
) -> list[PreflightCheck]:
    checks = [
        _check_writable_directory("data_path", data_dir),
        _check_writable_directory("metadata_path", metadata_dir),
    ]

    if checks[0].ok:
        try:
            free_bytes = shutil.disk_usage(data_dir).free
            checks.append(
                PreflightCheck(
                    name="disk_space",
                    ok=free_bytes >= min_free_bytes,
                    detail=(
                        f"{free_bytes / (1024**3):.1f} GiB livres em {data_dir.resolve()} "
                        f"(mínimo: {min_free_bytes / (1024**3):.1f} GiB)"
                    ),
                )
            )
        except OSError as exc:
            checks.append(PreflightCheck(name="disk_space", ok=False, detail=str(exc)))
    else:
        checks.append(
            PreflightCheck(
                name="disk_space",
                ok=False,
                detail="não foi possível medir o volume do diretório de dados",
            )
        )

    return checks
