from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from tse_urna.discovery.aux_parser import parse_aux_json
from tse_urna.ingestion.downloader import AsyncRateLimiter, is_retryable_status, retry_delay
from tse_urna.ingestion.manifest import Manifest
from tse_urna.models import SectionRef, StageStats


async def _discover_one(
    *,
    client: httpx.AsyncClient,
    limiter: AsyncRateLimiter,
    semaphore: asyncio.Semaphore,
    manifest: Manifest,
    row,
    base_url: str,
    retries: int = 4,
    refresh_run_id: int | None = None,
) -> bool:
    last_error: Exception | None = None
    last_status: int | None = None

    for attempt in range(retries):
        response: httpx.Response | None = None
        try:
            async with semaphore:
                await limiter.wait()
                response = await client.get(row["aux_url"])
            last_status = response.status_code
            if response.status_code == 404:
                manifest.mark_section_discovered(
                    row["id"],
                    files_found=0,
                    http_status=response.status_code,
                    refresh_run_id=refresh_run_id,
                )
                return True
            response.raise_for_status()
            payload = response.json()

            section = SectionRef.build(
                year=row["election_year"],
                pleito=row["pleito"],
                uf=row["uf"],
                municipality=row["municipality"],
                zone=row["zone"],
                section=row["section"],
            )
            discovered = parse_aux_json(payload, base_url=base_url, section=section)
            manifest.upsert_discovered(discovered)
            manifest.mark_section_discovered(
                row["id"],
                files_found=len(discovered),
                http_status=last_status,
                refresh_run_id=refresh_run_id,
            )
            return True
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            last_error = exc
            status = response.status_code if response is not None else None
            should_retry = status is None or is_retryable_status(status)
            if attempt + 1 < retries and should_retry:
                await asyncio.sleep(retry_delay(response, attempt))
                continue
            break

    manifest.mark_section_discovery_failed(
        row["id"], error=str(last_error or "discovery failed"), http_status=last_status
    )
    return False


async def discover_pending_sections(
    *,
    manifest: Manifest,
    base_url: str,
    year: int,
    pleito: str | int,
    uf: str,
    concurrency: int,
    requests_per_second: float,
    timeout_seconds: float,
    retries: int = 4,
    limit: int | None = None,
    refresh_run_id: int | None = None,
) -> StageStats:
    rows = manifest.pending_sections(
        year=year,
        pleito=pleito,
        uf=uf,
        limit=limit,
        refresh_run_id=refresh_run_id,
    )
    if not rows:
        return StageStats(processed=0, succeeded=0)

    limiter = AsyncRateLimiter(requests_per_second)
    semaphore = asyncio.Semaphore(concurrency)
    timeout = httpx.Timeout(timeout_seconds)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        results = await asyncio.gather(
            *[
                _discover_one(
                    client=client,
                    limiter=limiter,
                    semaphore=semaphore,
                    manifest=manifest,
                    row=row,
                    base_url=base_url,
                    retries=retries,
                    refresh_run_id=refresh_run_id,
                )
                for row in rows
            ]
        )
    return StageStats(processed=len(rows), succeeded=sum(results))


def state_config_cache_path(
    metadata_dir: Path, *, year: int, pleito: str | int, uf: str
) -> Path:
    return (
        metadata_dir
        / "discovery"
        / f"year={year}"
        / f"pleito={pleito}"
        / f"uf={uf.upper()}"
        / "state-config.json"
    )
