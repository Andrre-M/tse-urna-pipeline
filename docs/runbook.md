# Operação

## Preparação

No PowerShell, a partir da raiz do repositório:

```powershell
$env:TSE_DATA_DIR = 'D:\tse-urna-pipeline\data'
$env:TSE_METADATA_DIR = 'D:\tse-urna-pipeline\metadata'

uv sync --locked --extra dev
uv run ruff check .
uv run pytest -q
uv run urna-etl init
uv run urna-etl preflight --limit 1000
```

Sem `--limit`, o preflight exige 40 GiB livres. Com limite, a estimativa é
proporcional ao catálogo.

## Processamento

Execute uma etapa por vez e confira `urna-etl status` entre elas:

```powershell
uv run urna-etl discover-uf --year 2026 --pleito 3220 --uf CE --limit 1000
uv run urna-etl ingest --limit 500
uv run urna-etl extract --limit 500
uv run urna-etl bronze --limit 500 --batch-files 100 --target-rows 250000
uv run urna-etl compact-bronze --year 2026 --pleito 3220 --uf CE
uv run urna-etl quality-report --year 2026 --pleito 3220 --uf CE
uv run urna-etl silver --year 2026 --pleito 3220 --uf CE --limit 1
```

Repita cada etapa limitada enquanto houver pendências. Partes concluídas são
reutilizadas. Uma carga completa do Ceará exige aprovação explícita.

## Reconsulta de seções vazias

```powershell
uv run urna-etl discover-uf --year 2026 --pleito 3220 --uf CE --refresh-empty --limit 250
```

O comando informa o ID do ciclo e quantas seções restam. Repita até a mensagem
de conclusão; o SQLite registra cada seção já consultada naquele ciclo.

## Saídas Silver

```text
data/silver/events/year=2026/pleito=3220/uf=CE
data/silver/section_coverage/year=2026/pleito=3220/uf=CE
```

## Falhas

1. Rode `uv run urna-etl status`.
2. Consulte o erro em `metadata/manifest.db`.
3. Adicione um teste de regressão quando houver defeito no código.
4. Rode Ruff e pytest.
5. Repita apenas a etapa que falhou.

Não apague RAW, checkpoints ou lotes concluídos para tentar recuperar uma
execução. Nunca versione `data/` nem `metadata/manifest.db*`.
