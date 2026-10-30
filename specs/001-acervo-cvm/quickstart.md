# Quickstart — MVP do acervo CVM (resoluções)

Guia de uso do MVP da coleta: apenas a família **resoluções**, e somente documentos com **íntegra
HTML oficial** (PDF entra no fluxo como pendência até o conversor ser testado e aprovado; ele nunca
é omitido do catálogo). Coleta educada: uma requisição por vez, intervalo mínimo de 5 segundos,
`robots.txt`, User-Agent identificável; `dados.cvm.gov.br/api/` nunca é acessado.

Pré-requisitos: **Python 3.12** com biblioteca padrão apenas — nenhuma dependência de runtime
(constituição VI). Poppler/Tesseract só serão necessários quando o caminho de PDF for ativado.

A CLI do MVP está implementada e foi validada com a Resolução 249; ver
[resultados executados](research/validacao-mvp.md). Instale a partir da raiz com
`python -m pip install -e .` antes dos comandos. Os workflows estão implementados: testes
executados no runner, coleta preparada e ainda não acionada.

## 1. Enumerar o catálogo (antes de coletar)

```bash
python -m cvm_archive.cli catalog --category resolucoes --output .
```

- Percorre todas as páginas de resultado da busca oficial do portal de legislação da CVM e grava
  `catalogo/resolucoes.json` com **entradas de listagem** (`url`, `title`, `category`,
  `number`/`date` como candidatos — Confirmação só na página/epígrafe). O `catalog` **não**
  precisa resolver a íntegra de cada ato.
- Requisito do fluxo: **catálogo completo antes de cada lote** — é dele que saem o denominador
  da cobertura e a partição em lotes. O `collect` também cumpre esse requisito sozinho: se o
  catálogo local estiver ausente, ele **enumera automaticamente** antes do lote (§2).
- `catalog` não publica nada e não altera `reguladores/` nem `cobertura/`.
- Falha na enumeração encerra com **exit 2** (ou **3**, se a fonte bloquear o acesso) e **não**
  substitui o catálogo nem a cobertura anteriores.

## 2. Coletar (carga inicial em lotes)

```bash
python -m cvm_archive.cli collect \
  --category resolucoes \
  --batch 0 \
  --output . \
  --cache-dir .scratch/cache \
  --min-interval 5 \
  --user-agent "NormasCVMResearch/0.5 (+https://github.com/StaffeToxic/normas-cvm; local run)"
```

O que acontece:

- O lote `0` cobre a **primeira fatia do catálogo completo, em ordem estável**; o lote 1 a fatia
  seguinte, e assim por diante. O tamanho da fatia é fixo em 50 no coletor.
  Como a partição é sobre o catálogo todo (não sobre pendências), documentos da fatia
  já resolvidos por lotes anteriores são conferidos por hash e pulados rapidamente — o lote 1
  nunca pula documentos que o lote 0 acabou de resolver.
- Cada documento com trabalho pendente na fatia é baixado para `.scratch/cache` (bytes originais +
  SHA-256), conferido por hash e submetido aos portões de fidelidade antes de virar `.md` em
  `reguladores/cvm/resolucoes/<ano>/`.
- `--limit N` (opcional) processa no máximo `N` documentos pendentes da fatia (ideal para testes).
  Para **reprocessar um único documento**, informe `--document <URL da página da norma>` — nesse
  modo `--batch`/`--limit` são ignorados e o denominador continua sendo o catálogo completo.
- Ao fim de cada coleta bem-sucedida: `cobertura/cobertura.json` (máquina) e
  `cobertura/COBERTURA.md` (leitura humana). Pendências sempre com motivo explícito, por exemplo
  `pdf-conversor-pendente`, `tabela-nao-reproduzida`, `portao-fidelidade` — pendência não é erro.
  Um ato pendente por consolidado pode ter o **original aprovado** publicado e listado; o motivo
  cobre a versão faltante (ex.: `consolidada: tabela-nao-reproduzida`).
- Coleta sem mudança semântica na fonte: `changed: false` e **nenhum arquivo versionado é
  reescrito** — inclusive a cobertura, sem virada de data; contadores da passada ficam só no log
  local (FR-023/SC-005). O stdout termina com um JSON
  `{"changed": ..., "publicados": ...}` para consumo por máquina (workflow).

Variações úteis:

