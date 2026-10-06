from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class QualityResult:
    ok: bool
    valid_rows: int
    rejected_rows: int
    rejection_rate: float


def basic_quality(*, parquet_path: Path, valid_rows: int, rejected_rows: int) -> QualityResult:
    if not parquet_path.exists():
        return QualityResult(False, valid_rows, rejected_rows, 1.0)
    total = valid_rows + rejected_rows
    rejection_rate = rejected_rows / total if total else 0.0
    return QualityResult(
        ok=valid_rows > 0 and rejection_rate < 0.05,
        valid_rows=valid_rows,
        rejected_rows=rejected_rows,
        rejection_rate=rejection_rate,
    )
