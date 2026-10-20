# Arquitetura

## Visão geral

O projeto possui dois fluxos analíticos separados. Logs técnicos nunca são
usados para calcular votos, comparecimento ou resultados eleitorais.

```text
                         PIPELINE DE LOGS

catálogo estadual ─► discovery ─► RAW ─► Bronze ─► Silver ─► Gold de logs
                         │                    │
                         └─ SQLite            └─ qualidade e cobertura

                       PIPELINE ELEITORAL

resultados por seção ───────┐
detalhes de votação ────────┼─► Gold eleitoral ─► build ─► dashboard estático
perfil do eleitorado ───────┤
cadastro de candidaturas ───┘
```

## Pipeline de logs

O catálogo estadual define o universo de seções. Para cada seção, o discovery
consulta o `aux.json` e registra os arquivos encontrados. O SQLite guarda o
andamento operacional; os dados permanecem em arquivos.

O RAW é imutável. Bronze e Silver usam Parquet com compressão Zstandard. Linhas
que o parser não reconhece são gravadas em quarantine com arquivo, número da
linha, conteúdo e motivo.

`section_coverage` mantém uma linha para cada seção do catálogo. Se o TSE não
publicou arquivo, a seção recebe `publication_status = not_published` e
permanece no denominador de cobertura. Nenhum evento é inventado.

`event_timestamp_recorded` preserva o horário encontrado no log. Quando o ano
diverge do ano eleitoral, o evento recebe
`timestamp_status = outside_election_year`; o pipeline não tenta adivinhar uma
data correta. Os 316 eventos atípicos continuam na Gold de logs.

A Gold de logs é derivada somente da Silver e contém `overview`, `coverage`,
`event_timeline`, `applications` e `temporal_outliers`.

## Pipeline eleitoral

A Gold eleitoral é independente da Gold de logs. Ela combina sete arquivos
oficiais do TSE convertidos para UTF-8:

- votação por seção para cargos estaduais e Presidência;
- detalhes de votação por seção para os dois escopos;
- perfil cadastral do eleitorado do Ceará;
- cadastro de candidaturas estaduais e presidenciais.

O processamento usa Polars, normaliza códigos territoriais como texto, mantém
as medidas por cargo e classifica separadamente candidaturas, votos de legenda,
brancos e nulos. `SQ_CANDIDATO = -3` é tratado como voto de legenda; apenas
identificadores positivos representam candidaturas.

As sete tabelas resultantes são promovidas de forma atômica somente depois da
escrita completa. A validação reconcilia os resultados municipais com as
seções, as dimensões do perfil cadastral e os metadados de candidaturas.

## Dashboard estático

Por padrão, `scripts/build_dashboard.py` baixa a revisão da Gold eleitoral
fixada no código e confere o hash do manifesto e dos sete Parquets. Os arquivos
validados ficam em cache. Para desenvolvimento, `--gold-dir` permite indicar
uma cópia local.

O build gera:

- um atlas estadual com indicadores, municípios, eleitorado e índice de seções;
- um arquivo por cargo para os resultados de candidaturas;
- um arquivo por par município/zona para carregamento progressivo do explorador;
- geometrias municipais associadas ao código TSE pelo nome oficial do IBGE.

O frontend não executa consultas em Bronze, Silver ou RAW e não requer servidor
de aplicação. Um servidor HTTP simples é suficiente para a prévia local.

## Armazenamento e retomada

`TSE_DATA_DIR` e `TSE_METADATA_DIR` permitem manter dados e estado operacional
fora do checkout. Discovery, download, extração e transformação registram
checkpoints. Escritas analíticas usam diretórios temporários e promoção atômica
para evitar saídas parciais.

Dados, `dist/`, SQLite, checkpoints, caches e segredos não são versionados.

## Publicação

A publicação do dashboard depende desta ordem:

1. construir e validar a Gold eleitoral;
2. publicar os Parquets em `Andrre-M/tse-urna-ce-2026-gold`;
3. validar a cópia remota e fixar sua revisão imutável;
4. reconstruir o dashboard consumindo somente a revisão fixada no build;
5. publicar o artefato estático e conferir o carregamento da página e dos dados.
