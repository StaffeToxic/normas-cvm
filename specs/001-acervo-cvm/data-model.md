# Data Model — Acervo de normas da CVM

**Feature**: `001-acervo-cvm`
**Data**: 2026-10-22
**Status**: desenho conceitual; nenhuma classe, módulo ou código é criado nesta etapa.

Este documento descreve as entidades, os invariantes e as transições de estado necessárias para implementar o acervo. Ele não substitui os contratos públicos: o cabeçalho YAML continua regido por `contracts/front-matter.md` (schema 1.0) e o relatório por `contracts/coverage-report.md`. Em caso de conflito, valem a constituição e os contratos.

## 1. Decisões transversais

- **Stack prevista**: Python 3.12 com biblioteca padrão. O MVP cobre a coleta e a conversão de resoluções com íntegra HTML oficial. PDF, OCR, tabelas, demais famílias, orientações, minutas e operação incremental são fases posteriores; o modelo já reserva os campos contratuais necessários para elas, sem ampliar o schema por antecipação.
- **Fonte oficial prevalece**: todo valor publicado vem da fonte oficial ou é `null`. Não se infere vigência, número, data, unidade, relação ou anexo.
- **Identidade é derivada, não inventada**: `id` segue a fórmula do contrato. Documento sem número ou sem ano não recebe número, ano ou sufixo sintético; fica pendente até decisão explícita de contrato.
- **Proveniência do artefato**: o hash de `Artifact` é o SHA-256 dos bytes baixados. `sha256_fonte` é o hash dos bytes do artefato declarado em `fonte`. O hash do Markdown gerado é outro valor, usado apenas para detectar mudança de saída; ele nunca substitui o hash dos bytes de origem.
- **Cobertura é do catálogo**: o denominador é o catálogo oficial por categoria, nunca 319 arquivos auxiliares, 241 identidades ou 9 casos de triagem.
- **Falha não apaga história**: falha de catálogo ou de coleta não substitui nem apaga a cobertura anterior. Uma nova cobertura só é promovida depois de gerada e validada por inteiro.
- **Direitos**: o texto oficial pode ser coletado da fonte oficial. A licença da compilação auxiliar externa permanece `UNVERIFIED`; isso não bloqueia a coleta direta da fonte oficial. Corpo proveniente da compilação externa só pode ser publicado após verificação de licença e proveniência.
- **Sem campos públicos não contratados**: dados auxiliares de origem, revisão ou licença externa ficam em registro auxiliar; não entram no front matter nem no `cobertura.json` sem decisão de schema.

### 1.1 Fases

| Fase | Escopo | Efeito no modelo |
|---|---|---|
| MVP | Resoluções com íntegra HTML oficial; catálogo, artefato, metadados, conversão e cobertura | Usa `formato_fonte: html`; tabela não reproduzível fica pendente; nenhum corpo auxiliar externo é publicado |
| Posterior | PDF com camada de texto | `formato_fonte: pdf`; `ocr: false`; o mesmo `sha256_fonte` passa a apontar para o PDF convertido |
| Posterior | OCR em páginas sem texto | `ocr: true`; aviso obrigatório no início do corpo; `warnings` registra as páginas afetadas |
| Posterior | Tabelas dedicadas | Tabela real em Markdown ou HTML; se não reproduzível, `pendente` com motivo, nunca texto achatado |
| Posterior | Demais famílias, orientações e minutas | Novos `tipo`/`classe` do contrato; nenhum enum novo sem decisão de schema |
| Posterior | Coleta incremental | `sha256_fontes` é o índice de mudança; comparação por URL e hash, sem depender de cache persistente |

## 2. Visão geral

| Relação | Cardinalidade | Regra |
|---|---|---|
| `CatalogEntry` → `Artifact` | 1 para 0..n | Um registro do catálogo pode ter artefatos de íntegra, consolidado, anexos e variantes |
| `Artifact` → `Conversion` | 1 para 0..1 | Cada artefato tem uma conversão candidata corrente; tentativas anteriores não são apagadas do histórico de coleta |
| `Conversion` → `DocumentMetadata` | 0..1 para 1 | Só existe metadado publicável quando a conversão passou pelos gates e tem proveniência completa |
| `CatalogEntry` → registro de `Coverage` | 1 para 1 | Todo item do catálogo no escopo tem estado explícito na cobertura |
| `Coverage` → `categorias` | 1 para n | Cada categoria agrega totais do catálogo, não do acervo auxiliar |

