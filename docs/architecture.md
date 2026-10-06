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

## Idempotência

A URL da seção e a URL de cada arquivo são `UNIQUE`. Reexecutar discovery atualiza metadados sem duplicar registros.

Downloads existentes são reutilizados e recebem SHA-256 local.

## RAW

RAW não é transformado:

```text
data/raw/year=2026/pleito=3220/uf=CE/municipality=13897/zone=0003/section=0444/<hash>/<arquivo>.logjez
```

## Bronze

Bronze preserva a mensagem original e acrescenta metadados de origem.

A implementação atual escreve por arquivo, adequada para validação funcional. Para processar/publicar o Ceará completo, a v0.3 introduzirá batch writing e compaction para evitar milhares de Parquets pequenos.

## Quarantine

Linhas não interpretadas não são descartadas. Elas mantêm arquivo-fonte, número da linha, conteúdo bruto e motivo.

## Escala

A estratégia é:

1. validar uma seção real;
2. executar discovery do Ceará inteiro;
3. otimizar a escrita/compaction;
4. processar Ceará ponta a ponta;
5. somente então decidir se Brasil inteiro agrega valor ao portfólio.
