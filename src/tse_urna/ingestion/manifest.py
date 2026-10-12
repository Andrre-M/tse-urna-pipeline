from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from tse_urna.models import DiscoveredFile

DDL = """
CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    election_year INTEGER NOT NULL,
    pleito TEXT NOT NULL,
    uf TEXT NOT NULL,
    municipality TEXT NOT NULL,
    zone TEXT NOT NULL,
    section TEXT NOT NULL,
    aux_url TEXT NOT NULL UNIQUE,
    discovery_status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    files_found INTEGER NOT NULL DEFAULT 0,
    http_status INTEGER,
    error TEXT,
    discovered_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(election_year, pleito, uf, municipality, zone, section)
);

CREATE INDEX IF NOT EXISTS idx_sections_discovery
ON sections(election_year, pleito, uf, discovery_status);

CREATE TABLE IF NOT EXISTS section_refresh_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    election_year INTEGER NOT NULL,
    pleito TEXT NOT NULL,
    uf TEXT NOT NULL,
    baseline_empty_sections INTEGER NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_section_refresh_runs_partition
ON section_refresh_runs(election_year, pleito, uf, completed_at);

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    election_year INTEGER NOT NULL,
    pleito TEXT NOT NULL,
    uf TEXT NOT NULL,
    municipality TEXT NOT NULL,
    zone TEXT NOT NULL,
    section TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    filename TEXT NOT NULL,
    source_url TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    http_status INTEGER,
    local_path TEXT,
    file_size INTEGER,
    sha256_local TEXT,
    downloaded_at TEXT,
    extracted_path TEXT,
    extract_status TEXT NOT NULL DEFAULT 'pending',
    parsed_path TEXT,
    parse_status TEXT NOT NULL DEFAULT 'pending',
    error TEXT,
    discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_files_status ON files(status);
CREATE INDEX IF NOT EXISTS idx_files_partition
ON files(election_year, pleito, uf, municipality, zone, section);
"""


