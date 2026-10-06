# Dicionário de dados — Bronze

| Campo | Tipo | Descrição |
|---|---|---|
| `election_year` | int | Ano da eleição |
| `pleito` | string | Código do pleito no TSE |
| `uf` | string | UF da seção |
| `municipality` | string | Código TSE do município |
| `zone` | string | Zona eleitoral, 4 dígitos |
| `section` | string | Seção eleitoral, 4 dígitos |
| `source_hash` | string | Hash/diretório publicado no arquivo auxiliar do TSE |
| `source_file` | string | Nome do `.logjez` original |
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
