# Contrato: CLI do coletor (`python -m cvm_archive.cli`)

Contrato público da interface de linha de comando. Implementação futura (esta etapa define
comportamento, não código). Regras de idioma: flags, valores de flag, identificadores e mensagens
de log em inglês; documentação e mensagens voltadas a pessoas em português brasileiro.

- **Runtime:** Python 3.12, somente biblioteca padrão (constituição VI). Módulos previstos:
  `argparse`, `urllib.request`, `urllib.robotparser`, `hashlib`, `pathlib`, `json`, `re`,
  `zipfile`/`html.parser` para conversão HTML; testes com `unittest`
  (https://docs.python.org/3.12/library/unittest.html). Nenhuma dependência de runtime.
- **Formato dos dados de saída:** segue o que definem `contracts/front-matter.md` e
  `contracts/coverage-report.md`; este contrato define os comandos, argumentos e códigos de saída.

## Layout de diretórios controlado por `--output DIR`

`--output DIR` aponta para a **raiz de dados** (no repo, a própria raiz). A CLI cria/usa:

| Subárvore | Conteúdo |
|---|---|
| `<output>/catalogo/<category>.json` | catálogo enumerado da categoria (ver abaixo) |
| `<output>/reguladores/cvm/<tipo>/<ano>/` | `.md` publicados (contrato front-matter) |
| `<output>/cobertura/cobertura.json` e `cobertura/COBERTURA.md` | relatório de cobertura (contrato coverage-report) |

`--cache-dir DIR` (default `.scratch/cache`) guarda os **bytes originais baixados** e o SHA-256
registrado (FR-005): `<cache-dir>/<hex>.<ext>` + `<hex>.meta.json`. É argumento operacional
documentado; em CI aponta para diretório volátil do runner, nunca commitado.

## Comandos

### `catalog` — enumerar o catálogo completo

```
python -m cvm_archive.cli catalog --category resolucoes --output DIR
```

| Flag | Obrig. | Valor |
|---|---|---|
| `--category` | sim | família do catálogo; MVP: só `resolucoes` (valores futuros seguem a tabela de tipos do contrato front-matter em código inglês, ex. `instrucoes`) |
| `--output` | sim | raiz de dados |
| `--min-interval` | não | segundos entre requisições (default `5`) |
| `--user-agent` | não | User-Agent (default: UA do projeto com link para o repositório) |

Comportamento (FR-001):

1. Percorre **todas** as páginas de resultado da busca oficial do portal de legislação da CVM
   (coleta educada: uma requisição por vez, intervalo ≥ `--min-interval`, User-Agent com link
   para o repositório, `robots.txt` respeitado; nada em `dados.cvm.gov.br/api/` — constituição III,
   FR-003).
2. Coleta **apenas as entradas de listagem**: cada registro guarda `url` (página canônica do ato no
   catálogo), `title`, `category`, `number` e `date` — conforme `CatalogEntry` em
   `data-model.md` §4 — **sem resolver a íntegra de cada ato** (o link HTML só vira íntegra depois
   de inspecionado, na etapa de documento). O número e a data do catálogo são **candidatos** até a
   epígrafe/página oficial confirmá-los; o `tipo` contratual também só se firma na epígrafe (C2).
   Não há `id` no registro de catálogo: a identidade é calculada depois, pelo contrato
   front-matter.
3. Deduplica entradas pelo mesmo destino canônico, deduplica alias de caminho (uma identidade,
   uma URL canônica; alternativas ficam para a cobertura) e registra contagem incoerente (ex.:
   contador da fonte oscila entre páginas) sem inventar número.
4. Grava `<output>/catalogo/resolucoes.json` com `schema_versao`, `gerado_em`, `metodo`
   (`"enumeracao"`), `contador_divulgado` (quando a fonte exibe), `total` e lista `registros`
   ordenada por `url` (ordem estável do catálogo).
5. O catálogo **não publica nada** e **não toca** em `reguladores/` nem em `cobertura/`.

Falha de catálogo (erro de enumeração, resposta bloqueada, catálogo incomparável):
**exit 2** (erro) quando nenhum bloqueio de acesso; **exit 3** quando a fonte bloqueou o acesso;
e NENHUM arquivo novo é gravado — **o catálogo anterior e a cobertura anterior permanecem intactos**
(uma coleta quebrada não substitui cobertura válida).

### `collect` — coletar e publicar

```
python -m cvm_archive.cli collect --category resolucoes \
  [--document URL] [--limit N] \
  --batch 0 \
  --output DIR \
  --cache-dir .scratch/cache \
  --min-interval 5 \
  --user-agent "NormasCVMResearch/0.5 (+https://github.com/<org>/<repo>; collect)"
```

| Flag | Obrig. | Valor |
|---|---|---|
| `--category` | sim | MVP: `resolucoes` |
| `--document` | não | URL da página de uma norma: modo documento único (FR-024), para revisão pontual; ignora `--batch`/`--limit` |
| `--limit` | não | `N` > 0: dentro da fatia do lote, processa no máximo `N` documentos **com trabalho pendente**, na ordem estável do catálogo; o restante da fatia não é tocado nesta passada |
| `--batch` | não | default `0`, ignorado com `--document`; `N` ≥ 0: **particiona o catálogo completo estável** (ordem por `url`), não o conjunto mutável de pendentes — fatia fixa `[N×S, (N+1)×S)` com tamanho `S=50`. Documentos sem trabalho pendente são rechecados por hash sem sair do denominador |
| `--output` | sim | raiz dos dados |
| `--cache-dir` | não | default `.scratch/cache`, nunca versionado |
| `--min-interval` | não | default `5` segundos, mínimo de 5 definido pelo projeto |
| `--user-agent` | não | default do projeto com URL do repositório |

Pré-condições e ordem (obrigatórias):

1. **Catálogo completo antes do lote:** o contrato exige catálogo completo e estável da categoria.
   Se `<output>/catalogo/resolucoes.json` estiver **ausente**, `collect` o **enumera
   automaticamente** (com o mesmo cliente educado e os mesmos códigos de saída) antes de processar
   o lote; se estiver presente e válido (`metodo: "enumeracao"`, `total` coerente), é usado como
   está. Catálogo presente porém indecifrável/incoerente: exit 2, sem gravar nada — a cobertura
   anterior permanece (C7/denominador).
2. O denominador de cobertura é sempre o **catálogo completo**, nunca o subconjunto processado.
   `--limit` e `--batch` reduzem só o trabalho da passada.

Comportamento por documento (FR-006 para o MVP):

- **Somente íntegra HTML oficial** entra em conversão/publicação no MVP. Documento cujo corpo
  exista apenas em PDF fica **pendente**, não ignorado: entra no relatório com motivo
  `pdf-conversor-pendente` (US3/FR-011 não abertos nesta fase). Registre também anexos em PDF como
  pendências do próprio documento quando forem a única forma do conteúdo (nunca omitir do
  catálogo).
- Bytes baixados → cache → recomputação de SHA-256 → portões de fidelidade (FR-014, tokens +
  contagens) → só então publicação; falha de portão = `pendente` com motivo `portao-fidelidade`
  (nunca publicar silenciosamente; constituição II).
- Documento com tabela não reproduzível: `pendente` com motivo `tabela-nao-reproduzida`.
- Bloqueio do host (401/403/429) ou path proibido por `robots.txt`: recuo e interrupção imediata
  sem contornar (FR-004), registro da falha no relatório da coleta.
- Hash sem mudança (cache válido): documento **não reconvertido** e **não reescrito** (FR-005).
  Coleta sem mudança na fonte = zero alterações em `reguladores/` e em `cobertura/` (FR-023/SC-005).
- Modo documento (`--document URL`): atualiza o documento apontado e revalida seu estado; não
  reenumera a categoria quando já existe catálogo completo local (documenta `modo: "documento"` na
  cobertura); se não houver catálogo local, enumera antes, para preservar o denominador — nunca
  coleta documento solto sem catálogo que o contemple.
- **Cobertura:** ao fim de cada coleta, o relatório é revalidado por inteiro antes de qualquer
  troca (escrito em área temporária e promovido de forma atômica; falha de promoção mantém o
  anterior — data-model §7.3). Com `catalogo_total` do catálogo completo e estados
  `{publicado, pendente, indisponivel, divergente, fora-de-escopo}` com motivo obrigatório para
  pendências. **Sem mudança semântica na fonte, os arquivos da cobertura são preservados byte a
  byte — inclusive `gerado_em` e `coleta`:** a troca de datas a cada run não é obrigatória (o
  contrato de cobertura permite, mas não exige, diferenças de execução; a opção estrita adotada
  aqui é registrada no `plan.md` e atende FR-023/US6). Contadores da passada (requisições,
  falhas, pendências da vez) ficam em **log local**, não em arquivos versionados — o relatório
  público só muda com conteúdo/estado.
- **Saída de máquina (contrato com o workflow):** a última linha copiada do stdout de `collect` é
  um JSON único:

  ```json
  {"changed": true, "publicados": 3, "pendentes": 12, "indisponiveis": 0, "falhas_http": 0}
  ```

  `changed` é `true` se e somente se algum arquivo de `reguladores/` ou de `cobertura/` mudou
  nesta coleta (a CLI compara antes/depois; sem mudança semântica, `changed` é `false` e **nenhum
  arquivo versionado é reescrito**, inclusive cobertura e datas). O workflow usa esse
  campo para decidir o commit (ver `contracts/workflow.md`).

Expansão futura (**FORA do MVP**, escrita aqui para direção, sem implementação):

- `collect --incremental`: RSS de legislação + RSS de audiências como sinal de novidade,
  reconciliado com o catálogo completo e com **hashes rotativos** (checar periodicamente hash de
  documentos publicados), conforme FR-002 e política de `sha256_fontes` em coverage-report.

### `verify` — conferir repositório de dados

```
python -m cvm_archive.cli verify --root DIR
```

`--root` é a mesma raiz de dados (subárvores `reguladores/`, `cobertura/`, `catalogo/`). Verifica
**sem rede**:

1. Todo `.md` publicado parseia: YAML front matter válido, campos obrigatórios presentes,
   anulabilidade respeitada (`null` explícito), `schema_versao` conhecido, UTF-8 sem BOM, LF
   (contrato front-matter).
2. `sha256_fonte` confere com os bytes no cache local quando disponíveis; quando não estão
   disponíveis, informar no stdout que a conferência dos bytes é UNVERIFIED. Não criar campo
   `fontes` nem declarar verificação histórica não demonstrada. Ausência de cache não invalida
   sozinha um arquivo cujo schema e vínculo com o índice sejam válidos.
3. O estado do `cobertura.json` é coerente com os arquivos no disco (nenhum arquivo publicado fora
   do relatório; `id` únicos; ordenação estável). Ato `pendente` **pode** ter arquivos publicados
   listados em `arquivos` — por exemplo, o original aprovado de um ato cujo consolidado ainda está
   pendente (data-model §7.2/§7.3): nesse caso o `motivo` identifica a versão faltante e a causa
   (ex.: `consolidada: tabela-nao-reproduzida`), o ato conta uma vez em `pendentes` (não soma
   também em `publicados`) e o original válido não é apagado por falha do consolidado. `verify`
   não exige genericamente "nenhum pendente publicado"; o que exige é que toda publicação esteja
   no relatório e que nenhuma versão pendente seja publicada.
4. Caminhos por tipo/ano/identidade seguem a tabela da front-matter (incluindo `sem-data/`).

Saída: contadores por categoria e lista de violações; **exit 0** sem violação, **exit 2** com
violações (nenhum arquivo é modificado por `verify`).

## Códigos de saída (exit codes)

| Código | Significado | Exemplos |
|---|---|---|
| `0` | sucesso, inclusive coleta com pendências e/ou zero mudanças | pendências registradas; `changed: false` |
| `2` | erro de uso/programa/estado | flags inválidas; catálogo/dados indecifráveis ou incoerentes; parse/normalização impossível; violação em `verify` |
| `3` | **bloqueio do acesso à fonte** | 401/403/429; caminho proibido por `robots.txt`; recuo acionado (FR-004) |

Regras de atomicidade: nos códigos 2 e 3 a CLI **não** grava `cobertura/` novo nem move arquivos
publicados — a última cobertura válida permanece. A retentativa após bloqueio/erro é decisão de
quem invoca (a política de recuo fica no coletor; o workflow, ver `contracts/workflow.md`, não
reaproveita run parcial).

## Observação sobre pendências (semântica de exit 0)

Pendência **não é erro**: o documento entrou no relatório com motivo explícito e segue no
denominador (SC-001). O mantenedor distingue pendência de erro nos logs; o exit 0 cobre
ambos os casos "publicou algo" e "não publicou nada mas registrou tudo".

## Testes contratados (Princípio IV; deliverable de implementação)

`unittest` sem dependências extras; fixtures de texto real da CVM, incluindo os casos negativos
do plano revisado (C1, C8, C9, C10): republicação parcial, tabela não reproduzível,
remoção/permutação/duplicação de dispositivo, hash inalterado, alteração de 1 byte, casos
`sem-data`, colisão de dois caminhos. Casos obrigatórios de CLI:

1. `catalog` coleta só entradas de listagem (sem resolver íntegra); número/data ficam candidatos e
   nenhum `id` é inventado; contagem incoerente é registrada, nunca resolvida por suposição.
2. `catalog` com falha de enumeração → exit 2 (ou 3, se bloqueio) e nada gravado; catálogo e
   cobertura anteriores intactos.
3. `collect` sem catálogo local → auto-enumera antes do lote; modo documento sem catálogo idem.
4. `collect --batch 0` resolve dez pendentes na fatia e `--batch 1` na sequência **não pula**
   documentos que o lote 0 já publicou (partição estável do catálogo completo).
5. `collect` com bloqueio 403 → exit 3 e nada publicou/alterou; falha registrada no log.
6. `collect` documento cujo único corpo é PDF → exit 0 e pendência `pdf-conversor-pendente` no
   relatório (nunca sumido do catálogo).
7. Coleta repetida sem mudança semântica → `changed: false`, bytes de `reguladores/` e
   `cobertura/` preservados (inclusive datas; contadores só no log local; SC-005/FR-023).
8. Ato pendente por consolidado com original aprovado: `verify` sai 0 com `arquivos` listando só
   o aprovado e motivo cobrindo a versão faltante; falha do consolidado não apaga o original.
9. `verify` detecta front matter malformado, hash errado e publicação fora do relatório → exit 2.
10. Última linha do stdout de `collect` parseia como JSON com `changed` booleano.
