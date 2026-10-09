import asyncio
from pathlib import Path

import httpx

from tse_urna.discovery.uf import _discover_one
from tse_urna.discovery.urls import section_aux_url
from tse_urna.ingestion.downloader import AsyncRateLimiter
from tse_urna.ingestion.manifest import Manifest
from tse_urna.models import SectionRef


def test_discovery_treats_missing_aux_as_refreshable_empty_section(tmp_path: Path):
    manifest = Manifest(tmp_path / "manifest.db")
    ref = SectionRef.build(
        year=2026, pleito=3220, uf="CE", municipality=13005, zone=30, section=447
    )
    manifest.upsert_sections(
        [(ref, section_aux_url(base_url="https://example.test", section=ref))]
    )
    row = manifest.pending_sections(year=2026, pleito=3220, uf="CE")[0]
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404)

    async def run() -> bool:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await _discover_one(
                client=client,
                limiter=AsyncRateLimiter(10_000),
                semaphore=asyncio.Semaphore(1),
                manifest=manifest,
                row=row,
                base_url="https://example.test",
                retries=4,
            )

    assert asyncio.run(run())
    assert calls == 1
    assert manifest.pending_sections(year=2026, pleito=3220, uf="CE") == []

    refreshable = manifest.pending_sections(
        year=2026, pleito=3220, uf="CE", refresh_empty=True
    )
    assert len(refreshable) == 1
    assert refreshable[0]["http_status"] == 404
