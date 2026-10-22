# Feature Specification: Acervo de normas da CVM em Markdown

**Feature Branch**: `001-acervo-cvm`

**Created**: 2026-10-22

**Status**: Draft

**Input**: User description: "Reunir as resoluções e normas da CVM em um repositório aberto, um `.md` por documento, formatado com cuidado, aproveitando o que já existe em acervos abertos e buscando na fonte oficial da CVM o que falta."

Insumos: [research.md](research.md) (D-1 a D-6), [research/decisoes-usuario.md](research/decisoes-usuario.md) (D-U1 a D-U11), [research/inventario.md](research/inventario.md), [research/fontes-cvm.md](research/fontes-cvm.md), [research/pdf-para-md.md](research/pdf-para-md.md) e a constituição v1.0.0.

## Clarifications

### Session 2026-10-22

- Q: Onde roda a coleta periódica exigida por SC-006? → A: GitHub Actions agendado; commits de atualização de dados saem como `github-actions[bot]`, commits de código continuam do mantenedor (D-U12).

## User Scenarios & Testing *(mandatory)*

Atores: **leitor** (pessoa que consulta uma norma no GitHub ou em clone local), **sistema consumidor** (programa que lê o acervo para busca ou citação) e **mantenedor** (quem roda a coleta e revisa pendências).

### User Story 1 - Ler uma resolução da CVM com texto fiel (Priority: P1)

O leitor abre `reguladores/cvm/resolucoes/<ano>/` e encontra cada resolução como um `.md` com cabeçalho de metadados, título, artigos, parágrafos, incisos e anexos na ordem da fonte oficial, e o link para conferir.

**Why this priority**: resoluções são a família vigente e mais consultada (249 registros) e quase todas têm íntegra HTML oficial; é o menor recorte que já entrega um acervo útil e prova o formato.

**Independent Test**: coletar só a família de resoluções; abrir 10 arquivos sorteados e comparar com a página oficial: mesmo texto, mesma ordem, metadados preenchidos ou `null`.

**Acceptance Scenarios**:

1. **Given** uma resolução com íntegra HTML oficial, **When** a coleta roda, **Then** o `.md` contém cabeçalho com `titulo`, `tipo`, `numero`, `data`, `fonte`, `sha256_fonte`, `baixado_em`, um `# Título` e todo o corpo, com `**Art. Nº**` e `**§ Nº**` em negrito e cada inciso e alínea em parágrafo próprio.
2. **Given** uma resolução cuja página não diz se ela foi revogada, **When** o `.md` é gerado, **Then** `revogada` é `null`.
3. **Given** uma resolução com anexo dentro da íntegra, **When** o `.md` é gerado, **Then** o anexo aparece como título próprio e consta em `anexos` com rótulo, URL e hash.

---

### User Story 2 - Saber qual texto vale hoje (Priority: P2)

O leitor encontra, ao lado do texto original, o texto consolidado publicado pela CVM, e vê quais normas alteraram ou revogaram aquela.

**Why this priority**: a pergunta prática é "qual regra vale hoje"; o texto original sozinho não responde. É o principal ganho sobre acervos baseados apenas no Diário Oficial.

**Independent Test**: para a Resolução 175, existem dois arquivos (original e consolidado), cada um com seu `versao_texto` e hash, e `alterada_por` lista as alteradoras encontradas na página oficial.

**Acceptance Scenarios**:

1. **Given** uma norma com consolidado oficial, **When** a coleta roda, **Then** são publicados dois arquivos distintos, `versao_texto: "publicação original"` e `versao_texto: "consolidada"`.
2. **Given** duas páginas oficiais que divergem sobre as alterações de uma norma, **When** a coleta roda, **Then** ambas as informações são preservadas e a divergência aparece no relatório de cobertura.
3. **Given** um consolidado substituído na mesma URL, **When** a coleta seguinte roda, **Then** a mudança de hash gera nova versão e um commit com a data real da coleta.

---

### User Story 3 - Consultar as demais normas, inclusive as antigas (Priority: P3)

O leitor encontra instruções, deliberações, pareceres de orientação, decisões conjuntas e portarias normativas, inclusive documentos antigos disponíveis só em PDF.

**Why this priority**: completa a parte normativa do acervo (≈ 1.600 registros), mas exige conversão de PDF e, em parte, OCR.

