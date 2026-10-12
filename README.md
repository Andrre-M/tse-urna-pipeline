# TSE Urna Pipeline

Pipeline de engenharia de dados para coletar, preservar, extrair e estruturar os **logs públicos das urnas eletrônicas** disponibilizados pelo Tribunal Superior Eleitoral (TSE).

Estado atual: [`PROJECT_STATE.md`](PROJECT_STATE.md). Operação: [`docs/runbook.md`](docs/runbook.md).

> O foco deste repositório é **engenharia de dados**. Análises e dashboard são consumidores do dataset, não o núcleo do projeto.

## Objetivo

Construir um pipeline reprodutível para o **Ceará completo**, transformando arquivos públicos `.logjez` em dados tabulares rastreáveis e prontos para as camadas Silver/Gold.

```text
TSE
 │
 ├─ catálogo da UF (*-cs.json)
 ▼
Seções do Ceará
 │
 ├─ discovery (-aux.json por seção)
 ▼
Manifest SQLite / checkpoints
 │
 ├─ ingestion (.logjez)
 ▼
RAW imutável
 │
 ├─ extraction (7z)
 ▼
logd.dat
 │
 ├─ parsing
 ▼
BRONZE (Parquet)
 │
 ├─ normalização / qualidade / compaction
 ▼
SILVER (Parquet)
```

## Escopo atual — v0.3

A unidade de teste ainda pode ser uma seção isolada, mas o **MVP operacional é a UF CE inteira**.

Já implementado:

- construção determinística das URLs do TSE;
- leitura do catálogo estadual `{uf}-pXXXXXX-cs.json`;
- expansão `município → zona → seção`;
- manifest de seções com checkpoint de discovery;
- discovery concorrente dos `-aux.json`;
- identificação de logs antigos `.logjez` e do formato 2026 `*-log.jez`;
- manifest persistente de arquivos em SQLite;
- download com retry, checkpoint e SHA-256 local;
- RAW imutável;
- extração segura de contêineres 7-Zip e ZIP, inclusive `.jez` aninhados;
- parser do formato de log;
- Bronze em lotes Parquet com partes de tamanho controlado;
- compactação reiniciável por eleição/UF;
- quarantine idempotente por lote;
- testes automatizados e CI.

Validado contra o TSE em 6 de outubro de 2026:

- catálogo com **25.650 seções** do Ceará;
- piloto com 5 seções e 5 arquivos `*-log.jez` reais;
- 31.947 eventos válidos e zero linhas em quarantine no piloto;
- geração de um lote Bronze e sua compactação.

Ainda falta antes de considerar o Ceará inteiro concluído:

- Silver normalizada;
- publicação do dataset.

Processamento completo validado em 12 de outubro de 2026:

- 25.650 seções consultadas e 23.765 arquivos processados;
- 143.703.249 eventos válidos, zero quarantine e zero nulos críticos;
- qualidade `PASS WITH WARNINGS` por 1.885 seções sem arquivo publicado e 316
  timestamps fora de 2026.

Veja o [`relatório de qualidade`](docs/quality_report_ce_2026_3220.md).

## Instalação

