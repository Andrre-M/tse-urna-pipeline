# Publicação da Silver

Este é o procedimento canônico para publicar o recorte Ceará 2026/3220. Ele não
executa o ETL e não altera os dados em `D:`.

## Estado de entrada

Antes de começar, confira `PROJECT_STATE.md`. A publicação preparada contém:

| Configuração | Arquivos | Linhas | Bytes |
|---|---:|---:|---:|
| `events` | 8 | 143.703.249 | 2.630.037.414 |
| `section_coverage` | 1 | 25.650 | 96.901 |
| Total | 9 | 143.728.899 | 2.630.134.315 |

Arquivos locais:

```text
D:\tse-urna-pipeline\data\silver\events\year=2026\pleito=3220\uf=CE
D:\tse-urna-pipeline\data\silver\section_coverage\year=2026\pleito=3220\uf=CE
```

Metadados versionados:

```text
dataset/README.md
dataset/manifest.json
dataset/checksums.sha256
docs/data_dictionary.md
docs/quality_report_ce_2026_3220.md
```

Não copie os Parquets para o checkout, não envie RAW, Bronze ou SQLite e não
apague a cópia existente em `C:`.

## Autorização necessária

O destino recomendado é o Hugging Face, no repositório público
`<conta>/tse-urna-ce-2026`. Antes de criar o repositório, obtenha do proprietário:

1. confirmação do uso do Hugging Face;
2. nome exato da conta ou organização que será proprietária;
3. autorização para criar o repositório e enviar os dados.

Não deduza a conta pelo nome do GitHub. A autenticação deve ser feita pelo
proprietário no navegador ou terminal; tokens não entram no chat, Git ou logs.

## Verificação local

Abra o PowerShell e execute a partir da raiz do projeto:

```powershell
Set-Location -LiteralPath 'C:\Users\André Incentive.me\Documents\Codex\Projects\tse-urna-pipeline'

uv run ruff check .
uv run pytest -q
git status --short
```

O estado deve estar limpo. Compare os arquivos reais com o manifesto:

```powershell
$manifest = Get-Content -LiteralPath 'dataset\manifest.json' -Raw | ConvertFrom-Json
$roots = @{
    events = 'D:\tse-urna-pipeline\data\silver\events\year=2026\pleito=3220\uf=CE'
    section_coverage = 'D:\tse-urna-pipeline\data\silver\section_coverage\year=2026\pleito=3220\uf=CE'
}

foreach ($config in @('events', 'section_coverage')) {
    foreach ($entry in $manifest.configurations.$config.files) {
        $path = Join-Path $roots[$config] ([IO.Path]::GetFileName($entry.path))
        if ((Get-Item -LiteralPath $path).Length -ne $entry.bytes) {
            throw "Tamanho divergente: $path"
        }
        $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($hash -ne $entry.sha256) {
            throw "SHA-256 divergente: $path"
        }
    }
}

'Manifesto local conferido.'
```

Uma divergência interrompe a publicação. Investigue a origem; não atualize o
manifesto apenas para fazê-lo coincidir.

## Criação e envio

Substitua somente `<conta>` pelo identificador confirmado. `uvx` executa a CLI
sem adicioná-la às dependências do projeto.

```powershell
Set-Location -LiteralPath 'C:\Users\André Incentive.me\Documents\Codex\Projects\tse-urna-pipeline'

$repo = '<conta>/tse-urna-ce-2026'
$events = 'D:\tse-urna-pipeline\data\silver\events\year=2026\pleito=3220\uf=CE'
$coverage = 'D:\tse-urna-pipeline\data\silver\section_coverage\year=2026\pleito=3220\uf=CE'

uvx hf auth login
uvx hf auth whoami
uvx hf repos create $repo --repo-type dataset --public --exist-ok

uvx hf upload $repo 'dataset\README.md' 'README.md' --repo-type dataset
uvx hf upload $repo 'dataset\manifest.json' 'manifest.json' --repo-type dataset
uvx hf upload $repo 'dataset\checksums.sha256' 'checksums.sha256' --repo-type dataset
uvx hf upload $repo 'docs\data_dictionary.md' 'DATA_DICTIONARY.md' --repo-type dataset
uvx hf upload $repo 'docs\quality_report_ce_2026_3220.md' 'QUALITY_REPORT.md' --repo-type dataset
uvx hf upload $repo $events 'data/events' --repo-type dataset
uvx hf upload $repo $coverage 'data/section_coverage' --repo-type dataset
```

Os envios são retomáveis: se houver interrupção, execute novamente o mesmo
comando. Não inicie dois processos de upload simultâneos para a mesma pasta.

## Validação remota

Após o envio:

```powershell
uvx hf datasets info $repo --expand sha,siblings,private --format json
uvx hf datasets card $repo --metadata
uvx hf datasets parquet $repo
```

Conte as linhas diretamente nos Parquets expostos pela plataforma:

```powershell
$eventFiles = uvx hf datasets parquet $repo --subset events --format json |
    ConvertFrom-Json
$coverageFiles = uvx hf datasets parquet $repo --subset section_coverage --format json |
    ConvertFrom-Json

$eventUrls = ($eventFiles.url | ForEach-Object { "'$_'" }) -join ', '
$coverageUrls = ($coverageFiles.url | ForEach-Object { "'$_'" }) -join ', '

uvx hf datasets sql "SELECT COUNT(*) AS rows FROM read_parquet([$eventUrls])"
uvx hf datasets sql "SELECT COUNT(*) AS rows FROM read_parquet([$coverageUrls])"
```

Confirme no resultado e na página pública:

- nove Parquets nos caminhos declarados em `manifest.json`;
- configurações `events` e `section_coverage`;
- cartão e arquivos de apoio acessíveis;
- 143.703.249 linhas em `events`;
- 25.650 linhas em `section_coverage`;
- repositório público.

Se o processamento automático da plataforma ainda estiver em andamento,
registre isso como pendência e volte a verificar; não declare a publicação
concluída antes das duas configurações aparecerem.

## Encerramento

Quando a validação terminar:

1. registre em `PROJECT_STATE.md` a URL, a revisão publicada, a data e as
   contagens verificadas;
2. marque a publicação como concluída em `ROADMAP.md`;
3. crie commits pequenos e rode Ruff e pytest;
4. envie os commits ao GitHub;
5. só então escolha o próximo produto analítico.

Qualquer atualização posterior repete o fluxo com novo manifesto e nova versão.
Nunca substitua silenciosamente uma versão já declarada como validada.

Os comandos foram conferidos com a CLI `hf` 2.2.0 em 13 de outubro de 2026.
Se a sintaxe mudar, valide primeiro com `uvx hf <comando> --help` e consulte a
[documentação oficial](https://huggingface.co/docs/huggingface_hub/en/guides/cli)
antes de atualizar este procedimento.