**Independent Test**: coletar uma família por vez; sortear documentos por década e conferir texto e metadados com a fonte.

**Acceptance Scenarios**:

1. **Given** uma norma disponível só em PDF com texto, **When** a coleta roda, **Then** o `.md` sai sem cabeçalhos e rodapés repetidos, com palavras hifenizadas unidas e URLs preservadas.
2. **Given** um PDF sem camada de texto, **When** a coleta roda, **Then** o texto vem de OCR e o `.md` traz aviso visível de que pode conter erros de reconhecimento.
3. **Given** uma página com tabela, **When** a conversão não consegue reproduzir a tabela fielmente, **Then** o documento fica pendente no relatório em vez de ser publicado com a tabela achatada.
4. **Given** uma portaria administrativa (RH, TI, orçamento, comitês), **When** a coleta roda, **Then** ela não é publicada.

---

### User Story 4 - Distinguir regra de orientação (Priority: P4)

O leitor e o sistema consumidor encontram ofícios circulares, notas explicativas, perguntas e respostas e manuais com `tipo` de orientação, separados das normas.

**Why this priority**: esse material explica como cumprir as regras e é muito usado, mas citá-lo como regra é erro; precisa de classe própria.

**Independent Test**: todo arquivo sob as pastas de orientação tem classe `orientação` e subtipo; nenhum aparece sob as pastas de normas.

**Acceptance Scenarios**:

1. **Given** um ofício circular, **When** é publicado, **Then** traz classe `orientação`, subtipo `oficio-circular`, a unidade emissora (SEP, SIN…) e o ano, e sua identidade não depende só do número.
2. **Given** um ofício que é determinação a um regulado, **When** é publicado, **Then** traz marcação explícita dessa natureza.

---

### User Story 5 - Acompanhar normas em discussão (Priority: P5)

O leitor encontra as audiências e consultas públicas como minutas, com edital, relatório de análise e o link para a norma que resultou delas.

**Why this priority**: mostra o que vem por aí e o histórico de cada norma, mas não é regra vigente.

**Independent Test**: para a Consulta Pública SDM 04/2024, o `.md` tem classe `minuta`, fase `Norma publicada` e vínculo com a Resolução 235.

**Acceptance Scenarios**:

1. **Given** uma audiência com fase `Norma publicada`, **When** é publicada, **Then** o `.md` liga para a norma resultante.
2. **Given** uma audiência com manifestações de participantes, **When** é publicada, **Then** as manifestações aparecem apenas como link para a página oficial, sem texto nem nomes.
3. **Given** uma audiência `Em análise`, **When** sua fase muda na fonte, **Then** a coleta seguinte atualiza a fase.

---

### User Story 6 - Manter o acervo atualizado e auditável (Priority: P2)

O mantenedor roda a coleta periodicamente; normas novas e alteradas entram em commits com a data da coleta, e um relatório mostra o que está publicado, pendente e com divergência.

**Why this priority**: sem atualização o acervo envelhece e perde valor; sem relatório, não se sabe o que falta.

**Independent Test**: rodar a coleta duas vezes sem mudança na fonte gera zero alterações; simular uma norma nova gera exatamente um arquivo novo e uma entrada no relatório.

**Acceptance Scenarios**:

1. **Given** nenhuma mudança na fonte, **When** a coleta roda de novo, **Then** nenhum arquivo muda.
2. **Given** uma norma nova no catálogo ou no RSS, **When** a coleta roda, **Then** ela é publicada e registrada no relatório.
3. **Given** que a fonte responde 403 ou 429, **When** a coleta roda, **Then** ela recua e para sem tentar contornar o bloqueio, e registra a falha.

### Edge Cases

- Contador do catálogo oscila entre duas execuções (ex.: 342/343): a coleta usa a enumeração real e registra a divergência.
- URL de anexo devolve página HTML com status 200 no lugar do PDF (soft-404): o documento fica pendente, não é publicado com conteúdo errado.
- URL antiga responde 410: registrada como indisponível, sem gerar arquivo.
- Mesmo documento em dois caminhos (`/legislacao/...` e `/assuntos/...`): uma identidade, URL canônica e URL de origem registradas.
- Ofícios com mesmo número em superintendências diferentes: identidades distintas.
- Página de norma sem data ou com data só no corpo: `data` vem da epígrafe; se ausente, `null`.
- Documento com camada de texto parcial (algumas páginas sem texto): OCR só nessas páginas, com aviso.
- Normas publicadas originalmente apenas no Diário Oficial e já disponíveis em acervo aberto de terceiro: reaproveitadas como `publicação original`, conferidas contra a fonte da CVM quando houver.

