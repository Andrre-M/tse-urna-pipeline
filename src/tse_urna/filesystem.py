from __future__ import annotations

import time
from pathlib import Path


def promote_directory(staging: Path, destination: Path, retries: int = 5) -> None:
    """Promove um diretório, tolerando bloqueios transitórios do Windows."""
    for attempt in range(retries):
        try:
            staging.replace(destination)
            return
        except PermissionError:
            if attempt + 1 == retries:
                raise
            time.sleep(0.05 * 2**attempt)
