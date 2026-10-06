from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from tse_urna.discovery.aux_parser import parse_aux_json
from tse_urna.ingestion.downloader import AsyncRateLimiter
from tse_urna.ingestion.manifest import Manifest
from tse_urna.models import SectionRef


async def _discover_one(
    *,
    client: httpx.AsyncClient,
    limiter: AsyncRateLimiter,
    semaphore: asyncio.Semaphore,
    manifest: Manifest,
    row,
    base_url: str,
    retries: int = 4,
) -> None:
    last_error: Exception | None = None
    last_status: int | None = None

    async with semaphore:
        for attempt in range(retries):
            try:
                await limiter.wait()
                response = await client.get(row["aux_url"])
                last_status = response.status_code
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
                    row["id"], files_found=len(discovered), http_status=last_status
                )
                return
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                last_error = exc
                if attempt + 1 < retries:
                    await asyncio.sleep(min(2**attempt, 8))

    manifest.mark_section_discovery_failed(
        row["id"], error=str(last_error or "discovery failed"), http_status=last_status
    )


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
    limit: int | None = None,
) -> int:
    rows = manifest.pending_sections(year=year, pleito=pleito, uf=uf, limit=limit)
    if not rows:
        return 0

    limiter = AsyncRateLimiter(requests_per_second)
    semaphore = asyncio.Semaphore(concurrency)
    timeout = httpx.Timeout(timeout_seconds)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        await asyncio.gather(
            *[
                _discover_one(
                    client=client,
                    limiter=limiter,
                    semaphore=semaphore,
                    manifest=manifest,
                    row=row,
                    base_url=base_url,
                )
                for row in rows
            ]
        )
    return len(rows)


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
