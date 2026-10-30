# Tasks: Acervo de normas da CVM

**Input**: [plan.md](plan.md), [spec.md](spec.md), [data-model.md](data-model.md), decisões D-7..D-10 e contratos.

Testes são obrigatórios em toda história. Uma caixa só é marcada após execução em commit exato; um gate novo exige sabotagem. Documentação de desenho não equivale a implementação. `blockedBy` representa dependência real; `conflictKeys` impede escrita paralela no mesmo módulo. Todos os testes são `unittest` com fixtures reais e saída esperada, sem dependência de rede por padrão.

## Fase 1 — Setup

- [x] T001 Criar pacote Python 3.12 e modelos comuns em `pyproject.toml`, `src/cvm_archive/__init__.py`, `src/cvm_archive/models.py` e estrutura de testes em `tests/`; teste `tests/unit/test_models.py`; blockedBy=[]; conflictKeys=[package,models]; risco=baixo. Validar hash exato, bytes imutáveis e dataclasses Artifact/CatalogEntry/Conversion; nenhuma funcionalidade fictícia.

## Fase 2 — Fundação

Revisão de 29/10/2026: T002 tem implementação integrada e 37 testes executados, mas a cadeia
oficial atual de robots expôs limitação de inicialização ainda pendente. T004 tem 43 testes
positivos, porém oito contraexemplos executados impedem seu aceite. Ver a
[reconferência](research/reconferencia-2026-10-29.md) e a [revisão HTML](research/revisao-html.md).
Naquele checkpoint ambos estavam abertos. T002 foi corrigido em `903c81d`, com 39 testes e
consulta HTTP real pela cadeia oficial, sem cache preparado. Isso encerra o ticket de transporte,
não os critérios de aceite de coleta completa ou agendamento. T004 foi corrigido em `8bbc7aa`,
com 14 regressões adicionais e 57 testes na branch do ticket; a integração executou 88 testes.
Os oito casos agora preservam o conteúdo ou geram pendência explícita. SC-002 continua aberto.

T003 foi revisado e concluído em `cc58752`: 45 testes na branch do ticket, incluindo enumeração
das cinco páginas da fixture oficial, 249 URLs distintas e conferência dos 17 arquivos pelo
manifesto de proveniência. Sete contraexemplos falharam antes das correções e passaram depois:
contador ausente, data de publicação confundida com data do ato, revogação de outro ato,
negação de revogação, status conflitante, título sem epígrafe e indicação expressa de vigência.
A expectativa incorreta `181/22` foi corrigida para `181/23`, conforme a fixture oficial.
A integração executou 125 testes. Não houve HTTP novo para T003; fixtures não certificam a
atualidade de todas as relações, e as versões/divergências continuam no escopo de T007.

- [x] T002 [P] Implementar transporte educado em `src/cvm_archive/fetch/client.py` e `tests/unit/test_fetch.py`; blockedBy=[T001]; conflictKeys=[fetch]; risco=alto. FR-003..005/SC-007: robots por host, redirecionamento, UA, intervalo >=5s, 401/403/429/5xx, cache bruto e log; testes de relógio falso e sabotagem de acesso proibido, mais consulta real controlada da cadeia oficial.
- [x] T003 [P] Implementar catálogo e metadados de resoluções em `src/cvm_archive/sources/catalog.py`, `sources/document.py`, `tests/unit/test_sources.py` e fixtures HTML; blockedBy=[T001]; conflictKeys=[sources]; risco=alto. FR-001/009/019: todas as páginas, contagem incoerente, aliases, epígrafe, data, revogação explícita, relações e anexos; selector não confunde PDF próprio/site com alteradoras.
- [x] T004 [P] Implementar conversão estrutural HTML e normalização em `src/cvm_archive/convert/html.py`, `normalize/text.py`, `tests/unit/test_html.py` e fixtures esperadas; blockedBy=[T001]; conflictKeys=[html,normalize]; risco=alto. FR-006/010/011: dispositivos, entidades, anexos e tabelas reais; conteúdo ambíguo/estrutura não suportada gera pendência, não silêncio.

## Fase 3 — US1 / MVP de resoluções

**Teste independente:** catálogo real completo, Resolução 249 e fixture esperada; original aprovado e tudo que não for processável aparece pendente. SC-002 de 50 documentos só será aceito no fechamento, não por esta amostra mínima.

