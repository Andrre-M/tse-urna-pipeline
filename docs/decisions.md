# Decisões de implementação

## Processamento e armazenamento

Polars faz as transformações e agregações; Parquet permite ler apenas as
colunas necessárias e comprimir os resultados com Zstandard. O processamento
atual funciona com essas ferramentas, sem uma segunda camada de consultas.

SQLite registra downloads e checkpoints para retomar uma execução interrompida.
Os dados analíticos ficam nos Parquets. As escritas usam lotes e diretórios
temporários para evitar que a próxima etapa leia uma saída incompleta.

## Preservação da fonte

Seções sem arquivo continuam na cobertura porque removê-las mudaria o universo
da análise. Linhas não reconhecidas ficam em quarentena para investigação.

Os timestamps atípicos são preservados porque não há informação suficiente
para atribuir uma data correta a eles. A linha do tempo os exclui; as outras
contagens e a tabela de anomalias os mantêm.

## Resultados e dashboard

Logs registram eventos técnicos; os votos vêm dos resultados por seção e o
perfil vem do cadastro eleitoral. Cada fonte conserva suas medidas e validações.
Essa separação evita usar cadastro como comparecimento ou eventos como votos.

O site usa arquivos estáticos divididos por cargo e município/zona para carregar
os detalhes conforme a consulta. A revisão fixada da Gold e os checksums evitam
que uma atualização do dataset altere silenciosamente os dados publicados.

## Detalhes do formato e da execução

- O recorte validado é Ceará, eleição 2026, pleito 3220.
- SQLite guarda checkpoints; Parquet guarda os dados analíticos.
- O RAW não é alterado depois do download.
- O discovery aceita os nomes `.logjez` e `*-log.jez` encontrados na fonte.
- A extração trata contêineres ZIP e 7-Zip e rejeita caminhos inseguros.
- Bronze e Silver são escritas em lotes atômicos e retomáveis.
- Linhas não interpretadas vão para quarantine em vez de serem descartadas.
- Seções sem arquivo permanecem na tabela de cobertura.
- Timestamps fora do ano eleitoral são preservados, não corrigidos.
- A Gold usa o catálogo estadual do discovery para associar código e nome do município.
- Agregações Gold limitadas geram apenas parciais; tabelas finais exigem toda a Silver.
- A linha do tempo exclui timestamps atípicos; as demais contagens os preservam.
- Dados baixados, resultados e SQLite ficam fora do Git.
- A Gold eleitoral é independente da Gold de logs e nunca usa eventos técnicos como votos.
- O dashboard consome somente a Gold eleitoral; Bronze, Silver e RAW não fazem parte do frontend.
- As transformações usam Polars; não há dependência de DuckDB.
- Códigos de município, zona e seção permanecem como texto para preservar zeros à esquerda.
- Perfil cadastral, aptos por cargo e comparecimento são universos distintos e permanecem nomeados separadamente.
- `SQ_CANDIDATO = -3` identifica voto de legenda; apenas identificadores positivos são tratados como candidaturas.
- A correspondência das geometrias do IBGE com códigos TSE é validada para os 184 municípios antes do build.
- O dashboard é estático e dividido em arquivos por cargo e município/zona para carregamento progressivo.
- O build publicado baixa a revisão fixada da Gold eleitoral; `--gold-dir` permite testar uma cópia local.
