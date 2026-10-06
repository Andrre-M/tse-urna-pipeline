from __future__ import annotations

import asyncio
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
from tse_urna.transformation.bronze import build_bronze

app = typer.Typer(no_args_is_help=True, help="Pipeline de logs públicos de urnas do TSE.")


def _manifest() -> Manifest:
    return Manifest(settings.manifest_path)


@app.command("init")
def init_project() -> None:
    """Inicializa diretórios locais e o banco de manifest."""
    for path in [
        settings.data_dir / "raw",
        settings.data_dir / "extracted",
        settings.data_dir / "bronze",
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

    processed = asyncio.run(
        discover_pending_sections(
            manifest=manifest,
            base_url=settings.base_url,
            year=year,
            pleito=pleito,
            uf=uf,
            concurrency=settings.concurrency,
            requests_per_second=settings.requests_per_second,
            timeout_seconds=settings.timeout_seconds,
            limit=limit,
        )
    )
    typer.echo(f"{processed} seção(ões) tiveram o aux.json processado nesta execução.")

    for row in manifest.section_status_counts(year=year, pleito=pleito, uf=uf):
        typer.echo(
            f"discovery={row['discovery_status']:<10} total={row['total']} "
            f"logjez={row['files_found'] or 0}"
        )


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
    count = asyncio.run(
        download_pending(
            manifest=_manifest(),
            data_dir=settings.data_dir,
            concurrency=settings.concurrency,
            requests_per_second=settings.requests_per_second,
            timeout_seconds=settings.timeout_seconds,
            limit=limit,
        )
    )
    typer.echo(f"{count} registro(s) de download processado(s).")


@app.command("extract")
def extract(
    limit: int | None = typer.Option(
        None, help="Limita a quantidade de arquivos nesta execução."
    ),
) -> None:
    """Extrai logd.dat dos .logjez baixados ainda pendentes."""
    manifest = _manifest()
    rows = manifest.downloaded_files(limit=limit)
    for row in rows:
        source = Path(row["local_path"])
        destination = (
            settings.data_dir
            / "extracted"
            / f"year={row['election_year']}"
            / f"pleito={row['pleito']}"
            / f"uf={row['uf'].upper()}"
            / f"municipality={row['municipality']}"
            / f"zone={row['zone']}"
            / f"section={row['section']}"
            / row["source_hash"]
        )
        try:
            logs = extract_logjez(source, destination)
            manifest.mark_extracted(row["id"], extracted_path=str(destination))
            typer.echo(f"{source.name}: {len(logs)} log(s) extraído(s)")
        except Exception as exc:
            manifest.mark_extract_failed(row["id"], error=str(exc))
            typer.echo(f"ERRO {source}: {exc}", err=True)


@app.command("bronze")
def bronze(
    limit: int | None = typer.Option(
        None, help="Limita a quantidade de arquivos nesta execução."
    ),
) -> None:
    """Converte logs extraídos para Bronze Parquet e quarantine JSONL."""
    manifest = _manifest()
    rows = manifest.extracted_files(limit=limit)

    for row in rows:
        extracted_root = Path(row["extracted_path"])
        log_files = sorted(extracted_root.rglob("logd.dat"))
        try:
            total_valid = 0
            total_rejected = 0
            outputs: list[str] = []
            for index, log_path in enumerate(log_files):
                out_dir = (
                    settings.data_dir
                    / "bronze"
                    / f"year={row['election_year']}"
                    / f"pleito={row['pleito']}"
                    / f"uf={row['uf'].upper()}"
                    / f"municipality={row['municipality']}"
                    / f"zone={row['zone']}"
                    / f"section={row['section']}"
                )
                parquet = out_dir / f"{row['source_hash']}-{index:02d}.parquet"
                quarantine = settings.data_dir / "quarantine" / "unparsed_lines.jsonl"
                valid, rejected = build_bronze(
                    log_path=log_path,
                    output_path=parquet,
                    quarantine_path=quarantine,
                    metadata={
                        "election_year": row["election_year"],
                        "pleito": row["pleito"],
                        "uf": row["uf"].upper(),
                        "municipality": row["municipality"],
                        "zone": row["zone"],
                        "section": row["section"],
                        "source_hash": row["source_hash"],
                        "source_file": row["filename"],
                    },
                )
                total_valid += valid
                total_rejected += rejected
                outputs.append(str(parquet))

            manifest.mark_parsed(row["id"], parsed_path=";".join(outputs))
            typer.echo(
                f"{row['filename']}: {total_valid} válidas / {total_rejected} quarantine"
            )
        except Exception as exc:
            manifest.mark_parse_failed(row["id"], error=str(exc))
            typer.echo(f"ERRO {row['filename']}: {exc}", err=True)


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
