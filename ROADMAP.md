# Roadmap

## v0.1 — coração do pipeline

- [x] Estrutura de pacote Python
- [x] URL builder
- [x] Parser do `-aux.json`
- [x] Manifest SQLite de arquivos
- [x] Downloader idempotente com retry
- [x] SHA-256 local
- [x] Extração recursiva de `.logjez` / `.jez`
- [x] Parser de `logd.dat`
- [x] Bronze Parquet + quarantine
- [x] Testes unitários
- [x] CI com GitHub Actions

## v0.2 — Ceará como MVP

- [x] Ler `{uf}-pXXXXXX-cs.json`
- [x] Expandir municípios → zonas → seções
- [x] Manifest/checkpoint de discovery por seção
- [x] Discovery concorrente dos `aux.json`
- [x] Retomada sem repetir seções concluídas
- [x] Limite de execução para testes (`--limit`)
- [x] Cache do catálogo estadual
- [x] Validação end-to-end contra o TSE real (piloto de 5 seções)
- [x] Métricas completas de discovery/ingestão

## v0.3 — processamento eficiente do Ceará

- [x] Bronze escrito em lotes
- [x] Evitar small files
- [x] Compaction por partição lógica
- [x] Quarantine particionada
- [x] Relatório de qualidade da UF
- [ ] Benchmark de memória, disco e tempo
- [ ] Silver normalizada

## v0.4 — publicação

- [ ] Dataset Silver do Ceará versionado
- [ ] Publicação gratuita em Parquet
- [ ] Workflow reprodutível via GitHub Actions
- [ ] Data dictionary final
- [ ] Métricas de execução no README

## v0.5 — expansão opcional

- [ ] Tornar qualquer UF uma execução de primeira classe
- [ ] Execução multi-UF
- [ ] Brasil completo, se custo/volume fizer sentido

## Fora do núcleo de engenharia

- Dashboard
- Métricas analíticas de duração de votação
- Rankings
- Mapas

Esses itens serão consumidores da Silver/Gold, não responsabilidades do pipeline principal.
