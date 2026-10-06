from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import httpx

from tse_urna.ingestion.manifest import Manifest


class AsyncRateLimiter:
    """Rate limiter simples e global para requisições concorrentes."""

    def __init__(self, requests_per_second: float):
        self.interval = 1.0 / requests_per_second
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def wait(self) -> None:
        loop = asyncio.get_running_loop()
        async with self._lock:
            now = loop.time()
            wait_for = self.interval - (now - self._last_call)
            if wait_for > 0:
                await asyncio.sleep(wait_for)
            self._last_call = loop.time()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def raw_path(data_dir: Path, row) -> Path:
    return (
        data_dir
        / "raw"
        / f"year={row['election_year']}"
        / f"pleito={row['pleito']}"
        / f"uf={row['uf'].upper()}"
        / f"municipality={row['municipality']}"
        / f"zone={row['zone']}"
        / f"section={row['section']}"
        / row["source_hash"]
        / row["filename"]
    )


async def _download_one(
    *,
    client: httpx.AsyncClient,
    limiter: AsyncRateLimiter,
    semaphore: asyncio.Semaphore,
    manifest: Manifest,
    row,
    data_dir: Path,
    retries: int = 4,
) -> None:
    destination = raw_path(data_dir, row)
    destination.parent.mkdir(parents=True, exist_ok=True)

    # Se o arquivo já existir, valida e usa como checkpoint.
    if destination.exists() and destination.stat().st_size > 0:
        digest = sha256_file(destination)
        manifest.mark_downloaded(
            row["id"],
            local_path=str(destination),
            file_size=destination.stat().st_size,
            sha256_local=digest,
            http_status=200,
        )
        return

    temp_path = destination.with_suffix(destination.suffix + ".part")
    last_error: Exception | None = None
    last_status: int | None = None

    async with semaphore:
        for attempt in range(retries):
            try:
                await limiter.wait()
                async with client.stream("GET", row["source_url"]) as response:
                    last_status = response.status_code
                    response.raise_for_status()
                    with temp_path.open("wb") as fh:
                        async for chunk in response.aiter_bytes(1024 * 1024):
                            fh.write(chunk)

                temp_path.replace(destination)
                digest = sha256_file(destination)
                manifest.mark_downloaded(
                    row["id"],
                    local_path=str(destination),
                    file_size=destination.stat().st_size,
                    sha256_local=digest,
                    http_status=last_status or 200,
                )
                return
            except (httpx.HTTPError, OSError) as exc:
                last_error = exc
                if temp_path.exists():
                    temp_path.unlink(missing_ok=True)
                if attempt + 1 < retries:
                    await asyncio.sleep(min(2**attempt, 8))

    manifest.mark_download_failed(
        row["id"], error=str(last_error or "download failed"), http_status=last_status
    )


async def download_pending(
    *,
    manifest: Manifest,
    data_dir: Path,
    concurrency: int,
    requests_per_second: float,
    timeout_seconds: float,
    limit: int | None = None,
) -> int:
    rows = manifest.pending_downloads(limit=limit)
    if not rows:
        return 0

    limiter = AsyncRateLimiter(requests_per_second)
    semaphore = asyncio.Semaphore(concurrency)
    timeout = httpx.Timeout(timeout_seconds)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        await asyncio.gather(
            *[
                _download_one(
                    client=client,
                    limiter=limiter,
                    semaphore=semaphore,
                    manifest=manifest,
                    row=row,
                    data_dir=data_dir,
                )
                for row in rows
            ]
        )
    return len(rows)
