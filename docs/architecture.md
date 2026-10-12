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

## Escala

A estratégia é:

1. validar uma seção real;
2. executar discovery do Ceará inteiro;
3. executar o piloto real (concluído: 5 arquivos, 31.947 eventos, zero rejeições);
4. processar Ceará inteiro ponta a ponta;
5. somente então decidir se Brasil inteiro agrega valor ao portfólio.