Um artefato é imutável para fins de identidade: a mesma URL com bytes diferentes gera um novo `Artifact`, não sobrescreve o anterior. A conversão é um candidato; ela não altera metadados oficiais e não publica nada por si só.

## 3. `Artifact`

Representa os bytes exatos baixados de uma origem. Não é o documento publicado e não carrega metadados jurídicos.

| Campo | Tipo | Nulabilidade | Regra |
|---|---|---|---|
| `url` | URL absoluta | não nula | URL exata de onde os bytes foram obtidos; não é a página de metadados por conveniência |
| `bytes` | bytes | não nulo | Conteúdo bruto, sem normalização; usado para hash, extração e conferência |
| `sha256` | hex(64) | não nulo | SHA-256 de `bytes`; distinto do hash do Markdown |
| `content_type` | string | não nulo | Tipo declarado ou detectado do artefato; `html`, `pdf`, `docx` e `doc` são os formatos contratuais relevantes |
| `fetched_at` | data/hora UTC | não nula | Momento real da coleta; não é a data de publicação do ato |

Invariantes:

- `sha256` é calculado sobre os bytes efetivamente usados, não sobre uma versão transformada.
- Os `bytes` de origem não são publicados no `.md`; são cache de trabalho e prova de conferência.
- Um artefato só pode instruir um `DocumentMetadata` se seu `sha256` for exatamente o `sha256_fonte` do metadado e seu `url` for exatamente o `fonte` declarado.
- HTML do DOU, PDF da CVM e Markdown gerado são artefatos/saídas distintos; um hash não prova os outros.
- Um DOCX/DOC auxiliar de tabela é um artefato separado e não substitui o artefato do corpo.

## 4. `CatalogEntry`

Representa um item descoberto no catálogo oficial, antes de qualquer conversão.

| Campo | Tipo | Nulabilidade | Regra |
|---|---|---|---|
| `url` | URL absoluta | não nula | Página canônica do item no catálogo oficial; aliases vão para a cobertura; nome interno alinhado ao plano |
| `title` | string | não nula | Título como no catálogo; não normalizar caixa nem corrigir por suposição |
| `category` | string | não nula | Família do catálogo; o `tipo` contratual é confirmado pela epígrafe antes da publicação |
| `date` | date | nula | Data do ato, quando o catálogo ou a epígrafe a informar; ausência vira `null` |
| `number` | string | nula | Número como na fonte, sem zeros à esquerda; ausência vira `null` |

Invariantes:

- `CatalogEntry` não tem `id` próprio. A identidade publicada é calculada conforme o contrato, depois de confirmar classe, tipo, unidade, número e ano.
- `url` é a página do ato apontada pelo catálogo, não necessariamente o artefato convertido nem a listagem de resultados. A distinção entre `fonte` e `fonte_cvm` ocorre em `DocumentMetadata`.
- Um item sem número ou sem data não recebe número/data inventados. Se a fórmula de identidade não puder ser aplicada, a publicação fica bloqueada até decisão de contrato.
- Categoria não é destino automático: a epígrafe prevalece sobre a pasta ou o rótulo do catálogo.
- O catálogo oficial é a fonte do denominador de cobertura. Uma entrada ausente não é apagada silenciosamente do histórico.

## 5. `DocumentMetadata` — schema 1.0

É o cabeçalho YAML do `.md`, conforme `contracts/front-matter.md`. Campos obrigatórios devem existir como chave; campos anuláveis usam `null` quando o valor é desconhecido. Ausência de chave não é equivalente a `null`.

### 5.1 Campos sempre presentes

