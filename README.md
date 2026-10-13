# TSE Urna Pipeline

Pipeline em Python para baixar e estruturar os logs públicos de urnas divulgados
pelo Tribunal Superior Eleitoral no
[Portal de Dados Abertos](https://dadosabertos-novo.tse.jus.br/).

O recorte processado neste repositório é o Ceará na eleição de 2026, pleito
3220. A carga foi feita para todas as seções disponíveis no catálogo estadual,
sem amostragem.

## Resultado

- 25.650 seções catalogadas;
- 23.765 arquivos de urna processados;
- 143.703.249 eventos na camada Silver;
- 1.885 seções sem arquivo publicado;
- nenhuma linha em quarentena;
- 316 timestamps fora de 2026, preservados e sinalizados.

O relatório completo está em
[docs/quality_report_ce_2026_3220.md](docs/quality_report_ce_2026_3220.md).

## Dataset

A camada Silver está disponível no
[Hugging Face](https://huggingface.co/datasets/Andrre-M/tse-urna-ce-2026),
separada em `events` e `section_coverage`. A publicação inclui manifesto,
checksums, dicionário de dados e relatório de qualidade.

## Organização dos dados

```text
catálogo → discovery → RAW → extração → Bronze → qualidade → Silver
```

O RAW guarda os arquivos baixados sem transformação. A Bronze preserva os
eventos e seus metadados de origem. A Silver oferece duas tabelas:

- `events`: eventos normalizados, com identificação da seção e política
  temporal explícita;
- `section_coverage`: todas as seções do catálogo, inclusive as que não tinham
  arquivo publicado.

O estado operacional fica em SQLite e os dados analíticos em Parquet. Arquivos
baixados, resultados e banco local não são versionados.

## Ambiente

O projeto requer Python 3.12 ou superior e
[uv](https://docs.astral.sh/uv/).

```powershell
uv sync --locked --extra dev
uv run ruff check .
uv run pytest -q
uv run urna-etl --help
```

Os diretórios de dados e metadados podem ficar fora do checkout:

```powershell
$env:TSE_DATA_DIR = 'D:\dados\tse-urna\data'
$env:TSE_METADATA_DIR = 'D:\dados\tse-urna\metadata'
```

O schema das camadas está em [docs/data_dictionary.md](docs/data_dictionary.md)
e as decisões de implementação em [docs/decisions.md](docs/decisions.md).

## Limites

Os resultados deste recorte foram validados apenas para o Ceará em
2026/3220. A ausência de arquivo para uma seção e os timestamps atípicos
reproduzem o material encontrado na fonte; isoladamente, não permitem concluir
nada sobre o processo eleitoral.

Este é um projeto independente e sem vínculo com o TSE.
