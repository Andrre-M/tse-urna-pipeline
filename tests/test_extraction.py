import zipfile
from pathlib import Path

import py7zr

from tse_urna.extraction.logjez import extract_logjez


def test_extraction_is_checkpointed_atomically(tmp_path: Path):
    log = tmp_path / "logd.dat"
    log.write_text("linha\n", encoding="utf-8")
    archive = tmp_path / "sample.logjez"
    with py7zr.SevenZipFile(archive, "w") as output:
        output.write(log, arcname="logd.dat")

    destination = tmp_path / "extracted"
    first = extract_logjez(archive, destination)
    archive.unlink()
    second = extract_logjez(archive, destination)

    assert len(first) == 1
    assert second == first
    assert (destination / "_SUCCESS").read_text(encoding="ascii") == "ok\n"


def test_extracts_current_zip_based_jez(tmp_path: Path):
    log = tmp_path / "logd.dat"
    log.write_text("linha\n", encoding="utf-8")
    archive = tmp_path / "sample-log.jez"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        output.write(log, arcname="logd.dat")

    logs = extract_logjez(archive, tmp_path / "current")

    assert len(logs) == 1
    assert logs[0].read_text(encoding="utf-8") == "linha\n"


def test_extraction_retries_transient_windows_directory_lock(
    tmp_path: Path, monkeypatch
):
    log = tmp_path / "logd.dat"
    log.write_text("linha\n", encoding="utf-8")
    archive = tmp_path / "sample-log.jez"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        output.write(log, arcname="logd.dat")

    original_replace = Path.replace
    calls = 0

    def transient_failure(path: Path, target: Path):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise PermissionError("arquivo temporariamente bloqueado")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", transient_failure)

    logs = extract_logjez(archive, tmp_path / "current")

    assert calls == 2
    assert len(logs) == 1
