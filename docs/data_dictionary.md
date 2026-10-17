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

## Gold eleitoral

Partição física:
`data/gold_electoral/year=<ano>/round=<turno>/uf=<uf>/<tabela>`.

Esta Gold é independente da Gold de logs. Resultados eleitorais, perfil
cadastral e eventos técnicos não são combinados.

### Campos territoriais e eleitorais comuns

| Campo | Tipo | Descrição |
|---|---|---|
| `election_year` | int | Ano da eleição ou do cadastro |
| `round` | int | Turno eleitoral; ausente apenas em `electorate_profile` |
| `uf` | string | UF em maiúsculas |
| `municipality_code` | string | Código TSE do município, 5 dígitos |
| `municipality_name` | string | Nome oficial do município |
| `zone` | string | Zona eleitoral, 4 dígitos |
| `section` | string | Seção eleitoral, 4 dígitos |
| `section_id` | string | Chave `UF-município-zona-seção` |
| `office_code` | int | Código do cargo no TSE |
| `office` | string | Nome do cargo |

### Medidas de votação comuns

| Campo | Tipo | Descrição |
|---|---|---|
| `eligible_voters` | int | Eleitores aptos no universo oficial do cargo |
| `turnout` | int | Comparecimento oficial |
| `abstentions` | int | Abstenções oficiais |
| `nominal_votes` | int | Votos nominais |
| `party_votes` | int | Votos de legenda |
| `blank_votes` | int | Votos brancos |
| `null_votes` | int | Votos nulos |
| `separately_annulled_votes` | int | Votos anulados apurados em separado |
| `valid_votes` | int | Soma de votos nominais e de legenda |
| `total_votes` | int | Soma das categorias de voto |
| `turnout_rate` | float | `turnout / eligible_voters` |
| `abstention_rate` | float | `abstentions / eligible_voters` |
| `blank_vote_rate` | float | `blank_votes / total_votes` |
| `null_vote_rate` | float | `null_votes / total_votes` |

Perfil cadastral, aptos por cargo e comparecimento têm universos oficiais
distintos; campos com nomes diferentes não devem ser somados ou substituídos.

### `election_overview`

Uma linha por cargo. Além das medidas comuns, contém:

| Campo | Tipo | Descrição |
|---|---|---|
| `election_code` | int | Código da eleição no TSE |
| `election_name` | string | Nome da eleição |
| `election_date` | string | Data publicada na fonte |

### `municipality_summary`

Uma linha por município e cargo. Contém os campos da visão estadual acrescidos
de `municipality_code` e `municipality_name`.

### `electorate_profile`

Perfil cadastral agregado por município e dimensão.

| Campo | Tipo | Descrição |
|---|---|---|
| `dimension` | string | `gender`, `age_band`, `education` ou `age_gender` |
| `category` | string | Categoria principal da dimensão |
| `subcategory` | string, nullable | Gênero quando `dimension = age_gender`; nulo nas demais dimensões |
| `registered_electors` | int | Eleitores cadastrados no grupo |
| `biometric_electors` | int | Eleitores com biometria no grupo |
| `electors_with_disability` | int | Eleitores com deficiência no grupo |
| `electors_with_social_name` | int | Eleitores com nome social no grupo |

Em `age_gender`, `category` contém a faixa etária e `subcategory` contém o
gênero. A soma por faixa reconcilia com `age_band`; a soma por gênero reconcilia
com `gender`. O perfil não representa comparecimento ou resultado eleitoral.

### `candidate_results`

Resultados agregados por município, cargo e opção de voto.

| Campo | Tipo | Descrição |
|---|---|---|
| `ballot_number` | int | Número digitado ou código especial de voto |
| `ballot_name` | string | Nome publicado para a opção de voto |
| `candidate_id` | int, nullable | Sequencial do candidato no TSE |
| `result_type` | string | `candidate` ou `party` |
| `votes` | int | Votos da opção no município |
| `candidate_number` | int, nullable | Número da candidatura |
| `candidate_name` | string, nullable | Nome de urna |
| `candidate_full_name` | string, nullable | Nome completo |
| `party_abbreviation` | string, nullable | Sigla partidária |
| `party_name` | string, nullable | Nome do partido |
| `candidacy_status` | string, nullable | Situação da candidatura |
| `round_result_status` | string, nullable | Resultado da candidatura no turno |

Linhas com `result_type = party` representam votos de legenda e não recebem
metadados de candidatura. Apenas identificadores positivos são candidatos.

### `section_summary`

Uma linha por seção e cargo, com as medidas de votação comuns e:

| Campo | Tipo | Descrição |
|---|---|---|
| `voting_place_code` | string | Código do local de votação |
| `voting_place_name` | string | Nome do local de votação |
| `voting_place_address` | string | Endereço publicado para o local |
| `section_installed` | string | Indicador de seção instalada |
| `section_annulled` | string | Indicador de seção anulada |

### `section_results`

Resultados por seção, cargo e opção de voto. Contém os campos de identificação
de `candidate_results`, além de município, zona, seção e `section_id`.
Também preserva `blank` e `null` em `result_type`.

### `metadata`

Uma linha descrevendo o pacote publicado.

| Campo | Tipo | Descrição |
|---|---|---|
| `schema_version` | int | Versão do contrato da Gold eleitoral |
| `scope` | string | Escopo declarado do pacote |
| `source_authority` | string | Autoridade responsável pelas fontes |
| `registered_electors_profile` | int | Total reconciliado do perfil cadastral |
| `presidential_eligible_voters` | int | Aptos no universo oficial de Presidência |
| `limitations` | string | Limitações essenciais de interpretação |
| `source_files` | string | Lista JSON dos arquivos de origem |
