# Validação da Gold eleitoral — CE 2026, primeiro turno

Gerado em: 17 de outubro de 2026

Status local e remoto: **PASS**

Dataset: `Andrre-M/tse-urna-ce-2026-gold`

Revisão imutável validada:
`f9d59eb4e924d3f554d2862d1e3ba1629633f7f9`.

## Escopo

- 184 municípios;
- 23.765 seções;
- 5 cargos;
- 6.998.494 registros no perfil cadastral;
- schema da Gold eleitoral: versão 2;
- nenhuma candidatura sem partido após a reconciliação com o cadastro oficial.

## Tabelas

| Tabela | Linhas | Bytes | SHA-256 |
|---|---:|---:|---|
| `election_overview` | 5 | 8.596 | `453baefc64639a5846e04b2d2dbefe4ff4cf21d036abc6c19af4bd64899c5726` |
| `municipality_summary` | 920 | 44.481 | `ac9285ac285c0324c191cbe4b8e473f3c35cb24a9af6be6efa896a45cd677dbd` |
| `electorate_profile` | 14.094 | 83.568 | `8789f2203dccd3be13c8f393f27407d264bf640366b5257b6fb9ca9b67b228f9` |
| `candidate_results` | 66.528 | 678.700 | `71896581cbe09630a69eac28c33d9dc16d45dd932cc1facfb034148f34dfe45d` |
| `section_summary` | 118.825 | 2.125.883 | `47ee0dd649a2a5743fb5484e75ea135581d1af593fcb0e2202b24ecfe360c867` |
| `section_results` | 2.751.489 | 24.816.698 | `e5d4aef85368aa47c2493529b1592becadbd4e0dc55f5cfc1903dda1d3e9178d` |
| `metadata` | 1 | 5.534 | `550bc2f92a5d194c39d5db5eded45c4d220a36e6001ef9e0695962a20620f49e` |

## Consistência

- `election_overview` contém uma linha por cargo;
- `municipality_summary` contém uma linha por município e cargo;
- `section_summary` contém uma linha por seção e cargo;
- `candidate_results` reconcilia com a agregação de `section_results`;
- a soma do perfil por gênero, faixa etária e faixa etária/gênero resulta em
  6.998.494 em cada dimensão;
- `metadata.registered_electors_profile` reconcilia com o perfil cadastral;
- votos de legenda (`SQ_CANDIDATO = -3`) permanecem separados de candidaturas;
- todas as candidaturas em `candidate_results` possuem partido associado.

## Reprodução

```powershell
uv run python scripts/validate_electoral_gold.py `
  data/gold_electoral/year=2026/round=1/uf=CE
```

O comando falha se uma tabela estiver ausente ou se alguma reconciliação não
fechar. Bronze, Silver, RAW e a Gold de logs não são lidos por essa validação.