| Campo | Tipo | Nulabilidade | Regra |
|---|---|---|---|
| `schema_versao` | string | não nula | `"1.0"` nesta versão |
| `id` | string | não nula | Identidade estável pela fórmula contratual; não usar caminho ou sufixo do DOU |
| `classe` | enum | não nula | `norma` \| `orientação` \| `minuta` |
| `tipo` | string | não nula | Rótulo contratual confirmado pela epígrafe |
| `titulo` | string | não nula | Título como na fonte, sem normalizar caixa |
| `orgao` | string | não nula | `"Comissão de Valores Mobiliários"`; em ato conjunto, todos os órgãos separados por ` / ` |
| `unidade` | string \| null | obrigatória, anulável | Unidade emissora somente quando a fonte a informar; senão `null` |
| `numero` | string \| null | obrigatória, anulável | Como na fonte, sem zeros à esquerda; senão `null` |
| `data` | date \| null | obrigatória, anulável | Data do ato; senão `null` |
| `revogada` | bool \| null | obrigatória, anulável | `true`/`false` somente com evidência na página oficial; senão `null` |
| `revogada_por` | lista de Relação | não nula | Vazia quando nenhuma relação foi encontrada na fonte consultada |
| `alterada_por` | lista de Relação | não nula | Vazia quando nenhuma relação foi encontrada na fonte consultada |
| `versao_texto` | enum | não nula | `"publicação original"` \| `"consolidada"`; nenhum terceiro valor |
| `publicacao` | string \| null | obrigatória, anulável | Texto literal da fonte, quando houver |
| `data_publicacao` | date \| null | obrigatória, anulável | Data de publicação oficial, quando informada |
| `edicao` | string \| null | obrigatória, anulável | Edição do DOU, quando informada |
| `ementa` | string \| null | obrigatória, anulável | Ementa como na fonte; senão `null` |
| `fonte` | URL | não nula | URL exata do artefato convertido |
| `fonte_cvm` | URL \| null | obrigatória, anulável | Página da norma na CVM quando distinta de `fonte`; `null` quando `fonte` já é essa página ou quando não há valor verificável, sem inventar URL |
| `sha256_fonte` | hex(64) | não nula | SHA-256 dos bytes de `fonte`; nunca o hash do Markdown |
| `formato_fonte` | enum | não nula | `html` \| `pdf` \| `docx` \| `doc` |
| `ocr` | bool | não nula | `true` se alguma página veio de OCR |
| `baixado_em` | date | não nula | Data real da coleta |
| `anexos` | lista de Anexo | não nula | Vazia quando nenhum anexo foi encontrado na fonte consultada; não é prova universal de inexistência |

### 5.2 Campos condicionais

| Campo | Quando existe | Regra |
|---|---|---|
| `natureza` | `classe: orientação` | `determinação` somente quando a fonte caracterizar ato dirigido a regulado; senão `null` |
| `fase` | `classe: minuta` | `aberta` \| `em análise` \| `norma publicada` \| `encerrada sem norma` |
| `resultou_em` | `classe: minuta` | Lista de Relação; vazia se nenhuma norma resultante foi encontrada na fonte |
| `manifestacoes_url` | `classe: minuta` | URL da página oficial; texto e nomes de participantes nunca são copiados |

### 5.3 Relação e Anexo

**Relação**: `id` (id do documento ou `null`), `titulo`, `url`, `contexto` (trecho literal onde foi encontrada).

**Anexo**: `rotulo`, `url`, `sha256` (hex dos bytes do anexo) e `formato` (`html`, `pdf`, `docx`, `doc` ou `xlsx`).

`alterada_por: []` e `revogada_por: []` significam **nenhuma relação encontrada na fonte consultada**, não inexistência jurídica universal. Para `anexos: []`, a descoberta na fonte consultada precisa estar concluída: um anexo mencionado no corpo, ausente ou ainda não inspecionado não pode ser ocultado por uma lista vazia; o artefato fica pendente. Isso não afirma inexistência de anexos em outras fontes.

### 5.4 Identidade, versão e nomes

