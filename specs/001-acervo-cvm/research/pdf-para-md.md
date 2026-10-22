# PDF para Markdown — benchmark real da rodada 2

Data local: 21/10/2026. Escopo: três documentos oficiais, conversões completas, comparação editorial e recomendação para D-5. Este benchmark não implementa o coletor, não importa a semente de 319 atos e não publica um corpus. D-1 a D-6 continuam preservadas em [research.md](../research.md).

## 1. Entradas e cadeia de evidência

Os bytes foram obtidos em nova fila HTTP, com User-Agent identificado, robots.txt conferido e intervalo mínimo de 3 s. Nenhum acesso a `dados.cvm.gov.br/api`. URLs finais, hashes, MIME, datas UTC e headers estão em evidência local não versionada (`http-evidence.json`); a reconferência de catálogo/título/hash está em [reconferencia.md](reconferencia.md).

| Caso real | Entrada usada | Tamanho / páginas com texto | SHA-256 do PDF |
|---|---|---|---|
| Resolução CVM 249, original, 13/10/2026 | [PDF](https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/200/resol249.pdf) e [íntegra HTML](https://conteudo.cvm.gov.br/legislacao/resolucoes/anexos/200/resol249.htm) | 342.863 bytes / **14 páginas** | `24eb8b5a0808c547b8ca78c80b6c79d95509a8dbef63334715e08a642d3f71ef` |
| Parecer de Orientação CVM 40, 11/10/2022 | [PDF](https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/pareceres-orientacao/anexos/Pare040.pdf), acessível pela [página do parecer](https://conteudo.cvm.gov.br/legislacao/pareceres-orientacao/pare040.html) | 1.508.565 bytes / **22 páginas** | `e5b54c00e0f67ac444392a343e510832ec70c4d814e03316b1b3490a03788a90` |
| Resolução CVM 175, consolidada, 23/12/2022 | [PDF consolidado](https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/100/resol175consolid.pdf), vinculado na [página da norma](https://conteudo.cvm.gov.br/legislacao/resolucoes/resol175.html) | 3.259.373 bytes / **399 páginas** | `8921f2352cd918c7640463bebe94a87cbe474774e7ba5bd7a3d1155d1b3d3db8` |

O Parecer 40 oferece também DOCX na página examinada; “só PDF” aqui significa **sem íntegra HTML identificada na página**, não ausência de todo outro formato. Não se inventou uma versão HTML do parecer ou da 175 a partir da página de metadados. A 175 contém parte geral, anexos normativos, suplementos e formulários. Sua própria capa enumera alterações até **240/26**: o rótulo “consolidada” não prova atualização a todas as alterações posteriores.

O HTML 249 tem **39.566 bytes**, SHA-256 `4ecd56d72acffb325d882fbca55ae720f9e1b22ac059385006eb35ecaa20d78b`. Ele inclui o Anexo A no mesmo documento.

## 2. Métodos efetivamente executados

### Poppler e método exato da referência

Foi executado `pdftotext -layout -enc UTF-8` sobre cada PDF completo. O `.txt` cru foi mantido. Em seguida foi chamada **`comum.texto_pdf_para_md` sem alteração**, proveniente de código de terceiro sob MIT (ver `THIRD_PARTY_NOTICES.md`), e preservado o `.md` resultante. Assim, a comparação não atribui a Poppler uma formatação criada por outro parser.

`comum.py:280–319` recompõe parágrafos, retira linhas repetidas na maioria das páginas, descarta linhas exclusivamente numéricas de até três dígitos, reconhece blocos jurídicos e aplica negrito a artigos/parágrafos. **Não reconstrói a geometria de tabelas.** Essa limitação é central para a 175 e pode afetar números isolados em células; não confundir remoção de paginação com prova de que todo número removido era rodapé.

Código exato, licença MIT e hashes estão em evidência local não versionada (`reference/`), com evidência local não versionada (`PROVENANCE.md`). A cópia conserva o LICENSE original; a referência correta para atos oficiais adotada pelo projeto é art. 8º, **IV**, conforme D-2. O benchmark não executa as rotinas de rede/OCR do módulo copiado.

### HTML estrutural

O HTML da íntegra 249 foi convertido pela função **`html2md.convert` da mesma revisão, sem alteração**, com preservação de tachados por padrão. Não foi convertido o HTML de navegação do portal como se fosse íntegra normativa. Para os outros dois casos, **não há saída HTML estrutural comparável**: não foi encontrado link de íntegra HTML no recorte observado.

### Docling

Executado localmente, **Docling 2.141.0**, `docling-core 2.103.1`, `docling-ibm-models 4.0.4`, PyTorch **2.14.1+cpu**, Python **3.13.5**, pipeline PDF padrão, extração de tabelas ligada, **OCR desligado**, **CPU com oito threads**, serviços remotos e plugins externos desligados. O script conserva Markdown e JSON estruturado por documento. A GPU física RTX 4060 Laptop não foi usada: a distribuição instalada de PyTorch informa `cuda.is_available() == false`.

Configuração completa e tempos: evidência local não versionada (`docling-metrics.json`). Código: evidência local não versionada (`run_docling.py`). Revisões baixadas: layout Heron `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`; pacote de modelos `v2.3.0`, commit `fc0f2d45e2218ea24bce5045f58a389aed16dc23`, registradas em evidência local não versionada (`model-revisions.json`). Os modelos são dependências do conversor, não dados do corpus.

A primeira tentativa falhou porque `artifacts_path` foi apontado a um diretório vazio. Essa opção exige modelos já baixados; o caminho foi retirado e o download passou a usar `HF_HOME` isolado em scratch. A falha e seus tempos estão preservados em evidência local não versionada (`docling-initial-failure.json`) e no log correspondente; **não contam como tempo de conversão bem-sucedida**. Windows também emitiu aviso de cache sem symlinks; não foi alterado o modo de desenvolvedor nem pedido privilégio de administrador para suprimi-lo.

### OCR condicionado, não acionado

Nenhuma página ficou sem texto extraível nos três PDFs: mínimos de **487**, **1.547** e **705 caracteres por página**, respectivamente, no Poppler. As páginas renderizadas mostram texto nativo, e não uma digitalização integral. **Tesseract `por` não foi instalado nem executado**, cumprindo o condicionamento pedido. Qualidade de OCR e tempo de Tesseract em documentos escaneados ficam **UNVERIFIED**, sem substituir esse cenário por estimativas. Presença de texto em uma página não certifica extração de toda imagem ou diagrama que ela possa conter.

## 3. Arquivos de saída e tempos

Saídas Windows em evidência local não versionada (`output/`): `<caso>.poppler.raw.txt`, Markdown normalizado por documento, Markdown estrutural da 249, e `docling/<caso>.md` com JSON estruturado. Saídas Poppler/HTML do Linux ficam em `output/linux/`. As entradas foram preservadas em `input/`; binários, ambiente Python, modelos e PNGs de inspeção ficam ignorados, sem entrar nos commits.

Medições de uma execução por documento, sem carga de rede CVM no tempo de conversão. Windows 11, Ryzen 7 8845HS, oito núcleos/16 threads; Linux é **Ubuntu em WSL2 no mesmo computador**, acessando o filesystem montado `/mnt/c`. Versões Poppler distintas e overhead de I/O impedem transformar estes valores em ranking geral de sistemas operacionais.

| Documento | Poppler Windows 26.09.0 | `texto_pdf_para_md`, Windows | HTML estrutural, Windows | Docling Windows, conversão |
|---|---:|---:|---:|---:|
| 249, 14 páginas | **0,071 s** | **0,006 s** | **0,008 s** | **79,548 s** |
| Parecer 40, 22 páginas | **0,074 s** | **0,009 s** | Não disponível no recorte | **16,764 s** |
| 175 consolidada, 399 páginas | **0,719 s** | **0,160 s** | Não disponível no recorte | **570,478 s** |

O primeiro tempo Docling inclui aquisição/inicialização dos modelos na primeira conversão; **não mede inferência aquecida isolada**. Importação/configuração do processo e exportação são medidas separadamente no JSON. Não foi repetida uma bateria estatística nem medida utilização máxima de RAM; percentis e memória de pico são **UNVERIFIED**.

| Documento | Poppler Linux 26.01.0, WSL2 | Conversão + leitura/escrita Markdown, Linux |
|---|---:|---:|
| 249 | **0,299 s** | **0,019 s** |
| Parecer 40 | **0,532 s** | **0,028 s** |
| 175 consolidada | **5,572 s** | **0,157 s** |

HTML 249 no Linux, incluindo leitura do arquivo: **0,017 s**. Os quatro Markdown Poppler/HTML de Windows e Linux são **textualmente iguais após normalizar quebras de linha**; os bytes diferem por CRLF/LF. A comparação está em evidência local não versionada (`quality-metrics.json`). Não se normalizaram os arquivos crus para maquiar a comparação.

## 4. Lado a lado: ordem de leitura e dispositivos da 249

O PDF tem a epígrafe repetida no alto das páginas; o HTML apresenta uma epígrafe e o corpo em sequência. Trechos completos estão nas saídas, os excertos abaixo não substituem a íntegra.

| Ponto | Poppler + conversor de referência | HTML + conversor de referência | Docling padrão |
|---|---|---|---|
| Epígrafe | Removida por repetição; deve voltar do metadado no `# Título` | Mantida antes da ementa | Retida e frequentemente unida ao primeiro parágrafo da página |
| Artigo 1º | `**Art. 1º** Fica instituído o Programa Piloto DLT CVM...` | Mesmo marcador, com itálicos do original onde existem | `Art. 1º Fica instituído...`, sem o negrito jurídico esperado |
| Parágrafo 1º | `**§ 1º** As operações experimentais podem ter por objeto...` | Mesmo marcador e separação | `§ 1º As operações...`, sem negrito |
| Incisos na página 2 | Cada `I –`, `II –` etc. em parágrafo próprio | Mesmo padrão da referência | Vários incisos e o início do Art. 2º no mesmo bloco exportado |
| Cabeçalhos | Um nome CVM dentro do preâmbulo, sem cabeçalhos de página | Um nome CVM dentro do preâmbulo | **14** ocorrências do nome CVM, com cabeçalhos indevidamente incorporados |
| Anexo A | Texto preservado, título ainda sem nível de heading | Texto preservado, título ainda sem nível de heading | Precisa da mesma validação de limite e identidade do anexo |

Exemplo de bloco real do Docling no início da página 2, em `output/docling/resol249.md`:

```markdown
## COMISSÃO DE VALORES MOBILIÁRIOS

[www.cvm.gov.br](http://www.cvm.gov.br/)

RESOLUÇÃO CVM Nº 249, DE 13 DE OUTUBRO DE 2026 I - têm natureza experimental, vedada a participação de investidores reais, a utilização de valores mobiliários efetivamente emitidos ou em circulação e a movimentação de recursos financeiros reais; II - não representam autorização para o exercício de atividades reguladas,
```

O excerto foi cortado **após a vírgula** para caber no relatório; no arquivo real o parágrafo continua até outros incisos/artigos. Não é ausência do restante da norma, mas quebra inadequada de blocos e contaminação por cabeçalho. O maior parágrafo exportado por Docling tem **2.558 caracteres**, contra **542** nos outros dois caminhos.

A métrica de **início de linha**, não de presença de dispositivo, é: Poppler/HTML **26 artigos, 15 parágrafos numerados e 99 incisos romanos**; Docling **3, 3 e 0**. Isso comprova a diferença de estrutura editorial, **não perda automática de 23 artigos**: há dispositivos dentro de blocos maiores. A 249 não fornece alíneas `a)` em início de bloco nesse recorte; o caso com alíneas é o Parecer 40 e a 175.

A comparação dos tokens ordenados HTML × Poppler encontrou somente a ausência da epígrafe inicial no caminho PDF. Razão de similaridade descritiva: **0,998825**; retirando essa epígrafe, a sequência de tokens do corpo coincide. **Esse diagnóstico ignora pontuação, links, estilos e geometria**, logo não aprova sozinho fidelidade jurídica ou diagramação. evidência local não versionada (`analyze_outputs.py`) registra a regra e os resultados. Uma contagem preliminar de parágrafos feita pelo terminal teve problema de codificação; foi descartada em favor da análise UTF-8 reproduzível, que retorna **15 nos dois caminhos**.

## 5. Lado a lado: Parecer 40, notas, alíneas e hifenização

O documento é um parecer com seções e notas, não um articulado que precise ser artificialmente reescrito em Art./§.

| Critério | Poppler + de referência | Docling padrão |
|---|---|---|
| Início | Epígrafe, subtítulo e seção 1 antes da prosa | Exportação começa pela seção 1; a epígrafe/subtítulo da primeira página aparecem depois das primeiras notas |
| Alíneas | **18** inícios `a)` etc. preservados | Também **18**; não basta esse número para aprovar a ordem global |
| Notas de rodapé | Texto das notas permanece, mas marcadores/sobrescritos não viram referências Markdown; mistura corpo e notas | Reconhece parte como `footnote` (12 itens no JSON), mas não remove a necessidade de revisar associação e ordem |
| Cabeçalho de endereços | Retirado por repetição: **0** ocorrências de “Rua Sete de Setembro” no `.md` | **22** ocorrências; endereço e nome do órgão repetidos entre o corpo |
| Seções | `1. Objeto deste Parecer de Orientação` é texto simples | `## 1. Objeto deste Parecer de Orientação`, melhor hierarquia local |
| Tabelas | Não há tabela comparável identificada neste caso | Zero tabelas detectadas; não é uma deficiência por si só |

**Exemplo verificável de hifenização em URL**, nota 3 da página 1, conferida também no PNG renderizado:

| Evidência | Trecho real |
|---|---|
| PDF / Poppler cru | `https://www.oecd.org/daf/fin/financial-` seguido de quebra de linha e `markets/Why-Decentralised-Finance-DeFi-Matters-and-the-Policy-Implications.pdf` |
| Markdown Poppler + de referência | `.../financial- markets/Why-Decentralised-Finance-DeFi-Matters-and-the-Policy-Implications.pdf` |
| Markdown Docling | `.../financialmarkets/Why-Decentralised-Finance-DeFi-Matters-and-the-Policy-Implications.pdf` |
| Normalização necessária | Unir a quebra **preservando o hífen**: `.../financial-markets/Why-Decentralised-Finance-DeFi-Matters-and-the-Policy-Implications.pdf` |

Os links externos acima são transcrição do PDF, **não URLs requisitadas nesta rodada**. Há também quebra semelhante em `legal-` / `content`. Logo, “remover todo hífen no fim da linha” é regra incorreta. URLs, identificadores como `2.228-1` e palavras com hífen lexical precisam ser preservados; remover hífen só quando houver evidência de separação editorial, mantendo auditoria da transformação.

## 6. Lado a lado: 175 consolidada, tabelas e anexos

A conversão completa terminou: **399 páginas, 123 tabelas, 570,478 s**, exportação Markdown/JSON em mais **1,809 s**, status `SUCCESS` e lista `errors` vazia. O log, porém, contém quatro avisos de células descartadas (1 + 3 + 3 + 2 = **9 células**). Sucesso operacional não certifica fidelidade. O Markdown contém 2.010 linhas iniciadas por `|`, mas também 400 ocorrências do nome do órgão e 399 do endereço; cabeçalhos continuam incorporados. Qualidade integral das 399 páginas: **UNVERIFIED**.

Foram inspecionadas visualmente a capa, a página 12 e as páginas físicas **361 e 366** do PDF. Na 361 há o formulário do Suplemento J e uma tabela de ativos; na 366, matrizes de emissores, incluindo LIG. Os índices de tabela a seguir são base zero no JSON completo: 77/78 na 361, 84 na 366.

| Página / critério | Poppler cru `-layout` | Poppler + conversor | Docling completo |
|---|---|---|---|
| 361, formulário | Mantém alinhamento por espaços: `Nome da Classe`, `CNPJ da Classe`, `Data de Funcionamento`; rótulos longos quebram em linhas | Retira geometria e transforma campos em parágrafos; não preserva células vazias nem mesclagens | JSON: matriz 10 × 3; separa `Classe Exclusiva`, `Classificação autorregulação` e `Prazo de Duração`. Markdown replica textos de células mescladas em colunas |
| 361, ativos | `Relação de terrenos...`, `Área (m2)`, `% do terreno...`, `% em relação às receitas do FII.` alinhados, com cabeçalhos partidos | Junta cabeçalhos e linhas; zero linhas de tabela Markdown no documento inteiro | JSON: matriz 10 × 9; os quatro rótulos estão presentes, mas a grade contém subdivisões/mesclagens que exigem comparação com a fonte |
| 366, LIG | Conserva espaços entre `Emissor`, `CNPJ`, `Vencimento`, `Quantidade`, `Valor`; também extrai um `Valor` na linha Emissor 1 não visível na renderização | Achata os emissores e a próxima seção num bloco contínuo | JSON: matriz 39 × 7; funde `Emissor N Letra Imobiliária Garantida (LIG)`; o Markdown propaga esse texto pelas colunas mescladas. Não resolve o texto extra `Valor` |

Trecho literal Poppler cru, página 366 (espaços preservados):

```text
          Emissor            CNPJ               Vencimento Quantidade                Valor
          Emissor 1                                                                  Valor
          Emissor 2
          Emissor N
```

Trecho literal após o conversor de parágrafos:

```text
Emissor 2 Emissor N 1.2.4 Letra Imobiliária Garantida (LIG) Emissor CNPJ Vencimento Quantidade Valor Emissor 1 Valor Emissor 2 Emissor N 1.2.5 Certificado de Potencial Adicional de Construção (CEPAC)
```

### Teste real: somente regiões de tabela → HTML dentro do Markdown

Quatro regiões foram recortadas como PDFs vetoriais, mantendo a camada textual. As primeiras três usam caixas detectadas na conversão completa, com margem de 3 pontos; a quarta foi delimitada manualmente. Não foi testado um detector autônomo de regiões. Mesmo Docling 2.141.0, CPU/oito threads, modelos locais em cache, OCR desligado. A exportação usou `export_to_html(labels={DocItemLabel.TABLE})`; os elementos `<table>` foram inseridos **diretamente no `.md`**, sem cercas de código. JSON, recortes, imagens e saídas são evidência local não versionada (`table-region-metrics.json`, `table-region-run.log`, `output/table-regions/`).

| Região | Caixa em pontos PDF, origem superior esquerda | Conversão | Resultado real |
|---|---|---:|---|
| 361, formulário | (52,721; 237,591)–(570,345; 456,964) | **16,114 s** | 1 tabela, 10 × 3; 6 atributos `colspan`, nenhum `rowspan`. Funde três rótulos em uma célula e deixa `houver)` isolado na seguinte; pior que o JSON da página completa nesse trecho |
| 361, ativos | (53,280; 464,770)–(570,093; 780,263) | **38,421 s** | 1 tabela, 13 × 5; 11 `colspan`, nenhum `rowspan`. Aviso: **22 de 97 células PDF descartadas** na tentativa de grade 126 × 12; `Área (m2)` e `% do terreno...` não aparecem nas células correspondentes exportadas |
| 366, bloco de emissores | (53,406; 184,196)–(570,082; 783,649) | **9,096 s** | 1 tabela, 39 × 6; 22 `colspan`, nenhum `rowspan`. Separa o título LIG de Emissor N, mas funde `CNPJ Vencimento` e mantém o `Valor` extra |
| 366, somente LIG | (54; 215)–(570; 299) | **UNVERIFIED**: duração não persistida | JSON foi salvo com **zero tabelas**; exportação abortou com `No HTML tables exported for p366-lig`. Não foi fabricado HTML para compensar a falha |

Excertos literais dos HTMLs emitidos, apresentados como código para tornar os defeitos legíveis no relatório (nas saídas locais são HTML ativo dentro do Markdown):

```html
<!-- Página 361: formulário; rótulos indevidamente fundidos -->
<tr><td>Classe Exclusiva (Sim ou Não) Classificação autorregulação (se Prazo de Duração</td><th colspan="2">Cotistas possuem vínculo familiar ou societário familiar (Sim ou Não)</th></tr>
<tr><td>houver)</td><th colspan="2">Encerramento do exercício social</th></tr>
<!-- Página 366: título separado, duas colunas indevidamente fundidas -->
<tr><th>1.2.4</th><th colspan="5">Letra Imobiliária Garantida (LIG)</th></tr>
<tr><td></td><th>Emissor</th><td colspan="2">CNPJ Vencimento</td><td>Quantidade</td><td>Valor</td></tr>
```

**Recomendação para tabelas:** HTML no Markdown é a representação adequada para mesclagens, porém **Docling regional não foi aprovado como conversor automático fiel** nesta amostra. O recorte pode melhorar um limite e piorar células. Conservar Poppler cru e a imagem como evidência; tratar Docling/JSON/HTML como proposta de reconstrução, confrontar cada célula, vazios e mesclagens com o PDF e corrigir/revisar antes de publicar. Células descartadas, título fundido, coluna ausente ou tabela não detectada bloqueiam a publicação daquela tabela. Não publicar a prosa achatada nem substituir uma falha por conteúdo inferido. Detecção automática de regiões, continuidade entre páginas e taxa de aprovação no corpus completo: **UNVERIFIED**. Esta conclusão complementa a pesquisa e **não reescreve D-5**, que permanece decisão do usuário.

## 7. Recomendação de pipeline e pós-processamento

**Recomendação sustentada pelas três conversões completas e pelo teste regional:** priorizar **HTML estrutural** quando houver íntegra oficial; para PDF textual, conservar **Poppler `-layout` como extração auditável**, separando reconstrução de prosa da reconstrução de tabelas. **Não adotar Docling padrão para toda norma só porque a saída já termina em `.md`**: nos casos pequenos houve regressão de ordem, blocos e cabeçalhos. Para tabelas, aplicar o controle editorial da seção 6; o teste regional não demonstrou fidelidade automática.

Pós-processamento necessário para chegar ao padrão D-3:

1. **Bytes e identidade:** preservar fonte e hash, distinguir original/consolidada, nunca substituir a data do ato pela data da coleta. Emitir UTF-8 e LF de forma explícita; guardar métrica de transformação.
2. **Cabeçalhos e rodapés:** detectar repetição **por zona geométrica de página e seção**, excluir numeração somente da área de rodapé e preservar uma epígrafe canônica no título. Não apagar números só porque estão isolados nem manter endereços repetidos entre incisos.
3. **Blocos jurídicos:** normalizar os inícios de Art., § e Parágrafo único em negrito, sem inventar ponto/ordinal; manter incisos `I –` e alíneas `a)` em parágrafos próprios. Usar limites reais de bloco, sem promover referências incidentais no meio da frase a artigos novos.
4. **Hierarquia:** seguir a convenção da referência para títulos/capítulos/seções, separar anexos/suplementos e incluir o escopo do anexo nos IDs de dispositivos. A letra `A` em `ANEXO A` precisa ser reconhecida; o conversor copiado só cobre certos rótulos romanos/numéricos nesse padrão.
5. **Tabelas:** preservar matriz e células vazias, títulos, unidades, notas, `rowspan`/`colspan` e continuidade entre páginas. Usar tabela Markdown somente quando representar a estrutura; preferir HTML de tabela no `.md` para mesclagens, como já permite a referência, com revisão visual. Nunca publicar prosa achatada como se fosse tabela fiel.
6. **Hifenização e links:** resolver quebras antes de perder o contexto de linha; proteger URLs, códigos e hífens lexicais. Validar links contra a transcrição da fonte sem acessar indiscriminadamente domínios citados pelo documento.
7. **Notas e marcas:** vincular notas ao ponto de chamada, preservar tachados, versões alteradas e remissões. Retirar decoração não pode apagar conteúdo normativo. Não atribuir vigência a partir de ausência de tachado.
8. **Portões editoriais:** confrontar sequência de dispositivos e tokens, células/títulos, anexos e notas com a fonte; comparar páginas renderizadas. Contagens ou similaridade alta não substituem revisão do que pode ter sido fundido, deslocado ou omitido. Falha vira pendência explícita.

Essas regras são a recomendação de pesquisa; não foi escrito um normalizador de produção nem declarada qualidade universal a partir de três PDFs. O único exemplo final normalizado abaixo é gerado integralmente a partir da íntegra HTML 249, com mudanças mínimas e verificáveis.

## 8. Exemplo final completo no formato D-3

Arquivo completo: evidência local não versionada (`resol249.final-example.md`). Gerador: evidência local não versionada (`make_final_example.py`). Ele conserva todos os **4.260 tokens** do corpo HTML convertido, na mesma ordem, adiciona front matter e `# Título`, normaliza Unicode/espaços e promove o rótulo literal `ANEXO A` a heading. Esse teste não cobre pontuação ou geometria de outras fontes. evidência local não versionada (`final-example-check.json`).

O cabeçalho segue o formato da publicação original 239/2026 examinado na referência e acrescenta os campos de D-3. `edicao` está ausente na página consultada e fica `null`; `revogada: null` é desconhecido. As listas vazias registram relações não identificadas na página, sem afirmar inexistência jurídica de alteração/revogação. O Anexo A é interno ao mesmo HTML, por isso usa URL/hash do artefato que o contém; não foi inventado um download separado.

```yaml
---
titulo: "RESOLUÇÃO CVM Nº 249, DE 13 DE OUTUBRO DE 2026"
orgao: "Comissão de Valores Mobiliários"
tipo: "Resolução"
numero: "249"
data: 2026-10-13
revogada: null
versao_texto: "publicação original"
publicacao: "DOU de 14/10/2026"
data_publicacao: 2026-10-14
edicao: null  # UNVERIFIED: não informada na página consultada
fonte: "https://conteudo.cvm.gov.br/legislacao/resolucoes/anexos/200/resol249.htm"
baixado_em: 2026-10-21
sha256_fonte: "4ecd56d72acffb325d882fbca55ae720f9e1b22ac059385006eb35ecaa20d78b"
fonte_cvm: "https://conteudo.cvm.gov.br/legislacao/resolucoes/resol249.html"
alterada_por: []  # Nenhuma relação identificada na página
revogada_por: []  # Nenhuma relação identificada na página
anexos:
  - rotulo: "ANEXO A — MODELO DE TERMO DE ADESÃO AO PROGRAMA PILOTO DLT CVM"
    url: "https://conteudo.cvm.gov.br/legislacao/resolucoes/anexos/200/resol249.htm"
    sha256: "4ecd56d72acffb325d882fbca55ae720f9e1b22ac059385006eb35ecaa20d78b"
unidade: null
---
```

Trecho literal do corpo, que segue ao `# RESOLUÇÃO CVM Nº 249, DE 13 DE OUTUBRO DE 2026` e à epígrafe/ementa/preâmbulo preservados no arquivo completo:

```markdown
#### CAPÍTULO I – ÂMBITO, FINALIDADE E CARÁTER EXPERIMENTAL

**Art. 1º** Fica instituído o Programa Piloto DLT CVM, programa de testes destinado à realização de operações experimentais de emissão, oferta, distribuição, negociação, escrituração, custódia, depósito centralizado e liquidação de valores mobiliários em redes de tecnologia de registro distribuído (*distributed ledger technology* – DLT) admitidas nos termos desta Resolução.

**§ 1º** As operações experimentais podem ter por objeto quaisquer das espécies de valores mobiliários de que trata o art. 2º da Lei nº 6.385, de 1976, tais como ações, debêntures, certificados de recebíveis, cotas de fundos de investimento e demais títulos ou contratos de investimento coletivo.

**§ 2º** O Programa Piloto DLT CVM insere-se no âmbito dos trabalhos do Grupo de Trabalho de Tokenização – GTT, instituído pela Portaria CVM/PTE nº 177, de 15 de julho de 2026, e observará os prazos nela estabelecidos.

**§ 3º** As atividades desenvolvidas no âmbito do Programa Piloto DLT CVM:

I – têm natureza experimental, vedada a participação de investidores reais, a utilização de valores mobiliários efetivamente emitidos ou em circulação e a movimentação de recursos financeiros reais;
```

O último inciso é somente um excerto editorial do relatório; a íntegra do exemplo mantém os demais incisos, os 26 artigos, a assinatura e o formulário do Anexo A. Campos `[•]` e similares no formulário são **literais da fonte oficial**, não preenchimentos inventados pelo benchmark.

## 9. Dependências e reprodução em Windows/Linux

| Caminho | Windows testado | Linux/WSL testado ou limite |
|---|---|---|
| Poppler | Binários 26.09.0 do empacotamento `oschwartz10612/poppler-windows`; ZIP verificado contra SHA-256 publicado `7a6f256a0ddf7536182246a5733331bf4677cbcc34f4663774947ad34556c8d0`. Download/extração medidos em **6,969 s**, isolados do tempo de conversão | `apt-get install poppler-utils`, versão 26.01.0. Execuções reais na mesma entrada, não estimativas |
| Parser da referência | Python 3.14.3 e biblioteca padrão; Poppler externo. Não aciona Swift/Vision | Python 3.14.4 e biblioteca padrão; sem dependências Python extras para esse caminho |
| Docling | Venv Python 3.13.5 via `uv`; resolução/instalação observada de **112 pacotes**, com aproximadamente 62 s de preparação/instalação, fora da conversão. Lista exata em `requirements-windows.txt`; modelos baixados à parte | Documentação oficial declara suporte Linux. **Instalação e tempos Docling em Linux: UNVERIFIED**, não executados |
| OCR futuro | Tesseract e dados `por` seriam dependências externas caso apareça PDF escaneado; não instalados aqui | Mesmo condicionamento; não executar OCR apenas porque o arquivo tem extensão PDF |

Reprodução local: os runners `verify_sources.py`, `run_baselines.py`, `run_docling.py`, `run_table_regions.py`, `run_linux.py`, `make_final_example.py` e `analyze_outputs.py` permanecem como evidência local não versionada. Não são ferramentas distribuídas por este repositório. A captura de rede é separada da reanálise dos bytes preservados. O baseline usa Poppler e o conversor MIT; Docling usa venv Python 3.13 e as versões/opções registradas acima. A lista exata local é `requirements-windows.txt`. Binários, modelos e fontes brutas não entram nos commits. PyTorch CPU foi usado aqui; desempenho CUDA, containers de produção, Linux nativo e corpus completo permanecem **UNVERIFIED**.

Documentação primária consultada: [instalação Docling](https://docling-project.github.io/docling/getting_started/installation/), [CLI Docling](https://docling-project.github.io/docling/reference/cli/) e código/tipos efetivamente instalados. A CLI instalada tem subcomando `docling convert`; o benchmark usa API Python com opções registradas, sem depender de uma assinatura lembrada de outra versão.
