# Contrato: workflow de coleta agendada (GitHub Actions)

Contrato do workflow que implementa a coleta periódica (SC-006, D-U12). **Esta etapa não cria o
arquivo**: o esqueleto abaixo será materializado, quando a implementação for autorizada, em
`.github/workflows/collect.yml`. Os fatos oficiais citados aqui vêm da documentação oficial listada
na seção "Fontes oficiais".

Idioma: identificadores, comentários e nomes de passos em inglês conforme regra de código.

## Gatilhos e rótulos

| Item | Contrato | Base oficial |
|---|---|---|
| `runs-on` | `ubuntu-24.04` **pinado** (o `ubuntu-latest` migra para 26.04 em nov 2026; anúncio oficial) | runner-images README + issue 14748 |
| Python | `actions/setup-python` com `python-version: "3.12"` (a imagem já lista 3.12.3; o `setup-python` dá versão explícita) | hosted-runners + README da imagem |
| Dependências | `apt-get update` + `poppler-utils tesseract-ocr tesseract-ocr-por` instaladas **em cada job**, com `pdftotext -v` e `tesseract --version` impressos como verificação (`UNVERIFIED` nos tempos reais do runner) | hosted-runners (`sudo` sem senha) |
| Tempos locais de referência | instalação update+poppler+2×tesseract: **143,48 s** (run 1; a revisão do plano conservou a divergência com os 143,46 s do texto R2) e **94,74 s** (run 2), medidos em docker `ubuntu:24.04.5` local — **não certificam o runner real** | medição local da pesquisa técnica |
| LibreOffice | **sem passo no MVP**. A rota LibreOffice apenas extraído falhou (plano revisado); se o roteiro DOCX/DOC for aprovado, o passo futuro é a instalação via apt testada, comentada no esqueleto | decisão de plano |
| Cache de apt | **não cachear por padrão** (custo medido pequeno; deriva de versão; 10 GB/7 dias contra o Princípio VI). Cache só se candidato: LibreOffice aprovado (doc de cache, limite de 10 GB) | doc de cache, "Usage limits and eviction policy" |

## Gatilhos (`on`)

- `schedule`: `cron "27 6 * * 2,5"` (terças e sextas, 06:27 UTC; minuto fora de `:00` para reduzir
  atrasos por congestionamento). O `schedule` **executa sempre o arquivo que está na default
  branch** (doc oficial events). **SLA de 7 dias (SC-006): UNVERIFIED** — atrasos/drops
  documentados, desativação automática após 60 dias de inatividade em repo público e dependência
  da default branch são limites aceitos nesta fase; monitoramento/reativação é escopo de
  melhoria futura.
- `workflow_dispatch` com inputs — **ligados de fato à CLI** (tabela abaixo):
  - `categoria`: `choice`; no MVP aceita apenas `resolucoes` (a CLI devolve exit 2 para demais
    valores; demais categorias entram quando o caminho da família correspondente existir);
  - `documento`: `string`, opcional (rerun pontual de uma norma; FR-024);
  - `lote`: `number`, opcional, default 0 (carga inicial em lotes);
  - `limite`: `number`, opcional, default 10 — lote limitado: no máximo `N` documentos pendentes
    processados nesta passada; `0` significa sem limite.

## Permissões e concorrência

- `permissions: contents: write` (mínimo para o push de dados; permissões não listadas viram
  `none` — workflow-syntax). O `GITHUB_TOKEN` vive até o fim do job, máx. 6 h (doc oficial do
  token).
- `concurrency: group "collect-cvm"`, `cancel-in-progress: false` — **uma fila única, sem
  cancelamento** (constituição III; nunca matar coleta educada a meio caminho). Limite de 20 jobs
  concorrentes no Free é muito acima do uso (doc de limits).

## Wiring dos inputs → CLI (obrigatório, é o defeito que o esqueleto R2 deixou implícito)

O passo `Collect` executa a CLI com os inputs **repassados de fato**:

| Input do dispatch / evento | Passe para a CLI |
|---|---|
| `categoria` | `--category "$CVM_COLLECT_CATEGORY"` (eventos `schedule`: o MVP agenda roda `--category resolucoes`; a retomada vem do `--batch` e dos hashes do cache) |
| `documento` (se não vazio) | `--document "$CVM_COLLECT_DOCUMENT"` |
| `lote` | `--batch "$CVM_COLLECT_BATCH"` |
| `limite` (se > 0) | `--limit "$CVM_COLLECT_LIMIT"` |
| fixo | `--min-interval 5`, `--user-agent` com repositório no UA, `--cache-dir "$RUNNER_TEMP/cvm-cache"` (diretório volátil do runner, **nunca commitado**) e `--output` na raiz do workspace |

