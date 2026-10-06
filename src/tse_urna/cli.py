from __future__ import annotations

import asyncio
import hashlib
from collections import defaultdict
from pathlib import Path

import httpx
import typer

from tse_urna.config import settings
from tse_urna.discovery.aux_parser import parse_aux_json
from tse_urna.discovery.state_parser import parse_state_config
from tse_urna.discovery.uf import discover_pending_sections, state_config_cache_path
from tse_urna.discovery.urls import section_aux_url, state_config_url
from tse_urna.extraction.logjez import extract_logjez
from tse_urna.ingestion.downloader import download_pending
from tse_urna.ingestion.manifest import Manifest
from tse_urna.models import SectionRef
from tse_urna.transformation.bronze import build_bronze_batch
from tse_urna.transformation.compaction import compact_bronze_partition

app = typer.Typer(no_args_is_help=True, help="Pipeline de logs públicos de urnas do TSE.")


def _manifest() -> Manifest:
    return Manifest(settings.manifest_path)


@app.command("init")
def init_project() -> None:
    """Inicializa diretórios locais e o banco de manifest."""
    for path in [
        settings.data_dir / "raw",
        settings.data_dir / "extracted",
        settings.data_dir / "x",
        settings.data_dir / "bronze",
        settings.data_dir / "bronze_compacted",
        settings.data_dir / "quarantine",
        settings.metadata_dir,
    ]:
        path.mkdir(parents=True, exist_ok=True)
    _manifest().init()
    typer.echo(f"Manifest inicializado em {settings.manifest_path}")


