# Roadmap

## Concluído

- Catálogo e discovery de todas as seções do Ceará.
- Download, extração e parsing com retomada por checkpoint.
- Bronze em lotes, quarantine e compactação.
- Relatório de qualidade do Ceará 2026/3220.
- Silver de eventos e cobertura de seções.
- Reconsulta reiniciável de seções sem arquivo.

## Agora

1. Confirmar com o proprietário o destino e a conta de publicação. O destino
   operacional recomendado é o Hugging Face.
2. Publicar a versão `0.4.0` conforme `docs/publication.md`.
3. Validar arquivos, configurações, documentação e acesso público.
4. Registrar a URL e a revisão publicada em `PROJECT_STATE.md`.

## Depois

- Escolher, em uma decisão separada, entre notebook de análise, artigo técnico
  ou dashboard como primeiro consumidor da Silver.
- Avaliar outras UFs somente após a publicação do Ceará.

## Publicação concluída quando

- os 9 Parquets estiverem disponíveis no destino público;
- `events` e `section_coverage` forem reconhecidos como configurações distintas;
- cartão, dicionário, relatório, manifesto e checksums estiverem publicados;
- as contagens públicas forem 143.703.249 e 25.650 linhas;
- a URL e a revisão imutável estiverem registradas no estado do projeto.
