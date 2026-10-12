from pathlib import Path

from tse_urna.config import Settings


def test_settings_accept_external_storage_paths(monkeypatch):
    monkeypatch.setenv("TSE_DATA_DIR", r"D:\tse-urna-pipeline\data")
    monkeypatch.setenv("TSE_METADATA_DIR", r"D:\tse-urna-pipeline\metadata")

    configured = Settings()

    assert configured.data_dir == Path(r"D:\tse-urna-pipeline\data")
    assert configured.metadata_dir == Path(r"D:\tse-urna-pipeline\metadata")
