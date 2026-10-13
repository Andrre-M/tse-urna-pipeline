# Arquitetura

## Fluxo

```text
catálogo estadual
       │
       ▼
discovery por seção ──► manifest SQLite
       │
       ▼
    RAW imutável
       │
       ▼
extração do logd.dat
       │
       ▼
 Bronze + quarantine
       │
       ▼
 compactação e qualidade
       │
       ▼
 Silver events + section_coverage
       │
       ▼
 Gold agregada para o dashboard
```

O catálogo estadual define o universo de seções. Para cada seção, o discovery
consulta o `aux.json` e registra os arquivos de urna encontrados. O SQLite
guarda o andamento das etapas; os dados permanecem em arquivos.

## Armazenamento

Os diretórios podem ser configurados por `TSE_DATA_DIR` e
`TSE_METADATA_DIR`. Isso permite manter os dados em outro volume sem colocar
arquivos gerados no repositório.

O RAW é imutável. Bronze e Silver usam Parquet com compressão Zstandard. Linhas
que o parser não reconhece são gravadas em quarantine com arquivo, número da
linha, conteúdo e motivo.

## Retomada

Discovery, download, extração e transformação registram checkpoints. Os lotes
Bronze são identificados pelas fontes que contêm e só substituem o destino após
uma escrita completa. A Silver repete a mesma estratégia para cada parte do
Bronze compactado.

Reexecutar uma etapa reutiliza o que já terminou. O parâmetro `--limit` serve
para testar e avançar em lotes menores; ele não altera a identidade das saídas.

## Cobertura

`section_coverage` tem uma linha para cada seção do catálogo. Se o TSE não
publicou arquivo, a seção recebe `publication_status = not_published` e continua
no denominador de cobertura. Nenhum evento é inventado para preencher essa
ausência.

As reconsultas de seções vazias têm checkpoint próprio. Se forem interrompidas,
retomam apenas as seções ainda não consultadas naquele ciclo.

## Timestamps

`event_timestamp_recorded` preserva o horário encontrado no log. Quando o ano
diverge do ano eleitoral, `timestamp_status` recebe
`outside_election_year` e as colunas temporais validadas ficam nulas. O pipeline
não tenta adivinhar a data correta.

## Gold

A Gold é derivada somente da Silver. Cada Parquet de eventos gera agregações
parciais com checkpoint próprio; a execução seguinte reutiliza as partes já
concluídas. As cinco tabelas finais só são promovidas depois que todas as partes
da entrada foram processadas e as contagens de consistência fecharam.

O nome do município é associado pelo código TSE usando o catálogo estadual
cacheado no discovery. O dashboard lê apenas `overview`, `coverage`,
`event_timeline`, `applications` e `temporal_outliers`.

## Dashboard

O dashboard é um site estático. Durante a publicação, um gerador em Python e
Polars baixa os cinco Parquets da revisão Gold fixada, valida hashes, schemas e
reconciliações e produz JSON somente no artefato do GitHub Pages. O navegador
usa Plotly para filtros e gráficos; não há servidor de aplicação nem acesso às
camadas Silver, Bronze ou RAW.
