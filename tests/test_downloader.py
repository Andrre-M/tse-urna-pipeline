import asyncio
from pathlib import Path

import httpx

from tse_urna.ingestion.downloader import AsyncRateLimiter, _download_one
from tse_urna.ingestion.manifest import Manifest
from tse_urna.models import DiscoveredFile, SectionRef


def _pending_row(tmp_path: Path):
    manifest = Manifest(tmp_path / "manifest.db")
    ref = SectionRef.build(
        year=2026, pleito=3220, uf="CE", municipality=13897, zone=3, section=444
    )
    manifest.upsert_discovered(
        [
            DiscoveredFile(
                section=ref,
                source_hash="abc",
                filename="sample.logjez",
                source_url="https://example.test/sample.logjez",
            )
        ]
    )
    return manifest, manifest.pending_downloads()[0]


def test_download_retries_transient_status(tmp_path: Path):
    manifest, row = _pending_row(tmp_path)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, headers={"Retry-After": "0"})
        return httpx.Response(200, content=b"archive", headers={"Content-Length": "7"})

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await _download_one(
                client=client,
                limiter=AsyncRateLimiter(10_000),
                semaphore=asyncio.Semaphore(1),
                manifest=manifest,
                row=row,
                data_dir=tmp_path / "data",
                retries=2,
            )

    asyncio.run(run())
    assert calls == 2
    assert manifest.status_counts()[0]["status"] == "downloaded"


def test_download_does_not_retry_permanent_404(tmp_path: Path):
    manifest, row = _pending_row(tmp_path)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404)

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await _download_one(
                client=client,
                limiter=AsyncRateLimiter(10_000),
                semaphore=asyncio.Semaphore(1),
                manifest=manifest,
                row=row,
                data_dir=tmp_path / "data",
                retries=4,
            )

    asyncio.run(run())
    assert calls == 1
    assert manifest.status_counts()[0]["status"] == "failed"


def test_rate_limiter_rejects_non_positive_rate():
    try:
        AsyncRateLimiter(0)
    except ValueError as exc:
        assert "maior que zero" in str(exc)
    else:
        raise AssertionError("taxa zero deveria ser rejeitada")
