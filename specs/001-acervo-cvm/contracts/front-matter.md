# Contrato: cabeçalho YAML dos documentos (schema v1)

Contrato público com leitores e sistemas consumidores. Mudanças seguem o Princípio V da constituição:
campo opcional novo = MINOR; renomear, remover ou mudar significado = MAJOR com nota de migração.
A versão do schema é declarada em `schema_versao`.

## Layout do arquivo

```text
---
<cabeçalho YAML>
---
# <titulo>

<corpo>
```

UTF-8 sem BOM, fim de linha LF, uma linha em branco entre blocos, sem espaço no fim da linha, arquivo
termina com uma quebra de linha.

## Campos

| Campo | Tipo | Obrigatório | Regra |
|---|---|---|---|
| `schema_versao` | string | sim | `"1.0"` nesta versão |
| `id` | string | sim | identidade estável; ver "Identidade" |
| `classe` | enum | sim | `norma` \| `orientação` \| `minuta` |
| `tipo` | string | sim | rótulo legível da coluna `tipo` em "Tipos" (ex.: `"Resolução"`), compatível com acervos existentes |
| `titulo` | string | sim | título como aparece na fonte, sem normalizar caixa |
| `orgao` | string | sim | `"Comissão de Valores Mobiliários"`; em atos conjuntos, todos os órgãos separados por ` / ` |
| `unidade` | string \| null | sim | superintendência emissora (`SEP`, `SIN`, `SNC/SSE`…) quando a fonte informar; senão `null` |
| `numero` | string \| null | sim | como na fonte, sem zeros à esquerda (`"175"`, `"02/2024"` para ofícios) |
| `data` | date \| null | sim | data do ato (`AAAA-MM-DD`), da epígrafe ou da página; `null` se ausente |
| `revogada` | bool \| null | sim | `true`/`false` só com evidência na página oficial; senão `null` |
| `revogada_por` | lista de Relação | sim | vazia se nenhuma encontrada na fonte |
| `alterada_por` | lista de Relação | sim | vazia se nenhuma encontrada na fonte |
| `versao_texto` | enum | sim | `"publicação original"` \| `"consolidada"` |
| `publicacao` | string \| null | sim | texto literal da fonte (ex.: `"DOU de 14/10/2026, seção 1, p. 26"`) |
| `data_publicacao` | date \| null | sim | data de publicação oficial, se informada |
| `edicao` | string \| null | sim | edição do DOU, se informada |
| `ementa` | string \| null | sim | ementa como na fonte |
| `fonte` | URL | sim | URL exata do artefato convertido |
| `fonte_cvm` | URL \| null | sim | página da norma no portal da CVM, quando diferente de `fonte` |
| `sha256_fonte` | hex(64) | sim | SHA-256 dos bytes de `fonte` |
| `formato_fonte` | enum | sim | `html` \| `pdf` \| `docx` \| `doc` |
| `ocr` | bool | sim | `true` se alguma página veio de OCR |
| `baixado_em` | date | sim | data da coleta |
| `anexos` | lista de Anexo | sim | vazia se não houver |
| `natureza` | enum \| null | só `orientação` | `determinação` quando o ofício for ato dirigido a regulado; senão `null` |
| `fase` | enum | só `minuta` | `aberta` \| `em análise` \| `norma publicada` \| `encerrada sem norma` |
| `resultou_em` | lista de Relação | só `minuta` | norma(s) resultante(s) |
| `manifestacoes_url` | URL \| null | só `minuta` | link para a página oficial; texto e nomes não são copiados |

**Relação**: `{ id: <id do documento ou null>, titulo: <string>, url: <URL>, contexto: <trecho literal onde foi encontrada> }`

**Anexo**: `{ rotulo: <string>, url: <URL>, sha256: <hex(64)>, formato: <html|pdf|docx|doc|xlsx> }`

## Tipos

| `classe` | `tipo` (rótulo) / código usado no `id` | Pasta |
|---|---|---|
| norma | `Resolução` / `resolucao` | `reguladores/cvm/resolucoes/<ano>/` |
| norma | `Instrução` / `instrucao` | `reguladores/cvm/instrucoes/<ano>/` |
| norma | `Deliberação` / `deliberacao` | `reguladores/cvm/deliberacoes/<ano>/` |
| norma | `Parecer de Orientação` / `parecer-de-orientacao` | `reguladores/cvm/pareceres-orientacao/<ano>/` |
| norma | `Decisão Conjunta` / `decisao-conjunta` | `reguladores/cvm/decisoes-conjuntas/<ano>/` |
| norma | `Portaria` / `portaria` | `reguladores/cvm/portarias/<ano>/` |
| orientação | `Ofício Circular` / `oficio-circular` | `reguladores/cvm/oficios-circulares/<ano>/` |
| orientação | `Nota Explicativa` / `nota-explicativa` | `reguladores/cvm/notas-explicativas/<ano>/` |
| orientação | `Perguntas e Respostas` / `perguntas-e-respostas` | `reguladores/cvm/perguntas-e-respostas/` |
| orientação | `Manual` ou `Guia` / `manual`, `guia` | `reguladores/cvm/manuais/` |
| minuta | `Audiência Pública` ou `Consulta Pública` / `audiencia-publica`, `consulta-publica` | `reguladores/cvm/audiencias-publicas/<ano>/` |

`<ano>` é o ano de `data`; sem data, a pasta `sem-data/`.

## Identidade e nome de arquivo

- `id` = `cvm-<tipo>-[<unidade>-]<numero>-<ano>`, minúsculo, ASCII, `-` como separador
  (ex.: `cvm-resolucao-175-2022`, `cvm-oficio-circular-sep-02-2024`).
- Arquivo: slug do título no padrão de acervos existentes, sem sufixo de identificador do DOU:
  `resolucao-cvm-n-175-de-23-de-dezembro-de-2022.md`; o consolidado acrescenta `.consolidada`
  antes de `.md`. Sem data no título, usa-se `<id>.md`. O `id` fica no cabeçalho.
- Um documento presente em dois caminhos da fonte tem um único `id`; a URL alternativa vai para o
  relatório de cobertura.

## Corpo

- Início de `Art.`, `§` e `Parágrafo único` em negrito: `**Art. 1º**`, `**§ 2º**`, `**Parágrafo único.**`.
- Incisos (`I –`) e alíneas (`a)`) em parágrafo próprio, sem marcador de lista Markdown.
- `TÍTULO`, `CAPÍTULO`, `SEÇÃO`, `SUBSEÇÃO` como `##`, `###`, `####`, `#####`; `ANEXO …` como `##`.
- Tabelas: Markdown quando a grade é simples; `<table>` HTML quando houver mesclagem
  (`colspan`/`rowspan`) ou célula vazia significativa.
- Texto de OCR: primeira linha do corpo
  `> Texto obtido por OCR a partir de PDF sem camada de texto; pode conter erros de reconhecimento.`
- Texto tachado da fonte preservado como `~~texto~~`.
