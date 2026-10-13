# Dicionário de dados

## Bronze

| Campo | Tipo | Descrição |
|---|---|---|
| `election_year` | int | Ano da eleição |
| `pleito` | string | Código do pleito no TSE |
| `uf` | string | UF da seção |
| `municipality` | string | Código TSE do município |
| `zone` | string | Zona eleitoral, 4 dígitos |
| `section` | string | Seção eleitoral, 4 dígitos |
| `source_hash` | string | Hash/diretório publicado no arquivo auxiliar do TSE |
| `source_file` | string | Nome do `.logjez` ou `*-log.jez` original |
| `source_log` | string | `logd.dat` efetivamente parseado |
| `line_number` | int | Linha no arquivo de log |
| `event_timestamp` | datetime | Data e hora do evento |
| `severity` | string | Severidade registrada no log |
| `ue_id` | string | Identificador da urna no log |
| `application` | string | Aplicação que emitiu o evento |
| `message_raw` | string | Mensagem original, sem classificação analítica |
| `mac` | string | Campo MAC/assinatura presente na linha do log |

## Observação

A camada Bronze evita inferências como `event_type=VOTE_COMPUTED`. Classificações de evento pertencem à Silver para que as regras possam evoluir sem perda do dado original.

## Silver — `events`

Partição física: `data/silver/events/year=<ano>/pleito=<pleito>/uf=<uf>`.

| Campo | Tipo | Descrição |
|---|---|---|
| `event_id` | string | Chave determinística composta pela origem e linha do log |
| `section_id` | string | Chave legível `UF-município-zona-seção` |
| `election_year` | int | Ano da eleição |
| `pleito` | string | Código do pleito no TSE |
| `uf` | string | UF em maiúsculas |
| `municipality` | string | Código TSE do município |
| `zone` | string | Zona eleitoral, 4 dígitos |
| `section` | string | Seção eleitoral, 4 dígitos |
| `source_hash` | string | Identificador publicado no arquivo auxiliar do TSE |
| `source_file` | string | Nome do arquivo de urna de origem |
| `source_log_member` | string | Caminho interno do `logd.dat` no arquivo extraído, sem diretório local |
| `line_number` | int | Linha no `logd.dat` de origem |
| `event_timestamp_recorded` | datetime | Horário preservado exatamente como registrado pela urna |
| `event_year_recorded` | int | Ano derivado do horário registrado |
| `timestamp_status` | string | `valid` ou `outside_election_year` |
| `event_timestamp_validated` | datetime, nullable | Horário para análise temporal; nulo quando o ano diverge do ano eleitoral |
| `event_date_validated` | date, nullable | Data derivada do horário validado |
| `severity` | string | Severidade sem espaços e em maiúsculas |
| `ue_id` | string | Identificador da urna no log |
| `application` | string | Aplicação sem espaços e em maiúsculas |
| `message` | string | Mensagem do evento, preservada sem classificação especulativa |
| `mac` | string | Campo MAC/assinatura registrado no log |

Os 316 eventos de 2009, 2028 e 2029 mantêm
`event_timestamp_recorded`, recebem `timestamp_status = outside_election_year` e
ficam com as colunas temporais validadas nulas. A Silver não tenta inferir a data
correta.

## Silver — `section_coverage`

Partição física:
`data/silver/section_coverage/year=<ano>/pleito=<pleito>/uf=<uf>`.

| Campo | Tipo | Descrição |
|---|---|---|
| `section_id` | string | Chave legível `UF-município-zona-seção` |
| `election_year` | int | Ano da eleição |
| `pleito` | string | Código do pleito no TSE |
| `uf` | string | UF em maiúsculas |
| `municipality` | string | Código TSE do município |
| `zone` | string | Zona eleitoral, 4 dígitos |
| `section` | string | Seção eleitoral, 4 dígitos |
| `discovery_status` | string | Estado operacional da consulta ao `aux.json` |
| `publication_status` | string | `published`, `not_published`, `discovery_pending` ou `discovery_failed` |
| `files_found` | int | Quantidade de arquivos de urna localizados para a seção |
| `has_published_file` | bool | Indica se ao menos um arquivo foi publicado |
| `last_checked_at` | datetime, nullable | Última conclusão registrada do discovery |

As 1.885 seções sem arquivo publicado permanecem nessa tabela com
`publication_status = not_published`. Elas não são removidas do denominador de
cobertura e não geram linhas artificiais em `events`.

## Gold

Partição física: `data/gold/year=<ano>/pleito=<pleito>/uf=<uf>`. Cada tabela é
gravada em seu próprio subdiretório. `municipality_name` vem do par `cd`/`nm`
do catálogo estadual usado no discovery; códigos ausentes nesse catálogo são
rejeitados.

