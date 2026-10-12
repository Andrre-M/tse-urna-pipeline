from datetime import datetime
from pathlib import Path

import polars as pl

from tse_urna.discovery.urls import section_aux_url
from tse_urna.ingestion.manifest import Manifest
from tse_urna.models import DiscoveredFile, SectionRef
from tse_urna.quality.report import build_quality_summary, write_quality_report


def test_quality_report_passes_complete_partition(tmp_path: Path):
    manifest = Manifest(tmp_path / "manifest.db")
    with_file = SectionRef.build(
        year=2026, pleito=3220, uf="CE", municipality=13897, zone=3, section=444
    )
    empty = SectionRef.build(
        year=2026, pleito=3220, uf="CE", municipality=13897, zone=3, section=445
    )
    manifest.upsert_sections(
        [
            (with_file, section_aux_url(base_url="https://example.test", section=with_file)),
            (empty, section_aux_url(base_url="https://example.test", section=empty)),
        ]
    )
    sections = manifest.pending_sections(year=2026, pleito=3220, uf="CE")
    by_section = {row["section"]: row for row in sections}
    manifest.mark_section_discovered(
        by_section["0444"]["id"], files_found=1, http_status=200
    )
    manifest.mark_section_discovered(
        by_section["0445"]["id"], files_found=0, http_status=404
    )
    manifest.upsert_discovered(
        [
            DiscoveredFile(
                section=with_file,
                source_hash="hash-a",
                filename="sample.jez",
                source_url="https://example.test/sample.jez",
            )
        ]
    )
    file_row = manifest.pending_downloads()[0]
    manifest.mark_downloaded(
        file_row["id"],
        local_path="raw",
        file_size=1,
        sha256_local="sha",
        http_status=200,
    )
    manifest.mark_extracted(file_row["id"], extracted_path="x")
    manifest.mark_parsed(file_row["id"], parsed_path="bronze")

    compacted = tmp_path / "compacted"
    compacted.mkdir()
    pl.DataFrame(
        {
            "election_year": [2026],
            "pleito": ["3220"],
            "uf": ["CE"],
            "municipality": ["13897"],
            "zone": ["0003"],
            "section": ["0444"],
            "source_hash": ["hash-a"],
            "source_file": ["sample.jez"],
            "event_timestamp": [datetime(2026, 10, 4)],
            "severity": ["INFO"],
            "ue_id": ["1"],
            "application": ["APP"],
            "message_raw": ["ok"],
            "mac": ["AA"],
        }
    ).write_parquet(compacted / "part-00000.parquet")
    quarantine = tmp_path / "quarantine"
    quarantine.mkdir()
    (quarantine / "batch.jsonl").write_text("", encoding="utf-8")

    summary = build_quality_summary(
        manifest=manifest,
        compacted_dir=compacted,
        quarantine_dir=quarantine,
        year=2026,
        pleito=3220,
        uf="CE",
    )
    output = tmp_path / "quality.md"
    write_quality_report(summary, output_path=output, year=2026, pleito=3220, uf="CE")

    assert summary.passed
    assert summary.has_warnings
    assert summary.valid_rows == 1
    assert summary.empty_sections == 1
    assert summary.temporal_outlier_rows == 0
    assert "Status: **PASS WITH WARNINGS**" in output.read_text(encoding="utf-8")