```bash
# lote seguinte (retomada da carga inicial)
python -m cvm_archive.cli collect --category resolucoes --batch 1 --output . \
  --cache-dir .scratch/cache --min-interval 5

# teste contido: no máximo 10 documentos pendentes deste lote
python -m cvm_archive.cli collect --category resolucoes --batch 0 --limit 10 --output . \
  --cache-dir .scratch/cache --min-interval 5

# revisão pontual de um documento
python -m cvm_archive.cli collect --category resolucoes --output . \
  --document "https://conteudo.cvm.gov.br/legislacao/resolucoes/resol175.html" \
  --cache-dir .scratch/cache --min-interval 5
```

## 3. Conferir o acervo

```bash
python -m cvm_archive.cli verify --root .
```

Verifica sem rede: cabeçalho YAML válido e completo, anulabilidade, UTF-8 sem BOM e LF, `id`
únicos, coerência entre `cobertura/cobertura.json` e os arquivos em disco, caminhos por
`tipo/ano/identidade`. Não exige genericamente "nenhum pendente publicado": um ato pendente por
consolidado com o original aprovado é válido (o relatório conta o ato uma vez, em `pendentes`).
Imprime contadores por categoria e lista de violações. Sem violações, sai com **0**; com
violações, **2** (nada é modificado por `verify`).

## Atualização incremental

```bash
python -m cvm_archive.cli collect --category resolucoes --incremental --limit 10 --output .
```

Reconcilia o catálogo completo, usa os dois feeds como sinais e reconsulta a primeira página e
uma fatia semanal de hashes. Não combina com `--document`. Remoção sem alias confirmado exige
revisão, preservando os dados anteriores; não significa revogação. A implementação foi testada
com fixtures, sem novas coletas; execução incremental real permanece UNVERIFIED.

## Códigos de saída

| Código | Significado | O que fazer |
|---|---|---|
| `0` | sucesso (publicou algo, só registrou pendências ou nada mudou) | conferir cobertura |
| `2` | erro de uso/programa/estado (inclui catálogo quebrado, lote inválido, flags inválidas) | corrigir e repetir |
| `3` | **bloqueio da fonte** (401/403/429, caminho proibido por `robots.txt`) | parar; nunca contornar; aguardar e repetir depois |

Em `2` e `3` nada é gravado: a última cobertura válida permanece (o denominador preservado).

## Sincronização com o repositório

- O workflow agendado implementado (ver `contracts/workflow.md`, ticket T009) usa a mesma CLI e
  commitar dados como `github-actions[bot]`, com push restrito a `HEAD:001-acervo-cvm` — nada sobe para
  `main` automaticamente.
- Coleta local na máquina do mantenedor obedece às mesmas regras de coleta; a decisão de commit é
  sua (autoria humana, Conventional Commits).

## Futuro indicado nesta versão

- **Empacotamento:** `pyproject.toml` e a CLI estão disponíveis; a instalação do pacote é
  necessária por causa do layout `src/`.
- O workflow de `collect --incremental` está preparado; ativação e SLA dependem da default branch
  e de execução/observação reais, ainda UNVERIFIED.
- Demais categorias (`instrucoes`, `deliberacoes`, ...) entram por família quando o caminho de
  PDF/OCR estiver comprovado contra fixtures.
- Serviço de API ou MCP para consumo programático fica para outra feature (definição pendente,
  D-U1).

## Roteiro rápido de verificação do mantenedor

1. Rodar na ordem: `catalog` → `collect` → `verify`; conferir os contadores de `COBERTURA.md`
   (total do catálogo, publicados, pendentes, indisponíveis, divergentes).
2. Rodar duas vezes seguidas sem mudança na fonte: a segunda deve terminar com `changed: false`
   e nenhum byte alterado em `reguladores/` e `cobertura/`.
3. Reproduzir uma pendência: escolher um documento que só existe em PDF e ver no relatório o
   motivo `pdf-conversor-pendente` (ele não pode sumir do catálogo).
4. Testes: `python -m unittest discover -s tests` (nenhuma dependência extra).

Referências de comportamento detalhado: `contracts/cli.md` (comandos, flags e exit codes),
`contracts/workflow.md` (agendamento no GitHub Actions), `contracts/coverage-report.md`
(relatório) e `contracts/front-matter.md` (formato dos `.md`).