O contrato exige catálogo completo e estável antes da fatia do lote; a CLI o cumpre **auto-
enumerando** quando o catálogo local está ausente (`contracts/cli.md`), então o workflow não
precisa de passo separado de `catalog` — e um run agendado parte sempre de catálogo completo.

O passo captura a **última linha do stdout** da CLI (JSON com `changed`; contrato
`contracts/cli.md`) e a publica como `outputs.changed` do passo; o passo de commit só roda com
`changed == 'true'`. Códigos de saída 2/3 da CLI **falham o job** (sem `continue-on-error`): erro
integra o run; bloqueio (exit 3) também falha o job — a retentativa é decisão do mantenedor
(reexecutar dispatch), nunca automática.

## Commit e push (política de branch)

- **Alvo exclusivo:** `git push origin HEAD:001-acervo-cvm`. Nenhuma liberação automática para
  `main` decorre deste workflow; `main` recebe só merge revisado (constituição Workflow).
- Guarda no passo de commit: se o branch atual tiver nome e não for `001-acervo-cvm`, o passo
  falha **antes** do commit/push. O checkout usa `ref: 001-acervo-cvm` explícito para o run
  agendado, pois o gatilho `schedule` sempre parte do conteúdo do workflow na default branch.
  Quando a integração à default branch for autorizada, o ajuste é retirar o `ref` e o sufixo do
  push.
- **Autoria:** commits de dados como
  `github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>` (única exceção
  autorizada, D-U12; identidade verificada na API oficial do GitHub — usuário `github-actions[bot]`,
  id 41898282, type Bot); commits de código
  continuam humanos. Mensagem de commit com a **data real da coleta** e descrição do lote (FR-021;
  ex.: `data: collect resolucoes batch 0 (2026-10-22)`).
- Paths do `git add`: `reguladores/`, `cobertura/` e `catalogo/` (o catálogo é versionado no MVP
  para rastreio do denominador e das pendências). Nunca o cache (volátil do runner), `temp` ou
  diretórios locais de pesquisa.
- Push com `GITHUB_TOKEN` **não** dispara outros workflows (doc do token) — sem recorrência.

## Esqueleto (proposta, não criado nesta etapa)

```yaml
name: collect
# Scheduled + manual collector for the CVM archive. Skeleton (contract, not yet a file).
# - Politeness: one request at a time, >= 5 s interval, robots.txt, UA with repo link (CLI enforces).
# - Authorship: data commits come from github-actions[bot] (D-U12); code commits stay human.
# - Branch policy: pushes target 001-acervo-cvm only; no automatic merge to main.
# - MVP: only 'resolucoes'; the CLI rejects other categories with exit code 2.
# - Caveat: schedule depends on this file being on the default branch; SC-006 SLA is UNVERIFIED.

on:
  schedule:
    - cron: "27 6 * * 2,5"
  workflow_dispatch:
    inputs:
      categoria:
        description: "Catalog category (MVP: only resolucoes)"
        type: choice
        required: false
        default: "resolucoes"
        options: [resolucoes]   # more categories enter when their CLI path exists
      documento:
        description: "Optional single-document rerun (norm page URL)"
        type: string
        required: false
        default: ""
      lote:
        description: "Batch index (0 = from the start)"
        type: number
        required: false
        default: 0
      limite:
        description: "Limited batch: max pending documents this run (0 = unlimited)"
        type: number
        required: false
        default: 10

permissions:
  contents: write

concurrency:
  group: collect-cvm
  cancel-in-progress: false

jobs:
  collect:
    runs-on: ubuntu-24.04
    timeout-minutes: 360
    steps:
      - name: Checkout
        uses: actions/checkout@v5
        with:
          ref: 001-acervo-cvm
          # persist-credentials: true (default): commit step pushes with GITHUB_TOKEN.

      - name: Install Poppler and Portuguese OCR
        run: |
          sudo apt-get update -qq
          sudo apt-get install -y -qq poppler-utils tesseract-ocr tesseract-ocr-por
          pdftotext -v | head -1
          tesseract --version | head -1

      # Future, only if the DOCX/DOC route is approved (apt install; portable LibreOffice failed):
      # sudo apt-get install -y -qq --no-install-recommends libreoffice

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Collect
        id: collect
        env:
          CVM_COLLECT_CATEGORY: ${{ inputs.categoria || 'resolucoes' }}
          CVM_COLLECT_DOCUMENT: ${{ inputs.documento }}
          CVM_COLLECT_BATCH: ${{ inputs.lote || 0 }}
          CVM_COLLECT_LIMIT: ${{ github.event_name == 'schedule' && 10 || inputs.limite || 0 }}
          CVM_MIN_INTERVAL_SECS: "5"
          CVM_USER_AGENT: "NormasCVMResearch/0.5 (+https://github.com/<org>/<repo>; scheduled collection)"
        run: |
          set -euo pipefail
          args=(collect --category "$CVM_COLLECT_CATEGORY" --batch "$CVM_COLLECT_BATCH"
                --output . --cache-dir "$RUNNER_TEMP/cvm-cache"
                --min-interval "$CVM_MIN_INTERVAL_SECS" --user-agent "$CVM_USER_AGENT")
          if [ -n "$CVM_COLLECT_DOCUMENT" ]; then args+=(--document "$CVM_COLLECT_DOCUMENT"); fi
          if [ "$CVM_COLLECT_LIMIT" -gt 0 ]; then args+=(--limit "$CVM_COLLECT_LIMIT"); fi
          python -m cvm_archive.cli "${args[@]}" > "$RUNNER_TEMP/collect.log"
          # Parse with Python, not text substitution (contract: CLI stdout JSON last line).
          changed="$(python -c 'import json, sys
lines = [l for l in open(sys.argv[1], encoding="utf-8").read().splitlines() if l.strip()]
print("true" if json.loads(lines[-1]).get("changed") else "false")' "$RUNNER_TEMP/collect.log")"
          echo "Collect summary: changed=$changed"
          tail -n 1 "$RUNNER_TEMP/collect.log" >> "$GITHUB_STEP_SUMMARY" || true
          echo "changed=$changed" >> "$GITHUB_OUTPUT"

      - name: Commit collected data
        if: ${{ steps.collect.outputs.changed == 'true' }}
        env:
          COLLECT_CATEGORY: ${{ inputs.categoria || 'resolucoes' }}
          COLLECT_BATCH: ${{ inputs.lote || 0 }}
        run: |
          set -euo pipefail
          b="$(git branch --show-current)"
          if [ -n "$b" ] && [ "$b" != "001-acervo-cvm" ]; then
            echo "::error::unexpected branch $b; refusing to push"; exit 1
          fi
          git config user.name  "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add reguladores cobertura catalogo
          git commit -m "data: collect $COLLECT_CATEGORY batch $COLLECT_BATCH $(date -u +%F)"
          git push origin HEAD:001-acervo-cvm
```