T005 foi executado em `6e55980`, com 166 testes no commit limpo, incluindo 41 contratuais novos.
Os gates rejeitam corrupção de conteúdo, metadados e estrutura; promoção com falha é revertida.
Escopo e limites em [revisão de publicação](research/revisao-publicacao.md). A coleta real pela
CLI e os critérios globais continuam em T006 e nos tickets posteriores.

T006 foi validado com código `e779a29`, dados `c21cdb5` e relatório `757ff89`: 189 testes em
commit limpo; coleta real da 249 com catálogo completo de 249, 1 publicação e 248 pendências.
A repetição após commit retornou `changed: false`, zero processados e Git limpo. Foram 15
requisições nas duas execuções, com intervalo mínimo observado de 5 s por host de conteúdo.
Ver [validação do MVP](research/validacao-mvp.md). O aceite é desta história mínima, sem
certificar o acervo completo, SC-002, PDF/OCR, outras famílias ou o agendamento.
Correção posterior `451cbf2`: o anexo incorporado também passou a constar no front matter,
com URL/hash da íntegra. Dois testes de omissão/hash incorreto foram demonstrados falhando
antes da correção; a suíte passou com 191 testes. Corpo e hash de fonte da 249 não mudaram.

- [x] T005 [US1] Implementar gates e escrita de documentos/cobertura em `src/cvm_archive/gates/fidelity.py`, `gates/metadata.py`, `publish/markdown.py`, `publish/coverage.py` e `tests/contract/test_publication.py`; blockedBy=[T001,T004]; conflictKeys=[gates,publish]; risco=alto. FR-007..014/022 e SC-003/004: schema, hash/URL, sequência, dispositivos, anexos, tabela; provar reprovação por deleção, permutação, duplicação, hash incorreto e conteúdo ausente; lista vazia não mascara anexo desconhecido.
- [x] T006 [US1] Integrar CLI e primeira coleta em `src/cvm_archive/cli.py`, `tests/integration/test_cli.py`, fixtures da Resolução 249 e dados `catalogo/`, `reguladores/`, `cobertura/`; blockedBy=[T002,T003,T004,T005]; conflictKeys=[cli,data]; risco=alto. FR-021..024/SC-005/009: catalog/collect/verify, flags, limite/lote estável, documento único, JSON changed, catálogo completo antes do lote; falha não promove saída parcial. Executar CLI em estado commitado, coleta real educada e repetição sem mudanças.

## Fase 4 — US2 / versões e relações

**Teste independente:** original/consolidado com fontes e hashes separados; um consolidado pendente não elimina original aprovado nem conta o ato duas vezes.

Checkpoint `9997a21`: 201 testes executados; republicação pendente por artefato, relação por
contexto, revogação parcial e declaração conflitante preservadas. T007 permanece aberto para
aliases, comparação entre páginas e fixtures reais complementares; ver
[revisão de versões](research/revisao-versoes.md).
Conclusão do fundamento: `e6537e6`, dados `9dc613b` e relatório `d384904`, 211 testes e
coleta/repetição reais da 175 sem promover PDF/anexos não aprovados. Aliases confirmados
agregados, URLs/candidatos preservados e divergências visíveis nos dois relatórios. O aceite
integral de US2 com dois arquivos reais da 175 depende de T010/T011; não foi certificado.

- [x] T007 [US2] Ampliar versões/relações/divergências em `src/cvm_archive/sources/document.py`, `publish/coverage.py`, `tests/integration/test_versions.py`; blockedBy=[T006]; conflictKeys=[sources,publish]; risco=alto. FR-009/013/019 e C1/C2/C4/C10/C11: Resolução 175, Deliberação 870 e Pareceres 39/40; republicações 59/100/110 pendentes por artefato, sem novo enum; evidências oficiais conflitantes preservadas e original+consolidado pendente agregados conforme modelo.

## Fase 5 — US6 / atualização e auditoria

**Teste independente:** fixtures de RSS/catalogo e duas coletas sem mudança; nova norma gera apenas o delta, bloqueio interrompe sem publicar. Runner/agendamento só são aceitos com execução externa real.

T008 implementado em `450c448`, com 222 testes e onze cenários novos sem rede. RSS real
reutilizado de bytes já auditados; catálogo completo, rotação, substituição de consolidado na
mesma URL e preservação após remoção/bloqueio verificados. Execução incremental ao vivo e SLA
permanecem UNVERIFIED; novas coletas foram adiadas. Ver
[validação incremental](research/validacao-incremental.md).