## Requirements *(mandatory)*

### Functional Requirements

**Descoberta e coleta**

- **FR-001**: O sistema MUST inventariar cada categoria do escopo a partir da busca oficial do portal de legislação da CVM, enumerando todas as páginas de resultado, e registrar a contagem obtida.
- **FR-002**: O sistema MUST usar o RSS de legislação e de audiências como sinal de novidade e reconciliar periodicamente com o catálogo completo.
- **FR-003**: O sistema MUST respeitar o `robots.txt` de cada host, fazer uma requisição por vez por host com intervalo mínimo configurável, identificar-se no User-Agent e não acessar `dados.cvm.gov.br/api/`.
- **FR-004**: O sistema MUST recuar e interromper diante de respostas 401, 403 ou 429 e registrar a falha, sem contornar bloqueios.
- **FR-005**: O sistema MUST guardar em cache local os bytes originais baixados e seu SHA-256, e não reconverter documento cujo hash não mudou.

**Conversão e formato**

- **FR-006**: O sistema MUST preferir a íntegra HTML oficial quando existir; senão, o PDF com camada de texto; e só usar OCR em páginas sem texto.
- **FR-007**: O sistema MUST produzir um `.md` por documento em `reguladores/cvm/<tipo>/<ano>/`, UTF-8 com LF, com cabeçalho YAML, `# Título` e corpo.
- **FR-008**: O cabeçalho MUST conter `titulo`, `orgao`, `tipo`, `numero`, `data`, `revogada`, `versao_texto`, `fonte`, `baixado_em` e `sha256_fonte`, e quando aplicável `publicacao`, `data_publicacao`, `fonte_cvm`, `alterada_por`, `revogada_por`, `anexos` e `unidade`.
- **FR-009**: Valores que a fonte não informa MUST ser `null`; `revogada` só é `true` ou `false` com evidência na página oficial.
- **FR-010**: O normalizador MUST marcar em negrito o início de `Art.`, `§` e `Parágrafo único`, manter incisos e alíneas em parágrafos próprios, promover `ANEXO`, `CAPÍTULO`, `SEÇÃO` e `TÍTULO` a títulos, remover cabeçalhos e rodapés repetidos por posição na página e unir hifenização preservando URLs, códigos e hífens lexicais.
- **FR-011**: Tabelas MUST ser publicadas como tabela (Markdown ou HTML) que preserve células, células vazias e mesclagens; quando isso não for possível, o documento MUST ficar pendente.
- **FR-012**: Texto obtido por OCR MUST trazer aviso visível no início do corpo.
- **FR-013**: Original e consolidado MUST ser arquivos distintos, identificados por `versao_texto`.
- **FR-014**: Cada documento MUST passar por portões de fidelidade (sequência de tokens, contagem de artigos, parágrafos, incisos e anexos comparada com a fonte) antes de ser publicado; falha vira pendência no relatório.

**Escopo e classificação**

- **FR-015**: O acervo MUST incluir, com classe `norma`: resoluções, instruções, deliberações, pareceres de orientação, decisões conjuntas e portarias com efeito normativo externo.
- **FR-016**: O acervo MUST incluir, com classe `orientação` e subtipo: ofícios circulares, notas explicativas, perguntas e respostas, manuais e guias; ofícios de determinação recebem marcação própria.
- **FR-017**: O acervo MUST incluir audiências e consultas públicas com classe `minuta`, fase, edital, relatório de análise e vínculo com a norma resultante, sem copiar manifestações de participantes.
- **FR-018**: O acervo MUST NOT incluir portarias administrativas, decisões do Colegiado, processos sancionadores, leis e decretos federais, textos de pronunciamentos CPC/ICPC/OCPC nem dados pessoais.
- **FR-019**: Ofícios MUST ser identificados por unidade emissora, número e ano; um documento presente em dois caminhos MUST ter uma única identidade com URL canônica e URL de origem.
- **FR-020**: O sistema MUST reaproveitar textos de publicação original já existentes em acervo aberto de terceiro sob licença compatível, registrando a origem, e conferi-los com a fonte da CVM quando houver.