class Manifest:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.executescript(DDL)
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(sections)").fetchall()
            }
            if "last_refresh_id" not in columns:
                conn.execute("ALTER TABLE sections ADD COLUMN last_refresh_id INTEGER")

    def upsert_sections(self, sections: Iterable[tuple[object, str]]) -> int:
        rows = list(sections)
        if not rows:
            return 0
        self.init()
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO sections (
                    election_year, pleito, uf, municipality, zone, section, aux_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(aux_url) DO UPDATE SET
                    updated_at = CURRENT_TIMESTAMP
                """,
                [
                    (
                        ref.year,
                        ref.pleito,
                        ref.uf,
                        ref.municipality,
                        ref.zone,
                        ref.section,
                        aux_url,
                    )
                    for ref, aux_url in rows
                ],
            )
        return len(rows)

    def pending_sections(
        self,
        *,
        year: int,
        pleito: str | int,
        uf: str,
        limit: int | None = None,
        refresh_run_id: int | None = None,
    ) -> list[sqlite3.Row]:
        self.init()
        sql = """
            SELECT * FROM sections
            WHERE election_year=? AND pleito=? AND uf=?
              AND (
                discovery_status IN ('pending', 'failed')
                OR (
                    ? IS NOT NULL
                    AND discovery_status='discovered'
                    AND files_found=0
                    AND COALESCE(last_refresh_id, 0) != ?
                )
              )
            ORDER BY municipality, zone, section
        """
        params: list[object] = [
            int(year),
            str(pleito),
            uf.lower(),
            refresh_run_id,
            refresh_run_id,
        ]
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        with self.connect() as conn:
            return conn.execute(sql, params).fetchall()

    def mark_section_discovered(
        self,
        record_id: int,
        *,
        files_found: int,
        http_status: int,
        refresh_run_id: int | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE sections SET discovery_status='discovered', attempts=attempts+1,
                    files_found=?, http_status=?, error=NULL, discovered_at=CURRENT_TIMESTAMP,
                    last_refresh_id=COALESCE(?, last_refresh_id),
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (files_found, http_status, refresh_run_id, record_id),
            )

    def start_or_resume_empty_refresh(
        self, *, year: int, pleito: str | int, uf: str
    ) -> sqlite3.Row:
        self.init()
        partition = (int(year), str(pleito), uf.lower())
        with self.connect() as conn:
            active = conn.execute(
                """
                SELECT * FROM section_refresh_runs
                WHERE election_year=? AND pleito=? AND uf=? AND completed_at IS NULL
                ORDER BY id DESC LIMIT 1
                """,
                partition,
            ).fetchone()
            if active is not None:
                return active
            baseline = conn.execute(
                """
                SELECT COUNT(*) FROM sections
                WHERE election_year=? AND pleito=? AND uf=?
                  AND discovery_status='discovered' AND files_found=0
                """,
                partition,
            ).fetchone()[0]
            cursor = conn.execute(
                """
                INSERT INTO section_refresh_runs (
                    election_year, pleito, uf, baseline_empty_sections
                ) VALUES (?, ?, ?, ?)
                """,
                (*partition, int(baseline)),
            )
            return conn.execute(
                "SELECT * FROM section_refresh_runs WHERE id=?", (cursor.lastrowid,)
            ).fetchone()

    def empty_refresh_remaining(
        self, *, refresh_run_id: int, year: int, pleito: str | int, uf: str
    ) -> int:
        self.init()
        with self.connect() as conn:
            return int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM sections
                    WHERE election_year=? AND pleito=? AND uf=?
                      AND files_found=0
                      AND discovery_status IN ('discovered', 'failed')
                      AND COALESCE(last_refresh_id, 0) != ?
                    """,
                    (int(year), str(pleito), uf.lower(), int(refresh_run_id)),
                ).fetchone()[0]
            )

    def complete_empty_refresh(self, refresh_run_id: int) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE section_refresh_runs SET completed_at=CURRENT_TIMESTAMP
                WHERE id=? AND completed_at IS NULL
                """,
                (int(refresh_run_id),),
            )

    def mark_section_discovery_failed(
        self, record_id: int, *, error: str, http_status: int | None
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE sections SET discovery_status='failed', attempts=attempts+1,
                    http_status=?, error=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (http_status, error[:2000], record_id),
            )

    def section_status_counts(self, *, year: int, pleito: str | int, uf: str) -> list[sqlite3.Row]:
        self.init()
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT discovery_status, COUNT(*) AS total, SUM(files_found) AS files_found
                FROM sections
                WHERE election_year=? AND pleito=? AND uf=?
                GROUP BY discovery_status
                ORDER BY discovery_status
                """,
                (int(year), str(pleito), uf.lower()),
            ).fetchall()

    def section_coverage_rows(
        self, *, year: int, pleito: str | int, uf: str
    ) -> list[sqlite3.Row]:
        self.init()
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT election_year, pleito, uf, municipality, zone, section,
                       discovery_status, files_found, discovered_at
                FROM sections
                WHERE election_year=? AND pleito=? AND uf=?
                ORDER BY municipality, zone, section
                """,
                (int(year), str(pleito), uf.lower()),
            ).fetchall()

    def upsert_discovered(self, files: Iterable[DiscoveredFile]) -> int:
        rows = list(files)
        if not rows:
            return 0
        self.init()
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO files (
                    election_year, pleito, uf, municipality, zone, section,
                    source_hash, filename, source_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_url) DO UPDATE SET
                    source_hash = excluded.source_hash,
                    filename = excluded.filename,
                    updated_at = CURRENT_TIMESTAMP
                """,
                [
                    (
                        f.section.year,
                        f.section.pleito,
                        f.section.uf,
                        f.section.municipality,
                        f.section.zone,
                        f.section.section,
                        f.source_hash,
                        f.filename,
                        f.source_url,
                    )
                    for f in rows
                ],
            )
        return len(rows)

    def _fetch_files_with_limit(self, sql: str, limit: int | None = None) -> list[sqlite3.Row]:
        self.init()
        params: list[object] = []
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        with self.connect() as conn:
            return conn.execute(sql, params).fetchall()

    def pending_downloads(self, limit: int | None = None) -> list[sqlite3.Row]:
        return self._fetch_files_with_limit(
            "SELECT * FROM files WHERE status IN ('pending', 'failed') ORDER BY id",
            limit,
        )

    def downloaded_files(self, limit: int | None = None) -> list[sqlite3.Row]:
        return self._fetch_files_with_limit(
            "SELECT * FROM files WHERE status='downloaded' "
            "AND extract_status IN ('pending','failed') ORDER BY id",
            limit,
        )

    def extracted_files(self, limit: int | None = None) -> list[sqlite3.Row]:
        return self._fetch_files_with_limit(
            "SELECT * FROM files WHERE extract_status='extracted' "
            "AND parse_status IN ('pending','failed') ORDER BY id",
            limit,
        )

    def mark_downloaded(
        self,
        record_id: int,
        *,
        local_path: str,
        file_size: int,
        sha256_local: str,
        http_status: int,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE files SET
                    status='downloaded', attempts=attempts+1, http_status=?,
                    local_path=?, file_size=?, sha256_local=?,
                    downloaded_at=CURRENT_TIMESTAMP, error=NULL,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (http_status, local_path, file_size, sha256_local, record_id),
            )

    def mark_download_failed(self, record_id: int, *, error: str, http_status: int | None) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE files SET status='failed', attempts=attempts+1,
                    http_status=?, error=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (http_status, error[:2000], record_id),
            )

    def mark_extracted(self, record_id: int, *, extracted_path: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE files SET extract_status='extracted', extracted_path=?, error=NULL,
                    updated_at=CURRENT_TIMESTAMP WHERE id=?
                """,
                (extracted_path, record_id),
            )

    def mark_extract_failed(self, record_id: int, *, error: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE files SET extract_status='failed', error=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (error[:2000], record_id),
            )

    def mark_parsed(self, record_id: int, *, parsed_path: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE files SET parse_status='parsed', parsed_path=?, error=NULL,
                    updated_at=CURRENT_TIMESTAMP WHERE id=?
                """,
                (parsed_path, record_id),
            )

    def mark_parsed_many(self, record_ids: Iterable[int], *, parsed_path: str) -> None:
        ids = [int(record_id) for record_id in record_ids]
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        with self.connect() as conn:
            conn.execute(
                f"""
                UPDATE files SET parse_status='parsed', parsed_path=?, error=NULL,
                    updated_at=CURRENT_TIMESTAMP WHERE id IN ({placeholders})
                """,
                [parsed_path, *ids],
            )

    def mark_parse_failed(self, record_id: int, *, error: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE files SET parse_status='failed', error=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (error[:2000], record_id),
            )
    def all_section_status_counts(self) -> list[sqlite3.Row]:
        self.init()
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT election_year, pleito, uf, discovery_status,
                       COUNT(*) AS total, SUM(files_found) AS files_found
                FROM sections
                GROUP BY election_year, pleito, uf, discovery_status
                ORDER BY election_year, pleito, uf, discovery_status
                """
            ).fetchall()

    def status_counts(self) -> list[sqlite3.Row]:
        self.init()
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT status, extract_status, parse_status, COUNT(*) AS total
                FROM files
                GROUP BY status, extract_status, parse_status
                ORDER BY status, extract_status, parse_status
                """
            ).fetchall()
