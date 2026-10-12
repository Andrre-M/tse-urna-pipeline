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

    manifest.mark_section_discovered(pending[0]["id"], files_found=0, http_status=200)
    remaining = manifest.pending_sections(year=2026, pleito=3220, uf="CE")
    assert len(remaining) == 1
    assert remaining[0]["section"] == "0445"

    refresh = manifest.start_or_resume_empty_refresh(year=2026, pleito=3220, uf="CE")
    refreshable = manifest.pending_sections(
        year=2026, pleito=3220, uf="CE", refresh_run_id=refresh["id"]
    )
    assert {row["section"] for row in refreshable} == {"0444", "0445"}


def test_empty_section_refresh_resumes_after_completed_rows(tmp_path: Path):
    from tse_urna.discovery.urls import section_aux_url

    manifest = Manifest(tmp_path / "manifest.db")
    refs = [
        SectionRef.build(
            year=2026, pleito=3220, uf="CE", municipality=13897, zone=3, section=section
        )
        for section in (444, 445, 446)
    ]
    manifest.upsert_sections(
        (ref, section_aux_url(base_url="https://example.test", section=ref))
        for ref in refs
    )
    for row in manifest.pending_sections(year=2026, pleito=3220, uf="CE"):
        manifest.mark_section_discovered(row["id"], files_found=0, http_status=404)

    refresh = manifest.start_or_resume_empty_refresh(year=2026, pleito=3220, uf="CE")
    first = manifest.pending_sections(
        year=2026, pleito=3220, uf="CE", limit=1, refresh_run_id=refresh["id"]
    )[0]
    manifest.mark_section_discovered(
        first["id"], files_found=0, http_status=404, refresh_run_id=refresh["id"]
    )

    resumed = manifest.start_or_resume_empty_refresh(year=2026, pleito=3220, uf="CE")
    remaining = manifest.pending_sections(
        year=2026, pleito=3220, uf="CE", refresh_run_id=resumed["id"]
    )

    assert resumed["id"] == refresh["id"]
    assert {row["section"] for row in remaining} == {"0445", "0446"}
    assert manifest.empty_refresh_remaining(
        refresh_run_id=refresh["id"], year=2026, pleito=3220, uf="CE"
    ) == 2


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


def test_mark_parsed_many_is_atomic_for_a_batch(tmp_path: Path):
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
            for index in range(2)
        ]
    )
    rows = manifest.pending_downloads()
    for row in rows:
        manifest.mark_downloaded(
            row["id"],
            local_path="raw",
            file_size=1,
            sha256_local="sha",
            http_status=200,
        )
        manifest.mark_extracted(row["id"], extracted_path="extracted")

    extracted = manifest.extracted_files()
    manifest.mark_parsed_many([row["id"] for row in extracted], parsed_path="batch=abc")

    assert manifest.extracted_files() == []
    assert manifest.status_counts()[0]["parse_status"] == "parsed"
