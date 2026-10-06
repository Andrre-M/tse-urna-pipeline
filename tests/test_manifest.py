from pathlib import Path

from tse_urna.ingestion.manifest import Manifest
from tse_urna.models import DiscoveredFile, SectionRef


def test_manifest_upsert_is_idempotent(tmp_path: Path):
    manifest = Manifest(tmp_path / "manifest.db")
    ref = SectionRef.build(
        year=2026, pleito=3220, uf="CE", municipality=13897, zone=3, section=444
    )
    item = DiscoveredFile(
        section=ref,
        source_hash="abc",
        filename="sample.logjez",
        source_url="https://example.test/sample.logjez",
    )

    manifest.upsert_discovered([item])
    manifest.upsert_discovered([item])

    rows = manifest.pending_downloads()
    assert len(rows) == 1
    assert rows[0]["filename"] == "sample.logjez"


def test_section_manifest_is_resumable(tmp_path: Path):
    from tse_urna.discovery.urls import section_aux_url

    manifest = Manifest(tmp_path / "manifest.db")
    refs = [
        SectionRef.build(
            year=2026, pleito=3220, uf="CE", municipality=13897, zone=3, section=444
        ),
        SectionRef.build(
            year=2026, pleito=3220, uf="CE", municipality=13897, zone=3, section=445
        ),
    ]
    manifest.upsert_sections(
        (ref, section_aux_url(base_url="https://example.test", section=ref)) for ref in refs
    )
    manifest.upsert_sections(
        (ref, section_aux_url(base_url="https://example.test", section=ref)) for ref in refs
    )

    pending = manifest.pending_sections(year=2026, pleito=3220, uf="CE")
    assert len(pending) == 2

    manifest.mark_section_discovered(pending[0]["id"], files_found=1, http_status=200)
    remaining = manifest.pending_sections(year=2026, pleito=3220, uf="CE")
    assert len(remaining) == 1
    assert remaining[0]["section"] == "0445"


def test_file_stage_queries_support_limit(tmp_path: Path):
    manifest = Manifest(tmp_path / "manifest.db")
    ref = SectionRef.build(
        year=2026, pleito=3220, uf="CE", municipality=13897, zone=3, section=444
    )
    manifest.upsert_discovered(
        [
            DiscoveredFile(
                section=ref,
                source_hash=f"hash-{index}",
                filename=f"sample-{index}.logjez",
                source_url=f"https://example.test/sample-{index}.logjez",
            )
            for index in range(3)
        ]
    )

    rows = manifest.pending_downloads(limit=2)
    assert len(rows) == 2


def test_all_section_status_counts(tmp_path: Path):
    from tse_urna.discovery.urls import section_aux_url

    manifest = Manifest(tmp_path / "manifest.db")
    refs = [
        SectionRef.build(
            year=2026, pleito=3220, uf="CE", municipality=13897, zone=3, section=444
        ),
        SectionRef.build(
            year=2026, pleito=3220, uf="CE", municipality=13897, zone=3, section=445
        ),
    ]
    manifest.upsert_sections(
        (ref, section_aux_url(base_url="https://example.test", section=ref)) for ref in refs
    )

    pending = manifest.pending_sections(year=2026, pleito=3220, uf="CE")
    manifest.mark_section_discovered(pending[0]["id"], files_found=1, http_status=200)

    counts = manifest.all_section_status_counts()
    by_status = {row["discovery_status"]: row["total"] for row in counts}
    assert by_status == {"discovered": 1, "pending": 1}
