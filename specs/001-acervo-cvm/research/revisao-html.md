# Revisão independente do conversor HTML

Consulta e execução: **29/10/2026**, horário de Brasília. Commit examinado:
`88b1e0e79b11f48a799215b79e81dc750c3ee6da`, branch de ticket T004, ainda não integrado.
Esta revisão usa arquivos reais do projeto e entradas sintéticas; não fez novas requisições HTTP.

## Resultado

A suíte existente passou novamente: **43 testes** (35 de T004 e 8 da base comum).
Oito entradas adversariais adicionais reproduziram oito falhas. Em todos esses casos,
`pending_reason` permaneceu `None`, embora o resultado perdesse conteúdo ou aceitasse estrutura
que não pode ser publicada como fiel. Suíte verde não encerra FR-011 ou FR-014.

Os casos e saídas completos estão preservados como evidência local não versionada. Os trechos
abaixo são reproduções sintéticas, não normas reais nem evidência de prevalência no acervo.

## Casos executados

Cada entrada contém uma epígrafe sintética e `Art. 1º Regra.`. A tabela mostra o acréscimo
necessário para reproduzir a falha, sem depender de acesso ao portal.

| Caso | Entrada relevante | Resultado observado | Consequência |
|---|---|---|---|
| H1 — anexo em elemento irmão | Artigos e epígrafe em um `div`; depois dele, `section` com `ANEXO A` e texto obrigatório | O seletor escolheu o `div` mais profundo; o anexo sumiu de `source_text` e do Markdown | A referência usada pelo futuro gate já está truncada; comparar apenas essa referência com a saída não detectaria a omissão |
| H2 — imagem sem descrição | `<img src="formula.png">` dentro do corpo | Imagem descartada, apenas com aviso; conversão continuou sem pendência | Ausência de `alt` não prova que uma imagem seja decorativa; fórmula, quadro ou texto pode desaparecer |
| H3 — protocolo de link inadequado | `<a href="javascript:alert(1)">Regra.</a>` | Saída `[Regra.](javascript:alert(1))` | O conversor não valida protocolo do destino antes de gerar um link |
| H4 — texto de célula interpretado como HTML | Célula com `&lt;limite&gt; &amp; R$`, seguida de célula vazia | Tabela HTML saiu com `<td><limite> & R$</td>`; um parser HTML deixou de ver o texto literal `<limite>` | Faltou escapar texto/atributos ao emitir HTML; preservação visual e textual não está demonstrada |
| H5 — tachado perdido em tabela simples | Cabeçalho `th` e célula `<del>Revogado</del>` | A tabela Markdown contém `Revogado` sem tachado | `_render_markdown_table` usa o texto simples e descarta estilo significativo, também relevante para marcações de alteração |
| H6 — mesclagens sobrepostas | Primeira linha: A com `rowspan=2`, B, C com `rowspan=2`; segunda: D com `colspan=2` | Grade aceita sem pendência, embora D atravesse a coluna já ocupada por C | A validação considera larguras, mas não rejeita toda sobreposição entre células |
| H7 — parágrafos de célula concatenados | `<td><p>Primeira.</p><p>Segunda.</p></td>` | `source_text` e tabela contêm `Primeira.Segunda.` | Limite entre blocos foi perdido antes do gate; em outros textos isso pode fundir palavras |
| H8 — filho não reconhecido de tabela | Um `tr` seguido por `div` com `Nota normativa obrigatória.` dentro de `table` | Nota omitida de `source_text` e Markdown, sem pendência | Ignorar um elemento não suportado com conteúdo é perda silenciosa, mesmo que o HTML de origem seja irregular |

## Arquivos e funções conferidos

- `src/cvm_archive/convert/html.py`: `_select_container`, `_collect_blocks`, `_inline_runs`,
  `_handle_image`, `_table_blocks`, `_grid_is_consistent`, `_render_markdown_table` e
  `_render_html_runs`.
- `src/cvm_archive/normalize/text.py`: regras de dispositivos e headings; não explica nem corrige
  as perdas de seleção/estrutura acima.
