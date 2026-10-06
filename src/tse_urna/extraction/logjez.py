from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

import py7zr


class ExtractionError(RuntimeError):
    pass


def _validate_members(names: list[str]) -> None:
    for name in names:
        member = Path(name)
        if member.is_absolute() or ".." in member.parts:
            raise ExtractionError(f"Caminho inseguro no arquivo: {name}")


def _extract_archive(
    archive_path: Path, destination: Path, depth: int = 0, max_depth: int = 4
) -> list[Path]:
    if depth > max_depth:
        raise ExtractionError(f"Limite de arquivos .jez aninhados excedido em {archive_path}")
    destination.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="urna-log-") as tmp:
        tmpdir = Path(tmp)
        try:
            with py7zr.SevenZipFile(archive_path, mode="r") as archive:
                _validate_members(archive.getnames())
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
            logs.extend(_extract_archive(nested, nested_out, depth + 1, max_depth))

        return logs


def extract_logjez(source: Path, destination: Path) -> list[Path]:
    success_marker = destination / "_SUCCESS"
    if success_marker.exists():
        logs = sorted(destination.rglob("logd.dat"))
        if logs:
            return logs

    staging = destination.with_name(f".{destination.name}.tmp-{uuid4().hex}")
    try:
        logs = _extract_archive(source, staging)
        if not logs:
            raise ExtractionError(f"Nenhum logd.dat encontrado em {source}")
        (staging / "_SUCCESS").write_text("ok\n", encoding="ascii")
        if destination.exists():
            shutil.rmtree(destination)
        staging.replace(destination)
        return sorted(destination.rglob("logd.dat"))
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