Observações do esqueleto (contrato, não implementação):

- O passo `Collect` roda com `set -euo pipefail` e saída em arquivo para que **o exit code da CLI
  (2/3) falhe o job intacto** — um pipe por `tail` não pode mascarar bloqueio ou erro. O parse de
  `changed` é **Python com `json`**, não substituição de texto (a última linha do stdout JSON é o
  contrato; o formato do parse é implementação livre).
- O passo `Commit` demonstra a mensagem FR-021 (data real da coleta + lote). O env `CVM_COLLECT_*`
  de um passo **não cruza passos**: o commit deriva `categoria` dos `inputs` no próprio passo. O
  texto do lote na mensagem (lote, limite, documento) deve fazer referência ao que rodou — a
  implementação deriva dos `inputs` no passo de commit, com a data real de UTC que colheu.

## O que este workflow NÃO faz

- Não faz merge, push ou PR para `main` (nenhuma autorização automática de liberação).
- Não roda conversão PDF (MVP) — pendências de PDF seguem para o relatório via CLI.
- Não reexecuta coleta em falha (sem retry automático; retentativa é do mantenedor).
- Não publica/committa nada quando `changed == false`.

## Fontes oficiais (base da pesquisa da fase 0)

- Imagens e anúncio de migração: https://github.com/actions/runner-images/blob/main/README.md e
  https://github.com/actions/runner-images/issues/14748
- Runners, `sudo`, `ubuntu-slim`: https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- Limites (6 h/job, 35 dias/workflow, 20 jobs, fila): https://docs.github.com/en/actions/reference/limits
- `schedule`/`workflow_dispatch`: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- Sintaxe (`permissions`, `timeout-minutes`, `concurrency`): https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- Cache: https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching
- `GITHUB_TOKEN`: https://docs.github.com/en/actions/concepts/security/github_token e
  https://docs.github.com/en/actions/tutorials/authenticate-with-github_token
- `actions/checkout` (persist-credentials): https://github.com/actions/checkout/blob/main/README.md
- Billing: https://docs.github.com/en/billing/concepts/product-billing/github-actions

## UNVERIFIED (herdados da R2 + desta etapa)

1. Durações e banda no **runner real** (não executado); os 143,48/94,74 s são locais.
2. **SLA de 7 dias** com 2 crons/semana (atrasos/drops/desativação/default branch); exige
   monitoramento futuro.
3. Se commits do `github-actions[bot]` contam como atividade contra os 60 dias de desativação.
4. Tempos de lote reais (dependem de nº de requisições e conversões; nenhum lote executado).
5. Comportamento do `outputs.changed` em execução real (contratado acima, não executado).
