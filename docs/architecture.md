# Arquitetura

## Decisão central

O MVP é o **Ceará completo**. A seção isolada existe somente para teste, debug e validação de formato.

O TSE é a source of truth. O pipeline mantém checkpoints locais suficientes para retomar discovery, ingestão e transformação sem reprocessar trabalho concluído.

```text
                           ┌──────────────────┐
                           │       TSE        │
                           └────────┬─────────┘
                                    │
                         catálogo UF│ *-cs.json
                                    ▼
                           ┌──────────────────┐
                           │ Sections manifest│
                           │ CE inteiro       │
                           └────────┬─────────┘
                                    │
                         discovery │ -aux.json
                                    ▼
                           ┌──────────────────┐
                           │ Files manifest   │
                           │ .logjez          │
                           └────────┬─────────┘
                                    │
                         ingestion │
                                    ▼
                           ┌──────────────────┐
                           │ RAW imutável     │
                           └────────┬─────────┘
                                    │
                         extraction│ 7-Zip
                                    ▼
                           ┌──────────────────┐
                           │ logd.dat         │
                           └────────┬─────────┘
                                    │
                            parsing│
                                    ▼
                           ┌──────────────────┐
                           │ Bronze Parquet   │
                           └────────┬─────────┘
                                    │
                    quality/compact│ normalize
                                    ▼
                           ┌──────────────────┐
                           │ Silver Parquet   │
                           └──────────────────┘
```

## Manifest em dois níveis

### `sections`

Registra toda seção eleitoral descoberta no catálogo estadual e o estado da consulta de seu `aux.json`.

```text
pending → discovered | failed
```

Isso torna o discovery do Ceará reiniciável: uma execução interrompida não precisa consultar novamente as seções já concluídas.

Reconsultas de seções vazias usam um ciclo persistido em
`section_refresh_runs`. Cada ciclo recebe um ID e a seção registra
`last_refresh_id` somente após uma consulta bem-sucedida. Um comando
interrompido retoma as seções ainda sem esse ID; falhas continuam pendentes e
um novo ciclo só começa depois que o anterior é concluído.

### `files`

Registra cada `.logjez` encontrado e controla os estágios posteriores.

```text
download: pending → downloaded | failed
extract:  pending → extracted  | failed
parse:    pending → parsed     | failed
```

SQLite foi escolhido para o estado operacional porque é local, transacional, gratuito e suficiente para metadados. Ele não é o warehouse analítico.

Os diretórios de dados e estado podem ficar fora do checkout por meio de
`TSE_DATA_DIR` e `TSE_METADATA_DIR`. Isso permite usar outro volume sem alterar a
identidade dos checkpoints nem versionar dados gerados.

## Idempotência

A URL da seção e a URL de cada arquivo são `UNIQUE`. Reexecutar discovery atualiza metadados sem duplicar registros.

Downloads existentes são reutilizados e recebem SHA-256 local. Respostas transitórias
(`408`, `425`, `429` e `5xx`) usam retry com backoff/`Retry-After`; erros permanentes não
consomem tentativas desnecessárias.

## RAW

RAW não é transformado:

```text
data/raw/y=2026/p=3220/u=CE/m=13005/z=0030/s=0082/file-00000001.jez
```

## Bronze

Bronze preserva a mensagem original e acrescenta metadados de origem.

O Bronze agrupa arquivos-fonte em lotes determinísticos. Cada lote escreve partes com
quantidade-alvo de linhas e um `_SUCCESS.json`; uma interrupção antes do marcador reconstrói
o mesmo lote sem duplicar eventos. A compactação posterior combina partes pequenas por
`year/pleito/uf` usando execução streaming do Polars.

## Quarantine

Linhas não interpretadas não são descartadas. Elas mantêm arquivo-fonte, número da linha,
conteúdo bruto e motivo em um JSONL idempotente por lote.

## Silver

A Silver tem dois conjuntos conformados e particionados por
`year/pleito/uf`:

- `silver/events`: um evento por linha do Bronze, com identificadores estáveis,
  nomes normalizados e tratamento temporal explícito;
- `silver/section_coverage`: uma linha por seção do catálogo, inclusive quando o
  TSE não publicou arquivo de urna.

`section_coverage` é a referência para denominadores e cobertura. Uma seção
descoberta com `files_found = 0` recebe
`publication_status = not_published`; ela não gera evento sintético nem é
descartada. Estados `pending` e `failed` permanecem distintos para que ausência
de publicação não seja confundida com falha do pipeline.

Em `events`, `event_timestamp_recorded` preserva exatamente o horário do Bronze.
`timestamp_status` indica se o ano registrado coincide com o ano eleitoral e
`event_timestamp_validated` só é preenchido nessa condição. Não há correção ou
clamp sem uma fonte oficial capaz de determinar o horário pretendido. Assim, os
316 registros fora de 2026 continuam auditáveis, mas ficam fora de séries
temporais baseadas na coluna validada.

Cada parte compactada do Bronze é um lote determinístico da Silver. O resultado
é escrito em arquivo temporário, promovido atomicamente e acompanhado de um
checkpoint com o fingerprint da fonte. Reexecuções reutilizam lotes concluídos;
`--limit` restringe somente lotes pendentes. O `_SUCCESS.json` da partição só é
publicado quando todas as fontes esperadas e a cobertura de seções estão
concluídas.

## Escala

A estratégia é:

1. validar uma seção real;
2. executar discovery do Ceará inteiro;
3. executar o piloto real (concluído: 5 arquivos, 31.947 eventos, zero rejeições);
4. processar Ceará inteiro ponta a ponta;
5. construir e validar a Silver reiniciável;
6. publicar o dataset antes de qualquer dashboard;
7. somente então decidir se Brasil inteiro agrega valor ao portfólio.
