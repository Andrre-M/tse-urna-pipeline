from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    base_url: str = os.getenv("TSE_BASE_URL", "https://resultados.tse.jus.br/oficial")
    requests_per_second: float = float(os.getenv("TSE_REQUESTS_PER_SECOND", "20"))
    concurrency: int = int(os.getenv("TSE_CONCURRENCY", "8"))
    timeout_seconds: float = float(os.getenv("TSE_TIMEOUT_SECONDS", "30"))
    retries: int = int(os.getenv("TSE_RETRIES", "4"))
    bronze_batch_files: int = int(os.getenv("TSE_BRONZE_BATCH_FILES", "100"))
    bronze_target_rows: int = int(os.getenv("TSE_BRONZE_TARGET_ROWS", "250000"))
    data_dir: Path = field(
        default_factory=lambda: Path(os.getenv("TSE_DATA_DIR", "data"))
    )
    metadata_dir: Path = field(
        default_factory=lambda: Path(os.getenv("TSE_METADATA_DIR", "metadata"))
    )

    @property
    def manifest_path(self) -> Path:
        return self.metadata_dir / "manifest.db"


settings = Settings()
