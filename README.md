# TSE Urna Pipeline

Pipeline local para baixar e estruturar os logs públicos de urnas divulgados
pelo Tribunal Superior Eleitoral.

O recorte atual é o Ceará, eleição de 2026, pleito 3220. O processamento foi
concluído até a camada Silver; a publicação do dataset é a próxima etapa.

## Resultado

Em 12 de outubro de 2026:

- 25.650 seções consultadas;
- 23.765 arquivos de urna processados;
- 143.703.249 eventos na Silver;
- 1.885 seções sem arquivo publicado, reconsultadas após a carga;
- zero linhas em quarantine;
- 316 timestamps fora de 2026, preservados e sinalizados;
- qualidade `PASS WITH WARNINGS`.

Os detalhes estão no [relatório de qualidade](docs/quality_report_ce_2026_3220.md)
e no [estado do projeto](PROJECT_STATE.md).

## Fluxo

```text
catálogo CE → discovery → RAW → extração → Bronze → qualidade → Silver
                 │
                 └── manifest e checkpoints em SQLite
```

O SQLite guarda apenas estado operacional. Os dados analíticos ficam em
Parquet:

```text
data/bronze_compacted/year=2026/pleito=3220/uf=CE
data/silver/events/year=2026/pleito=3220/uf=CE
data/silver/section_coverage/year=2026/pleito=3220/uf=CE
```

`events` contém os logs conformados. `section_coverage` mantém o catálogo
completo, inclusive as seções para as quais o TSE não publicou arquivo.

## Ambiente

Requer Python 3.12 ou superior e [uv](https://docs.astral.sh/uv/).

```powershell
uv sync --locked --extra dev
uv run ruff check .
uv run pytest -q
```

Dados e checkpoints podem ficar fora do repositório:

```powershell
$env:TSE_DATA_DIR = 'D:\tse-urna-pipeline\data'
$env:TSE_METADATA_DIR = 'D:\tse-urna-pipeline\metadata'
```

O [runbook](docs/runbook.md) contém a ordem dos comandos, limites e recuperação
de falhas.

## Escolhas do projeto

- RAW é imutável.
- Downloads e transformações retomam de checkpoints.
- Linhas não interpretadas vão para quarantine.
- O timestamp registrado pela urna nunca é corrigido por inferência.
- Dados gerados e SQLite não entram no Git.
- Dashboard só começa depois da publicação do dataset.

O projeto é independente e não possui vínculo com o TSE.
