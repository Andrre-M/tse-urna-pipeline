from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import py7zr


class ExtractionError(RuntimeError):
    pass


def _extract_archive(archive_path: Path, destination: Path, depth: int = 0) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="urna-log-") as tmp:
        tmpdir = Path(tmp)
        try:
            with py7zr.SevenZipFile(archive_path, mode="r") as archive:
                archive.extractall(path=tmpdir)
        except Exception as exc:  # py7zr exposes multiple exception types by format/version
            raise ExtractionError(f"Falha ao extrair {archive_path}: {exc}") from exc

        logs: list[Path] = []
        for log_file in tmpdir.rglob("logd.dat"):
            target_dir = destination / f"depth={depth}" / log_file.parent.name
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / "logd.dat"
            shutil.copy2(log_file, target)
            logs.append(target)

        # Logs de contingência podem estar arquivados em .jez internos.
        for nested in tmpdir.rglob("*.jez"):
            nested_out = destination / "nested" / nested.stem
            logs.extend(_extract_archive(nested, nested_out, depth + 1))

        return logs


def extract_logjez(source: Path, destination: Path) -> list[Path]:
    logs = _extract_archive(source, destination)
    if not logs:
        raise ExtractionError(f"Nenhum logd.dat encontrado em {source}")
    return logs