- `tests/unit/test_html.py`: fixtures da Resolução 249, golden parcial, contagens e testes
  sintéticos existentes. Os oito casos desta revisão não estavam cobertos por essa suíte.

## Decision

Manter T004 **pendente de correção e nova revisão**. Não integrar esse commit como conversor
aprovado para publicação. A Resolução 249 continua sendo uma fixture positiva útil; não certifica
todos os formatos HTML do portal.

## Rationale

H1, H7 e H8 mostram que a mesma extração pode perder conteúdo tanto na referência quanto no
Markdown. Um gate que compare apenas essas duas saídas pode aprovar uma perda idêntica nos dois
lados. H2, H4, H5 e H6 impedem afirmar preservação de figuras/tabelas. As falhas foram executadas,
não apenas inferidas da leitura do código.

Correções necessárias antes do aceite:

1. Selecionar a íntegra incluindo anexos, notas e assinaturas; conteúdo relevante fora do bloco
   escolhido deve ser incluído ou produzir pendência explícita. Usar referência independente
   para testar que o próprio extrator não truncou o documento.
2. Não classificar imagem desconhecida como decorativa apenas por `alt` vazio ou curto.
3. Validar destinos de links e escapar texto/atributos HTML sem alterar o texto jurídico.
4. Preservar tachado e links nas células; usar HTML quando a tabela Markdown não conservar a
   estrutura ou a formatação relevante.
5. Rejeitar sobreposição de células, preservar limites de parágrafos e colocar conteúdo não
   suportado em pendência, em vez de ignorá-lo.
6. Acrescentar regressões que falhem no commit examinado e passem após a correção; repetir os
   testes em commit exato e árvore limpa.

## Alternatives considered

- Integrar com base nos 43 testes: rejeitado, pois os oito contraexemplos continuam aceitos.
- Corrigir só o gate final: insuficiente quando o texto de referência já foi truncado.
- Publicar toda a página de navegação para evitar seleção: rejeitado; isso não identifica a
  íntegra e pode introduzir conteúdo externo ao ato.
- Tornar toda estrutura desconhecida pendente: aceitável como proteção inicial, desde que o
  relatório mantenha esses atos no denominador e registre a causa.

## UNVERIFIED

- Frequência dessas estruturas no conjunto atual de normas oficiais.
- Preservação integral de 50 documentos HTML, exigida por SC-002.
- Fidelidade de tabelas oficiais complexas e equivalência com PDF/DOCX da mesma edição.
- Segurança de todos os protocolos, atributos e construções HTML possíveis além dos casos
  reproduzidos. Nenhuma conformidade geral foi certificada.

## Correção e integração posteriores

O commit `8bbc7aa` corrige os oito casos acima. Foram acrescentados 14 métodos de regressão,
sem retirar os testes existentes: 57 testes passaram na branch do ticket, em commit exato e
árvore limpa; a suíte integrada executou 88 testes. As oito regressões originais foram
executadas antes da correção e falharam, demonstrando que detectam as perdas examinadas.

| Caso | Comportamento corrigido |
|---|---|
| H1 | Conteúdo fora do corpo selecionado gera pendência; anexos irmãos ainda não são convertidos automaticamente. |
| H2 | Imagem desconhecida, com descrição ausente ou curta, gera pendência. |
| H3 | Protocolos diferentes de HTTP, HTTPS e mailto geram pendência. |
| H4 | Texto e atributos da tabela HTML são escapados. |
| H5 | Tachado e links são preservados nas células. |
| H6 | Sobreposição de mesclagens gera pendência. |
| H7 | Parágrafos mantêm separação; tabelas com blocos internos usam HTML. |
| H8 | Estrutura de tabela desconhecida com conteúdo gera pendência. |

As regressões adicionais cobrem imagem escondida em estrutura não suportada, tachado por
estilo inline, parênteses em links, títulos sem acento, folha de estilo não resolvida e
conteúdo oculto. Estilos externos e conteúdo oculto não são interpretados como prova de
ausência: produzem pendência conservadora.

T004 está apto à integração com essas limitações explícitas. Isto não certifica os 50 HTMLs
de SC-002 nem substitui os gates independentes de T005. Os itens UNVERIFIED acima permanecem.