**Atualização e auditoria**

- **FR-021**: Cada coleta MUST gerar commits com a data real da coleta e mensagem que descreva o lote.
- **FR-022**: O sistema MUST manter um relatório de cobertura legível por pessoas e por máquina, com, por categoria: total no catálogo, publicados, pendentes com motivo (incluindo `soft-404`), indisponíveis (404/410) e divergências entre fontes. Um ato com original aprovado e consolidado pendente conta uma vez como pendente, conservando em `arquivos` apenas as versões aprovadas.
- **FR-023**: Uma coleta sem mudança na fonte MUST NOT alterar nenhum arquivo publicado.
- **FR-024**: O sistema MUST permitir rodar a coleta por categoria e por documento, para revisão e correção pontual.

### Key Entities

- **Documento**: um ato ou material publicado pela CVM; identidade = classe + tipo + (unidade) + número + ano; tem uma ou mais versões.
- **Versão de texto**: publicação original ou consolidada de um documento; tem fonte, hash, data de coleta e o `.md` gerado.
- **Artefato de origem**: arquivo baixado (HTML, PDF, DOC/DOCX) com URL, MIME, hash e data; um documento pode ter vários (íntegra, consolidado, anexos).
- **Anexo**: parte normativa ou suplemento de um documento, com rótulo, URL e hash próprios.
- **Relação**: `altera`, `revoga` ou `resulta de` (minuta → norma), com URL e contexto onde foi encontrada.
- **Registro de cobertura**: estado de cada documento do catálogo (publicado, pendente, indisponível, divergente) e motivo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% dos registros do catálogo no escopo (≈ 2.990) aparecem no relatório de cobertura como publicados, pendentes com motivo ou indisponíveis; nenhum registro some sem explicação.
- **SC-002**: Em amostra de 50 documentos com íntegra HTML oficial, o corpo publicado reproduz a sequência de palavras da fonte em pelo menos 99,5% e não perde nenhum artigo, parágrafo, inciso ou anexo.
- **SC-003**: Nenhum arquivo publicado contém tabela achatada em texto corrido; todo documento com tabela não reproduzível está pendente.
- **SC-004**: 100% dos arquivos publicados têm `fonte`, `sha256_fonte` e `baixado_em`; nenhum tem `revogada` diferente de `null` sem evidência na página oficial.
- **SC-005**: Duas coletas seguidas sem mudança na fonte produzem zero diferenças nos arquivos publicados.
- **SC-006**: Uma norma nova publicada no catálogo da CVM aparece no acervo em até 7 dias.
- **SC-007**: O registro de requisições de uma coleta completa mostra zero acessos a caminhos proibidos pelo `robots.txt` e nenhum intervalo entre requisições ao mesmo host abaixo do mínimo configurado.
- **SC-008**: Nenhum arquivo publicado contém texto de manifestação de participante de audiência pública.
- **SC-009**: Para as resoluções (User Story 1), 100% das 249 do catálogo estão publicadas ou pendentes com motivo na primeira entrega.

## Assumptions

- O acervo publica dados e o coletor; busca por API ou servidor MCP fica para outra feature (pendente em D-U1).
- A coleta periódica roda em GitHub Actions agendado (D-U12), com Poppler disponível no runner; a coleta também pode ser rodada localmente pelo mantenedor.
- O portal `conteudo.cvm.gov.br` continua sendo a fonte de verdade do catálogo; os sitemaps servem só para descobrir anexos, pois estão desatualizados desde 09/06/2026.
- Os endpoints internos de busca do portal podem mudar sem aviso; quebras viram falha registrada, não publicação parcial silenciosa.
- Vigência por dispositivo não é informada; o consolidado reflete o que a CVM publicava na data da coleta.
- A classificação das 2 portarias de fronteira é revisada manualmente pelo mantenedor.
- A amostragem de PDFs antigos mediu 78 PDFs e 676 páginas sem página de texto vazio, sem inferência populacional; OCR continua obrigatório quando necessário. Ver D-10 em `research.md`.
