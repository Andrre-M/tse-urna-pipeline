# Relatório de qualidade — CE 2026/3220

Gerado em: 2026-10-12T10:30:47-03:00

Status: **PASS WITH WARNINGS**

## Cobertura

- Seções no catálogo: 25,650
- Seções com discovery concluído: 25,650
- Seções com arquivo de urna: 23,765
- Seções sem arquivo publicado: 1,885
- Arquivos no manifest: 23,765
- Arquivos concluídos até Bronze: 23,765

## Bronze compactado

- Eventos válidos: 143,703,249
- Linhas em quarantine: 0
- Fontes distintas: 23,765
- Seções distintas com eventos: 23,765
- Nulos em colunas críticas: 0
- Timestamps fora de 2026: 316
- Distribuição dos anos atípicos: 2009: 62, 2028: 65, 2029: 189
- Partes Parquet: 8
- Tamanho Parquet: 1,995,230,981 bytes
- Primeiro timestamp: 2009-01-09 21:55:10
- Último timestamp: 2029-09-29 15:53:03

## Critérios

- Discovery concluído para todo o catálogo.
- Todos os arquivos encontrados concluídos até Bronze.
- Uma fonte Bronze distinta por arquivo concluído.
- Cobertura de seções consistente entre manifest e Bronze.
- Zero linhas rejeitadas e zero nulos em colunas críticas.

## Avisos

- Seções sem arquivo publicado são mantidas como cobertura ausente e podem ser
  reconsultadas com `discover-uf --refresh-empty`.
- Timestamps fora do ano eleitoral são preservados como registrados pela urna e devem
  ser tratados explicitamente na camada Silver.
