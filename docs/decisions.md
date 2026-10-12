# Decisões

- O recorte do MVP é Ceará, eleição 2026, pleito 3220.
- SQLite guarda estado operacional; Parquet guarda dados analíticos.
- RAW é imutável e nenhum dado gerado entra no Git.
- `TSE_DATA_DIR` e `TSE_METADATA_DIR` permitem usar outro volume sem alterar
  checkpoints.
- O discovery aceita os nomes `.logjez` e `*-log.jez` publicados pelo TSE.
- A extração trata contêineres ZIP e 7-Zip e rejeita caminhos inseguros.
- Bronze e Silver são processadas em lotes atômicos e retomáveis.
- Seções sem arquivo permanecem na tabela Silver de cobertura; não são criados
  eventos artificiais.
- Timestamps fora do ano eleitoral são preservados, sinalizados e excluídos da
  coluna temporal validada.
- Cada ciclo de reconsulta das seções vazias tem checkpoint próprio no SQLite.
- O dashboard começa somente depois da publicação do dataset.