- `id = cvm-<tipo>-[<unidade>-]<numero>-<ano>`, minúsculo, ASCII e com `-`; exemplos corretos incluem `cvm-deliberacao-870-2021`, `cvm-parecer-de-orientacao-39-2021` e `cvm-parecer-de-orientacao-40-2022`.
- Tipo, ID e pasta são corrigidos pela epígrafe. Uma Deliberação não se torna Resolução porque está na pasta de resoluções; um Parecer de Orientação não se torna “Parecer Normativo” porque o rótulo auxiliar diz isso.
- O caminho do arquivo não inclui sufixo de identificador do DOU. O `id` fica no cabeçalho; aliases e URLs alternativas ficam na cobertura.
- Original e consolidado são arquivos distintos, com o mesmo `id` de ato e `versao_texto` diferente. Um não substitui o outro.
- `versao_texto` tem exatamente os dois valores do contrato. Republicação não vira `original` nem `consolidada` por conveniência; não se inventa um terceiro valor.
- As três republicações identificadas na fase de pesquisa ficam pendentes **por artefato**: a 59/2021 com `revisao-manual`; as 100/2022 e 110/2022 com `republicacao-parcial`. Se houver outro artefato oficial independente e íntegro, ele pode seguir o fluxo normal; o artefato republicado não é completado silenciosamente com texto de outra fonte.
- Documento sem número, como FAQ ou manual, não recebe número sintético nem `id` improvisado. A publicação exige decisão prévia de contrato sobre identidade; até lá, o registro fica pendente e `numero` permanece `null`.
- Documento sem data não recebe ano inventado. A pasta `sem-data/` é permitida pelo contrato, mas a fórmula de `id` com ano exige decisão específica antes de publicar.

## 6. `Conversion`

Representa a tentativa de transformar um artefato em Markdown. É interna ao pipeline e não é um contrato público de leitura.

| Campo | Tipo | Nulabilidade | Regra |
|---|---|---|---|
| `source_text` | string | não nula | Texto normalizado extraído do artefato, usado para comparação e gates; não é o corpo publicado |
| `markdown` | string | não nula | Candidato a corpo Markdown, UTF-8 com LF, na ordem da fonte |
| `warnings` | lista de string | não nula | Avisos de OCR, tabela, resíduo ou proveniência; vazia se não houver |
| `pending_reason` | string \| null | anulável | Se não nulo, a conversão não publica; o motivo deve ser registrado na cobertura |

Invariantes:

- `source_text` não pode ser editado para “melhorar” o texto; ele é a base de comparação com o artefato.
- `markdown` só se torna público se `pending_reason` for `null`, os gates de fidelidade passarem e o metadado estiver completo.
- `warnings` não substitui `pending_reason`: um aviso de OCR é obrigatório no corpo, mas não impede por si só a publicação se o gate passar.
- `pending_reason` usa os motivos já previstos no contrato de cobertura quando aplicável, como `tabela-nao-reproduzida`, `portao-fidelidade`, `ocr-pendente`, `soft-404` e `revisao-manual`. Não se cria um enum novo para conveniência; `republicacao-parcial` é o motivo registrado para as duas republicações parciais.
- O hash do Markdown é calculado e comparado para detectar mudanças, mas não é `Artifact.sha256` nem `DocumentMetadata.sha256_fonte`.
- A conversão não preenche `revogada`, relações ou anexos por inferência; esses valores vêm da fonte oficial.

## 7. `Coverage`

Segue o contrato atual de cobertura. O relatório é uma fotografia do catálogo, não do acervo auxiliar.

### 7.1 Estrutura

| Nível | Campos | Regra |
|---|---|---|
| Raiz | `schema_versao`, `gerado_em`, `coleta`, `categorias`, `documentos`, `divergencias` | `coleta.modo` é `completa` \| `incremental` \| `documento`; `coleta` contém `requisicoes` e `falhas_http`; `gerado_em` é o momento da geração em UTC |
| Categoria | `tipo`, `catalogo_total`, `catalogo_metodo`, `publicados`, `pendentes`, `indisponiveis`, `divergentes`, `fora_de_escopo` | Cobertura 1.1: contador opcional `fora_de_escopo` tem default zero para arquivos antigos; a soma dos estados fecha o catálogo; `catalogo_metodo` é `contador da busca` \| `enumeração` |
| Documento | `id`, `estado`, `motivo`, `arquivos`, `fonte_cvm`, `urls_alternativas`, `sha256_fontes`, `verificado_em` | `sha256_fontes` é o mapa URL → SHA-256 dos bytes de cada artefato; é também o índice incremental |
| Divergência | `id`, `descricao`, `evidencias` | Preserva as duas declarações oficiais; não escolhe uma silenciosamente |

### 7.2 Estados

