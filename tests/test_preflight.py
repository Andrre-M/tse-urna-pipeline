from pathlib import Path
from shutil import _ntuple_diskusage

from tse_urna import preflight


def test_preflight_accepts_writable_paths_with_enough_space(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(
        preflight.shutil,
        "disk_usage",
        lambda _: _ntuple_diskusage(total=100, used=20, free=80),
    )

    checks = preflight.run_preflight(
        data_dir=tmp_path / "data",
        metadata_dir=tmp_path / "metadata",
        min_free_bytes=40,
    )

    assert all(check.ok for check in checks)
    assert not list(tmp_path.rglob(".preflight-*"))


def test_preflight_fails_when_disk_space_is_below_minimum(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(
        preflight.shutil,
        "disk_usage",
        lambda _: _ntuple_diskusage(total=100, used=70, free=30),
    )

    checks = preflight.run_preflight(
        data_dir=tmp_path / "data",
        metadata_dir=tmp_path / "metadata",
        min_free_bytes=40,
    )

    disk_check = next(check for check in checks if check.name == "disk_space")
    assert not disk_check.ok
    assert disk_check.status == "error"


def test_preflight_warns_but_accepts_space_for_limited_batch(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(
        preflight.shutil,
        "disk_usage",
        lambda _: _ntuple_diskusage(total=100, used=70, free=30),
    )

    checks = preflight.run_preflight(
        data_dir=tmp_path / "data",
        metadata_dir=tmp_path / "metadata",
        min_free_bytes=40,
        limit=10,
        full_workload_items=100,
    )

    disk_check = next(check for check in checks if check.name == "disk_space")
    assert disk_check.ok
    assert disk_check.status == "warning"
    assert "lote de até 10 item(ns)" in disk_check.detail


def test_preflight_fails_when_space_is_below_limited_batch_estimate(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(
        preflight.shutil,
        "disk_usage",
        lambda _: _ntuple_diskusage(total=100, used=98, free=2),
    )

    checks = preflight.run_preflight(
        data_dir=tmp_path / "data",
        metadata_dir=tmp_path / "metadata",
        min_free_bytes=40,
        limit=10,
        full_workload_items=100,
    )

    disk_check = next(check for check in checks if check.name == "disk_space")
    assert not disk_check.ok
    assert disk_check.status == "error"
