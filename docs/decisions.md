# Decisões de implementação

- O recorte validado é Ceará, eleição 2026, pleito 3220.
- SQLite guarda checkpoints; Parquet guarda os dados analíticos.
- O RAW não é alterado depois do download.
- O discovery aceita os nomes `.logjez` e `*-log.jez` encontrados na fonte.
- A extração trata contêineres ZIP e 7-Zip e rejeita caminhos inseguros.
- Bronze e Silver são escritas em lotes atômicos e retomáveis.
- Linhas não interpretadas vão para quarantine em vez de serem descartadas.
- Seções sem arquivo permanecem na tabela de cobertura.
- Timestamps fora do ano eleitoral são preservados, não corrigidos.
- Dados baixados, resultados e SQLite ficam fora do Git.
