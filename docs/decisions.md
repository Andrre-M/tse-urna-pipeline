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
- O pacote público usa Parquet e separa `events` de `section_coverage`; os
  arquivos de origem e o SQLite nunca fazem parte da publicação.
- O Hugging Face é o destino operacional recomendado para a primeira versão por
  aceitar Parquet diretamente, permitir retomada do envio e expor configurações
  distintas. A conta proprietária precisa ser confirmada antes de qualquer ação
  externa. Uma troca de destino deve ser registrada aqui antes do envio.
- A primeira versão pública será `0.4.0`, igual ao manifesto preparado. Uma
  versão `1.0.0` só será adotada por decisão explícita após a publicação ter sido
  validada.
- O dashboard começa somente depois da publicação do dataset.