T009 implementado em `1048ef8` e documentado em `0228cc0`: 231 testes locais e no
[runner real](https://github.com/StaffeToxic/normas-cvm/actions/runs/40995070490), sem coleta
adicional. Guardas, bot, escopo de commit, parâmetros e códigos 2/3 testados. Coleta agendada,
commit/push real do bot e SC-006 continuam UNVERIFIED; o workflow de coleta não foi acionado.

- [x] T008 [US6] Implementar RSS e rechecagem incremental em `src/cvm_archive/sources/feeds.py`, `cli.py`, `tests/integration/test_incremental.py`; blockedBy=[T006,T007]; conflictKeys=[sources,cli,data]; risco=alto. FR-002/005/021..024: RSS como sinal, reconciliação integral periódica e hashes rotativos; nova URL, removido do catálogo, fonte inalterada e consolidado alterado na mesma URL; sem cache durável obrigatório.
- [x] T009 [US6] Criar verificação e coleta Actions em `.github/workflows/test.yml`, `.github/workflows/collect.yml` e `tests/contract/test_workflow.py`; blockedBy=[T008]; conflictKeys=[workflows]; risco=alto. D-U12/SC-006/007: inputs ligados à CLI, lote medido, bot só dados, data real, fila sem cancelamento, JSON de mudança e push fixo feature. Validar falha CLI sem mascarar exit, nenhum commit vazio, nenhuma escrita main; executar runner real quando disponível. SC-006 continua UNVERIFIED até ativação/observação.

## Fase 6 — US3 / demais normas e conversores

**Teste independente:** amostra por década com original/consolidado e caso sem texto, preservando tabelas ou pendência; nenhuma portaria administrativa publicada.

T010 implementado e verificado: 13 testes em `tests/integration/test_pdf.py` (total de 244 testes passando na suíte completa). Extração de layout via Poppler (`pdftotext -layout -enc UTF-8`), remoção de cabeçalhos institucionais e rodapés repetidos por zonas de página, preservação de epígrafe do ato e dispositivos legais, descarte de numeração de página isolada no rodapé, hifenização tratada (soft hyphens removidos, prefixos lexicais preservados), URLs quebradas unidas sem inserção de espaço, detecção explícita de `ocr-pendente` para PDFs sem camada de texto e `tabela-nao-reproduzida` para matrizes complexas. Fixtures com manifesto em `tests/fixtures/pdf/manifest.json`.

T011 implementado e verificado: 9 testes em `tests/integration/test_tables.py` (total de 253 testes passando na suíte completa). Extração auxiliar de tabelas de arquivos Word (.docx / OOXML) usando exclusivamente biblioteca padrão (`zipfile` e `xml.etree.ElementTree`). Suporte a mesclagem horizontal (`w:gridSpan` -> `colspan`) e vertical (`w:vMerge` -> `rowspan`), preservação de células vazias, renderização em Markdown para matrizes simples e em HTML para tabelas com spans. Gates de fidelidade validados: rejeição de grades assimétricas/sobrepostas (`tabela-estrutura-inconsistente`), rejeição de `vMerge continue` sem `restart`, detecção de parágrafos idênticos duplicados na mesma célula (caso Resolução 175 LIG gerando `tabela-discrepancia-edicao`), e arquivos inválidos (`arquivo-corrompido`). Fixtures com manifesto em `tests/fixtures/tables/manifest.json`.

- [x] T010 [US3] Implementar PDF textual e normalização por zona em `src/cvm_archive/convert/pdf.py`, `normalize/text.py`, `tests/integration/test_pdf.py`; blockedBy=[T007]; conflictKeys=[pdf,normalize]; risco=alto. FR-006/010/014: Poppler layout, cabeçalho/rodapé por posição, hifenização sem quebrar URL/código/hífen lexical; Parecer 40 e PDFs antigos com fixtures e textos esperados.
- [x] T011 [US3] Implementar tabelas auxiliares condicionais em `src/cvm_archive/convert/word.py`, `tests/integration/test_tables.py`; blockedBy=[T010]; conflictKeys=[word,html]; risco=alto. FR-011/C9/D-8: gridSpan/vMerge, células vazias, comparação por tabela e proveniência de todos os artefatos; sabotagem de merge deve falhar; LIG da 175 continua pendente sem autorização específica baseada em evidência.
- [ ] T012 [US3] Implementar OCR de páginas sem texto em `src/cvm_archive/convert/ocr.py`, `tests/integration/test_ocr.py`; blockedBy=[T010]; conflictKeys=[ocr,pdf]; risco=alto. FR-006/012/014: Tesseract por só em páginas sem texto, distinguir página branca/vetorial/raster; Portaria 109 e folha de assinatura esparsa; aviso obrigatório e gates, sem usar amostra F5 para dispensar OCR globalmente.
- [ ] T013 [US3] Ampliar catálogo/classificação e insumo externo em `src/cvm_archive/sources/`, `tests/integration/test_families.py` e registro de proveniência contratado; blockedBy=[T007,T010,T011,T012]; conflictKeys=[sources,data]; risco=alto. FR-015/018/020 e C1..C12: instruções, deliberações, pareceres, conjuntas e portarias normativas. Reuso de corpo externo somente após licença e contrato de origem compatíveis; sem confirmação manter pendência e caminho oficial. Classificar individualmente os 78, sem tomar o recorte curado como universo.

## Fase 7 — US4 / orientações

**Teste independente:** ofícios de unidades diferentes não colidem, classe orientação e natureza de determinação só explícita; FAQ/manual sem identidade contratada não é publicado.

- [ ] T014 [US4] Definir identidade sem número/ano com motivo/versionamento em `specs/001-acervo-cvm/contracts/front-matter.md` e implementar orientações em `src/cvm_archive/sources/orientations.py`, `tests/integration/test_orientations.py`; blockedBy=[T013]; conflictKeys=[contracts,sources,data]; risco=alto. FR-016/019: ofícios por unidade/número/ano, notas, FAQ, manuais/guias; nenhuma identidade sintética inventada antes de contrato. Testes de aliases e natureza.

## Fase 8 — US5 / minutas

**Teste independente:** Consulta SDM 04/2024 com vínculo à Resolução 235 e fase da fonte; nenhuma manifestação ou nome de participante copiado.

- [ ] T015 [US5] Implementar peças oficiais de consultas em `src/cvm_archive/sources/consultations.py`, `tests/integration/test_consultations.py`; blockedBy=[T014]; conflictKeys=[sources,data]; risco=alto. FR-017/018 e SC-008: edital, análise, fase e norma resultante; fixtures com manifestações como armadilha devem provar exclusão dos corpos/nomes e só link oficial permitido.

## Fase 9 — Fechamento e publicação

- [ ] T016 Verificar todas as histórias e documentação em `README.md`, `specs/001-acervo-cvm/quickstart.md` e relatório local de aceite; blockedBy=[T009,T013,T014,T015]; conflictKeys=[docs,data]; risco=alto. Executar SC-001..009 com saída e hash exato: cobertura integral, 50 HTML, tabelas, fonte/hash, repetição, SLA observado, log educado e ausência de manifestações. Cada resultado não observado permanece UNVERIFIED. Reexecutar suite após integração, verificar autoria/segredos/ausência de evidência local no histórico e somente então integrar main conforme autorização do mantenedor.

## DAG e execução

`T001 → {T002,T003,T004}; T004 → T005; {T002,T003,T004,T005} → T006 → T007; T007 → {T008,T010}; T008 → T009; T010 → {T011,T012}; {T007,T010,T011,T012} → T013 → T014 → T015; {T009,T013,T014,T015} → T016`.

Até três tickets simultâneos, cada um em worktree/branch própria, sem `conflictKeys` comuns. Exemplo inicial após T001: T002/T003/T004. Depois T007: T008 e T010 conflitam por `cli` versus `pdf,normalize` apenas se novos diffs ampliarem os arquivos; conferir a lista antes do despacho. T011/T012 não rodam juntos se ambos alterarem `pdf`. Integração e atualização das caixas ficam sob revisão central.

## Rastreabilidade

| Requisitos | Tickets |
|---|---|
| FR-001 | T003,T006,T013..T015 |
| FR-002 | T008 |
| FR-003..005 | T002,T006,T008,T009 |
| FR-006..010 | T003..T007,T010,T012 |
| FR-011..014 | T004,T005,T007,T010..T012 |
| FR-015,FR-018,FR-020 | T013..T015 |
| FR-016,FR-019 | T003,T007,T014 |
| FR-017 | T015 |
| FR-021..024 | T006,T008,T009 |
| SC-001..009 | T016, com evidência incremental nos tickets anteriores |

MVP é T001..T006, sem declarar as outras histórias entregues. A implementação parcial mantém todos os documentos descobertos no denominador aplicável e deixa pendências explícitas.
