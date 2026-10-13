# Validação da Gold — CE 2026/3220

Gerado em: 2026-10-13

Status: **PASS**

## Totais

- 143.703.249 eventos;
- 143.702.933 eventos com timestamp válido;
- 316 eventos com timestamp fora de 2026;
- 25.650 seções no catálogo;
- 23.765 seções publicadas e com eventos;
- 1.885 seções não publicadas e sem eventos;
- 184 municípios e 205 pares município/zona;
- 9 aplicações e 5 severidades.

Os anos atípicos reproduzem a Silver: 2009 com 62 eventos, 2028 com 65 e
2029 com 189.

## Tabelas

| Tabela | Linhas | Bytes | SHA-256 |
|---|---:|---:|---|
| `overview` | 1 | 6.552 | `2b29c6e37c2f3e15ca4a50ffea6893093c0985b440fbd827987b552546a1614e` |
| `coverage` | 25.650 | 114.825 | `ecf1a29501333d133f76f4be1023e92404acd4ddb2f1a1a67d0b3a4b8a616135` |
| `event_timeline` | 12.307 | 46.539 | `b5d80a577f939b0a3282ab6cfa0c74f7c791e883641688cfce4f1c4f9e836c33` |
| `applications` | 2.780 | 15.094 | `7cd66abd0f84e97e5119cb8d42e155eee0d0ba7d050bbd4054f6741b1510b1bf` |
| `temporal_outliers` | 11 | 5.491 | `c38dc7afc8be716fe0d42d4ed9697404ae05b01fa4111cc4f27a1dafc09ee202` |

## Consistência

- `coverage.event_count` e `applications.event_count` somam 143.703.249;
- `event_timeline.event_count` soma os 143.702.933 timestamps válidos;
- `temporal_outliers.event_count` soma os 316 timestamps atípicos;
- não há `section_id` duplicado nem município sem nome;
- nenhuma seção publicada ficou sem eventos;
- nenhuma seção não publicada recebeu eventos;
- uma nova execução reutilizou os oito checkpoints sem reprocessamento.

A Gold foi construída somente a partir das tabelas Silver. Bronze e RAW não
foram relidos.