| Estado | Significado | Publicação permitida |
|---|---|---|
| `publicado` | Todas as versões oficiais descobertas e no escopo têm metadados válidos, arquivos e gates aprovados | Sim, somente versões aprovadas |
| `pendente` | Falta artefato, metadado, gate, licença ou decisão de contrato em pelo menos uma versão; `motivo` é obrigatório | Não publica a versão pendente; pode conservar outra versão aprovada em `arquivos` |
| `indisponivel` | Todas as origens necessárias à publicação do ato estão indisponíveis por 404/410, sem outra versão publicável | Não; soft-404 fica `pendente`, com motivo `soft-404`, conforme contrato |
| `divergente` | Fontes oficiais, identidade ou hash entram em conflito; a divergência está registrada | Não até resolução |
| `fora-de-escopo` | A exclusão foi verificada contra FR-018, com motivo verificável | Não |

`fora-de-escopo` não é o estado inicial de uma portaria sem equivalente. Os 78 casos sem correspondência no recorte curado de 65 não são automaticamente excluídos nem declarados inexistentes.

### 7.3 Regras de cobertura e falha

- O denominador é `catalogo_total` por categoria. Nunca usar 319, 241 ou 9 como denominador oficial.
- Toda entrada do catálogo no escopo aparece em `documentos` com um estado. Nenhum registro some sem explicação.
- `pendente` sempre tem `motivo`. `publicado` exige `arquivos`, `fonte_cvm` verificável quando aplicável e `sha256_fontes` com os bytes usados.
- **Agregação de versões, sem novo campo de schema:** se o original passou e o consolidado descoberto ainda não passou, o ato permanece `pendente`; `arquivos` lista apenas o original aprovado e `motivo` identifica a versão faltante e a causa, por exemplo `consolidada: tabela-nao-reproduzida`. Contar o ato uma vez em `pendentes`, sem somá-lo também em `publicados`. Não apagar o original válido por falha exclusiva do consolidado. Quando todas as versões descobertas no escopo passarem, promover o ato para `publicado`. Indisponibilidade de uma versão com outra aprovada também permanece pendência da versão, não indisponibilidade do ato inteiro.
- Cobertura 2.0 (D-13): antes de consultar a página/epígrafe, `id` e `verificado_em` são `null`; a chave operacional é `fonte_cvm`. Sem processamento, estado `pendente`, motivo `nao-processado`, arquivos e hashes vazios. Nunca publicar com identidade não confirmada nem calcular o ID pelos candidatos do catálogo.
- Ordenação estável: categorias na ordem da tabela de tipos; documentos confirmados por `id`, seguidos dos não confirmados por `fonte_cvm`.
- Falha de enumeração do catálogo, 401/403/429/5xx ou falha de validação do próprio relatório **não substitui** a cobertura anterior. A cobertura vigente permanece intacta e a falha é registrada; a coleta termina sem promover um relatório parcial.
- A cobertura nova é escrita primeiro em área temporária, validada e só então promovida de forma atômica. Se a promoção falhar, a anterior continua válida.
- Uma coleta sem mudança semântica preserva todos os bytes públicos, inclusive `gerado_em`, `coleta` e `verificado_em`; contadores correntes ficam no log e stdout. Cobertura 1.1 esclarece essa política estrita para FR-023/US6; front matter continua 1.0.
- Ausência de um item no catálogo não apaga automaticamente arquivo publicado nem cobertura anterior; a mudança vira revisão manual registrada.
- `sha256_fontes` distingue origens: o hash do HTML do DOU, o do PDF da CVM e o do Markdown não são intercambiáveis.
- Divergência entre páginas oficiais é registrada em `divergencias`, com as duas evidências; a coleta não escolhe uma delas.

## 8. Proveniência, licença e insumo auxiliar

