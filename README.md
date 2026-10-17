# TSE Urna Pipeline

Pipeline reprodutível em Python para organizar dados públicos do Tribunal
Superior Eleitoral e transformá-los em produtos analíticos verificáveis.

O projeto trabalha com dois domínios independentes:

- **logs técnicos de urna**, processados em Bronze, Silver e Gold sem qualquer
  interpretação como votos;
- **resultados eleitorais e perfil cadastral**, consolidados em uma Gold
  eleitoral própria e consumidos por um dashboard totalmente estático.

O recorte atual é o Ceará, eleição de 2026, primeiro turno, pleito 3220.

## Resultado atual

### Logs técnicos

- 25.650 seções catalogadas;
- 23.765 arquivos de urna processados;
- 143.703.249 eventos na Silver;
- 1.885 seções sem arquivo publicado;
- nenhuma linha em quarentena;
- 316 timestamps fora de 2026, preservados e sinalizados.

Esses eventos são registros técnicos. Eles não representam votos nem resultados
eleitorais. A validação completa está em
[docs/gold_validation_ce_2026_3220.md](docs/gold_validation_ce_2026_3220.md).

### Gold eleitoral

- 184 municípios;
- 23.765 seções;
- 5 cargos;
- 6.998.494 registros no perfil cadastral;
- 66.528 resultados agregados por município e opção de voto;
- 2.751.489 resultados por seção;
- sete tabelas Parquet, validadas com reconciliações e SHA-256.

O relatório está em
[docs/electoral_gold_validation_ce_2026_round_1.md](docs/electoral_gold_validation_ce_2026_round_1.md).

## Dashboard

O frontend em `dashboard/` é HTML, CSS e JavaScript estáticos. O build lê apenas
a Gold eleitoral e gera arquivos em `dist/`, que não são versionados.

As cinco áreas do produto são:

1. **Overview** — visão estadual e indicadores centrais;
2. **Municípios** — mapa, comparação e tabela ordenável;
3. **Eleitorado** — perfil cadastral, biometria, escolaridade e pirâmide etária;
4. **Cargos** — resultados, candidaturas, mapas e comparações territoriais;
5. **Explorador** — navegação progressiva por município, zona e seção.

`Fonte e metodologia` permanece como conteúdo secundário no rodapé. O dashboard
não acessa Bronze, Silver ou RAW.

A publicação pública do dashboard será adicionada depois que a Gold eleitoral
for publicada, validada e fixada por uma revisão imutável.

## Arquitetura

```text
logs de urna ──► RAW ──► Bronze ──► Silver ──► Gold de logs

resultados + eleitorado oficiais ──► Gold eleitoral ──► build estático
                                                       └─► dashboard
```

As duas Golds não são misturadas. O desenho completo está em
[docs/architecture.md](docs/architecture.md), o contrato das tabelas em
[docs/data_dictionary.md](docs/data_dictionary.md) e as decisões em
[docs/decisions.md](docs/decisions.md).

## Datasets publicados

- [Silver de logs](https://huggingface.co/datasets/Andrre-M/tse-urna-ce-2026),
  revisão `6cf582bf2fbbe39eb5f0198ec68f88d7e0014ea7`;
- [Gold de logs e eleitoral](https://huggingface.co/datasets/Andrre-M/tse-urna-ce-2026-gold),
  revisão `f9d59eb4e924d3f554d2862d1e3ba1629633f7f9`.

A extensão eleitoral está em `data/electoral/` e possui manifesto, checksums,
dicionário e validação independentes da Gold de logs. Dados, builds, SQLite,
checkpoints e segredos permanecem fora do Git.

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

## Gold eleitoral local

O comando espera os sete CSVs oficiais convertidos para UTF-8 em um mesmo
diretório:

```powershell
uv run urna-etl electoral-gold --source-dir <diretorio-dos-csvs>
```

Para escolher explicitamente o destino:

```powershell
uv run python scripts/build_electoral_gold.py <fontes> <gold-destino>
uv run python scripts/validate_electoral_gold.py <gold-destino>
```

Por padrão, o build baixa e valida a revisão imutável da Gold eleitoral
publicada. As geometrias e a relação de municípios usadas no mapa vêm das APIs
oficiais do IBGE e são fornecidas como arquivos locais, sem serem incorporadas
ao repositório:

```powershell
uv run python scripts/build_dashboard.py `
  --source-dir dashboard `
  --output-dir dist `
  --geojson <malha-municipal-geojson> `
  --ibge-municipalities <municipios-ibge-json>
```

`--gold-dir` existe apenas como override explícito para desenvolvimento local.

## Limites

- O recorte foi validado somente para Ceará, 2026, primeiro turno e pleito 3220.
- Perfil cadastral, eleitores aptos por cargo e comparecimento têm universos
  oficiais distintos e não devem ser tratados como a mesma medida.
- Ausência de arquivo de log e timestamps atípicos reproduzem a fonte e,
  isoladamente, não permitem concluir nada sobre o processo eleitoral.
- O projeto é independente e não possui vínculo com o TSE.

## Licença

Código disponibilizado sob a licença MIT. Os dados permanecem sujeitos às
condições e à atribuição de suas fontes oficiais.
