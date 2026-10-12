# Estado do projeto

Atualizado em 12 de outubro de 2026.

## Concluído

- Catálogo completo do Ceará para 2026/3220: 25.650 seções.
- Discovery finalizado: 23.765 arquivos publicados e 1.885 seções sem arquivo.
- Os 23.765 arquivos passaram por download, extração e Bronze.
- Bronze compactado: 143.703.249 eventos, 8 Parquets, zero quarantine e zero
  nulos críticos.
- Silver de eventos: 143.703.249 linhas em 23.765 seções.
- Silver de cobertura: 25.650 linhas, incluindo as 1.885 seções sem arquivo.
- Os 316 timestamps fora de 2026 foram preservados, sinalizados e excluídos da
  coluna temporal validada.
- O ciclo de reconsulta das 1.885 seções vazias terminou sem encontrar arquivos
  novos.
- Ruff limpo e 40 testes aprovados.

Dados e SQLite estão em `D:\tse-urna-pipeline`. A cópia original em `C:` não foi
removida. Dados gerados continuam fora do Git.

Relatório: `docs/quality_report_ce_2026_3220.md`.

## Pendente

1. Definir o pacote e o destino da publicação.
2. Publicar o dataset Silver.

Dashboard continua fora do escopo até a publicação.