- O acervo auxiliar externo tem 319 arquivos; 241 têm identidade compatível com o catálogo, mas isso não aprova texto, versão, anexo ou publicação. Nove casos passaram apenas por triagem exploratória, sem FR-014. Nenhum desses números é denominador de cobertura.
- Os 78 arquivos sem correspondência no recorte curado de 65 são portarias não casadas nesse recorte, não atos inexistentes na CVM. A classificação individual de escopo continua pendente.
- Metadados DOU podem enriquecer `publicacao`, `data_publicacao` e `edicao`, desde que sua URL e seu hash próprios sejam verificados e rastreados. Eles não provam `fonte_cvm`, vigência, relações ou anexos e não substituem `fonte`/`sha256_fonte` do corpo quando este vem de outro artefato.
- Texto oficial pode ser coletado diretamente da CVM. A licença da compilação auxiliar externa é `UNVERIFIED`; enquanto não verificada, corpo proveniente dessa compilação fica pendente com motivo de licença. A coleta oficial direta não depende dessa licença.
- A origem auxiliar (URL, revisão, caminho e digest do arquivo) é registrada em registro auxiliar, não em campos públicos não contratados. Qualquer extensão do front matter ou do `cobertura.json` exige decisão de schema, justificativa e versionamento.
- Tabelas extraídas de DOCX/DOC são auxiliares. Só podem apoiar a conversão quando a proveniência de **todos** os artefatos envolvidos estiver registrada: URL, bytes, SHA-256, tipo de conteúdo, data de coleta e indicação de qual artefato originou o corpo. Sem essa cadeia, a tabela não é usada e o documento fica pendente; nenhum campo público novo é criado para “resolver” a lacuna.
- Um DOCX/DOC auxiliar não substitui automaticamente o corpo PDF ou HTML, não vira `fonte` por conveniência e não altera `formato_fonte` do artefato principal.

## 9. Invariantes de aceite do modelo

1. Todo `DocumentMetadata` publicado tem `fonte`, `sha256_fonte` e `baixado_em`; o hash corresponde aos bytes do artefato de `fonte`.
2. Nenhum hash de Markdown é usado como `sha256_fonte` ou em `sha256_fontes`.
3. `revogada: false` só existe com evidência oficial registrada; sem evidência, `null`.
4. `alterada_por` e `revogada_por` vazios significam “nenhuma encontrada na fonte consultada”; não são prova universal.
5. `versao_texto` permanece com os dois valores contratuais; republicações não são forçadas a nenhum deles.
6. As republicações 59/2021, 100/2022 e 110/2022 ficam pendentes por artefato, com os motivos definidos no plano; nenhuma é completada silenciosamente.
7. Tipo, ID e pasta são derivados da epígrafe; 870/2021 e os Pareceres 39/2021 e 40/2022 não podem gerar IDs ou pastas errados.
8. Documento sem número ou sem ano não recebe número, ano ou ID sintético; a decisão de contrato precede a publicação.
9. Nenhum campo obrigatório é omitido; campo anulável desconhecido é `null`, não string vazia nem valor inventado.
10. `fonte_cvm` não é inventada; quando não verificável, a proveniência ambígua bloqueia o artefato.
11. A cobertura usa o catálogo oficial como denominador e não usa 319/241/9 como totais.
12. Falha de catálogo ou de coleta não apaga nem substitui a cobertura anterior.
13. Tabela não reproduzível, anexo ausente, OCR pendente ou gate de fidelidade reprovado impedem a publicação.
14. Texto externo só é publicado após licença e proveniência verificadas; a coleta oficial direta segue independente.
15. Tabela Word auxiliar só é usada com proveniência completa de todos os artefatos e sem campos públicos não contratados.

## 10. Não decidido nesta etapa

- Forma de identidade de FAQ, manual ou outro documento sem número/ano: exige decisão de contrato antes de publicar; não criar número.
- Tratamento de republicação como valor de `versao_texto` ou entidade separada: exige decisão de schema; o enum atual não é ampliado.
- Classificação individual das 78 portarias sem correspondência no recorte curado: `UNVERIFIED`; não converter em `fora-de-escopo` por conveniência.
- Licença da compilação externa: `UNVERIFIED`; não confundir com a licença do código.
- FR-014 dos 10 casos da triagem e dos demais candidatos: não executado; 9/10 não é certificação.
- Necessidade de qualquer campo público adicional para origem auxiliar, revisão ou licença: não decidida; não implementar por antecipação.
- Volume, tempo e qualidade de OCR, tabelas e PDFs nas fases posteriores: `UNVERIFIED`.
- Deriva do catálogo oficial após a data da pesquisa: `UNVERIFIED`.