@app.command("discover-uf")
def discover_uf(
    year: int = typer.Option(...),
    pleito: str = typer.Option(...),
    uf: str = typer.Option(...),
    limit: int | None = typer.Option(
        None, help="Limita a quantidade de seções nesta execução (útil para testes)."
    ),
    catalog_only: bool = typer.Option(
        False, "--catalog-only", help="Registra as seções, mas não consulta os aux.json."
    ),
    refresh_empty: bool = typer.Option(
        False,
        "--refresh-empty",
        help="Reconsulta seções concluídas sem logs, útil durante publicação gradual.",
    ),
) -> None:
    """Descobre todas as seções de uma UF e seus arquivos .logjez."""
    uf = uf.upper()
    manifest = _manifest()
    manifest.init()

    config_url = state_config_url(
        base_url=settings.base_url, year=year, pleito=pleito, uf=uf
    )
    typer.echo(f"Baixando catálogo da UF: {config_url}")
    with httpx.Client(timeout=settings.timeout_seconds, follow_redirects=True) as client:
        response = client.get(config_url)
        response.raise_for_status()
        payload = response.json()

    cache_path = state_config_cache_path(
        settings.metadata_dir, year=year, pleito=pleito, uf=uf
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(response.content)

    sections = parse_state_config(payload, year=year, pleito=pleito, uf=uf)
    registered = manifest.upsert_sections(
        (ref, section_aux_url(base_url=settings.base_url, section=ref))
        for ref in sections
    )
    typer.echo(f"{registered} seção(ões) catalogada(s) para {uf}.")

    if catalog_only:
        typer.echo("Catálogo concluído; consulta dos aux.json não executada.")
        return

    stats = asyncio.run(
        discover_pending_sections(
            manifest=manifest,
            base_url=settings.base_url,
            year=year,
            pleito=pleito,
            uf=uf,
            concurrency=settings.concurrency,
            requests_per_second=settings.requests_per_second,
            timeout_seconds=settings.timeout_seconds,
            retries=settings.retries,
            limit=limit,
            refresh_empty=refresh_empty,
        )
    )
    typer.echo(f"Discovery: {stats.succeeded}/{stats.processed} seção(ões) concluída(s).")

    for row in manifest.section_status_counts(year=year, pleito=pleito, uf=uf):
        typer.echo(
            f"discovery={row['discovery_status']:<10} total={row['total']} "
            f"logjez={row['files_found'] or 0}"
        )
    if stats.failed:
        raise typer.Exit(code=1)


@app.command("discover-section")
def discover_section(
    year: int = typer.Option(...),
    pleito: str = typer.Option(...),
    uf: str = typer.Option(...),
    municipality: str = typer.Option(...),
    zone: str = typer.Option(...),
    section: str = typer.Option(...),
) -> None:
    """Descobre os .logjez associados a uma seção e registra no manifest."""
    ref = SectionRef.build(
        year=year,
        pleito=pleito,
        uf=uf,
        municipality=municipality,
        zone=zone,
        section=section,
    )
    url = section_aux_url(base_url=settings.base_url, section=ref)
    typer.echo(f"Consultando: {url}")

    with httpx.Client(timeout=settings.timeout_seconds, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        payload = response.json()

    discovered = parse_aux_json(payload, base_url=settings.base_url, section=ref)
    count = _manifest().upsert_discovered(discovered)
    typer.echo(f"{count} arquivo(s) .logjez registrado(s) no manifest.")


@app.command("ingest")
def ingest(
    limit: int | None = typer.Option(
        None, help="Limita a quantidade de arquivos nesta execução."
    ),
) -> None:
    """Baixa arquivos pendentes do manifest de forma idempotente."""
    stats = asyncio.run(
        download_pending(
            manifest=_manifest(),
            data_dir=settings.data_dir,
            concurrency=settings.concurrency,
            requests_per_second=settings.requests_per_second,
            timeout_seconds=settings.timeout_seconds,
            retries=settings.retries,
            limit=limit,
        )
    )
    typer.echo(f"Downloads: {stats.succeeded}/{stats.processed} concluído(s).")
    if stats.failed:
        raise typer.Exit(code=1)


@app.command("extract")
def extract(
    limit: int | None = typer.Option(
        None, help="Limita a quantidade de arquivos nesta execução."
    ),
) -> None:
    """Extrai logd.dat dos .logjez baixados ainda pendentes."""
    manifest = _manifest()
    rows = manifest.downloaded_files(limit=limit)
    failures = 0
    for row in rows:
        source = Path(row["local_path"])
        destination = (
            settings.data_dir
            / "x"
            / f"f={int(row['id']):08d}"
        )
        try:
            logs = extract_logjez(source, destination)
            manifest.mark_extracted(row["id"], extracted_path=str(destination))
            typer.echo(f"{source.name}: {len(logs)} log(s) extraído(s)")
        except Exception as exc:
            failures += 1
            manifest.mark_extract_failed(row["id"], error=str(exc))
            typer.echo(f"ERRO {source}: {exc}", err=True)
    if failures:
        raise typer.Exit(code=1)


@app.command("bronze")
def bronze(
    limit: int | None = typer.Option(
        None, help="Limita a quantidade de arquivos nesta execução."
    ),
    batch_files: int = typer.Option(
        settings.bronze_batch_files,
        min=1,
        help="Máximo de arquivos-fonte agrupados em cada lote reiniciável.",
    ),
    target_rows: int = typer.Option(
        settings.bronze_target_rows,
        min=1,
        help="Número-alvo de registros por parte Parquet.",
    ),
) -> None:
    """Converte logs extraídos em lotes Bronze e quarantine idempotentes."""
    manifest = _manifest()
    rows = manifest.extracted_files(limit=limit)
    failures = 0
    grouped: dict[tuple[int, str, str], list] = defaultdict(list)
    for row in rows:
        grouped[(row["election_year"], row["pleito"], row["uf"].upper())].append(row)

    for (year, pleito, uf), partition_rows in grouped.items():
        for offset in range(0, len(partition_rows), batch_files):
            batch_rows = partition_rows[offset : offset + batch_files]
            identity = "|".join(
                f"{row['id']}:{row['source_hash']}"
                for row in sorted(batch_rows, key=lambda r: r["id"])
            )
            batch_id = hashlib.sha256(identity.encode()).hexdigest()[:16]
            output_dir = (
                settings.data_dir
                / "bronze"
                / f"year={year}"
                / f"pleito={pleito}"
                / f"uf={uf}"
                / f"batch={batch_id}"
            )
            quarantine_path = (
                settings.data_dir
                / "quarantine"
                / f"year={year}"
                / f"pleito={pleito}"
                / f"uf={uf}"
                / f"batch={batch_id}.jsonl"
            )
            try:
                logs: list[tuple[Path, dict[str, str | int]]] = []
                for row in batch_rows:
                    log_files = sorted(Path(row["extracted_path"]).rglob("logd.dat"))
                    if not log_files:
                        raise FileNotFoundError(f"logd.dat ausente para {row['filename']}")
                    metadata = {
                        "election_year": row["election_year"],
                        "pleito": row["pleito"],
                        "uf": row["uf"].upper(),
                        "municipality": row["municipality"],
                        "zone": row["zone"],
                        "section": row["section"],
                        "source_hash": row["source_hash"],
                        "source_file": row["filename"],
                    }
                    logs.extend((log_path, metadata) for log_path in log_files)

                result = build_bronze_batch(
                    logs=logs,
                    output_dir=output_dir,
                    quarantine_path=quarantine_path,
                    target_rows=target_rows,
                )
                manifest.mark_parsed_many(
                    [row["id"] for row in batch_rows], parsed_path=result.output_dir
                )
                typer.echo(
                    f"batch={batch_id}: {len(batch_rows)} arquivo(s), "
                    f"{result.valid_rows} válidas / {result.rejected_rows} quarantine, "
                    f"{len(result.output_files)} Parquet(s)"
                )
            except Exception as exc:
                failures += len(batch_rows)
                for row in batch_rows:
                    manifest.mark_parse_failed(row["id"], error=str(exc))
                typer.echo(f"ERRO batch={batch_id}: {exc}", err=True)
    if failures:
        raise typer.Exit(code=1)


@app.command("compact-bronze")
def compact_bronze(
    year: int = typer.Option(...),
    pleito: str = typer.Option(...),
    uf: str = typer.Option(...),
    target_size_mb: int = typer.Option(
        256, min=1, help="Tamanho compactado aproximado de cada Parquet."
    ),
) -> None:
    """Compacta os lotes Bronze de uma eleição/UF em poucos Parquets."""
    uf = uf.upper()
    partition = Path(f"year={year}") / f"pleito={pleito}" / f"uf={uf}"
    outputs = compact_bronze_partition(
        input_dir=settings.data_dir / "bronze" / partition,
        output_dir=settings.data_dir / "bronze_compacted" / partition,
        target_size_mb=target_size_mb,
    )
    typer.echo(f"{len(outputs)} Parquet(s) compactado(s) para {year}/{pleito}/{uf}.")


@app.command("status")
def status() -> None:
    """Mostra o estado atual do discovery e dos arquivos no manifest."""
    manifest = _manifest()

    section_rows = manifest.all_section_status_counts()
    if section_rows:
        typer.echo("SEÇÕES")
        for row in section_rows:
            typer.echo(
                f"{row['election_year']} pleito={row['pleito']} uf={row['uf'].upper()} "
                f"discovery={row['discovery_status']:<10} total={row['total']} "
                f"logjez={row['files_found'] or 0}"
            )

    file_rows = manifest.status_counts()
    if file_rows:
        typer.echo("ARQUIVOS")
        for row in file_rows:
            typer.echo(
                f"download={row['status']:<10} extract={row['extract_status']:<10} "
                f"parse={row['parse_status']:<10} total={row['total']}"
            )

    if not section_rows and not file_rows:
        typer.echo("Manifest vazio.")


if __name__ == "__main__":
    app()
