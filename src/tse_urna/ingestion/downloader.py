from __future__ import annotations

import asyncio
import hashlib
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx

from tse_urna.ingestion.manifest import Manifest


class AsyncRateLimiter:
    """Rate limiter simples e global para requisições concorrentes."""

    def __init__(self, requests_per_second: float):
        if requests_per_second <= 0:
            raise ValueError("requests_per_second deve ser maior que zero")
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
    suffix = Path(row["filename"]).suffix.lower() or ".bin"
    return (
        data_dir
        / "raw"
        / f"y={row['election_year']}"
        / f"p={row['pleito']}"
        / f"u={row['uf'].upper()}"
        / f"m={row['municipality']}"
        / f"z={row['zone']}"
        / f"s={row['section']}"
        / f"file-{int(row['id']):08d}{suffix}"
    )


def is_retryable_status(status_code: int) -> bool:
    return status_code in {408, 425, 429} or 500 <= status_code < 600


def retry_delay(response: httpx.Response | None, attempt: int) -> float:
    fallback = min(2**attempt, 8)
    if response is None:
        return fallback
    value = response.headers.get("Retry-After")
    if not value:
        return fallback
    try:
        return min(max(float(value), 0.0), 60.0)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
            now = parsedate_to_datetime(response.headers.get("Date", value))
            return min(max((retry_at - now).total_seconds(), 0.0), 60.0)
        except (TypeError, ValueError, OverflowError):
            return fallback


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
    temp_path = destination.with_suffix(destination.suffix + f".{row['id']}.part")
    last_error: Exception | None = None
    last_status: int | None = None

    for attempt in range(retries):
        response: httpx.Response | None = None
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Arquivo movido antes de uma interrupção é um checkpoint recuperável.
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
            async with semaphore:
                await limiter.wait()
                async with client.stream("GET", row["source_url"]) as response:
                    last_status = response.status_code
                    response.raise_for_status()
                    expected_size = response.headers.get("Content-Length")
                    downloaded_size = 0
                    with temp_path.open("wb") as fh:
                        async for chunk in response.aiter_bytes(1024 * 1024):
                            fh.write(chunk)
                            downloaded_size += len(chunk)

            if downloaded_size == 0:
                raise OSError("resposta vazia")
            if expected_size is not None and downloaded_size != int(expected_size):
                raise OSError(
                    f"download incompleto: esperado={expected_size}, recebido={downloaded_size}"
                )

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
        except (httpx.HTTPError, OSError, ValueError) as exc:
            last_error = exc
            temp_path.unlink(missing_ok=True)
            status = response.status_code if response is not None else None
            should_retry = status is None or is_retryable_status(status)
            if attempt + 1 < retries and should_retry:
                await asyncio.sleep(retry_delay(response, attempt))
                continue
            break

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
    retries: int = 4,
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
                    retries=retries,
                )
                for row in rows
            ]
        )
    return len(rows)