Recomendado: [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev
```

ou com `pip`:

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -e ".[dev]"
```

## Primeira execução recomendada

Por padrão, dados e checkpoints ficam em `data/` e `metadata/`. Para usar outro
volume no PowerShell:

```powershell
$env:TSE_DATA_DIR = 'D:\tse-urna-pipeline\data'
$env:TSE_METADATA_DIR = 'D:\tse-urna-pipeline\metadata'
```

Antes de processar o Ceará inteiro, valide o pipeline em um lote pequeno:

```bash
uv sync --extra dev
uv run pytest -q
uv run ruff check .
uv run urna-etl init
uv run urna-etl preflight --limit 100

# Cataloga todas as seções do Ceará sem consultar cada aux.json
uv run urna-etl discover-uf --year 2026 --pleito 3220 --uf CE --catalog-only
uv run urna-etl status

# Processa apenas 100 seções como piloto
uv run urna-etl discover-uf --year 2026 --pleito 3220 --uf CE --limit 100
uv run urna-etl ingest --limit 100
uv run urna-etl extract --limit 100
uv run urna-etl bronze --limit 100
uv run urna-etl compact-bronze --year 2026 --pleito 3220 --uf CE
uv run urna-etl status
```

Só depois desse piloto validado vale liberar o discovery/ingestão da UF inteira. A geração Bronze completa deve esperar a etapa de compaction para evitar milhares de arquivos pequenos.

## Uso — Ceará completo

### 1. Inicializar

```bash
uv run urna-etl init
```

### 2. Catalogar e descobrir todas as seções do Ceará

Antes da execução, confirme os caminhos locais e pelo menos 40 GiB livres:

```bash
uv run urna-etl preflight
```

```bash
uv run urna-etl discover-uf \
  --year 2026 \
  --pleito 3220 \
  --uf CE
```

Essa etapa:

1. baixa o catálogo oficial do Ceará;
2. registra todas as seções no manifest;
3. consulta os `-aux.json` ainda pendentes;
4. registra todos os `.logjez` encontrados.

Se a execução for interrompida, a próxima execução continua apenas das seções `pending/failed`.
Durante uma publicação gradual do TSE, use `--refresh-empty` para reconsultar seções que
antes responderam sem logs:

```bash
uv run urna-etl discover-uf --year 2026 --pleito 3220 --uf CE --refresh-empty
```

Para testar o fluxo sem percorrer a UF inteira:

```bash
uv run urna-etl preflight --limit 100
uv run urna-etl discover-uf \
  --year 2026 \
  --pleito 3220 \
  --uf CE \
  --limit 100
```

Com `--limit`, o preflight estima o espaço proporcionalmente ao catálogo de 25.650
seções. Se houver espaço para o lote, a falta dos 40 GiB da carga completa gera apenas
um aviso. Sem `--limit`, os 40 GiB continuam obrigatórios.

Também é possível apenas catalogar as seções:

```bash
uv run urna-etl discover-uf --year 2026 --pleito 3220 --uf CE --catalog-only
```

### 3. Baixar os `.logjez` pendentes

```bash
uv run urna-etl ingest
```

Downloads já concluídos não são repetidos. Cada arquivo recebe SHA-256 local.

Para uma execução controlada:

```bash
uv run urna-etl ingest --limit 100
```

### 4. Extrair os logs

```bash
uv run urna-etl extract
```

ou em lote:

```bash
uv run urna-etl extract --limit 100
```

### 5. Gerar Bronze

```bash
uv run urna-etl bronze
```

ou em lote:

```bash
uv run urna-etl bronze --limit 100
```

O padrão agrupa até 100 arquivos-fonte por lote e limita cada parte a aproximadamente
250 mil registros. Ambos são configuráveis:

```bash
uv run urna-etl bronze --batch-files 100 --target-rows 250000
```

### 6. Compactar Bronze

```bash
uv run urna-etl compact-bronze --year 2026 --pleito 3220 --uf CE
```

A compactação é uma camada derivada e reiniciável; RAW e os lotes Bronze permanecem imutáveis.

### 7. Status

```bash
uv run urna-etl status
```

## Debug por seção

Uma seção específica continua disponível para investigação de formato e regressão:

```bash
uv run urna-etl discover-section \
  --year 2026 \
  --pleito 3220 \
  --uf CE \
  --municipality 13897 \
  --zone 3 \
  --section 444
```

Ela **não representa mais o escopo do MVP**.

## Estrutura

```text
src/tse_urna/
├── cli.py
├── config.py
├── discovery/
│   ├── aux_parser.py
│   ├── state_parser.py
│   ├── uf.py
│   └── urls.py
├── ingestion/
│   ├── downloader.py
│   └── manifest.py
├── extraction/
│   └── logjez.py
├── parsing/
│   └── log_parser.py
├── transformation/
│   └── bronze.py
└── quality/
    └── checks.py
```

## Princípios

**UF como unidade do MVP.** O projeto deve conseguir reconstruir o Ceará completo; seção isolada serve para teste/debug.

**RAW imutável.** O arquivo recebido do TSE nunca é alterado. O layout físico usa IDs curtos
do manifest para funcionar também em caminhos Windows; URL, hash e nome original ficam no SQLite.

**Idempotência.** Reexecutar discovery/ingestion não deve duplicar trabalho concluído.

**Checkpoint em dois níveis.** O SQLite controla tanto a descoberta das seções quanto o ciclo de vida dos arquivos.

**Rastreabilidade.** Todo registro mantém eleição, UF, município, zona, seção, hash e arquivo-fonte.

**Falha explícita.** Registros não interpretados vão para quarantine.

**Sem infraestrutura artificial.** SQLite, Parquet e processamento local/CI enquanto forem suficientes; serviços adicionais só entram quando houver necessidade real.

## Dados

Dados pesados não são versionados no Git. O repositório contém código, documentação e fixtures pequenas. O dataset processado será publicado separadamente em Parquet.

## Roadmap

Veja [`ROADMAP.md`](ROADMAP.md).

## Fonte

Os arquivos de urna são publicados pelo Tribunal Superior Eleitoral em `resultados.tse.jus.br`. O projeto é independente e não possui vínculo com o TSE.