### `overview`

Uma linha por eleição, pleito e UF.

| Campo | Tipo | Descrição |
|---|---|---|
| `election_year` | int | Ano da eleição |
| `pleito` | string | Código do pleito no TSE |
| `uf` | string | UF em maiúsculas |
| `catalog_sections` | int | Seções presentes em `section_coverage` |
| `published_sections` | int | Seções com `publication_status = published` |
| `unpublished_sections` | int | Seções com `publication_status = not_published` |
| `sections_with_events` | int | Seções com ao menos um evento Silver |
| `municipalities` | int | Municípios distintos na cobertura |
| `zones` | int | Pares município/zona distintos na cobertura |
| `total_events` | int | Total de eventos Silver |
| `valid_timestamp_events` | int | Eventos com `timestamp_status = valid` |
| `temporal_outlier_events` | int | Eventos com `timestamp_status = outside_election_year` |
| `applications` | int | Aplicações distintas em todos os eventos |
| `severities` | int | Severidades distintas em todos os eventos |
| `coverage_rate` | float | `published_sections / catalog_sections` |
| `first_valid_event_at` | datetime, nullable | Menor timestamp validado |
| `last_valid_event_at` | datetime, nullable | Maior timestamp validado |

### `coverage`

Uma linha por seção do catálogo. A contagem de eventos é obtida por `section_id`;
seções sem correspondência em `events` recebem zero.

| Campo | Tipo | Descrição |
|---|---|---|
| `section_id` | string | Chave `UF-município-zona-seção` |
| `election_year` | int | Ano da eleição |
| `pleito` | string | Código do pleito no TSE |
| `uf` | string | UF em maiúsculas |
| `municipality` | string | Código TSE do município |
| `municipality_name` | string | Nome do município no catálogo estadual |
| `zone` | string | Zona eleitoral, 4 dígitos |
| `section` | string | Seção eleitoral, 4 dígitos |
| `publication_status` | string | Estado de publicação herdado da Silver |
| `has_published_file` | bool | Indica se havia arquivo publicado |
| `event_count` | int | Eventos Silver associados à seção |
| `has_events` | bool | Indica se `event_count > 0` |

### `event_timeline`

Somente eventos com `timestamp_status = valid`, agregados por município, zona,
data, hora e severidade.

| Campo | Tipo | Descrição |
|---|---|---|
| `election_year` | int | Ano da eleição |
| `pleito` | string | Código do pleito no TSE |
| `uf` | string | UF em maiúsculas |
| `municipality` | string | Código TSE do município |
| `municipality_name` | string | Nome do município no catálogo estadual |
| `zone` | string | Zona eleitoral, 4 dígitos |
| `event_date` | date | Data validada do evento |
| `event_hour` | int | Hora local registrada, de 0 a 23 |
| `severity` | string | Severidade normalizada |
| `event_count` | int | Eventos do grupo |

### `applications`

Todos os eventos, inclusive os temporalmente atípicos, agregados por município,
zona, aplicação e severidade.

| Campo | Tipo | Descrição |
|---|---|---|
| `election_year` | int | Ano da eleição |
| `pleito` | string | Código do pleito no TSE |
| `uf` | string | UF em maiúsculas |
| `municipality` | string | Código TSE do município |
| `municipality_name` | string | Nome do município no catálogo estadual |
| `zone` | string | Zona eleitoral, 4 dígitos |
| `application` | string | Aplicação normalizada |
| `severity` | string | Severidade normalizada |
| `event_count` | int | Eventos do grupo |

### `temporal_outliers`

Somente eventos com `timestamp_status = outside_election_year`, agregados por
seção, ano registrado, aplicação e severidade.

| Campo | Tipo | Descrição |
|---|---|---|
| `election_year` | int | Ano esperado para a eleição |
| `pleito` | string | Código do pleito no TSE |
| `uf` | string | UF em maiúsculas |
| `municipality` | string | Código TSE do município |
| `municipality_name` | string | Nome do município no catálogo estadual |
| `zone` | string | Zona eleitoral, 4 dígitos |
| `section` | string | Seção eleitoral, 4 dígitos |
| `section_id` | string | Chave `UF-município-zona-seção` |
| `event_year_recorded` | int | Ano preservado do timestamp original |
| `application` | string | Aplicação normalizada |
| `severity` | string | Severidade normalizada |
| `event_count` | int | Eventos do grupo |
| `first_recorded_event_at` | datetime | Menor timestamp registrado no grupo |
| `last_recorded_event_at` | datetime | Maior timestamp registrado no grupo |

As tabelas Gold só são publicadas quando todos os Parquets Silver da partição
foram agregados. Execuções limitadas persistem parciais reiniciáveis, mas não
substituem uma Gold completa.
