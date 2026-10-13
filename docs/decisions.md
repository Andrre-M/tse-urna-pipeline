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
- A Gold usa o catálogo estadual do discovery para associar código e nome do município.
- Agregações Gold limitadas geram apenas parciais; tabelas finais exigem toda a Silver.
- A linha do tempo exclui timestamps atípicos; as demais contagens os preservam.
- Dados baixados, resultados e SQLite ficam fora do Git.
- O dashboard é estático e publicado no GitHub Pages para evitar hibernação de
  servidor; seus dados são gerados apenas da revisão Gold publicada e não são
  versionados no repositório.
