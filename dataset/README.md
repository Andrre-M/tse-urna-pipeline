---
language:
  - pt
license: other
license_name: Termos de Dados Abertos do TSE
license_link: https://dadosabertos.tse.jus.br/pages/perguntasfrequentes
pretty_name: Logs públicos de urnas — Ceará 2026/3220
size_categories:
  - 100M<n<1B
tags:
  - tabular
  - elections
  - brazil
  - tse
configs:
  - config_name: events
    default: true
    data_files:
      - split: full
        path: data/events/*.parquet
  - config_name: section_coverage
    data_files:
      - split: full
        path: data/section_coverage/*.parquet
---

# Logs públicos de urnas — Ceará 2026/3220

Este dataset organiza em Parquet os logs públicos de urnas divulgados pelo
Tribunal Superior Eleitoral para todas as seções do Ceará no pleito 3220 da
eleição de 2026.

Versão preparada: `0.4.0`.

São duas configurações:

- `events`: 143.703.249 eventos de 23.765 seções com arquivo publicado;
- `section_coverage`: as 25.650 seções do catálogo, inclusive as 1.885 para as
  quais não havia arquivo publicado após a reconsulta.

O processamento foi concluído em 12 de outubro de 2026, com zero linha em
quarentena. A avaliação geral foi `PASS WITH WARNINGS`.

## Decisões de tratamento

O horário original nunca foi corrigido por inferência. Os 316 registros cujo
ano difere de 2026 mantêm `event_timestamp_recorded`, recebem
`timestamp_status = outside_election_year` e ficam sem valor nas colunas
temporais validadas.

As 1.885 seções sem arquivo permanecem em `section_coverage` com
`publication_status = not_published`. Elas contam no universo de cobertura e
não geram eventos artificiais.

## Arquivos de apoio

- `DATA_DICTIONARY.md`: campos e tipos das duas configurações;
- `QUALITY_REPORT.md`: cobertura, critérios e avisos de qualidade;
- `manifest.json`: contagens, tamanhos e SHA-256 de cada Parquet;
- `checksums.sha256`: lista de hashes para verificação independente.

O código do pipeline e o histórico das decisões estão no repositório
[Andrre-M/tse-urna-pipeline](https://github.com/Andrre-M/tse-urna-pipeline).

## Origem e licença

Fonte: [Portal de Dados Abertos do TSE](https://dadosabertos-novo.tse.jus.br/).
O uso dos dados segue os
[termos de dados abertos do TSE](https://dadosabertos.tse.jus.br/pages/perguntasfrequentes),
com atribuição da fonte. A licença MIT do repositório vale para o código do
pipeline, não substitui os termos aplicáveis aos dados de origem.

Este é um projeto independente, sem vínculo com o TSE. A ausência de arquivo
para uma seção e os timestamps atípicos refletem o material encontrado na
fonte e não devem ser interpretados, isoladamente, como evidência sobre o
processo eleitoral.
